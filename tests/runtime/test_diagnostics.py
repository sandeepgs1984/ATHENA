"""M10.4 playbook diagnostics: propose-only tuning suggestions."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena import BLUEPRINT_VERSION, __version__
from athena.config.loader import (
    load_decision_config,
    load_diagnostics_config,
    load_scoring_config,
)
from athena.config.models import DiagnosticsConfig
from athena.data.store import SqliteRepository
from athena.diagnostics import (
    DiagnosticReportWriter,
    DiagnosticStatus,
    PlaybookDiagnosticsAnalyzer,
    PlaybookDiagnosticsService,
    RepositoryOutcomeSource,
    capture_baseline,
    write_baseline,
)
from athena.domain.decision import Decision, DecisionJournalEntry, GateResult, TradeOutcome
from athena.domain.enums import DecisionType, Direction, QualityGate, RunStatus, RunTrigger, UserAction
from athena.domain.run import RunRecord
from athena.errors import ConfigError, DiagnosticsError

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 16, 0, tzinfo=IST)


def _outcome(
    outcome_id: str, decision_ref: str, *, pnl: str, closed_ts: datetime = AS_OF
) -> TradeOutcome:
    return TradeOutcome(
        outcome_id=outcome_id, decision_ref=decision_ref,
        entry_price=Decimal("100"), exit_price=Decimal("100") + Decimal(pnl),
        quantity=1, pnl=Decimal(pnl), holding_seconds=3600,
        adherence={"entry": True}, closed_ts=closed_ts,
    )


def _run(run_id: str, *, status: RunStatus = RunStatus.COMPLETED) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        cycle_id=f"c-{run_id}",
        trigger=RunTrigger.REFRESH,
        started_ts=AS_OF,
        status=status,
        software_version=__version__,
        blueprint_version=BLUEPRINT_VERSION,
        strategy_profile="intraday-momentum",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg",
        finished_ts=AS_OF,
    )


def _decision(
    decision_id: str,
    *,
    dtype: DecisionType = DecisionType.WATCH,
    gates: tuple[GateResult, ...] = (),
) -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id="r1",
        cycle_id="c1",
        decision_type=dtype,
        explanation=f"{decision_id} explanation",
        instrument_id="SYN-AAA",
        direction=Direction.NONE,
        gate_results=gates,
    )


class TestConfig:
    def test_loads_diagnostics_config(self, config_dir):
        cfg = load_diagnostics_config(config_dir)
        assert cfg.enabled is True
        assert cfg.min_sample_size == 30

    def test_missing_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"diagnostics.json"):
            load_diagnostics_config(tmp_path)


class TestAnalyzer:
    def test_empty_insufficient(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        report = analyzer.analyze(as_of=AS_OF, runs=[], decisions=[], journal=[])
        assert report.status is DiagnosticStatus.INSUFFICIENT_DATA
        assert report.proposals == ()

    def test_runs_only_degraded(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        report = analyzer.analyze(as_of=AS_OF, runs=[_run("r1")], decisions=[], journal=[])
        assert report.status is DiagnosticStatus.DEGRADED
        assert "no_decision_inputs" in report.degradation_reasons
        assert report.to_json() == analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], decisions=[], journal=[],
        ).to_json()

    def test_failed_run_rate_finding(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(failed_run_rate_watch=0.2),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        runs = [_run("a", status=RunStatus.FAILED), _run("b"), _run("c"), _run("d", status=RunStatus.FAILED)]
        report = analyzer.analyze(as_of=AS_OF, runs=runs)
        assert any(f.finding_id == "ops-failed-run-rate" for f in report.findings)

    def test_rejection_proposal_blocked_below_min_sample(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=30, rejection_rate_actionable=0.4),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        journal = [
            DecisionJournalEntry("d1", UserAction.REJECTED, AS_OF),
            DecisionJournalEntry("d2", UserAction.IGNORED, AS_OF),
            DecisionJournalEntry("d3", UserAction.ACCEPTED, AS_OF),
        ]
        report = analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], decisions=[_decision("d1")], journal=journal,
        )
        props = [p for p in report.proposals if p.proposal_id == "prop-decision-min-composite"]
        assert len(props) == 1
        assert props[0].blocked is True
        assert props[0].block_reason == "sample_below_minimum"

    def test_rejection_proposal_actionable_with_sample(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=5, rejection_rate_actionable=0.4),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        journal = [
            DecisionJournalEntry(f"d{i}", UserAction.REJECTED, AS_OF) for i in range(4)
        ] + [DecisionJournalEntry("d4", UserAction.ACCEPTED, AS_OF)]
        report = analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], decisions=[_decision("d0")], journal=journal,
        )
        props = [p for p in report.proposals if not p.blocked]
        assert any(p.parameter_path == "thresholds.min_composite_for_trade" for p in props)

    def test_risk_gate_paired_weight_proposals_sum_stable(self, config_dir):
        scoring = load_scoring_config(config_dir)
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=2),
            scoring=scoring,
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        gate = GateResult(QualityGate.RISK, False, "risk elevated")
        decisions = [
            _decision("d1", gates=(gate,)),
            _decision("d2", gates=(gate,)),
        ]
        report = analyzer.analyze(as_of=AS_OF, runs=[_run("r1")], decisions=decisions)
        mq = next(p for p in report.proposals if p.parameter_path == "weights.market_quality")
        mom = next(p for p in report.proposals if p.parameter_path == "weights.momentum")
        assert mq.proposed_value + mom.proposed_value == (
            scoring.weights.market_quality + scoring.weights.momentum
        )


class TestPatternHitRateFindings:
    def test_no_finding_below_min_sample_size(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=5),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        outcomes = [_outcome("o1", "d1", pnl="10"), _outcome("o2", "d2", pnl="-5")]
        labels = {"d1": "BULL_TREND", "d2": "BULL_TREND"}
        report = analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], trade_outcomes=outcomes, pattern_labels=labels,
        )
        assert not any(f.category == "pattern_hit_rate" for f in report.findings)

    def test_finding_appears_once_sample_met(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=2),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        outcomes = [
            _outcome("o1", "d1", pnl="10"),
            _outcome("o2", "d2", pnl="-5"),
            _outcome("o3", "d3", pnl="20"),
        ]
        labels = {"d1": "BULL_TREND", "d2": "BULL_TREND", "d3": "BULL_TREND"}
        report = analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], trade_outcomes=outcomes, pattern_labels=labels,
        )
        finding = next(f for f in report.findings if f.finding_id == "pattern-hit-rate-BULL_TREND")
        assert finding.evidence["wins"] == 2
        assert finding.evidence["total"] == 3
        assert finding.evidence["hit_rate"] == round(2 / 3, 4)

    def test_buckets_are_independent(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=2),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        outcomes = [
            _outcome("o1", "d1", pnl="10"), _outcome("o2", "d2", pnl="10"),  # BULL: 2 (met)
            _outcome("o3", "d3", pnl="-5"),  # BEAR: 1 (not met)
        ]
        labels = {"d1": "BULL_TREND", "d2": "BULL_TREND", "d3": "BEAR_TREND"}
        report = analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], trade_outcomes=outcomes, pattern_labels=labels,
        )
        assert any(f.finding_id == "pattern-hit-rate-BULL_TREND" for f in report.findings)
        assert not any(f.finding_id == "pattern-hit-rate-BEAR_TREND" for f in report.findings)

    def test_outcome_with_unresolved_label_is_ignored(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(min_sample_size=1),
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
            tzinfo=IST,
        )
        outcomes = [_outcome("o1", "d1", pnl="10")]
        report = analyzer.analyze(
            as_of=AS_OF, runs=[_run("r1")], trade_outcomes=outcomes, pattern_labels={},
        )
        assert not any(f.category == "pattern_hit_rate" for f in report.findings)

    def test_no_trade_outcomes_is_a_degradation_reason(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(), tzinfo=IST,
            scoring=load_scoring_config(config_dir), decision=load_decision_config(config_dir),
        )
        report = analyzer.analyze(as_of=AS_OF, runs=[_run("r1")])
        assert "no_trade_outcome_inputs" in report.degradation_reasons


class TestWeightDriftFindings:
    def test_no_finding_when_no_drifts(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(), tzinfo=IST,
            scoring=load_scoring_config(config_dir), decision=load_decision_config(config_dir),
        )
        report = analyzer.analyze(as_of=AS_OF, runs=[_run("r1")], weight_drifts=())
        assert not any(f.category == "weight_drift" for f in report.findings)

    def test_finding_lists_every_drift(self, config_dir):
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(), tzinfo=IST,
            scoring=load_scoring_config(config_dir), decision=load_decision_config(config_dir),
        )
        drifts = ["scoring.weights.trend: 20 -> 30", "scoring.weights.momentum: 20 -> 10"]
        report = analyzer.analyze(as_of=AS_OF, runs=[_run("r1")], weight_drifts=drifts)
        finding = next(f for f in report.findings if f.finding_id == "signal-weight-drift")
        assert finding.evidence["drifts"] == drifts
        assert finding.severity == "watch"


class TestRepositoryOutcomeSource:
    def test_bounds_decisions_and_journal_to_as_of(self, tmp_path: Path):
        repo = SqliteRepository(tmp_path / "src.db")
        repo.initialize()
        early = _decision("d-early")
        late_ts = AS_OF + timedelta(days=1)
        late = Decision(
            decision_id="d-late", ts=late_ts, run_id="r1", cycle_id="c1",
            decision_type=DecisionType.WATCH, explanation="late",
            instrument_id="SYN-AAA", direction=Direction.NONE,
        )
        repo.save_decision(early)
        repo.save_decision(late)
        repo.save_journal_entry(DecisionJournalEntry("d-early", UserAction.ACCEPTED, AS_OF))
        repo.save_journal_entry(
            DecisionJournalEntry("d-late", UserAction.ACCEPTED, late_ts)
        )

        source = RepositoryOutcomeSource(repo, limit=100)
        decisions = source.list_decisions(AS_OF)
        journal = source.list_journal(AS_OF)
        repo.close()

        assert {d.decision_id for d in decisions} == {"d-early"}
        assert {j.decision_ref for j in journal} == {"d-early"}


class TestServiceWeightDriftAlert:
    def test_dispatches_alert_when_baseline_drifted(self, tmp_path: Path, config_dir):
        import json

        from athena.config.models import FailureAlertsConfig
        from athena.ops.failure_alerts import FailureAlertDispatcher

        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        repo.save_run(_run("r1"), detail={"phase": "finished"})

        # Capture a baseline, then mutate the config on disk so the NEXT
        # service.run() sees a real drift relative to that captured file.
        scoring = load_scoring_config(config_dir)
        decision = load_decision_config(config_dir)
        cfg = DiagnosticsConfig(output_dir=str(tmp_path / "diag"))
        baseline = capture_baseline(scoring, decision, as_of=AS_OF)
        write_baseline(tmp_path / "diag" / cfg.weight_drift_baseline_file, baseline)

        scoring_path = config_dir / "scoring.json"
        data = json.loads(scoring_path.read_text())
        data["weights"]["trend"] += 5
        data["weights"]["momentum"] -= 5
        scoring_path.write_text(json.dumps(data))

        alerts = FailureAlertDispatcher(
            FailureAlertsConfig(enabled=True, output_dir=str(tmp_path / "alerts")),
            repo_root=tmp_path, tzinfo=IST,
        )
        service = PlaybookDiagnosticsService(
            repo, cfg, tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
            alert_dispatcher=alerts,
        )
        report, _, _ = service.run(as_of=AS_OF)
        repo.close()

        assert any(f.category == "weight_drift" for f in report.findings)
        alert_files = list((tmp_path / "alerts").glob("alert-*.json"))
        assert alert_files
        payload = json.loads(alert_files[0].read_text())
        assert payload["source"] == "weight-drift"

    def test_no_alert_when_no_baseline_captured_yet(self, tmp_path: Path, config_dir):
        from unittest.mock import MagicMock

        repo = SqliteRepository(tmp_path / "b.db")
        repo.initialize()
        repo.save_run(_run("r1"), detail={"phase": "finished"})
        alerts = MagicMock()
        cfg = DiagnosticsConfig(output_dir=str(tmp_path / "diag"))
        service = PlaybookDiagnosticsService(
            repo, cfg, tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
            alert_dispatcher=alerts,
        )
        report, _, _ = service.run(as_of=AS_OF)
        repo.close()
        assert not any(f.category == "weight_drift" for f in report.findings)
        alerts.dispatch.assert_not_called()


class TestResolvePatternLabels:
    def test_resolves_trend_label_from_persisted_run_detail(self, tmp_path: Path, config_dir):
        repo = SqliteRepository(tmp_path / "c.db")
        repo.initialize()
        decision = _decision("d1")
        repo.save_decision(decision)
        run_detail = {
            "decision_reports": {
                "decision-SYN-AAA-2026-02-13": {
                    "decision": {"id": "d1", "instrument_id": "SYN-AAA"},
                    "regime": {
                        "evidence": [
                            {"dimension": "trend", "outcome": "BULL_TREND"},
                            {"dimension": "breadth", "outcome": "STRONG_BREADTH"},
                        ]
                    },
                }
            }
        }
        repo.save_run(_run("r1"), detail=run_detail)
        outcomes = [_outcome("o1", "d1", pnl="10")]

        cfg = DiagnosticsConfig(output_dir=str(tmp_path / "diag"))
        service = PlaybookDiagnosticsService(
            repo, cfg, tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
        )
        labels = service._resolve_pattern_labels([decision], outcomes)
        repo.close()

        assert labels == {"d1": "BULL_TREND"}

    def test_no_outcomes_resolves_nothing(self, tmp_path: Path, config_dir):
        repo = SqliteRepository(tmp_path / "d.db")
        repo.initialize()
        cfg = DiagnosticsConfig(output_dir=str(tmp_path / "diag"))
        service = PlaybookDiagnosticsService(
            repo, cfg, tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
        )
        labels = service._resolve_pattern_labels([], [])
        repo.close()
        assert labels == {}

    def test_missing_report_for_ref_is_skipped(self, tmp_path: Path, config_dir):
        repo = SqliteRepository(tmp_path / "e.db")
        repo.initialize()
        decision = _decision("d-missing")
        repo.save_decision(decision)
        repo.save_run(_run("r1"), detail={"decision_reports": {}})
        outcomes = [_outcome("o1", "d-missing", pnl="10")]
        cfg = DiagnosticsConfig(output_dir=str(tmp_path / "diag"))
        service = PlaybookDiagnosticsService(
            repo, cfg, tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
        )
        labels = service._resolve_pattern_labels([decision], outcomes)
        repo.close()
        assert labels == {}


class TestWriterAndService:
    def test_writer_does_not_touch_config(self, tmp_path, config_dir):
        scoring_path = config_dir / "scoring.json"
        before = scoring_path.read_text(encoding="utf-8")
        analyzer = PlaybookDiagnosticsAnalyzer(
            DiagnosticsConfig(), tzinfo=IST,
            scoring=load_scoring_config(config_dir),
            decision=load_decision_config(config_dir),
        )
        report = analyzer.analyze(as_of=AS_OF, runs=[_run("r1")])
        out = tmp_path / "diagnostics"
        DiagnosticReportWriter(out).write(report)
        assert (out / f"{report.report_id}.json").exists()
        assert scoring_path.read_text(encoding="utf-8") == before

    def test_service_writes_artifacts(self, tmp_path, config_dir):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        repo.save_run(_run("r1"), detail={"phase": "finished"})
        cfg = DiagnosticsConfig(output_dir=str(tmp_path / "diag"))
        service = PlaybookDiagnosticsService(
            repo, cfg, tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
        )
        report, json_path, text_path = service.run(as_of=AS_OF)
        assert report.status is DiagnosticStatus.DEGRADED
        assert json_path.exists() and text_path.exists()
        repo.close()

    def test_disabled_fails(self, tmp_path, config_dir):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        with pytest.raises(DiagnosticsError, match=r"disabled"):
            PlaybookDiagnosticsService(
                repo, DiagnosticsConfig(enabled=False),
                tzinfo=IST, config_dir=config_dir, repo_root=tmp_path,
            )
        repo.close()
