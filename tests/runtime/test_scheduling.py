"""Scheduling Framework tests (M4.7): manual execution, recurring schedules,
replay schedules, execution ordering, deterministic reruns, immutable outputs,
schedule history, configuration validation, and a real end-to-end scheduled
execution through the full operational pipeline."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.analytics import ReportingAnalyticsEngine
from athena.backtest import BacktestingEngine, ReplayPoint
from athena.config.loader import (
    load_analytics_config,
    load_scheduling_config,
    load_strategy_config,
    load_watchlist_config,
)
from athena.config.models import SchedulingConfig
from athena.decision.models import DecisionOutcome
from athena.domain.decision import Decision, DecisionTrace, TraceStage
from athena.domain.enums import DecisionType
from athena.errors import ConfigError
from athena.runtime import ExecutionStatus, WorkflowEngine, WorkflowStage, build_definition
from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
from athena.scheduling import (
    ScheduleDefinition,
    ScheduleMode,
    SchedulingFramework,
)
from athena.strategy import StrategyFramework
from athena.watchlist import WatchlistManager

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


# --------------------------------------------------------------- helpers


def _builder_factory(decisions):
    """Build a per-instrument pipeline_builder from a {id: DecisionType} map."""

    def builder(instrument_id):
        dtype = decisions.get(instrument_id)
        if dtype is None:
            return None
        box: dict = {}

        def decide(ctx):
            decision = Decision(
                decision_id=f"d-{instrument_id}-{ctx.as_of.date()}", ts=ctx.as_of,
                run_id="sched", cycle_id="sched", decision_type=dtype,
                instrument_id=instrument_id,
                explanation=f"{instrument_id} {dtype.value}")
            trace = DecisionTrace(
                decision_ref=decision.decision_id,
                stages=(TraceStage("decision", (decision.decision_id,), "real"),))
            box["cap"] = ScanCapture(
                outcome=DecisionOutcome(decision=decision, trace=trace))
            return {"decided": True}

        defn = build_definition(
            f"pipe-{instrument_id}",
            [WorkflowStage("decide", decide, produces=("decided",))])
        return InstrumentPlan(definition=defn, collect=lambda: box.get("cap"))

    return builder


def _daily_def(name="daily-scan", mode=ScheduleMode.DAILY):
    return ScheduleDefinition(
        definition_id=name, name=f"Test {name}",
        mode=mode, description=f"Test schedule {name}")


def _replay_def():
    return ScheduleDefinition(
        definition_id="replay-1", name="Test Replay",
        mode=ScheduleMode.REPLAY, description="Test replay schedule")


def _framework(config_dir, *, config=None):
    clock = FakeClock()
    scanner = DailyMarketScanner(WorkflowEngine(clock=clock))
    wl = WatchlistManager(load_watchlist_config(config_dir))
    fw = StrategyFramework.from_config(load_strategy_config(config_dir))
    bt = BacktestingEngine(scanner, wl, fw)
    analytics = ReportingAnalyticsEngine(load_analytics_config(config_dir))
    return SchedulingFramework(
        scanner, wl, fw, bt, analytics, config=config, clock=clock)


def _point(as_of, decisions):
    return ReplayPoint(
        as_of=as_of, universe=tuple(sorted(decisions)),
        pipeline_builder=_builder_factory(decisions))


# --------------------------------------------------------------- tests


class TestManualExecution:
    def test_full_pipeline_execution(self, config_dir):
        fw = _framework(config_dir)
        decisions = {"INFY": DecisionType.TRADE, "TCS": DecisionType.WATCH}
        execution = fw.execute(
            _daily_def(mode=ScheduleMode.MANUAL), as_of=AS_OF,
            pipeline_builder=_builder_factory(decisions),
            universe=("INFY", "TCS"))
        assert execution.status is ExecutionStatus.COMPLETED
        assert execution.references.scan_id is not None
        assert execution.references.watchlist_snapshot_id is not None
        assert execution.references.strategy_execution_id is not None
        assert execution.references.analytics_report_id is not None
        assert execution.duration_seconds > 0
        assert execution.mode is ScheduleMode.MANUAL

    def test_references_preserved(self, config_dir):
        fw = _framework(config_dir)
        decisions = {"INFY": DecisionType.TRADE}
        execution = fw.execute(
            _daily_def(), as_of=AS_OF,
            pipeline_builder=_builder_factory(decisions),
            universe=("INFY",))
        refs = execution.references
        assert refs.scan_id and refs.watchlist_snapshot_id
        assert refs.strategy_execution_id and refs.analytics_report_id
        assert refs.backtest_run_id is None  # not a replay


class TestRecurring:
    def test_daily_multiple_executions(self, config_dir):
        fw = _framework(config_dir)
        defn = _daily_def()
        decisions = {"INFY": DecisionType.TRADE}
        e1 = fw.execute(defn, as_of=AS_OF,
                        pipeline_builder=_builder_factory(decisions),
                        universe=("INFY",))
        e2 = fw.execute(defn, as_of=DAY2,
                        pipeline_builder=_builder_factory(decisions),
                        universe=("INFY",))
        assert len(fw.history.executions) == 2
        assert e1.execution_id != e2.execution_id
        assert e1.definition_id == e2.definition_id

    def test_weekly_mode(self, config_dir):
        fw = _framework(config_dir)
        execution = fw.execute(
            _daily_def(mode=ScheduleMode.WEEKLY), as_of=AS_OF,
            pipeline_builder=_builder_factory({"INFY": DecisionType.TRADE}),
            universe=("INFY",))
        assert execution.mode is ScheduleMode.WEEKLY

    def test_one_time_mode(self, config_dir):
        fw = _framework(config_dir)
        execution = fw.execute(
            _daily_def(mode=ScheduleMode.ONE_TIME), as_of=AS_OF,
            pipeline_builder=_builder_factory({"INFY": DecisionType.TRADE}),
            universe=("INFY",))
        assert execution.mode is ScheduleMode.ONE_TIME


class TestReplaySchedule:
    def test_replay_execution(self, config_dir):
        fw = _framework(config_dir)
        execution = fw.execute_replay(
            _replay_def(), as_of=DAY3,
            replay_points=[
                _point(AS_OF, {"INFY": DecisionType.WATCH}),
                _point(DAY2, {"TCS": DecisionType.TRADE}),
            ])
        assert execution.status is ExecutionStatus.COMPLETED
        assert execution.references.backtest_run_id is not None
        assert execution.references.analytics_report_id is not None
        assert execution.references.scan_id is None  # replay path
        assert execution.mode is ScheduleMode.REPLAY

    def test_execute_rejects_replay_mode(self, config_dir):
        """execute() must refuse REPLAY — use execute_replay() instead."""
        fw = _framework(config_dir)
        with pytest.raises(ValueError, match="execute_replay"):
            fw.execute(
                _replay_def(), as_of=AS_OF,
                pipeline_builder=_builder_factory({}), universe=())


class TestExecutionOrdering:
    def test_history_preserves_chronological_order(self, config_dir):
        fw = _framework(config_dir)
        decisions = {"INFY": DecisionType.TRADE}
        for day in (AS_OF, DAY2, DAY3):
            fw.execute(_daily_def(), as_of=day,
                       pipeline_builder=_builder_factory(decisions),
                       universe=("INFY",))
        history = fw.history
        assert len(history.executions) == 3
        dates = [e.as_of for e in history.executions]
        assert dates == [AS_OF, DAY2, DAY3]


class TestContract:
    def test_deterministic_rerun(self, config_dir):
        decisions = {"INFY": DecisionType.TRADE}
        fw1 = _framework(config_dir)
        e1 = fw1.execute(_daily_def(), as_of=AS_OF,
                         pipeline_builder=_builder_factory(decisions),
                         universe=("INFY",))
        fw2 = _framework(config_dir)
        e2 = fw2.execute(_daily_def(), as_of=AS_OF,
                         pipeline_builder=_builder_factory(decisions),
                         universe=("INFY",))
        assert e1.to_dict() == e2.to_dict()

    def test_immutable_execution(self, config_dir):
        fw = _framework(config_dir)
        execution = fw.execute(
            _daily_def(), as_of=AS_OF,
            pipeline_builder=_builder_factory({"INFY": DecisionType.TRADE}),
            universe=("INFY",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            execution.status = ExecutionStatus.FAILED

    def test_immutable_history(self, config_dir):
        fw = _framework(config_dir)
        fw.execute(_daily_def(), as_of=AS_OF,
                   pipeline_builder=_builder_factory({"INFY": DecisionType.TRADE}),
                   universe=("INFY",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            fw.history.executions = ()


class TestHistory:
    def test_record_and_filter_by_definition(self, config_dir):
        fw = _framework(config_dir)
        decisions = {"INFY": DecisionType.TRADE}
        d1 = _daily_def("scan-a")
        d2 = _daily_def("scan-b")
        fw.execute(d1, as_of=AS_OF,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        fw.execute(d2, as_of=AS_OF,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        fw.execute(d1, as_of=DAY2,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        assert len(fw.history.for_definition("scan-a")) == 2
        assert len(fw.history.for_definition("scan-b")) == 1

    def test_filter_by_mode(self, config_dir):
        fw = _framework(config_dir)
        decisions = {"INFY": DecisionType.TRADE}
        fw.execute(_daily_def(mode=ScheduleMode.DAILY), as_of=AS_OF,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        fw.execute(_daily_def("wk", mode=ScheduleMode.WEEKLY), as_of=AS_OF,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        assert len(fw.history.for_mode(ScheduleMode.DAILY)) == 1
        assert len(fw.history.for_mode(ScheduleMode.WEEKLY)) == 1

    def test_summarize(self, config_dir):
        fw = _framework(config_dir)
        decisions = {"INFY": DecisionType.TRADE}
        fw.execute(_daily_def(), as_of=AS_OF,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        fw.execute(_daily_def(), as_of=DAY2,
                   pipeline_builder=_builder_factory(decisions), universe=("INFY",))
        summary = fw.summarize()
        assert summary.total_executions == 2
        assert summary.completed == 2
        assert summary.failed == 0
        assert summary.by_mode["DAILY"] == 2
        assert summary.by_definition["daily-scan"] == 2

    def test_record_history_disabled(self, config_dir):
        cfg = SchedulingConfig(record_history=False)
        fw = _framework(config_dir, config=cfg)
        fw.execute(_daily_def(), as_of=AS_OF,
                   pipeline_builder=_builder_factory({"INFY": DecisionType.TRADE}),
                   universe=("INFY",))
        assert len(fw.history.executions) == 0


class TestDisabledDefinition:
    def test_disabled_definition_rejected(self, config_dir):
        fw = _framework(config_dir)
        defn = ScheduleDefinition(
            definition_id="disabled", name="Disabled", mode=ScheduleMode.DAILY,
            description="disabled schedule", enabled=False)
        with pytest.raises(ValueError, match="disabled"):
            fw.execute(defn, as_of=AS_OF,
                       pipeline_builder=_builder_factory({}), universe=())


class TestFailureIsolation:
    def test_pipeline_error_recorded(self, config_dir):
        """A scanner-level failure is caught and recorded as FAILED."""
        clock = FakeClock()
        real_scanner = DailyMarketScanner(WorkflowEngine(clock=clock))
        wl = WatchlistManager(load_watchlist_config(config_dir))
        sf = StrategyFramework.from_config(load_strategy_config(config_dir))
        bt = BacktestingEngine(real_scanner, wl, sf)
        analytics = ReportingAnalyticsEngine(load_analytics_config(config_dir))

        class BrokenScanner:
            """Simulates a scanner that explodes unconditionally."""

            def scan(self, *_a, **_kw):
                raise RuntimeError("scanner exploded")

        fw = SchedulingFramework(
            BrokenScanner(), wl, sf, bt, analytics, clock=clock)  # type: ignore[arg-type]
        execution = fw.execute(
            _daily_def(), as_of=AS_OF,
            pipeline_builder=_builder_factory({}), universe=("INFY",))
        assert execution.status is ExecutionStatus.FAILED
        assert "exploded" in execution.note
        assert len(fw.history.executions) == 1


class TestConfigValidation:
    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            SchedulingConfig.model_validate({"bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_scheduling_config(config_dir)
        assert cfg.record_history is True

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_scheduling_config(tmp_path)


class TestEndToEnd:
    def test_full_scheduled_pipeline(self, config_dir):
        """A real scheduled execution through the complete M4.1→M4.6 chain."""
        fw = _framework(config_dir)
        decisions = {
            "INFY": DecisionType.TRADE,
            "TCS": DecisionType.WATCH,
            "RELIANCE": DecisionType.NO_TRADE,
        }
        execution = fw.execute(
            _daily_def(mode=ScheduleMode.MANUAL), as_of=AS_OF,
            pipeline_builder=_builder_factory(decisions),
            universe=tuple(sorted(decisions)))

        assert execution.status is ExecutionStatus.COMPLETED
        assert execution.mode is ScheduleMode.MANUAL
        assert execution.references.scan_id is not None
        assert execution.references.watchlist_snapshot_id is not None
        assert execution.references.strategy_execution_id is not None
        assert execution.references.analytics_report_id is not None
        assert execution.duration_seconds > 0

        # History records it
        assert len(fw.history.executions) == 1
        summary = fw.summarize()
        assert summary.total_executions == 1 and summary.completed == 1

        # Serialization works
        d = execution.to_dict()
        assert d["status"] == "COMPLETED"
        assert d["references"]["scan_id"] is not None
