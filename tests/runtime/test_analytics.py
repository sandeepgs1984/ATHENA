"""Reporting & Analytics tests (M4.6): daily analytics, replay analytics,
aggregation correctness, empty inputs, deterministic replay, immutable outputs,
serialization, configuration validation, and a real BacktestRun end-to-end."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.analytics import ReportingAnalyticsEngine
from athena.backtest import BacktestingEngine, ReplayPoint
from athena.config.loader import (
    load_analytics_config,
    load_strategy_config,
    load_watchlist_config,
)
from athena.config.models import AnalyticsConfig
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
from athena.strategy import StrategyFramework
from athena.watchlist import WatchlistManager
from athena.watchlist.models import WatchlistEntry, WatchlistSnapshot, WatchlistSummary

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
DAY2 = AS_OF + timedelta(days=1)
DAY3 = AS_OF + timedelta(days=2)


class FakeClock:
    def __init__(self, step=1.0):
        self._t = 0.0
        self._step = step

    def __call__(self):
        self._t += self._step
        return self._t


def _report(inst, dtype, *, conf_level="UNKNOWN", risk_level="UNKNOWN"):
    machine = {
        "decision": {"type": dtype, "direction": "NONE", "explanation": f"{inst} {dtype}"},
        "confidence": {"status": "OK", "level": conf_level},
        "risk": {"status": "OK", "level": risk_level},
    }
    return DecisionReport(decision_id=f"dec-{inst}", decision_type=dtype, ts=AS_OF,
                          machine=machine, text=f"{inst} report")


def _scan(specs, *, as_of=AS_OF, scan_id="scan-1", skipped=0):
    results = tuple(
        InstrumentScanResult(
            instrument_id=inst, status=ExecutionStatus.COMPLETED, decision_type=s["dtype"],
            workflow_execution=None,
            report=_report(inst, s["dtype"], conf_level=s.get("conf", "UNKNOWN"),
                           risk_level=s.get("risk", "UNKNOWN")),
            note="ok")
        for inst, s in sorted(specs.items())
    )
    stats = ScanStatistics(total=len(results) + skipped, successful=len(results),
                           failed=0, skipped=skipped)
    counts: dict[str, int] = {}
    for s in specs.values():
        counts[s["dtype"]] = counts.get(s["dtype"], 0) + 1
    return DailyScanReport(scan_id=scan_id, as_of=as_of, results=results,
                           statistics=stats, summary=ScanSummary(decision_counts=counts))


def _watchlist(memberships, *, as_of=AS_OF, scan_id="scan-1"):
    entries = tuple(
        WatchlistEntry(watchlist=name, instrument_id=inst, decision_type="TRADE",
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
        summary=WatchlistSummary(counts=counts, added=len(entries), retained=0, removed=0))


_SPECS = {
    "AAA": {"dtype": "TRADE", "conf": "HIGH", "risk": "LOW"},
    "BBB": {"dtype": "TRADE", "conf": "HIGH", "risk": "MEDIUM"},
    "CCC": {"dtype": "WATCH", "conf": "MEDIUM", "risk": "LOW"},
}


@pytest.fixture()
def engine():
    return ReportingAnalyticsEngine()


class TestDaily:
    def test_decision_distribution(self, engine):
        report = engine.daily_report(_scan(_SPECS), as_of=AS_OF)
        assert report.daily.decision_distribution == {"TRADE": 2, "WATCH": 1}
        assert report.daily.instruments_scanned == 3

    def test_confidence_and_risk_distributions(self, engine):
        report = engine.daily_report(_scan(_SPECS), as_of=AS_OF)
        assert report.daily.confidence_distribution == {"HIGH": 2, "MEDIUM": 1}
        assert report.daily.risk_distribution == {"LOW": 2, "MEDIUM": 1}

    def test_embeds_watchlist_and_strategy(self, engine):
        scan = _scan(_SPECS)
        wl = _watchlist({"AAA": ["High Conviction"], "CCC": ["Watch"]})
        report = engine.daily_report(scan, as_of=AS_OF, watchlist=wl)
        assert report.daily.watchlist.total_entries == 2
        assert report.daily.watchlist.counts["High Conviction"] == 1
        assert report.references["watchlist_snapshot_id"] == wl.snapshot_id
        assert report.summary.totals["watchlist_entries"] == 2

    def test_skipped_counted(self, engine):
        report = engine.daily_report(_scan(_SPECS, skipped=2), as_of=AS_OF)
        assert report.daily.skipped == 2
        assert report.daily.instruments_scanned == 5


class TestConfigDrivenDistribution:
    def test_include_unknown_toggle(self):
        specs = {"AAA": {"dtype": "TRADE", "conf": "HIGH"},
                 "BBB": {"dtype": "WATCH"}}  # BBB conf UNKNOWN
        with_unknown = ReportingAnalyticsEngine(AnalyticsConfig(include_unknown=True))
        without = ReportingAnalyticsEngine(AnalyticsConfig(include_unknown=False))
        assert with_unknown.daily_report(_scan(specs), as_of=AS_OF).daily \
            .confidence_distribution == {"HIGH": 1, "UNKNOWN": 1}
        assert without.daily_report(_scan(specs), as_of=AS_OF).daily \
            .confidence_distribution == {"HIGH": 1}


class TestEmpty:
    def test_empty_scan(self, engine):
        report = engine.daily_report(_scan({}), as_of=AS_OF)
        assert report.daily.decision_distribution == {}
        assert report.daily.confidence_distribution == {}
        assert report.daily.instruments_scanned == 0
        assert report.daily.watchlist is None and report.daily.strategy is None


class TestContract:
    def test_deterministic_replay(self, engine):
        scan, wl = _scan(_SPECS), _watchlist({"AAA": ["High Conviction"]})
        r1 = engine.daily_report(scan, as_of=AS_OF, watchlist=wl)
        r2 = engine.daily_report(scan, as_of=AS_OF, watchlist=wl)
        assert r1.to_dict() == r2.to_dict()

    def test_immutable_report(self, engine):
        report = engine.daily_report(_scan(_SPECS), as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.report_id = "x"

    def test_serialization_is_sorted_json(self, engine):
        report = engine.daily_report(_scan(_SPECS), as_of=AS_OF)
        text = report.to_json()
        parsed = json.loads(text)
        assert parsed["kind"] == "daily"
        assert parsed["daily"]["decision_distribution"] == {"TRADE": 2, "WATCH": 1}
        # sorted-key determinism
        assert json.dumps(parsed, sort_keys=True, indent=2) == text


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            AnalyticsConfig.model_validate({"bogus": 1})

    def test_lowercase_level_rejected(self):
        with pytest.raises(Exception, match="upper-case"):
            AnalyticsConfig.model_validate({"confidence_levels": ["low"]})

    def test_production_config_loads(self, config_dir):
        cfg = load_analytics_config(config_dir)
        assert cfg.confidence_levels == ["LOW", "MEDIUM", "HIGH"]

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_analytics_config(tmp_path)


class TestReplayEndToEnd:
    def test_real_backtest_run(self, config_dir):
        """Analytics over a BacktestRun produced by the real M4.5 chain."""

        def builder_factory(decisions):
            def builder(instrument_id):
                dtype = decisions[instrument_id]
                box: dict = {}

                def decide(ctx):
                    decision = Decision(
                        decision_id=f"d-{instrument_id}-{ctx.as_of.date()}", ts=ctx.as_of,
                        run_id="bt", cycle_id="bt", decision_type=dtype,
                        instrument_id=instrument_id,
                        explanation=f"{instrument_id} {dtype.value}")
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

        def point(as_of, decisions):
            return ReplayPoint(as_of=as_of, universe=tuple(sorted(decisions)),
                               pipeline_builder=builder_factory(decisions))

        scanner = DailyMarketScanner(WorkflowEngine(clock=FakeClock()))
        wl = WatchlistManager(load_watchlist_config(config_dir))
        fw = StrategyFramework.from_config(load_strategy_config(config_dir))
        backtester = BacktestingEngine(scanner, wl, fw)

        run = backtester.run([
            point(AS_OF, {"INFY": DecisionType.WATCH, "TCS": DecisionType.NO_TRADE}),
            point(DAY2, {"INFY": DecisionType.INCREASE_POSITION, "TCS": DecisionType.WATCH}),
        ])

        engine = ReportingAnalyticsEngine(load_analytics_config(config_dir))
        report = engine.backtest_report(run, as_of=DAY3)

        assert report.kind == "replay"
        assert report.backtest.total_steps == 2
        assert report.backtest.completed_steps == 2
        # decision distribution aggregated across both replay days
        dist = report.backtest.decision_distribution
        assert dist.get("WATCH", 0) >= 2 and dist.get("INCREASE_POSITION", 0) >= 1
        # sector_rotation surfaced the High-Conviction INCREASE_POSITION
        assert report.backtest.strategy_match_counts.get("sector_rotation", 0) >= 1
        assert report.references["run_id"] == run.run_id
        assert report.to_json()  # serializes without error
