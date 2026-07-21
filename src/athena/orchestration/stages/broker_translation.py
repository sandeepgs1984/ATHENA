"""Broker Translation stage implementation (P7.2).

Consumes ExecutionPlan from PipelineContext, runs BrokerManager,
and publishes BrokerExecutionPlan under ExecutionArtifactKey.BROKER_PLAN.
"""

from __future__ import annotations

from athena.brokers import BrokerManager
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import ExecutionArtifactKey, ExecutionStageId
from athena.orders.models import ExecutionPlan


class BrokerTranslationStage:
    """Stage that translates canonical execution plans into broker-specific execution plans."""

    def __init__(self, broker_manager: BrokerManager) -> None:
        self._broker_manager = broker_manager

    @property
    def stage_id(self) -> str:
        return ExecutionStageId.BROKER_TRANSLATION.value

    @property
    def name(self) -> str:
        return "Broker Translation"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        exec_plan = context.get(ExecutionArtifactKey.EXECUTION_PLAN.value)

        if not isinstance(exec_plan, ExecutionPlan):
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Missing or invalid ExecutionPlan under key '{ExecutionArtifactKey.EXECUTION_PLAN.value}'",
            )
            return StageExecutionResult(stage_result=result, context=context)

        try:
            b_plan = self._broker_manager.translate_plan(
                exec_plan, as_of=context.as_of
            )
            updated_context = context.with_value(
                ExecutionArtifactKey.BROKER_PLAN.value, b_plan
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=f"Translated BrokerExecutionPlan {b_plan.broker_plan_id} for broker {b_plan.broker_id}",
                output_key=ExecutionArtifactKey.BROKER_PLAN.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Broker translation failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
