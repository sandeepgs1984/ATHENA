"""Workspace snapshots resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import FilterParams, ResourceReference


class WorkspaceReferencesDTO(BaseModel):
    """Composed links referencing origin platform artifacts."""

    model_config = ConfigDict(frozen=True)

    report_ref: ResourceReference | None = None
    dashboard_ref: ResourceReference | None = None
    explanation_ref: ResourceReference | None = None
    timeline_ref: ResourceReference | None = None
    monitoring_ref: ResourceReference | None = None
    export_ref: ResourceReference | None = None


class WorkspaceEntryDTO(BaseModel):
    """Catalog entry in the snapshot."""

    model_config = ConfigDict(frozen=True)

    entry_id: str
    artifact_type: str
    title: str
    as_of: datetime
    references: WorkspaceReferencesDTO


class WorkspaceSummaryDTO(BaseModel):
    """Aggregated metadata summary of the snapshot contents."""

    model_config = ConfigDict(frozen=True)

    total_entries: int
    artifact_counts: dict[str, int] = Field(default_factory=dict)
    overall_health: str


class WorkspaceSnapshotSummaryDTO(BaseModel):
    """Lightweight metadata descriptor for collection list endpoints.

    Avoids loading full catalog entries array in collection results.
    """

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    as_of: datetime
    summary: WorkspaceSummaryDTO
    references: WorkspaceReferencesDTO


class WorkspaceSnapshotDTO(BaseModel):
    """Complete detail container housing the catalog entries list."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    as_of: datetime
    summary: WorkspaceSummaryDTO
    references: WorkspaceReferencesDTO
    entries: list[WorkspaceEntryDTO] = Field(default_factory=list)


class WorkspaceFilterParams(FilterParams):
    """Filter parameters for workspace snapshots collection queries."""

    overall_health: str | None = Field(
        default=None, description="Filter by workspace overall health (HEALTHY, DEGRADED)"
    )
