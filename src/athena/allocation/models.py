"""Capital Allocation Engine artifacts (P5.2).

Immutable capital allocation representations. The Capital Allocation Engine
determines how much capital should be reserved/allocated for each approved
investment opportunity.

It performs NO market analysis, NO position sizing (share quantities), and NO
order execution — it evaluates capital availability and allocation policy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from athena.config.models import AllocationModel


@dataclass(frozen=True, slots=True)
class AllocationReferences:
    """Cross-references back to originating portfolio, decision, strategy, and schedule."""

    portfolio_snapshot_id: str | None = None
    decision_id: str | None = None
    strategy: str | None = None
    watchlist: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "watchlist": self.watchlist,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class CapitalAllocation:
    """Capital allocated to one approved investment opportunity."""

    allocation_id: str
    instrument_id: str
    allocated_amount: Decimal
    requested_amount: Decimal
    model_used: AllocationModel
    status: str
    explanation: str
    as_of: datetime
    references: AllocationReferences = field(default_factory=AllocationReferences)

    def __post_init__(self) -> None:
        if not self.allocation_id or not self.instrument_id or not self.status:
            raise ValueError("CapitalAllocation mandatory fields missing")
        if not self.explanation:
            raise ValueError("CapitalAllocation.explanation is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("CapitalAllocation.as_of must be timezone-aware")
        if self.allocated_amount < Decimal("0") or self.requested_amount < Decimal("0"):
            raise ValueError("CapitalAllocation amounts must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "allocation_id": self.allocation_id,
            "instrument_id": self.instrument_id,
            "allocated_amount": str(self.allocated_amount),
            "requested_amount": str(self.requested_amount),
            "model_used": self.model_used.value,
            "status": self.status,
            "explanation": self.explanation,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AllocationDecision:
    """Allocation result paired with originating decision metadata."""

    decision_id: str
    instrument_id: str
    decision_type: str
    allocation: CapitalAllocation

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "instrument_id": self.instrument_id,
            "decision_type": self.decision_type,
            "allocation": self.allocation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AllocationSummary:
    """Aggregated summary of an allocation plan."""

    as_of: datetime
    total_candidates: int
    allocated_count: int
    rejected_count: int
    total_allocated_capital: Decimal
    remaining_available_cash: Decimal
    min_cash_reserve_floor: Decimal

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("AllocationSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "total_candidates": self.total_candidates,
            "allocated_count": self.allocated_count,
            "rejected_count": self.rejected_count,
            "total_allocated_capital": str(self.total_allocated_capital),
            "remaining_available_cash": str(self.remaining_available_cash),
            "min_cash_reserve_floor": str(self.min_cash_reserve_floor),
        }


@dataclass(frozen=True, slots=True)
class AllocationPlan:
    """Immutable output of running the Capital Allocation Engine over a set of opportunities."""

    plan_id: str
    as_of: datetime
    portfolio_snapshot_id: str
    allocations: tuple[CapitalAllocation, ...]
    summary: AllocationSummary
    references: AllocationReferences = field(default_factory=AllocationReferences)

    def __post_init__(self) -> None:
        if not self.plan_id or not self.portfolio_snapshot_id:
            raise ValueError("AllocationPlan mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("AllocationPlan.as_of must be timezone-aware")

    def allocation_for(self, instrument_id: str) -> CapitalAllocation | None:
        """Find allocation for an instrument."""
        return next((a for a in self.allocations if a.instrument_id == instrument_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "as_of": self.as_of.isoformat(),
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "allocations": [a.to_dict() for a in self.allocations],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class AllocationHistory:
    """Append-only record of allocation plans."""

    records: tuple[AllocationPlan, ...] = ()

    def record(self, plan: AllocationPlan) -> AllocationHistory:
        """Return a new history with plan appended."""
        return AllocationHistory(records=self.records + (plan,))

    def for_instrument(self, instrument_id: str) -> tuple[CapitalAllocation, ...]:
        """Find all allocations across history for an instrument."""
        res = []
        for plan in self.records:
            alloc = plan.allocation_for(instrument_id)
            if alloc is not None:
                res.append(alloc)
        return tuple(res)

    def to_dict(self) -> dict[str, object]:
        return {"records": [plan.to_dict() for plan in self.records]}
