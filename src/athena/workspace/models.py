"""Unified Intelligence Workspace artifacts (P6.7).

Immutable consolidated workspace models. The Unified Intelligence Workspace provides
a single, unified, read-only composition surface across all Phase 6 intelligence artifacts.

It performs NO state mutation, NO user authentication, NO REST APIs, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class WorkspaceReferences:
    """Cross-references back to originating platform artifacts."""

    report_id: str | None = None
    dashboard_snapshot_id: str | None = None
    explanation_snapshot_id: str | None = None
    timeline_snapshot_id: str | None = None
    monitoring_snapshot_id: str | None = None
    export_snapshot_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "dashboard_snapshot_id": self.dashboard_snapshot_id,
            "explanation_snapshot_id": self.explanation_snapshot_id,
            "timeline_snapshot_id": self.timeline_snapshot_id,
            "monitoring_snapshot_id": self.monitoring_snapshot_id,
            "export_snapshot_id": self.export_snapshot_id,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceEntry:
    """A single catalog entry within a WorkspaceSnapshot."""

    entry_id: str
    artifact_type: str
    title: str
    as_of: datetime
    references: WorkspaceReferences = field(default_factory=WorkspaceReferences)

    def __post_init__(self) -> None:
        if not self.entry_id or not self.artifact_type or not self.title:
            raise ValueError("WorkspaceEntry mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("WorkspaceEntry.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "artifact_type": self.artifact_type,
            "title": self.title,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    """Summary tallies of a WorkspaceSnapshot."""

    total_entries: int
    artifact_counts: Mapping[str, int]
    overall_health: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_counts", MappingProxyType(dict(self.artifact_counts)))

    def to_dict(self) -> dict[str, object]:
        return {
            "total_entries": self.total_entries,
            "artifact_counts": dict(self.artifact_counts),
            "overall_health": self.overall_health,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    """Immutable output of assembling the Unified Intelligence Workspace."""

    snapshot_id: str
    as_of: datetime
    entries: tuple[WorkspaceEntry, ...]
    summary: WorkspaceSummary
    references: WorkspaceReferences = field(default_factory=WorkspaceReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("WorkspaceSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("WorkspaceSnapshot.as_of must be timezone-aware")

    def filter_by_type(self, artifact_type: str) -> tuple[WorkspaceEntry, ...]:
        """Filter workspace entries by artifact_type."""
        return tuple(e for e in self.entries if e.artifact_type.upper() == artifact_type.upper())

    def find_by_id(self, entry_id: str) -> WorkspaceEntry | None:
        """Lookup workspace entry by entry_id."""
        return next((e for e in self.entries if e.entry_id == entry_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "entries": [e.to_dict() for e in self.entries],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class WorkspaceHistory:
    """Append-only record of workspace snapshots."""

    records: tuple[WorkspaceSnapshot, ...] = ()

    def record(self, snapshot: WorkspaceSnapshot) -> WorkspaceHistory:
        """Return a new history with snapshot appended."""
        return WorkspaceHistory(records=self.records + (snapshot,))

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
