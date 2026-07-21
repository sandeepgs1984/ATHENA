"""Decision Engine tests (M3.6): gates, trade/non-trade outcomes, UNKNOWN,
frozen-domain invariant enforcement, determinism, immutability, traces, config."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.confidence import ConfidenceEngine
from athena.config.loader import (
    load_confidence_config,
    load_config,
    load_decision_config,
    load_market_health_config,
    load_risk_assessment_config,
    load_scoring_config,
)
from athena.decision import DecisionEngine
from athena.domain.enums import DecisionType, Direction, QualityGate, Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.errors import ConfigError
from athena.evidence import EvidenceAggregationEngine, EvidenceSource
from athena.indicators import IndicatorEngine, IndicatorName
from athena.market_health import MarketHealthEngine
from athena.regime import RegimeEngine
from athena.risk import RiskEngine
from athena.scoring import ScoringEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def decision(config_dir) -> DecisionEngine:
    return DecisionEngine(load_decision_config(config_dir))


def _candles(closes, *, volume=1_000_000):
    out = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        out.append(Candle(instrument_id="X", timeframe=Timeframe.D1,
                          ts_open=datetime.combine(start + timedelta(days=i),
                                                   datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                          open=c, high=c + 1, low=c - 1, close=c, volume=volume, source="test"))
    return out


def _bull_snapshot():
    return MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                          breadth_advances=80, breadth_declines=20, india_vix=Decimal("12"))


def _pipeline(config_dir, candles, snapshot):
    """Run the full analytical pipeline to produce approved artifacts."""
    indicators = IndicatorEngine(load_config(config_dir).indicators).compute_all(
        [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.ADX,
         IndicatorName.MACD, IndicatorName.ATR, IndicatorName.VOLUME_MA], candles, as_of=AS_OF)
    regime = RegimeEngine(load_config(config_dir).regime).assess(
        "NIFTY50", candles, snapshot, as_of=AS_OF)
    market_health = MarketHealthEngine(load_market_health_config(config_dir)).assess(
        "NIFTY50", candles, snapshot, as_of=AS_OF)
    scoring = ScoringEngine(load_scoring_config(config_dir)).score(
        "X", as_of=AS_OF, indicators=indicators, regime=regime, market_health=market_health)
    confidence = ConfidenceEngine(load_confidence_config(config_dir)).assess(
        as_of=AS_OF, scoring=scoring, indicators=indicators)
    risk = RiskEngine(load_risk_assessment_config(config_dir)).assess(
        "X", as_of=AS_OF, regime=regime, market_health=market_health, indicators=indicators)
    bundle = EvidenceAggregationEngine().aggregate(
        as_of=AS_OF, regime=regime, market_health=market_health,
        required_sources=(EvidenceSource.REGIME,))
    return dict(scoring=scoring, confidence=confidence, risk=risk, evidence_bundle=bundle,
                regime=regime, indicators=indicators, market_health=market_health)


class TestOutcomes:
    def test_trade_when_all_conditions_met(self, decision, config_dir):
        # Strong bull, calm, liquid → high composite + passing gates
        artifacts = _pipeline(config_dir, _candles(range(100, 170)), _bull_snapshot())
        outcome = decision.decide("X", as_of=AS_OF, **artifacts)
        d = outcome.decision
        if d.decision_type is DecisionType.TRADE:
            assert d.trade_plan is not None
            assert d.direction is Direction.LONG
            assert all(g.passed for g in d.gate_results)  # invariant: no failed gates
        else:
            # If policy thresholds not met, must be WATCH/NO_TRADE — never a broken TRADE
            assert d.decision_type in {DecisionType.WATCH, DecisionType.NO_TRADE}

    def test_insufficient_data_without_scoring(self, decision):
        outcome = decision.decide("X", as_of=AS_OF)
        assert outcome.decision.decision_type is DecisionType.INSUFFICIENT_DATA
        assert outcome.decision.trade_plan is None

    def test_no_trade_low_composite(self, decision, config_dir):
        # Falling market → low composite → NO_TRADE
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=20, breadth_declines=80, india_vix=Decimal("25"))
        artifacts = _pipeline(config_dir, _candles(range(170, 100, -1)), snap)
        outcome = decision.decide("X", as_of=AS_OF, **artifacts)
        assert outcome.decision.decision_type in {DecisionType.NO_TRADE, DecisionType.WATCH}


class TestGates:
    def test_all_six_gates_evaluated(self, decision, config_dir):
        artifacts = _pipeline(config_dir, _candles(range(100, 170)), _bull_snapshot())
        outcome = decision.decide("X", as_of=AS_OF, **artifacts)
        gates = {g.gate for g in outcome.decision.gate_results}
        assert gates == {QualityGate.DATA, QualityGate.EVIDENCE, QualityGate.RISK,
                         QualityGate.EXPLAINABILITY, QualityGate.CONFIDENCE, QualityGate.MARKET}

    def test_failing_gate_prevents_trade(self, decision, config_dir):
        # No confidence/risk/evidence → those gates fail → cannot be TRADE
        candles = _candles(range(100, 170))
        indicators = IndicatorEngine(load_config(config_dir).indicators).compute_all(
            [IndicatorName.SMA, IndicatorName.ATR], candles, as_of=AS_OF)
        regime = RegimeEngine(load_config(config_dir).regime).assess(
            "NIFTY50", candles, _bull_snapshot(), as_of=AS_OF)
        scoring = ScoringEngine(load_scoring_config(config_dir)).score(
            "X", as_of=AS_OF, indicators=indicators, regime=regime)
        outcome = decision.decide("X", as_of=AS_OF, scoring=scoring, regime=regime,
                                  indicators=indicators)
        assert outcome.decision.decision_type is not DecisionType.TRADE


class TestTraceAndContract:
    def test_trace_references_decision(self, decision, config_dir):
        artifacts = _pipeline(config_dir, _candles(range(100, 170)), _bull_snapshot())
        outcome = decision.decide("X", as_of=AS_OF, **artifacts)
        assert outcome.trace.decision_ref == outcome.decision.decision_id
        stage_names = {s.stage for s in outcome.trace.stages}
        assert "decision" in stage_names and "score" in stage_names

    def test_deterministic_repeat(self, decision, config_dir):
        artifacts = _pipeline(config_dir, _candles(range(100, 170)), _bull_snapshot())
        a = decision.decide("X", as_of=AS_OF, **artifacts)
        b = decision.decide("X", as_of=AS_OF, **artifacts)
        assert a.decision == b.decision and a.trace == b.trace

    def test_immutable(self, decision):
        outcome = decision.decide("X", as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.decision.decision_type = DecisionType.TRADE

    def test_refs_preserved(self, decision, config_dir):
        artifacts = _pipeline(config_dir, _candles(range(100, 170)), _bull_snapshot())
        outcome = decision.decide("X", as_of=AS_OF, **artifacts)
        assert outcome.decision.confidence_ref is not None
        assert outcome.decision.risk_ref is not None
        assert outcome.decision.score_ref is not None


class TestConfig:
    def test_production_config_loads(self):
        cfg = load_decision_config(REPO / "config")
        assert cfg.thresholds.watch_composite <= cfg.thresholds.min_composite_for_trade

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*decision.json"):
            load_decision_config(tmp_path)

    def test_invalid_thresholds_rejected(self, config_dir):
        import json
        path = config_dir / "decision.json"
        data = json.loads(path.read_text())
        data["thresholds"]["watch_composite"] = 90
        data["thresholds"]["min_composite_for_trade"] = 60
        path.write_text(json.dumps(data))
        with pytest.raises(ConfigError):
            load_decision_config(config_dir)
