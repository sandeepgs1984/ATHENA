"""Decision Reporting tests (M3.7): report faithfulness across outcomes, UNKNOWN
display, determinism, immutability, machine serialization, reasoning preservation."""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
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
from athena.domain.enums import DecisionType, Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.evidence import EvidenceAggregationEngine, EvidenceSource
from athena.indicators import IndicatorEngine, IndicatorName
from athena.market_health import MarketHealthEngine
from athena.regime import RegimeEngine
from athena.reporting import DecisionReportingEngine
from athena.risk import RiskEngine
from athena.scoring import ScoringEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)


@pytest.fixture()
def reporting() -> DecisionReportingEngine:
    return DecisionReportingEngine()


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


def _artifacts(config_dir, closes, snapshot):
    indicators = IndicatorEngine(load_config(config_dir).indicators).compute_all(
        [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.ADX,
         IndicatorName.MACD, IndicatorName.ATR, IndicatorName.VOLUME_MA],
        _candles(closes), as_of=AS_OF)
    regime = RegimeEngine(load_config(config_dir).regime).assess(
        "NIFTY50", _candles(closes), snapshot, as_of=AS_OF)
    mh = MarketHealthEngine(load_market_health_config(config_dir)).assess(
        "NIFTY50", _candles(closes), snapshot, as_of=AS_OF)
    scoring = ScoringEngine(load_scoring_config(config_dir)).score(
        "X", as_of=AS_OF, indicators=indicators, regime=regime, market_health=mh)
    confidence = ConfidenceEngine(load_confidence_config(config_dir)).assess(
        as_of=AS_OF, scoring=scoring, indicators=indicators)
    risk = RiskEngine(load_risk_assessment_config(config_dir)).assess(
        "X", as_of=AS_OF, regime=regime, market_health=mh, indicators=indicators)
    bundle = EvidenceAggregationEngine().aggregate(
        as_of=AS_OF, regime=regime, market_health=mh, required_sources=(EvidenceSource.REGIME,))
    outcome = DecisionEngine(load_decision_config(config_dir)).decide(
        "X", as_of=AS_OF, scoring=scoring, confidence=confidence, risk=risk,
        evidence_bundle=bundle, regime=regime, indicators=indicators, market_health=mh)
    return dict(outcome=outcome, scoring=scoring, confidence=confidence, risk=risk,
                evidence_bundle=bundle, indicators=indicators, regime=regime,
                market_health=mh)


def _bull():
    return MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                          breadth_advances=80, breadth_declines=20, india_vix=Decimal("12"))


class TestReportFaithfulness:
    def test_trade_report(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        report = reporting.report(**arts)
        assert report.decision_type == arts["outcome"].decision.decision_type.value
        machine = report.to_dict()
        assert machine["decision"]["type"] == report.decision_type
        assert len(machine["gates"]) == 6
        if report.decision_type == "TRADE":
            assert machine["trade_plan"] is not None
            assert "TRADE PLAN" in report.to_text()

    def test_no_trade_report(self, reporting, config_dir):
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=20, breadth_declines=80, india_vix=Decimal("25"))
        arts = _artifacts(config_dir, range(170, 100, -1), snap)
        report = reporting.report(**arts)
        assert report.decision_type in {"NO_TRADE", "WATCH"}
        assert report.to_dict()["trade_plan"] is None

    def test_insufficient_data_report(self, reporting, config_dir):
        outcome = DecisionEngine(load_decision_config(config_dir)).decide("X", as_of=AS_OF)
        report = reporting.report(outcome)
        assert report.decision_type == DecisionType.INSUFFICIENT_DATA.value
        machine = report.to_dict()
        # UNKNOWN shown explicitly for absent artifacts
        assert machine["score"]["status"] == "UNKNOWN"
        assert machine["confidence"]["status"] == "UNKNOWN"
        assert machine["risk"]["status"] == "UNKNOWN"
        assert machine["evidence"]["status"] == "UNKNOWN"
        assert machine["regime"]["status"] == "UNKNOWN"
        assert machine["market_health"]["status"] == "UNKNOWN"
        assert "UNKNOWN" in report.to_text()


class TestReasoningPreservation:
    def test_all_gates_present(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        gates = {g["gate"] for g in reporting.report(**arts).to_dict()["gates"]}
        assert gates == {"DATA", "EVIDENCE", "RISK", "EXPLAINABILITY", "CONFIDENCE", "MARKET"}

    def test_reasoning_stages_preserved(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        report = reporting.report(**arts)
        n_stages = len(arts["outcome"].trace.stages)
        assert len(report.to_dict()["reasoning"]["stages"]) == n_stages

    def test_score_components_preserved(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        score = reporting.report(**arts).to_dict()["score"]
        comps = score["components"]
        assert len(comps) == 6  # all scoring components represented
        assert score["explanation"]
        assert all("explanation" in component for component in comps)
        assert all("contributions" in component for component in comps)

    def test_confidence_and_risk_rationale_preserved(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        machine = reporting.report(**arts).to_dict()
        for name in ("confidence", "risk"):
            block = machine[name]
            assert block["explanation"]
            assert block["dimensions"]
            assert all("explanation" in dimension for dimension in block["dimensions"])
            assert all("contributions" in dimension for dimension in block["dimensions"])

    def test_indicators_listed(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        names = {i["name"] for i in reporting.report(**arts).to_dict()["indicators"]}
        assert "SMA" in names and "RSI" in names


class TestRegimeMarketHealthPersistence:
    """M-D4: regime and market-health context, persisted alongside score/confidence/risk."""

    def test_regime_persisted(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        machine = reporting.report(**arts).to_dict()
        reg = machine["regime"]
        assert reg["status"] == "ASSESSED"
        assert reg["assessment_id"] == arts["regime"].assessment.assessment_id
        assert reg["labels"] == list(arts["regime"].assessment.labels)
        assert reg["explanation"]
        assert reg["evidence"]
        assert all("explanation" in item for item in reg["evidence"])

    def test_market_health_persisted(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        machine = reporting.report(**arts).to_dict()
        mh = machine["market_health"]
        assert mh["status"] == "ASSESSED"
        assert mh["assessment_id"] == arts["market_health"].assessment.assessment_id
        assert mh["dimensions"] == dict(arts["market_health"].assessment.dimensions)
        assert mh["explanation"]
        assert mh["evidence"]

    def test_regime_market_health_in_text(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        text = reporting.report(**arts).to_text()
        assert "REGIME" in text
        assert "MARKET HEALTH" in text


class TestContract:
    def test_machine_is_json_serializable(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        report = reporting.report(**arts)
        # round-trips through JSON without error
        assert json.loads(report.to_json())["decision"]["id"] == report.decision_id

    def test_deterministic_repeat(self, reporting, config_dir):
        arts = _artifacts(config_dir, range(100, 170), _bull())
        a = reporting.report(**arts)
        b = reporting.report(**arts)
        assert a.to_json() == b.to_json()
        assert a.to_text() == b.to_text()

    def test_immutable(self, reporting, config_dir):
        outcome = DecisionEngine(load_decision_config(config_dir)).decide("X", as_of=AS_OF)
        report = reporting.report(outcome)
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.text = "tampered"

    def test_to_dict_is_a_copy(self, reporting, config_dir):
        outcome = DecisionEngine(load_decision_config(config_dir)).decide("X", as_of=AS_OF)
        report = reporting.report(outcome)
        d = report.to_dict()
        d["decision"]["type"] = "HACKED"
        assert report.to_dict()["decision"]["type"] != "HACKED"  # original untouched
