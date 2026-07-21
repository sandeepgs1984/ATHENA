"""Timeline & Audit Engine artifacts (P6.4).

Immutable chronological timeline and audit entry models. The Timeline & Audit Engine
reconstructs platform history into deterministic, causally ordered audit streams.

It performs NO state mutation, NO live streaming, NO event altering, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from athena.config.models import TimelineDomain


@dataclass(frozen=True, slots=True)
class TimelineReferences:
    """Cross-references back to all originating platform artifacts."""

    decision_id: str | None = None
    portfolio_snapshot_id: str | None = None
    allocation_plan_id: str | None = None
    position_sizing_plan_id: str | None = None
    execution_plan_id: str | None = None
    broker_execution_plan_id: str | None = None
    execution_state_id: str | None = None
    performance_snapshot_id: str | None = None
    report_id: str | None = None
    dashboard_snapshot_id: str | None = None
    explanation_snapshot_id: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "allocation_plan_id": self.allocation_plan_id,
            "position_sizing_plan_id": self.position_sizing_plan_id,
            "execution_plan_id": self.execution_plan_id,
            "broker_execution_plan_id": self.broker_execution_plan_id,
            "execution_state_id": self.execution_state_id,
            "performance_snapshot_id": self.performance_snapshot_id,
            "report_id": self.report_id,
            "dashboard_snapshot_id": self.dashboard_snapshot_id,
            "explanation_snapshot_id": self.explanation_snapshot_id,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """A single chronological platform event."""

    event_id: str
    ts: datetime
    domain: TimelineDomain
    event_type: str
    summary: str
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.event_id or not self.event_type or not self.summary:
            raise ValueError("TimelineEvent mandatory fields missing")
        if self.ts.tzinfo is None:
            raise ValueError("TimelineEvent.ts must be timezone-aware")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "ts": self.ts.isoformat(),
            "domain": self.domain.value,
            "event_type": self.event_type,
            "summary": self.summary,
            "details": json.loads(json.dumps(dict(self.details))),
        }


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """An ordered audit entry wrapping a TimelineEvent."""

    audit_id: str
    sequence_number: int
    event: TimelineEvent
    references: TimelineReferences = field(default_factory=TimelineReferences)

    def __post_init__(self) -> None:
        if not self.audit_id or self.sequence_number < 1:
            raise ValueError("AuditEntry mandatory fields missing or invalid sequence_number")

    def to_dict(self) -> dict[str, object]:
        return {
            "audit_id": self.audit_id,
            "sequence_number": self.sequence_number,
            "event": self.event.to_dict(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class TimelineSummary:
    """Summary statistics of a TimelineSnapshot."""

    total_events: int
    domains_covered: tuple[TimelineDomain, ...]
    start_time: datetime | None
    end_time: datetime | None

    def to_dict(self) -> dict[str, object]:
        return {
            "total_events": self.total_events,
            "domains_covered": [d.value for d in self.domains_covered],
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


@dataclass(frozen=True, slots=True)
class TimelineSnapshot:
    """Immutable chronological timeline reconstruction artifact."""

    snapshot_id: str
    as_of: datetime
    entries: tuple[AuditEntry, ...]
    summary: TimelineSummary
    references: TimelineReferences = field(default_factory=TimelineReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("TimelineSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("TimelineSnapshot.as_of must be timezone-aware")

    def entries_for_domain(self, domain: TimelineDomain) -> tuple[AuditEntry, ...]:
        """Filter audit entries by domain."""
        return tuple(e for e in self.entries if e.event.domain == domain)

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
class TimelineHistory:
    """Append-only record of timeline snapshots."""

    records: tuple[TimelineSnapshot, ...] = ()

    def record(self, snapshot: TimelineSnapshot) -> TimelineHistory:
        """Return a new history with snapshot appended."""
        return TimelineHistory(records=self.records + (snapshot,))

    def for_domain(self, domain: TimelineDomain) -> tuple[AuditEntry, ...]:
        """Collect all audit entries for a domain across history."""
        res = []
        for snap in self.records:
            res.extend(snap.entries_for_domain(domain))
        return tuple(res)

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
