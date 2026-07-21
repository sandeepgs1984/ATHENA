"""Portfolio Analytics Engine artifacts (P5.7).

Immutable performance metrics and analytics snapshot models. The Portfolio Analytics
Engine computes realized/unrealized P&L, returns, win/loss stats, exposure, and drawdowns.

It performs NO investment decision making, NO capital allocation, NO position sizing, NO
order planning, and NO broker communication — it measures outcomes only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from athena.domain.enums import Direction


@dataclass(frozen=True, slots=True)
class PortfolioAnalyticsReferences:
    """Cross-references back to originating execution state, broker plan, sizing, allocation, portfolio, decision, and schedule."""

    execution_state_id: str | None = None
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
            "execution_state_id": self.execution_state_id,
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
class TradePerformance:
    """Performance outcome for a completed trade/position."""

    trade_id: str
    instrument_id: str
    direction: Direction
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    realized_pnl: Decimal
    return_pct: Decimal
    holding_period_days: float
    is_win: bool
    is_loss: bool
    as_of: datetime
    references: PortfolioAnalyticsReferences = field(default_factory=PortfolioAnalyticsReferences)

    def __post_init__(self) -> None:
        if not self.trade_id or not self.instrument_id:
            raise ValueError("TradePerformance mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("TradePerformance.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_id": self.trade_id,
            "instrument_id": self.instrument_id,
            "direction": self.direction.value,
            "entry_price": str(self.entry_price),
            "exit_price": str(self.exit_price),
            "quantity": str(self.quantity),
            "realized_pnl": str(self.realized_pnl),
            "return_pct": str(self.return_pct),
            "holding_period_days": self.holding_period_days,
            "is_win": self.is_win,
            "is_loss": self.is_loss,
            "as_of": self.as_of.isoformat(),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PortfolioPerformance:
    """Aggregated portfolio performance metrics."""

    as_of: datetime
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    total_return_pct: Decimal
    portfolio_value: Decimal
    peak_portfolio_value: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal
    max_drawdown_pct: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    cash_utilization_pct: Decimal
    references: PortfolioAnalyticsReferences = field(default_factory=PortfolioAnalyticsReferences)

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("PortfolioPerformance.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "total_pnl": str(self.total_pnl),
            "total_return_pct": str(self.total_return_pct),
            "portfolio_value": str(self.portfolio_value),
            "peak_portfolio_value": str(self.peak_portfolio_value),
            "drawdown": str(self.drawdown),
            "drawdown_pct": str(self.drawdown_pct),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "gross_exposure": str(self.gross_exposure),
            "net_exposure": str(self.net_exposure),
            "cash_utilization_pct": str(self.cash_utilization_pct),
            "references": self.references.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    """Summary tallies and statistics across trade performance."""

    as_of: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    avg_gain: Decimal
    avg_loss: Decimal
    win_loss_ratio: Decimal
    avg_holding_period_days: float
    max_drawdown_pct: Decimal

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None:
            raise ValueError("AnalyticsSummary.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": str(self.win_rate_pct),
            "avg_gain": str(self.avg_gain),
            "avg_loss": str(self.avg_loss),
            "win_loss_ratio": str(self.win_loss_ratio),
            "avg_holding_period_days": self.avg_holding_period_days,
            "max_drawdown_pct": str(self.max_drawdown_pct),
        }


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    """Immutable output of running the Portfolio Analytics Engine."""

    snapshot_id: str
    as_of: datetime
    portfolio_performance: PortfolioPerformance
    trade_performances: tuple[TradePerformance, ...]
    summary: AnalyticsSummary
    references: PortfolioAnalyticsReferences = field(default_factory=PortfolioAnalyticsReferences)

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("PerformanceSnapshot mandatory fields missing")
        if self.as_of.tzinfo is None:
            raise ValueError("PerformanceSnapshot.as_of must be timezone-aware")

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "as_of": self.as_of.isoformat(),
            "portfolio_performance": self.portfolio_performance.to_dict(),
            "trade_performances": [t.to_dict() for t in self.trade_performances],
            "summary": self.summary.to_dict(),
            "references": self.references.to_dict(),
        }

    def to_json(self) -> str:
        """Deterministic JSON representation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass(frozen=True, slots=True)
class PortfolioAnalyticsHistory:
    """Append-only record of performance snapshots."""

    records: tuple[PerformanceSnapshot, ...] = ()

    def record(self, snapshot: PerformanceSnapshot) -> PortfolioAnalyticsHistory:
        """Return a new history with snapshot appended."""
        return PortfolioAnalyticsHistory(records=self.records + (snapshot,))

    def to_dict(self) -> dict[str, object]:
        return {"records": [s.to_dict() for s in self.records]}
