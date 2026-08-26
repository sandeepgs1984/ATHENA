"""EM-1b forward-label contract (owner decision, 2026-08-26): a checkpoint
label is a genuinely forward-looking question. An event already observable
before the checkpoint is ALREADY_OCCURRED, never silently folded into
label=0 or label=1. Tests reproduce the owner's own worked example exactly
and lock down the candle-observability boundary that prevents leakage."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST
from athena.explosive_move.event_labels import (
    ForwardLabelOutcome,
    evaluate_close_label,
    evaluate_touch_label,
    first_touch_time,
    outcome_from_touch_time,
    price_at_checkpoint,
    session_high_so_far,
    threshold_price,
)

IST = ZoneInfo("Asia/Kolkata")
DAY = datetime(2024, 3, 15, tzinfo=IST)
REFERENCE = Decimal("100")  # the owner's own example: previous close = 100
THRESHOLD_PERCENT = 10  # +10% -> 110


def _t(hour: int, minute: int) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


def _candle(ts_open: datetime, high: Decimal, *, open_: Decimal | None = None) -> Candle:
    return Candle(
        instrument_id="NSE:AAA", timeframe=Timeframe.M5, ts_open=ts_open,
        open=open_ if open_ is not None else high, high=high,
        low=Decimal("99"), close=Decimal("100"), volume=1000, source="kite", adjusted=False,
    )


def _full_session_no_touch() -> tuple[Candle, ...]:
    """A quiet session: every candle stays well under the 110 threshold."""
    return tuple(
        _candle(_t(9, 15) + timedelta(minutes=5 * i), Decimal("101"))
        for i in range(75)
    )


def _session_with_touch_at(touch_time: datetime) -> tuple[Candle, ...]:
    """Identical to the quiet session, except one candle spikes to 112."""
    candles = list(_full_session_no_touch())
    for i, c in enumerate(candles):
        if c.ts_open == touch_time:
            candles[i] = _candle(touch_time, Decimal("112"))
    return tuple(candles)


# --------------------------------------------------------------------------- #
# The owner's own worked example, reproduced exactly:
# previous close = 100, +10% threshold = 110, first touch at the 09:25 candle.
# 09:20 checkpoint -> still forward -> POSITIVE.
# 09:30 checkpoint -> already known -> ALREADY_OCCURRED.
# --------------------------------------------------------------------------- #

TOUCH_TIME = _t(9, 25)
SESSION = _session_with_touch_at(TOUCH_TIME)


def test_checkpoint_before_the_touch_sees_it_as_a_genuine_forward_positive():
    result = evaluate_touch_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=_t(9, 20), session_candles=SESSION,
    )
    assert result.outcome is ForwardLabelOutcome.POSITIVE
    assert result.first_touch_time == TOUCH_TIME


def test_checkpoint_after_the_touch_sees_it_as_already_occurred():
    result = evaluate_touch_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=_t(9, 30), session_candles=SESSION,
    )
    assert result.outcome is ForwardLabelOutcome.ALREADY_OCCURRED
    assert result.first_touch_time == TOUCH_TIME


def test_checkpoint_exactly_at_the_touching_candle_is_still_forward():
    """The critical leakage boundary: a candle whose ts_open exactly
    equals the checkpoint instant is NOT YET CLOSED at that instant --
    its own outcome must count as forward, not already-known."""
    result = evaluate_touch_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=TOUCH_TIME, session_candles=SESSION,
    )
    assert result.outcome is ForwardLabelOutcome.POSITIVE
    assert result.first_touch_time == TOUCH_TIME


def test_checkpoint_one_candle_after_the_touch_is_already_occurred():
    result = evaluate_touch_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=TOUCH_TIME + timedelta(minutes=5), session_candles=SESSION,
    )
    assert result.outcome is ForwardLabelOutcome.ALREADY_OCCURRED


def test_session_that_never_touches_is_negative_not_already_occurred():
    result = evaluate_touch_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=_t(9, 20), session_candles=_full_session_no_touch(),
    )
    assert result.outcome is ForwardLabelOutcome.NEGATIVE
    assert result.first_touch_time is None


def test_first_touch_time_is_the_earliest_qualifying_candle_not_any_qualifying_one():
    candles = list(_full_session_no_touch())
    for i, c in enumerate(candles):
        if c.ts_open in (_t(9, 25), _t(9, 35)):
            candles[i] = _candle(c.ts_open, Decimal("112"))
    result = evaluate_touch_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=_t(9, 15), session_candles=tuple(candles),
    )
    assert result.first_touch_time == _t(9, 25)


# --------------------------------------------------------------------------- #
# CLOSE_N: no ALREADY_OCCURRED concept, per explicit owner instruction.
# --------------------------------------------------------------------------- #

def test_close_label_has_no_already_occurred_state_even_late_in_the_session():
    """A checkpoint at 14:00, well after any intraday spike, must still
    resolve CLOSE purely from the final session close -- never
    ALREADY_OCCURRED, since the close itself isn't known until 15:30."""
    result = evaluate_close_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        session_close=Decimal("111"),
    )
    assert result.outcome is ForwardLabelOutcome.POSITIVE
    assert result.first_touch_time is None


def test_close_label_negative_when_close_falls_short():
    result = evaluate_close_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        session_close=Decimal("105"),
    )
    assert result.outcome is ForwardLabelOutcome.NEGATIVE


def test_close_label_boundary_is_inclusive_at_exact_threshold():
    result = evaluate_close_label(
        reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
        session_close=Decimal("110"),
    )
    assert result.outcome is ForwardLabelOutcome.POSITIVE


