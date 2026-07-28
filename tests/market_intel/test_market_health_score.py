"""F-5 MarketHealthScore construction + scoring cutover (MH-2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.config.loader import load_market_health_config, load_scoring_config
from athena.domain.enums import Timeframe
from athena.domain.market import (
    Candle,
    InstitutionalFlowSession,
    MarketHealthScore,
    MarketSnapshot,
)
from athena.errors import ConfigError
from athena.market_health import MarketHealthEngine, construct_market_health_score
from athena.market_health.aggregates import (
    GapStabilityResult,
    LiquidityAggregateResult,
    UniverseBreadthResult,
)
from athena.scoring import ScoreStatus, ScoringEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
IDX = "NIFTY50"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def health_cfg(config_dir):
    return load_market_health_config(config_dir)


def _series(closes) -> list[Candle]:
    candles = []
    start = date(2026, 1, 1)
    for i, close in enumerate(closes):
        c = Decimal(str(close))
        candles.append(
            Candle(
                instrument_id=IDX,
                timeframe=Timeframe.D1,
                ts_open=datetime.combine(
                    start + timedelta(days=i),
                    datetime.min.time(),
                    tzinfo=IST,
                ).replace(hour=9, minute=15),
                open=c,
                high=c + 1,
                low=c - 1,
                close=c,
                volume=1000,
                source="test",
            )
        )
    return candles


def _snapshot(*, adv=70, dec=30, neutral=0, vix=15) -> MarketSnapshot:
    return MarketSnapshot(
        ts=AS_OF,
        indices={IDX: Decimal("25000")},
        breadth_advances=adv,
        breadth_declines=dec,
        india_vix=Decimal(str(vix)) if vix is not None else None,
        breadth_neutral=neutral,
    )


def _flow(*, net: Decimal = Decimal("2500"), session: date | None = None):
    day = session or AS_OF.date()
    buy = max(net, Decimal(0)) + Decimal("1000")
    sell = buy - net
    return InstitutionalFlowSession(
        session_date=day,
        fii_buy=buy,
        fii_sell=sell,
        fii_net=net,
        dii_buy=Decimal("500"),
        dii_sell=Decimal("400"),
        dii_net=Decimal("100"),
        provisional=False,
        source_id="test",
        fetched_at=AS_OF,
    )


def _full_inputs(*, coverage_ok=True, members=80):
    """Inputs that should produce a complete six-component score."""
    scored = 80 if coverage_ok else 10
    universe = 100
    breadth = UniverseBreadthResult(
        advances=int(scored * 0.7),
        declines=int(scored * 0.3),
        neutral=0,
        universe_size=universe,
        scored=scored,
    )
    liquidity = LiquidityAggregateResult(
        member_count=members,
        median_turnover=Decimal("60000000"),
        method="median",
    )
    gap = GapStabilityResult(
        gap_days=2,
        scored_days=20,
        stability_ratio=Decimal("0.90"),
        gap_pct_threshold=Decimal("0.5"),
    )
    return breadth, liquidity, gap


class TestConstructMarketHealthScore:
    def test_emits_score_when_all_six_present(self, health_cfg, config_dir):
        candles = _series(range(100, 140))
        mh = MarketHealthEngine(health_cfg).assess(
            IDX, candles, _snapshot(), as_of=AS_OF
        )
        breadth, liquidity, gap = _full_inputs()
        build = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap,
            institutional_flow=_flow(),
            health_result=mh,
        )
        assert build.unavailable_reason is None
        assert build.score is not None
        assert set(build.score.components) == {
            "trend_quality",
            "breadth",
            "liquidity",
            "volatility",
            "institutional_strength",
            "gap_stability",
        }
        assert 0 <= build.score.total <= 100
        assert "MarketHealthScore" in build.score.explanation

    def test_unavailable_when_coverage_low(self, health_cfg):
        candles = _series(range(100, 140))
        mh = MarketHealthEngine(health_cfg).assess(
            IDX, candles, _snapshot(), as_of=AS_OF
        )
        breadth, liquidity, gap = _full_inputs(coverage_ok=False)
        build = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap,
            institutional_flow=_flow(),
            health_result=mh,
        )
        assert build.score is None
        assert "breadth" in (build.unavailable_reason or "")
        breadth_detail = next(c for c in build.components if c.name == "breadth")
        assert breadth_detail.points is None

    def test_unavailable_when_institutional_missing(self, health_cfg):
        candles = _series(range(100, 140))
        mh = MarketHealthEngine(health_cfg).assess(
            IDX, candles, _snapshot(), as_of=AS_OF
        )
        breadth, liquidity, gap = _full_inputs()
        build = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap,
            institutional_flow=None,
            health_result=mh,
        )
        assert build.score is None
        assert "institutional_strength" in (build.unavailable_reason or "")

    def test_unavailable_when_institutional_stale(self, health_cfg):
        candles = _series(range(100, 140))
        mh = MarketHealthEngine(health_cfg).assess(
            IDX, candles, _snapshot(), as_of=AS_OF
        )
        breadth, liquidity, gap = _full_inputs()
        stale = _flow(session=AS_OF.date() - timedelta(days=10))
        build = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap,
            institutional_flow=stale,
            health_result=mh,
        )
        assert build.score is None
        assert "institutional_strength" in (build.unavailable_reason or "")

    def test_weighted_total_deterministic(self, health_cfg):
        candles = _series(range(100, 140))
        mh = MarketHealthEngine(health_cfg).assess(
            IDX, candles, _snapshot(), as_of=AS_OF
        )
        breadth, liquidity, gap = _full_inputs()
        a = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap,
            institutional_flow=_flow(),
            health_result=mh,
        )
        b = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=breadth,
            liquidity=liquidity,
            gap_stability=gap,
            institutional_flow=_flow(),
            health_result=mh,
        )
        assert a.score == b.score
        # Manual weighted check from component points
        assert a.score is not None
        w = health_cfg.weights
        comps = a.score.components
        expected = round(
            (
                comps["trend_quality"] * w.trend_quality
                + comps["breadth"] * w.breadth
                + comps["liquidity"] * w.liquidity
                + comps["volatility"] * w.volatility
                + comps["institutional_strength"] * w.institutional_strength
                + comps["gap_stability"] * w.gap_stability
            )
            / 100
        )
        assert a.score.total == expected

    def test_payload_includes_diagnostics_when_unavailable(self, health_cfg):
        build = construct_market_health_score(
            as_of=AS_OF,
            config=health_cfg,
            breadth=UniverseBreadthResult(0, 0, 0, 0, 0),
            liquidity=LiquidityAggregateResult(0, None, "median"),
            gap_stability=GapStabilityResult(0, 0, None, Decimal("0.5")),
            institutional_flow=None,
            health_result=None,
        )
        payload = build.to_payload()
        assert payload["score"] is None
        assert len(payload["components"]) == 6
        assert payload["unavailable_reason"]


class TestScoringCutover:
    def test_market_quality_prefers_score_total(self, config_dir):
        scoring = ScoringEngine(load_scoring_config(config_dir))
        score = MarketHealthScore(
            ts=AS_OF,
            components={
                "trend_quality": 80,
                "breadth": 80,
                "liquidity": 50,
                "volatility": 55,
                "institutional_strength": 90,
                "gap_stability": 80,
            },
            total=74,
            explanation="test score",
        )
        result = scoring.score("X", as_of=AS_OF, market_health_score=score)
        mq = result.components["market_quality"]
        assert mq.status is ScoreStatus.OK
        assert mq.value == Decimal(74)
        assert any(c.source.startswith("market_health_score:") for c in mq.contributions)

    def test_market_quality_falls_back_to_categorical(self, config_dir, health_cfg):
        scoring = ScoringEngine(load_scoring_config(config_dir))
        candles = _series(range(100, 140))
        mh = MarketHealthEngine(health_cfg).assess(
            IDX, candles, _snapshot(), as_of=AS_OF
        )
        result = scoring.score("X", as_of=AS_OF, market_health=mh)
        mq = result.components["market_quality"]
        assert mq.status is ScoreStatus.OK
        assert any(c.source.startswith("market_health:") for c in mq.contributions)


class TestConfig:
    def test_production_weights_sum_100(self):
        cfg = load_market_health_config(REPO / "config")
        total = (
            cfg.weights.trend_quality
            + cfg.weights.breadth
            + cfg.weights.liquidity
            + cfg.weights.volatility
            + cfg.weights.institutional_strength
            + cfg.weights.gap_stability
        )
        assert total == 100

    def test_invalid_weights_rejected(self, config_dir):
        path = config_dir / "market_health.json"
        text = path.read_text(encoding="utf-8")
        # Break sum while keeping JSON valid
        path.write_text(
            text.replace('"gap_stability": 15', '"gap_stability": 10'),
            encoding="utf-8",
        )
        with pytest.raises(ConfigError):
            load_market_health_config(config_dir)
