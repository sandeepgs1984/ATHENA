"""Order Lifecycle Engine implementation (P5.6).

Tracks order lifecycle states, validates legal state transitions, and records execution history.
Performs NO live broker polling, NO WebSockets/REST calls, NO exchange connectivity, and NO market analysis.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from athena.brokers.models import BrokerExecutionPlan
from athena.config.models import ExecutionConfig, OrderLifecycleState
from athena.errors import LifecycleError
from athena.execution.models import (
    ExecutionEvent,
    ExecutionReferences,
    ExecutionState,
    LifecycleHistory,
    OrderLifecycle,
)

_TWO_PLACES = Decimal("0.01")

LEGAL_TRANSITIONS: dict[OrderLifecycleState, set[OrderLifecycleState]] = {
    OrderLifecycleState.CREATED: {
        OrderLifecycleState.ACCEPTED,
        OrderLifecycleState.SUBMITTED,
        OrderLifecycleState.REJECTED,
        OrderLifecycleState.CANCELLED,
    },
    OrderLifecycleState.ACCEPTED: {
        OrderLifecycleState.SUBMITTED,
        OrderLifecycleState.CANCELLED,
        OrderLifecycleState.REJECTED,
    },
    OrderLifecycleState.SUBMITTED: {
        OrderLifecycleState.PARTIALLY_FILLED,
        OrderLifecycleState.FILLED,
        OrderLifecycleState.CANCELLED,
        OrderLifecycleState.REJECTED,
        OrderLifecycleState.EXPIRED,
    },
    OrderLifecycleState.PARTIALLY_FILLED: {
        OrderLifecycleState.PARTIALLY_FILLED,
        OrderLifecycleState.FILLED,
        OrderLifecycleState.CANCELLED,
        OrderLifecycleState.EXPIRED,
    },
    OrderLifecycleState.FILLED: set(),
    OrderLifecycleState.CANCELLED: set(),
    OrderLifecycleState.REJECTED: set(),
    OrderLifecycleState.EXPIRED: set(),
}


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class OrderLifecycleEngine:
    """Deterministic Order Lifecycle Engine."""

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self._config = config or ExecutionConfig()
        self._counter = 0
        self._current_state: ExecutionState | None = None
        self._history = LifecycleHistory()

    @property
    def current_state(self) -> ExecutionState | None:
        """Get current execution state snapshot."""
        return self._current_state

    @property
    def history(self) -> LifecycleHistory:
        """Get accumulated lifecycle history."""
        return self._history

    def initialize_from_plan(
        self,
        broker_plan: BrokerExecutionPlan,
        *,
        as_of: datetime,
    ) -> ExecutionState:
        """Initialize order lifecycles from a BrokerExecutionPlan."""
        if as_of.tzinfo is None:
            raise ValueError("initialize_from_plan as_of datetime must be timezone-aware")

        lifecycles: dict[str, OrderLifecycle] = {}

        for req in broker_plan.requests:
            order_id = req.request_id
            inst_id = req.instrument_id
            refs = ExecutionReferences(
                broker_execution_plan_id=broker_plan.broker_plan_id,
                execution_plan_id=broker_plan.execution_plan_id,
                position_sizing_plan_id=req.references.position_sizing_plan_id,
                allocation_plan_id=req.references.allocation_plan_id,
                portfolio_snapshot_id=req.references.portfolio_snapshot_id,
                decision_id=req.references.decision_id,
                strategy=req.references.strategy,
                watchlist=req.references.watchlist,
                schedule_execution_id=req.references.schedule_execution_id,
            )

            init_event = ExecutionEvent(
                event_id=f"evt-{self._next_counter():04d}",
                order_id=order_id,
                from_state=OrderLifecycleState.CREATED,
                to_state=OrderLifecycleState.CREATED,
                fill_quantity=None,
                fill_price=None,
                explanation=f"Initialized lifecycle for {inst_id} (status: {req.status})",
                as_of=as_of,
                references=refs,
            )

            lc = OrderLifecycle(
                order_id=order_id,
                instrument_id=inst_id,
                current_state=OrderLifecycleState.CREATED,
                target_quantity=req.quantity,
                filled_quantity=Decimal("0"),
                avg_fill_price=Decimal("0.00"),
                events=(init_event,),
                as_of=as_of,
                references=refs,
            )

            lifecycles[order_id] = lc

        state_id = f"execstate-{self._next_counter():04d}"
        plan_refs = ExecutionReferences(
            broker_execution_plan_id=broker_plan.broker_plan_id,
            execution_plan_id=broker_plan.execution_plan_id,
            position_sizing_plan_id=broker_plan.references.position_sizing_plan_id,
            allocation_plan_id=broker_plan.references.allocation_plan_id,
            portfolio_snapshot_id=broker_plan.references.portfolio_snapshot_id,
            strategy=broker_plan.references.strategy,
            watchlist=broker_plan.references.watchlist,
            schedule_execution_id=broker_plan.references.schedule_execution_id,
        )

        state = ExecutionState(
            state_id=state_id,
            as_of=as_of,
            broker_execution_plan_id=broker_plan.broker_plan_id,
            lifecycles=lifecycles,
            references=plan_refs,
        )

        self._current_state = state
        if self._config.record_history:
            self._history = self._history.record(state)

        return state

    def record_event(
        self,
        order_id: str,
        to_state: OrderLifecycleState,
        *,
        as_of: datetime,
        fill_quantity: Decimal | None = None,
        fill_price: Decimal | None = None,
        explanation: str = "",
        references: ExecutionReferences | None = None,
    ) -> ExecutionState:
        """Record an explicit state transition for an order."""
        if self._current_state is None:
            raise LifecycleError("Engine state not initialized — call initialize_from_plan first")
        if as_of.tzinfo is None:
            raise ValueError("record_event as_of datetime must be timezone-aware")
        if order_id not in self._current_state.lifecycles:
            raise LifecycleError(f"Order '{order_id}' not found in current execution state")

        existing_lc = self._current_state.lifecycles[order_id]
        from_st = existing_lc.current_state

        # Validate legal transition
        if self._config.enforce_strict_transitions:
            allowed = LEGAL_TRANSITIONS.get(from_st, set())
            if to_state not in allowed and from_st != to_state:
                raise LifecycleError(
                    f"Illegal state transition for order '{order_id}': {from_st.value} -> {to_state.value}"
                )

        # Validate fill parameters for fill states
        new_filled_qty = existing_lc.filled_quantity
        new_avg_price = existing_lc.avg_fill_price

        if to_state in (OrderLifecycleState.PARTIALLY_FILLED, OrderLifecycleState.FILLED):
            if fill_quantity is None or fill_quantity <= Decimal("0"):
                if to_state == OrderLifecycleState.FILLED:
                    fill_quantity = existing_lc.target_quantity - existing_lc.filled_quantity
                else:
                    raise LifecycleError(
                        f"Fill quantity must be > 0 for fill state {to_state.value}"
                    )
            if fill_price is None or fill_price <= Decimal("0"):
                raise LifecycleError(
                    f"Fill price must be > 0 for fill state {to_state.value}"
                )

            prev_cost = existing_lc.filled_quantity * existing_lc.avg_fill_price
            add_cost = fill_quantity * fill_price
            new_filled_qty = existing_lc.filled_quantity + fill_quantity

            if new_filled_qty > existing_lc.target_quantity:
                raise LifecycleError(
                    f"Filled quantity {new_filled_qty} exceeds target quantity {existing_lc.target_quantity} for order '{order_id}'"
                )

            new_avg_price = (prev_cost + add_cost) / new_filled_qty
            new_avg_price = _quantize(new_avg_price)

            if to_state == OrderLifecycleState.PARTIALLY_FILLED and new_filled_qty == existing_lc.target_quantity:
                to_state = OrderLifecycleState.FILLED

        refs = references or existing_lc.references
        evt_expl = explanation or f"Transition {from_st.value} -> {to_state.value} for {existing_lc.instrument_id}"

        event = ExecutionEvent(
            event_id=f"evt-{self._next_counter():04d}",
            order_id=order_id,
            from_state=from_st,
            to_state=to_state,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            explanation=evt_expl,
            as_of=as_of,
            references=refs,
        )

        updated_lc = OrderLifecycle(
            order_id=order_id,
            instrument_id=existing_lc.instrument_id,
            current_state=to_state,
            target_quantity=existing_lc.target_quantity,
            filled_quantity=new_filled_qty,
            avg_fill_price=new_avg_price,
            events=existing_lc.events + (event,),
            as_of=as_of,
            references=refs,
        )

        new_lifecycles = dict(self._current_state.lifecycles)
        new_lifecycles[order_id] = updated_lc

        new_state = ExecutionState(
            state_id=f"execstate-{self._next_counter():04d}",
            as_of=as_of,
            broker_execution_plan_id=self._current_state.broker_execution_plan_id,
            lifecycles=new_lifecycles,
            references=self._current_state.references,
        )

        self._current_state = new_state
        if self._config.record_history:
            self._history = self._history.record(new_state)

        return new_state

    def get_order_lifecycle(self, order_id: str) -> OrderLifecycle:
        """Get current OrderLifecycle for an order_id."""
        if self._current_state is None or order_id not in self._current_state.lifecycles:
            raise LifecycleError(f"Order '{order_id}' not found")
        return self._current_state.lifecycles[order_id]

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
