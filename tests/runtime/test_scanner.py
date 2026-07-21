"""Daily Market Scanner tests (M4.2): multi-instrument scans, partial failures,
deterministic ordering, replay, immutability, statistics, empty universe,
failed workflow handling, and a real multi-instrument pipeline."""

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
from athena.indicators import IndicatorEngine, IndicatorName
from athena.regime import RegimeEngine
from athena.reporting import DecisionReportingEngine
from athena.runtime import ExecutionStatus, WorkflowEngine, WorkflowStage, build_definition
from athena.scanner import DailyMarketScanner, InstrumentPlan, ScanCapture
from athena.scoring import ScoringEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)


class FakeClock:
    def __init__(self, step=1.0):
        self._t = 0.0
        self._step = step

    def __call__(self):
        self._t += self._step
        return self._t


@pytest.fixture()
def scanner():
    return DailyMarketScanner(WorkflowEngine(clock=FakeClock()), DecisionReportingEngine())


# --- lightweight synthetic pipeline (no analytical engines) for control tests ---

def _toy_builder(*, fail_on=(), skip=()):
    """Build a per-instrument plan whose 'decide' stage captures a fake outcome."""
    from athena.decision.models import DecisionOutcome
    from athena.domain.decision import Decision, DecisionTrace, TraceStage
    from athena.domain.enums import DecisionType

    def builder(instrument_id):
        if instrument_id in skip:
            return None
        box: dict[str, DecisionOutcome] = {}

        def decide_stage(ctx):
            if instrument_id in fail_on:
                raise RuntimeError(f"forced failure for {instrument_id}")
            decision = Decision(
                decision_id=f"decision-{instrument_id}", ts=ctx.as_of,
                run_id="scan", cycle_id="scan", decision_type=DecisionType.NO_TRADE,
                instrument_id=instrument_id, explanation="toy no-trade")
            trace = DecisionTrace(decision_ref=decision.decision_id,
                                  stages=(TraceStage("decision", (decision.decision_id,), "toy"),))
            box["outcome"] = DecisionOutcome(decision=decision, trace=trace)
            return {"decided": True}

        defn = build_definition(
            f"toy-{instrument_id}",
            [WorkflowStage("decide", decide_stage, produces=("decided",))])
        return InstrumentPlan(definition=defn,
                              collect=lambda: ScanCapture(outcome=box["outcome"]) if box else None)
    return builder


class TestScanBasics:
    def test_multi_instrument_scan(self, scanner):
        report = scanner.scan(["AAA", "BBB", "CCC"], as_of=AS_OF, pipeline_builder=_toy_builder())
        assert report.statistics.total == 3
        assert report.statistics.successful == 3
        assert report.summary.decision_counts["NO_TRADE"] == 3

    def test_deterministic_ordering(self, scanner):
        report = scanner.scan(["ZZZ", "AAA", "MMM"], as_of=AS_OF, pipeline_builder=_toy_builder())
        ids = [r.instrument_id for r in report.results]
        assert ids == ["AAA", "MMM", "ZZZ"]  # stable sorted

    def test_empty_universe(self, scanner):
        report = scanner.scan([], as_of=AS_OF, pipeline_builder=_toy_builder())
        assert report.statistics.total == 0
        assert report.results == ()


class TestFailureIsolation:
    def test_partial_failure_continues(self, scanner):
        report = scanner.scan(["AAA", "BBB", "CCC"], as_of=AS_OF,
                              pipeline_builder=_toy_builder(fail_on=("BBB",)))
        by = {r.instrument_id: r.status for r in report.results}
        assert by["AAA"] is ExecutionStatus.COMPLETED
        assert by["BBB"] is ExecutionStatus.FAILED   # its workflow stage failed
        assert by["CCC"] is ExecutionStatus.COMPLETED
        assert report.statistics.successful == 2 and report.statistics.failed == 1

    def test_skipped_instrument(self, scanner):
        report = scanner.scan(["AAA", "BBB"], as_of=AS_OF,
                              pipeline_builder=_toy_builder(skip=("BBB",)))
        by = {r.instrument_id: r.status for r in report.results}
        assert by["BBB"] is ExecutionStatus.SKIPPED
        assert report.statistics.skipped == 1

    def test_failed_result_has_no_report(self, scanner):
        report = scanner.scan(["BBB"], as_of=AS_OF, pipeline_builder=_toy_builder(fail_on=("BBB",)))
        assert report.result_for("BBB").report is None


