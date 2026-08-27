"""EM-4C MFE/MAE/time-to-target: forward-only boundary (no candle before
the checkpoint may contribute), CLOSE has no time-to-target, and
time-to-target is only computed for genuinely positive-labelled cases."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.forward_excursion import compute_forward_excursion

IST = ZoneInfo("Asia/Kolkata")
DAY = datetime(2024, 3, 15, tzinfo=IST)
REFERENCE = Decimal("100")
THRESHOLD_PERCENT = 10  # -> 110


def _t(hour: int, minute: int) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


def _candle(ts_open: datetime, high: Decimal, low: Decimal) -> Candle:
    return Candle(
        instrument_id="NSE:AAA", timeframe=Timeframe.M5, ts_open=ts_open,
        open=Decimal("100"), high=high, low=low, close=Decimal("100"),
        volume=1000, source="kite", adjusted=False,
    )


def _session() -> tuple[Candle, ...]:
    # a quiet session, then a spike to 112 at 09:35, then a dip to 92 at 09:50
    candles = []
    for i in range(75):
        t = _t(9, 15) + timedelta(minutes=5 * i)
        if t == _t(9, 35):
            candles.append(_candle(t, Decimal("112"), Decimal("99")))
        elif t == _t(9, 50):
            candles.append(_candle(t, Decimal("101"), Decimal("92")))
        else:
            candles.append(_candle(t, Decimal("101"), Decimal("99")))
    return tuple(candles)


SESSION = _session()


def test_mfe_mae_only_use_forward_candles():
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 20), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="TOUCH", is_positive_label=True,
    )
    assert result.mfe_percent == Decimal("12")  # (112/100 - 1) * 100
    assert result.mae_percent == Decimal("-8")  # (92/100 - 1) * 100


def test_mfe_mae_excludes_a_spike_before_the_checkpoint():
    """Checkpoint at 09:40 -- the 09:35 spike to 112 already closed before
    it, so it must not count toward forward MFE."""
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 40), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="TOUCH", is_positive_label=True,
    )
    assert result.mfe_percent == Decimal("1")  # only the quiet 101 highs remain forward
    assert result.mae_percent == Decimal("-8")  # the 09:50 dip to 92 is still forward


def test_no_forward_candles_is_unknown():
    result = compute_forward_excursion(
        checkpoint_instant=_t(15, 30), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="TOUCH", is_positive_label=True,
    )
    assert result.mfe_percent is None
    assert result.unknown_reason is not None


def test_time_to_target_touch_family_positive_label():
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 20), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="TOUCH", is_positive_label=True,
    )
    assert result.time_to_target_applicable is True
    assert result.time_to_target_minutes == Decimal("15")  # 09:20 -> 09:35


def test_time_to_target_open_to_high_family_positive_label():
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 20), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="OPEN_TO_HIGH", is_positive_label=True,
    )
    assert result.time_to_target_applicable is True
    assert result.time_to_target_minutes == Decimal("15")


def test_time_to_target_not_applicable_for_close_family():
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 20), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="CLOSE", is_positive_label=True,
    )
    assert result.time_to_target_applicable is False
    assert result.time_to_target_minutes is None


def test_time_to_target_not_computed_for_negative_label():
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 20), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="TOUCH", is_positive_label=False,
    )
    assert result.time_to_target_minutes is None


def test_time_to_target_none_when_threshold_never_reached_after_checkpoint():
    result = compute_forward_excursion(
        checkpoint_instant=_t(9, 40), session_candles=SESSION, reference_price=REFERENCE,
        threshold_percent=THRESHOLD_PERCENT, event_family="TOUCH", is_positive_label=True,
    )
    assert result.time_to_target_minutes is None
