"""Intraday Analytics Engine (ID-2) — typed formalization of the existing
VWAP/5m-15m-confluence evidence. No BUY/SELL/TRADE meaning anywhere here;
see `athena.intraday`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import Timeframe
from athena.indicators.models import IndicatorEvidence, IndicatorName, IndicatorResult, IndicatorStatus
from athena.intraday import IntradayAnalyticsEngine, IntradayTrendLabel, VwapRelation
from athena.scoring.models import ConfluenceInputs
from athena.session import SessionContextEngine

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
IID = "NSE:TEST"
AS_OF = datetime(2026, 8, 28, 9, 40, tzinfo=IST)
DAY = date(2026, 8, 28)
FIVE_PERIOD, FIFTEEN_PERIOD = 9, 5


@pytest.fixture()
def calendar() -> CalendarEngine:
    cfg = load_config(CONFIG_DIR)
    return CalendarEngine.from_config_dir(CONFIG_DIR, cfg.market)


@pytest.fixture()
def sessions_cfg():
    return load_config(CONFIG_DIR).market.sessions


@pytest.fixture()
def session_context(calendar, sessions_cfg):
    return SessionContextEngine().assess(
        IID, as_of=AS_OF, exchange="NSE", calendar=calendar, sessions=sessions_cfg,
        tzinfo=IST, five_min_candles=[], fifteen_min_candles=[], latest_quote_ts=None,
    )


@pytest.fixture()
def engine() -> IntradayAnalyticsEngine:
    return IntradayAnalyticsEngine()


def _assess(engine, session_context, *, vwap=None, confluence=None, as_of=AS_OF):
    return engine.assess(
        IID, as_of=as_of, session_date=DAY, session_context=session_context,
        vwap=vwap, confluence=confluence,
        five_min_sma_period=FIVE_PERIOD, fifteen_min_sma_period=FIFTEEN_PERIOD,
    )


def _vwap_ok(deviation_pct: str) -> IndicatorResult:
    return IndicatorResult(
        name=IndicatorName.VWAP, status=IndicatorStatus.OK,
        parameters={}, window_used=1,
        values={"vwap": Decimal("100"), "deviation_pct": Decimal(deviation_pct)},
        evidence=IndicatorEvidence(formula="vwap", inputs={}, explanation="test vwap"),
        ts=AS_OF,
    )


def _vwap_unknown() -> IndicatorResult:
    return IndicatorResult(
        name=IndicatorName.VWAP, status=IndicatorStatus.UNKNOWN,
        parameters={}, window_used=0, values={},
        evidence=IndicatorEvidence(formula="vwap", inputs={}, explanation="no session bars"),
        ts=AS_OF,
    )


# --------------------------------------------------------------------------- #
# 1/2 — immutable, explanation-bearing
# --------------------------------------------------------------------------- #

def test_1_2_signal_set_and_trend_context_are_immutable_and_explained(engine, session_context):
    sig = _assess(engine, session_context, vwap=_vwap_ok("1.5"),
                  confluence=ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=True))
    assert sig.explanation
    assert sig.trend.explanation
    assert sig.vwap.explanation
    with pytest.raises(AttributeError):
        sig.instrument_id = "NSE:OTHER"  # frozen dataclass -- no mutation
    with pytest.raises(AttributeError):
        sig.trend.trend_label = IntradayTrendLabel.BEARISH


def test_no_buy_sell_or_probability_concept_exists_on_the_contract():
    """Structural proof, not just a promise: the dataclasses simply have no
    such fields to accidentally populate."""
    import dataclasses

    from athena.intraday.models import IntradaySignalSet, IntradayTrendContext
    forbidden = {"buy", "sell", "trade", "probability", "score", "signal_strength"}
    for cls in (IntradaySignalSet, IntradayTrendContext):
        names = {f.name.lower() for f in dataclasses.fields(cls)}
        assert not (names & forbidden), f"{cls.__name__} has a forbidden field: {names & forbidden}"


# --------------------------------------------------------------------------- #
# VWAP formalization — no invented "near VWAP" band
# --------------------------------------------------------------------------- #

def test_vwap_above(engine, session_context):
    sig = _assess(engine, session_context, vwap=_vwap_ok("1.5"))
    assert sig.vwap.relation is VwapRelation.ABOVE_VWAP
    assert sig.vwap.deviation_pct == Decimal("1.5")


def test_vwap_below(engine, session_context):
    sig = _assess(engine, session_context, vwap=_vwap_ok("-2.0"))
    assert sig.vwap.relation is VwapRelation.BELOW_VWAP


def test_vwap_exactly_at(engine, session_context):
    sig = _assess(engine, session_context, vwap=_vwap_ok("0"))
    assert sig.vwap.relation is VwapRelation.AT_VWAP


def test_vwap_unavailable_when_indicator_unknown(engine, session_context):
    sig = _assess(engine, session_context, vwap=_vwap_unknown())
    assert sig.vwap.relation is VwapRelation.VWAP_UNAVAILABLE
    assert sig.vwap.deviation_pct is None
    assert sig.vwap.explanation


def test_vwap_unavailable_when_none(engine, session_context):
    sig = _assess(engine, session_context, vwap=None)
    assert sig.vwap.relation is VwapRelation.VWAP_UNAVAILABLE


# --------------------------------------------------------------------------- #
# 8/9/10/11 — per-timeframe evidence independence
# --------------------------------------------------------------------------- #

def test_8_no_5m_data_is_explicit_unavailable(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=None, fifteen_min_bullish=True)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.five_min.bullish is None
    assert sig.trend.five_min.explanation


def test_9_no_15m_data_is_explicit_unavailable(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=None)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.fifteen_min.bullish is None
    assert sig.trend.fifteen_min.explanation


def test_10_5m_valid_15m_unavailable_preserves_5m_evidence(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=None)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.five_min.bullish is True  # preserved, not discarded
    assert sig.trend.trend_label is IntradayTrendLabel.UNKNOWN  # aggregate can't be formed


def test_11_15m_valid_5m_unavailable_preserves_15m_evidence(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=None, fifteen_min_bullish=False)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.fifteen_min.bullish is False
    assert sig.trend.trend_label is IntradayTrendLabel.UNKNOWN


def test_12_missing_expected_bars_propagate_into_the_explanation(engine, calendar, sessions_cfg):
    """A real EXPECTED_BAR_MISSING SessionContext (per ID-1's own gap
    detection) must show up in the trend evidence's explanation, not be
    silently dropped."""
    from athena.domain.market import Candle

    def m5(hh, mm):
        px = Decimal("100")
        return Candle(instrument_id=IID, timeframe=Timeframe.M5,
                      ts_open=datetime(2026, 8, 28, hh, mm, tzinfo=IST),
                      open=px, high=px + 1, low=px - 1, close=px, volume=1000, source="test")

    gappy_session = SessionContextEngine().assess(
        IID, as_of=AS_OF, exchange="NSE", calendar=calendar, sessions=sessions_cfg,
        tzinfo=IST, five_min_candles=[m5(9, 15), m5(9, 25)],  # 09:20 missing
        fifteen_min_candles=[], latest_quote_ts=None,
    )
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=None, fifteen_min_bullish=None)
    sig = _assess(engine, gappy_session, confluence=confluence)
    assert "EXPECTED_BAR_MISSING" in sig.trend.five_min.explanation


# --------------------------------------------------------------------------- #
# Trend aggregation — zero new weights/thresholds
# --------------------------------------------------------------------------- #

def test_both_timeframes_bullish_is_bullish(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=True)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.trend_label is IntradayTrendLabel.BULLISH


def test_both_timeframes_bearish_is_bearish(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=False, five_min_bullish=False, fifteen_min_bullish=False)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.trend_label is IntradayTrendLabel.BEARISH


def test_disagreement_is_mixed_and_visible_not_hidden(engine, session_context):
    """ID-2.1 owner decision: disagreement is labelled MIXED, not NEUTRAL —
    NEUTRAL could be misread as price structure itself being flat, when
    what's actually known is that the two timeframes disagree."""
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=False)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.trend_label is IntradayTrendLabel.MIXED
    assert "5m=bullish" in sig.trend.explanation and "15m=bearish" in sig.trend.explanation


