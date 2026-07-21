"""Explainability stage implementation (P7.3).

Independent producer stage. Consumes execution artifacts from PipelineContext,
runs ExplainabilityEngine to produce domain explanations, aggregates them into
an ExplanationSnapshot, and publishes it under IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.

Declares no intelligence-stage dependencies. explain_reporting() is deliberately
omitted to preserve stage independence — all other explain_* methods consume only
execution artifacts.
"""

from __future__ import annotations

from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.brokers.models import BrokerExecutionPlan
from athena.execution.models import ExecutionState
from athena.explainability.engine import ExplainabilityEngine
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import (
    ExecutionArtifactKey,
    IntelligenceArtifactKey,
    IntelligenceStageId,
)
from athena.orders.models import ExecutionPlan
from athena.portfolio.models import PortfolioSnapshot
from athena.sizing.models import PositionSizingPlan


class ExplainabilityStage:
    """Independent producer stage that generates a multi-domain ExplanationSnapshot."""

    def __init__(self, explainability_engine: ExplainabilityEngine) -> None:
        self._explainability_engine = explainability_engine

    @property
    def stage_id(self) -> str:
        return IntelligenceStageId.EXPLAINABILITY.value

    @property
    def name(self) -> str:
        return "Explainability"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        alloc_plan = context.get(ExecutionArtifactKey.ALLOCATION_PLAN.value)
        sizing_plan = context.get(ExecutionArtifactKey.SIZING_PLAN.value)
        exec_plan = context.get(ExecutionArtifactKey.EXECUTION_PLAN.value)
        broker_plan = context.get(ExecutionArtifactKey.BROKER_PLAN.value)
        exec_state = context.get(ExecutionArtifactKey.EXECUTION_STATE.value)
        perf_snap = context.get(ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value)

        try:
            explanations = []

            if isinstance(p_snap, PortfolioSnapshot):
                explanations.append(
                    self._explainability_engine.explain_portfolio(
                        p_snap, as_of=context.as_of
                    )
                )

            if isinstance(alloc_plan, AllocationPlan):
                explanations.append(
                    self._explainability_engine.explain_allocation(
                        alloc_plan, as_of=context.as_of
                    )
                )

            if isinstance(sizing_plan, PositionSizingPlan):
                explanations.append(
                    self._explainability_engine.explain_sizing(
                        sizing_plan, as_of=context.as_of
                    )
                )

            if isinstance(exec_plan, ExecutionPlan):
                explanations.append(
                    self._explainability_engine.explain_order_planning(
                        exec_plan, as_of=context.as_of
                    )
                )

            if isinstance(broker_plan, BrokerExecutionPlan):
                explanations.append(
                    self._explainability_engine.explain_broker_translation(
                        broker_plan, as_of=context.as_of
                    )
                )

            if isinstance(exec_state, ExecutionState):
                explanations.append(
                    self._explainability_engine.explain_lifecycle(
                        exec_state, as_of=context.as_of
                    )
                )

            if isinstance(perf_snap, PerformanceSnapshot):
                explanations.append(
                    self._explainability_engine.explain_analytics(
                        perf_snap, as_of=context.as_of
                    )
                )

            exp_snap = self._explainability_engine.create_snapshot(
                explanations, as_of=context.as_of
            )
            updated_context = context.with_value(
                IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value, exp_snap
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Created ExplanationSnapshot {exp_snap.snapshot_id} "
                    f"with {len(explanations)} explanation(s)"
                ),
                output_key=IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Explainability stage failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
