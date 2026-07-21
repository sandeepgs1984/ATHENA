"""Order Lifecycle stage implementation (P7.2).

Consumes BrokerExecutionPlan from PipelineContext, runs OrderLifecycleEngine,
and publishes ExecutionState under ExecutionArtifactKey.EXECUTION_STATE.
"""

from __future__ import annotations

from athena.brokers.models import BrokerExecutionPlan
from athena.execution import OrderLifecycleEngine
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId


class OrderLifecycleStage:
    """Stage that initializes order tracking and lifecycle state from broker plans."""

    def __init__(self, lifecycle_engine: OrderLifecycleEngine) -> None:
        self._lifecycle_engine = lifecycle_engine

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.ORDER_LIFECYCLE.value

    @property
    def name(self) -> str:
        return "Order Lifecycle"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        b_plan = context.get(ExecutionArtifactKey.BROKER_PLAN.value)

        if not isinstance(b_plan, BrokerExecutionPlan):
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Missing or invalid BrokerExecutionPlan under key '{ExecutionArtifactKey.BROKER_PLAN.value}'",
            )
            return StageExecutionResult(stage_result=result, context=context)

        try:
            exec_state = self._lifecycle_engine.initialize_from_plan(
                b_plan, as_of=context.as_of
            )
            updated_context = context.with_value(
                ExecutionArtifactKey.EXECUTION_STATE.value, exec_state
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Initialized ExecutionState {exec_state.state_id} "
                    f"with {exec_state.summary.total_orders} order(s)"
                ),
                output_key=ExecutionArtifactKey.EXECUTION_STATE.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Order lifecycle initialization failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
