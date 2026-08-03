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
from athena.diagnostics.weight_drift import detect_drift, read_baseline
from athena.diagnostics.writer import DiagnosticReportWriter
from athena.domain.decision import Decision, DecisionJournalEntry, TradeOutcome
from athena.errors import DiagnosticsError
from athena.ops.failure_alerts import FailureAlertDispatcher


class DecisionOutcomeSource(Protocol):
    def list_decisions(self, as_of: datetime) -> Sequence[Decision]: ...
    def list_journal(self, as_of: datetime) -> Sequence[DecisionJournalEntry]: ...


class RepositoryOutcomeSource:
    """M-X10: the first real `DecisionOutcomeSource` implementation —
    `_cmd_diagnose` previously constructed `PlaybookDiagnosticsService`
    with none at all, so `athena diagnose` has only ever seen ops/run
    data in production. Bounds both lists to `ts <= as_of` (no
    look-ahead), reusing the repository's own `list_decisions`/
    `list_journal` (limit-based) rather than adding new query methods."""

    def __init__(self, repo: SqliteRepository, *, limit: int) -> None:
        self._repo = repo
        self._limit = limit

    def list_decisions(self, as_of: datetime) -> Sequence[Decision]:
        return [d for d in self._repo.list_decisions(limit=self._limit) if d.ts <= as_of]

    def list_journal(self, as_of: datetime) -> Sequence[DecisionJournalEntry]:
        return [j for j in self._repo.list_journal(limit=self._limit) if j.action_ts <= as_of]


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
        alert_dispatcher: FailureAlertDispatcher | None = None,
    ) -> None:
        if not config.enabled:
            raise DiagnosticsError("diagnostics are disabled in config/diagnostics.json")
        self._repo = repo
        self._config = config
        self._tzinfo = tzinfo
        self._config_dir = Path(config_dir)
        self._repo_root = Path(repo_root)
        self._outcome_source = outcome_source
        # M-X10: optional — None means weight-drift is still detected (and
        # shown as a report finding) but never dispatched as an alert,
        # matching every other optional-dependency default in this service.
        self._alerts = alert_dispatcher

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

        trade_outcomes = tuple(
            o for o in self._repo.list_trade_outcomes(limit=self._config.lookback_decisions)
            if o.closed_ts <= as_of
        )
        pattern_labels = self._resolve_pattern_labels(decisions, trade_outcomes)

        scoring = load_scoring_config(self._config_dir)
        decision_cfg = load_decision_config(self._config_dir)

        weight_drifts: list[str] = []
        baseline_path = self._baseline_path()
        baseline = read_baseline(baseline_path)
        if baseline is not None:
            weight_drifts = detect_drift(baseline, scoring, decision_cfg)
            if weight_drifts and self._alerts is not None:
                self._alerts.dispatch(
                    title="ATHENA scoring/decision config drifted from baseline",
                    detail="; ".join(weight_drifts),
                    source="weight-drift",
                    as_of=as_of,
                )

        analyzer = PlaybookDiagnosticsAnalyzer(
            self._config, scoring=scoring, decision=decision_cfg, tzinfo=self._tzinfo,
        )
        report = analyzer.analyze(
            as_of=as_of, runs=day_runs, decisions=decisions, journal=journal,
            trade_outcomes=trade_outcomes, pattern_labels=pattern_labels,
            weight_drifts=tuple(weight_drifts),
        )

        out = self._output_dir()
        writer = DiagnosticReportWriter(out)
        json_path, text_path = writer.write(report)
        return report, json_path, text_path

    def _output_dir(self) -> Path:
        out = Path(self._config.output_dir)
        return out if out.is_absolute() else self._repo_root / out

    def _baseline_path(self) -> Path:
        return self._output_dir() / self._config.weight_drift_baseline_file

    def _resolve_pattern_labels(
        self, decisions: Sequence[Decision], trade_outcomes: Sequence[TradeOutcome],
    ) -> dict[str, str]:
        """Regime trend label at decision time, per `decision_ref` — read
        from the persisted run detail (`decision_reports`), the same
        source `ScoringEngine._trend` derives its own trend label from
        (`regime.evidence` where `dimension == "trend"`), never
        re-derived or guessed. Only resolves refs with a real
        `TradeOutcome`, since that's all `_pattern_hit_rate_findings`
        consumes — resolving every decision would be wasted work.
        """
        wanted_refs = {o.decision_ref for o in trade_outcomes}
        if not wanted_refs:
            return {}
        decision_by_ref = {d.decision_id: d for d in decisions}
        run_details: dict[str, dict] = {}
        labels: dict[str, str] = {}
        for ref in wanted_refs:
            decision = decision_by_ref.get(ref)
            if decision is None:
                continue
            detail = run_details.get(decision.run_id)
            if detail is None:
                detail = self._repo.get_run_detail(decision.run_id)
                run_details[decision.run_id] = detail
            reports = detail.get("decision_reports") or {}
            report = next(
                (r for r in reports.values() if r.get("decision", {}).get("id") == ref), None,
            )
            if report is None:
                continue
            evidence = (report.get("regime") or {}).get("evidence") or []
            trend_label = next(
                (e.get("outcome") for e in evidence if e.get("dimension") == "trend"), None,
            )
            if trend_label:
                labels[ref] = trend_label
        return labels
