"""Order Planning Engine implementation (P5.4).

Transforms position sizes into broker-neutral execution instructions and batches.
Performs NO broker communication, NO live order placement, NO fill monitoring, and NO market analysis.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from athena.config.models import OrderAction, OrderPlanningConfig, OrderType
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType
from athena.errors import OrderPlanningError
from athena.orders.models import (
    ExecutionBatch,
    ExecutionPlan,
    OrderPlanningHistory,
    OrderPlanningSummary,
    OrderReferences,
    PlannedOrder,
)
from athena.sizing.models import PositionSize, PositionSizingPlan

_TWO_PLACES = Decimal("0.01")


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class OrderPlanningEngine:
    """Deterministic, policy-driven Order Planning Engine."""

    def __init__(self, config: OrderPlanningConfig | None = None) -> None:
        self._config = config or OrderPlanningConfig()
        self._counter = 0
        self._history = OrderPlanningHistory()

    @property
    def history(self) -> OrderPlanningHistory:
        """Get accumulated order planning history."""
        return self._history

    def plan_execution(
        self,
        sizing_plan: PositionSizingPlan,
        *,
        as_of: datetime,
        decisions: Sequence[Decision] | None = None,
        order_type: OrderType | None = None,
    ) -> ExecutionPlan:
        """Transform a PositionSizingPlan into an ExecutionPlan."""
        if as_of.tzinfo is None:
            raise ValueError("plan_execution as_of datetime must be timezone-aware")

        ord_type = order_type or self._config.default_order_type
        dec_map: dict[str, Decision] = {}
        if decisions:
            for d in decisions:
                if d.instrument_id:
                    dec_map[d.instrument_id] = d

        planned_orders: list[PlannedOrder] = []
        buy_cnt = 0
        sell_cnt = 0
        hold_cnt = 0
        tot_buy_qty = Decimal("0")
        tot_sell_qty = Decimal("0")
        tot_val = Decimal("0.00")

        # Sort sizes deterministically by instrument_id
        sorted_sizes = sorted(sizing_plan.sizes, key=lambda s: s.instrument_id)

        for sz in sorted_sizes:
            inst_id = sz.instrument_id
            dec = dec_map.get(inst_id)
            refs = OrderReferences(
                position_sizing_plan_id=sizing_plan.plan_id,
                allocation_plan_id=sz.references.allocation_plan_id,
                portfolio_snapshot_id=sz.references.portfolio_snapshot_id,
                decision_id=sz.references.decision_id,
                strategy=sz.references.strategy,
                watchlist=sz.references.watchlist,
                schedule_execution_id=sz.references.schedule_execution_id,
            )

            action = self._determine_action(sz, dec)

            if action == OrderAction.BUY:
                if sz.quantity <= Decimal("0"):
                    order_status = "HOLD"
                    action = OrderAction.HOLD
                    hold_cnt += 1
                    expl = f"Quantity 0 for {inst_id} (status: {sz.status}) -> HOLD"
                    limit_price = None
                    stop_price = None
                else:
                    order_status = "PLANNED"
                    buy_cnt += 1
                    tot_buy_qty += sz.quantity
                    tot_val += sz.actual_cost
                    expl = f"Planned BUY {sz.quantity} units of {inst_id} at limit {sz.unit_price}"
                    limit_price = sz.unit_price if ord_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) else None
                    stop_price = None
            elif action == OrderAction.SELL:
                if sz.quantity <= Decimal("0"):
                    order_status = "HOLD"
                    action = OrderAction.HOLD
                    hold_cnt += 1
                    expl = f"Quantity 0 for {inst_id} -> HOLD"
                    limit_price = None
                    stop_price = None
                else:
                    order_status = "PLANNED"
                    sell_cnt += 1
                    tot_sell_qty += sz.quantity
                    tot_val += sz.actual_cost
                    expl = f"Planned SELL {sz.quantity} units of {inst_id} at limit {sz.unit_price}"
                    limit_price = sz.unit_price if ord_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) else None
                    stop_price = None
            else:
                order_status = "HOLD"
                hold_cnt += 1
                expl = f"HOLD instruction for {inst_id}"
                limit_price = None
                stop_price = None

            order = PlannedOrder(
                order_id=f"order-{self._next_counter():04d}",
                instrument_id=inst_id,
                action=action,
                order_type=ord_type if action != OrderAction.HOLD else OrderType.MARKET,
                quantity=sz.quantity if action != OrderAction.HOLD else Decimal("0"),
                limit_price=limit_price,
                stop_price=stop_price,
                status=order_status,
                explanation=expl,
                as_of=as_of,
                references=refs,
            )

            planned_orders.append(order)

        # Build execution batches
        batches = self._build_batches(planned_orders, as_of)

        summary = OrderPlanningSummary(
            as_of=as_of,
            total_candidates=len(sizing_plan.sizes),
            buy_count=buy_cnt,
            sell_count=sell_cnt,
            hold_count=hold_cnt,
            total_buy_quantity=tot_buy_qty,
            total_sell_quantity=tot_sell_qty,
            total_planned_value=_quantize(tot_val),
        )

        plan_id = f"execplan-{self._next_counter():04d}"
        plan_refs = OrderReferences(
            position_sizing_plan_id=sizing_plan.plan_id,
            allocation_plan_id=sizing_plan.references.allocation_plan_id,
            portfolio_snapshot_id=sizing_plan.references.portfolio_snapshot_id,
            strategy=sizing_plan.references.strategy,
            watchlist=sizing_plan.references.watchlist,
            schedule_execution_id=sizing_plan.references.schedule_execution_id,
        )

        plan = ExecutionPlan(
            plan_id=plan_id,
            as_of=as_of,
            position_sizing_plan_id=sizing_plan.plan_id,
            batches=tuple(batches),
            summary=summary,
            references=plan_refs,
        )

        if self._config.record_history:
            self._history = self._history.record(plan)

        return plan

    def create_order(
        self,
        instrument_id: str,
        action: OrderAction,
        quantity: Decimal,
        *,
        as_of: datetime,
        order_type: OrderType | None = None,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
        references: OrderReferences | None = None,
    ) -> PlannedOrder:
        """Create a single PlannedOrder instruction explicitly."""
        if as_of.tzinfo is None:
            raise ValueError("create_order as_of datetime must be timezone-aware")
        if quantity < Decimal("0"):
            raise OrderPlanningError(f"Order quantity must be >= 0, got {quantity}")

        ord_type = order_type or self._config.default_order_type
        refs = references or OrderReferences()

        if action == OrderAction.HOLD or quantity == Decimal("0"):
            status = "HOLD"
            expl = f"Explicit HOLD order for {instrument_id}"
        else:
            status = "PLANNED"
            expl = f"Explicit {action.value} order for {quantity} units of {instrument_id}"

        return PlannedOrder(
            order_id=f"order-{self._next_counter():04d}",
            instrument_id=instrument_id,
            action=action,
            order_type=ord_type,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            status=status,
            explanation=expl,
            as_of=as_of,
            references=refs,
        )

    def _determine_action(
        self, sz: PositionSize, decision: Decision | None
    ) -> OrderAction:
        if decision is not None:
            dtype = decision.decision_type
            if dtype in (DecisionType.TRADE, DecisionType.INCREASE_POSITION):
                return OrderAction.BUY
            elif dtype in (DecisionType.REDUCE_POSITION, DecisionType.FULL_EXIT, DecisionType.PARTIAL_EXIT):
                return OrderAction.SELL
            else:
                return OrderAction.HOLD

        if sz.status == "SIZED" and sz.quantity > Decimal("0"):
            return OrderAction.BUY
        return OrderAction.HOLD

    def _build_batches(
        self, orders: Sequence[PlannedOrder], as_of: datetime
    ) -> list[ExecutionBatch]:
        batches: list[ExecutionBatch] = []

        if self._config.batch_by_action:
            grouped: dict[str, list[PlannedOrder]] = {}
            for ord_item in orders:
                key = ord_item.action.value
                grouped.setdefault(key, []).append(ord_item)

            for key in sorted(grouped.keys()):
                group_orders = grouped[key]
                chunk_size = self._config.max_orders_per_batch
                for i in range(0, len(group_orders), chunk_size):
                    chunk = group_orders[i : i + chunk_size]
                    batch_id = f"batch-{self._next_counter():04d}"
                    batches.append(
                        ExecutionBatch(
                            batch_id=batch_id,
                            action_group=key,
                            as_of=as_of,
                            orders=tuple(chunk),
                        )
                    )
        else:
            chunk_size = self._config.max_orders_per_batch
            for i in range(0, len(orders), chunk_size):
                chunk = orders[i : i + chunk_size]
                batch_id = f"batch-{self._next_counter():04d}"
                batches.append(
                    ExecutionBatch(
                        batch_id=batch_id,
                        action_group="ALL",
                        as_of=as_of,
                        orders=tuple(chunk),
                    )
                )

        return batches

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
