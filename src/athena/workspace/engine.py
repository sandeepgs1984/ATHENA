"""Unified Intelligence Workspace implementation (P6.7).

Orchestrates a consolidated read-only query surface across all Phase 6 intelligence artifacts.
Performs NO state mutation, NO REST APIs, NO user authentication, and NO market analysis.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime

from athena.config.models import WorkspaceConfig
from athena.dashboard.models import DashboardSnapshot
from athena.errors import WorkspaceError
from athena.explainability.models import ExplanationSnapshot
from athena.export.models import ExportSnapshot
from athena.monitoring.models import MonitoringSnapshot
from athena.reporting.models import GenericReport
from athena.timeline.models import TimelineSnapshot
from athena.workspace.models import (
    WorkspaceEntry,
    WorkspaceHistory,
    WorkspaceReferences,
    WorkspaceSnapshot,
    WorkspaceSummary,
)


class UnifiedIntelligenceWorkspace:
    """Deterministic, read-only Unified Intelligence Workspace."""

    def __init__(self, config: WorkspaceConfig | None = None) -> None:
        self._config = config or WorkspaceConfig()
        self._counter = 0
        self._history = WorkspaceHistory()

    @property
    def history(self) -> WorkspaceHistory:
        """Get accumulated workspace history."""
        return self._history

    def assemble_workspace(
        self,
        reports: Sequence[GenericReport] | None = None,
        dashboard_snapshot: DashboardSnapshot | None = None,
        explanation_snapshot: ExplanationSnapshot | None = None,
        timeline_snapshot: TimelineSnapshot | None = None,
        monitoring_snapshot: MonitoringSnapshot | None = None,
        export_snapshot: ExportSnapshot | None = None,
        *,
        as_of: datetime,
    ) -> WorkspaceSnapshot:
        """Assemble a consolidated WorkspaceSnapshot from Phase 6 intelligence artifacts."""
        if as_of.tzinfo is None:
            raise ValueError("assemble_workspace as_of datetime must be timezone-aware")

        entries: list[WorkspaceEntry] = []

        # 1. Reports View
        if reports:
            for r in reports:
                entries.append(
                    WorkspaceEntry(
                        entry_id=f"entry-rep-{r.report_id}",
                        artifact_type="REPORT",
                        title=r.title,
                        as_of=r.as_of,
                        references=WorkspaceReferences(report_id=r.report_id),
                    )
                )

        # 2. Dashboards View
        if dashboard_snapshot:
            entries.append(
                WorkspaceEntry(
                    entry_id=f"entry-dash-{dashboard_snapshot.snapshot_id}",
                    artifact_type="DASHBOARD",
                    title=f"Dashboard Operational View ({dashboard_snapshot.snapshot_id})",
                    as_of=dashboard_snapshot.as_of,
                    references=WorkspaceReferences(dashboard_snapshot_id=dashboard_snapshot.snapshot_id),
                )
            )

        # 3. Explanations View
        if explanation_snapshot:
            entries.append(
                WorkspaceEntry(
                    entry_id=f"entry-exp-{explanation_snapshot.snapshot_id}",
                    artifact_type="EXPLAINABILITY",
                    title=f"Explanation Rationale View ({explanation_snapshot.snapshot_id})",
                    as_of=explanation_snapshot.as_of,
                    references=WorkspaceReferences(explanation_snapshot_id=explanation_snapshot.snapshot_id),
                )
            )

        # 4. Timelines View
        if timeline_snapshot:
            entries.append(
                WorkspaceEntry(
                    entry_id=f"entry-tl-{timeline_snapshot.snapshot_id}",
                    artifact_type="TIMELINE",
                    title=f"Audit & Timeline Reconstruction ({timeline_snapshot.snapshot_id})",
                    as_of=timeline_snapshot.as_of,
                    references=WorkspaceReferences(timeline_snapshot_id=timeline_snapshot.snapshot_id),
                )
            )

        # 5. Monitoring View
        if monitoring_snapshot:
            entries.append(
                WorkspaceEntry(
                    entry_id=f"entry-mon-{monitoring_snapshot.snapshot_id}",
                    artifact_type="MONITORING",
                    title=f"Operational Monitoring View ({monitoring_snapshot.snapshot_id})",
                    as_of=monitoring_snapshot.as_of,
                    references=WorkspaceReferences(monitoring_snapshot_id=monitoring_snapshot.snapshot_id),
                )
            )

        # 6. Export View
        if export_snapshot:
            entries.append(
                WorkspaceEntry(
                    entry_id=f"entry-export-{export_snapshot.snapshot_id}",
                    artifact_type="EXPORT",
                    title=f"Batch Export Package ({export_snapshot.snapshot_id})",
                    as_of=export_snapshot.as_of,
                    references=WorkspaceReferences(export_snapshot_id=export_snapshot.snapshot_id),
                )
            )

        # Sort entries deterministically: (as_of, artifact_type, title, entry_id)
        sorted_entries = sorted(entries, key=lambda e: (e.as_of, e.artifact_type, e.title, e.entry_id))

        counts = Counter(e.artifact_type for e in sorted_entries)
        overall_health = (
            monitoring_snapshot.summary.overall_status if monitoring_snapshot else "UNKNOWN"
        )

        summary = WorkspaceSummary(
            total_entries=len(sorted_entries),
            artifact_counts=dict(counts),
            overall_health=overall_health,
        )

        refs = WorkspaceReferences(
            dashboard_snapshot_id=dashboard_snapshot.snapshot_id if dashboard_snapshot else None,
            explanation_snapshot_id=explanation_snapshot.snapshot_id if explanation_snapshot else None,
            timeline_snapshot_id=timeline_snapshot.snapshot_id if timeline_snapshot else None,
            monitoring_snapshot_id=monitoring_snapshot.snapshot_id if monitoring_snapshot else None,
            export_snapshot_id=export_snapshot.snapshot_id if export_snapshot else None,
        )

        snapshot_id = f"ws-{self._next_counter():04d}"
        snapshot = WorkspaceSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            entries=tuple(sorted_entries),
            summary=summary,
            references=refs,
        )

        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
