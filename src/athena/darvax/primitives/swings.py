"""ZigZag swing points (DX-2).

The source deck's ZigZag setup (p.32) reads:

    - Plot ZigZag Indicator
    - Wait for Swing Low of ZigZag
    - Look for Retracement of Fibonacci Golden Ratio 61.8%
    - Wait for Buy Signal above 10 EMA
    - Ride the Trend till Next ZigZag Swing High

This module supplies only the first element of that list — where the confirmed
swing highs and lows are. The 61.8% part is :mod:`.levels`; the EMA trigger and
"buy signal" are DX-3.

Definition implemented (standard percentage-reversal ZigZag): while in an
up-leg, the running highest high is the candidate pivot; the pivot is
**confirmed as a swing high** once price falls ``threshold_pct`` from it, at
which point the leg flips down. The mirror rule applies to swing lows.

Only confirmed pivots are returned. The current, still-forming extreme is
deliberately omitted — calling it a swing before the reversal happens would be
a prediction, not a measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax.primitives._guards import (
    require_chronological_candles,
    require_positive,
)
from athena.darvax.primitives.models import SwingKind, SwingPoint
from athena.domain.market import Candle

#: Reversal size that confirms a pivot, in percent. The deck names no number
#: for its ZigZag, so this is an explicit parameter; 5% is a conventional
#: swing-trading default and DX-3 will wire it to DarvaX config.
DEFAULT_SWING_THRESHOLD_PCT = Decimal("5")


def _pct_move(from_price: Decimal, to_price: Decimal) -> Decimal:
    """Absolute percent move between two prices; 0 when the base is 0."""
    if from_price == 0:
        return Decimal(0)
    return abs(to_price - from_price) / from_price * Decimal(100)


def zigzag_swings(
    candles: Sequence[Candle],
    *,
    threshold_pct: Decimal = DEFAULT_SWING_THRESHOLD_PCT,
) -> tuple[SwingPoint, ...]:
    """Confirmed ZigZag pivots, oldest-first, strictly alternating high/low.

    Args:
        candles: oldest-first, single instrument, single timeframe.
        threshold_pct: reversal percentage required to confirm a pivot.

    Returns:
        Confirmed swing points. Empty when price never reversed by the
        threshold — an honest "no swing yet", not an error.
    """
    require_chronological_candles(candles, minimum=1, what="zigzag_swings")
    require_positive(threshold_pct, name="threshold_pct")

    swings: list[SwingPoint] = []
    high = candles[0].high
    high_index = 0
    low = candles[0].low
    low_index = 0
    direction: str | None = None  # None until the first threshold move resolves it

    def _emit(kind: SwingKind, index: int, price: Decimal) -> None:
        swings.append(
            SwingPoint(kind=kind, index=index, price=price, ts=candles[index].ts_open)
        )

    for i in range(1, len(candles)):
        bar = candles[i]

        if direction is None:
            # Track both extremes until one side moves far enough to define the
            # first leg's direction.
            if bar.high > high:
                high, high_index = bar.high, i
            if bar.low < low:
                low, low_index = bar.low, i
            if _pct_move(high, bar.low) >= threshold_pct and bar.low < high:
                _emit(SwingKind.HIGH, high_index, high)
                direction = "down"
                low, low_index = bar.low, i
            elif _pct_move(low, bar.high) >= threshold_pct and bar.high > low:
                _emit(SwingKind.LOW, low_index, low)
                direction = "up"
                high, high_index = bar.high, i

        elif direction == "up":
            if bar.high > high:
                high, high_index = bar.high, i
            elif _pct_move(high, bar.low) >= threshold_pct:
                _emit(SwingKind.HIGH, high_index, high)
                direction = "down"
                low, low_index = bar.low, i

        else:  # direction == "down"
            if bar.low < low:
                low, low_index = bar.low, i
            elif _pct_move(low, bar.high) >= threshold_pct:
                _emit(SwingKind.LOW, low_index, low)
                direction = "up"
                high, high_index = bar.high, i

    return tuple(swings)


def last_completed_swing_leg(
    swings: Sequence[SwingPoint],
) -> tuple[SwingPoint, SwingPoint] | None:
    """The most recent confirmed low→high or high→low pair, or None.

    Provided because Fibonacci retracement needs a swing *leg* (two pivots),
    not a single pivot. Returns the pair in chronological order.
    """
    if len(swings) < 2:
        return None
    return swings[-2], swings[-1]
