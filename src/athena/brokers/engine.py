"""Broker Abstraction Layer implementation (P5.5).

Translates broker-neutral execution plans into canonical broker requests and validates broker capabilities.
Performs NO network communication, NO OAuth, NO WebSocket/REST clients, and NO live order placement.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from athena.brokers.models import (
    BrokerCapabilities,
    BrokerDefinition,
    BrokerExecutionPlan,
    BrokerHistory,
    BrokerReferences,
    BrokerRequest,
    BrokerResponse,
    BrokerSummary,
)
from athena.config.models import BrokerConfig, OrderAction, OrderType, TimeInForce
from athena.errors import BrokerError
from athena.orders.models import ExecutionPlan, PlannedOrder

_TWO_PLACES = Decimal("0.01")


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class BrokerManager:
    """Deterministic Broker Abstraction Layer manager."""

    def __init__(self, config: BrokerConfig | None = None) -> None:
        self._config = config or BrokerConfig()
        self._counter = 0
        self._brokers: dict[str, BrokerDefinition] = {}
        self._history = BrokerHistory()

        # Register default paper_broker contract
        paper_caps = BrokerCapabilities(
            supported_order_types=(OrderType.MARKET, OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT),
            supports_fractional=True,
            supports_shorting=True,
            supported_time_in_force=(TimeInForce.DAY, TimeInForce.IOC, TimeInForce.FOK, TimeInForce.GTC),
            max_orders_per_request=100,
        )
        self.register_broker(
            BrokerDefinition(
                broker_id="paper_broker",
                name="ATHENA Paper Broker (Canonical Mock)",
                capabilities=paper_caps,
                enabled=True,
            )
        )

    @property
    def history(self) -> BrokerHistory:
        """Get accumulated broker history."""
        return self._history

    def register_broker(self, definition: BrokerDefinition) -> None:
        """Register a broker contract definition."""
        self._brokers[definition.broker_id] = definition

    def get_broker(self, broker_id: str) -> BrokerDefinition:
        """Get registered broker definition."""
        if broker_id not in self._brokers:
            raise BrokerError(f"Broker contract '{broker_id}' is not registered")
        return self._brokers[broker_id]

    def translate_plan(
        self,
        execution_plan: ExecutionPlan,
        broker_id: str | None = None,
        *,
        as_of: datetime,
        time_in_force: TimeInForce | None = None,
    ) -> BrokerExecutionPlan:
        """Translate a broker-neutral ExecutionPlan into a BrokerExecutionPlan."""
        if as_of.tzinfo is None:
            raise ValueError("translate_plan as_of datetime must be timezone-aware")

        b_id = broker_id or self._config.default_broker_id
        broker_def = self.get_broker(b_id)

        if not broker_def.enabled:
            raise BrokerError(f"Broker contract '{b_id}' is disabled")

        tif = time_in_force or self._config.default_time_in_force
        caps = broker_def.capabilities

        if self._config.validate_capabilities and tif not in caps.supported_time_in_force:
            raise BrokerError(
                f"Broker '{b_id}' does not support TimeInForce.{tif.value} (supported: {[t.value for t in caps.supported_time_in_force]})"
            )

        requests: list[BrokerRequest] = []
        accepted_cnt = 0
        rejected_cnt = 0
        skipped_cnt = 0
        tot_qty = Decimal("0")
        tot_val = Decimal("0.00")

        # Collect all planned orders across batches in deterministic order
        all_orders: list[PlannedOrder] = []
        for batch in execution_plan.batches:
            all_orders.extend(batch.orders)

        sorted_orders = sorted(all_orders, key=lambda o: o.instrument_id)

        for ord_item in sorted_orders:
            inst_id = ord_item.instrument_id
            refs = BrokerReferences(
                execution_plan_id=execution_plan.plan_id,
                position_sizing_plan_id=ord_item.references.position_sizing_plan_id,
                allocation_plan_id=ord_item.references.allocation_plan_id,
                portfolio_snapshot_id=ord_item.references.portfolio_snapshot_id,
                decision_id=ord_item.references.decision_id,
                strategy=ord_item.references.strategy,
                watchlist=ord_item.references.watchlist,
                schedule_execution_id=ord_item.references.schedule_execution_id,
            )

            if ord_item.action == OrderAction.HOLD or ord_item.status == "HOLD":
                req = BrokerRequest(
                    request_id=f"req-{self._next_counter():04d}",
                    broker_id=b_id,
                    instrument_id=inst_id,
                    action=OrderAction.HOLD,
                    order_type=ord_item.order_type,
                    quantity=Decimal("0"),
                    limit_price=None,
                    stop_price=None,
                    time_in_force=tif,
                    status="SKIPPED_HOLD",
                    explanation=f"Skipped HOLD instruction for {inst_id}",
                    as_of=as_of,
                    references=refs,
                )
                skipped_cnt += 1
                requests.append(req)
                continue

            # Validate capabilities if enabled
            status = "ACCEPTED"
            expl = f"Translated {ord_item.action.value} order for {ord_item.quantity} units to {b_id}"

            if self._config.validate_capabilities:
                if ord_item.order_type not in caps.supported_order_types:
                    status = "REJECTED_UNSUPPORTED_ORDER_TYPE"
                    expl = f"Broker '{b_id}' does not support OrderType.{ord_item.order_type.value}"
                elif (
                    ord_item.quantity % Decimal("1") != Decimal("0")
                    and not caps.supports_fractional
                ):
                    status = "REJECTED_UNSUPPORTED_FRACTIONAL"
                    expl = f"Broker '{b_id}' does not support fractional quantity {ord_item.quantity}"

            req = BrokerRequest(
                request_id=f"req-{self._next_counter():04d}",
                broker_id=b_id,
                instrument_id=inst_id,
                action=ord_item.action,
                order_type=ord_item.order_type,
                quantity=ord_item.quantity,
                limit_price=ord_item.limit_price,
                stop_price=ord_item.stop_price,
                time_in_force=tif,
                status=status,
                explanation=expl,
                as_of=as_of,
                references=refs,
            )

            if status == "ACCEPTED":
                accepted_cnt += 1
                tot_qty += ord_item.quantity
                if ord_item.limit_price is not None:
                    tot_val += _quantize(ord_item.quantity * ord_item.limit_price)
            else:
                rejected_cnt += 1

            requests.append(req)

        summary = BrokerSummary(
            as_of=as_of,
            broker_id=b_id,
            total_requests=len(requests),
            accepted_count=accepted_cnt,
            rejected_count=rejected_cnt,
            skipped_count=skipped_cnt,
            total_quantity=tot_qty,
            total_value=_quantize(tot_val),
        )

        plan_id = f"bplan-{self._next_counter():04d}"
        plan_refs = BrokerReferences(
            execution_plan_id=execution_plan.plan_id,
            position_sizing_plan_id=execution_plan.references.position_sizing_plan_id,
            allocation_plan_id=execution_plan.references.allocation_plan_id,
            portfolio_snapshot_id=execution_plan.references.portfolio_snapshot_id,
            strategy=execution_plan.references.strategy,
            watchlist=execution_plan.references.watchlist,
            schedule_execution_id=execution_plan.references.schedule_execution_id,
        )

        b_plan = BrokerExecutionPlan(
            broker_plan_id=plan_id,
            broker_id=b_id,
            as_of=as_of,
            execution_plan_id=execution_plan.plan_id,
            requests=tuple(requests),
            summary=summary,
            references=plan_refs,
        )

        if self._config.record_history:
            self._history = self._history.record(b_plan)

        return b_plan

    def create_mock_response(
        self, request: BrokerRequest, *, success: bool = True, message: str = "Mock execution contract response"
    ) -> BrokerResponse:
        """Generate a mock BrokerResponse artifact for contract testing."""
        ref = f"mock-ref-{request.request_id}" if success else None
        return BrokerResponse(
            response_id=f"resp-{self._next_counter():04d}",
            request_id=request.request_id,
            broker_id=request.broker_id,
            success=success,
            broker_order_ref=ref,
            message=message,
            as_of=request.as_of,
        )

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
