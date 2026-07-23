"""Backtests business service (P9.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from athena.api.exceptions import BacktestRunNotFoundError
from athena.api.v1.dtos import (
    BacktestRunDTO,
    BacktestRunSummaryDTO,
    BacktestStepDTO,
    BacktestSummaryDTO,
    CollectionResult,
    QuerySpecification,
    StrategyPerformanceDTO,
)

if TYPE_CHECKING:
    from athena.api.v1.dtos import EmptyFilterParams, PaginationParams, SortParams
    from athena.api.v1.providers.base import BacktestRunProvider
    from athena.backtest.models import BacktestRun


class BacktestsService:
    """Orchestrates backtesting history queries and DTO mapping."""

    def __init__(self, provider: BacktestRunProvider) -> None:
        self._provider = provider

    def list_runs(
        self,
        filters: EmptyFilterParams,
        sort: SortParams,
        pagination: PaginationParams,
    ) -> CollectionResult[BacktestRunSummaryDTO]:
        """Lists backtest runs using query specifications."""
        spec = QuerySpecification(filters=filters, sort=sort, pagination=pagination)
        result = self._provider.get_runs(spec)

        dto_items = tuple(self._map_to_summary_dto(r) for r in result.items)
        return CollectionResult(
            items=dto_items,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    def get_run(self, run_id: str) -> BacktestRunDTO:
        """Retrieves a single backtest run detail or raises BacktestRunNotFoundError."""
        r = self._provider.get_run(run_id)
        if not r:
            raise BacktestRunNotFoundError(f"Backtest run '{run_id}' not found")
        return self._map_to_detail_dto(r)

    def _map_to_summary_dto(self, r: BacktestRun) -> BacktestRunSummaryDTO:
        return BacktestRunSummaryDTO(
            run_id=r.run_id,
            first_replay_date=r.first_replay_date,
            last_replay_date=r.last_replay_date,
            meta=dict(r.meta) if r.meta else {},
            total_steps=r.summary.total_steps,
            completed_steps=r.summary.completed_steps,
            failed_steps=r.summary.failed_steps,
        )

    def _map_to_detail_dto(self, r: BacktestRun) -> BacktestRunDTO:
        perf_dtos = [
            StrategyPerformanceDTO(
                strategy=p.strategy,
                total_matches=p.total_matches,
                steps_with_matches=p.steps_with_matches,
                distinct_instruments=p.distinct_instruments,
                instruments=list(p.instruments),
            )
            for p in r.summary.performance
        ]

        summary_dto = BacktestSummaryDTO(
            total_steps=r.summary.total_steps,
            completed_steps=r.summary.completed_steps,
            failed_steps=r.summary.failed_steps,
            performance=perf_dtos,
        )

        step_dtos = [
            BacktestStepDTO(
                replay_date=s.replay_date,
                as_of=s.as_of,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                scan_id=s.scan_id,
                watchlist_snapshot_id=s.watchlist_snapshot_id,
                strategy_execution_id=s.strategy_execution_id,
                note=s.note,
            )
            for s in r.steps
        ]

        return BacktestRunDTO(
            run_id=r.run_id,
            first_replay_date=r.first_replay_date,
            last_replay_date=r.last_replay_date,
            meta=dict(r.meta) if r.meta else {},
            summary=summary_dto,
            steps=step_dtos,
        )
