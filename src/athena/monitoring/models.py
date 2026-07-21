"""Operational Monitoring Engine artifacts (P6.5).

Immutable health check and monitoring snapshot models. The Operational Monitoring
Engine evaluates platform health, detects missing or stale artifacts, and aggregates component status.

It performs NO state mutation, NO live polling, NO alert delivery, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from athena.config.models import MonitoringDomain


@dataclass(frozen=True, slots=True)
class MonitoringReferences:
    """Cross-references back to originating platform artifacts."""

    schedule_execution_id: str | None = None
    workflow_id: str | None = None
    portfolio_snapshot_id: str | None = None
    execution_state_id: str | None = None
    performance_snapshot_id: str | None = None
    report_id: str | None = None
    dashboard_snapshot_id: str | None = None
    explanation_snapshot_id: str | None = None
    timeline_snapshot_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_execution_id": self.schedule_execution_id,
            "workflow_id": self.workflow_id,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "execution_state_id": self.execution_state_id,
            "performance_snapshot_id": self.performance_snapshot_id,
            "report_id": self.report_id,
            "dashboard_snapshot_id": self.dashboard_snapshot_id,
            "explanation_snapshot_id": self.explanation_snapshot_id,
            "timeline_snapshot_id": self.timeline_snapshot_id,
        }


@dataclass(frozen=True, slots=True)
class MonitoringCheck:
    """A single health check result for a platform domain or component."""

    check_id: str
    domain: MonitoringDomain
    component: str
    status: str
    message: str
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.check_id or not self.component or not self.status:
            raise ValueError("MonitoringCheck mandatory fields missing")
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "domain": self.domain.value,
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "details": json.loads(json.dumps(dict(self.details))),
        }


@dataclass(frozen=True, slots=True)
class MonitoringSummary:
    """Summary tallies of a MonitoringSnapshot."""

    overall_status: str
    total_checks: int
    healthy_checks: int
    warning_checks: int
    missing_checks: int

    def to_dict(self) -> dict[str, object]:
        return {
            "overall_status": self.overall_status,
            "total_checks": self.total_checks,
            "healthy_checks": self.healthy_checks,
            "warning_checks": self.warning_checks,
            "missing_checks": self.missing_checks,
        }


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    """Immutable output of evaluating operational health."""

    snapshot_id: str
    as_of: datetime
    checks: tuple[MonitoringCheck, ...]
    summary: MonitoringSummary
    references: MonitoringReferences = field(default_factory=MonitoringReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("MonitoringSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("MonitoringSnapshot.as_of must be timezone-aware")

    def check_by_domain(self, domain: MonitoringDomain) -> MonitoringCheck | None:
        """Find check by domain."""
        return next((c for c in self.checks if c.domain == domain), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class MonitoringHistory:
    """Append-only record of monitoring snapshots."""

    records: tuple[MonitoringSnapshot, ...] = ()

    def record(self, snapshot: MonitoringSnapshot) -> MonitoringHistory:
        """Return a new history with snapshot appended."""
        return MonitoringHistory(records=self.records + (snapshot,))

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