# --------------------------------------------------------------------------- #
# OPEN_TO_HIGH_N: identical touch mechanics to TOUCH, but referenced off
# the session's own open -- can be ALREADY_OCCURRED even at the earliest
# candidate checkpoint if the session gaps up hard in its first minutes.
# --------------------------------------------------------------------------- #

def test_open_to_high_can_be_already_occurred_at_the_earliest_checkpoint():
    session_open = Decimal("100")
    candles = list(_full_session_no_touch())
    candles[0] = _candle(_t(9, 15), Decimal("112"), open_=session_open)  # spikes in the very first 5 minutes
    result = evaluate_touch_label(
        reference_price=session_open, threshold_percent=THRESHOLD_PERCENT,
        checkpoint_instant=_t(9, 20), session_candles=tuple(candles),
    )
    assert result.outcome is ForwardLabelOutcome.ALREADY_OCCURRED
    assert result.first_touch_time == _t(9, 15)


# --------------------------------------------------------------------------- #
# price_at_checkpoint / session_high_so_far -- the same observability
# boundary, applied to the checkpoint-record fields themselves.
# --------------------------------------------------------------------------- #

def test_price_at_checkpoint_uses_the_open_of_the_candle_starting_exactly_then():
    price = price_at_checkpoint(_t(9, 20), SESSION)
    matching = next(c for c in SESSION if c.ts_open == _t(9, 20))
    assert price == matching.open


def test_price_at_checkpoint_is_none_when_no_candle_opens_exactly_then():
    off_grid = _t(9, 21)
    assert price_at_checkpoint(off_grid, SESSION) is None


def test_session_high_so_far_excludes_the_in_progress_checkpoint_candle():
    """The candle opening exactly at the checkpoint is still in progress
    -- its high must not count toward 'so far', or a same-candle spike
    would leak into a value the checkpoint could not actually observe."""
    high_so_far = session_high_so_far(TOUCH_TIME, SESSION)
    closed_candles = [c for c in SESSION if c.ts_open < TOUCH_TIME]
    assert high_so_far == max(c.high for c in closed_candles)
    assert high_so_far < Decimal("112")  # the 09:25 spike itself must not leak in


def test_session_high_so_far_is_none_before_any_candle_has_closed():
    assert session_high_so_far(_t(9, 15), SESSION) is None


def test_threshold_price_is_upside_only():
    assert threshold_price(Decimal("100"), 10) == Decimal("110")
    assert threshold_price(Decimal("200"), 5) == Decimal("210")


# --------------------------------------------------------------------------- #
# first_touch_time / outcome_from_touch_time -- the whole-session-scan-once
# optimization used by the EM-1b measurement and dataset-generation scripts
# to avoid re-scanning a session per checkpoint. Proven exactly equivalent
# to calling evaluate_touch_label independently for every checkpoint.
# --------------------------------------------------------------------------- #

_CHECKPOINT_INSTANTS = tuple(
    DAY.replace(hour=int(cp.split(":")[0]), minute=int(cp.split(":")[1])) for cp in CANDIDATE_CHECKPOINTS_IST
)


def _assert_equivalent_to_reference(session_candles: tuple[Candle, ...]) -> None:
    touch_time = first_touch_time(REFERENCE, THRESHOLD_PERCENT, session_candles)
    for checkpoint_instant in _CHECKPOINT_INSTANTS:
        fast_outcome = outcome_from_touch_time(touch_time, checkpoint_instant)
        reference = evaluate_touch_label(
            reference_price=REFERENCE, threshold_percent=THRESHOLD_PERCENT,
            checkpoint_instant=checkpoint_instant, session_candles=session_candles,
        )
        assert fast_outcome == reference.outcome, (
            f"checkpoint {checkpoint_instant}: fast={fast_outcome} reference={reference.outcome}"
        )


def test_first_touch_time_equivalent_to_reference_when_touch_precedes_all_checkpoints():
    _assert_equivalent_to_reference(_session_with_touch_at(_t(9, 15)))


def test_first_touch_time_equivalent_to_reference_when_touch_follows_all_checkpoints():
    _assert_equivalent_to_reference(_session_with_touch_at(_t(13, 55)))


def test_first_touch_time_equivalent_to_reference_when_touch_falls_among_the_checkpoints():
    # 10:00 is itself a candidate checkpoint -- exercises the exact-equality
    # forward boundary against several checkpoints at once (09:20..09:45
    # already-occurred; 10:00..14:00 forward).
    _assert_equivalent_to_reference(_session_with_touch_at(_t(10, 0)))


def test_first_touch_time_equivalent_to_reference_when_session_never_touches():
    _assert_equivalent_to_reference(_session_with_touch_at(None))


def test_first_touch_time_is_none_when_no_candle_qualifies():
    assert first_touch_time(REFERENCE, THRESHOLD_PERCENT, _full_session_no_touch()) is None


def test_outcome_from_touch_time_boundary_is_non_vacuous():
    """Reintroduce the exact off-by-one the boundary rule guards against
    (`<=` instead of `<`) and confirm the equivalence check actually fails,
    proving the tests above would catch a real leakage regression."""
    touch_time = _t(10, 0)

    def _buggy(touch, checkpoint):
        if touch is None:
            return outcome_from_touch_time(None, checkpoint)
        if touch <= checkpoint:  # bug: leaks the boundary candle as ALREADY_OCCURRED
            return ForwardLabelOutcome.ALREADY_OCCURRED
        return ForwardLabelOutcome.POSITIVE

    correct = outcome_from_touch_time(touch_time, _t(10, 0))
    buggy = _buggy(touch_time, _t(10, 0))
    assert correct != buggy
