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

from fastapi import FastAPI

from athena.darvax import __version__ as darvax_version
from athena.darvax.adapters import SqliteMarketDataAdapter
from athena.darvax.config import load_darvax_config
from athena.darvax.ports import DarvaxMarketDataPort
from athena.darvax.store import DARVAX_SCHEMA_VERSION, DarvaxRepository


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
