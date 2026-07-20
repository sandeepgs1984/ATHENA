"""Regime Engine tests (M2.1): trend, volatility, gap dimensions, insufficient
data, determinism, immutability. Deterministic synthetic index series."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.regime import RegimeEngine, RegimeLabel

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
IDX = "NIFTY50"


@pytest.fixture()
def engine(config_dir) -> RegimeEngine:
    return RegimeEngine(load_config(config_dir).regime)


def _series(closes, *, opens=None) -> list[Candle]:
    """Build a daily index series; one candle per prior day, oldest first."""
    candles = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        o = Decimal(str(opens[i])) if opens else c
        hi = max(o, c) + Decimal("1")
        lo = min(o, c) - Decimal("1")
        candles.append(Candle(instrument_id=IDX, timeframe=Timeframe.D1,
                              ts_open=datetime.combine(start + timedelta(days=i),
                                                       datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                              open=o, high=hi, low=lo, close=c, volume=1000, source="test"))
    return candles


def _snapshot(vix) -> MarketSnapshot:
    return MarketSnapshot(ts=AS_OF, indices={IDX: Decimal("25000")},
                          india_vix=Decimal(str(vix)) if vix is not None else None)


def _label(result, dimension_prefix) -> str:
    return next(e.outcome.value for e in result.evidence if e.dimension == dimension_prefix)


class TestTrend:
    def test_bull_trend_rising_series(self, engine):
        # 60 rising closes → fast SMA > slow SMA, last close above slow SMA
        result = engine.assess(IDX, _series(range(100, 160)), _snapshot(15), as_of=AS_OF)
        assert _label(result, "trend") == RegimeLabel.BULL_TREND.value

    def test_bear_trend_falling_series(self, engine):
        result = engine.assess(IDX, _series(range(160, 100, -1)), _snapshot(15), as_of=AS_OF)
        assert _label(result, "trend") == RegimeLabel.BEAR_TREND.value

    def test_sideways_flat_series(self, engine):
        # Flat series: fast SMA == slow SMA → neither bull nor bear
        result = engine.assess(IDX, _series([100] * 60), _snapshot(15), as_of=AS_OF)
        assert _label(result, "trend") == RegimeLabel.SIDEWAYS.value

    def test_trend_unknown_insufficient_history(self, engine):
        result = engine.assess(IDX, _series(range(100, 110)), _snapshot(15), as_of=AS_OF)
        assert _label(result, "trend") == RegimeLabel.TREND_UNKNOWN.value


class TestVolatility:
    def test_high_volatility(self, engine):
        result = engine.assess(IDX, _series([100] * 60), _snapshot(25), as_of=AS_OF)
        assert _label(result, "volatility") == RegimeLabel.HIGH_VOLATILITY.value

    def test_low_volatility(self, engine):
        result = engine.assess(IDX, _series([100] * 60), _snapshot(10), as_of=AS_OF)
        assert _label(result, "volatility") == RegimeLabel.LOW_VOLATILITY.value

    def test_normal_volatility(self, engine):
        result = engine.assess(IDX, _series([100] * 60), _snapshot(15), as_of=AS_OF)
        assert _label(result, "volatility") == RegimeLabel.NORMAL_VOLATILITY.value

    def test_volatility_unknown_without_vix(self, engine):
        result = engine.assess(IDX, _series([100] * 60), _snapshot(None), as_of=AS_OF)
        assert _label(result, "volatility") == RegimeLabel.VOLATILITY_UNKNOWN.value

    def test_volatility_unknown_without_snapshot(self, engine):
        result = engine.assess(IDX, _series([100] * 60), None, as_of=AS_OF)
        assert _label(result, "volatility") == RegimeLabel.VOLATILITY_UNKNOWN.value


class TestGap:
    def test_gap_up(self, engine):
        # last open 110 vs prior close 100 = +10% >> 0.5% threshold
        series = _series([100, 100], opens=[100, 110])
        result = engine.assess(IDX, series, _snapshot(15), as_of=AS_OF)
        assert _label(result, "gap") == RegimeLabel.GAP_UP.value

    def test_gap_down(self, engine):
        series = _series([100, 100], opens=[100, 90])
        result = engine.assess(IDX, series, _snapshot(15), as_of=AS_OF)
        assert _label(result, "gap") == RegimeLabel.GAP_DOWN.value

    def test_no_gap(self, engine):
        series = _series([100, 100], opens=[100, 100])
        result = engine.assess(IDX, series, _snapshot(15), as_of=AS_OF)
        assert _label(result, "gap") == RegimeLabel.NO_GAP.value

    def test_gap_unknown_single_candle(self, engine):
        result = engine.assess(IDX, _series([100]), _snapshot(15), as_of=AS_OF)
        assert _label(result, "gap") == RegimeLabel.GAP_UNKNOWN.value


class TestAssessmentAndDeterminism:
    def test_assessment_has_three_labels_and_evidence(self, engine):
        result = engine.assess(IDX, _series(range(100, 160)), _snapshot(25), as_of=AS_OF)
        assert len(result.assessment.labels) == 3
        assert len(result.evidence) == 3
        assert result.assessment.evidence_ids == tuple(e.evidence_id for e in result.evidence)
        assert result.assessment.explanation

    def test_deterministic_repeat(self, engine):
        a = engine.assess(IDX, _series(range(100, 160)), _snapshot(25), as_of=AS_OF)
        b = engine.assess(IDX, _series(range(100, 160)), _snapshot(25), as_of=AS_OF)
        assert a.assessment == b.assessment
        assert a.evidence == b.evidence

    def test_evidence_is_immutable(self, engine):
        result = engine.assess(IDX, _series([100] * 60), _snapshot(15), as_of=AS_OF)
        with pytest.raises(TypeError):
            result.evidence[0].inputs["fast_sma"] = "999"

    def test_descriptive_only_no_recommendation_fields(self, engine):
        # Regime output must be purely descriptive: labels + evidence + explanation.
        result = engine.assess(IDX, _series(range(100, 160)), _snapshot(15), as_of=AS_OF)
        assert set(vars(result.assessment).keys() if hasattr(result.assessment, "__dict__")
                   else result.assessment.__slots__) == {
            "assessment_id", "ts", "labels", "evidence_ids", "explanation"}
