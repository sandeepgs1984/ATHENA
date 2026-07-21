"""Capital Allocation stage implementation (P7.2).

Consumes PortfolioSnapshot and candidate Decisions from PipelineContext, runs
CapitalAllocationEngine, and publishes AllocationPlan under ExecutionArtifactKey.ALLOCATION_PLAN.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.allocation import CapitalAllocationEngine
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId
from athena.portfolio.models import PortfolioSnapshot


class CapitalAllocationStage:
    """Stage that computes capital allocations across trade decisions."""

    def __init__(self, allocation_engine: CapitalAllocationEngine) -> None:
        self._allocation_engine = allocation_engine

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.CAPITAL_ALLOCATION.value

    @property
    def name(self) -> str:
        return "Capital Allocation"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        decisions = context.get(ExecutionArtifactKey.DECISIONS.value)

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

        if not isinstance(decisions, Sequence):
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Missing or invalid Decisions sequence under key '{ExecutionArtifactKey.DECISIONS.value}'",
            )
            return StageExecutionResult(stage_result=result, context=context)

        try:
            alloc_plan = self._allocation_engine.allocate(
                p_snap, decisions, as_of=context.as_of
            )
            updated_context = context.with_value(
                ExecutionArtifactKey.ALLOCATION_PLAN.value, alloc_plan
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Created AllocationPlan {alloc_plan.plan_id} with "
                    f"{alloc_plan.summary.allocated_count} allocation(s)"
                ),
                output_key=ExecutionArtifactKey.ALLOCATION_PLAN.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Capital allocation failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
