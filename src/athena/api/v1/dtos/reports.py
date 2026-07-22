"""Reports domain DTO schemas (P8.4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import FilterParams, ResourceReference
from athena.config.models import ReportType


class ReportMetadataDTO(BaseModel):
    """Extended report metadata tracking versioning and origin references."""

    model_config = ConfigDict(frozen=True)

    report_id: str
    report_type: ReportType
    title: str
    as_of: datetime
    report_version: int
    generated_at: datetime
    source_snapshot_reference: str | None = None


class ReportReferencesDTO(BaseModel):
    """Composed links back to source system parameters/snapshots."""

    model_config = ConfigDict(frozen=True)

    portfolio_snapshot_ref: ResourceReference | None = None
    execution_state_ref: ResourceReference | None = None
    allocation_plan_ref: ResourceReference | None = None
    performance_snapshot_ref: ResourceReference | None = None
    audit_ref: ResourceReference | None = None
    schedule_execution_ref: ResourceReference | None = None


class ReportDTO(BaseModel):
    """Detailed report model exposing full structured payload and text summary."""

    model_config = ConfigDict(frozen=True)

    metadata: ReportMetadataDTO
    content: dict[str, object]
    text_summary: str
    references: ReportReferencesDTO


class ReportSummaryDTO(BaseModel):
    """Lightweight summary model for report listings (omits large content payloads)."""

    model_config = ConfigDict(frozen=True)

    metadata: ReportMetadataDTO
    text_summary: str
    references: ReportReferencesDTO


class ReportFilterParams(FilterParams):
    """Query parameters to filter collections of reports."""

    report_type: ReportType | None = Field(default=None, description="Filter by report classification")
