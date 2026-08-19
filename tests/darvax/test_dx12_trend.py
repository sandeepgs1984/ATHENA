"""DX-12a: 50/100-session EMA trend context on the screener.

Requested directly by the owner ("adding 50 and 100 ema to darvax screener").
**Not a DAR-CARD rule** — the deck's only EMA usage is the 5/10/20/200 stop
ladder (an exit rule), not a trend filter. This is a conviction overlay layered
on top of the classification, exactly like DX-10a's liquidity and box-height:
it must never influence ``tier`` or ``action``, only ride alongside them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from athena.darvax.screening.engine import screen_signal, screen_signals
from athena.darvax.screening.trend import (
    EMA_TREND_PERIOD_LONG,
    EMA_TREND_PERIOD_MEDIUM,
    TREND_LOOKBACK_BARS,
    TrendReading,
    trend_reading,
    trend_state,
)
from athena.darvax.signals.ema import latest_ema
from athena.darvax.signals.models import DarvasRule, DarvaxSignal, DarvaxSignalType
from athena.darvax.store.repository import DarvaxRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

BASE = datetime(2026, 8, 1, tzinfo=timezone.utc)


def bar(price: str, day: int) -> Candle:
    return Candle(
        instrument_id="NSE:X", timeframe=Timeframe.D1,
        ts_open=BASE + timedelta(days=day),
        open=Decimal(price), high=Decimal(price), low=Decimal(price),
        close=Decimal(price), volume=100_000, source="test",
    )


def signal(*, close="100", state=DarvaxSignalType.BREAKOUT):
    return DarvaxSignal(
        signal_id="s", instrument_id="NSE:X", as_of=BASE, signal_type=state,
        darvas_rule=DarvasRule.B_BUY_ABOVE_TOPMOST_BOX, close=Decimal(close),
        box_top=Decimal("105"), box_bottom=Decimal("90"),
        trigger_price=Decimal("101"), stop=None,
        explanation="e", evidence={}, methodology_digest="d", darvax_version="t",
    )


# --------------------------------------------------------------------------- #
# 1. trend_reading / trend_state — pure arithmetic
# --------------------------------------------------------------------------- #


def test_trend_lookback_is_the_longer_of_the_two_periods():
    assert TREND_LOOKBACK_BARS == EMA_TREND_PERIOD_LONG == 100
    assert EMA_TREND_PERIOD_MEDIUM == 50


def test_trend_reading_matches_the_shared_ema_primitive_directly():
    """No second EMA implementation — trend_reading must agree, bar for bar,
    with the same latest_ema() the stop ladder already relies on."""
    candles = [bar(str(100 + i), i) for i in range(120)]
    closes = [c.close for c in candles]
    reading = trend_reading(candles)
    assert reading.ema_50 == latest_ema(candles, 50) == latest_ema(candles, 50)
    assert reading.ema_100 == latest_ema(candles, 100)
    assert reading.ema_50 != reading.ema_100  # sanity: not accidentally aliased


def test_ema_50_and_ema_100_are_independently_nullable():
    """A newly listed instrument may have 60 days of history: enough for
    EMA(50), not enough for EMA(100). Neither must be guessed or withheld
    together with the other."""
    candles = [bar(str(100 + i), i) for i in range(60)]
    reading = trend_reading(candles)
    assert reading.ema_50 is not None
    assert reading.ema_100 is None


def test_both_emas_absent_when_history_is_shorter_than_fifty_bars():
    candles = [bar(str(100 + i), i) for i in range(10)]
    reading = trend_reading(candles)
    assert reading.ema_50 is None
    assert reading.ema_100 is None


def test_trend_state_above_both_below_both_and_mixed():
    above = trend_state(Decimal("500"), TrendReading(ema_50=Decimal("100"), ema_100=Decimal("90")))
    below = trend_state(Decimal("10"), TrendReading(ema_50=Decimal("100"), ema_100=Decimal("90")))
    mixed = trend_state(Decimal("95"), TrendReading(ema_50=Decimal("100"), ema_100=Decimal("90")))
    assert above == "above_both"
    assert below == "below_both"
    assert mixed == "mixed"


def test_trend_state_is_none_when_either_ema_is_unmeasured():
    """A partial reading (one EMA known, one not) cannot honestly be called
    "above both" or "below both" — classifying on half the picture would be
    worse than admitting the state is unknown."""
    partial = TrendReading(ema_50=Decimal("100"), ema_100=None)
    assert trend_state(Decimal("500"), partial) is None
    assert trend_state(Decimal("500"), TrendReading(ema_50=None, ema_100=None)) is None


# --------------------------------------------------------------------------- #
# 2. screen_signal / screen_signals — threading, not gating
# --------------------------------------------------------------------------- #


def test_screen_signal_carries_trend_onto_the_result():
    reading = TrendReading(ema_50=Decimal("98.50"), ema_100=Decimal("95.00"))
    result = screen_signal(signal(), sweep_id="swp", trend=reading)
    assert result.ema_50 == Decimal("98.50")
    assert result.ema_100 == Decimal("95.00")


def test_screen_signal_defaults_to_no_trend_data():
    """Every pre-DX-12a caller of screen_signal must keep working unchanged."""
    result = screen_signal(signal(), sweep_id="swp")
    assert result.ema_50 is None
    assert result.ema_100 is None


def test_trend_never_changes_the_tier_or_action():
    """The core design constraint: trend is a passenger, not a gate. Two
    signals identical except for trend must classify identically."""
    bullish = screen_signal(signal(), sweep_id="swp",
                             trend=TrendReading(ema_50=Decimal("50"), ema_100=Decimal("40")))
    bearish = screen_signal(signal(), sweep_id="swp",
                             trend=TrendReading(ema_50=Decimal("999"), ema_100=Decimal("999")))
    assert bullish.tier == bearish.tier
    assert bullish.action == bearish.action
    assert bullish.signal_type == bearish.signal_type


def test_screen_signals_maps_trend_per_instrument_like_liquidity():
    sigs = [signal()]
    trend_map = {"NSE:X": TrendReading(ema_50=Decimal("97"), ema_100=Decimal("94"))}
    results = screen_signals(sigs, sweep_id="swp", trend=trend_map)
    assert results[0].ema_50 == Decimal("97")
    assert results[0].ema_100 == Decimal("94")


# --------------------------------------------------------------------------- #
# 3. Repository round-trip — persisted, not recomputed (ADR-005)
# --------------------------------------------------------------------------- #


def test_ema_values_round_trip_through_the_repository(tmp_path):
    repo = DarvaxRepository(str(tmp_path / "darvax.db"))
    repo.initialize()
    try:
        repo.save_sweep(_bare_sweep_record("swp-1"))
        result = screen_signal(
            signal(), sweep_id="swp-1",
            trend=TrendReading(ema_50=Decimal("98.50"), ema_100=Decimal("95.25")),
        )
        repo.save_screen_results([result])
        latest = repo.list_screen_results("swp-1")
        assert len(latest) == 1
        assert latest[0].ema_50 == Decimal("98.50")
        assert latest[0].ema_100 == Decimal("95.25")
    finally:
        repo.close()


def test_absent_ema_round_trips_as_none_not_zero(tmp_path):
    repo = DarvaxRepository(str(tmp_path / "darvax.db"))
    repo.initialize()
    try:
        repo.save_sweep(_bare_sweep_record("swp-2"))
        result = screen_signal(signal(), sweep_id="swp-2")  # no trend at all
        repo.save_screen_results([result])
        latest = repo.list_screen_results("swp-2")
        assert latest[0].ema_50 is None
        assert latest[0].ema_100 is None
    finally:
        repo.close()


def _bare_sweep_record(sweep_id: str):
    from athena.darvax.screening.models import DarvaxTier, SweepRecord

    return SweepRecord(
        sweep_id=sweep_id, started_at=BASE, state="completed",
        methodology_digest="d", darvax_version="t", requested=1, evaluated=1,
        tier_counts={t: 0 for t in DarvaxTier},
    )


# --------------------------------------------------------------------------- #
# 4. sweep.py — one combined read, isolation preserved
# --------------------------------------------------------------------------- #


class _StubMarketData:
    """Enough of DarvaxMarketDataPort for _context_for: recent_candles, with
    one instrument deliberately unreadable."""

    def __init__(self, by_instrument):
        self._by_instrument = by_instrument

    def list_instruments(self):
        raise NotImplementedError("not used by _context_for directly")

    def recent_candles(self, instrument_id, timeframe, limit):
        candles = self._by_instrument.get(instrument_id)
        if candles is None:
            raise RuntimeError("simulated read failure")
        return candles[-limit:]


def _signal_for(instrument_id: str) -> DarvaxSignal:
    return DarvaxSignal(
        signal_id="s", instrument_id=instrument_id, as_of=BASE,
        signal_type=DarvaxSignalType.BREAKOUT,
        darvas_rule=DarvasRule.B_BUY_ABOVE_TOPMOST_BOX, close=Decimal("100"),
        box_top=Decimal("105"), box_bottom=Decimal("90"),
        trigger_price=Decimal("101"), stop=None,
        explanation="e", evidence={}, methodology_digest="d", darvax_version="t",
    )


def _runner(market_data, tmp_path):
    from athena.darvax.config import DarvaxConfig
    from athena.darvax.screening.sweep import SweepRunner

    repo = DarvaxRepository(str(tmp_path / "darvax.db"))
    repo.initialize()
    runner = SweepRunner(
        market_data=market_data, store=repo, config=DarvaxConfig(),
        darvax_version="test",
    )
    return runner, repo


def test_context_for_derives_both_liquidity_and_trend_from_one_read(tmp_path):
    good_candles = [bar(str(100 + i), i) for i in range(120)]
    market_data = _StubMarketData({"NSE:GOOD": good_candles})
    runner, repo = _runner(market_data, tmp_path)
    try:
        liquidity, trend = runner._context_for([_signal_for("NSE:GOOD")])
        assert "NSE:GOOD" in liquidity
        assert "NSE:GOOD" in trend
        assert trend["NSE:GOOD"].ema_50 is not None
        assert trend["NSE:GOOD"].ema_100 is not None
    finally:
        repo.close()


def test_a_read_failure_excludes_the_symbol_from_both_maps(tmp_path):
    """The isolation property: one instrument's unreadable candles must not
    cost the sweep, and must not leave it half-measured (liquidity present,
    trend absent, or vice versa) — it is simply absent from both."""
    market_data = _StubMarketData({})  # every read raises
    runner, repo = _runner(market_data, tmp_path)
    try:
        liquidity, trend = runner._context_for([_signal_for("NSE:BAD")])
        assert "NSE:BAD" not in liquidity
        assert "NSE:BAD" not in trend
    finally:
        repo.close()
