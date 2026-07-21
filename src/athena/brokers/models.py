"""Broker Abstraction Layer artifacts (P5.5).

Immutable broker integration models and capability contracts. The Broker Abstraction
Layer defines canonical interfaces, capabilities, and requests.

It performs NO network communication, NO OAuth flows, NO WebSocket/REST connections, and NO
live order placement — it defines integration contracts only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from athena.config.models import OrderAction, OrderType, TimeInForce


@dataclass(frozen=True, slots=True)
class BrokerReferences:
    """Cross-references back to originating execution plan, sizing, allocation, portfolio, decision, and schedule."""

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
class BrokerCapabilities:
    """Capabilities supported by a broker integration contract."""

    supported_order_types: tuple[OrderType, ...] = (OrderType.MARKET, OrderType.LIMIT)
    supports_fractional: bool = False
    supports_shorting: bool = False
    supported_time_in_force: tuple[TimeInForce, ...] = (TimeInForce.DAY, TimeInForce.IOC, TimeInForce.GTC)
    max_orders_per_request: int = 50

    def to_dict(self) -> dict[str, object]:
        return {
            "supported_order_types": [ot.value for ot in self.supported_order_types],
            "supports_fractional": self.supports_fractional,
            "supports_shorting": self.supports_shorting,
            "supported_time_in_force": [tif.value for tif in self.supported_time_in_force],
            "max_orders_per_request": self.max_orders_per_request,
        }


@dataclass(frozen=True, slots=True)
class BrokerDefinition:
    """Canonical broker definition and configuration."""

    broker_id: str
    name: str
    capabilities: BrokerCapabilities
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.broker_id or not self.name:
            raise ValueError("BrokerDefinition mandatory fields missing")

    def to_dict(self) -> dict[str, object]:
        return {
            "broker_id": self.broker_id,
            "name": self.name,
            "capabilities": self.capabilities.to_dict(),
            "enabled": self.enabled,
        }


@dataclass(frozen=True, slots=True)
class BrokerRequest:
    """A single canonical broker order request."""

    request_id: str
    broker_id: str
    instrument_id: str
    action: OrderAction
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    time_in_force: TimeInForce
    status: str
    explanation: str
    as_of: datetime
    references: BrokerReferences = field(default_factory=BrokerReferences)

    def __post_init__(self) -> None:
        if not self.request_id or not self.broker_id or not self.instrument_id or not self.status:
            raise ValueError("BrokerRequest mandatory fields missing")
        if not self.explanation:
            raise ValueError("BrokerRequest.explanation is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("BrokerRequest.as_of must be timezone-aware")
        if self.quantity < Decimal("0"):
            raise ValueError("BrokerRequest.quantity must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "broker_id": self.broker_id,
            "instrument_id": self.instrument_id,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "quantity": str(self.quantity),
            "limit_price": str(self.limit_price) if self.limit_price is not None else None,
            "stop_price": str(self.stop_price) if self.stop_price is not None else None,
            "time_in_force": self.time_in_force.value,
            "status": self.status,
            "explanation": self.explanation,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BrokerResponse:
    """Abstract/mock broker response artifact."""

    response_id: str
    request_id: str
    broker_id: str
    success: bool
    broker_order_ref: str | None
    message: str
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.response_id or not self.request_id or not self.broker_id:
            raise ValueError("BrokerResponse mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("BrokerResponse.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "response_id": self.response_id,
            "request_id": self.request_id,
            "broker_id": self.broker_id,
            "success": self.success,
            "broker_order_ref": self.broker_order_ref,
            "message": self.message,
            "as_of": self.as_of.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BrokerSummary:
    """Aggregated summary of a broker execution plan."""

    as_of: datetime
    broker_id: str
    total_requests: int
    accepted_count: int
    rejected_count: int
    skipped_count: int
    total_quantity: Decimal
    total_value: Decimal

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("BrokerSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "broker_id": self.broker_id,
            "total_requests": self.total_requests,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "skipped_count": self.skipped_count,
            "total_quantity": str(self.total_quantity),
            "total_value": str(self.total_value),
        }


@dataclass(frozen=True, slots=True)
class BrokerExecutionPlan:
    """Immutable output of translating an ExecutionPlan for a specific broker."""

    broker_plan_id: str
    broker_id: str
    as_of: datetime
    execution_plan_id: str
    requests: tuple[BrokerRequest, ...]
    summary: BrokerSummary
    references: BrokerReferences = field(default_factory=BrokerReferences)

    def __post_init__(self) -> None:
        if not self.broker_plan_id or not self.broker_id or not self.execution_plan_id:
            raise ValueError("BrokerExecutionPlan mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("BrokerExecutionPlan.as_of must be timezone-aware")

    def request_for(self, instrument_id: str) -> BrokerRequest | None:
        """Find broker request for an instrument."""
        return next((r for r in self.requests if r.instrument_id == instrument_id), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "broker_plan_id": self.broker_plan_id,
            "broker_id": self.broker_id,
            "as_of": self.as_of.isoformat(),
            "execution_plan_id": self.execution_plan_id,
            "requests": [r.to_dict() for r in self.requests],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class BrokerHistory:
    """Append-only record of broker execution plans."""

    records: tuple[BrokerExecutionPlan, ...] = ()

    def record(self, plan: BrokerExecutionPlan) -> BrokerHistory:
        """Return a new history with plan appended."""
        return BrokerHistory(records=self.records + (plan,))

    def for_broker(self, broker_id: str) -> tuple[BrokerExecutionPlan, ...]:
        """Find all broker execution plans for a broker_id."""
        return tuple(p for p in self.records if p.broker_id == broker_id)

    def for_instrument(self, instrument_id: str) -> tuple[BrokerRequest, ...]:
        """Find all broker requests for an instrument across history."""
        res = []
        for plan in self.records:
            req = plan.request_for(instrument_id)
            if req is not None:
                res.append(req)
        return tuple(res)

    def to_dict(self) -> dict[str, object]:
        return {"records": [plan.to_dict() for plan in self.records]}
