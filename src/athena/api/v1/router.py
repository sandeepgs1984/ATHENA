"""v1 APIRouter aggregator (P8.1).

Combines health and metrics sub-routers under a unified v1 version prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from athena.api.v1.routers.analytics import router as analytics_router
from athena.api.v1.routers.auth import router as auth_router
from athena.api.v1.routers.dashboard import router as dashboard_router
from athena.api.v1.routers.decisions import router as decisions_router
from athena.api.v1.routers.exports import router as exports_router
from athena.api.v1.routers.health import router as health_router
from athena.api.v1.routers.metrics import router as metrics_router
from athena.api.v1.routers.pipelines import router as pipelines_router
from athena.api.v1.routers.portfolio import router as portfolio_router
from athena.api.v1.routers.reports import router as reports_router
from athena.api.v1.routers.scheduler import router as scheduler_router
from athena.api.v1.routers.workspace import router as workspace_router
from athena.api.v1.routers.strategies import router as strategies_router
from athena.api.v1.routers.backtests import router as backtests_router
from athena.api.v1.routers.ops import router as ops_router
from athena.api.v1.routers.market import router as market_router

router = APIRouter()

# Include sub-routers
router.include_router(health_router, tags=["platform"])
router.include_router(metrics_router, tags=["platform"])
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(decisions_router)
router.include_router(portfolio_router)
router.include_router(market_router)
router.include_router(pipelines_router)
router.include_router(scheduler_router)
router.include_router(workspace_router)
router.include_router(reports_router)
router.include_router(analytics_router)
router.include_router(exports_router)
router.include_router(strategies_router)
router.include_router(backtests_router)
router.include_router(ops_router)
