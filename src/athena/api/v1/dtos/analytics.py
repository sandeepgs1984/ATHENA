"""Portfolio performance analytics DTO schemas (P8.4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from athena.api.v1.dtos.base import FilterParams, ResourceReference


class AnalyticsProvenanceDTO(BaseModel):
    """Exposes references to the source data used to calculate metrics."""

    model_config = ConfigDict(frozen=True)

    decision_ref: ResourceReference | None = None
    portfolio_ref: ResourceReference | None = None
    execution_run_ref: ResourceReference | None = None
    scheduler_run_ref: ResourceReference | None = None


class TradePerformanceDTO(BaseModel):
    """Performance metrics for a closed position."""

    model_config = ConfigDict(frozen=True)

    trade_id: str
    instrument_id: str
    direction: str
    entry_price: str
    exit_price: str
    quantity: str
    realized_pnl: str
    return_pct: str
    holding_period_days: float
    is_win: bool
    is_loss: bool
    as_of: datetime
    provenance: AnalyticsProvenanceDTO


class PortfolioPerformanceDTO(BaseModel):
    """Aggregated portfolio valuation and drawdown metrics."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime
    realized_pnl: str
    unrealized_pnl: str
    total_pnl: str
    total_return_pct: str
    portfolio_value: str
    peak_portfolio_value: str
    drawdown: str
    drawdown_pct: str
    max_drawdown_pct: str
    gross_exposure: str
    net_exposure: str
    cash_utilization_pct: str


class AnalyticsSummaryDTO(BaseModel):
    """Summary statistics across all trades in the analytics snapshot."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: str
    avg_gain: str
    avg_loss: str
    win_loss_ratio: str
    avg_holding_period_days: float
    max_drawdown_pct: str


class PerformanceSnapshotDTO(BaseModel):
    """Detailed snapshot of portfolio performance metrics and trade listings."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    as_of: datetime
    portfolio_performance: PortfolioPerformanceDTO
    trade_performances: list[TradePerformanceDTO]
    summary: AnalyticsSummaryDTO
    provenance: AnalyticsProvenanceDTO


class PerformanceSnapshotSummaryDTO(BaseModel):
    """Lightweight summary of portfolio performance metrics (omits trade array)."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    as_of: datetime
    portfolio_performance: PortfolioPerformanceDTO
    summary: AnalyticsSummaryDTO
    provenance: AnalyticsProvenanceDTO


class EmptyFilterParams(FilterParams):
    """Filter schema for collection routes with no query filters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
