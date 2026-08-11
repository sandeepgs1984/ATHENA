"""FastAPI application factory with lifespan management (P8.1).

Coordinates CORS, custom middlewares, generic exception mapping, and API routing.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from athena.api.config import APISettings, api_settings_from_env
from athena.api.darvax_mount import mount_darvax_if_enabled
from athena.api.errors import exception_mapper
from athena.api.platform.health import router as platform_health_router
from athena.api.platform.info import router as platform_info_router
from athena.api.platform.metadata import router as platform_metadata_router
from athena.api.platform.middleware import PlatformMiddleware
from athena.api.platform.problem_details import ProblemDetail
from athena.api.platform.version import router as platform_version_router
from athena.api.security.audit import LoggingAuditSink
from athena.api.security.dependencies import get_session_store, get_user_repository
from athena.api.security.hashing import BcryptPasswordHasher
from athena.api.security.login_limiter import LoginAttemptLimiter, LoginLimitPolicy
from athena.api.security.owner_seed import seed_owner_user
from athena.api.security.service import AuthService
from athena.api.security.token import HMAC256TokenSigner, TokenClaimsFactory
from athena.api.v1.router import router as v1_router
from athena.errors import AthenaError
from athena.ops.kite_session import KiteSessionService

logger = logging.getLogger(__name__)

# dashboard.js concern-based source split (owner-requested maintainability
# refactor — the file had grown past 6,100 lines in one closure). Classic
# <script> tags have no browser-native multi-file mechanism (unlike CSS's
# @import, which the earlier dashboard.css split relies on), so this list is
# concatenated server-side, in this exact order, into the single script the
# browser requests at /dashboard/dashboard.js — reproducing the original
# file's single document.addEventListener("DOMContentLoaded", ...) closure
# byte-for-byte (every statement's source text unchanged, only relocated;
# verified with a standalone content-equality script during the refactor).
# Read fresh on every request (not cached) so editing a js/*.js file is
# reflected on the next reload, same as every other static asset here.
DASHBOARD_JS_PARTS: tuple[str, ...] = (
    "_header.js",
    "00-state-and-dom.js",
    "01-auth.js",
    "02-kite-gate.js",
    "03-app-shell.js",
    "04-api-client.js",
    "05-utils.js",
    "06-ui-helpers.js",
    "07-decision-format.js",
    "08-portfolio.js",
    "09-market-intelligence.js",
    "10-strategies-backtests.js",
    "11-decision-state.js",
    "12-decisions-list.js",
    "13-decision-brief-core.js",
    "14-decision-brief-analysis.js",
    "15-decision-brief-context.js",
    "16-decision-brief-chart.js",
    "17-decision-compare.js",
    "18-decision-brief-trace.js",
    "19-decision-brief-history.js",
    "20-operations.js",
    "21-bootstrap.js",
    "_footer.js",
)


def assemble_dashboard_js(static_dir: str) -> str:
    """Concatenate DASHBOARD_JS_PARTS, in order, into the served dashboard.js."""
    js_dir = Path(static_dir) / "js"
    parts = []
    for name in DASHBOARD_JS_PARTS:
        file_path = js_dir / name
        if not file_path.is_file():
            raise FileNotFoundError(f"dashboard.js part missing: {file_path}")
        parts.append(file_path.read_text(encoding="utf-8"))
    return "".join(parts)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifecycle management.

    Replaces deprecated startup/shutdown events. Future platform worker
    registration, database connectivity, or scheduler initialization hooks here.
    """
    logger.info("ATHENA Platform API starting up")
    yield
    repo = getattr(app.state, "sqlite_repo", None)
    if repo is not None:
        try:
            repo.close()
        except Exception:
            logger.exception("Failed to close SQLite repository on shutdown")
    logger.info("ATHENA Platform API shutting down")