def test_both_missing_is_unknown(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=None, fifteen_min_bullish=None)
    sig = _assess(engine, session_context, confluence=confluence)
    assert sig.trend.trend_label is IntradayTrendLabel.UNKNOWN


def test_no_confluence_at_all_is_unknown(engine, session_context):
    sig = _assess(engine, session_context, confluence=None)
    assert sig.trend.trend_label is IntradayTrendLabel.UNKNOWN


# --------------------------------------------------------------------------- #
# 6/7 — as_of controls everything; determinism
# --------------------------------------------------------------------------- #

def test_6_as_of_alone_can_change_which_evidence_is_eligible(engine, session_context):
    later = datetime(2026, 8, 28, 10, 0, tzinfo=IST)
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=True)
    a = _assess(engine, session_context, confluence=confluence, as_of=AS_OF)
    b = _assess(engine, session_context, confluence=confluence, as_of=later)
    assert a.as_of != b.as_of
    assert a.trend.as_of != b.trend.as_of


def test_7_identical_inputs_produce_identical_artifacts(engine, session_context):
    confluence = ConfluenceInputs(daily_bullish=True, five_min_bullish=True, fifteen_min_bullish=False)
    vwap = _vwap_ok("0.75")
    a = _assess(engine, session_context, vwap=vwap, confluence=confluence)
    b = IntradayAnalyticsEngine().assess(  # fresh engine instance -- no hidden shared state
        IID, as_of=AS_OF, session_date=DAY, session_context=session_context,
        vwap=vwap, confluence=confluence,
        five_min_sma_period=FIVE_PERIOD, fifteen_min_sma_period=FIFTEEN_PERIOD,
    )
    assert a == b


def test_naive_as_of_rejected(engine, session_context):
    with pytest.raises(ValueError, match="timezone-aware"):
        engine.assess(
            IID, as_of=datetime(2026, 8, 28, 9, 40), session_date=DAY,
            session_context=session_context, vwap=None, confluence=None,
            five_min_sma_period=FIVE_PERIOD, fifteen_min_sma_period=FIFTEEN_PERIOD,
        )
