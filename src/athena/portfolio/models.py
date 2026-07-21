"""Portfolio Engine artifacts (P5.1).

Immutable portfolio state representations. The Portfolio Engine maintains
portfolio state, holdings, available cash, reserved capital, realized/closed
positions, and append-only history.

It performs NO market analysis, NO position sizing calculations, and NO order
execution — it records what ATHENA's completed pipeline decided.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType

from athena.domain.enums import Direction


def _frozen_int_map(value: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class PortfolioReferences:
    """Cross-references back to originating evidence and decision context."""

    decision_id: str | None = None
    strategy: str | None = None
    watchlist: str | None = None
    schedule_execution_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "strategy": self.strategy,
            "watchlist": self.watchlist,
            "schedule_execution_id": self.schedule_execution_id,
        }


@dataclass(frozen=True, slots=True)
class Holding:
    """An open position / active holding in an instrument."""

    holding_id: str
    instrument_id: str
    opened_as_of: datetime
    last_updated_as_of: datetime
    quantity: int
    avg_price: Decimal
    total_cost: Decimal
    direction: Direction = Direction.LONG
    references: PortfolioReferences = field(default_factory=PortfolioReferences)

    def __post_init__(self) -> None:
        if not self.holding_id:
            raise ValueError("Holding.holding_id is mandatory")
        if not self.instrument_id:
            raise ValueError("Holding.instrument_id is mandatory")
        if self.opened_as_of.tzinfo is None or self.last_updated_as_of.tzinfo is None:
            raise ValueError("Holding timestamps must be timezone-aware")
        if self.opened_as_of > self.last_updated_as_of:
            raise ValueError("Holding.opened_as_of must be <= last_updated_as_of")
        if self.quantity <= 0:
            raise ValueError("Holding.quantity must be > 0")
        if self.avg_price <= Decimal("0"):
            raise ValueError("Holding.avg_price must be > 0")
        if self.total_cost <= Decimal("0"):
            raise ValueError("Holding.total_cost must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "holding_id": self.holding_id,
            "instrument_id": self.instrument_id,
            "opened_as_of": self.opened_as_of.isoformat(),
            "last_updated_as_of": self.last_updated_as_of.isoformat(),
            "quantity": self.quantity,
            "avg_price": str(self.avg_price),
            "total_cost": str(self.total_cost),
            "direction": self.direction.value,
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ClosedPosition:
    """A closed holding / realized position."""

    closed_position_id: str
    holding_id: str
    instrument_id: str
    opened_as_of: datetime
    closed_as_of: datetime
    quantity: int
    avg_entry_price: Decimal
    avg_exit_price: Decimal
    total_cost: Decimal
    total_proceeds: Decimal
    direction: Direction = Direction.LONG
    references: PortfolioReferences = field(default_factory=PortfolioReferences)

    def __post_init__(self) -> None:
        if not self.closed_position_id or not self.holding_id or not self.instrument_id:
            raise ValueError("ClosedPosition IDs are mandatory")
        if self.opened_as_of.tzinfo is None or self.closed_as_of.tzinfo is None:
            raise ValueError("ClosedPosition timestamps must be timezone-aware")
        if self.opened_as_of > self.closed_as_of:
            raise ValueError("ClosedPosition.opened_as_of must be <= closed_as_of")
        if self.quantity <= 0:
            raise ValueError("ClosedPosition.quantity must be > 0")
        if self.avg_entry_price <= Decimal("0") or self.avg_exit_price <= Decimal("0"):
            raise ValueError("ClosedPosition prices must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "closed_position_id": self.closed_position_id,
            "holding_id": self.holding_id,
            "instrument_id": self.instrument_id,
            "opened_as_of": self.opened_as_of.isoformat(),
            "closed_as_of": self.closed_as_of.isoformat(),
            "quantity": self.quantity,
            "avg_entry_price": str(self.avg_entry_price),
            "avg_exit_price": str(self.avg_exit_price),
            "total_cost": str(self.total_cost),
            "total_proceeds": str(self.total_proceeds),
            "direction": self.direction.value,
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CashBalance:
    """Cash allocation state at a point in time."""

    total_cash: Decimal
    available_cash: Decimal
    allocated_cash: Decimal
    reserved_cash: Decimal
    as_of: datetime
    currency: str = "INR"

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("CashBalance.as_of must be timezone-aware")
        if (
            self.total_cash < Decimal("0")
            or self.available_cash < Decimal("0")
            or self.allocated_cash < Decimal("0")
            or self.reserved_cash < Decimal("0")
        ):
            raise ValueError("CashBalance values must be >= 0")
        if self.total_cash != (self.available_cash + self.allocated_cash + self.reserved_cash):
            raise ValueError("CashBalance.total_cash must equal available + allocated + reserved")

    def to_dict(self) -> dict[str, object]:
        return {
            "total_cash": str(self.total_cash),
            "available_cash": str(self.available_cash),
            "allocated_cash": str(self.allocated_cash),
            "reserved_cash": str(self.reserved_cash),
            "as_of": self.as_of.isoformat(),
            "currency": self.currency,
        }


@dataclass(frozen=True, slots=True)
class ReservedCapital:
    """Explicitly reserved capital allocation."""

    reservation_id: str
    reason: str
    amount: Decimal
    created_as_of: datetime
    references: PortfolioReferences = field(default_factory=PortfolioReferences)

    def __post_init__(self) -> None:
        if not self.reservation_id or not self.reason:
            raise ValueError("ReservedCapital mandatory fields missing")
        if self.created_as_of.tzinfo is None:
            raise ValueError("ReservedCapital.created_as_of must be timezone-aware")
        if self.amount <= Decimal("0"):
            raise ValueError("ReservedCapital.amount must be > 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "reservation_id": self.reservation_id,
            "reason": self.reason,
            "amount": str(self.amount),
            "created_as_of": self.created_as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Portfolio:
    """Aggregate portfolio state."""

    portfolio_id: str
    as_of: datetime
    cash: CashBalance
    holdings: Mapping[str, Holding] = field(default_factory=dict)
    closed_positions: tuple[ClosedPosition, ...] = ()
    reservations: tuple[ReservedCapital, ...] = ()

    def __post_init__(self) -> None:
        if not self.portfolio_id:
            raise ValueError("Portfolio.portfolio_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("Portfolio.as_of must be timezone-aware")
        object.__setattr__(self, "holdings", MappingProxyType(dict(self.holdings)))

    def to_dict(self) -> dict[str, object]:
        return {
            "portfolio_id": self.portfolio_id,
            "as_of": self.as_of.isoformat(),
            "cash": self.cash.to_dict(),
            "holdings": {k: v.to_dict() for k, v in sorted(self.holdings.items())},
            "closed_positions": [p.to_dict() for p in self.closed_positions],
            "reservations": [r.to_dict() for r in self.reservations],
        }


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    """Summary metrics of portfolio state."""

    as_of: datetime
    total_holdings: int
    total_quantity: int
    total_allocated_cash: Decimal
    total_available_cash: Decimal
    total_reserved_cash: Decimal
    total_closed_positions: int
    holdings_by_instrument: Mapping[str, int]

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("PortfolioSummary.as_of must be timezone-aware")
        object.__setattr__(
            self, "holdings_by_instrument", _frozen_int_map(self.holdings_by_instrument)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "total_holdings": self.total_holdings,
            "total_quantity": self.total_quantity,
            "total_allocated_cash": str(self.total_allocated_cash),
            "total_available_cash": str(self.total_available_cash),
            "total_reserved_cash": str(self.total_reserved_cash),
            "total_closed_positions": self.total_closed_positions,
            "holdings_by_instrument": dict(self.holdings_by_instrument),
        }


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Immutable point-in-time snapshot of the portfolio after an operation."""

    snapshot_id: str
    as_of: datetime
    portfolio: Portfolio
    summary: PortfolioSummary
    references: PortfolioReferences
    operation: str

    def __post_init__(self) -> None:
        if not self.snapshot_id or not self.operation:
            raise ValueError("PortfolioSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("PortfolioSnapshot.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "operation": self.operation,
            "portfolio": self.portfolio.to_dict(),
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class PortfolioHistory:
    """Append-only record of portfolio snapshots."""

    records: tuple[PortfolioSnapshot, ...] = ()

    def record(self, snapshot: PortfolioSnapshot) -> PortfolioHistory:
        """Return a new history with snapshot appended."""
        return PortfolioHistory(records=self.records + (snapshot,))

    def for_instrument(self, instrument_id: str) -> tuple[PortfolioSnapshot, ...]:
        """Filter snapshots that involved instrument_id."""
        res = []
        for snap in self.records:
            if instrument_id in snap.portfolio.holdings or any(
                cp.instrument_id == instrument_id for cp in snap.portfolio.closed_positions
            ):
                res.append(snap)
        return tuple(res)

    def for_operation(self, operation: str) -> tuple[PortfolioSnapshot, ...]:
        """Filter snapshots by operation name."""
        return tuple(snap for snap in self.records if snap.operation == operation)

    def to_dict(self) -> dict[str, object]:
        return {"records": [snap.to_dict() for snap in self.records]}
