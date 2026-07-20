"""Indicator Engine tests (M3.2): reference values, boundaries, UNKNOWN,
determinism, immutability, Decimal precision, config."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.indicators import IndicatorEngine, IndicatorName, IndicatorStatus

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def engine(config_dir) -> IndicatorEngine:
    return IndicatorEngine(load_config(config_dir).indicators)


def _candles(closes, *, highs=None, lows=None, volumes=None) -> list[Candle]:
    out = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        hi = Decimal(str(highs[i])) if highs else c + Decimal("1")
        lo = Decimal(str(lows[i])) if lows else c - Decimal("1")
        vol = volumes[i] if volumes else 1000
        out.append(Candle(instrument_id="X", timeframe=Timeframe.D1,
                          ts_open=datetime.combine(start + timedelta(days=i),
                                                   datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                          open=c, high=hi, low=lo, close=c, volume=vol, source="test"))
    return out


class TestSMA:
    def test_exact_value(self, engine):
        # SMA(20) of 1..20 → mean(1..20) = 10.5
        r = engine.compute(IndicatorName.SMA, _candles(range(1, 21)), as_of=AS_OF)
        assert r.status is IndicatorStatus.OK
        assert r.values["value"] == Decimal("10.5")

    def test_constant_series(self, engine):
        r = engine.compute(IndicatorName.SMA, _candles([50] * 25), as_of=AS_OF)
        assert r.values["value"] == Decimal("50")

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.SMA, _candles([1, 2, 3]), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN
        assert r.values == {}


class TestEMA:
    def test_constant_series_equals_constant(self, engine):
        r = engine.compute(IndicatorName.EMA, _candles([42] * 30), as_of=AS_OF)
        assert r.values["value"] == Decimal("42")

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.EMA, _candles([1, 2]), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN


class TestRSI:
    def test_all_gains_is_100(self, engine):
        r = engine.compute(IndicatorName.RSI, _candles(range(1, 40)), as_of=AS_OF)
        assert r.values["value"] == Decimal("100")

    def test_all_losses_is_0(self, engine):
        r = engine.compute(IndicatorName.RSI, _candles(range(40, 1, -1)), as_of=AS_OF)
        assert r.values["value"] == Decimal("0")

    def test_alternating_near_50(self, engine):
        closes = [100 + (1 if i % 2 == 0 else 0) for i in range(40)]
        r = engine.compute(IndicatorName.RSI, _candles(closes), as_of=AS_OF)
        assert Decimal("30") < r.values["value"] < Decimal("70")

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.RSI, _candles(range(1, 10)), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN


class TestATR:
    def test_constant_ohlc_is_zero(self, engine):
        # high == low == close → true range 0 → ATR 0
        flat = [Decimal("100")] * 30
        candles = _candles([100] * 30, highs=flat, lows=flat)
        r = engine.compute(IndicatorName.ATR, candles, as_of=AS_OF)
        assert r.values["value"] == Decimal("0")

    def test_known_range_positive(self, engine):
        candles = _candles([100] * 30, highs=[102] * 30, lows=[98] * 30)
        r = engine.compute(IndicatorName.ATR, candles, as_of=AS_OF)
        assert r.values["value"] > Decimal("0")

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.ATR, _candles([1, 2, 3]), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN


class TestMACD:
    def test_constant_series_is_zero(self, engine):
        r = engine.compute(IndicatorName.MACD, _candles([100] * 60), as_of=AS_OF)
        assert r.values["macd"] == Decimal("0")
        assert r.values["signal"] == Decimal("0")
        assert r.values["histogram"] == Decimal("0")

    def test_rising_series_positive_macd(self, engine):
        r = engine.compute(IndicatorName.MACD, _candles(range(1, 80)), as_of=AS_OF)
        assert r.values["macd"] > Decimal("0")  # fast EMA above slow in an uptrend

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.MACD, _candles(range(1, 20)), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN


class TestADX:
    def test_trending_series_in_range(self, engine):
        r = engine.compute(IndicatorName.ADX, _candles(range(1, 60)), as_of=AS_OF)
        assert r.status is IndicatorStatus.OK
        assert Decimal("0") <= r.values["adx"] <= Decimal("100")
        assert "plus_di" in r.values and "minus_di" in r.values

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.ADX, _candles(range(1, 10)), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN


class TestVolumeMA:
    def test_exact_value(self, engine):
        vols = [100] * 19 + [200]  # 20 candles: nineteen 100s + one 200
        r = engine.compute(IndicatorName.VOLUME_MA, _candles([1] * 20, volumes=vols), as_of=AS_OF)
        assert r.values["value"] == Decimal("105")  # (19*100 + 200)/20

    def test_unknown_insufficient(self, engine):
        r = engine.compute(IndicatorName.VOLUME_MA, _candles([1] * 5), as_of=AS_OF)
        assert r.status is IndicatorStatus.UNKNOWN


class TestEngineContract:
    def test_compute_all(self, engine):
        candles = _candles(range(1, 80))
        results = engine.compute_all(
            [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.MACD], candles, as_of=AS_OF)
        assert set(results) == {IndicatorName.SMA, IndicatorName.RSI, IndicatorName.MACD}

    def test_deterministic_repeat(self, engine):
        candles = _candles(range(1, 80))
        a = engine.compute(IndicatorName.RSI, candles, as_of=AS_OF)
        b = engine.compute(IndicatorName.RSI, candles, as_of=AS_OF)
        assert a == b

    def test_result_immutable(self, engine):
        r = engine.compute(IndicatorName.SMA, _candles(range(1, 21)), as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.status = IndicatorStatus.UNKNOWN

    def test_values_mapping_immutable(self, engine):
        r = engine.compute(IndicatorName.SMA, _candles(range(1, 21)), as_of=AS_OF)
        with pytest.raises(TypeError):
            r.values["value"] = Decimal("0")

    def test_carries_evidence_and_params(self, engine):
        r = engine.compute(IndicatorName.SMA, _candles(range(1, 21)), as_of=AS_OF)
        assert r.evidence.formula and r.evidence.explanation
        assert r.parameters["period"] == 20

    def test_decimal_precision_preserved(self, engine):
        r = engine.compute(IndicatorName.SMA, _candles([Decimal("1.111")] * 20), as_of=AS_OF)
        assert r.values["value"] == Decimal("1.111")


class TestConfig:
    def test_production_config_loads(self):
        cfg = load_config(REPO / "config").indicators
        assert "sma" in cfg.params and "macd" in cfg.params
