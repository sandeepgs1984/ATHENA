"""Order Planning Engine artifacts (P5.4).

Immutable order planning representations. The Order Planning Engine
transforms approved position sizes into broker-neutral execution instructions
and execution batches.

It performs NO broker communication, NO order placement, NO fill monitoring, and NO
market analysis — it prepares execution instructions only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from athena.config.models import OrderAction, OrderType


@dataclass(frozen=True, slots=True)
class OrderReferences:
    """Cross-references back to originating sizing plan, allocation, portfolio, decision, and schedule."""

    position_sizing_plan_id: str | None = None
    allocation_plan_id: str | None = None
    portfolio_snapshot_id: str | None = None
    decision_id: str | None = None
    strategy: str | None = None
    watchlist: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "position_sizing_plan_id": self.position_sizing_plan_id,
            "allocation_plan_id": self.allocation_plan_id,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "watchlist": self.watchlist,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class PlannedOrder:
    """A single broker-neutral planned order instruction."""

    order_id: str
    instrument_id: str
    action: OrderAction
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    status: str
    explanation: str
    as_of: datetime
    references: OrderReferences = field(default_factory=OrderReferences)

    def __post_init__(self) -> None:
        if not self.order_id or not self.instrument_id or not self.status:
            raise ValueError("PlannedOrder mandatory fields missing")
        if not self.explanation:
            raise ValueError("PlannedOrder.explanation is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("PlannedOrder.as_of must be timezone-aware")
        if self.quantity < Decimal("0"):
            raise ValueError("PlannedOrder.quantity must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "quantity": str(self.quantity),
            "limit_price": str(self.limit_price) if self.limit_price is not None else None,
            "stop_price": str(self.stop_price) if self.stop_price is not None else None,
            "status": self.status,
            "explanation": self.explanation,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class OrderInstruction:
    """Wrapper container for a planned order instruction."""

    instruction_id: str
    order: PlannedOrder

    def to_dict(self) -> dict[str, object]:
        return {
            "instruction_id": self.instruction_id,
            "order": self.order.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ExecutionBatch:
    """A group of related planned orders prepared for batch execution."""

    batch_id: str
    action_group: str
    as_of: datetime
    orders: tuple[PlannedOrder, ...]

    def __post_init__(self) -> None:
        if not self.batch_id or not self.action_group:
            raise ValueError("ExecutionBatch mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("ExecutionBatch.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "action_group": self.action_group,
            "as_of": self.as_of.isoformat(),
            "orders": [o.to_dict() for o in self.orders],
        }


@dataclass(frozen=True, slots=True)
class OrderPlanningSummary:
    """Aggregated summary of an execution plan."""

    as_of: datetime
    total_candidates: int
    buy_count: int
    sell_count: int
    hold_count: int
    total_buy_quantity: Decimal
    total_sell_quantity: Decimal
    total_planned_value: Decimal

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("OrderPlanningSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "total_candidates": self.total_candidates,
            "buy_count": self.buy_count,
            "sell_count": self.sell_count,
            "hold_count": self.hold_count,
            "total_buy_quantity": str(self.total_buy_quantity),
            "total_sell_quantity": str(self.total_sell_quantity),
            "total_planned_value": str(self.total_planned_value),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Immutable output of running the Order Planning Engine over a PositionSizingPlan."""

    plan_id: str
    as_of: datetime
    position_sizing_plan_id: str
    batches: tuple[ExecutionBatch, ...]
    summary: OrderPlanningSummary
    references: OrderReferences = field(default_factory=OrderReferences)

    def __post_init__(self) -> None:
        if not self.plan_id or not self.position_sizing_plan_id:
            raise ValueError("ExecutionPlan mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("ExecutionPlan.as_of must be timezone-aware")

    def order_for(self, instrument_id: str) -> PlannedOrder | None:
        """Find planned order for an instrument across all batches."""
        for batch in self.batches:
            for order in batch.orders:
                if order.instrument_id == instrument_id:
                    return order
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "as_of": self.as_of.isoformat(),
            "position_sizing_plan_id": self.position_sizing_plan_id,
            "batches": [b.to_dict() for b in self.batches],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class OrderPlanningHistory:
    """Append-only record of execution plans."""

    records: tuple[ExecutionPlan, ...] = ()

    def record(self, plan: ExecutionPlan) -> OrderPlanningHistory:
        """Return a new history with plan appended."""
        return OrderPlanningHistory(records=self.records + (plan,))

    def for_instrument(self, instrument_id: str) -> tuple[PlannedOrder, ...]:
        """Find all planned orders across history for an instrument."""
        res = []
        for plan in self.records:
            order = plan.order_for(instrument_id)
            if order is not None:
                res.append(order)
        return tuple(res)

    def to_dict(self) -> dict[str, object]:
        return {"records": [plan.to_dict() for plan in self.records]}
