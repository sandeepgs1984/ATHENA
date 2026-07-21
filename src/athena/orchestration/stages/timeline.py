"""Timeline stage implementation (P7.3).

Intermediate aggregator stage. Depends on all four intelligence producer stages
(Reporting, Explainability, Dashboard, Monitoring). Consumes their outputs together
with execution artifacts, runs TimelineAuditEngine to produce a complete chronological
TimelineSnapshot, and publishes it under IntelligenceArtifactKey.TIMELINE_SNAPSHOT.

Dependencies are justified by contract completeness: TimelineAuditEngine accepts
reports, dashboard_snapshot, and explanation_snapshot as Optional parameters, but
passing them is the only way to produce a complete, audit-ready timeline that includes
intelligence events alongside execution events.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.allocation.models import AllocationPlan
from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.brokers.models import BrokerExecutionPlan
from athena.dashboard.models import DashboardSnapshot
from athena.execution.models import ExecutionState
from athena.explainability.models import ExplanationSnapshot
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
from athena.timeline.engine import TimelineAuditEngine


class TimelineStage:
    """Intermediate aggregator stage that builds a complete chronological TimelineSnapshot."""

    def __init__(self, timeline_engine: TimelineAuditEngine) -> None:
        self._timeline_engine = timeline_engine

    @property
    def stage_id(self) -> str:
        return IntelligenceStageId.TIMELINE.value

    @property
    def name(self) -> str:
        return "Timeline"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        # Execution artifacts
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        alloc_plan = context.get(ExecutionArtifactKey.ALLOCATION_PLAN.value)
        sizing_plan = context.get(ExecutionArtifactKey.SIZING_PLAN.value)
        exec_plan = context.get(ExecutionArtifactKey.EXECUTION_PLAN.value)
        broker_plan = context.get(ExecutionArtifactKey.BROKER_PLAN.value)
        exec_state = context.get(ExecutionArtifactKey.EXECUTION_STATE.value)
        perf_snap = context.get(ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value)

        # Intelligence producer outputs (aggregated from four upstream stages)
        reports = context.get(IntelligenceArtifactKey.REPORTS.value)
        dash_snap = context.get(IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value)
        exp_snap = context.get(IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value)

        try:
            timeline_snap = self._timeline_engine.build_timeline(
                portfolio_snapshot=(
                    p_snap if isinstance(p_snap, PortfolioSnapshot) else None
                ),
                allocation_plan=(
                    alloc_plan if isinstance(alloc_plan, AllocationPlan) else None
                ),
                sizing_plan=(
                    sizing_plan if isinstance(sizing_plan, PositionSizingPlan) else None
                ),
                execution_plan=(
                    exec_plan if isinstance(exec_plan, ExecutionPlan) else None
                ),
                broker_plan=(
                    broker_plan if isinstance(broker_plan, BrokerExecutionPlan) else None
                ),
                execution_state=(
                    exec_state if isinstance(exec_state, ExecutionState) else None
                ),
                performance_snapshot=(
                    perf_snap if isinstance(perf_snap, PerformanceSnapshot) else None
                ),
                reports=reports if isinstance(reports, Sequence) else None,
                dashboard_snapshot=(
                    dash_snap if isinstance(dash_snap, DashboardSnapshot) else None
                ),
                explanation_snapshot=(
                    exp_snap if isinstance(exp_snap, ExplanationSnapshot) else None
                ),
                as_of=context.as_of,
            )
            updated_context = context.with_value(
                IntelligenceArtifactKey.TIMELINE_SNAPSHOT.value, timeline_snap
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Built TimelineSnapshot {timeline_snap.snapshot_id} "
                    f"with {len(timeline_snap.entries)} audit entries"
                ),
                output_key=IntelligenceArtifactKey.TIMELINE_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Timeline stage failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
