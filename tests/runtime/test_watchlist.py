"""Watchlist Manager tests (M4.3): additions, removals, retention, history
preservation, deterministic replay, immutable snapshots, multiple watchlists,
empty scans, duplicate protection, config validation, and a real DailyScanReport."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_watchlist_config
from athena.config.models import WatchlistConfig
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
from athena.watchlist import WatchlistChangeType, WatchlistHistory, WatchlistManager

IST = ZoneInfo("Asia/Kolkata")
AS_OF_1 = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
AS_OF_2 = AS_OF_1 + timedelta(days=1)
AS_OF_3 = AS_OF_1 + timedelta(days=2)


class FakeClock:
    def __init__(self, step=1.0):
        self._t = 0.0
        self._step = step

    def __call__(self):
        self._t += self._step
        return self._t


# --- default 5-watchlist config, mirroring production ---------------------

_CFG = WatchlistConfig.model_validate({
    "decision_rank": {
        "TRADE": 6, "INCREASE_POSITION": 6, "WATCH": 5, "WAIT": 4,
        "PARTIAL_EXIT": 3, "REDUCE_POSITION": 3, "NO_TRADE": 2, "AVOID_SECTOR": 2,
        "FULL_EXIT": 1, "MARKET_CLOSED": 0, "INSUFFICIENT_DATA": 0,
        "DATA_VALIDATION_FAILED": 0,
    },
    "watchlists": [
        {"name": "High Conviction",
         "rule": {"type": "decision_in", "decisions": ["TRADE", "INCREASE_POSITION"]}},
        {"name": "Watch", "rule": {"type": "decision_in", "decisions": ["WATCH", "WAIT"]}},
        {"name": "Improving", "rule": {"type": "trend", "direction": "improving"}},
        {"name": "Weakening", "rule": {"type": "trend", "direction": "weakening"}},
        {"name": "Rejected",
         "rule": {"type": "decision_in", "decisions": ["NO_TRADE", "AVOID_SECTOR"]}},
    ],
})


def _report(instrument_id: str, decision_type: str, ts: datetime) -> DecisionReport:
    return DecisionReport(
        decision_id=f"dec-{instrument_id}-{decision_type}", decision_type=decision_type,
        ts=ts, machine={"decision": {"explanation": f"{instrument_id} judged {decision_type}"}},
        text=f"{instrument_id} report")


def _scan(as_of: datetime, decisions: dict[str, str]) -> DailyScanReport:
    """Build a synthetic completed DailyScanReport from {instrument: decision_type}."""
    results = tuple(
        InstrumentScanResult(
            instrument_id=inst, status=ExecutionStatus.COMPLETED, decision_type=dtype,
            workflow_execution=None, report=_report(inst, dtype, as_of),
            note=f"scanned: {dtype}")
        for inst, dtype in sorted(decisions.items())
    )
    stats = ScanStatistics(total=len(results), successful=len(results), failed=0, skipped=0)
    counts: dict[str, int] = {}
    for dtype in decisions.values():
        counts[dtype] = counts.get(dtype, 0) + 1
    return DailyScanReport(scan_id=f"scan-{as_of.isoformat()}", as_of=as_of,
                           results=results, statistics=stats,
                           summary=ScanSummary(decision_counts=counts))


@pytest.fixture()
def manager():
    return WatchlistManager(_CFG)


def _members(snapshot, name):
    return sorted(e.instrument_id for e in snapshot.watchlist(name))


class TestClassification:
    def test_decision_in_watchlists(self, manager):
        snap = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE", "BBB": "WATCH",
                                             "CCC": "NO_TRADE", "DDD": "WAIT"}),
                             as_of=AS_OF_1)
        assert _members(snap, "High Conviction") == ["AAA"]
        assert _members(snap, "Watch") == ["BBB", "DDD"]
        assert _members(snap, "Rejected") == ["CCC"]
        # trend lists empty with no prior scan
        assert _members(snap, "Improving") == []
        assert _members(snap, "Weakening") == []

    def test_instrument_can_join_multiple_watchlists(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "NO_TRADE"}), as_of=AS_OF_1)
        s2 = manager.apply(_scan(AS_OF_2, {"AAA": "TRADE"}), as_of=AS_OF_2, previous=s1)
        # AAA is now both High Conviction AND Improving (2 -> 6)
        assert "AAA" in _members(s2, "High Conviction")
        assert "AAA" in _members(s2, "Improving")


class TestMembershipChanges:
    def test_addition_recorded(self, manager):
        snap = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        adds = [c for c in snap.changes if c.change_type is WatchlistChangeType.ADDED]
        assert any(c.instrument_id == "AAA" and c.watchlist == "High Conviction"
                   for c in adds)
        assert all(c.reason for c in snap.changes)  # every change explained

    def test_retention_recorded(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        s2 = manager.apply(_scan(AS_OF_2, {"AAA": "TRADE"}), as_of=AS_OF_2, previous=s1)
        entry = s2.entry("High Conviction", "AAA")
        assert entry.entered_as_of == AS_OF_1  # entry timestamp preserved
        assert entry.last_seen_as_of == AS_OF_2
        assert any(c.change_type is WatchlistChangeType.RETAINED
                   and c.instrument_id == "AAA" for c in s2.changes)

    def test_removal_when_rule_no_longer_applies(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        s2 = manager.apply(_scan(AS_OF_2, {"AAA": "NO_TRADE"}), as_of=AS_OF_2, previous=s1)
        assert _members(s2, "High Conviction") == []
        removal = next(c for c in s2.changes
                       if c.change_type is WatchlistChangeType.REMOVED
                       and c.watchlist == "High Conviction")
        assert "rule no longer satisfied" in removal.reason

    def test_removal_when_absent_from_scan(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        s2 = manager.apply(_scan(AS_OF_2, {"BBB": "WATCH"}), as_of=AS_OF_2, previous=s1)
        removal = next(c for c in s2.changes
                       if c.change_type is WatchlistChangeType.REMOVED
                       and c.instrument_id == "AAA")
        assert "not present in current scan" in removal.reason
        assert removal.decision_type is None


class TestTrend:
    def test_improving_and_weakening(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "WATCH", "BBB": "TRADE"}), as_of=AS_OF_1)
        # AAA improves WATCH(5)->TRADE(6); BBB weakens TRADE(6)->NO_TRADE(2)
        s2 = manager.apply(_scan(AS_OF_2, {"AAA": "TRADE", "BBB": "NO_TRADE"}),
                           as_of=AS_OF_2, previous=s1)
        assert _members(s2, "Improving") == ["AAA"]
        assert _members(s2, "Weakening") == ["BBB"]
        imp = next(c for c in s2.changes if c.watchlist == "Improving"
                   and c.change_type is WatchlistChangeType.ADDED)
        assert "improved" in imp.reason and "WATCH(5)" in imp.reason

    def test_no_trend_without_prior(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        assert _members(s1, "Improving") == []
        assert _members(s1, "Weakening") == []


class TestHistory:
    def test_history_is_append_only(self, manager):
        history = WatchlistHistory()
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "WATCH"}), as_of=AS_OF_1)
        history1 = history.record(s1)
        s2 = manager.apply(_scan(AS_OF_2, {"AAA": "TRADE"}), as_of=AS_OF_2, previous=s1)
        history2 = history1.record(s2)
        # original histories are untouched (immutability of the record chain)
        assert history.records == ()
        assert len(history1.records) == len(s1.changes)
        assert len(history2.records) == len(s1.changes) + len(s2.changes)
        # AAA's full journey is preserved: entered Watch, then entered High Conviction
        journey = history2.for_instrument("AAA")
        watchlists = {c.watchlist for c in journey}
        assert {"Watch", "High Conviction", "Improving"} <= watchlists

    def test_history_explains_entry_and_exit(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        s2 = manager.apply(_scan(AS_OF_2, {"AAA": "NO_TRADE"}), as_of=AS_OF_2, previous=s1)
        history = WatchlistHistory().record(s1).record(s2)
        hc = history.for_watchlist("High Conviction")
        kinds = [c.change_type for c in hc]
        assert WatchlistChangeType.ADDED in kinds
        assert WatchlistChangeType.REMOVED in kinds


class TestContract:
    def test_replay_deterministic(self):
        m1, m2 = WatchlistManager(_CFG), WatchlistManager(_CFG)
        seq = [({"AAA": "WATCH", "BBB": "NO_TRADE"}, AS_OF_1),
               ({"AAA": "TRADE", "BBB": "WATCH"}, AS_OF_2),
               ({"AAA": "NO_TRADE"}, AS_OF_3)]

        def run(m):
            prev = None
            snaps = []
            for decisions, as_of in seq:
                prev = m.apply(_scan(as_of, decisions), as_of=as_of, previous=prev)
                snaps.append(prev.to_dict())
            return snaps

        assert run(m1) == run(m2)

    def test_snapshot_immutable(self, manager):
        snap = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.scan_id = "x"

    def test_empty_scan(self, manager):
        snap = manager.apply(_scan(AS_OF_1, {}), as_of=AS_OF_1)
        assert snap.entries == ()
        assert snap.changes == ()
        assert snap.summary.counts["High Conviction"] == 0

    def test_empty_scan_removes_prior_members(self, manager):
        s1 = manager.apply(_scan(AS_OF_1, {"AAA": "TRADE"}), as_of=AS_OF_1)
        s2 = manager.apply(_scan(AS_OF_2, {}), as_of=AS_OF_2, previous=s1)
        assert s2.entries == ()
        assert all(c.change_type is WatchlistChangeType.REMOVED for c in s2.changes)

    def test_duplicate_instrument_protection(self, manager):
        dup = InstrumentScanResult(
            instrument_id="AAA", status=ExecutionStatus.COMPLETED, decision_type="TRADE",
            workflow_execution=None, report=_report("AAA", "TRADE", AS_OF_1), note="x")
        stats = ScanStatistics(total=2, successful=2, failed=0, skipped=0)
        report = DailyScanReport(
            scan_id="scan-dup", as_of=AS_OF_1, results=(dup, dup),
            statistics=stats, summary=ScanSummary(decision_counts={"TRADE": 2}))
        with pytest.raises(ValueError, match="duplicate instrument"):
            manager.apply(report, as_of=AS_OF_1)

    def test_failed_and_skipped_results_ignored(self, manager):
        completed = InstrumentScanResult(
            instrument_id="AAA", status=ExecutionStatus.COMPLETED, decision_type="TRADE",
            workflow_execution=None, report=_report("AAA", "TRADE", AS_OF_1), note="ok")
        failed = InstrumentScanResult(
            instrument_id="BBB", status=ExecutionStatus.FAILED, decision_type=None,
            workflow_execution=None, report=None, note="boom")
        stats = ScanStatistics(total=2, successful=1, failed=1, skipped=0)
        report = DailyScanReport(
            scan_id="scan-mix", as_of=AS_OF_1, results=(completed, failed),
            statistics=stats, summary=ScanSummary(decision_counts={"TRADE": 1}))
        snap = manager.apply(report, as_of=AS_OF_1)
        assert _members(snap, "High Conviction") == ["AAA"]
        assert "BBB" not in snap.observed_decisions


class TestConfigValidation:
    def test_duplicate_watchlist_names_rejected(self):
        with pytest.raises(Exception, match="unique"):
            WatchlistConfig.model_validate({
                "decision_rank": {"TRADE": 6},
                "watchlists": [
                    {"name": "X", "rule": {"type": "decision_in", "decisions": ["TRADE"]}},
                    {"name": "X", "rule": {"type": "decision_in", "decisions": ["WATCH"]}},
                ]})

    def test_unknown_decision_rejected(self):
        with pytest.raises(Exception, match="unknown decision"):
            WatchlistConfig.model_validate({
                "decision_rank": {"TRADE": 6},
                "watchlists": [
                    {"name": "X", "rule": {"type": "decision_in", "decisions": ["NONSENSE"]}},
                ]})

    def test_production_config_loads(self, config_dir):
        cfg = load_watchlist_config(config_dir)
        assert [w.name for w in cfg.watchlists] == [
            "High Conviction", "Watch", "Improving", "Weakening", "Rejected"]

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_watchlist_config(tmp_path)


class TestRealScanReport:
    def test_real_daily_scan_report(self, config_dir):
        """Classify a DailyScanReport produced by the real M4.2 scanner."""
        cfg = load_watchlist_config(config_dir)

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
        universe = ["INFY", "RELIANCE", "TCS"]

        report1 = scanner.scan(universe, as_of=AS_OF_1, pipeline_builder=builder_factory(
            {"INFY": DecisionType.WATCH, "RELIANCE": DecisionType.NO_TRADE,
             "TCS": DecisionType.WATCH}))
        # INCREASE_POSITION (a High-Conviction decision) avoids the frozen-domain
        # TRADE invariant that would require a full TradePlan here.
        report2 = scanner.scan(universe, as_of=AS_OF_2, pipeline_builder=builder_factory(
            {"INFY": DecisionType.INCREASE_POSITION, "RELIANCE": DecisionType.WATCH,
             "TCS": DecisionType.NO_TRADE}))

        manager = WatchlistManager(cfg)
        s1 = manager.apply(report1, as_of=AS_OF_1)
        assert _members(s1, "Watch") == ["INFY", "TCS"]
        assert _members(s1, "Rejected") == ["RELIANCE"]

        s2 = manager.apply(report2, as_of=AS_OF_2, previous=s1)
        assert _members(s2, "High Conviction") == ["INFY"]      # WATCH -> INCREASE_POSITION
        assert "INFY" in _members(s2, "Improving")              # 5 -> 6
        assert "RELIANCE" in _members(s2, "Improving")          # NO_TRADE(2) -> WATCH(5)
        assert "TCS" in _members(s2, "Weakening")               # WATCH(5) -> NO_TRADE(2)
        # explanation faithfully carried from the real decision report
        assert (s2.entry("High Conviction", "INFY").explanation
                == "INFY concluded INCREASE_POSITION")
