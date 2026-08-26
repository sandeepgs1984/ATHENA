"""EM-1b forward-label contract: checkpoint-conditioned event labels.

Owner decision, 2026-08-26: a checkpoint's label answers a genuinely
forward-looking question -- "given information legitimately available AT
checkpoint C, does the upside threshold get reached AFTER C?" An event
that already happened before C is neither a positive nor a negative
forward-prediction example; it is a distinct ``ALREADY_OCCURRED`` outcome,
excluded from the eligible forward-prediction population, never silently
folded into label=0 or label=1. Direction is upside-only ("expansion"),
per the roadmap's own stated purpose.

Candle-observability boundary -- critical for preventing look-ahead
leakage, explicitly required by the owner. A 5-minute candle's
``ts_open`` is its OPEN time; its high/low/close are not final, not
observable, until its window ends at ``ts_open + 5 minutes``, which
equals the NEXT candle's ``ts_open``. So, relative to a checkpoint
instant C:
  - a candle with ``ts_open < C`` is fully closed and observable as of C
    (its close time, ``ts_open + 5min``, is <= C) -- this is the
    "backward" set, used to detect an event that already happened;
  - a candle with ``ts_open >= C`` has not yet closed as of C (even the
    candle whose ``ts_open`` exactly equals C is still in progress at
    that instant) -- this is the "forward" set, used to detect a genuine
    forward-prediction outcome.

Verified directly against the owner's own worked example: previous
close=100, +10% threshold=110, a candle opening at 09:25 is the one that
touches it. At checkpoint 09:20, that candle is in the forward set
(09:25 >= 09:20) -> POSITIVE. At checkpoint 09:30, that same candle is in
the backward set (09:25 < 09:30) -> ALREADY_OCCURRED. Exactly the
transition the owner specified.

``price_at_checkpoint`` uses the OPEN of the candle at ``ts_open == C``
(the first real trade price known at/after the checkpoint instant).

This module is pure: no I/O, no provider imports, no persistence. It
classifies label outcomes from a caller-supplied ordered sequence of
real candles; it does not decide which symbol-days/checkpoints are
evidence-ready (that stays EM-1a's frozen ``assess_checkpoint_readiness``,
unmodified).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from athena.domain.market import Candle


class ForwardLabelOutcome(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    ALREADY_OCCURRED = "ALREADY_OCCURRED"


@dataclass(frozen=True, slots=True)
class ForwardLabelResult:
    """One event family/threshold's checkpoint-conditioned outcome.

    ``first_touch_time`` is the *candle open time* of the earliest
    qualifying candle -- a real, documented granularity limit of 5-minute
    OHLC evidence: the exact intra-candle instant a threshold was crossed
    is not knowable from this data, only which 5-minute window it fell in.
    """

    outcome: ForwardLabelOutcome
    threshold_price: Decimal
    first_touch_time: datetime | None = None

    def __post_init__(self) -> None:
        if self.outcome is ForwardLabelOutcome.NEGATIVE and self.first_touch_time is not None:
            raise ValueError("a NEGATIVE outcome carries no touch time")
        if self.outcome is ForwardLabelOutcome.ALREADY_OCCURRED and self.first_touch_time is None:
            raise ValueError("ALREADY_OCCURRED requires a first_touch_time")
        # POSITIVE may or may not carry a first_touch_time: TOUCH/OPEN_TO_HIGH
        # always do (the qualifying candle); CLOSE never does (the "touch" is
        # the session close itself, not a specific intraday candle).


def threshold_price(reference_price: Decimal, threshold_percent: int) -> Decimal:
    """Upside-only: reference_price * (1 + threshold_percent / 100)."""
    return reference_price * (Decimal(100 + threshold_percent) / Decimal(100))


def evaluate_touch_label(
    *,
    reference_price: Decimal,
    threshold_percent: int,
    checkpoint_instant: datetime,
    session_candles: tuple[Candle, ...],
) -> ForwardLabelResult:
    """TOUCH_N and OPEN_TO_HIGH_N share identical touch mechanics -- does
    the session's high ever reach the threshold -- differing only in
    which reference_price the caller supplies (previous session's close
    for TOUCH; the current session's own open for OPEN_TO_HIGH)."""

    price = threshold_price(reference_price, threshold_percent)
    ordered = sorted(session_candles, key=lambda c: c.ts_open)

    for candle in ordered:
        if candle.ts_open >= checkpoint_instant:
            break
        if candle.high >= price:
            return ForwardLabelResult(
                outcome=ForwardLabelOutcome.ALREADY_OCCURRED,
                threshold_price=price,
                first_touch_time=candle.ts_open,
            )

    for candle in ordered:
        if candle.ts_open < checkpoint_instant:
            continue
        if candle.high >= price:
            return ForwardLabelResult(
                outcome=ForwardLabelOutcome.POSITIVE,
                threshold_price=price,
                first_touch_time=candle.ts_open,
            )

    return ForwardLabelResult(outcome=ForwardLabelOutcome.NEGATIVE, threshold_price=price)


def evaluate_close_label(
    *,
    reference_price: Decimal,
    threshold_percent: int,
    session_close: Decimal,
) -> ForwardLabelResult:
    """CLOSE_N has no ALREADY_OCCURRED concept: the qualifying close is
    only known at session close itself, so any checkpoint strictly before
    close asks the identical, still-open forward question. Never apply
    TOUCH's first-hit backward scan to CLOSE."""

    price = threshold_price(reference_price, threshold_percent)
    outcome = (
        ForwardLabelOutcome.POSITIVE if session_close >= price else ForwardLabelOutcome.NEGATIVE
    )
    return ForwardLabelResult(outcome=outcome, threshold_price=price)


def price_at_checkpoint(
    checkpoint_instant: datetime, session_candles: tuple[Candle, ...]
) -> Decimal | None:
    """The OPEN of the candle whose ts_open exactly equals the checkpoint
    instant -- the first real trade price known at/after that instant.
    None if no such candle exists in the supplied session."""

    for candle in session_candles:
        if candle.ts_open == checkpoint_instant:
            return candle.open
    return None


def session_high_so_far(
    checkpoint_instant: datetime, session_candles: tuple[Candle, ...]
) -> Decimal | None:
    """Max high among candles fully closed strictly before the checkpoint
    instant (ts_open < checkpoint_instant). None if none have closed yet."""

    closed = [c for c in session_candles if c.ts_open < checkpoint_instant]
    if not closed:
        return None
    return max(c.high for c in closed)


def first_touch_time(
    reference_price: Decimal, threshold_percent: int, session_candles: tuple[Candle, ...]
) -> datetime | None:
    """The earliest candle open time at which the session's high reaches
    the threshold, scanning the WHOLE session regardless of checkpoint --
    a caller-side optimization: computing this once per (symbol-day,
    family, threshold) and deriving every checkpoint's outcome from it via
    ``outcome_from_touch_time`` is exactly equivalent to calling
    ``evaluate_touch_label`` independently per checkpoint (proven by
    ``tests/data_layer/test_em1b_partition_measurement.py``), at a
    fraction of the cost when many checkpoints share one session scan."""

    price = threshold_price(reference_price, threshold_percent)
    for candle in sorted(session_candles, key=lambda c: c.ts_open):
        if candle.high >= price:
            return candle.ts_open
    return None


def outcome_from_touch_time(
    touch_time: datetime | None, checkpoint_instant: datetime
) -> ForwardLabelOutcome:
    """Derive a single checkpoint's outcome from a whole-session
    ``first_touch_time`` -- the same candle-observability boundary as
    ``evaluate_touch_label`` (ts_open < checkpoint -> already known)."""

    if touch_time is None:
        return ForwardLabelOutcome.NEGATIVE
    if touch_time < checkpoint_instant:
        return ForwardLabelOutcome.ALREADY_OCCURRED
    return ForwardLabelOutcome.POSITIVE
