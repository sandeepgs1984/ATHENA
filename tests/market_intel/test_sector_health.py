"""Sector Health Engine tests (M2.3): trend, breadth, momentum, volatility context,
UNKNOWN fallbacks, multiple sectors, determinism, immutability, config."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_sector_health_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.errors import ConfigError
from athena.sector_health import SectorHealthEngine, SectorHealthLabel

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
SECTOR = "NIFTY_BANK"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def engine(config_dir) -> SectorHealthEngine:
    return SectorHealthEngine(load_sector_health_config(config_dir))


def _series(closes, symbol=SECTOR) -> list[Candle]:
    candles = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        candles.append(Candle(instrument_id=symbol, timeframe=Timeframe.D1,
                              ts_open=datetime.combine(start + timedelta(days=i),
                                                       datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                              open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test"))
    return candles


def _dim(result, dimension) -> str:
    return result.assessment.dimensions[dimension]


class TestTrend:
    def test_uptrend(self, engine):
        r = engine.assess(SECTOR, _series(range(100, 140)), as_of=AS_OF)
        assert _dim(r, "trend") == SectorHealthLabel.SECTOR_UPTREND.value

    def test_downtrend(self, engine):
        r = engine.assess(SECTOR, _series(range(140, 100, -1)), as_of=AS_OF)
        assert _dim(r, "trend") == SectorHealthLabel.SECTOR_DOWNTREND.value

    def test_sideways(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF)
        assert _dim(r, "trend") == SectorHealthLabel.SECTOR_SIDEWAYS.value

    def test_trend_unknown(self, engine):
        r = engine.assess(SECTOR, _series(range(100, 110)), as_of=AS_OF)
        assert _dim(r, "trend") == SectorHealthLabel.SECTOR_TREND_UNKNOWN.value


class TestBreadth:
    def test_unknown_without_constituent_data(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF)
        assert _dim(r, "breadth") == SectorHealthLabel.SECTOR_BREADTH_UNKNOWN.value

    def test_strong_when_supplied(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF, constituent_breadth=(8, 2))
        assert _dim(r, "breadth") == SectorHealthLabel.STRONG_SECTOR_BREADTH.value

    def test_weak_when_supplied(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF, constituent_breadth=(2, 8))
        assert _dim(r, "breadth") == SectorHealthLabel.WEAK_SECTOR_BREADTH.value

    def test_mixed_when_supplied(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF, constituent_breadth=(5, 5))
        assert _dim(r, "breadth") == SectorHealthLabel.MIXED_SECTOR_BREADTH.value

    def test_unknown_when_zero_totals(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF, constituent_breadth=(0, 0))
        assert _dim(r, "breadth") == SectorHealthLabel.SECTOR_BREADTH_UNKNOWN.value


class TestMomentum:
    def test_healthy(self, engine):
        r = engine.assess(SECTOR, _series(range(100, 140)), as_of=AS_OF)
        assert _dim(r, "momentum") == SectorHealthLabel.HEALTHY_SECTOR_MOMENTUM.value

    def test_weak(self, engine):
        r = engine.assess(SECTOR, _series(range(140, 100, -1)), as_of=AS_OF)
        assert _dim(r, "momentum") == SectorHealthLabel.WEAK_SECTOR_MOMENTUM.value

    def test_flat(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF)
        assert _dim(r, "momentum") == SectorHealthLabel.FLAT_SECTOR_MOMENTUM.value

    def test_unknown(self, engine):
        r = engine.assess(SECTOR, _series([100] * 5), as_of=AS_OF)
        assert _dim(r, "momentum") == SectorHealthLabel.SECTOR_MOMENTUM_UNKNOWN.value


class TestVolatility:
    def test_calm_flat_series(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF)
        assert _dim(r, "volatility") == SectorHealthLabel.SECTOR_VOLATILITY_CALM.value

    def test_elevated_volatile_series(self, engine):
        # Large alternating swings → high realized volatility
        volatile = [100 + (10 if i % 2 == 0 else -10) for i in range(40)]
        r = engine.assess(SECTOR, _series(volatile), as_of=AS_OF)
        assert _dim(r, "volatility") == SectorHealthLabel.SECTOR_VOLATILITY_ELEVATED.value

    def test_unknown_insufficient(self, engine):
        r = engine.assess(SECTOR, _series([100] * 5), as_of=AS_OF)
        assert _dim(r, "volatility") == SectorHealthLabel.SECTOR_VOLATILITY_UNKNOWN.value


class TestMultipleSectorsAndDeterminism:
    def test_assess_many(self, engine):
        results = engine.assess_many(
            {"NIFTY_BANK": _series(range(100, 140)),
             "NIFTY_IT": _series(range(140, 100, -1))},
            as_of=AS_OF,
            constituent_breadth={"NIFTY_BANK": (7, 3)})
        assert set(results) == {"NIFTY_BANK", "NIFTY_IT"}
        assert results["NIFTY_BANK"].assessment.dimensions["trend"] == \
            SectorHealthLabel.SECTOR_UPTREND.value
        assert results["NIFTY_IT"].assessment.dimensions["trend"] == \
            SectorHealthLabel.SECTOR_DOWNTREND.value
        # breadth supplied only for BANK; IT reports UNKNOWN honestly
        assert results["NIFTY_IT"].assessment.dimensions["breadth"] == \
            SectorHealthLabel.SECTOR_BREADTH_UNKNOWN.value

    def test_four_dimensions_and_evidence(self, engine):
        r = engine.assess(SECTOR, _series(range(100, 140)), as_of=AS_OF, constituent_breadth=(6, 4))
        assert set(r.assessment.dimensions) == {"trend", "breadth", "momentum", "volatility"}
        assert len(r.evidence) == 4
        assert r.assessment.sector == SECTOR

    def test_deterministic_repeat(self, engine):
        a = engine.assess(SECTOR, _series(range(100, 140)), as_of=AS_OF, constituent_breadth=(6, 4))
        b = engine.assess(SECTOR, _series(range(100, 140)), as_of=AS_OF, constituent_breadth=(6, 4))
        assert a.assessment == b.assessment and a.evidence == b.evidence

    def test_evidence_immutable(self, engine):
        r = engine.assess(SECTOR, _series([100] * 40), as_of=AS_OF)
        with pytest.raises(TypeError):
            r.evidence[0].inputs["ma_fast"] = "9"


class TestConfig:
    def test_loads_production_config(self):
        cfg = load_sector_health_config(REPO / "config")
        assert cfg.trend.ma_fast < cfg.trend.ma_slow

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*sector_health.json"):
            load_sector_health_config(tmp_path)

    def test_invalid_volatility_bands_rejected(self, config_dir):
        (config_dir / "sector_health.json").write_text(
            '{"trend":{"ma_fast":10,"ma_slow":30},'
            '"breadth":{"strong_ratio":0.6,"weak_ratio":0.4},'
            '"momentum":{"period":10,"healthy_pct":3.0},'
            '"volatility":{"window":20,"calm_pct":3.0,"elevated_pct":1.0}}', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_sector_health_config(config_dir)
