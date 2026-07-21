"""Export stage implementation (P7.3).

Terminal aggregator stage. Depends on all five upstream intelligence stages
(Reporting, Explainability, Dashboard, Monitoring, Timeline). Consumes their
outputs, runs ExportPresentationEngine to produce typed export artifacts for each
available intelligence artifact, aggregates them into an ExportSnapshot, and
publishes it under IntelligenceArtifactKey.EXPORT_SNAPSHOT.

Each dependency on an upstream stage is directly required by the corresponding
ExportPresentationEngine typed export method:
  export_report         → REPORTS (from ReportingStage)
  export_explanation    → EXPLANATION_SNAPSHOT (from ExplainabilityStage)
  export_dashboard      → DASHBOARD_SNAPSHOT (from DashboardStage)
  export_monitoring     → MONITORING_SNAPSHOT (from MonitoringStage)
  export_timeline       → TIMELINE_SNAPSHOT (from TimelineStage)
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.dashboard.models import DashboardSnapshot
from athena.explainability.models import ExplanationSnapshot
from athena.export.engine import ExportPresentationEngine
from athena.monitoring.models import MonitoringSnapshot
from athena.orchestration.models import (
    PipelineContext,
    StageExecutionResult,
    StageResult,
    StageStatus,
)
from athena.orchestration.pipelines.keys import (
    IntelligenceArtifactKey,
    IntelligenceStageId,
)
from athena.reporting.models import GenericReport
from athena.timeline.models import TimelineSnapshot


class ExportStage:
    """Terminal aggregator stage that exports all intelligence artifacts into an ExportSnapshot."""

    def __init__(self, export_engine: ExportPresentationEngine) -> None:
        self._export_engine = export_engine

    @property
    def stage_id(self) -> str:
        return IntelligenceStageId.EXPORT.value

    @property
    def name(self) -> str:
        return "Export"

    def execute(self, context: PipelineContext) -> StageExecutionResult:
        reports = context.get(IntelligenceArtifactKey.REPORTS.value)
        exp_snap = context.get(IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value)
        dash_snap = context.get(IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value)
        mon_snap = context.get(IntelligenceArtifactKey.MONITORING_SNAPSHOT.value)
        tl_snap = context.get(IntelligenceArtifactKey.TIMELINE_SNAPSHOT.value)

        try:
            exports = []

            if isinstance(reports, Sequence):
                for report in reports:
                    if isinstance(report, GenericReport):
                        exports.append(
                            self._export_engine.export_report(
                                report, as_of=context.as_of
                            )
                        )

            if isinstance(exp_snap, ExplanationSnapshot):
                exports.append(
                    self._export_engine.export_explanation(
                        exp_snap, as_of=context.as_of
                    )
                )

            if isinstance(dash_snap, DashboardSnapshot):
                exports.append(
                    self._export_engine.export_dashboard(
                        dash_snap, as_of=context.as_of
                    )
                )

            if isinstance(mon_snap, MonitoringSnapshot):
                exports.append(
                    self._export_engine.export_monitoring(
                        mon_snap, as_of=context.as_of
                    )
                )

            if isinstance(tl_snap, TimelineSnapshot):
                exports.append(
                    self._export_engine.export_timeline(tl_snap, as_of=context.as_of)
                )

            export_snapshot = self._export_engine.create_snapshot(
                exports, as_of=context.as_of
            )
            updated_context = context.with_value(
                IntelligenceArtifactKey.EXPORT_SNAPSHOT.value, export_snapshot
            )
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.SUCCESS,
                message=(
                    f"Created ExportSnapshot {export_snapshot.snapshot_id} "
                    f"with {export_snapshot.summary.total_exports} export(s)"
                ),
                output_key=IntelligenceArtifactKey.EXPORT_SNAPSHOT.value,
            )
            return StageExecutionResult(stage_result=result, context=updated_context)
        except Exception as exc:
            result = StageResult(
                stage_id=self.stage_id,
                status=StageStatus.FAILED,
                message=f"Export stage failed: {exc}",
            )
            return StageExecutionResult(stage_result=result, context=context)
