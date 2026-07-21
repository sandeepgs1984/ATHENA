"""Backtesting Engine tests (M4.5): chronological replay, deterministic reruns,
empty datasets, partial failures, immutable outputs, history preservation,
configuration validation, multi-strategy replay, and a full end-to-end replay
through the real workflow, scanner, watchlist manager, and strategy framework."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from athena.backtest import BacktestingEngine, ReplayPoint
from athena.config.loader import (
    load_backtest_config,
    load_strategy_config,
    load_watchlist_config,
)
from athena.config.models import BacktestConfig
from athena.decision.models import DecisionOutcome
from athena.domain.decision import Decision, DecisionTrace, TraceStage
from athena.domain.enums import DecisionType
from athena.errors import ConfigError
from athena.runtime import ExecutionStatus, WorkflowEngine, WorkflowStage, build_definition
from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
from athena.strategy import StrategyFramework
from athena.watchlist import WatchlistManager

IST = ZoneInfo("Asia/Kolkata")
DAY1 = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
DAY2 = DAY1 + timedelta(days=1)
DAY3 = DAY1 + timedelta(days=2)


class FakeClock:
    def __init__(self, step=1.0):
        self._t = 0.0
        self._step = step

    def __call__(self):
        self._t += self._step
        return self._t


def _builder_factory(decisions):
    def builder(instrument_id):
        dtype = decisions[instrument_id]
        box: dict = {}

        def decide(ctx):
            decision = Decision(
                decision_id=f"d-{instrument_id}-{ctx.as_of.date()}", ts=ctx.as_of,
                run_id="bt", cycle_id="bt", decision_type=dtype,
                instrument_id=instrument_id,
                explanation=f"{instrument_id} concluded {dtype.value}")
            trace = DecisionTrace(
                decision_ref=decision.decision_id,
                stages=(TraceStage("decision", (decision.decision_id,), "real"),))
            box["cap"] = ScanCapture(outcome=DecisionOutcome(decision=decision, trace=trace))
            return {"decided": True}

        defn = build_definition(
            f"pipe-{instrument_id}",
            [WorkflowStage("decide", decide, produces=("decided",))])
        return InstrumentPlan(definition=defn, collect=lambda: box.get("cap"))
    return builder


def _point(as_of, decisions):
    return ReplayPoint(as_of=as_of, universe=tuple(sorted(decisions)),
                       pipeline_builder=_builder_factory(decisions))


def _engine(config_dir, config=None):
    scanner = DailyMarketScanner(WorkflowEngine(clock=FakeClock()))
    wl = WatchlistManager(load_watchlist_config(config_dir))
    fw = StrategyFramework.from_config(load_strategy_config(config_dir))
    return BacktestingEngine(scanner, wl, fw, config=config)


class FlakyScanner:
    """Wraps a real scanner but raises for chosen replay timestamps."""

    def __init__(self, inner, fail_on):
        self._inner = inner
        self._fail_on = set(fail_on)

    def scan(self, universe, *, as_of, pipeline_builder):
        if as_of in self._fail_on:
            raise RuntimeError("simulated data outage")
        return self._inner.scan(universe, as_of=as_of, pipeline_builder=pipeline_builder)


# Two chronological points: day1 all WATCH, day2 INFY strengthens to a
# High-Conviction INCREASE_POSITION (so watchlist trend + strategies engage).
_POINTS = [
    _point(DAY1, {"INFY": DecisionType.WATCH, "TCS": DecisionType.NO_TRADE}),
    _point(DAY2, {"INFY": DecisionType.INCREASE_POSITION, "TCS": DecisionType.WATCH}),
]


class TestReplay:
    def test_chronological_order(self, config_dir):
        run = _engine(config_dir).run(list(reversed(_POINTS)))  # supplied out of order
        dates = [s.replay_date for s in run.steps]
        assert dates == [DAY1.date(), DAY2.date()]
        assert run.first_replay_date == DAY1.date()
        assert run.last_replay_date == DAY2.date()

    def test_all_steps_completed(self, config_dir):
        run = _engine(config_dir).run(_POINTS)
        assert run.summary.total_steps == 2
        assert run.summary.completed_steps == 2
        assert run.summary.failed_steps == 0
        assert all(s.status is ExecutionStatus.COMPLETED for s in run.steps)

    def test_step_references(self, config_dir):
        run = _engine(config_dir).run(_POINTS)
        step = run.steps[1]
        assert step.scan_id == f"scan-{DAY2.isoformat()}"
        assert step.watchlist_snapshot_id == f"watchlist-{DAY2.isoformat()}"
        assert step.strategy_execution_id == f"strategy-exec-{DAY2.isoformat()}"

    def test_watchlist_state_carries_forward(self, config_dir):
        run = _engine(config_dir).run(_POINTS)
        # day2 INFY improved WATCH->INCREASE_POSITION => trend "Improving" only
        # possible if the prior scan's decision was carried across steps.
        day2 = run.steps[1].watchlist
        improving = sorted(e.instrument_id for e in day2.watchlist("Improving"))
        assert "INFY" in improving

    def test_no_carry_when_disabled(self, config_dir):
        run = _engine(config_dir, BacktestConfig(carry_watchlist=False)).run(_POINTS)
        day2 = run.steps[1].watchlist
        assert day2.watchlist("Improving") == ()  # no prior state => no trend


class TestMultiStrategy:
    def test_strategy_performance_aggregated(self, config_dir):
        run = _engine(config_dir).run(_POINTS)
        perf = run.summary.performance_for("sector_rotation")
        assert perf is not None
        assert "INFY" in perf.instruments          # matched day2 High Conviction
        assert perf.steps_with_matches >= 1
        assert perf.total_matches >= 1
        # every configured strategy appears in the performance roll-up
        names = {p.strategy for p in run.summary.performance}
        assert {"momentum", "swing", "breakout", "mean_reversion",
                "sector_rotation"} <= names


class TestFailureIsolation:
    def test_partial_failure_continues(self, config_dir):
        eng = _engine(config_dir)
        eng._scanner = FlakyScanner(eng._scanner, fail_on={DAY1})
        run = eng.run(_POINTS)  # continue_on_error defaults True
        assert run.summary.total_steps == 2
        assert run.steps[0].status is ExecutionStatus.FAILED
        assert "simulated data outage" in run.steps[0].note
        assert run.steps[1].status is ExecutionStatus.COMPLETED

    def test_stop_on_error(self, config_dir):
        eng = _engine(config_dir, BacktestConfig(continue_on_error=False))
        eng._scanner = FlakyScanner(eng._scanner, fail_on={DAY1})
        run = eng.run(_POINTS)
        # replay stops after the first (failed) step; day2 never executed
        assert run.summary.total_steps == 1
        assert run.steps[0].status is ExecutionStatus.FAILED

    def test_failed_step_does_not_advance_state(self, config_dir):
        eng = _engine(config_dir)
        eng._scanner = FlakyScanner(eng._scanner, fail_on={DAY1})
        run = eng.run(_POINTS)
        # day2 sees no prior watchlist (day1 failed) => no Improving trend
        assert run.steps[1].watchlist.watchlist("Improving") == ()


class TestContract:
    def test_deterministic_rerun(self, config_dir):
        r1 = _engine(config_dir).run(_POINTS)
        r2 = _engine(config_dir).run(_POINTS)
        assert r1.to_dict() == r2.to_dict()

    def test_empty_dataset(self, config_dir):
        run = _engine(config_dir).run([])
        assert run.summary.total_steps == 0
        assert run.steps == ()
        assert run.first_replay_date is None
        assert run.run_id == "backtest-empty"

    def test_immutable_run(self, config_dir):
        run = _engine(config_dir).run(_POINTS)
        with pytest.raises(dataclasses.FrozenInstanceError):
            run.run_id = "x"

    def test_duplicate_replay_point_rejected(self, config_dir):
        with pytest.raises(ValueError, match="duplicate replay point"):
            _engine(config_dir).run([_POINTS[0], _POINTS[0]])

    def test_history_preserved_in_order(self, config_dir):
        run = _engine(config_dir).run(_POINTS)
        # steps retain each replay's full artifacts, chronologically
        assert [s.replay_date for s in run.steps] == [DAY1.date(), DAY2.date()]
        assert run.steps[0].scan_report is not None
        assert run.steps[0].strategy_execution is not None


class TestConfigValidation:
    def test_defaults(self):
        cfg = BacktestConfig()
        assert cfg.continue_on_error is True
        assert cfg.carry_watchlist is True

    def test_unknown_key_rejected(self):
        with pytest.raises(Exception, match=r"Extra inputs|extra"):
            BacktestConfig.model_validate({"continue_on_error": True, "bogus": 1})

    def test_production_config_loads(self, config_dir):
        cfg = load_backtest_config(config_dir)
        assert isinstance(cfg, BacktestConfig)

    def test_missing_config_fails_loudly(self, tmp_path):
        with pytest.raises(ConfigError):
            load_backtest_config(tmp_path)


class TestEndToEnd:
    def test_full_pipeline_replay(self, config_dir):
        """Three-day replay through the real workflow -> scanner -> watchlist ->
        strategy chain, asserting a coherent, deterministic BacktestRun."""
        points = [
            _point(DAY1, {"INFY": DecisionType.NO_TRADE, "TCS": DecisionType.WATCH}),
            _point(DAY2, {"INFY": DecisionType.WATCH, "TCS": DecisionType.INCREASE_POSITION}),
            _point(DAY3, {"INFY": DecisionType.INCREASE_POSITION, "TCS": DecisionType.NO_TRADE}),
        ]
        run = _engine(config_dir).run(points)
        assert run.summary.total_steps == 3
        assert run.summary.completed_steps == 3
        # sector_rotation should have surfaced High-Conviction names over the run
        perf = run.summary.performance_for("sector_rotation")
        assert perf.total_matches >= 1
        # serialization is JSON-shaped and complete
        d = run.to_dict()
        assert d["run_id"].startswith("backtest-")
        assert len(d["session"]["steps"]) == 3