class TestContract:
    def test_replay_deterministic(self):
        s1 = DailyMarketScanner(WorkflowEngine(clock=FakeClock()))
        s2 = DailyMarketScanner(WorkflowEngine(clock=FakeClock()))
        r1 = s1.scan(["AAA", "BBB"], as_of=AS_OF, pipeline_builder=_toy_builder())
        r2 = s2.scan(["AAA", "BBB"], as_of=AS_OF, pipeline_builder=_toy_builder())
        assert r1.to_dict() == r2.to_dict()

    def test_report_immutable(self, scanner):
        report = scanner.scan(["AAA"], as_of=AS_OF, pipeline_builder=_toy_builder())
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.scan_id = "x"

    def test_to_dict_shape(self, scanner):
        report = scanner.scan(["AAA"], as_of=AS_OF, pipeline_builder=_toy_builder())
        d = report.to_dict()
        assert d["statistics"]["successful"] == 1
        assert d["results"][0]["instrument_id"] == "AAA"
        assert d["results"][0]["has_report"] is True


class TestRealPipeline:
    def test_real_multi_instrument_scan(self, config_dir):
        """Scan several instruments through the real analytical pipeline via workflows."""
        cfg = load_config(config_dir)

        def candles(seed):
            return [Candle(instrument_id="X", timeframe=Timeframe.D1,
                           ts_open=datetime.combine(date(2026, 1, 1) + timedelta(days=i),
                                                    datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                           open=Decimal(str(seed + i)), high=Decimal(str(seed + i + 2)),
                           low=Decimal(str(seed + i - 1)), close=Decimal(str(seed + i + 1)),
                           volume=1_000_000, source="test") for i in range(70)]

        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=70, breadth_declines=30, india_vix=Decimal("14"))

        def builder(instrument_id):
            seed = 100 + len(instrument_id)  # deterministic per-id series
            cs = candles(seed)
            box: dict = {}

            def ind_stage(ctx):
                return {"indicators": IndicatorEngine(cfg.indicators).compute_all(
                    [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.ATR,
                     IndicatorName.VOLUME_MA], cs, as_of=ctx.as_of)}

            def reg_stage(ctx):
                return {"regime": RegimeEngine(cfg.regime).assess("NIFTY50", cs, snap,
                                                                  as_of=ctx.as_of)}

            def sco_stage(ctx):
                return {"scoring": ScoringEngine(load_scoring_config(config_dir)).score(
                    instrument_id, as_of=ctx.as_of, indicators=ctx.get("indicators"),
                    regime=ctx.get("regime"))}

            def dec_stage(ctx):
                outcome = DecisionEngine(load_decision_config(config_dir)).decide(
                    instrument_id, as_of=ctx.as_of, scoring=ctx.get("scoring"),
                    regime=ctx.get("regime"), indicators=ctx.get("indicators"))
                box["cap"] = ScanCapture(outcome=outcome, scoring=ctx.get("scoring"),
                                         indicators=ctx.get("indicators"))
                return {"outcome": True}

            defn = build_definition(f"pipe-{instrument_id}", [
                WorkflowStage("indicators", ind_stage, produces=("indicators",)),
                WorkflowStage("regime", reg_stage, produces=("regime",)),
                WorkflowStage("scoring", sco_stage, depends_on=("indicators", "regime"),
                              produces=("scoring",)),
                WorkflowStage("decision", dec_stage, depends_on=("scoring",),
                              produces=("outcome",)),
            ])
            return InstrumentPlan(definition=defn,
                                  collect=lambda: box.get("cap"))

        scanner = DailyMarketScanner(WorkflowEngine(clock=FakeClock()))
        report = scanner.scan(["RELIANCE", "TCS", "INFY"], as_of=AS_OF, pipeline_builder=builder)
        assert report.statistics.total == 3
        assert report.statistics.successful == 3
        assert all(r.report is not None for r in report.results)
        # each report faithfully carries the instrument's decision type
        assert all(r.decision_type is not None for r in report.results)
