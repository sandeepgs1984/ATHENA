"""Order Planning stage implementation (P7.2).

Consumes PositionSizingPlan and Decisions from PipelineContext, runs OrderPlanningEngine,
and publishes ExecutionPlan under ExecutionArtifactKey.EXECUTION_PLAN.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId
from athena.orders import OrderPlanningEngine
from athena.sizing.models import PositionSizingPlan


class OrderPlanningStage:
    """Stage that generates broker-neutral order execution plans."""

    def __init__(self, order_planning_engine: OrderPlanningEngine) -> None:
        self._order_planning_engine = order_planning_engine

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.ORDER_PLANNING.value

    @property
    def name(self) -> str:
        return "Order Planning"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        sz_plan = context.get(ExecutionArtifactKey.SIZING_PLAN.value)
        decisions = context.get(ExecutionArtifactKey.DECISIONS.value)

        if not isinstance(sz_plan, PositionSizingPlan):
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Missing or invalid PositionSizingPlan under key '{ExecutionArtifactKey.SIZING_PLAN.value}'",
            )
            return StageExecutionResult(stage_result=result, context=context)

        dec_seq = decisions if isinstance(decisions, Sequence) else None

        try:
            exec_plan = self._order_planning_engine.plan_execution(
                sz_plan, as_of=context.as_of, decisions=dec_seq
            )
            updated_context = context.with_value(
                ExecutionArtifactKey.EXECUTION_PLAN.value, exec_plan
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Created ExecutionPlan {exec_plan.plan_id} "
                    f"with {exec_plan.summary.total_candidates} candidate order(s)"
                ),
                output_key=ExecutionArtifactKey.EXECUTION_PLAN.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Order planning failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
