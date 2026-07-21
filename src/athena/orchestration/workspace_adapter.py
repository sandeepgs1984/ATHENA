"""Workspace Assembler adapter implementation (P7.4).

Isolates workspace post-processing by extracting produced intelligence artifacts
from PipelineContext and delegating assembly to UnifiedIntelligenceWorkspace.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.dashboard.models import DashboardSnapshot
from athena.explainability.models import ExplanationSnapshot
from athena.export.models import ExportSnapshot
from athena.monitoring.models import MonitoringSnapshot
from athena.orchestration.models import PipelineContext
from athena.orchestration.pipelines.keys import IntelligenceArtifactKey
from athena.timeline.models import TimelineSnapshot
from athena.workspace.engine import UnifiedIntelligenceWorkspace
from athena.workspace.models import WorkspaceSnapshot


class WorkspaceAssembler:
    """Post-processing adapter that constructs a WorkspaceSnapshot from a PipelineContext."""

    def __init__(self, workspace_engine: UnifiedIntelligenceWorkspace | None = None) -> None:
        self._workspace_engine = workspace_engine or UnifiedIntelligenceWorkspace()

    def assemble(self, context: PipelineContext) -> WorkspaceSnapshot:
        """Extract intelligence artifacts from context and assemble a WorkspaceSnapshot."""
        reports = context.get(IntelligenceArtifactKey.REPORTS.value)
        dash_snap = context.get(IntelligenceArtifactKey.DASHBOARD_SNAPSHOT.value)
        exp_snap = context.get(IntelligenceArtifactKey.EXPLANATION_SNAPSHOT.value)
        tl_snap = context.get(IntelligenceArtifactKey.TIMELINE_SNAPSHOT.value)
        mon_snap = context.get(IntelligenceArtifactKey.MONITORING_SNAPSHOT.value)
        export_snap = context.get(IntelligenceArtifactKey.EXPORT_SNAPSHOT.value)

        return self._workspace_engine.assemble_workspace(
            reports=reports if isinstance(reports, Sequence) else None,
            dashboard_snapshot=(
                dash_snap if isinstance(dash_snap, DashboardSnapshot) else None
            ),
            explanation_snapshot=(
                exp_snap if isinstance(exp_snap, ExplanationSnapshot) else None
            ),
            timeline_snapshot=(
                tl_snap if isinstance(tl_snap, TimelineSnapshot) else None
            ),
            monitoring_snapshot=(
                mon_snap if isinstance(mon_snap, MonitoringSnapshot) else None
            ),
            export_snapshot=(
                export_snap if isinstance(export_snap, ExportSnapshot) else None
            ),
            as_of=context.as_of,
        )
