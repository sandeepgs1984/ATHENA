"""Position Sizing Engine artifacts (P5.3).

Immutable position sizing representations. The Position Sizing Engine
converts approved capital allocations into executable share/unit quantities.

It performs NO market analysis, NO capital allocation policy decision, and NO
order placement or broker execution — it calculates unit quantities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from athena.config.models import RoundingMode, SizingModel


@dataclass(frozen=True, slots=True)
class SizingReferences:
    """Cross-references back to originating allocation, portfolio, decision, and schedule."""

    allocation_plan_id: str | None = None
    portfolio_snapshot_id: str | None = None
    decision_id: str | None = None
    strategy: str | None = None
    watchlist: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "allocation_plan_id": self.allocation_plan_id,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "watchlist": self.watchlist,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class PositionSize:
    """Calculated position size (unit quantity and actual cost) for one opportunity."""

    sizing_id: str
    instrument_id: str
    allocated_amount: Decimal
    unit_price: Decimal
    quantity: Decimal
    actual_cost: Decimal
    sizing_model: SizingModel
    rounding_mode: RoundingMode
    status: str
    explanation: str
    as_of: datetime
    references: SizingReferences = field(default_factory=SizingReferences)

    def __post_init__(self) -> None:
        if not self.sizing_id or not self.instrument_id or not self.status:
            raise ValueError("PositionSize mandatory fields missing")
        if not self.explanation:
            raise ValueError("PositionSize.explanation is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("PositionSize.as_of must be timezone-aware")
        if (
            self.allocated_amount < Decimal("0")
            or self.quantity < Decimal("0")
            or self.actual_cost < Decimal("0")
        ):
            raise ValueError("PositionSize amounts and quantities must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "sizing_id": self.sizing_id,
            "instrument_id": self.instrument_id,
            "allocated_amount": str(self.allocated_amount),
            "unit_price": str(self.unit_price),
            "quantity": str(self.quantity),
            "actual_cost": str(self.actual_cost),
            "sizing_model": self.sizing_model.value,
            "rounding_mode": self.rounding_mode.value,
            "status": self.status,
            "explanation": self.explanation,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PositionSizingDecision:
    """Position sizing result paired with originating decision metadata."""

    decision_id: str
    instrument_id: str
    size: PositionSize

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "instrument_id": self.instrument_id,
            "size": self.size.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PositionSizingSummary:
    """Aggregated summary of a position sizing plan."""

    as_of: datetime
    total_candidates: int
    sized_count: int
    zero_count: int
    total_allocated_capital: Decimal
    total_actual_cost: Decimal
    total_quantity: Decimal

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("PositionSizingSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "total_candidates": self.total_candidates,
            "sized_count": self.sized_count,
            "zero_count": self.zero_count,
            "total_allocated_capital": str(self.total_allocated_capital),
            "total_actual_cost": str(self.total_actual_cost),
            "total_quantity": str(self.total_quantity),
        }


@dataclass(frozen=True, slots=True)
class PositionSizingPlan:
    """Immutable output of running the Position Sizing Engine over an AllocationPlan."""

    plan_id: str
    as_of: datetime
    allocation_plan_id: str
    sizes: tuple[PositionSize, ...]
    summary: PositionSizingSummary
    references: SizingReferences = field(default_factory=SizingReferences)

    def __post_init__(self) -> None:
        if not self.plan_id or not self.allocation_plan_id:
            raise ValueError("PositionSizingPlan mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("PositionSizingPlan.as_of must be timezone-aware")

    def size_for(self, instrument_id: str) -> PositionSize | None:
        """Find calculated size for an instrument."""
        return next((s for s in self.sizes if s.instrument_id == instrument_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "as_of": self.as_of.isoformat(),
            "allocation_plan_id": self.allocation_plan_id,
            "sizes": [s.to_dict() for s in self.sizes],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class PositionSizingHistory:
    """Append-only record of position sizing plans."""

    records: tuple[PositionSizingPlan, ...] = ()

    def record(self, plan: PositionSizingPlan) -> PositionSizingHistory:
        """Return a new history with plan appended."""
        return PositionSizingHistory(records=self.records + (plan,))

    def for_instrument(self, instrument_id: str) -> tuple[PositionSize, ...]:
        """Find all position sizes across history for an instrument."""
        res = []
        for plan in self.records:
            sz = plan.size_for(instrument_id)
            if sz is not None:
                res.append(sz)
        return tuple(res)

    def to_dict(self) -> dict[str, object]:
        return {"records": [plan.to_dict() for plan in self.records]}
