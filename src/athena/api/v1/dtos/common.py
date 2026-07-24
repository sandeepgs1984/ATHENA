"""Common v1 DTOs for health and metrics endpoints (P8.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ComponentHealth(BaseModel):
    """Health status of a single platform component."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["healthy", "degraded", "unavailable"]
    detail: str | None = None


class LastCycleHealthDTO(BaseModel):
    """Last interactive/worker due-cycle summary (Live Entry M-E2)."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime
    idle: bool
    due: tuple[str, ...] = ()
    status: str
    run_id: str | None = None
    trigger: str | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    """Platform health summary DTO."""

    model_config = ConfigDict(frozen=True)

    status: Literal["healthy", "degraded", "unavailable"]
    version: str
    components: list[ComponentHealth]
    as_of: datetime
    kite_token_status: Literal["missing", "present", "unknown"] = "unknown"
    cycles_enabled: bool = False
    last_cycle: LastCycleHealthDTO | None = None
    serve_error: str | None = None


class MetricsResponse(BaseModel):
    """Platform metrics scaffold DTO.

    Returns zero-value counters in P8.1. Real metric aggregation belongs to the
    future observability platform (per PE architecture decision Q2).
    """

    model_config = ConfigDict(frozen=True)

    pipeline_runs_total: int
    pipeline_runs_succeeded: int
    pipeline_runs_failed: int
    schedule_runs_total: int
    schedule_runs_succeeded: int
    schedule_runs_failed: int
    uptime_seconds: float
    as_of: datetime
