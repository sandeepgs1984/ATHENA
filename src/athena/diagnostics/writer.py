"""Write diagnostic reports to disk — never touches config/ (M10.4)."""

from __future__ import annotations

from pathlib import Path

from athena.diagnostics.models import DiagnosticReport
from athena.errors import DiagnosticsError


class DiagnosticReportWriter:
    """Persist DiagnosticReport JSON + text under an output directory."""

    def __init__(self, output_dir: str | Path) -> None:
        self._output_dir = Path(output_dir)

    def write(self, report: DiagnosticReport) -> tuple[Path, Path]:
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            json_path = self._output_dir / f"{report.report_id}.json"
            text_path = self._output_dir / f"{report.report_id}.txt"
            json_path.write_text(report.to_json() + "\n", encoding="utf-8")
            text_path.write_text(report.to_text(), encoding="utf-8")
        except OSError as exc:
            raise DiagnosticsError(f"cannot write diagnostic artifacts: {exc}") from exc
        return json_path, text_path
