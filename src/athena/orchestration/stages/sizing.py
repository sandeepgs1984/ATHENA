"""Position Sizing stage implementation (P7.2).

Consumes AllocationPlan and current market prices from PipelineContext, runs
PositionSizingEngine, and publishes PositionSizingPlan under ExecutionArtifactKey.SIZING_PLAN.
"""

from __future__ import annotations

from collections.abc import Mapping

from athena.allocation.models import AllocationPlan
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId
from athena.sizing import PositionSizingEngine


class PositionSizingStage:
    """Stage that converts capital allocations into unit position sizes."""

    def __init__(self, sizing_engine: PositionSizingEngine) -> None:
        self._sizing_engine = sizing_engine

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.POSITION_SIZING.value

    @property
    def name(self) -> str:
        return "Position Sizing"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        alloc_plan = context.get(ExecutionArtifactKey.ALLOCATION_PLAN.value)
        prices = context.get(ExecutionArtifactKey.CURRENT_PRICES.value)

        if not isinstance(alloc_plan, AllocationPlan):
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Missing or invalid AllocationPlan under key '{ExecutionArtifactKey.ALLOCATION_PLAN.value}'",
            )
            return StageExecutionResult(stage_result=result, context=context)

        if not isinstance(prices, Mapping):
            prices = {}

        try:
            sz_plan = self._sizing_engine.size_plan(
                alloc_plan, prices, as_of=context.as_of
            )
            updated_context = context.with_value(
                ExecutionArtifactKey.SIZING_PLAN.value, sz_plan
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=f"Created PositionSizingPlan {sz_plan.plan_id} for {len(sz_plan.sizes)} size(s)",
                output_key=ExecutionArtifactKey.SIZING_PLAN.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Position sizing failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
