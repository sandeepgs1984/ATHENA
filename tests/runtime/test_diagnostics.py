"""M10.4 playbook diagnostics: propose-only tuning suggestions."""

from __future__ import annotations

from datetime import datetime
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
)
from athena.domain.decision import Decision, DecisionJournalEntry, GateResult
from athena.domain.enums import DecisionType, Direction, QualityGate, RunStatus, RunTrigger, UserAction
from athena.domain.run import RunRecord
from athena.errors import ConfigError, DiagnosticsError

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 16, 0, tzinfo=IST)


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
