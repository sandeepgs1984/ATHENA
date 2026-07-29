"""Scoring Engine tests (M3.3): component scoring, composite assembly, UNKNOWN
propagation, missing inputs, contribution traces, determinism, immutability, config."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import (
    load_config,
    load_market_health_config,
    load_scoring_config,
    load_sector_health_config,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, MarketSnapshot
from athena.errors import ConfigError
from athena.indicators import IndicatorEngine, IndicatorName
from athena.indicators.models import IndicatorEvidence, IndicatorResult, IndicatorStatus
from athena.market_health import MarketHealthEngine
from athena.regime import RegimeEngine
from athena.scoring import ScoreStatus, ScoringEngine
from athena.sector_health import SectorHealthEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
REPO = Path(__file__).resolve().parents[2]


def _ind(name: IndicatorName, values: dict[str, Decimal]) -> IndicatorResult:
    """Minimal OK IndicatorResult for unit tests that need exact input values."""
    return IndicatorResult(
        name=name,
        status=IndicatorStatus.OK,
        parameters={},
        window_used=14,
        values=values,
        evidence=IndicatorEvidence(formula="test", inputs={}, explanation="test fixture"),
        ts=AS_OF,
    )


@pytest.fixture()
def scoring(config_dir) -> ScoringEngine:
    return ScoringEngine(load_scoring_config(config_dir))


@pytest.fixture()
def indicator_engine(config_dir) -> IndicatorEngine:
    return IndicatorEngine(load_config(config_dir).indicators)


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


def _indicators(engine, candles):
    return engine.compute_all(
        [IndicatorName.SMA, IndicatorName.RSI, IndicatorName.ADX,
         IndicatorName.MACD, IndicatorName.VOLUME_MA], candles, as_of=AS_OF)


def _regime(config_dir, candles, vix=15):
    snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                          india_vix=Decimal(str(vix)))
    return RegimeEngine(load_config(config_dir).regime).assess("NIFTY50", candles, snap, as_of=AS_OF)


class TestComponents:
    def test_trend_scored_from_regime(self, scoring, config_dir, indicator_engine):
        candles = _candles(range(100, 160))  # rising → BULL_TREND
        result = scoring.score("X", as_of=AS_OF, indicators=_indicators(indicator_engine, candles),
                               regime=_regime(config_dir, candles))
        trend = result.components["trend"]
        assert trend.status is ScoreStatus.OK
        assert trend.value >= Decimal("80")  # BULL base 80 (+ possible ADX bonus)
        assert any(c.source == "regime:trend" for c in trend.contributions)

    def test_trend_unknown_without_regime(self, scoring):
        result = scoring.score("X", as_of=AS_OF)
        assert result.components["trend"].status is ScoreStatus.UNKNOWN

    def test_momentum_from_rsi(self, scoring, indicator_engine):
        candles = _candles(range(1, 60))  # strong uptrend → high RSI
        result = scoring.score("X", as_of=AS_OF, indicators=_indicators(indicator_engine, candles))
        mom = result.components["momentum"]
        assert mom.status is ScoreStatus.OK
        assert mom.value == Decimal("80")  # RSI 100 → strong_points

    def test_momentum_unknown_without_rsi(self, scoring):
        result = scoring.score("X", as_of=AS_OF, indicators={})
        assert result.components["momentum"].status is ScoreStatus.UNKNOWN

    def test_market_quality_from_health(self, scoring, config_dir, indicator_engine):
        candles = _candles(range(100, 140))
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=70, breadth_declines=30, india_vix=Decimal("15"))
        mh = MarketHealthEngine(load_market_health_config(config_dir)).assess(
            "NIFTY50", candles, snap, as_of=AS_OF)
        result = scoring.score("X", as_of=AS_OF, market_health=mh)
        mq = result.components["market_quality"]
        assert mq.status is ScoreStatus.OK
        assert len(mq.contributions) >= 1

    def test_sector_quality_from_health(self, scoring, config_dir):
        sh = SectorHealthEngine(load_sector_health_config(config_dir)).assess(
            "NIFTY_BANK", _candles(range(100, 140)), as_of=AS_OF, constituent_breadth=(7, 3))
        result = scoring.score("X", as_of=AS_OF, sector_health=sh)
        assert result.components["sector_quality"].status is ScoreStatus.OK

    def test_liquidity_high_and_low(self, scoring, indicator_engine):
        high = _indicators(indicator_engine, _candles(range(1, 40), volume=1_000_000))
        low = _indicators(indicator_engine, _candles(range(1, 40), volume=1000))
        r_high = scoring.score("X", as_of=AS_OF, indicators=high)
        r_low = scoring.score("X", as_of=AS_OF, indicators=low)
        assert r_high.components["liquidity"].value == Decimal("70")
        assert r_low.components["liquidity"].value == Decimal("30")

    def test_technical_structure_above_ma(self, scoring, indicator_engine):
        candles = _candles(range(1, 60))  # rising → last close above SMA
        result = scoring.score("X", as_of=AS_OF, indicators=_indicators(indicator_engine, candles))
        ts = result.components["technical_structure"]
        assert ts.status is ScoreStatus.OK
        assert ts.value >= Decimal("70")


class TestContinuousScoringAnchors:
    """SD-4: ramps must reproduce the pre-ramp anchors exactly."""

    def test_momentum_anchors_at_weak_mid_strong(self, scoring):
        cfg = scoring._config.rsi
        for rsi_val, expected in (
            (Decimal(str(cfg.weak)), Decimal(cfg.weak_points)),
            (Decimal(str((cfg.weak + cfg.strong) / 2)), Decimal(cfg.mid_points)),
            (Decimal(str(cfg.strong)), Decimal(cfg.strong_points)),
            (Decimal("0"), Decimal(cfg.weak_points)),    # below band
            (Decimal("100"), Decimal(cfg.strong_points)),  # above band
        ):
            result = scoring.score(
                "X", as_of=AS_OF, indicators={IndicatorName.RSI: _ind(IndicatorName.RSI, {"value": rsi_val})}
            )
            assert result.components["momentum"].value == expected, (
                f"RSI {rsi_val} → {result.components['momentum'].value}, expected {expected}"
            )

    def test_momentum_ramps_inside_band(self, scoring):
        # Halfway between mid and strong: RSI 55 → 65 pts under the production ramp.
        result = scoring.score(
            "X", as_of=AS_OF,
            indicators={IndicatorName.RSI: _ind(IndicatorName.RSI, {"value": Decimal("55")})},
        )
        assert result.components["momentum"].value == Decimal("65")

    def test_liquidity_anchors_at_floor_and_min(self, scoring):
        cfg = scoring._config.liquidity
        floor = Decimal(cfg.min_volume_ma)
        for vma, expected in (
            (floor * Decimal(str(cfg.low_volume_floor_ratio)), Decimal(cfg.low_points)),
            (floor, Decimal(cfg.ok_points)),
            (floor * Decimal("2"), Decimal(cfg.ok_points)),  # above min
            (floor * Decimal("0.1"), Decimal(cfg.low_points)),  # below floor
        ):
            result = scoring.score(
                "X", as_of=AS_OF,
                indicators={IndicatorName.VOLUME_MA: _ind(IndicatorName.VOLUME_MA, {"value": vma})},
            )
            assert result.components["liquidity"].value == expected, (
                f"Volume MA {vma} → {result.components['liquidity'].value}, expected {expected}"
            )

    def test_liquidity_ramps_just_under_min(self, scoring):
        # 0.5% under the floor used to cliff to low_points (30); now ~69.6.
        result = scoring.score(
            "X", as_of=AS_OF,
            indicators={
                IndicatorName.VOLUME_MA: _ind(
                    IndicatorName.VOLUME_MA, {"value": Decimal("497500")}
                )
            },
        )
        pts = result.components["liquidity"].value
        assert pts is not None
        assert Decimal("69") < pts < Decimal("70")

    def test_adx_bonus_anchors(self, scoring, config_dir):
        candles = _candles(range(100, 160))  # BULL_TREND base 80
        regime = _regime(config_dir, candles)
        cfg = scoring._config.adx
        base = Decimal("80")  # BULL_TREND label points
        for adx_val, expected_bonus in (
            (Decimal(str(cfg.weak)), Decimal(0)),
            (Decimal(str(cfg.strong)), Decimal(cfg.bonus)),
            (Decimal("5"), Decimal(0)),   # below weak
            (Decimal("40"), Decimal(cfg.bonus)),  # above strong
        ):
            result = scoring.score(
                "X", as_of=AS_OF, regime=regime,
                indicators={IndicatorName.ADX: _ind(IndicatorName.ADX, {"adx": adx_val})},
            )
            assert result.components["trend"].value == base + expected_bonus, (
                f"ADX {adx_val} → trend {result.components['trend'].value}, "
                f"expected {base + expected_bonus}"
            )

    def test_adx_bonus_ramps_mid_band(self, scoring, config_dir):
        candles = _candles(range(100, 160))
        regime = _regime(config_dir, candles)
        # Midway ADX 20 on a 15→25 / 0→10 ramp → +5.
        result = scoring.score(
            "X", as_of=AS_OF, regime=regime,
            indicators={IndicatorName.ADX: _ind(IndicatorName.ADX, {"adx": Decimal("20")})},
        )
        assert result.components["trend"].value == Decimal("85")


class TestComposite:
    def test_composite_full_inputs(self, scoring, config_dir, indicator_engine):
        candles = _candles(range(100, 160))
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=70, breadth_declines=30, india_vix=Decimal("15"))
        mh = MarketHealthEngine(load_market_health_config(config_dir)).assess(
            "NIFTY50", candles, snap, as_of=AS_OF)
        sh = SectorHealthEngine(load_sector_health_config(config_dir)).assess(
            "NIFTY_BANK", candles, as_of=AS_OF, constituent_breadth=(7, 3))
        result = scoring.score("X", as_of=AS_OF, indicators=_indicators(indicator_engine, candles),
                               regime=_regime(config_dir, candles), market_health=mh, sector_health=sh)
        comp = result.composite
        assert comp.status is ScoreStatus.OK
        assert comp.completeness == Decimal("1")
        assert len(comp.breakdown) == 6
        assert 0 <= comp.value <= 100

    def test_composite_partial_completeness(self, scoring, indicator_engine):
        # Only indicators → momentum, liquidity, technical_structure known
        candles = _candles(range(1, 60))
        result = scoring.score("X", as_of=AS_OF, indicators=_indicators(indicator_engine, candles))
        comp = result.composite
        assert comp.status is ScoreStatus.OK
        assert Decimal("0") < comp.completeness < Decimal("1")

    def test_composite_unknown_when_nothing(self, scoring):
        result = scoring.score("X", as_of=AS_OF)
        assert result.composite.status is ScoreStatus.UNKNOWN
        assert result.composite.value is None
        assert len(result.composite.breakdown) == 6  # breakdown retained even when unknown


class TestContractAndDeterminism:
    def test_deterministic_repeat(self, scoring, config_dir, indicator_engine):
        candles = _candles(range(100, 160))
        ind = _indicators(indicator_engine, candles)
        reg = _regime(config_dir, candles)
        a = scoring.score("X", as_of=AS_OF, indicators=ind, regime=reg)
        b = scoring.score("X", as_of=AS_OF, indicators=ind, regime=reg)
        assert a == b

    def test_result_immutable(self, scoring):
        result = scoring.score("X", as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.instrument_id = "Y"

    def test_every_known_score_has_contribution_trace(self, scoring, config_dir, indicator_engine):
        candles = _candles(range(100, 160))
        result = scoring.score("X", as_of=AS_OF, indicators=_indicators(indicator_engine, candles),
                               regime=_regime(config_dir, candles))
        for comp in result.components.values():
            if comp.is_known:
                assert comp.contributions  # no known score without a trace

    def test_no_recommendation_fields(self, scoring):
        # Scores are intermediate: components + composite only, no buy/sell/action.
        result = scoring.score("X", as_of=AS_OF)
        assert set(result.__slots__) == {"instrument_id", "ts", "components", "composite"}


class TestConfig:
    def test_production_config_loads(self):
        cfg = load_scoring_config(REPO / "config")
        total = sum(cfg.weights.model_dump().values())
        assert total == 100

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*scoring.json"):
            load_scoring_config(tmp_path)

    def test_weights_must_sum_100(self, config_dir):
        import json
        path = config_dir / "scoring.json"
        data = json.loads(path.read_text())
        data["weights"]["trend"] = 5
        path.write_text(json.dumps(data))
        with pytest.raises(ConfigError):
            load_scoring_config(config_dir)