def _register_exception_handlers(app: FastAPI) -> None:
    """Register API exception handlers mapping domain/generic errors to ProblemDetails."""

    @app.exception_handler(AthenaError)
    async def athena_error_handler(
        request: Request, exc: AthenaError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", request_id)
        detail = exception_mapper.classify(
            exc, str(request.url.path), request_id, correlation_id
        )
        headers = {"Content-Type": "application/problem+json"}
        retry_after = getattr(exc, "retry_after_seconds", None)
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return JSONResponse(
            status_code=detail.status,
            content=detail.to_dict(),
            headers=headers,
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", request_id)
        detail = exception_mapper.classify(
            exc, str(request.url.path), request_id, correlation_id
        )
        return JSONResponse(
            status_code=detail.status,
            content=detail.to_dict(),
            headers={"Content-Type": "application/problem+json"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", request_id)
        # Format list of validation errors
        errors = exc.errors()
        extensions = {"validation_errors": errors}

        # Build message detailing the failure
        messages = []
        for error in errors:
            loc = " -> ".join(str(x) for x in error.get("loc", []))
            msg = error.get("msg", "Unknown error")
            messages.append(f"{loc}: {msg}")
        detail_msg = "; ".join(messages) if messages else "Validation failed"

        detail = exception_mapper.classify(
            exc, str(request.url.path), request_id, correlation_id
        )
        # Override fields for validation specificity
        detail = ProblemDetail(
            type="https://athena.internal/errors/validation-error",
            title="Validation Failed",
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail_msg,
            instance=str(request.url.path),
            request_id=request_id,
            correlation_id=correlation_id,
            invalid_params=errors,
            extensions=extensions,
        )

        return JSONResponse(
            status_code=detail.status,
            content=detail.to_dict(),
            headers={"Content-Type": "application/problem+json"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse | FileResponse:
        if exc.status_code == 404 and request.url.path.startswith("/dashboard"):
            static_dir = os.path.join(os.path.dirname(__file__), "static")
            index_path = os.path.join(static_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)

        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", request_id)

        detail = ProblemDetail(
            type=f"https://athena.internal/errors/http-{exc.status_code}",
            title=exc.detail if exc.detail else "HTTP Error",
            status=exc.status_code,
            detail=exc.detail if exc.detail else "HTTP Error encountered",
            instance=str(request.url.path),
            request_id=request_id,
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=detail.status,
            content=detail.to_dict(),
            headers={"Content-Type": "application/problem+json"},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        correlation_id = getattr(request.state, "correlation_id", request_id)
        detail = exception_mapper.classify(
            exc, str(request.url.path), request_id, correlation_id
        )
        return JSONResponse(
            status_code=detail.status,
            content=detail.to_dict(),
            headers={"Content-Type": "application/problem+json"},
        )


def create_app(settings: APISettings | None = None) -> FastAPI:
    """Application factory for ATHENA Platform API.

    Ensures clean setup and lifecycle management.
    """
    # Load .env manually if it exists
    from athena.config.env import load_dotenv

    load_dotenv()

    settings = settings or api_settings_from_env()
    _secret_bytes = len(settings.security.jwt_secret.encode("utf-8"))
    if _secret_bytes < 32:
        raise ValueError(
            "security.jwt_secret must be at least 32 UTF-8 bytes for HS256 "
            f"(got {_secret_bytes}). Set ATHENA_JWT_SECRET or "
            "ATHENA_OWNER_PASSWORD_HASH."
        )

    app = FastAPI(
        title=settings.app.title,
        description=settings.app.description,
        version=settings.app.version,
        docs_url=settings.app.docs_url,
        redoc_url=settings.app.redoc_url,
        openapi_url=settings.app.openapi_url,
        lifespan=lifespan,
    )

    # Initialize Security components on app state
    app.state.api_settings = settings
    app.state.token_signer = HMAC256TokenSigner(
        secret_key=settings.security.jwt_secret,
        issuer=settings.security.jwt_issuer,
        audience=settings.security.jwt_audience,
        algorithm=settings.security.jwt_algorithm,
    )
    app.state.claims_factory = TokenClaimsFactory(settings.security)
    app.state.auth_service = AuthService(
        user_repo=get_user_repository(),
        session_store=get_session_store(),
        hasher=BcryptPasswordHasher(rounds=settings.security.bcrypt_rounds),
        signer=app.state.token_signer,
        claims_factory=app.state.claims_factory,
        audit_sink=LoggingAuditSink(),
    )
    app.state.login_limiter = LoginAttemptLimiter(
        LoginLimitPolicy(
            max_failures=settings.security.login_max_failures,
            window_minutes=settings.security.login_failure_window_minutes,
            lockout_minutes=settings.security.login_lockout_minutes,
        )
    )
    seed_owner_user(get_user_repository())
    config_dir = Path(os.environ.get("ATHENA_CONFIG_DIR", "config")).resolve()
    from athena.config.loader import load_validation_config

    app.state.intraday_freshness_minutes = (
        load_validation_config(config_dir).freshness.intraday_max_minutes_behind
    )
    app.state.kite_session_service = KiteSessionService(
        repo_root=config_dir.parent,
        config_dir=config_dir,
    )

    # Initialize Platform Infrastructure Providers on app state
    from athena.api.dependencies import get_build_info_provider, get_metadata_provider, wire_sqlite_providers
    app.state.build_info_provider = get_build_info_provider()
    app.state.metadata_provider = get_metadata_provider()

    # Live ledger providers (decisions / owner portfolio / cycle runs) — no seed data
    wire_sqlite_providers(app.state)

    # Middleware execution pipeline (outermost to innermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.transport.cors_origins,
        allow_credentials=settings.transport.cors_allow_credentials,
        allow_methods=settings.transport.cors_allow_methods,
        allow_headers=settings.transport.cors_allow_headers,
    )
    app.add_middleware(PlatformMiddleware)

    # Register Exception Handlers
    _register_exception_handlers(app)

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/dashboard/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    # Include Platform Infrastructure Routers (P8.5)
    app.include_router(platform_health_router)
    app.include_router(platform_version_router, prefix="/api")
    app.include_router(platform_metadata_router, prefix="/api")
    app.include_router(platform_info_router, prefix="/api")

    # Include Versioned Routers
    app.include_router(v1_router, prefix=settings.app.api_prefix + "/v1")

    # DarvaX satellite (ADR-010) — the single approved ATHENA→DarvaX seam.
    # Opt-in and off by default; when disabled nothing is imported and no route
    # exists. DarvaX never contributes to ATHENA's scoring/decision pipeline.
    # config_dir/repo_root are passed explicitly so DarvaX's flag is read from the
    # same directory ATHENA_CONFIG_DIR selects, exactly like every other config
    # consumer above. Without them the seam silently read the repo-root config.
    mount_darvax_if_enabled(
        app,
        repo=getattr(app.state, "sqlite_repo", None),
        config_dir=config_dir,
        repo_root=config_dir.parent,
    )

    # Mount StaticFiles for Dashboard UI (P9.1)
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    # dashboard.js is assembled from src/athena/api/static/js/*.js (see
    # DASHBOARD_JS_PARTS above) — registered ahead of the StaticFiles mount
    # below so this exact path is served by this route, not by a (now
    # nonexistent) single static dashboard.js file.
    @app.get(
        "/dashboard/dashboard.js",
        include_in_schema=False,
        operation_id="serveDashboardJs",
        tags=["platform"],
        summary="Assembled dashboard.js",
        description=(
            "Concatenates the concern-based js/*.js source files (see "
            "DASHBOARD_JS_PARTS) into the single script the dashboard SPA loads."
        ),
    )
    def serve_dashboard_js() -> PlainTextResponse:
        try:
            content = assemble_dashboard_js(static_dir)
        except FileNotFoundError as exc:
            # Surface loudly (500) rather than letting the /dashboard 404
            # handler below silently swallow this into an index.html response.
            raise AthenaError(str(exc)) from exc
        return PlainTextResponse(content, media_type="application/javascript")

    app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")

    return app
