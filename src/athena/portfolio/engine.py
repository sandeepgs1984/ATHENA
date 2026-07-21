"""Portfolio Engine implementation (P5.1).

Coordinates portfolio state based exclusively on completed ATHENA decisions and operations.
Performs NO market analysis, NO position sizing, and NO order execution.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Sequence

from athena.config.models import PortfolioConfig
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction
from athena.errors import PortfolioError
from athena.portfolio.models import (
    CashBalance,
    ClosedPosition,
    Holding,
    Portfolio,
    PortfolioHistory,
    PortfolioReferences,
    PortfolioSnapshot,
    PortfolioSummary,
    ReservedCapital,
)


class PortfolioEngine:
    """Deterministic, state-only Portfolio Engine."""

    def __init__(
        self,
        config: PortfolioConfig | None = None,
        *,
        initial_as_of: datetime | None = None,
    ) -> None:
        self._config = config or PortfolioConfig()
        self._counter = 0

        # Initialize cash balance
        cash = self._config.initial_cash
        init_as_of = initial_as_of or datetime.now().astimezone()

        initial_cash = CashBalance(
            total_cash=cash,
            available_cash=cash,
            allocated_cash=Decimal("0"),
            reserved_cash=Decimal("0"),
            currency=self._config.currency,
            as_of=init_as_of,
        )

        initial_portfolio = Portfolio(
            portfolio_id="portfolio-main",
            as_of=init_as_of,
            cash=initial_cash,
            holdings={},
            closed_positions=(),
            reservations=(),
        )

        initial_summary = self._build_summary(initial_portfolio, init_as_of)
        initial_refs = PortfolioReferences()

        self._current_snapshot = PortfolioSnapshot(
            snapshot_id="snap-0000",
            as_of=init_as_of,
            portfolio=initial_portfolio,
            summary=initial_summary,
            references=initial_refs,
            operation="INIT",
        )

        self._history = PortfolioHistory()
        if self._config.record_history:
            self._history = self._history.record(self._current_snapshot)

    @property
    def current_snapshot(self) -> PortfolioSnapshot:
        """Get current portfolio snapshot."""
        return self._current_snapshot

    @property
    def portfolio(self) -> Portfolio:
        """Get current portfolio state."""
        return self._current_snapshot.portfolio

    @property
    def history(self) -> PortfolioHistory:
        """Get accumulated portfolio history."""
        return self._history

    def summarize(self) -> PortfolioSummary:
        """Get summary of current portfolio state."""
        return self._current_snapshot.summary

    # ------------------------------------------------------------------ Operations

    def open_position(
        self,
        instrument_id: str,
        quantity: int,
        price: Decimal,
        *,
        as_of: datetime,
        direction: Direction = Direction.LONG,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Open a new position."""
        self._validate_as_of(as_of)
        if quantity <= 0:
            raise PortfolioError(f"Quantity must be > 0, got {quantity}")
        if price <= Decimal("0"):
            raise PortfolioError(f"Price must be > 0, got {price}")
        if instrument_id in self.portfolio.holdings:
            raise PortfolioError(f"Holding already exists for {instrument_id}")

        cost = Decimal(quantity) * price
        cash = self.portfolio.cash

        if cost > cash.available_cash:
            raise PortfolioError(
                f"Insufficient available cash ({cash.available_cash}) for cost {cost}"
            )

        refs = references or PortfolioReferences()
        holding_id = f"hold-{self._next_counter():04d}"

        new_holding = Holding(
            holding_id=holding_id,
            instrument_id=instrument_id,
            opened_as_of=as_of,
            last_updated_as_of=as_of,
            quantity=quantity,
            avg_price=price,
            total_cost=cost,
            direction=direction,
            references=refs,
        )

        new_holdings = dict(self.portfolio.holdings)
        new_holdings[instrument_id] = new_holding

        new_cash = CashBalance(
            total_cash=cash.total_cash,
            available_cash=cash.available_cash - cost,
            allocated_cash=cash.allocated_cash + cost,
            reserved_cash=cash.reserved_cash,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation("OPEN", as_of, new_holdings, new_cash, refs)

    def increase_position(
        self,
        instrument_id: str,
        quantity: int,
        price: Decimal,
        *,
        as_of: datetime,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Increase an existing position."""
        self._validate_as_of(as_of)
        if quantity <= 0:
            raise PortfolioError(f"Quantity must be > 0, got {quantity}")
        if price <= Decimal("0"):
            raise PortfolioError(f"Price must be > 0, got {price}")
        if instrument_id not in self.portfolio.holdings:
            raise PortfolioError(f"No existing holding for {instrument_id} to increase")

        existing = self.portfolio.holdings[instrument_id]
        add_cost = Decimal(quantity) * price
        cash = self.portfolio.cash

        if add_cost > cash.available_cash:
            raise PortfolioError(
                f"Insufficient available cash ({cash.available_cash}) for cost {add_cost}"
            )

        refs = references or PortfolioReferences()
        new_quantity = existing.quantity + quantity
        new_total_cost = existing.total_cost + add_cost
        new_avg_price = new_total_cost / Decimal(new_quantity)

        updated_holding = Holding(
            holding_id=existing.holding_id,
            instrument_id=instrument_id,
            opened_as_of=existing.opened_as_of,
            last_updated_as_of=as_of,
            quantity=new_quantity,
            avg_price=new_avg_price,
            total_cost=new_total_cost,
            direction=existing.direction,
            references=refs,
        )

        new_holdings = dict(self.portfolio.holdings)
        new_holdings[instrument_id] = updated_holding

        new_cash = CashBalance(
            total_cash=cash.total_cash,
            available_cash=cash.available_cash - add_cost,
            allocated_cash=cash.allocated_cash + add_cost,
            reserved_cash=cash.reserved_cash,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation("INCREASE", as_of, new_holdings, new_cash, refs)

    def reduce_position(
        self,
        instrument_id: str,
        quantity: int,
        price: Decimal,
        *,
        as_of: datetime,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Reduce an existing position quantity."""
        self._validate_as_of(as_of)
        if quantity <= 0:
            raise PortfolioError(f"Quantity must be > 0, got {quantity}")
        if price <= Decimal("0"):
            raise PortfolioError(f"Price must be > 0, got {price}")
        if instrument_id not in self.portfolio.holdings:
            raise PortfolioError(f"No existing holding for {instrument_id} to reduce")

        existing = self.portfolio.holdings[instrument_id]
        if quantity > existing.quantity:
            raise PortfolioError(
                f"Cannot reduce {quantity} > existing quantity {existing.quantity}"
            )

        if quantity == existing.quantity:
            return self.close_position(instrument_id, price, as_of=as_of, references=references)

        refs = references or PortfolioReferences()
        proceeds = Decimal(quantity) * price
        cost_reduced = Decimal(quantity) * existing.avg_price

        new_quantity = existing.quantity - quantity
        new_total_cost = Decimal(new_quantity) * existing.avg_price

        updated_holding = Holding(
            holding_id=existing.holding_id,
            instrument_id=instrument_id,
            opened_as_of=existing.opened_as_of,
            last_updated_as_of=as_of,
            quantity=new_quantity,
            avg_price=existing.avg_price,
            total_cost=new_total_cost,
            direction=existing.direction,
            references=refs,
        )

        new_holdings = dict(self.portfolio.holdings)
        new_holdings[instrument_id] = updated_holding

        cash = self.portfolio.cash
        new_allocated = cash.allocated_cash - cost_reduced
        new_available = cash.available_cash + proceeds
        new_total = new_available + new_allocated + cash.reserved_cash

        new_cash = CashBalance(
            total_cash=new_total,
            available_cash=new_available,
            allocated_cash=new_allocated,
            reserved_cash=cash.reserved_cash,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation("REDUCE", as_of, new_holdings, new_cash, refs)

    def close_position(
        self,
        instrument_id: str,
        price: Decimal,
        *,
        as_of: datetime,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Close an existing position completely."""
        self._validate_as_of(as_of)
        if price <= Decimal("0"):
            raise PortfolioError(f"Price must be > 0, got {price}")
        if instrument_id not in self.portfolio.holdings:
            raise PortfolioError(f"No existing holding for {instrument_id} to close")

        existing = self.portfolio.holdings[instrument_id]
        refs = references or PortfolioReferences()
        proceeds = Decimal(existing.quantity) * price

        closed_id = f"closed-{self._next_counter():04d}"
        closed_pos = ClosedPosition(
            closed_position_id=closed_id,
            holding_id=existing.holding_id,
            instrument_id=instrument_id,
            opened_as_of=existing.opened_as_of,
            closed_as_of=as_of,
            quantity=existing.quantity,
            avg_entry_price=existing.avg_price,
            avg_exit_price=price,
            total_cost=existing.total_cost,
            total_proceeds=proceeds,
            direction=existing.direction,
            references=refs,
        )

        new_holdings = dict(self.portfolio.holdings)
        del new_holdings[instrument_id]

        new_closed_positions = self.portfolio.closed_positions + (closed_pos,)

        cash = self.portfolio.cash
        new_allocated = cash.allocated_cash - existing.total_cost
        new_available = cash.available_cash + proceeds
        new_total = new_available + new_allocated + cash.reserved_cash

        new_cash = CashBalance(
            total_cash=new_total,
            available_cash=new_available,
            allocated_cash=new_allocated,
            reserved_cash=cash.reserved_cash,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation(
            "CLOSE",
            as_of,
            new_holdings,
            new_cash,
            refs,
            closed_positions=new_closed_positions,
        )

    def hold_position(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Record a HOLD decision for an instrument (updates last_updated_as_of if held)."""
        self._validate_as_of(as_of)
        refs = references or PortfolioReferences()
        new_holdings = dict(self.portfolio.holdings)

        if instrument_id in new_holdings:
            existing = new_holdings[instrument_id]
            new_holdings[instrument_id] = Holding(
                holding_id=existing.holding_id,
                instrument_id=instrument_id,
                opened_as_of=existing.opened_as_of,
                last_updated_as_of=as_of,
                quantity=existing.quantity,
                avg_price=existing.avg_price,
                total_cost=existing.total_cost,
                direction=existing.direction,
                references=refs,
            )

        cash = self.portfolio.cash
        new_cash = CashBalance(
            total_cash=cash.total_cash,
            available_cash=cash.available_cash,
            allocated_cash=cash.allocated_cash,
            reserved_cash=cash.reserved_cash,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation("HOLD", as_of, new_holdings, new_cash, refs)

    def reserve_capital(
        self,
        reservation_id: str,
        reason: str,
        amount: Decimal,
        *,
        as_of: datetime,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Reserve capital from available cash."""
        self._validate_as_of(as_of)
        if amount <= Decimal("0"):
            raise PortfolioError(f"Reservation amount must be > 0, got {amount}")
        cash = self.portfolio.cash
        if amount > cash.available_cash:
            raise PortfolioError(
                f"Cannot reserve {amount} > available cash {cash.available_cash}"
            )

        refs = references or PortfolioReferences()
        res = ReservedCapital(
            reservation_id=reservation_id,
            reason=reason,
            amount=amount,
            created_as_of=as_of,
            references=refs,
        )

        new_reservations = self.portfolio.reservations + (res,)

        new_cash = CashBalance(
            total_cash=cash.total_cash,
            available_cash=cash.available_cash - amount,
            allocated_cash=cash.allocated_cash,
            reserved_cash=cash.reserved_cash + amount,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation(
            "RESERVE",
            as_of,
            self.portfolio.holdings,
            new_cash,
            refs,
            reservations=new_reservations,
        )

    def release_capital(
        self,
        reservation_id: str,
        *,
        as_of: datetime,
        references: PortfolioReferences | None = None,
    ) -> PortfolioSnapshot:
        """Release a capital reservation back to available cash."""
        self._validate_as_of(as_of)
        res_idx = next(
            (i for i, r in enumerate(self.portfolio.reservations) if r.reservation_id == reservation_id),
            None,
        )
        if res_idx is None:
            raise PortfolioError(f"Reservation {reservation_id} not found")

        target_res = self.portfolio.reservations[res_idx]
        new_reservations = tuple(
            r for i, r in enumerate(self.portfolio.reservations) if i != res_idx
        )

        refs = references or target_res.references
        cash = self.portfolio.cash

        new_cash = CashBalance(
            total_cash=cash.total_cash,
            available_cash=cash.available_cash + target_res.amount,
            allocated_cash=cash.allocated_cash,
            reserved_cash=cash.reserved_cash - target_res.amount,
            currency=cash.currency,
            as_of=as_of,
        )

        return self._commit_operation(
            "RELEASE",
            as_of,
            self.portfolio.holdings,
            new_cash,
            refs,
            reservations=new_reservations,
        )

    def apply_decision(
        self,
        decision: Decision,
        price: Decimal,
        quantity: int,
        *,
        as_of: datetime,
        strategy: str | None = None,
        watchlist: str | None = None,
        schedule_execution_id: str | None = None,
    ) -> PortfolioSnapshot:
        """Apply a completed ATHENA Decision object to the portfolio."""
        if decision.instrument_id is None:
            raise PortfolioError("Cannot apply decision without instrument_id")

        refs = PortfolioReferences(
            decision_id=decision.decision_id,
            strategy=strategy,
            watchlist=watchlist,
            schedule_execution_id=schedule_execution_id,
        )

        inst = decision.instrument_id
        dtype = decision.decision_type

        if dtype in (DecisionType.TRADE, DecisionType.INCREASE_POSITION):
            if inst in self.portfolio.holdings:
                return self.increase_position(
                    inst, quantity, price, as_of=as_of, references=refs
                )
            else:
                return self.open_position(
                    inst,
                    quantity,
                    price,
                    as_of=as_of,
                    direction=decision.direction,
                    references=refs,
                )
        elif dtype is DecisionType.REDUCE_POSITION:
            if inst in self.portfolio.holdings:
                return self.reduce_position(
                    inst, quantity, price, as_of=as_of, references=refs
                )
            return self.hold_position(inst, as_of=as_of, references=refs)
        elif dtype in (DecisionType.FULL_EXIT, DecisionType.PARTIAL_EXIT):
            if inst in self.portfolio.holdings:
                if (
                    dtype is DecisionType.PARTIAL_EXIT
                    and quantity < self.portfolio.holdings[inst].quantity
                ):
                    return self.reduce_position(
                        inst, quantity, price, as_of=as_of, references=refs
                    )
                return self.close_position(inst, price, as_of=as_of, references=refs)
            return self.hold_position(inst, as_of=as_of, references=refs)
        else:
            # NO_TRADE, WATCH, WAIT, AVOID_SECTOR, etc.
            return self.hold_position(inst, as_of=as_of, references=refs)

    # ------------------------------------------------------------------ Internal Helpers

    def _validate_as_of(self, as_of: datetime) -> None:
        if as_of.tzinfo is None:
            raise ValueError("Operation as_of datetime must be timezone-aware")
        if as_of < self.portfolio.as_of:
            raise PortfolioError(
                f"Operation as_of ({as_of.isoformat()}) is earlier than portfolio as_of ({self.portfolio.as_of.isoformat()})"
            )

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter

    def _commit_operation(
        self,
        operation: str,
        as_of: datetime,
        holdings: dict[str, Holding] | Mapping[str, Holding],
        cash: CashBalance,
        references: PortfolioReferences,
        *,
        closed_positions: Sequence[ClosedPosition] | None = None,
        reservations: Sequence[ReservedCapital] | None = None,
    ) -> PortfolioSnapshot:
        cp = (
            tuple(closed_positions)
            if closed_positions is not None
            else self.portfolio.closed_positions
        )
        res = (
            tuple(reservations)
            if reservations is not None
            else self.portfolio.reservations
        )

        new_portfolio = Portfolio(
            portfolio_id=self.portfolio.portfolio_id,
            as_of=as_of,
            cash=cash,
            holdings=holdings,
            closed_positions=cp,
            reservations=res,
        )

        summary = self._build_summary(new_portfolio, as_of)
        snap_id = f"snap-{self._next_counter():04d}"

        snapshot = PortfolioSnapshot(
            snapshot_id=snap_id,
            as_of=as_of,
            portfolio=new_portfolio,
            summary=summary,
            references=references,
            operation=operation,
        )

        self._current_snapshot = snapshot
        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _build_summary(self, portfolio: Portfolio, as_of: datetime) -> PortfolioSummary:
        tot_qty = sum(h.quantity for h in portfolio.holdings.values())
        h_by_inst = {k: v.quantity for k, v in sorted(portfolio.holdings.items())}

        return PortfolioSummary(
            as_of=as_of,
            total_holdings=len(portfolio.holdings),
            total_quantity=tot_qty,
            total_allocated_cash=portfolio.cash.allocated_cash,
            total_available_cash=portfolio.cash.available_cash,
            total_reserved_cash=portfolio.cash.reserved_cash,
            total_closed_positions=len(portfolio.closed_positions),
            holdings_by_instrument=h_by_inst,
        )
