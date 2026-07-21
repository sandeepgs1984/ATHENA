"""Reporting stage implementation (P7.3).

Independent producer stage. Consumes execution artifacts from PipelineContext,
runs ReportingEngine to produce GenericReport instances, and publishes a list of
reports under IntelligenceArtifactKey.REPORTS.

Declares no intelligence-stage dependencies. All inputs are execution pipeline
artifacts (PORTFOLIO_SNAPSHOT, EXECUTION_STATE, ALLOCATION_PLAN, PERFORMANCE_SNAPSHOT).
"""

from __future__ import annotations

from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.execution.models import ExecutionState
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
from athena.portfolio.models import PortfolioSnapshot
from athena.reporting.engine import ReportingEngine


class ReportingStage:
    """Independent producer stage that generates GenericReport artifacts."""

    def __init__(self, reporting_engine: ReportingEngine) -> None:
        self._reporting_engine = reporting_engine

    @property
    def stage_id(self) -> str:
        return IntelligenceStageId.REPORTING.value

    @property
    def name(self) -> str:
        return "Reporting"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        exec_state = context.get(ExecutionArtifactKey.EXECUTION_STATE.value)
        alloc_plan = context.get(ExecutionArtifactKey.ALLOCATION_PLAN.value)
        perf_snap = context.get(ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value)

        try:
            reports = []

            if isinstance(p_snap, PortfolioSnapshot):
                reports.append(
                    self._reporting_engine.generate_portfolio_report(
                        p_snap, as_of=context.as_of
                    )
                )

            if isinstance(exec_state, ExecutionState):
                reports.append(
                    self._reporting_engine.generate_execution_report(
                        exec_state, as_of=context.as_of
                    )
                )

            if isinstance(alloc_plan, AllocationPlan):
                reports.append(
                    self._reporting_engine.generate_allocation_report(
                        alloc_plan, as_of=context.as_of
                    )
                )

            if isinstance(perf_snap, PerformanceSnapshot):
                reports.append(
                    self._reporting_engine.generate_analytics_report(
                        perf_snap, as_of=context.as_of
                    )
                )

            updated_context = context.with_value(
                IntelligenceArtifactKey.REPORTS.value, reports
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=f"Generated {len(reports)} report(s)",
                output_key=IntelligenceArtifactKey.REPORTS.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Reporting stage failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
