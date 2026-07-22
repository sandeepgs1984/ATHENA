"""Health and Diagnostics Controllers (P8.5)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from athena.api.dependencies import get_health_service
from athena.api.v1.services.health_service import HealthService

router = APIRouter(tags=["Platform Health"])


class CheckResultDTO(BaseModel):
    """Health status of a single subsystem check."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["UP", "DOWN"]
    detail: str | None = None


class PlatformHealthDTO(BaseModel):
    """Production health diagnostic response model."""

    model_config = ConfigDict(frozen=True)

    status: Literal["UP", "DOWN"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    version: str
    checks: list[CheckResultDTO] = Field(default_factory=list)


@router.get(
    "/health",
    response_model=PlatformHealthDTO,
    summary="Get aggregated platform health",
    response_description="Returns aggregated health metrics across all components",
    operation_id="getPlatformHealth",
)
def get_health(
    request: Request,
    service: HealthService = Depends(get_health_service),  # noqa: B008
) -> PlatformHealthDTO:
    """Retrieve detailed platform operational and database connectivity metrics."""
    h = service.get_health()
    
    # Map from v1 HealthResponse to PlatformHealthDTO checks
    checks = []
    overall_status: Literal["UP", "DOWN"] = "UP"
    for comp in h.components:
        c_status: Literal["UP", "DOWN"] = "UP" if comp.status == "healthy" else "DOWN"
        if c_status == "DOWN":
            overall_status = "DOWN"
        checks.append(CheckResultDTO(name=comp.name, status=c_status, detail=comp.detail))

    return PlatformHealthDTO(
        status=overall_status,
        timestamp=h.as_of,
        version=h.version,
        checks=checks,
    )


@router.get(
    "/health/live",
    response_model=PlatformHealthDTO,
    summary="Liveness check",
    response_description="Confirm API process is running and responsive",
    operation_id="getLiveness",
)
def get_live(request: Request) -> PlatformHealthDTO:
    """Standard k8s/runtime process liveness ping."""
    return PlatformHealthDTO(
        status="UP",
        timestamp=datetime.now(tz=timezone.utc),
        version="1.0.0",
        checks=[CheckResultDTO(name="process", status="UP", detail="API server responsive")],
    )


@router.get(
    "/health/ready",
    response_model=PlatformHealthDTO,
    summary="Readiness check",
    response_description="Confirm database and external providers are ready to serve traffic",
    operation_id="getReadiness",
)
def get_ready(
    request: Request,
    service: HealthService = Depends(get_health_service),  # noqa: B008
) -> PlatformHealthDTO:
    """Evaluate database connectivity, workspace access, and platform readiness."""
    h = service.get_health()

    checks = []
    overall_status: Literal["UP", "DOWN"] = "UP"
    for comp in h.components:
        c_status: Literal["UP", "DOWN"] = "UP" if comp.status == "healthy" else "DOWN"
        if c_status == "DOWN":
            overall_status = "DOWN"
        checks.append(CheckResultDTO(name=comp.name, status=c_status, detail=comp.detail))

    return PlatformHealthDTO(
        status=overall_status,
        timestamp=h.as_of,
        version=h.version,
        checks=checks,
    )
