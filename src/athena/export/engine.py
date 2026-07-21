"""Export & Presentation Layer implementation (P6.6).

Transforms platform artifacts into standardized presentation formats (JSON, Markdown, Text, CSV).
Performs NO state mutation, NO PDF rendering, NO REST endpoints, and NO market analysis.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from datetime import datetime

from athena.config.models import ExportConfig, ExportFormat
from athena.dashboard.models import DashboardSnapshot
from athena.errors import ExportError
from athena.explainability.models import ExplanationSnapshot
from athena.monitoring.models import MonitoringSnapshot
from athena.reporting.models import GenericReport
from athena.timeline.models import TimelineSnapshot
from athena.export.models import (
    ExportArtifact,
    ExportHistory,
    ExportReferences,
    ExportSnapshot,
    ExportSummary,
)

_MIME_MAP = {
    ExportFormat.JSON: "application/json",
    ExportFormat.MARKDOWN: "text/markdown",
    ExportFormat.TEXT: "text/plain",
    ExportFormat.CSV: "text/csv",
}

_EXT_MAP = {
    ExportFormat.JSON: "json",
    ExportFormat.MARKDOWN: "md",
    ExportFormat.TEXT: "txt",
    ExportFormat.CSV: "csv",
}


class ExportPresentationEngine:
    """Deterministic, read-only Export & Presentation Layer engine."""

    def __init__(self, config: ExportConfig | None = None) -> None:
        self._config = config or ExportConfig()
        self._counter = 0
        self._history = ExportHistory()

    @property
    def history(self) -> ExportHistory:
        """Get accumulated export history."""
        return self._history

    def export_report(
        self, report: GenericReport, fmt: ExportFormat = ExportFormat.JSON, *, as_of: datetime
    ) -> ExportArtifact:
        """Export GenericReport to specified format."""
        if as_of.tzinfo is None:
            raise ValueError("export_report as_of datetime must be timezone-aware")

        payload = self._render_artifact(report, fmt)
        filename = f"report_{report.report_id}.{_EXT_MAP[fmt]}"
        refs = ExportReferences(report_id=report.report_id)

        return ExportArtifact(
            export_id=f"exp-{self._next_counter():04d}",
            format=fmt,
            filename=filename,
            content_type=_MIME_MAP[fmt],
            payload=payload,
            as_of=as_of,
            references=refs,
        )

    def export_dashboard(
        self, dashboard_snapshot: DashboardSnapshot, fmt: ExportFormat = ExportFormat.JSON, *, as_of: datetime
    ) -> ExportArtifact:
        """Export DashboardSnapshot to specified format."""
        if as_of.tzinfo is None:
            raise ValueError("export_dashboard as_of datetime must be timezone-aware")

        payload = self._render_artifact(dashboard_snapshot, fmt)
        filename = f"dashboard_{dashboard_snapshot.snapshot_id}.{_EXT_MAP[fmt]}"
        refs = ExportReferences(dashboard_snapshot_id=dashboard_snapshot.snapshot_id)

        return ExportArtifact(
            export_id=f"exp-{self._next_counter():04d}",
            format=fmt,
            filename=filename,
            content_type=_MIME_MAP[fmt],
            payload=payload,
            as_of=as_of,
            references=refs,
        )

    def export_explanation(
        self, explanation_snapshot: ExplanationSnapshot, fmt: ExportFormat = ExportFormat.JSON, *, as_of: datetime
    ) -> ExportArtifact:
        """Export ExplanationSnapshot to specified format."""
        if as_of.tzinfo is None:
            raise ValueError("export_explanation as_of datetime must be timezone-aware")

        payload = self._render_artifact(explanation_snapshot, fmt)
        filename = f"explanation_{explanation_snapshot.snapshot_id}.{_EXT_MAP[fmt]}"
        refs = ExportReferences(explanation_snapshot_id=explanation_snapshot.snapshot_id)

        return ExportArtifact(
            export_id=f"exp-{self._next_counter():04d}",
            format=fmt,
            filename=filename,
            content_type=_MIME_MAP[fmt],
            payload=payload,
            as_of=as_of,
            references=refs,
        )

    def export_timeline(
        self, timeline_snapshot: TimelineSnapshot, fmt: ExportFormat = ExportFormat.JSON, *, as_of: datetime
    ) -> ExportArtifact:
        """Export TimelineSnapshot to specified format."""
        if as_of.tzinfo is None:
            raise ValueError("export_timeline as_of datetime must be timezone-aware")

        payload = self._render_artifact(timeline_snapshot, fmt)
        filename = f"timeline_{timeline_snapshot.snapshot_id}.{_EXT_MAP[fmt]}"
        refs = ExportReferences(timeline_snapshot_id=timeline_snapshot.snapshot_id)

        return ExportArtifact(
            export_id=f"exp-{self._next_counter():04d}",
            format=fmt,
            filename=filename,
            content_type=_MIME_MAP[fmt],
            payload=payload,
            as_of=as_of,
            references=refs,
        )

    def export_monitoring(
        self, monitoring_snapshot: MonitoringSnapshot, fmt: ExportFormat = ExportFormat.JSON, *, as_of: datetime
    ) -> ExportArtifact:
        """Export MonitoringSnapshot to specified format."""
        if as_of.tzinfo is None:
            raise ValueError("export_monitoring as_of datetime must be timezone-aware")

        payload = self._render_artifact(monitoring_snapshot, fmt)
        filename = f"monitoring_{monitoring_snapshot.snapshot_id}.{_EXT_MAP[fmt]}"
        refs = ExportReferences(monitoring_snapshot_id=monitoring_snapshot.snapshot_id)

        return ExportArtifact(
            export_id=f"exp-{self._next_counter():04d}",
            format=fmt,
            filename=filename,
            content_type=_MIME_MAP[fmt],
            payload=payload,
            as_of=as_of,
            references=refs,
        )

    def create_snapshot(
        self, exports: Sequence[ExportArtifact], *, as_of: datetime
    ) -> ExportSnapshot:
        """Aggregate export artifacts into an ExportSnapshot."""
        if as_of.tzinfo is None:
            raise ValueError("create_snapshot as_of datetime must be timezone-aware")

        fmts = tuple(sorted(list({e.format for e in exports}), key=lambda f: f.value))
        tot_bytes = sum(len(e.payload.encode("utf-8")) for e in exports)

        summary = ExportSummary(
            total_exports=len(exports),
            formats_used=fmts,
            total_bytes=tot_bytes,
        )

        snapshot_id = f"expsnap-{self._next_counter():04d}"
        snapshot = ExportSnapshot(
            snapshot_id=snapshot_id,
            as_of=as_of,
            exports=tuple(exports),
            summary=summary,
        )

        if self._config.record_history:
            self._history = self._history.record(snapshot)

        return snapshot

    def _render_artifact(self, obj: object, fmt: ExportFormat) -> str:
        if fmt is ExportFormat.JSON:
            if hasattr(obj, "to_json"):
                return obj.to_json()
            if hasattr(obj, "to_dict"):
                return json.dumps(obj.to_dict(), indent=2, sort_keys=True)
            return json.dumps(obj, indent=2, sort_keys=True)

        elif fmt is ExportFormat.MARKDOWN:
            if hasattr(obj, "to_text"):
                text = obj.to_text()
            else:
                text = str(obj)
            return f"# ATHENA EXPORT\n\n```text\n{text}\n```\n"

        elif fmt is ExportFormat.TEXT:
            if hasattr(obj, "to_text"):
                return obj.to_text()
            if hasattr(obj, "to_dict"):
                return json.dumps(obj.to_dict(), sort_keys=True)
            return str(obj)

        elif fmt is ExportFormat.CSV:
            output = io.StringIO()
            writer = csv.writer(output)

            # Tabular serialization depending on object type
            if hasattr(obj, "checks"):  # MonitoringSnapshot
                writer.writerow(["check_id", "domain", "component", "status", "message"])
                for c in getattr(obj, "checks"):
                    writer.writerow([c.check_id, c.domain.value, c.component, c.status, c.message])
            elif hasattr(obj, "entries"):  # TimelineSnapshot
                writer.writerow(["audit_id", "sequence_number", "domain", "event_type", "summary"])
                for e in getattr(obj, "entries"):
                    writer.writerow([e.audit_id, e.sequence_number, e.event.domain.value, e.event.event_type, e.event.summary])
            elif hasattr(obj, "sections"):  # DashboardSnapshot
                writer.writerow(["section_id", "title", "status", "summary"])
                for s in getattr(obj, "sections"):
                    writer.writerow([s.section_id, s.title, s.status, s.text_summary])
            elif hasattr(obj, "explanations"):  # ExplanationSnapshot
                writer.writerow(["explanation_id", "domain", "title", "summary"])
                for ex in getattr(obj, "explanations"):
                    writer.writerow([ex.explanation_id, ex.domain.value, ex.title, ex.summary])
            else:
                writer.writerow(["key", "value"])
                if hasattr(obj, "to_dict"):
                    for k, v in sorted(obj.to_dict().items()):
                        writer.writerow([k, str(v)])
                else:
                    writer.writerow(["content", str(obj)])

            return output.getvalue()

        else:
            raise ExportError(f"Unsupported export format: {fmt}")

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter
