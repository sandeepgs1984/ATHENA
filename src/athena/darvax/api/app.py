"""DarvaX's own sub-application, mounted at ``/darvax`` (ADR-010 §4).

This is a self-contained FastAPI app with its own routes and its own lifecycle.
It does **not** enter ``DASHBOARD_JS_PARTS``, modify ``index.html``, or touch
``dashboard.js``/``dashboard.css`` — ATHENA's dashboard asset-versioning
discipline is entirely unaffected because none of its assets change.

DX-1 scope: a single status endpoint that proves the mount boundary works and
reports what DarvaX has wired up. There is no product UI and no methodology
here — those are DX-4 and DX-2/DX-3 respectively.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from athena.api.errors import exception_mapper
from athena.darvax import __version__ as darvax_version
from athena.darvax.adapters import SqliteMarketDataAdapter
from athena.darvax.api.routes import router as routes_router
from athena.darvax.config import load_darvax_config
from athena.darvax.ports import DarvaxMarketDataPort
from athena.darvax.screening.sweep import SweepRunner
from athena.darvax.store import DARVAX_SCHEMA_VERSION, DarvaxRepository
from athena.errors import AthenaError


class RevalidatedStatic(StaticFiles):
    """DarvaX's static files, always revalidated.

    ``?v=`` on an asset URL only busts caches for assets the *page* references,
    and one DarvaX asset is referenced without any version at all:
    ``tab.js``, from ATHENA's ``index.html``. A cached ``tab.js`` keeps building
    the old iframe, and a cached iframe document keeps requesting the old
    bundle — so a milestone can ship, the server can restart, and the owner can
    still be looking at the previous UI with nothing obviously wrong.

    That is exactly what happened after DX-7c. Revalidation makes the whole
    class of problem go away: ``no-cache`` still allows storage, so an unchanged
    file answers **304** on its ETag. For a localhost single-user app the cost
    is a conditional request; the cost of the alternative is debugging a stale
    interface.
    """

    def file_response(self, *args: object, **kwargs: object):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


def create_darvax_app(
    *,
    config_dir: Path | str,
    market_data: DarvaxMarketDataPort,
    repo_root: Path | str | None = None,
) -> FastAPI:
    """Build the DarvaX sub-application.

    Only ever called from ``athena.api.darvax_mount`` after ATHENA has already
    determined that activation was requested — so reaching this function means
    DarvaX is enabled, and creating its database here satisfies "lazy creation
    only when enabled".

    DarvaX loads and validates its own complete configuration here; ATHENA has
    inspected nothing beyond the activation flag (ADR-010 §8).
    """
    config = load_darvax_config(config_dir)

    # SU-6 (ADR-011): DarvaX applies its own universe from its own config. The
    # seam stays methodology-blind — it passes an unscoped adapter and knows
    # nothing about universes. Duck-typed so a test double without the method
    # keeps working.
    if config.universe is not None and hasattr(market_data, "with_universe"):
        market_data = market_data.with_universe(config.universe)

    db_path = Path(config.database.path)
    if not db_path.is_absolute():
        base = Path(repo_root) if repo_root is not None else Path.cwd()
        db_path = base / db_path
    store = DarvaxRepository(db_path)
    store.initialize()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        store.close()

    app = FastAPI(
        lifespan=lifespan,
        title="DarvaX (satellite)",
        version=darvax_version,
        description=(
            "Experimental / Unvalidated. DarvaX is a parallel advisory lane and "
            "never contributes to ATHENA's scoring, confidence, risk, Decision, "
            "TradePlan, or universe (ADR-010)."
        ),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.darvax_config = config
    app.state.darvax_store = store
    app.state.darvax_market_data = market_data
    # One sweep coordinator per mounted app, not a module global: the runner's
    # lifetime is this sub-application's, so two apps cannot contend over one
    # another's sweeps and there is no hidden process-wide state (DX-6b).
    app.state.darvax_sweep_runner = SweepRunner(
        market_data=market_data,
        store=store,
        config=config,
        darvax_version=darvax_version,
    )

    # A mounted sub-application does not inherit the parent's exception
    # handlers, so DarvaX registers its own. Without this an authentication
    # rejection — an AthenaError raised by the guard DarvaX delegates to —
    # escapes as a crash instead of a clean 401/403. The status mapping is
    # ATHENA's own `exception_mapper`, reused rather than reinvented so the two
    # lanes cannot drift apart on what a given failure means.
    @app.exception_handler(AthenaError)
    async def _athena_error(request: Request, exc: AthenaError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "darvax")
        problem = exception_mapper.classify(
            exc,
            instance=str(request.url.path),
            request_id=request_id,
            correlation_id=request_id,
        )
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(mode="json", exclude_none=True),
            media_type="application/problem+json",
        )

    app.include_router(routes_router)

    # DarvaX's own static assets, served from its own directory. These never
    # enter ATHENA's DASHBOARD_JS_PARTS and never touch dashboard.js/css, so
    # ATHENA's asset-versioning discipline is unaffected (ADR-010 §4).
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount(
        "/static", RevalidatedStatic(directory=str(static_dir)), name="darvax-static"
    )

    @app.get("/", include_in_schema=False)
    def darvax_index() -> FileResponse:
        """DarvaX's own page — a separate surface, not an ATHENA dashboard tab.

        Served ``no-cache`` so the browser revalidates the document on every
        load. The ``?v=`` query on the CSS and JS only busts those files *once
        the new HTML has been fetched* — cache the document and the version
        bump can never be seen, which is precisely what happened after DX-7c:
        the dashboard tab embeds this page in a lazy iframe, so the owner
        restarted onto new code and still saw the previous bundle.

        ``no-cache`` means "revalidate", not "do not store": the response is a
        304 whenever the file is unchanged, so this costs a conditional request
        rather than a re-download.
        """
        return FileResponse(
            static_dir / "index.html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )

    @app.get("/status")
    def darvax_status() -> dict[str, object]:
        """What DarvaX has wired up. No market data, no methodology output."""
        return {
            "module": "darvax",
            "version": darvax_version,
            "enabled": config.enabled,
            "status": "EXPERIMENTAL_UNVALIDATED",
            "milestone": "DX-1 (isolation foundation only — no trading logic)",
            "schema_version": DARVAX_SCHEMA_VERSION,
            "database_path": store.path,
        }

    return app


__all__ = ["SqliteMarketDataAdapter", "create_darvax_app"]
