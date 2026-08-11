"""Darvas box construction (DX-2) — the methodology's structural core.

Implements the box definition from Nicolas Darvas' own rules, reproduced in the
source deck on p.67 ("HOW I USE THE DAR-CARD") and referenced there via
thepatternsite.com / perfecttrendsystem.com:

    A. A stock is in a rising trend when it is in its topmost box.
    B. If the price moves above the top of this topmost box the stock becomes a
       BUY. A 10 percent stop-loss should be set on the first breakout.
    C. Having formed a new higher box, if the price falls below the bottom the
       stock is a SELL.
    D. There is no reason to HOLD or BUY a stock that is not in its topmost box.

This module implements **only the geometry** those rules operate on: where the
boxes are, and whether each is the topmost so far. It deliberately does not
detect breakouts, evaluate rules B/C, or emit any signal — that is DX-3.

Algorithm, stated exactly so it can be reviewed and reproduced by hand:

1. Scanning forward, track the running highest high. Any bar exceeding it
   becomes the new candidate ceiling.
2. The **ceiling is confirmed** once ``confirmation_bars`` bars have passed
   after the ceiling bar without any of them exceeding it.
3. From the bar immediately after the ceiling bar, track the running lowest
   low. Any bar below it becomes the new candidate floor. (Starting here means
   the pullback that forms the floor includes the ceiling's own confirmation
   bars, which is how Darvas describes it.)
4. The **floor is confirmed** once ``confirmation_bars`` bars have passed after
   the floor bar without any of them breaching it. The box is now complete.
5. **Invalidation:** if any bar clears the ceiling before the floor is
   confirmed, no box formed here — price simply kept rising. Scanning restarts
   from that bar, which will go on to establish a higher ceiling.
6. Scanning for the next box resumes after the confirmed floor.

Where the deck is silent on a number, it is an explicit parameter with a cited
default rather than an invented value presented as the author's.
"""

from __future__ import annotations

from collections.abc import Sequence

from athena.darvax.primitives._guards import (
    require_chronological_candles,
    require_positive,
)
from athena.darvax.primitives.models import DarvasBox
from athena.domain.market import Candle

#: Bars a ceiling/floor must survive unbeaten to count as confirmed. Three is
#: the value used by the classical Darvas implementations the deck links to
#: (thepatternsite.com, perfecttrendsystem.com); the deck itself states no
#: number, so this stays a parameter. DX-3 will wire it to DarvaX config.
DEFAULT_CONFIRMATION_BARS = 3


def darvas_boxes(
    candles: Sequence[Candle],
    *,
    confirmation_bars: int = DEFAULT_CONFIRMATION_BARS,
) -> tuple[DarvasBox, ...]:
    """Every **completed** Darvas box in a chronological candle series.

    Args:
        candles: oldest-first, single instrument, single timeframe.
        confirmation_bars: bars a ceiling/floor must hold to be confirmed.

    Returns:
        Boxes in the order they completed. Empty when the history is too short
        for even one box to complete — an honest "cannot know yet", not an error.
    """
    require_chronological_candles(candles, minimum=1, what="darvas_boxes")
    require_positive(confirmation_bars, name="confirmation_bars")

    total = len(candles)
    boxes: list[DarvasBox] = []
    highest_top_so_far = None
    scan = 0

    while scan < total:
        # --- Phase A: confirm a ceiling ------------------------------------
        top = candles[scan].high
        top_index = scan
        top_confirmed_index: int | None = None
        cursor = scan + 1
        while cursor < total:
            if candles[cursor].high > top:
                top = candles[cursor].high
                top_index = cursor
            elif cursor - top_index >= confirmation_bars:
                top_confirmed_index = cursor
                break
            cursor += 1
        if top_confirmed_index is None:
            break  # history ran out before any ceiling could be confirmed

        # --- Phase B: confirm a floor beneath that ceiling -----------------
        floor_scan_start = top_index + 1
        if floor_scan_start >= total:
            break
        bottom = candles[floor_scan_start].low
        bottom_index = floor_scan_start
        bottom_confirmed_index: int | None = None
        invalidated_at: int | None = None

        cursor = floor_scan_start + 1
        while cursor < total:
            # A break above the ceiling means this box never formed (step 5).
            # Checked first so a single wide bar that both breaks out and makes
            # a new low is treated as a breakout, not as a deeper floor.
            if candles[cursor].high > top:
                invalidated_at = cursor
                break
            if candles[cursor].low < bottom:
                bottom = candles[cursor].low
                bottom_index = cursor
            elif cursor - bottom_index >= confirmation_bars:
                bottom_confirmed_index = cursor
                break
            cursor += 1

        if invalidated_at is not None:
            scan = invalidated_at
            continue
        if bottom_confirmed_index is None:
            break  # history ran out before the floor could be confirmed

        is_topmost = highest_top_so_far is None or top >= highest_top_so_far
        boxes.append(
            DarvasBox(
                top=top,
                bottom=bottom,
                top_index=top_index,
                bottom_index=bottom_index,
                top_confirmed_index=top_confirmed_index,
                bottom_confirmed_index=bottom_confirmed_index,
                top_ts=candles[top_index].ts_open,
                bottom_ts=candles[bottom_index].ts_open,
                is_topmost=is_topmost,
            )
        )
        if highest_top_so_far is None or top > highest_top_so_far:
            highest_top_so_far = top

        scan = bottom_confirmed_index + 1

    return tuple(boxes)


def current_box(
    candles: Sequence[Candle],
    *,
    confirmation_bars: int = DEFAULT_CONFIRMATION_BARS,
) -> DarvasBox | None:
    """The most recently completed box, or None if none has completed yet.

    Convenience over :func:`darvas_boxes` for the common "where does price sit
    now" question. Still pure measurement — it reports the latest box, and
    says nothing about what to do about it.
    """
    boxes = darvas_boxes(candles, confirmation_bars=confirmation_bars)
    return boxes[-1] if boxes else None
