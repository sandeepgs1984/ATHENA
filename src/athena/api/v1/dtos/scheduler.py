"""Scheduler history resource DTOs (P8.3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import FilterParams, ResourceReference
from athena.api.v1.dtos.pipelines import SystemPipelineResultDTO


class PipelineScheduleRunDTO(BaseModel):
    """DTO representing the execution envelope of a scheduled pipeline cycle."""

    model_config = ConfigDict(frozen=True)

    schedule_run_id: str
    job: ResourceReference
    definition_id: str
    system_result: SystemPipelineResultDTO
    duration_seconds: float


class SchedulerHistoryFilterParams(FilterParams):
    """Filter parameters for scheduler history collection queries."""

    job_id: str | None = Field(
        default=None, description="Filter by scheduled job identifier"
    )
    overall_status: str | None = Field(
        default=None, description="Filter by system run status (SUCCESS, FAILED)"
    )
