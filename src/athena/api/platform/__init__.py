"""ATHENA API platform infrastructure package (P8.5)."""

from __future__ import annotations

from athena.api.platform.headers import inject_platform_headers
from athena.api.platform.health import router as health_router
from athena.api.platform.info import router as info_router
from athena.api.platform.metadata import router as metadata_router
from athena.api.platform.middleware import PlatformMiddleware, RequestContext
from athena.api.platform.problem_details import ProblemDetail
from athena.api.platform.version import router as version_router

__all__ = [
    "PlatformMiddleware",
    "ProblemDetail",
    "RequestContext",
    "health_router",
    "info_router",
    "inject_platform_headers",
    "metadata_router",
    "version_router",
]
