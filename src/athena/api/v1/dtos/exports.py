"""Presentation exports DTO schemas (P8.4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import ArtifactMetadataDTO, SourceArtifactType
from athena.config.models import ExportFormat


class SourceReferenceDTO(BaseModel):
    """Refers to the source system artifact targeted for export."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str
    artifact_type: SourceArtifactType


class ExportOptionsDTO(BaseModel):
    """Presentation formatting parameters passed to the adaptation engine."""

    model_config = ConfigDict(frozen=True)

    options: dict[str, object] = Field(
        default_factory=dict,
        description="Format specific properties (e.g. delimiters, styling)",
    )


class ExportRequestDTO(BaseModel):
    """Composed payload requesting format transformation for an artifact."""

    model_config = ConfigDict(frozen=True)

    source: SourceReferenceDTO
    format: ExportFormat
    options: ExportOptionsDTO = Field(default_factory=ExportOptionsDTO)


class ExportArtifactDTO(BaseModel):
    """Adaptation result containing structured metadata and payload."""

    model_config = ConfigDict(frozen=True)

    metadata: ArtifactMetadataDTO
    payload: str


class ExportSummaryDTO(BaseModel):
    """Tallies and metadata summary for a batch of exports."""

    model_config = ConfigDict(frozen=True)

    total_exports: int
    formats_used: list[ExportFormat]
    total_bytes: int


class ExportSnapshotDTO(BaseModel):
    """Detailed snapshot of a batch export operation and nested artifacts."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    as_of: datetime
    exports: list[ExportArtifactDTO]
    summary: ExportSummaryDTO


class ExportSnapshotSummaryDTO(BaseModel):
    """Lightweight metadata overview of a batch export snapshot."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    as_of: datetime
    summary: ExportSummaryDTO
