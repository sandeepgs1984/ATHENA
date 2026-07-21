"""Portfolio Analytics stage implementation (P7.2).

Consumes PortfolioSnapshot, ExecutionState, and current prices from PipelineContext,
runs PortfolioAnalyticsEngine, and publishes PerformanceSnapshot under ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.
"""

from __future__ import annotations

from collections.abc import Mapping

from athena.analytics.portfolio import PortfolioAnalyticsEngine
from athena.execution.models import ExecutionState
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId
from athena.portfolio.models import PortfolioSnapshot


class PortfolioAnalyticsStage:
    """Stage that computes portfolio valuation and performance statistics."""

    def __init__(self, analytics_engine: PortfolioAnalyticsEngine) -> None:
        self._analytics_engine = analytics_engine

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.PORTFOLIO_ANALYTICS.value

    @property
    def name(self) -> str:
        return "Portfolio Analytics"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        exec_state = context.get(ExecutionArtifactKey.EXECUTION_STATE.value)
        prices = context.get(ExecutionArtifactKey.CURRENT_PRICES.value)

        if not isinstance(p_snap, PortfolioSnapshot):
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=(
                    f"Missing or invalid PortfolioSnapshot under key "
                    f"'{ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value}'"
                ),
            )
            return StageExecutionResult(stage_result=result, context=context)

        exec_st = exec_state if isinstance(exec_state, ExecutionState) else None
        mkt_prices = prices if isinstance(prices, Mapping) else None

        try:
            perf_snap = self._analytics_engine.analyze(
                p_snap,
                execution_state=exec_st,
                current_prices=mkt_prices,
                as_of=context.as_of,
            )
            updated_context = context.with_value(
                ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value, perf_snap
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Analyzed PerformanceSnapshot {perf_snap.snapshot_id} "
                    f"with PnL {perf_snap.portfolio_performance.total_pnl}"
                ),
                output_key=ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Portfolio analytics failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
