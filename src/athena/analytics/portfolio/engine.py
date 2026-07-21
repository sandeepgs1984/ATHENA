"""Portfolio Analytics Engine implementation (P5.7).

Computes realized/unrealized P&L, portfolio returns, win/loss accounting, exposures, and drawdowns.
Performs NO investment decision making, NO capital allocation, NO position sizing, NO order planning, and NO broker communication.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from athena.analytics.portfolio.models import (
    AnalyticsSummary,
    PerformanceSnapshot,
    PortfolioAnalyticsHistory,
    PortfolioAnalyticsReferences,
    PortfolioPerformance,
    TradePerformance,
)
from athena.config.models import PortfolioAnalyticsConfig
from athena.domain.enums import Direction
from athena.errors import PortfolioAnalyticsError
from athena.execution.models import ExecutionState
from athena.portfolio.models import PortfolioSnapshot

_TWO_PLACES = Decimal("0.01")


def _quantize(val: Decimal) -> Decimal:
    return val.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


class PortfolioAnalyticsEngine:
    """Deterministic, policy-driven Portfolio Analytics Engine."""

    def __init__(self, config: PortfolioAnalyticsConfig | None = None) -> None:
        self._config = config or PortfolioAnalyticsConfig()
        self._counter = 0
        self._peak_value: Decimal = self._config.initial_capital
        self._max_drawdown_pct: Decimal = Decimal("0.00")
        self._history = PortfolioAnalyticsHistory()

    @property
    def history(self) -> PortfolioAnalyticsHistory:
        """Get accumulated analytics history."""
        return self._history

    def analyze(
        self,
        portfolio_snapshot: PortfolioSnapshot,
        execution_state: ExecutionState | None = None,
        current_prices: Mapping[str, Decimal] | None = None,
        *,
        as_of: datetime,
    ) -> PerformanceSnapshot:
        """Compute comprehensive performance snapshot for a portfolio state."""
        if as_of.tzinfo is None:
            raise ValueError("analyze as_of datetime must be timezone-aware")

        prices = current_prices or {}

        # 1. Compute position unrealized P&L and exposures
        unrealized_pnl = Decimal("0.00")
        gross_exp = Decimal("0.00")
        net_exp = Decimal("0.00")

        # Sort holdings deterministically by instrument_id
        sorted_pos_ids = sorted(portfolio_snapshot.portfolio.holdings.keys())

        for inst_id in sorted_pos_ids:
            pos = portfolio_snapshot.portfolio.holdings[inst_id]
            price = prices.get(inst_id, pos.avg_price)
            mkt_val = pos.quantity * price
            gross_exp += mkt_val
            net_exp += mkt_val  # Long positions
            unrealized_pnl += (price - pos.avg_price) * pos.quantity

        unrealized_pnl = _quantize(unrealized_pnl)
        gross_exp = _quantize(gross_exp)
        net_exp = _quantize(net_exp)

        # 2. Compute portfolio valuation and returns
        port_val = portfolio_snapshot.portfolio.cash.available_cash + portfolio_snapshot.portfolio.cash.reserved_cash + gross_exp
        if self._peak_value < port_val:
            self._peak_value = port_val

        dd = self._peak_value - port_val
        dd_pct = (dd / self._peak_value * Decimal("100")) if self._peak_value > Decimal("0") else Decimal("0.00")
        dd_pct = _quantize(dd_pct)

        if self._max_drawdown_pct < dd_pct:
            self._max_drawdown_pct = dd_pct

        init_cap = self._config.initial_capital
        tot_return_pct = ((port_val - init_cap) / init_cap * Decimal("100")) if init_cap > Decimal("0") else Decimal("0.00")
        tot_return_pct = _quantize(tot_return_pct)

        cash_val = portfolio_snapshot.portfolio.cash.total_cash
        cash_util_pct = ((port_val - cash_val) / port_val * Decimal("100")) if port_val > Decimal("0") else Decimal("0.00")
        cash_util_pct = _quantize(cash_util_pct)

        realized_pnl = sum((cp.total_proceeds - cp.total_cost for cp in portfolio_snapshot.portfolio.closed_positions), Decimal("0.00"))
        total_pnl = realized_pnl + unrealized_pnl

        # 3. Compute trade performance metrics from closed positions
        trade_perfs: list[TradePerformance] = []
        win_cnt = 0
        loss_cnt = 0
        tot_win_val = Decimal("0.00")
        tot_loss_val = Decimal("0.00")
        tot_days = 0.0

        sorted_closed = sorted(portfolio_snapshot.portfolio.closed_positions, key=lambda cp: cp.instrument_id)

        for cp in sorted_closed:
            pnl = cp.total_proceeds - cp.total_cost
            ret_pct = ((cp.avg_exit_price - cp.avg_entry_price) / cp.avg_entry_price * Decimal("100")) if cp.avg_entry_price > Decimal("0") else Decimal("0.00")
            is_win = pnl > Decimal("0")
            is_loss = pnl < Decimal("0")

            if is_win:
                win_cnt += 1
                tot_win_val += pnl
            elif is_loss:
                loss_cnt += 1
                tot_loss_val += abs(pnl)

            days = (cp.closed_as_of - cp.opened_as_of).total_seconds() / 86400.0
            tot_days += days

            t_ref = PortfolioAnalyticsReferences(
                execution_state_id=execution_state.state_id if execution_state else None,
                broker_execution_plan_id=execution_state.broker_execution_plan_id if execution_state else None,
                portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
                decision_id=cp.references.decision_id,
                strategy=cp.references.strategy,
                watchlist=cp.references.watchlist,
                schedule_execution_id=cp.references.schedule_execution_id,
            )

            t_perf = TradePerformance(
                trade_id=f"trade-{self._next_counter():04d}",
                instrument_id=cp.instrument_id,
                direction=Direction.LONG,
                entry_price=cp.avg_entry_price,
                exit_price=cp.avg_exit_price,
                quantity=cp.quantity,
                realized_pnl=cp.total_proceeds - cp.total_cost,
                return_pct=_quantize(ret_pct),
                holding_period_days=round(days, 2),
                is_win=is_win,
                is_loss=is_loss,
                as_of=as_of,
                references=t_ref,
            )
            trade_perfs.append(t_perf)

        tot_trades = len(sorted_closed)
        win_rate = (Decimal(win_cnt) / Decimal(tot_trades) * Decimal("100")) if tot_trades > 0 else Decimal("0.00")
        avg_gain = (tot_win_val / Decimal(win_cnt)) if win_cnt > 0 else Decimal("0.00")
        avg_loss = (tot_loss_val / Decimal(loss_cnt)) if loss_cnt > 0 else Decimal("0.00")
        wl_ratio = (avg_gain / avg_loss) if avg_loss > Decimal("0") else Decimal("0.00")
        avg_holding_days = round(tot_days / tot_trades, 2) if tot_trades > 0 else 0.0

        plan_refs = PortfolioAnalyticsReferences(
            execution_state_id=execution_state.state_id if execution_state else None,
            broker_execution_plan_id=execution_state.broker_execution_plan_id if execution_state else None,
            portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
        )

        port_perf = PortfolioPerformance(
            as_of=as_of,
            realized_pnl=_quantize(realized_pnl),
            unrealized_pnl=_quantize(unrealized_pnl),
            total_pnl=_quantize(total_pnl),
            total_return_pct=tot_return_pct,
            portfolio_value=_quantize(port_val),
            peak_portfolio_value=_quantize(self._peak_value),
            drawdown=_quantize(dd),
            drawdown_pct=dd_pct,
            max_drawdown_pct=self._max_drawdown_pct,
            gross_exposure=gross_exp,
            net_exposure=net_exp,
            cash_utilization_pct=cash_util_pct,
            references=plan_refs,
        )

        summary = AnalyticsSummary(
            as_of=as_of,
            total_trades=tot_trades,
            winning_trades=win_cnt,
            losing_trades=loss_cnt,
            win_rate_pct=_quantize(win_rate),
            avg_gain=_quantize(avg_gain),
            avg_loss=_quantize(avg_loss),
            win_loss_ratio=_quantize(wl_ratio),
            avg_holding_period_days=avg_holding_days,
            max_drawdown_pct=self._max_drawdown_pct,
        )

        snapshot_id = f"psnap-{self._next_counter():04d}"
        snapshot = PerformanceSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            portfolio_performance=port_perf,
            trade_performances=tuple(trade_perfs),
            summary=summary,
            references=plan_refs,
        )

        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
