"""Risk Engine tests (M3.5): risk dimensions, overall, UNKNOWN propagation,
determinism, immutability, config, traces."""

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
    load_risk_assessment_config,
)
from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import CalendarContext, CalendarEvent, Candle, Instrument, MarketSnapshot
from athena.errors import ConfigError
from athena.indicators import IndicatorEngine, IndicatorName
from athena.market_health import MarketHealthEngine
from athena.regime import RegimeEngine
from athena.risk import RiskEngine, RiskStatus
from athena.universe import UniverseEngine

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 8, 30, tzinfo=IST)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def risk(config_dir) -> RiskEngine:
    return RiskEngine(load_risk_assessment_config(config_dir))


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


def _regime(config_dir, candles, vix=15):
    snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")}, india_vix=Decimal(str(vix)))
    return RegimeEngine(load_config(config_dir).regime).assess("NIFTY50", candles, snap, as_of=AS_OF)


def _indicators(config_dir, candles):
    return IndicatorEngine(load_config(config_dir).indicators).compute_all(
        [IndicatorName.VOLUME_MA], candles, as_of=AS_OF)


def _cal(*, events=(), weekly=False):
    return CalendarContext(context_date=date(2026, 3, 2), session_type=SessionType.NORMAL,
                           exchange="NSE", timezone="Asia/Kolkata", open_time=None, close_time=None,
                           is_weekly_expiry=weekly, events=tuple(events))


