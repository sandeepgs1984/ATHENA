"""Monitoring stage implementation (P7.3).

Independent producer stage. Consumes execution artifacts from PipelineContext,
runs OperationalMonitoringEngine to produce a MonitoringSnapshot, and publishes
it under IntelligenceArtifactKey.MONITORING_SNAPSHOT.

Declares no intelligence-stage dependencies. All of OperationalMonitoringEngine's
intelligence artifact parameters (dashboard_snapshot, explanation_snapshot,
timeline_snapshot) are Optional — this stage passes None for them, preserving
independence and maximum parallelism.
"""

from __future__ import annotations

from athena.analytics.portfolio.models import PerformanceSnapshot
from athena.execution.models import ExecutionState
from athena.monitoring.engine import OperationalMonitoringEngine
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


class MonitoringStage:
    """Independent producer stage that evaluates platform operational health."""

    def __init__(self, monitoring_engine: OperationalMonitoringEngine) -> None:
        self._monitoring_engine = monitoring_engine

    @property
    def stage_id(self) -> str:
        return IntelligenceStageId.MONITORING.value

    @property
    def name(self) -> str:
        return "Monitoring"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        p_snap = context.get(ExecutionArtifactKey.PORTFOLIO_SNAPSHOT.value)
        exec_state = context.get(ExecutionArtifactKey.EXECUTION_STATE.value)
        perf_snap = context.get(ExecutionArtifactKey.PERFORMANCE_SNAPSHOT.value)

        try:
            mon_snap = self._monitoring_engine.evaluate_health(
                portfolio_snapshot=(
                    p_snap if isinstance(p_snap, PortfolioSnapshot) else None
                ),
                execution_state=(
                    exec_state if isinstance(exec_state, ExecutionState) else None
                ),
                performance_snapshot=(
                    perf_snap if isinstance(perf_snap, PerformanceSnapshot) else None
                ),
                # Intelligence-stage outputs not required by contract — stay independent
                reports=None,
                dashboard_snapshot=None,
                explanation_snapshot=None,
                timeline_snapshot=None,
                as_of=context.as_of,
            )
            updated_context = context.with_value(
                IntelligenceArtifactKey.MONITORING_SNAPSHOT.value, mon_snap
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Evaluated MonitoringSnapshot {mon_snap.snapshot_id} "
                    f"— status {mon_snap.summary.overall_status}"
                ),
                output_key=IntelligenceArtifactKey.MONITORING_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Monitoring stage failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
