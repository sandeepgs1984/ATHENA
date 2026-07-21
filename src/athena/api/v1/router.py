"""v1 APIRouter aggregator (P8.1).

Combines health and metrics sub-routers under a unified v1 version prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from athena.api.v1.routers.decisions import router as decisions_router
from athena.api.v1.routers.health import router as health_router
from athena.api.v1.routers.metrics import router as metrics_router
from athena.api.v1.routers.pipelines import router as pipelines_router
from athena.api.v1.routers.portfolio import router as portfolio_router
from athena.api.v1.routers.scheduler import router as scheduler_router
from athena.api.v1.routers.workspace import router as workspace_router

router = APIRouter()

# Include sub-routers
router.include_router(health_router, tags=["platform"])
router.include_router(metrics_router, tags=["platform"])
router.include_router(decisions_router)
router.include_router(portfolio_router)
router.include_router(pipelines_router)
router.include_router(scheduler_router)
router.include_router(workspace_router)
