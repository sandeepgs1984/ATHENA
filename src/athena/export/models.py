"""Export & Presentation Layer artifacts (P6.6).

Immutable exported representation models. The Export & Presentation Layer transforms
platform artifacts into standardized presentation formats (JSON, Markdown, Plain Text, CSV).

It performs NO state mutation, NO PDF rendering, NO REST endpoints, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from athena.config.models import ExportFormat


@dataclass(frozen=True, slots=True)
class ExportReferences:
    """Cross-references back to originating platform artifacts."""

    report_id: str | None = None
    dashboard_snapshot_id: str | None = None
    explanation_snapshot_id: str | None = None
    timeline_snapshot_id: str | None = None
    monitoring_snapshot_id: str | None = None
    decision_brief_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "dashboard_snapshot_id": self.dashboard_snapshot_id,
            "explanation_snapshot_id": self.explanation_snapshot_id,
            "timeline_snapshot_id": self.timeline_snapshot_id,
            "monitoring_snapshot_id": self.monitoring_snapshot_id,
            "decision_brief_id": self.decision_brief_id,
        }


@dataclass(frozen=True, slots=True)
class ExportRequest:
    """A formal request to produce an export artifact."""

    request_id: str
    format: ExportFormat
    source_artifact_id: str
    options: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.request_id or not self.source_artifact_id:
            raise ValueError("ExportRequest mandatory fields missing")
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "format": self.format.value,
            "source_artifact_id": self.source_artifact_id,
            "options": json.loads(json.dumps(dict(self.options))),
        }


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    """An immutable exported representation artifact."""

    export_id: str
    format: ExportFormat
    filename: str
    content_type: str
    payload: str
    as_of: datetime
    references: ExportReferences = field(default_factory=ExportReferences)

    def __post_init__(self) -> None:
        if not self.export_id or not self.filename or not self.content_type:
            raise ValueError("ExportArtifact mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("ExportArtifact.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "export_id": self.export_id,
            "format": self.format.value,
            "filename": self.filename,
            "content_type": self.content_type,
            "payload": self.payload,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation of export metadata & payload."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class ExportSummary:
    """Summary tallies of an ExportSnapshot."""

    total_exports: int
    formats_used: tuple[ExportFormat, ...]
    total_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "total_exports": self.total_exports,
            "formats_used": [f.value for f in self.formats_used],
            "total_bytes": self.total_bytes,
        }


@dataclass(frozen=True, slots=True)
class ExportSnapshot:
    """Immutable output of a batch export operation."""

    snapshot_id: str
    as_of: datetime
    exports: tuple[ExportArtifact, ...]
    summary: ExportSummary
    references: ExportReferences = field(default_factory=ExportReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("ExportSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("ExportSnapshot.as_of must be timezone-aware")

    def export_by_format(self, fmt: ExportFormat) -> tuple[ExportArtifact, ...]:
        """Filter exports in snapshot by format."""
        return tuple(e for e in self.exports if e.format == fmt)

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "exports": [e.to_dict() for e in self.exports],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class ExportHistory:
    """Append-only record of export snapshots."""

    records: tuple[ExportSnapshot, ...] = ()

    def record(self, snapshot: ExportSnapshot) -> ExportHistory:
        """Return a new history with snapshot appended."""
        return ExportHistory(records=self.records + (snapshot,))

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
