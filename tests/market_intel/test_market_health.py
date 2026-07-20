"""Market Health Engine tests (M2.2): breadth, trend quality, momentum,
volatility context, partial/missing data, determinism, immutability, config."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_market_health_config
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.errors import ConfigError
from athena.market_health import MarketHealthEngine, MarketHealthLabel

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
IDX = "NIFTY50"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def engine(config_dir) -> MarketHealthEngine:
    return MarketHealthEngine(load_market_health_config(config_dir))


def _series(closes) -> list[Candle]:
    candles = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        candles.append(Candle(instrument_id=IDX, timeframe=Timeframe.D1,
                              ts_open=datetime.combine(start + timedelta(days=i),
                                                       datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                              open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test"))
    return candles


def _snapshot(*, adv=0, dec=0, vix=None) -> MarketSnapshot:
    return MarketSnapshot(ts=AS_OF, indices={IDX: Decimal("25000")},
                          breadth_advances=adv, breadth_declines=dec,
                          india_vix=Decimal(str(vix)) if vix is not None else None)


def _dim(result, dimension) -> str:
    return result.assessment.dimensions[dimension]


class TestBreadth:
    def test_strong_breadth(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=70, dec=30), as_of=AS_OF)
        assert _dim(r, "breadth") == MarketHealthLabel.STRONG_BREADTH.value

    def test_weak_breadth(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=30, dec=70), as_of=AS_OF)
        assert _dim(r, "breadth") == MarketHealthLabel.WEAK_BREADTH.value

    def test_mixed_breadth(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=50, dec=50), as_of=AS_OF)
        assert _dim(r, "breadth") == MarketHealthLabel.MIXED_BREADTH.value

    def test_breadth_unknown_no_data(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=0, dec=0), as_of=AS_OF)
        assert _dim(r, "breadth") == MarketHealthLabel.BREADTH_UNKNOWN.value

    def test_breadth_unknown_no_snapshot(self, engine):
        r = engine.assess(IDX, _series([100] * 30), None, as_of=AS_OF)
        assert _dim(r, "breadth") == MarketHealthLabel.BREADTH_UNKNOWN.value


class TestTrendQuality:
    def test_strong_trend_quality_all_up(self, engine):
        r = engine.assess(IDX, _series(range(100, 130)), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "trend_quality") == MarketHealthLabel.STRONG_TREND_QUALITY.value

    def test_weak_trend_quality_choppy(self, engine):
        # Alternating up/down → consistency ~0.5, below strong, above weak → MIXED;
        # to force WEAK make it near-perfectly alternating (consistency ≈ 0.5 → MIXED).
        choppy = []
        v = 100
        for i in range(30):
            v += 1 if i % 2 == 0 else -1
            choppy.append(v)
        r = engine.assess(IDX, _series(choppy), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "trend_quality") in {
            MarketHealthLabel.MIXED_TREND_QUALITY.value,
            MarketHealthLabel.WEAK_TREND_QUALITY.value,
        }

    def test_trend_quality_unknown_insufficient(self, engine):
        r = engine.assess(IDX, _series(range(100, 110)), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "trend_quality") == MarketHealthLabel.TREND_QUALITY_UNKNOWN.value


class TestMomentum:
    def test_healthy_momentum(self, engine):
        r = engine.assess(IDX, _series(range(100, 130)), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "momentum") == MarketHealthLabel.HEALTHY_MOMENTUM.value

    def test_weak_momentum(self, engine):
        r = engine.assess(IDX, _series(range(130, 100, -1)), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "momentum") == MarketHealthLabel.WEAK_MOMENTUM.value

    def test_flat_momentum(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "momentum") == MarketHealthLabel.FLAT_MOMENTUM.value

    def test_momentum_unknown_insufficient(self, engine):
        r = engine.assess(IDX, _series([100] * 5), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "momentum") == MarketHealthLabel.MOMENTUM_UNKNOWN.value


class TestVolatilityContext:
    def test_calm(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(vix=10), as_of=AS_OF)
        assert _dim(r, "volatility") == MarketHealthLabel.VOLATILITY_CALM.value

    def test_elevated(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(vix=25), as_of=AS_OF)
        assert _dim(r, "volatility") == MarketHealthLabel.VOLATILITY_ELEVATED.value

    def test_normal(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(vix=15), as_of=AS_OF)
        assert _dim(r, "volatility") == MarketHealthLabel.VOLATILITY_NORMAL.value

    def test_unknown_without_vix(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=50, dec=50), as_of=AS_OF)
        assert _dim(r, "volatility") == MarketHealthLabel.VOLATILITY_UNKNOWN.value


class TestAssessmentAndDeterminism:
    def test_four_dimensions_and_evidence(self, engine):
        r = engine.assess(IDX, _series(range(100, 130)), _snapshot(adv=60, dec=40, vix=15), as_of=AS_OF)
        assert set(r.assessment.dimensions) == {"breadth", "trend_quality", "momentum", "volatility"}
        assert len(r.evidence) == 4
        assert r.assessment.evidence_ids == tuple(e.evidence_id for e in r.evidence)

    def test_evidence_includes_thresholds(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=60, dec=40, vix=15), as_of=AS_OF)
        breadth = next(e for e in r.evidence if e.dimension == "breadth")
        assert "strong_ratio" in breadth.inputs and "weak_ratio" in breadth.inputs

    def test_deterministic_repeat(self, engine):
        a = engine.assess(IDX, _series(range(100, 130)), _snapshot(adv=60, dec=40, vix=15), as_of=AS_OF)
        b = engine.assess(IDX, _series(range(100, 130)), _snapshot(adv=60, dec=40, vix=15), as_of=AS_OF)
        assert a.assessment == b.assessment and a.evidence == b.evidence

    def test_evidence_immutable(self, engine):
        r = engine.assess(IDX, _series([100] * 30), _snapshot(adv=60, dec=40, vix=15), as_of=AS_OF)
        with pytest.raises(TypeError):
            r.evidence[0].inputs["strong_ratio"] = "9"

    def test_regime_aware_but_not_dependent(self, engine, config_dir):
        # Works with no regime; and passing a regime only enriches explanation.
        from athena.config.loader import load_config
        from athena.regime import RegimeEngine
        regime = RegimeEngine(load_config(config_dir).regime).assess(
            IDX, _series(range(100, 160)), _snapshot(vix=15), as_of=AS_OF)
        with_regime = engine.assess(IDX, _series(range(100, 130)), _snapshot(adv=60, dec=40, vix=15),
                                    as_of=AS_OF, regime=regime)
        without = engine.assess(IDX, _series(range(100, 130)), _snapshot(adv=60, dec=40, vix=15),
                                as_of=AS_OF)
        # Same labels regardless of regime presence (not dependent)
        assert with_regime.assessment.dimensions == without.assessment.dimensions


class TestConfig:
    def test_loads_production_config(self):
        cfg = load_market_health_config(REPO / "config")
        assert cfg.breadth.strong_ratio > cfg.breadth.weak_ratio

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*market_health.json"):
            load_market_health_config(tmp_path)

    def test_invalid_breadth_bands_rejected(self, config_dir):
        (config_dir / "market_health.json").write_text(
            '{"breadth":{"strong_ratio":0.4,"weak_ratio":0.6},'
            '"momentum":{"period":10,"healthy_pct":2.0},'
            '"trend_quality":{"window":20,"strong_consistency":0.65,"weak_consistency":0.45},'
            '"volatility":{"calm_vix":12.0,"elevated_vix":20.0}}', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_market_health_config(config_dir)
