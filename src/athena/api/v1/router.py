"""v1 APIRouter aggregator (P8.1).

Combines health and metrics sub-routers under a unified v1 version prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from athena.api.v1.routers.health import router as health_router
from athena.api.v1.routers.metrics import router as metrics_router

router = APIRouter()

# Include sub-routers with appropriate tags
router.include_router(health_router, tags=["platform"])
router.include_router(metrics_router, tags=["platform"])
