"""Workflow Orchestration Engine tests (M4.1): success, ordering, failure
isolation, replay determinism, immutability, dependency validation, timing,
multiple definitions, and real-engine coordination."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_config, load_decision_config, load_scoring_config
from athena.decision import DecisionEngine
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.errors import WorkflowError
from athena.indicators import IndicatorEngine, IndicatorName
from athena.regime import RegimeEngine
from athena.runtime import (
    ExecutionStatus,
    WorkflowEngine,
    WorkflowReport,
    WorkflowStage,
    build_definition,
)
from athena.scoring import ScoringEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)


class FakeClock:
    """Deterministic monotonic clock: each call advances by a fixed step."""

    def __init__(self, step: float = 1.0) -> None:
        self._t = 0.0
        self._step = step

    def __call__(self) -> float:
        self._t += self._step
        return self._t


def _stage(name, produces=(), depends_on=(), value=None, fail=False):
    def run(ctx):
        if fail:
            raise RuntimeError(f"boom in {name}")
        return {k: (value if value is not None else name) for k in produces}
    return WorkflowStage(name=name, run=run, depends_on=depends_on, produces=produces)


class TestSuccess:
    def test_complete_workflow(self):
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            _stage("b", produces=("y",), depends_on=("a",)),
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        assert execution.status is ExecutionStatus.COMPLETED
        assert all(s.passed for s in execution.stage_results)
        assert set(execution.produced_keys) == {"x", "y"}

    def test_stage_can_read_prior_output(self):
        def consumer(ctx):
            assert ctx.get("x") == "a"
            return {"z": "ok"}
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            WorkflowStage("b", consumer, depends_on=("a",), produces=("z",)),
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        assert execution.completed


class TestOrdering:
    def test_topological_order(self):
        defn = build_definition("t", [
            _stage("c", depends_on=("a", "b")),
            _stage("a"),
            _stage("b", depends_on=("a",)),
        ])
        assert defn.execution_order == ("a", "b", "c")

    def test_stages_execute_in_order(self):
        defn = build_definition("t", [
            _stage("first", produces=("a",)),
            _stage("second", produces=("b",), depends_on=("first",)),
            _stage("third", produces=("c",), depends_on=("second",)),
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        names = [s.stage_name for s in execution.stage_results]
        assert names == ["first", "second", "third"]


class TestFailureIsolation:
    def test_failed_stage_skips_dependents(self):
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            _stage("b", fail=True, depends_on=("a",)),
            _stage("c", depends_on=("b",)),          # transitive dependent → skipped
            _stage("d", produces=("y",)),            # independent → still runs
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        by = {s.stage_name: s.status for s in execution.stage_results}
        assert by["a"] is ExecutionStatus.COMPLETED
        assert by["b"] is ExecutionStatus.FAILED
        assert by["c"] is ExecutionStatus.SKIPPED
        assert by["d"] is ExecutionStatus.COMPLETED
        assert execution.status is ExecutionStatus.FAILED

    def test_failed_stage_records_error(self):
        defn = build_definition("t", [_stage("a", fail=True)])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        stage = execution.stage("a")
        assert stage.status is ExecutionStatus.FAILED
        assert "boom" in stage.error

    def test_declared_output_mismatch_is_failure(self):
        bad = WorkflowStage("a", run=lambda ctx: {"wrong": 1}, produces=("expected",))
        execution = WorkflowEngine(clock=FakeClock()).execute(
            build_definition("t", [bad]), as_of=AS_OF)
        assert execution.stage("a").status is ExecutionStatus.FAILED


class TestReplayAndImmutability:
    def test_replay_deterministic_with_fixed_clock(self):
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            _stage("b", produces=("y",), depends_on=("a",)),
        ])
        a = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        b = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        assert a == b  # identical incl. timing under a fixed clock

    def test_execution_immutable(self):
        execution = WorkflowEngine(clock=FakeClock()).execute(
            build_definition("t", [_stage("a")]), as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            execution.status = ExecutionStatus.FAILED

    def test_timing_metadata_present(self):
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            _stage("b", produces=("y",), depends_on=("a",)),
        ])
        execution = WorkflowEngine(clock=FakeClock(step=2.0)).execute(defn, as_of=AS_OF)
        assert execution.total_duration_seconds > 0
        assert all(s.duration_seconds >= 0 for s in execution.stage_results)
        # offsets are non-decreasing in execution order
        offsets = [s.started_offset_seconds for s in execution.stage_results]
        assert offsets == sorted(offsets)


class TestDependencyValidation:
    def test_missing_dependency_rejected(self):
        with pytest.raises(WorkflowError, match=r"unknown stage"):
            build_definition("t", [_stage("a", depends_on=("ghost",))])

    def test_cycle_rejected(self):
        with pytest.raises(WorkflowError, match=r"cycle detected"):
            build_definition("t", [
                _stage("a", depends_on=("b",)),
                _stage("b", depends_on=("a",)),
            ])

    def test_duplicate_stage_rejected(self):
        with pytest.raises(WorkflowError, match=r"duplicate stage"):
            build_definition("t", [_stage("a"), _stage("a")])

    def test_key_collision_is_failure(self):
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            _stage("b", produces=("x",)),  # re-produces existing key
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        assert execution.stage("b").status is ExecutionStatus.FAILED


class TestMultipleDefinitionsAndReport:
    def test_multiple_definitions_independent(self):
        engine = WorkflowEngine(clock=FakeClock())
        d1 = build_definition("one", [_stage("a", produces=("x",))])
        d2 = build_definition("two", [_stage("b", produces=("y",))])
        e1 = engine.execute(d1, as_of=AS_OF)
        e2 = engine.execute(d2, as_of=AS_OF)
        assert e1.workflow_name == "one" and e2.workflow_name == "two"

    def test_report_summary(self):
        defn = build_definition("t", [
            _stage("a", produces=("x",)),
            _stage("b", fail=True, depends_on=("a",)),
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        report = WorkflowReport.of(execution)
        machine = report.to_dict()
        assert machine["status"] == "FAILED"
        assert machine["stage_counts"]["COMPLETED"] == 1
        assert machine["stage_counts"]["FAILED"] == 1
        assert "FAIL" in report.to_text()


class TestRealEngineCoordination:
    def test_orchestrates_real_pipeline_without_duplicating_logic(self, config_dir):
        """Stages invoke the existing analytical engines; the orchestrator only coordinates."""
        candles = [Candle(instrument_id="X", timeframe=Timeframe.D1,
                          ts_open=datetime.combine(date(2026, 1, 1) + timedelta(days=i),
                                                   datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                          open=Decimal(str(100 + i)), high=Decimal(str(102 + i)),
                          low=Decimal(str(99 + i)), close=Decimal(str(101 + i)),
                          volume=1_000_000, source="test") for i in range(70)]
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=80, breadth_declines=20, india_vix=Decimal("12"))
        cfg = load_config(config_dir)

        def indicators_stage(ctx):
            return {"indicators": IndicatorEngine(cfg.indicators).compute_all(
                [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.ATR,
                 IndicatorName.VOLUME_MA], candles, as_of=ctx.as_of)}

        def regime_stage(ctx):
            return {"regime": RegimeEngine(cfg.regime).assess("NIFTY50", candles, snap,
                                                              as_of=ctx.as_of)}

        def scoring_stage(ctx):
            return {"scoring": ScoringEngine(load_scoring_config(config_dir)).score(
                "X", as_of=ctx.as_of, indicators=ctx.get("indicators"), regime=ctx.get("regime"))}

        def decision_stage(ctx):
            return {"outcome": DecisionEngine(load_decision_config(config_dir)).decide(
                "X", as_of=ctx.as_of, scoring=ctx.get("scoring"), regime=ctx.get("regime"),
                indicators=ctx.get("indicators"))}

        defn = build_definition("pipeline", [
            WorkflowStage("indicators", indicators_stage, produces=("indicators",)),
            WorkflowStage("regime", regime_stage, produces=("regime",)),
            WorkflowStage("scoring", scoring_stage, depends_on=("indicators", "regime"),
                          produces=("scoring",)),
            WorkflowStage("decision", scoring_stage and decision_stage,
                          depends_on=("scoring",), produces=("outcome",)),
        ])
        execution = WorkflowEngine(clock=FakeClock()).execute(defn, as_of=AS_OF)
        assert execution.completed
        assert set(execution.produced_keys) == {"indicators", "regime", "scoring", "outcome"}
