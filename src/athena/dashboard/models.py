"""Dashboard & Snapshot Engine artifacts (P6.2).

Immutable derived operational view artifacts and snapshot models. The Dashboard &
Snapshot Engine aggregates platform status, portfolio health, execution progress, and analytics.

It performs NO state mutation, NO order execution, NO UI rendering, and NO market analysis.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DashboardReferences:
    """Cross-references back to originating platform artifacts."""

    portfolio_snapshot_id: str | None = None
    performance_snapshot_id: str | None = None
    execution_state_id: str | None = None
    allocation_plan_id: str | None = None
    report_id: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "performance_snapshot_id": self.performance_snapshot_id,
            "execution_state_id": self.execution_state_id,
            "allocation_plan_id": self.allocation_plan_id,
            "report_id": self.report_id,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class DashboardSection:
    """A single section within a DashboardSnapshot."""

    section_id: str
    title: str
    metrics: Mapping[str, object]
    status: str
    text_summary: str

    def __post_init__(self) -> None:
        if not self.section_id or not self.title or not self.status:
            raise ValueError("DashboardSection mandatory fields missing")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "metrics": json.loads(json.dumps(dict(self.metrics))),
            "status": self.status,
            "text_summary": self.text_summary,
        }


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Summary tallies of a DashboardSnapshot."""

    as_of: datetime
    portfolio_value: Decimal
    total_positions: int
    active_orders: int
    total_pnl: Decimal
    health_status: str

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("DashboardSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "portfolio_value": str(self.portfolio_value),
            "total_positions": self.total_positions,
            "active_orders": self.active_orders,
            "total_pnl": str(self.total_pnl),
            "health_status": self.health_status,
        }


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """Immutable output of running the Dashboard Engine."""

    snapshot_id: str
    as_of: datetime
    sections: tuple[DashboardSection, ...]
    summary: DashboardSummary
    references: DashboardReferences = field(default_factory=DashboardReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("DashboardSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("DashboardSnapshot.as_of must be timezone-aware")

    def section_by_id(self, section_id: str) -> DashboardSection | None:
        """Find dashboard section by section_id."""
        return next((s for s in self.sections if s.section_id == section_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "sections": [s.to_dict() for s in self.sections],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class DashboardHistory:
    """Append-only record of dashboard snapshots."""

    records: tuple[DashboardSnapshot, ...] = ()

    def record(self, snapshot: DashboardSnapshot) -> DashboardHistory:
        """Return a new history with snapshot appended."""
        return DashboardHistory(records=self.records + (snapshot,))

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
