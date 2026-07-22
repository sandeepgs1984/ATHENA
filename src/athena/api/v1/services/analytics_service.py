"""Portfolio analytics operational query service (P8.4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import PerformanceSnapshotNotFoundError
from athena.api.v1.dtos import (
    AnalyticsProvenanceDTO,
    AnalyticsSummaryDTO,
    CollectionResult,
    PerformanceSnapshotDTO,
    PerformanceSnapshotSummaryDTO,
    PortfolioPerformanceDTO,
    QuerySpecification,
    ResourceReference,
    TradePerformanceDTO,
)

if TYPE_CHECKING:
    from athena.analytics.portfolio.models import (
        AnalyticsSummary,
        PerformanceSnapshot,
        PortfolioAnalyticsReferences,
        PortfolioPerformance,
        TradePerformance,
    )
    from athena.api.v1.dtos import EmptyFilterParams, PaginationParams, SortParams
    from athena.api.v1.providers import PerformanceAnalyticsProvider


class AnalyticsService:
    """Orchestrates portfolio analytics queries and DTO mapping."""

    def __init__(self, provider: PerformanceAnalyticsProvider) -> None:
        self._provider = provider

    def list_snapshots(
        self,
        filters: EmptyFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[PerformanceSnapshotSummaryDTO]:
        """Lists portfolio performance snapshots using query specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_snapshots(spec)

        dto_items = tuple(self._map_to_summary_dto(s) for s in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_snapshot(self, snapshot_id: str) -> PerformanceSnapshotDTO:
        """Retrieves complete performance snapshot details or raises PerformanceSnapshotNotFoundError."""
        s = self._provider.get_snapshot(snapshot_id)
        if not s:
            raise PerformanceSnapshotNotFoundError(f"Performance snapshot '{snapshot_id}' not found")
        return self._map_to_detail_dto(s)

    def _map_to_summary_dto(self, s: PerformanceSnapshot) -> PerformanceSnapshotSummaryDTO:
        return PerformanceSnapshotSummaryDTO(
            snapshot_id=s.snapshot_id,
            as_of=s.as_of,
            portfolio_performance=self._map_portfolio_perf_dto(s.portfolio_performance),
            summary=self._map_summary_dto(s.summary),
            provenance=self._map_provenance_dto(s.references),
        )

    def _map_to_detail_dto(self, s: PerformanceSnapshot) -> PerformanceSnapshotDTO:
        trades_dtos = [self._map_trade_perf_dto(t) for t in s.trade_performances] if s.trade_performances else []

        return PerformanceSnapshotDTO(
            snapshot_id=s.snapshot_id,
            as_of=s.as_of,
            portfolio_performance=self._map_portfolio_perf_dto(s.portfolio_performance),
            trade_performances=trades_dtos,
            summary=self._map_summary_dto(s.summary),
            provenance=self._map_provenance_dto(s.references),
        )

    def _map_portfolio_perf_dto(self, p: PortfolioPerformance) -> PortfolioPerformanceDTO:
        return PortfolioPerformanceDTO(
            as_of=p.as_of,
            realized_pnl=str(p.realized_pnl),
            unrealized_pnl=str(p.unrealized_pnl),
            total_pnl=str(p.total_pnl),
            total_return_pct=str(p.total_return_pct),
            portfolio_value=str(p.portfolio_value),
            peak_portfolio_value=str(p.peak_portfolio_value),
            drawdown=str(p.drawdown),
            drawdown_pct=str(p.drawdown_pct),
            max_drawdown_pct=str(p.max_drawdown_pct),
            gross_exposure=str(p.gross_exposure),
            net_exposure=str(p.net_exposure),
            cash_utilization_pct=str(p.cash_utilization_pct),
        )

    def _map_summary_dto(self, sum_val: AnalyticsSummary) -> AnalyticsSummaryDTO:
        return AnalyticsSummaryDTO(
            as_of=sum_val.as_of,
            total_trades=sum_val.total_trades,
            winning_trades=sum_val.winning_trades,
            losing_trades=sum_val.losing_trades,
            win_rate_pct=str(sum_val.win_rate_pct),
            avg_gain=str(sum_val.avg_gain),
            avg_loss=str(sum_val.avg_loss),
            win_loss_ratio=str(sum_val.win_loss_ratio),
            avg_holding_period_days=sum_val.avg_holding_period_days,
            max_drawdown_pct=str(sum_val.max_drawdown_pct),
        )

    def _map_trade_perf_dto(self, t: TradePerformance) -> TradePerformanceDTO:
        return TradePerformanceDTO(
            trade_id=t.trade_id,
            instrument_id=t.instrument_id,
            direction=t.direction.value,
            entry_price=str(t.entry_price),
            exit_price=str(t.exit_price),
            quantity=str(t.quantity),
            realized_pnl=str(t.realized_pnl),
            return_pct=str(t.return_pct),
            holding_period_days=t.holding_period_days,
            is_win=t.is_win,
            is_loss=t.is_loss,
            as_of=t.as_of,
            provenance=self._map_provenance_dto(t.references),
        )

    def _map_provenance_dto(self, ref: PortfolioAnalyticsReferences | None) -> AnalyticsProvenanceDTO:
        if not ref:
            return AnalyticsProvenanceDTO()

        return AnalyticsProvenanceDTO(
            decision_ref=(
                ResourceReference(id=ref.decision_id, resource_type="decision")
                if ref.decision_id
                else None
            ),
            portfolio_ref=(
                ResourceReference(id=ref.portfolio_snapshot_id, resource_type="portfolio_snapshot")
                if ref.portfolio_snapshot_id
                else None
            ),
            execution_run_ref=(
                ResourceReference(id=ref.execution_state_id, resource_type="execution_state")
                if ref.execution_state_id
                else None
            ),
            # Strategy matches the workflow scheduler trigger name in scheduler history
            scheduler_run_ref=(
                ResourceReference(id=ref.strategy, resource_type="strategy")
                if ref.strategy
                else None
            ),
        )
