"""EM-1c regime-evidence prerequisite: point-in-time-safe historical replay
(Owner/Chief Architect decision, 2026-08-27). The six required leakage
properties are each proven directly, non-vacuously where the property is
about a boundary rather than a plain absence.

Uses the real config/regime.json values (fast SMA=20, slow SMA=50, VIX
bands [12, 20], gap threshold 0.5%) so the warm-up/threshold behavior
matches production exactly, per the owner's "canonical RegimeEngine only,
unchanged" instruction.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.config.models import RegimeConfig
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.regime_replay import reconstruct_session_regime
from athena.regime.models import RegimeLabel

IST = ZoneInfo("Asia/Kolkata")
INDEX = "NSE:NIFTY 50"

CONFIG = RegimeConfig(
    gap_pct_threshold=0.5, high_volatility_vix=20.0, low_volatility_vix=12.0,
    trend_ma_fast=20, trend_ma_slow=50, market_health_floor=40, sector_health_floor=40,
)


def _d1(d: date, close: str, *, open_: str | None = None) -> Candle:
    open_val = Decimal(open_ if open_ is not None else close)
    close_val = Decimal(close)
    return Candle(
        instrument_id=INDEX, timeframe=Timeframe.D1,
        ts_open=datetime(d.year, d.month, d.day, tzinfo=IST),
        open=open_val, high=max(open_val, close_val), low=min(open_val, close_val),
        close=close_val, volume=0, source="kite", adjusted=False,
    )


def _uptrend_warmup(start: date, days: int, base: str) -> list[Candle]:
    """`days` consecutive rising-close sessions ending the day before `start`."""
    base_val = Decimal(base)
    out = []
    for i in range(days):
        d = start - timedelta(days=days - i)
        out.append(_d1(d, str(base_val + i)))
    return out


T = date(2024, 6, 20)  # arbitrary session under test
T_MINUS_1 = T - timedelta(days=1)


def _warmup(base: str = "100") -> list[Candle]:
    return _uptrend_warmup(T, 55, base)  # 55 >= slow_ma(50) + a margin


def test_1_session_t_regime_cannot_access_t_close():
    """T's own real close is far outside any threshold; if it leaked into
    trend, the trend SMA would visibly shift. It must not."""
    warmup = _warmup()
    baseline = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup),
        vix_candles=(), config=CONFIG,
    )
    with_t_close = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX,
        nifty_candles=tuple([*warmup, _d1(T, "999999")]),  # T's own wild close
        vix_candles=(), config=CONFIG,
    )
    assert with_t_close.trend == baseline.trend
    assert with_t_close.trend_explanation == baseline.trend_explanation


def test_2_modifying_t_high_low_close_after_checkpoint_does_not_alter_pre_close_classification():
    warmup = _warmup()
    a = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX,
        nifty_candles=tuple([*warmup, _d1(T, "150", open_="101")]),
        vix_candles=(), config=CONFIG,
    )
    b = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX,
        # same open (legitimate), wildly different close/high/low (not legitimate)
        nifty_candles=tuple([*warmup, _d1(T, "5", open_="101")]),
        vix_candles=(), config=CONFIG,
    )
    assert a.trend == b.trend
    assert a.volatility == b.volatility
    assert a.gap == b.gap  # gap only reads T's open, unaffected by close/high/low


def _downtrend_warmup(start: date, days: int, base: str) -> list[Candle]:
    """`days` consecutive falling-close sessions ending the day before `start`."""
    base_val = Decimal(base)
    return [_d1(start - timedelta(days=days - i), str(base_val - i)) for i in range(days)]


def test_3_modifying_t_minus_1_history_can_legitimately_alter_t_classification():
    warmup_up = _warmup(base="100")
    warmup_down = _downtrend_warmup(T, 55, base="300")
    up = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup_up),
        vix_candles=(), config=CONFIG,
    )
    down = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup_down),
        vix_candles=(), config=CONFIG,
    )
    assert up.trend != down.trend
    assert up.trend is RegimeLabel.BULL_TREND
    assert down.trend is RegimeLabel.BEAR_TREND


def test_4_future_sessions_cannot_influence_earlier_regimes():
    warmup = _warmup()
    baseline = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup),
        vix_candles=(), config=CONFIG,
    )
    future_candle = _d1(T + timedelta(days=5), "999999")
    with_future = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple([*warmup, future_candle]),
        vix_candles=(), config=CONFIG,
    )
    assert with_future.trend == baseline.trend
    assert with_future.volatility == baseline.volatility
    assert with_future.gap == baseline.gap


def test_5_first_train_sessions_use_only_warmup_history_preceding_them():
    """A session with exactly 50 (slow_ma) prior candles gets a real
    classification; one fewer gets UNKNOWN -- confirms the boundary is
    exactly at the config's own trend_ma_slow, not an approximation."""
    exact_warmup = _uptrend_warmup(T, 50, "100")
    result = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(exact_warmup),
        vix_candles=(), config=CONFIG,
    )
    assert result.trend is not RegimeLabel.TREND_UNKNOWN

    one_short = exact_warmup[1:]  # 49 candles
    short_result = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(one_short),
        vix_candles=(), config=CONFIG,
    )
    assert short_result.trend is RegimeLabel.TREND_UNKNOWN


def test_6_insufficient_warmup_is_unknown_not_backfilled_from_future():
    """Zero prior history (T is the very first session in the acquired
    range) must produce TREND_UNKNOWN/VOLATILITY_UNKNOWN, never a value
    silently borrowed from T's own or a later session."""
    result = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=(_d1(T, "100"),),
        vix_candles=(), config=CONFIG,
    )
    assert result.trend is RegimeLabel.TREND_UNKNOWN
    assert result.volatility is RegimeLabel.VOLATILITY_UNKNOWN
    assert result.index_data_cutoff is None


def test_gap_uses_t_open_legitimately():
    warmup = _warmup()
    prev_close = warmup[-1].close
    gap_up_close = prev_close * Decimal("1.02")  # +2%, above 0.5% threshold
    result = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX,
        nifty_candles=tuple([*warmup, _d1(T, "100", open_=str(gap_up_close))]),
        vix_candles=(), config=CONFIG,
    )
    assert result.gap is RegimeLabel.GAP_UP


def test_gap_is_unknown_when_t_own_candle_is_absent():
    """T's own candle is genuinely missing from the acquired series (e.g.
    the real 2024-01-22 provider blackout) -- gap must not be silently
    computed from the wrong (T-1 vs T-2) pair."""
    warmup = _warmup()
    result = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup),  # no T candle at all
        vix_candles=(), config=CONFIG,
    )
    assert result.gap is RegimeLabel.GAP_UNKNOWN


def test_volatility_uses_vix_strictly_before_t():
    vix_before = (_d1(T_MINUS_1, "15"),)
    vix_including_t = (*vix_before, _d1(T, "999"))  # T's own VIX close, must not leak
    warmup = _warmup()
    before_only = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup),
        vix_candles=vix_before, config=CONFIG,
    )
    including_t = reconstruct_session_regime(
        session_date=T, index_symbol=INDEX, nifty_candles=tuple(warmup),
        vix_candles=vix_including_t, config=CONFIG,
    )
    assert before_only.volatility == including_t.volatility
    assert before_only.volatility is RegimeLabel.NORMAL_VOLATILITY
    assert before_only.vix_data_cutoff == T_MINUS_1
