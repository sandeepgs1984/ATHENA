"""Reporting Framework artifacts (P6.1).

Immutable, presentation-only report models. The Reporting Framework produces
structured machine-readable and human-readable operational reports from platform artifacts.

It performs NO state mutation, NO order execution, NO analytical calculations, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from athena.config.models import ReportType


@dataclass(frozen=True, slots=True)
class DecisionReport:
    """Faithful, deterministic report of a single decision. Presentation only (M3.7)."""

    decision_id: str
    decision_type: str
    ts: datetime
    machine: Mapping[str, object]
    text: str

    def __post_init__(self) -> None:
        if not self.machine:
            raise ValueError("DecisionReport.machine must be non-empty")
        if not self.text:
            raise ValueError("DecisionReport.text must be non-empty")
        if self.ts.tzinfo is None:
            raise ValueError("DecisionReport.ts must be timezone-aware")
        object.__setattr__(self, "machine", MappingProxyType(dict(self.machine)))

    def to_dict(self) -> dict[str, object]:
        """Machine-readable structured report (deep-copied, JSON-safe)."""
        return json.loads(json.dumps(dict(self.machine)))

    def to_text(self) -> str:
        """Human-readable report."""
        return self.text

    def to_json(self) -> str:
        """Deterministic JSON serialization of the machine-readable report."""
        return json.dumps(dict(self.machine), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class ReportingReferences:
    """Cross-references back to originating platform artifacts."""

    portfolio_snapshot_id: str | None = None
    execution_state_id: str | None = None
    allocation_plan_id: str | None = None
    performance_snapshot_id: str | None = None
    audit_id: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "execution_state_id": self.execution_state_id,
            "allocation_plan_id": self.allocation_plan_id,
            "performance_snapshot_id": self.performance_snapshot_id,
            "audit_id": self.audit_id,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class GenericReport:
    """Immutable operational report artifact for Phase 6."""

    report_id: str
    report_type: ReportType
    title: str
    as_of: datetime
    content: Mapping[str, object]
    text_summary: str
    references: ReportingReferences = field(default_factory=ReportingReferences)

    def __post_init__(self) -> None:
        if not self.report_id or not self.title or not self.text_summary:
            raise ValueError("GenericReport mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("GenericReport.as_of must be timezone-aware")
        object.__setattr__(self, "content", MappingProxyType(dict(self.content)))

    def to_dict(self) -> dict[str, object]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "title": self.title,
            "as_of": self.as_of.isoformat(),
            "content": json.loads(json.dumps(dict(self.content))),
            "text_summary": self.text_summary,
            "references": self.references.to_dict(),
        }

    def to_text(self) -> str:
        return self.text_summary

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class ReportingHistory:
    """Append-only record of generated reports."""

    records: tuple[GenericReport, ...] = ()

    def record(self, report: GenericReport) -> ReportingHistory:
        """Return a new history with report appended."""
        return ReportingHistory(records=self.records + (report,))

    def for_type(self, report_type: ReportType) -> tuple[GenericReport, ...]:
        """Filter reports by ReportType."""
        return tuple(r for r in self.records if r.report_type == report_type)

    def to_dict(self) -> dict[str, object]:
        return {"records": [r.to_dict() for r in self.records]}
