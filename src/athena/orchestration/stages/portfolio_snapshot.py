"""Portfolio Snapshot stage implementation (P7.2).

Retrieves the current PortfolioSnapshot from PortfolioEngine and publishes it
to the PipelineContext under ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.
"""

from __future__ import annotations

from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId
from athena.portfolio.engine import PortfolioEngine


class PortfolioSnapshotStage:
    """Stage that captures the current portfolio state."""

    def __init__(self, portfolio_engine: PortfolioEngine) -> None:
        self._portfolio_engine = portfolio_engine

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.PORTFOLIO_SNAPSHOT.value

    @property
    def name(self) -> str:
        return "Portfolio Snapshot"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        try:
            snapshot = self._portfolio_engine.current_snapshot
            updated_context = context.with_value(
                ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value, snapshot
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=f"Captured portfolio snapshot {snapshot.snapshot_id}",
                output_key=ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Failed to capture portfolio snapshot: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
