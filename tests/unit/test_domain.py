"""Domain invariant tests: immutability, mandatory explanations, OHLC sanity,
TRADE-decision contracts, PipelineContext discipline."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from athena.domain import (
    CalendarContext,
    Candle,
    ContextDelta,
    Decision,
    DecisionType,
    Direction,
    Evidence,
    EvidenceCategory,
    GateResult,
    PipelineContext,
    QualityGate,
    RunRecord,
    RunStatus,
    RunTrigger,
    Score,
    SessionType,
    Timeframe,
    TradePlan,
)
from athena.domain.run import ConfigurationSnapshot

TS = datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc)


def _candle(**overrides):
    values = dict(
        instrument_id="INE000A01010", timeframe=Timeframe.M5, ts_open=TS,
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
        close=Decimal("100.5"), volume=1000, source="test",
    )
    values.update(overrides)
    return Candle(**values)


def _evidence(**overrides):
    values = dict(
        evidence_id="ev-1", category=EvidenceCategory.VOLUME, source="test", ts=TS,
        raw_value=Decimal("2.1"), normalized_value=Decimal("0.8"),
        weight=Decimal("20"), confidence=Decimal("0.7"),
        explanation="volume 2.1x its 20-day average",
    )
    values.update(overrides)
    return Evidence(**values)


class TestImmutability:
    def test_candle_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _candle().close = Decimal("200")

    def test_evidence_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _evidence().weight = Decimal("99")


class TestFailLoudly:
    def test_impossible_ohlc_rejected(self):
        with pytest.raises(ValueError, match=r"Impossible OHLC"):
            _candle(high=Decimal("98"))  # high below low

    def test_naive_timestamp_rejected(self):
        with pytest.raises(ValueError, match=r"timezone-aware"):
            _candle(ts_open=datetime(2026, 7, 20, 10, 0))

    def test_evidence_requires_explanation(self):
        with pytest.raises(ValueError, match=r"explanation is mandatory"):
            _evidence(explanation="")

    def test_score_breakdown_must_sum_to_total(self):
        with pytest.raises(ValueError, match=r"breakdown must sum to total"):
            Score(score_id="s1", instrument_id="X", total=90,
                  breakdown={"momentum": 50, "volume": 30},
                  evidence_ids=("ev-1",), config_snapshot_id="cfg-1",
                  explanation="test")


class TestDecisionContract:
    def _plan(self):
        return TradePlan(
            entry_low=Decimal("100"), entry_high=Decimal("101"),
            stop_loss=Decimal("98"), targets=(Decimal("105"),),
            position_size=10, risk_amount=Decimal("300"),
            risk_reward=Decimal("2.5"), valid_from=TS,
            valid_until=TS.replace(hour=15),
        )

    def test_trade_requires_plan_and_direction(self):
        with pytest.raises(ValueError, match=r"must carry a TradePlan"):
            Decision(decision_id="d1", ts=TS, run_id="r1", cycle_id="c1",
                     decision_type=DecisionType.TRADE, explanation="x",
                     direction=Direction.LONG)

    def test_trade_with_failed_gate_is_impossible(self):
        failed = GateResult(gate=QualityGate.DATA, passed=False, detail="stale candles")
        with pytest.raises(ValueError, match=r"cannot have failed quality gates"):
            Decision(decision_id="d1", ts=TS, run_id="r1", cycle_id="c1",
                     decision_type=DecisionType.TRADE, explanation="x",
                     direction=Direction.LONG, trade_plan=self._plan(),
                     gate_results=(failed,))

    def test_non_trade_decision_needs_no_plan(self):
        d = Decision(decision_id="d2", ts=TS, run_id="r1", cycle_id="c1",
                     decision_type=DecisionType.NO_TRADE,
                     explanation="market health 32 below floor 40")
        assert d.trade_plan is None


class TestPipelineContext:
    def _ctx(self):
        run = RunRecord(
            run_id="r1", cycle_id="c1", trigger=RunTrigger.PREMARKET, started_ts=TS,
            status=RunStatus.RUNNING, software_version="abc123",
            blueprint_version="ATHENA-002 v1.1", strategy_profile="intraday-momentum",
            strategy_profile_version="1.0.0", indicator_versions={"rsi": "1.0.0"},
            config_snapshot_id="cfg-1",
        )
        cal = CalendarContext(
            context_date=date(2026, 7, 20), session_type=SessionType.NORMAL,
            exchange="NSE", timezone="Asia/Kolkata", open_time=None, close_time=None,
        )
        snap = ConfigurationSnapshot(snapshot_id="cfg-1", content_hash="h",
                                     payload_json="{}", created_ts=TS)
        return PipelineContext(run=run, calendar=cal, config_snapshot=snap)

    def test_missing_key_fails_with_hint(self):
        with pytest.raises(KeyError, match=r"no 'scores' yet"):
            self._ctx().get("scores")

    def test_delta_produces_new_context(self):
        ctx = self._ctx()
        ctx2 = ctx.with_delta(ContextDelta(producer="regime", outputs={"regime": "BULL"}))
        assert ctx2.get("regime") == "BULL"
        assert not ctx.has("regime")  # original untouched

    def test_reproducing_a_key_is_a_bug(self):
        ctx = self._ctx().with_delta(ContextDelta(producer="regime", outputs={"regime": "BULL"}))
        with pytest.raises(ValueError, match=r"re-produce existing keys"):
            ctx.with_delta(ContextDelta(producer="rogue", outputs={"regime": "BEAR"}))

    def test_context_data_is_read_only(self):
        ctx = self._ctx().with_delta(ContextDelta(producer="regime", outputs={"regime": "BULL"}))
        with pytest.raises(TypeError):
            ctx.data["regime"] = "BEAR"  # type: ignore[index]
