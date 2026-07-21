"""Order Lifecycle Engine artifacts (P5.6).

Immutable execution state representations and event transitions. The Order Lifecycle
Engine tracks state transitions for planned orders from creation to terminal states.

It performs NO live broker polling, NO WebSockets/REST calls, NO exchange connectivity, and NO
market analysis — it tracks execution state transitions only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from athena.config.models import OrderLifecycleState


@dataclass(frozen=True, slots=True)
class ExecutionReferences:
    """Cross-references back to originating broker plan, execution plan, sizing, allocation, portfolio, decision, and schedule."""

    broker_execution_plan_id: str | None = None
    execution_plan_id: str | None = None
    position_sizing_plan_id: str | None = None
    allocation_plan_id: str | None = None
    portfolio_snapshot_id: str | None = None
    decision_id: str | None = None
    strategy: str | None = None
    watchlist: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "broker_execution_plan_id": self.broker_execution_plan_id,
            "execution_plan_id": self.execution_plan_id,
            "position_sizing_plan_id": self.position_sizing_plan_id,
            "allocation_plan_id": self.allocation_plan_id,
            "portfolio_snapshot_id": self.portfolio_snapshot_id,
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "watchlist": self.watchlist,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Immutable single lifecycle transition event for an order."""

    event_id: str
    order_id: str
    from_state: OrderLifecycleState
    to_state: OrderLifecycleState
    fill_quantity: Decimal | None
    fill_price: Decimal | None
    explanation: str
    as_of: datetime
    references: ExecutionReferences = field(default_factory=ExecutionReferences)

    def __post_init__(self) -> None:
        if not self.event_id or not self.order_id:
            raise ValueError("ExecutionEvent mandatory fields missing")
        if not self.explanation:
            raise ValueError("ExecutionEvent.explanation is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("ExecutionEvent.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "fill_quantity": str(self.fill_quantity) if self.fill_quantity is not None else None,
            "fill_price": str(self.fill_price) if self.fill_price is not None else None,
            "explanation": self.explanation,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class OrderLifecycle:
    """Authoritative lifecycle state model for a single order."""

    order_id: str
    instrument_id: str
    current_state: OrderLifecycleState
    target_quantity: Decimal
    filled_quantity: Decimal
    avg_fill_price: Decimal
    events: tuple[ExecutionEvent, ...]
    as_of: datetime
    references: ExecutionReferences = field(default_factory=ExecutionReferences)

    def __post_init__(self) -> None:
        if not self.order_id or not self.instrument_id:
            raise ValueError("OrderLifecycle mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("OrderLifecycle.as_of must be timezone-aware")
        if self.target_quantity < Decimal("0") or self.filled_quantity < Decimal("0"):
            raise ValueError("OrderLifecycle quantities must be >= 0")
        if self.filled_quantity > self.target_quantity:
            raise ValueError("OrderLifecycle.filled_quantity cannot exceed target_quantity")

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "current_state": self.current_state.value,
            "target_quantity": str(self.target_quantity),
            "filled_quantity": str(self.filled_quantity),
            "avg_fill_price": str(self.avg_fill_price),
            "events": [e.to_dict() for e in self.events],
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class LifecycleSummary:
    """Summary tallies of order lifecycles."""

    as_of: datetime
    total_orders: int
    active_orders: int
    filled_orders: int
    partially_filled_orders: int
    cancelled_orders: int
    rejected_orders: int
    expired_orders: int
    total_filled_quantity: Decimal
    total_filled_value: Decimal

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("LifecycleSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "total_orders": self.total_orders,
            "active_orders": self.active_orders,
            "filled_orders": self.filled_orders,
            "partially_filled_orders": self.partially_filled_orders,
            "cancelled_orders": self.cancelled_orders,
            "rejected_orders": self.rejected_orders,
            "expired_orders": self.expired_orders,
            "total_filled_quantity": str(self.total_filled_quantity),
            "total_filled_value": str(self.total_filled_value),
        }


@dataclass(frozen=True, slots=True)
class ExecutionState:
    """Overall snapshot of all tracked order lifecycles at a point in time."""

    state_id: str
    as_of: datetime
    broker_execution_plan_id: str
    lifecycles: Mapping[str, OrderLifecycle] = field(default_factory=dict)
    summary: LifecycleSummary = field(init=False)
    references: ExecutionReferences = field(default_factory=ExecutionReferences)

    def __post_init__(self) -> None:
        if not self.state_id or not self.broker_execution_plan_id:
            raise ValueError("ExecutionState mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("ExecutionState.as_of must be timezone-aware")

        object.__setattr__(self, "lifecycles", MappingProxyType(dict(self.lifecycles)))

        # Build summary automatically
        tot_orders = len(self.lifecycles)
        active_cnt = 0
        filled_cnt = 0
        part_filled_cnt = 0
        cancelled_cnt = 0
        rejected_cnt = 0
        expired_cnt = 0
        tot_filled_qty = Decimal("0")
        tot_filled_val = Decimal("0.00")

        for lc in self.lifecycles.values():
            st = lc.current_state
            if st in (
                OrderLifecycleState.CREATED,
                OrderLifecycleState.ACCEPTED,
                OrderLifecycleState.SUBMITTED,
            ):
                active_cnt += 1
            elif st is OrderLifecycleState.PARTIALLY_FILLED:
                active_cnt += 1
                part_filled_cnt += 1
            elif st is OrderLifecycleState.FILLED:
                filled_cnt += 1
            elif st is OrderLifecycleState.CANCELLED:
                cancelled_cnt += 1
            elif st is OrderLifecycleState.REJECTED:
                rejected_cnt += 1
            elif st is OrderLifecycleState.EXPIRED:
                expired_cnt += 1

            tot_filled_qty += lc.filled_quantity
            tot_filled_val += lc.filled_quantity * lc.avg_fill_price

        sum_obj = LifecycleSummary(
            as_of=self.as_of,
            total_orders=tot_orders,
            active_orders=active_cnt,
            filled_orders=filled_cnt,
            partially_filled_orders=part_filled_cnt,
            cancelled_orders=cancelled_cnt,
            rejected_orders=rejected_cnt,
            expired_orders=expired_cnt,
            total_filled_quantity=tot_filled_qty,
            total_filled_value=tot_filled_val.quantize(Decimal("0.01")),
        )
        object.__setattr__(self, "summary", sum_obj)

    def to_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "as_of": self.as_of.isoformat(),
            "broker_execution_plan_id": self.broker_execution_plan_id,
            "lifecycles": {k: v.to_dict() for k, v in sorted(self.lifecycles.items())},
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class LifecycleHistory:
    """Append-only record of execution states."""

    records: tuple[ExecutionState, ...] = ()

    def record(self, state: ExecutionState) -> LifecycleHistory:
        """Return a new history with state appended."""
        return LifecycleHistory(records=self.records + (state,))

    def for_order(self, order_id: str) -> tuple[ExecutionEvent, ...]:
        """Collect all transition events for an order across history."""
        if not self.records:
            return ()
        latest_state = self.records[-1]
        lc = latest_state.lifecycles.get(order_id)
        return lc.events if lc else ()

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
