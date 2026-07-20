"""Confidence Engine tests (M3.4): dimensions, overall, UNKNOWN propagation,
consistency, determinism, immutability, config."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.confidence import ConfidenceEngine, ConfidenceStatus
from athena.config.loader import (
    load_confidence_config,
    load_config,
    load_scoring_config,
)
from athena.data.validation.reports import (
    Severity,
    ValidationReport,
    ValidationResult,
    ValidationType,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.errors import ConfigError
from athena.evidence import EvidenceAggregationEngine, EvidenceSource
from athena.indicators import IndicatorEngine, IndicatorName
from athena.regime import RegimeEngine
from athena.scoring import ScoringEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def confidence(config_dir) -> ConfidenceEngine:
    return ConfidenceEngine(load_confidence_config(config_dir))


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


def _indicators(config_dir, candles):
    eng = IndicatorEngine(load_config(config_dir).indicators)
    return eng.compute_all(
        [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.ADX,
         IndicatorName.MACD, IndicatorName.VOLUME_MA], candles, as_of=AS_OF)


def _scoring(config_dir, candles, indicators):
    regime = RegimeEngine(load_config(config_dir).regime).assess(
        "NIFTY50", candles,
        MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")}, india_vix=Decimal("15")),
        as_of=AS_OF)
    return ScoringEngine(load_scoring_config(config_dir)).score(
        "X", as_of=AS_OF, indicators=indicators, regime=regime)


def _bundle(config_dir, *, complete=True, validation_passed=True):
    agg = EvidenceAggregationEngine()
    reports = [ValidationReport(
        validation_type=ValidationType.FRESHNESS,
        result=ValidationResult.PASSED if validation_passed else ValidationResult.FAILED,
        severity=Severity.INFO if validation_passed else Severity.ERROR,
        explanation="fresh" if validation_passed else "stale", ts=AS_OF)]
    regime = RegimeEngine(load_config(config_dir).regime).assess(
        "NIFTY50", _candles(range(100, 160)),
        MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")}, india_vix=Decimal("15")),
        as_of=AS_OF)
    required = (EvidenceSource.REGIME,) if complete else (EvidenceSource.REGIME,
                                                          EvidenceSource.UNIVERSE)
    return agg.aggregate(as_of=AS_OF, regime=regime, validation_reports=reports,
                         required_sources=required)


class TestDimensions:
    def test_evidence_completeness_full(self, confidence, config_dir):
        result = confidence.assess(as_of=AS_OF, evidence_bundle=_bundle(config_dir, complete=True))
        dim = result.dimensions["evidence_completeness"]
        assert dim.status is ConfidenceStatus.OK
        assert dim.value == Decimal("100")

    def test_evidence_completeness_partial(self, confidence, config_dir):
        result = confidence.assess(as_of=AS_OF, evidence_bundle=_bundle(config_dir, complete=False))
        assert result.dimensions["evidence_completeness"].value < Decimal("100")

    def test_evidence_completeness_unknown_without_bundle(self, confidence):
        result = confidence.assess(as_of=AS_OF)
        assert result.dimensions["evidence_completeness"].status is ConfidenceStatus.UNKNOWN

    def test_data_freshness_passed_vs_failed(self, confidence, config_dir):
        good = confidence.assess(as_of=AS_OF,
                                 evidence_bundle=_bundle(config_dir, validation_passed=True))
        bad = confidence.assess(as_of=AS_OF,
                                evidence_bundle=_bundle(config_dir, validation_passed=False))
        assert good.dimensions["data_freshness"].value == Decimal("100")
        assert bad.dimensions["data_freshness"].value == Decimal("0")

    def test_indicator_availability(self, confidence, config_dir):
        full = _indicators(config_dir, _candles(range(1, 80)))
        result = confidence.assess(as_of=AS_OF, indicators=full)
        assert result.dimensions["indicator_availability"].value == Decimal("100")

    def test_indicator_availability_partial(self, confidence, config_dir):
        partial = _indicators(config_dir, _candles(range(1, 15)))  # short → some UNKNOWN
        result = confidence.assess(as_of=AS_OF, indicators=partial)
        assert result.dimensions["indicator_availability"].value < Decimal("100")

    def test_cross_engine_agreement(self, confidence, config_dir):
        candles = _candles(range(100, 160))
        scoring = _scoring(config_dir, candles, _indicators(config_dir, candles))
        result = confidence.assess(as_of=AS_OF, scoring=scoring)
        assert result.dimensions["cross_engine_agreement"].status is ConfidenceStatus.OK

    def test_unknown_ratio(self, confidence, config_dir):
        candles = _candles(range(100, 160))
        result = confidence.assess(as_of=AS_OF, indicators=_indicators(config_dir, candles))
        assert result.dimensions["unknown_ratio"].status is ConfidenceStatus.OK

    def test_consistency(self, confidence, config_dir):
        candles = _candles(range(100, 160))
        scoring = _scoring(config_dir, candles, _indicators(config_dir, candles))
        result = confidence.assess(as_of=AS_OF, scoring=scoring)
        assert result.dimensions["consistency"].status is ConfidenceStatus.OK


class TestOverall:
    def test_full_inputs_high_confidence(self, confidence, config_dir):
        candles = _candles(range(100, 160))
        ind = _indicators(config_dir, candles)
        result = confidence.assess(
            as_of=AS_OF, evidence_bundle=_bundle(config_dir),
            scoring=_scoring(config_dir, candles, ind), indicators=ind)
        assert result.overall_status is ConfidenceStatus.OK
        assert result.completeness == Decimal("1")
        assert 0 <= result.overall_value <= 100

    def test_no_inputs_unknown_overall(self, confidence):
        result = confidence.assess(as_of=AS_OF)
        assert result.overall_status is ConfidenceStatus.UNKNOWN
        assert result.overall_value is None
        # dimensions still enumerated even when all unknown
        assert len(result.dimensions) == 6

    def test_unknown_stats(self, confidence, config_dir):
        partial = _indicators(config_dir, _candles(range(1, 15)))
        result = confidence.assess(as_of=AS_OF, indicators=partial)
        assert result.unknown_stats["unknown_indicators"] >= 1


class TestContractAndConfig:
    def test_deterministic_repeat(self, confidence, config_dir):
        candles = _candles(range(100, 160))
        ind = _indicators(config_dir, candles)
        args = dict(as_of=AS_OF, evidence_bundle=_bundle(config_dir),
                    scoring=_scoring(config_dir, candles, ind), indicators=ind)
        assert confidence.assess(**args) == confidence.assess(**args)

    def test_immutable(self, confidence):
        result = confidence.assess(as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.overall_value = Decimal("50")

    def test_every_known_dimension_explained(self, confidence, config_dir):
        candles = _candles(range(100, 160))
        ind = _indicators(config_dir, candles)
        result = confidence.assess(as_of=AS_OF, evidence_bundle=_bundle(config_dir),
                                   scoring=_scoring(config_dir, candles, ind), indicators=ind)
        for dim in result.dimensions.values():
            assert dim.explanation
            if dim.is_known:
                assert dim.contributions

    def test_production_config_loads(self):
        cfg = load_confidence_config(REPO / "config")
        assert sum(cfg.weights.model_dump().values()) == 100

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*confidence.json"):
            load_confidence_config(tmp_path)
