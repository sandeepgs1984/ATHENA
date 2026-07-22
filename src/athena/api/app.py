"""FastAPI application factory with lifespan management (P8.1).

Coordinates CORS, custom middlewares, generic exception mapping, and API routing.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from athena.api.config import APISettings
from athena.api.errors import exception_mapper
from athena.api.platform.health import router as platform_health_router
from athena.api.platform.info import router as platform_info_router
from athena.api.platform.metadata import router as platform_metadata_router
from athena.api.platform.middleware import PlatformMiddleware
from athena.api.platform.problem_details import ProblemDetail
from athena.api.platform.version import router as platform_version_router
from athena.api.security.token import HMAC256TokenSigner, TokenClaimsFactory
from athena.api.v1.router import router as v1_router
from athena.errors import AthenaError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifecycle management.

    Replaces deprecated startup/shutdown events. Future platform worker
    registration, database connectivity, or scheduler initialization hooks here.
    """
    logger.info("ATHENA Platform API starting up")
    yield
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
        return JSONResponse(
            status_code=detail.status,
            content=detail.to_dict(),
            headers={"Content-Type": "application/problem+json"},
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
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    ) -> JSONResponse:
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
    settings = settings or APISettings()

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
    app.state.token_signer = HMAC256TokenSigner(
        secret_key=settings.security.jwt_secret,
        issuer=settings.security.jwt_issuer,
        audience=settings.security.jwt_audience,
        algorithm=settings.security.jwt_algorithm,
    )
    app.state.claims_factory = TokenClaimsFactory(settings.security)

    # Initialize Platform Infrastructure Providers on app state
    from athena.api.dependencies import get_build_info_provider, get_metadata_provider
    app.state.build_info_provider = get_build_info_provider()
    app.state.metadata_provider = get_metadata_provider()

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

    # Include Platform Infrastructure Routers (P8.5)
    app.include_router(platform_health_router)
    app.include_router(platform_version_router, prefix="/api")
    app.include_router(platform_metadata_router, prefix="/api")
    app.include_router(platform_info_router, prefix="/api")

    # Include Versioned Routers
    app.include_router(v1_router, prefix=settings.app.api_prefix + "/v1")

    return app
