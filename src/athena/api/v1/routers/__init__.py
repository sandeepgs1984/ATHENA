"""ATHENA API v1 routers package (P8.1)."""

from athena.api.v1.routers.analytics import router as analytics_router
from athena.api.v1.routers.decisions import router as decisions_router
from athena.api.v1.routers.exports import router as exports_router
from athena.api.v1.routers.health import router as health_router
from athena.api.v1.routers.metrics import router as metrics_router
from athena.api.v1.routers.pipelines import router as pipelines_router
from athena.api.v1.routers.portfolio import router as portfolio_router
from athena.api.v1.routers.reports import router as reports_router
from athena.api.v1.routers.scheduler import router as scheduler_router
from athena.api.v1.routers.workspace import router as workspace_router

__all__ = [
    "analytics_router",
    "decisions_router",
    "exports_router",
    "health_router",
    "metrics_router",
    "pipelines_router",
    "portfolio_router",
    "reports_router",
    "scheduler_router",
    "workspace_router",
]
