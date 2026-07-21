"""Pipeline Runs resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import FilterParams, ResourceReference


class PipelineMetadataDTO(BaseModel):
    """DTO representing pipeline metadata."""

    model_config = ConfigDict(frozen=True)

    definition_id: str
    version: str
    name: str
    description: str
    metadata: dict[str, object] = Field(default_factory=dict)


class PipelineContextDTO(BaseModel):
    """DTO representing a snapshot of execution context."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    as_of: datetime
    data: dict[str, object] = Field(default_factory=dict)


class StageResultDTO(BaseModel):
    """DTO representing execution results of an individual stage."""

    model_config = ConfigDict(frozen=True)

    stage_id: str
    status: str
    message: str
    output_key: str | None = None


class PipelineResultDTO(BaseModel):
    """DTO representing results of a single pipeline run within a system run."""

    model_config = ConfigDict(frozen=True)

    pipeline_run_id: str
    metadata: PipelineMetadataDTO
    as_of: datetime
    stages: list[StageResultDTO]
    overall_status: str
    final_context: PipelineContextDTO


class SystemPipelineResultDTO(BaseModel):
    """DTO representing results of executing an integrated system pipeline chain."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    as_of: datetime
    pipeline_runs: list[PipelineResultDTO]
    workspace_snapshot: ResourceReference | None = None  # Composed link instead of raw snapshot
    overall_status: str
    final_context: PipelineContextDTO


class PipelineRunFilterParams(FilterParams):
    """Filter parameters for pipeline runs collection queries."""

    overall_status: str | None = Field(
        default=None, description="Filter by overall pipeline status (SUCCESS, FAILED)"
    )
