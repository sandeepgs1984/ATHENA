"""EM-2 CHECKPOINT_DYNAMIC evidence: the 13 fields computed independently
per (symbol, session T, checkpoint C), using only same-session M5 candles
with ``ts_open < C`` -- the exact boundary already frozen and tested in
EM-1b's ``event_labels.py`` (a candle is observable as of C iff its
close time, ts_open+5min, is <= C).

Pure: no I/O, no clock. Callers supply the historical baselines this
module needs (20-session high/low, the REL_VOLUME_C comparable-time-of-day
baseline) rather than this module reaching into any repository itself --
keeps the leakage boundary auditable in one place per baseline, computed
once by the orchestration layer and reused, not recomputed per field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from athena.domain.market import Candle
from athena.explosive_move.event_labels import price_at_checkpoint, session_high_so_far
from athena.explosive_move.evidence_values import DailyBar, EvidenceValue
from athena.indicators.calculations import vwap


@dataclass(frozen=True, slots=True)
class CheckpointDynamicEvidence:
    cum_volume_c: EvidenceValue
    rel_volume_c: EvidenceValue
    dist_from_20d_high_c: EvidenceValue
    dist_from_20d_low_c: EvidenceValue
    range_position_20d_c: EvidenceValue
    return_from_open_c: EvidenceValue
    return_from_prev_close_c: EvidenceValue
    high_so_far_c: EvidenceValue
    low_so_far_c: EvidenceValue
    range_so_far_c: EvidenceValue
    dist_from_high_so_far_c: EvidenceValue
    vwap_through_c: EvidenceValue
    vwap_rel_c: EvidenceValue


def session_low_so_far(checkpoint_instant: datetime, session_candles: tuple[Candle, ...]) -> Decimal | None:
    """Mirrors ``event_labels.session_high_so_far``'s exact boundary
    (ts_open < checkpoint_instant): min low among fully-closed candles."""

    closed = [c for c in session_candles if c.ts_open < checkpoint_instant]
    if not closed:
        return None
    return min(c.low for c in closed)


def cumulative_volume_so_far(checkpoint_instant: datetime, session_candles: tuple[Candle, ...]) -> int | None:
    closed = [c for c in session_candles if c.ts_open < checkpoint_instant]
    if not closed:
        return None
    return sum(c.volume for c in closed)


def _high_low_20d(daily_bars: tuple[DailyBar, ...], before_count: int) -> tuple[Decimal, Decimal] | None:
    if before_count < 20:
        return None
    window = daily_bars[-20:]
    return max(b.high for b in window), min(b.low for b in window)


def compute_checkpoint_dynamic_evidence(
    *,
    checkpoint_instant: datetime,
    session_candles: tuple[Candle, ...],
    session_open: Decimal,
    prior_daily_bars: tuple[DailyBar, ...],  # already filtered to strictly before T, sorted ascending
    prev_close: Decimal | None,
    historical_checkpoint_volumes: tuple[int, ...],  # trailing prior sessions' cum volume through this same checkpoint
) -> CheckpointDynamicEvidence:
    price = price_at_checkpoint(checkpoint_instant, session_candles)
    no_candle_at_c = "no candle at exactly C"

    cum_vol = cumulative_volume_so_far(checkpoint_instant, session_candles)
    cum_volume_c = EvidenceValue.known(Decimal(cum_vol)) if cum_vol is not None else EvidenceValue.unknown(
        "no M5 candles with ts_open < C"
    )

    if cum_vol is None:
        rel_volume_c = EvidenceValue.unknown("CUM_VOLUME_C is UNKNOWN")
    elif len(historical_checkpoint_volumes) < 20:
        rel_volume_c = EvidenceValue.unknown(
            f"fewer than 20 prior admitted sessions with comparable-time-of-day volume data "
            f"(have {len(historical_checkpoint_volumes)})"
        )
    else:
        window = historical_checkpoint_volumes[-20:]
        mean_vol = sum(window) / len(window)
        rel_volume_c = (
            EvidenceValue.known(Decimal(cum_vol) / Decimal(mean_vol))
            if mean_vol != 0 else EvidenceValue.unknown("zero historical comparable volume baseline")
        )

    high_low = _high_low_20d(prior_daily_bars, len(prior_daily_bars))
    insufficient_20d = "fewer than 20 admitted daily bars strictly before T"
    if high_low is None:
        dist_from_20d_high_c = EvidenceValue.unknown(insufficient_20d)
        dist_from_20d_low_c = EvidenceValue.unknown(insufficient_20d)
        range_position_20d_c = EvidenceValue.unknown(insufficient_20d)
    elif price is None:
        dist_from_20d_high_c = EvidenceValue.unknown(no_candle_at_c)
        dist_from_20d_low_c = EvidenceValue.unknown(no_candle_at_c)
        range_position_20d_c = EvidenceValue.unknown(no_candle_at_c)
    else:
        high_20d, low_20d = high_low
        dist_from_20d_high_c = EvidenceValue.known(price / high_20d - 1)
        dist_from_20d_low_c = EvidenceValue.known(price / low_20d - 1)
        range_position_20d_c = (
            EvidenceValue.known((price - low_20d) / (high_20d - low_20d))
            if high_20d != low_20d else EvidenceValue.unknown("HIGH_20D == LOW_20D")
        )

    return_from_open_c = EvidenceValue.known(price / session_open - 1) if price is not None else EvidenceValue.unknown(
        no_candle_at_c
    )

    if prev_close is None:
        return_from_prev_close_c = EvidenceValue.unknown("no admitted daily bar for T-1")
    elif price is None:
        return_from_prev_close_c = EvidenceValue.unknown(no_candle_at_c)
    else:
        return_from_prev_close_c = EvidenceValue.known(price / prev_close - 1)

    high_so_far = session_high_so_far(checkpoint_instant, session_candles)
    low_so_far = session_low_so_far(checkpoint_instant, session_candles)
    no_closed_candles = "no M5 candles with ts_open < C"
    high_so_far_c = (
        EvidenceValue.known(high_so_far) if high_so_far is not None else EvidenceValue.unknown(no_closed_candles)
    )
    low_so_far_c = (
        EvidenceValue.known(low_so_far) if low_so_far is not None else EvidenceValue.unknown(no_closed_candles)
    )

    if high_so_far is None or low_so_far is None:
        range_so_far_c = EvidenceValue.unknown("HIGH_SO_FAR_C or LOW_SO_FAR_C is UNKNOWN")
        dist_from_high_so_far_c = EvidenceValue.unknown("HIGH_SO_FAR_C is UNKNOWN")
    else:
        range_so_far_c = EvidenceValue.known((high_so_far - low_so_far) / session_open)
        dist_from_high_so_far_c = (
            EvidenceValue.known(price / high_so_far - 1) if price is not None else EvidenceValue.unknown(no_candle_at_c)
        )

    closed_candles = tuple(c for c in session_candles if c.ts_open < checkpoint_instant)
    vwap_result = vwap(closed_candles, checkpoint_instant) if closed_candles else None
    if vwap_result is None:
        vwap_through_c = EvidenceValue.unknown(no_closed_candles)
        vwap_rel_c = EvidenceValue.unknown("VWAP_THROUGH_C is UNKNOWN")
    else:
        vwap_value = vwap_result[0]
        vwap_through_c = EvidenceValue.known(vwap_value)
        vwap_rel_c = (
            EvidenceValue.known(price / vwap_value - 1) if price is not None else EvidenceValue.unknown(no_candle_at_c)
        )

    return CheckpointDynamicEvidence(
        cum_volume_c=cum_volume_c, rel_volume_c=rel_volume_c,
        dist_from_20d_high_c=dist_from_20d_high_c, dist_from_20d_low_c=dist_from_20d_low_c,
        range_position_20d_c=range_position_20d_c,
        return_from_open_c=return_from_open_c, return_from_prev_close_c=return_from_prev_close_c,
        high_so_far_c=high_so_far_c, low_so_far_c=low_so_far_c, range_so_far_c=range_so_far_c,
        dist_from_high_so_far_c=dist_from_high_so_far_c,
        vwap_through_c=vwap_through_c, vwap_rel_c=vwap_rel_c,
    )
