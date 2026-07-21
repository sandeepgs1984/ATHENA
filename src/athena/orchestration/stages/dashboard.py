"""Dashboard stage implementation (P7.3).

Independent producer stage. Consumes execution artifacts from PipelineContext,
runs DashboardEngine to produce a DashboardSnapshot, and publishes it under
IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.

Declares no intelligence-stage dependencies. The DashboardEngine reports
parameter is optional (None-safe); DashboardStage passes None rather than
blocking on ReportingStage.
"""

from __future__ import annotations

from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.dashboard.engine import DashboardEngine
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


class DashboardStage:
    """Independent producer stage that creates a comprehensive DashboardSnapshot."""

    def __init__(self, dashboard_engine: DashboardEngine) -> None:
        self._dashboard_engine = dashboard_engine

    @property
    def stage_id(self) -> str:
        return IntelligenceStageId.DASHBOARD.value

    @property
    def name(self) -> str:
        return "Dashboard"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        alloc_plan = context.get(ExecutionArtifactKey.ALLOCATION_PLAN.value)
        exec_state = context.get(ExecutionArtifactKey.EXECUTION_STATE.value)
        perf_snap = context.get(ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value)

        try:
            dash_snap = self._dashboard_engine.create_snapshot(
                portfolio_snapshot=p_snap if isinstance(p_snap, PortfolioSnapshot) else None,
                allocation_plan=alloc_plan if isinstance(alloc_plan, AllocationPlan) else None,
                execution_state=exec_state if isinstance(exec_state, ExecutionState) else None,
                performance_snapshot=(
                    perf_snap if isinstance(perf_snap, PerformanceSnapshot) else None
                ),
                reports=None,  # independent: reports not required by contract
                as_of=context.as_of,
            )
            updated_context = context.with_value(
                IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value, dash_snap
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Created DashboardSnapshot {dash_snap.snapshot_id} "
                    f"with {len(dash_snap.sections)} section(s)"
                ),
                output_key=IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Dashboard stage failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
