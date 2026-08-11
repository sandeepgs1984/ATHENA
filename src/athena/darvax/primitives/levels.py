"""Fibonacci retracement levels and zone classification (DX-2).

The deck (p.30) names exactly four retracement levels to watch — 23.6%, 38.2%,
50.0%, 61.8% — and gives two named interpretations of where price sits:

    if Retracement is between 23.6 - 38.2% ⚡ Trend is Very Strong 💪
    In Extreme Market Crash 🦥 We Will Luv to Date our Favorite Stocks 💞
    In Retracement Zone 50 - 61.8%

Both named bands are reproduced faithfully in :class:`RetracementZone`. The
bands outside them (below 23.6%, between 38.2-50%, above 61.8%) are labelled
neutrally as SHALLOW / MODERATE / DEEP because the deck assigns them no meaning
and inventing one would be putting words in the author's mouth.

Retracement is measured **down from the swing high toward the swing low**, which
is the up-leg-pullback case the deck describes.
"""

from __future__ import annotations

from decimal import Decimal

from athena.darvax.primitives._guards import DarvaxPrimitiveError
from athena.darvax.primitives.models import FibonacciLevels, RetracementZone

#: The four levels the deck names (p.30). Ordered shallowest-first; the tuple
#: ordering is part of the published contract.
FIBONACCI_RETRACEMENT_PERCENTS: tuple[Decimal, ...] = (
    Decimal("23.6"),
    Decimal("38.2"),
    Decimal("50.0"),
    Decimal("61.8"),
)

_VERY_STRONG_LOW = Decimal("23.6")
_VERY_STRONG_HIGH = Decimal("38.2")
_ACCUMULATION_LOW = Decimal("50.0")
_ACCUMULATION_HIGH = Decimal("61.8")


def classify_retracement(pct: Decimal) -> RetracementZone:
    """Map a retracement percentage onto the deck's named bands.

    Band edges are inclusive at the lower bound and inclusive at the upper
    bound of each named band, so 23.6 and 38.2 both read as VERY_STRONG_TREND
    and 50.0 and 61.8 both read as ACCUMULATION — matching how the deck writes
    them as closed ranges ("between 23.6 - 38.2%", "Zone 50 - 61.8%").
    """
    if pct < _VERY_STRONG_LOW:
        return RetracementZone.SHALLOW
    if pct <= _VERY_STRONG_HIGH:
        return RetracementZone.VERY_STRONG_TREND
    if pct < _ACCUMULATION_LOW:
        return RetracementZone.MODERATE
    if pct <= _ACCUMULATION_HIGH:
        return RetracementZone.ACCUMULATION
    return RetracementZone.DEEP


def fibonacci_levels(
    swing_low: Decimal,
    swing_high: Decimal,
    *,
    price: Decimal | None = None,
) -> FibonacciLevels:
    """Retracement prices for a swing leg, and optionally where ``price`` sits.

    Args:
        swing_low: the leg's low.
        swing_high: the leg's high. Must be >= ``swing_low``.
        price: optional current price to locate within the leg.

    A zero-height swing (high == low) yields every level at that same price, a
    ``None`` retracement percentage, and zone ``UNDEFINED`` — there is nothing
    to retrace, and reporting 0% would imply a measurement that was never made.
    """
    if swing_high < swing_low:
        raise DarvaxPrimitiveError(
            f"swing_high ({swing_high}) must be >= swing_low ({swing_low})"
        )

    height = swing_high - swing_low
    levels = tuple(
        (pct, swing_high - height * pct / Decimal(100))
        for pct in FIBONACCI_RETRACEMENT_PERCENTS
    )

    if height == 0:
        return FibonacciLevels(
            swing_low=swing_low,
            swing_high=swing_high,
            levels=levels,
            price=price,
            retracement_pct=None,
            zone=RetracementZone.UNDEFINED,
        )

    retracement_pct: Decimal | None = None
    zone = RetracementZone.UNDEFINED
    if price is not None:
        retracement_pct = (swing_high - price) / height * Decimal(100)
        zone = classify_retracement(retracement_pct)

    return FibonacciLevels(
        swing_low=swing_low,
        swing_high=swing_high,
        levels=levels,
        price=price,
        retracement_pct=retracement_pct,
        zone=zone,
    )