class TestDimensions:
    def test_volatility_risk_high(self, risk, config_dir):
        r = risk.assess("X", as_of=AS_OF, regime=_regime(config_dir, _candles([100] * 60), vix=25))
        d = r.dimensions["volatility_risk"]
        assert d.status is RiskStatus.OK and d.value == Decimal("80")

    def test_volatility_risk_low(self, risk, config_dir):
        r = risk.assess("X", as_of=AS_OF, regime=_regime(config_dir, _candles([100] * 60), vix=10))
        assert r.dimensions["volatility_risk"].value == Decimal("20")

    def test_volatility_unknown_without_regime(self, risk):
        r = risk.assess("X", as_of=AS_OF)
        assert r.dimensions["volatility_risk"].status is RiskStatus.UNKNOWN

    def test_liquidity_risk_high_low(self, risk, config_dir):
        low_vol = risk.assess("X", as_of=AS_OF,
                              indicators=_indicators(config_dir, _candles(range(1, 40), volume=1000)))
        high_vol = risk.assess("X", as_of=AS_OF,
                               indicators=_indicators(config_dir, _candles(range(1, 40), volume=1_000_000)))
        assert low_vol.dimensions["liquidity_risk"].value == Decimal("80")
        assert high_vol.dimensions["liquidity_risk"].value == Decimal("20")

    def test_gap_risk(self, risk, config_dir):
        # prior close 100, next candle opens at 110 (+10% gap up) with valid OHLC
        first = _candles([100])[0]
        second = Candle(instrument_id="X", timeframe=Timeframe.D1,
                        ts_open=datetime(2026, 1, 2, 9, 15, tzinfo=IST),
                        open=Decimal("110"), high=Decimal("112"), low=Decimal("109"),
                        close=Decimal("111"), volume=1000, source="test")
        r = risk.assess("X", as_of=AS_OF, regime=_regime(config_dir, [first, second]))
        assert r.dimensions["gap_risk"].value == Decimal("70")

    def test_event_risk_variants(self, risk):
        with_event = risk.assess("X", as_of=AS_OF,
                                 calendar_context=_cal(events=[CalendarEvent(date(2026, 3, 2), "BUDGET", "Budget")]))
        expiry = risk.assess("X", as_of=AS_OF, calendar_context=_cal(weekly=True))
        normal = risk.assess("X", as_of=AS_OF, calendar_context=_cal())
        assert with_event.dimensions["event_risk"].value == Decimal("80")
        assert expiry.dimensions["event_risk"].value == Decimal("70")
        assert normal.dimensions["event_risk"].value == Decimal("20")

    def test_event_risk_unknown_without_calendar(self, risk):
        assert risk.assess("X", as_of=AS_OF).dimensions["event_risk"].status is RiskStatus.UNKNOWN

    def test_market_environment_risk(self, risk, config_dir):
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=20, breadth_declines=80, india_vix=Decimal("25"))
        mh = MarketHealthEngine(load_market_health_config(config_dir)).assess(
            "NIFTY50", _candles(range(140, 100, -1)), snap, as_of=AS_OF)
        r = risk.assess("X", as_of=AS_OF, market_health=mh)
        d = r.dimensions["market_environment_risk"]
        assert d.status is RiskStatus.OK and d.value > Decimal("50")  # weak breadth + elevated vol

    def test_concentration_indicator(self, risk, config_dir):
        instruments = [Instrument(instrument_id="I1", symbol="AAA", exchange="NSE", series="EQ",
                                  isin=None, lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE")]
        universe = UniverseEngine(load_config(config_dir).universe).build(
            instruments, {"I1": _candles(range(100, 140))}, as_of=AS_OF)
        r = risk.assess("X", as_of=AS_OF, universe=universe)
        # only 1 eligible << min_universe_size → concentrated
        assert r.dimensions["concentration_indicator"].value == Decimal("70")


class TestOverall:
    def test_full_inputs(self, risk, config_dir):
        candles = _candles(range(100, 160))
        snap = MarketSnapshot(ts=AS_OF, indices={"NIFTY50": Decimal("25000")},
                              breadth_advances=60, breadth_declines=40, india_vix=Decimal("15"))
        mh = MarketHealthEngine(load_market_health_config(config_dir)).assess(
            "NIFTY50", candles, snap, as_of=AS_OF)
        instruments = [Instrument(instrument_id="I1", symbol="AAA", exchange="NSE", series="EQ",
                                  isin=None, lot_size=1, tick_size=Decimal("0.05"), status="ACTIVE")]
        universe = UniverseEngine(load_config(config_dir).universe).build(
            instruments, {"I1": candles}, as_of=AS_OF)
        r = risk.assess("X", as_of=AS_OF, regime=_regime(config_dir, candles),
                        market_health=mh, indicators=_indicators(config_dir, candles),
                        calendar_context=_cal(), universe=universe)
        assert r.overall_status is RiskStatus.OK
        assert r.completeness == Decimal("1")
        assert 0 <= r.overall_value <= 100

    def test_no_inputs_unknown(self, risk):
        r = risk.assess("X", as_of=AS_OF)
        assert r.overall_status is RiskStatus.UNKNOWN
        assert r.overall_value is None
        assert len(r.dimensions) == 6
        assert r.unknown_stats["unknown_dimensions"] == 6


class TestContractAndConfig:
    def test_deterministic_repeat(self, risk, config_dir):
        candles = _candles(range(100, 160))
        args = dict(as_of=AS_OF, regime=_regime(config_dir, candles),
                    indicators=_indicators(config_dir, candles), calendar_context=_cal())
        assert risk.assess("X", **args) == risk.assess("X", **args)

    def test_immutable(self, risk):
        r = risk.assess("X", as_of=AS_OF)
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.overall_value = Decimal("1")

    def test_known_dimensions_have_traces(self, risk, config_dir):
        r = risk.assess("X", as_of=AS_OF, regime=_regime(config_dir, _candles([100] * 60)),
                        calendar_context=_cal())
        for d in r.dimensions.values():
            assert d.explanation
            if d.is_known:
                assert d.contributions

    def test_production_config_loads(self):
        cfg = load_risk_assessment_config(REPO / "config")
        assert sum(cfg.weights.model_dump().values()) == 100

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"Missing configuration file.*risk_assessment.json"):
            load_risk_assessment_config(tmp_path)
