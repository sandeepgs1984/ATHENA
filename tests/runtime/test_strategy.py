"""Strategy Framework tests (M4.4): multiple strategies, overlapping matches,
no matches, deterministic replay, immutable outputs, configuration validation,
explanation preservation, strategy registration, and a real DailyScanReport +
WatchlistSnapshot chain."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_strategy_config, load_watchlist_config
from athena.config.models import StrategyConfig, StrategyRuleCfg
from athena.decision.models import DecisionOutcome
from athena.domain.decision import Decision, DecisionTrace, TraceStage
from athena.domain.enums import DecisionType
from athena.errors import ConfigError
from athena.reporting.models import DecisionReport
from athena.runtime import ExecutionStatus, WorkflowEngine, WorkflowStage, build_definition
from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
from athena.scanner.models import (
    DailyScanReport,
    InstrumentScanResult,
    ScanStatistics,
    ScanSummary,
)
from athena.strategy import (
    BreakoutStrategy,
    MomentumStrategy,
    StrategyFramework,
)
from athena.watchlist import WatchlistManager
from athena.watchlist.models import WatchlistEntry, WatchlistSnapshot, WatchlistSummary

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
AS_OF_2 = AS_OF + timedelta(days=1)


class FakeClock:
    def __init__(self, step=1.0):
        self._t = 0.0
        self._step = step

    def __call__(self):
        self._t += self._step
        return self._t


def _report(inst, dtype, *, direction="NONE", score=None, conf=None, risk=None):
    machine = {
        "decision": {"type": dtype, "direction": direction,
                     "explanation": f"{inst} judged {dtype}"},
        "score": {"status": "OK" if score is not None else "UNKNOWN",
                  "composite": str(score) if score is not None else None},
        "confidence": {"status": "OK" if conf is not None else "UNKNOWN",
                       "overall": str(conf) if conf is not None else None},
        "risk": {"status": "OK" if risk is not None else "UNKNOWN",
                 "overall": str(risk) if risk is not None else None},
        "references": {"score_ref": f"s-{inst}", "confidence_ref": f"c-{inst}",
                       "risk_ref": f"r-{inst}"},
    }
    return DecisionReport(decision_id=f"dec-{inst}", decision_type=dtype, ts=AS_OF,
                          machine=machine, text=f"{inst} report")


def _scan(specs: dict[str, dict], *, as_of=AS_OF, scan_id="scan-1") -> DailyScanReport:
    results = tuple(
        InstrumentScanResult(
            instrument_id=inst, status=ExecutionStatus.COMPLETED,
            decision_type=s["dtype"], workflow_execution=None,
            report=_report(inst, s["dtype"], direction=s.get("direction", "NONE"),
                           score=s.get("score"), conf=s.get("conf"), risk=s.get("risk")),
            note="ok")
        for inst, s in sorted(specs.items())
    )
    stats = ScanStatistics(total=len(results), successful=len(results), failed=0, skipped=0)
    counts: dict[str, int] = {}
    for s in specs.values():
        counts[s["dtype"]] = counts.get(s["dtype"], 0) + 1
    return DailyScanReport(scan_id=scan_id, as_of=as_of, results=results,
                           statistics=stats, summary=ScanSummary(decision_counts=counts))


def _watchlist(memberships: dict[str, list[str]], *, as_of=AS_OF,
               scan_id="scan-1") -> WatchlistSnapshot:
    entries = tuple(
        WatchlistEntry(
            watchlist=name, instrument_id=inst, decision_type="TRADE",
            decision_id=f"dec-{inst}", explanation="x", decision_ts=as_of,
            scan_id=scan_id, entered_as_of=as_of, last_seen_as_of=as_of)
        for inst, names in sorted(memberships.items()) for name in names
    )
    counts: dict[str, int] = {}
    for names in memberships.values():
        for name in names:
            counts[name] = counts.get(name, 0) + 1
    return WatchlistSnapshot(
        snapshot_id=f"watchlist-{as_of.isoformat()}", as_of=as_of, scan_id=scan_id,
        entries=entries, changes=(), observed_decisions={},
        summary=WatchlistSummary(counts=counts, added=0, retained=0, removed=0))


_MOMENTUM = StrategyRuleCfg(decisions=["TRADE", "INCREASE_POSITION"],
                            watchlists_any=["High Conviction", "Improving"], min_score=60)
_BREAKOUT = StrategyRuleCfg(decisions=["TRADE"], direction="LONG", min_score=65)


def _framework() -> StrategyFramework:
    fw = StrategyFramework()
    fw.register(MomentumStrategy(_MOMENTUM))
    fw.register(BreakoutStrategy(_BREAKOUT))
    return fw


_SPECS = {
    "AAA": {"dtype": "TRADE", "direction": "LONG", "score": 70},
    "BBB": {"dtype": "TRADE", "direction": "SHORT", "score": 62},
    "CCC": {"dtype": "WATCH", "score": 80},
    "DDD": {"dtype": "TRADE", "direction": "LONG", "score": 50},
}
_MEMBERS = {"AAA": ["High Conviction"], "BBB": ["Improving"],
            "CCC": ["Watch"], "DDD": ["High Conviction"]}


def _matched(execution, strategy):
    r = execution.result_for(strategy)
    return sorted(m.instrument_id for m in r.matches)


class TestSelection:
    def test_multiple_strategies(self):
        ex = _framework().execute(_scan(_SPECS), _watchlist(_MEMBERS), as_of=AS_OF)
        assert _matched(ex, "momentum") == ["AAA", "BBB"]  # DDD score too low, CCC wrong decision
        assert _matched(ex, "breakout") == ["AAA"]          # BBB SHORT, DDD score too low

    def test_overlapping_matches(self):
        ex = _framework().execute(_scan(_SPECS), _watchlist(_MEMBERS), as_of=AS_OF)
        assert ex.summary.overlapping_instruments == ("AAA",)
        assert sorted(m.strategy for m in ex.matches_for_instrument("AAA")) == \
            ["breakout", "momentum"]

    def test_no_matches(self):
        fw = StrategyFramework()
        fw.register(MomentumStrategy(StrategyRuleCfg(decisions=["TRADE"], min_score=99)))
        ex = fw.execute(_scan(_SPECS), _watchlist(_MEMBERS), as_of=AS_OF)
        assert _matched(ex, "momentum") == []
        assert ex.summary.total_matches == 0

    def test_unknown_value_excludes(self):
        specs = {"EEE": {"dtype": "TRADE", "direction": "LONG"}}  # no score
        ex = _framework().execute(_scan(specs), _watchlist({"EEE": ["High Conviction"]}),
                                  as_of=AS_OF)
        assert _matched(ex, "momentum") == []  # min_score set, score UNKNOWN -> excluded
        assert _matched(ex, "breakout") == []

    def test_failed_results_ignored(self):
        failed = InstrumentScanResult(
            instrument_id="ZZZ", status=ExecutionStatus.FAILED, decision_type=None,
            workflow_execution=None, report=None, note="boom")
        good = InstrumentScanResult(
            instrument_id="AAA", status=ExecutionStatus.COMPLETED, decision_type="TRADE",
            workflow_execution=None, report=_report("AAA", "TRADE", direction="LONG", score=70),
            note="ok")
        stats = ScanStatistics(total=2, successful=1, failed=1, skipped=0)
        scan = DailyScanReport(scan_id="s", as_of=AS_OF, results=(good, failed),
                               statistics=stats, summary=ScanSummary(decision_counts={"TRADE": 1}))
        ex = _framework().execute(scan, _watchlist({"AAA": ["High Conviction"]}), as_of=AS_OF)
        assert _matched(ex, "momentum") == ["AAA"]
        assert ex.result_for("momentum").considered == 1


class TestExplanation:
    def test_reason_and_references_preserved(self):
        ex = _framework().execute(_scan(_SPECS), _watchlist(_MEMBERS), as_of=AS_OF)
        match = next(m for m in ex.result_for("momentum").matches if m.instrument_id == "AAA")
        assert "momentum" in match.explanation
        assert "score 70>=60" in match.explanation
        assert match.references["decision_id"] == "dec-AAA"
        assert match.references["scan_id"] == "scan-1"
        assert match.references["score_ref"] == "s-AAA"       # lifted from report
        assert match.watchlists == ("High Conviction",)


class TestRegistration:
    def test_strategies_registered(self):
        fw = _framework()
        assert [s.name for s in fw.strategies()] == ["momentum", "breakout"]

    def test_duplicate_registration_rejected(self):
        fw = StrategyFramework()
        fw.register(MomentumStrategy(_MOMENTUM))
        with pytest.raises(ValueError, match="already registered"):
            fw.register(MomentumStrategy(_MOMENTUM))

    def test_from_config_builds_enabled_only(self):
        cfg = StrategyConfig.model_validate({"strategies": {
            "momentum": {"enabled": True, "decisions": ["TRADE"]},
            "breakout": {"enabled": False, "decisions": ["TRADE"]},
        }})
        fw = StrategyFramework.from_config(cfg)
        assert [s.name for s in fw.strategies()] == ["momentum"]

    def test_from_config_unknown_strategy_rejected(self):
        cfg = StrategyConfig.model_validate({"strategies": {
            "nonsense": {"enabled": True, "decisions": ["TRADE"]},
        }})
        with pytest.raises(ValueError, match="unknown reference strategy"):
            StrategyFramework.from_config(cfg)


class TestContract:
    def test_replay_deterministic(self):
        scan, wl = _scan(_SPECS), _watchlist(_MEMBERS)
        ex1 = _framework().execute(scan, wl, as_of=AS_OF)
        ex2 = _framework().execute(scan, wl, as_of=AS_OF)
        assert ex1.to_dict() == ex2.to_dict()

    def test_execution_immutable(self):
        ex = _framework().execute(_scan(_SPECS), _watchlist(_MEMBERS), as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ex.execution_id = "x"

    def test_empty_universe(self):
        ex = _framework().execute(_scan({}), _watchlist({}), as_of=AS_OF)
        assert ex.summary.total_matches == 0
        assert all(r.matches == () for r in ex.results)


class TestConfigValidation:
    def test_unknown_decision_rejected(self):
        with pytest.raises(Exception, match="unknown decision"):
            StrategyConfig.model_validate({"strategies": {
                "momentum": {"decisions": ["NONSENSE"]}}})

    def test_unknown_direction_rejected(self):
        with pytest.raises(Exception, match="unknown direction"):
            StrategyConfig.model_validate({"strategies": {
                "breakout": {"direction": "SIDEWAYS"}}})

    def test_empty_strategies_rejected(self):
        with pytest.raises(Exception, match="at least one strategy"):
            StrategyConfig.model_validate({"strategies": {}})

    def test_production_config_loads(self, config_dir):
        cfg = load_strategy_config(config_dir)
        assert set(cfg.strategies) == {
            "momentum", "swing", "breakout", "mean_reversion", "sector_rotation"}

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_strategy_config(tmp_path)


class TestRealChain:
    def test_real_scan_and_watchlist(self, config_dir):
        """Run the production strategies over artifacts from the real M4.2
        scanner and M4.3 watchlist manager."""

        def builder_factory(decisions):
            def builder(instrument_id):
                dtype = decisions[instrument_id]
                box: dict = {}

                def decide(ctx):
                    decision = Decision(
                        decision_id=f"d-{instrument_id}", ts=ctx.as_of, run_id="scan",
                        cycle_id="scan", decision_type=dtype, instrument_id=instrument_id,
                        explanation=f"{instrument_id} concluded {dtype.value}")
                    trace = DecisionTrace(
                        decision_ref=decision.decision_id,
                        stages=(TraceStage("decision", (decision.decision_id,), "real"),))
                    box["cap"] = ScanCapture(outcome=DecisionOutcome(decision=decision,
                                                                     trace=trace))
                    return {"decided": True}

                defn = build_definition(
                    f"pipe-{instrument_id}",
                    [WorkflowStage("decide", decide, produces=("decided",))])
                return InstrumentPlan(definition=defn, collect=lambda: box.get("cap"))
            return builder

        scanner = DailyMarketScanner(WorkflowEngine(clock=FakeClock()))
        scan_report = scanner.scan(
            ["INFY", "RELIANCE", "TCS"], as_of=AS_OF, pipeline_builder=builder_factory(
                {"INFY": DecisionType.INCREASE_POSITION, "RELIANCE": DecisionType.NO_TRADE,
                 "TCS": DecisionType.WATCH}))

        wl_manager = WatchlistManager(load_watchlist_config(config_dir))
        snapshot = wl_manager.apply(scan_report, as_of=AS_OF)

        framework = StrategyFramework.from_config(load_strategy_config(config_dir))
        execution = framework.execute(scan_report, snapshot, as_of=AS_OF)

        # sector_rotation has no score/confidence thresholds: it selects the
        # High-Conviction INCREASE_POSITION on real artifacts.
        assert _matched(execution, "sector_rotation") == ["INFY"]
        match = execution.result_for("sector_rotation").matches[0]
        assert match.explanation.startswith("sector_rotation:")
        assert "High Conviction" in match.watchlists
        assert match.references["decision_id"] == "d-INFY"
        # score-gated strategies match nothing (real reports carry no score here)
        assert _matched(execution, "momentum") == []
