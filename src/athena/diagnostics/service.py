"""Orchestrate playbook diagnostics from the run ledger (M10.4)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from athena.config.loader import load_decision_config, load_scoring_config
from athena.config.models import DiagnosticsConfig
from athena.data.store.repository import SqliteRepository
from athena.diagnostics.analyzer import PlaybookDiagnosticsAnalyzer
from athena.diagnostics.models import DiagnosticReport
from athena.diagnostics.writer import DiagnosticReportWriter
from athena.domain.decision import Decision, DecisionJournalEntry
from athena.errors import DiagnosticsError


class DecisionOutcomeSource(Protocol):
    def list_decisions(self, as_of: datetime) -> Sequence[Decision]: ...
    def list_journal(self, as_of: datetime) -> Sequence[DecisionJournalEntry]: ...


class PlaybookDiagnosticsService:
    """Assemble inputs → analyze → write artifacts. Never mutates config."""

    def __init__(
        self,
        repo: SqliteRepository,
        config: DiagnosticsConfig,
        *,
        tzinfo: ZoneInfo,
        config_dir: Path,
        repo_root: Path,
        outcome_source: DecisionOutcomeSource | None = None,
    ) -> None:
        if not config.enabled:
            raise DiagnosticsError("diagnostics are disabled in config/diagnostics.json")
        self._repo = repo
        self._config = config
        self._tzinfo = tzinfo
        self._config_dir = Path(config_dir)
        self._repo_root = Path(repo_root)
        self._outcome_source = outcome_source

    def run(self, *, as_of: datetime) -> tuple[DiagnosticReport, Path, Path]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        runs = self._repo.list_runs(limit=self._config.lookback_runs)
        day = as_of.astimezone(self._tzinfo).date()
        day_runs = [
            r for r in runs
            if r.started_ts.astimezone(self._tzinfo).date() == day
        ]
        day_runs.sort(key=lambda r: (r.started_ts, r.run_id))

        decisions: Sequence[Decision] = ()
        journal: Sequence[DecisionJournalEntry] = ()
        if self._outcome_source is not None:
            decisions = tuple(self._outcome_source.list_decisions(as_of))
            journal = tuple(self._outcome_source.list_journal(as_of))

        scoring = load_scoring_config(self._config_dir)
        decision_cfg = load_decision_config(self._config_dir)
        analyzer = PlaybookDiagnosticsAnalyzer(
            self._config, scoring=scoring, decision=decision_cfg, tzinfo=self._tzinfo,
        )
        report = analyzer.analyze(
            as_of=as_of, runs=day_runs, decisions=decisions, journal=journal,
        )

        out = Path(self._config.output_dir)
        if not out.is_absolute():
            out = self._repo_root / out
        writer = DiagnosticReportWriter(out)
        json_path, text_path = writer.write(report)
        return report, json_path, text_path
