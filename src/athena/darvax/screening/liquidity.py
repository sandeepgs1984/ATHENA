"""Traded value per day — DarvaX's stand-in for market cap (DX-10a).

**Why liquidity and not capitalisation.** ATHENA holds no market-cap data: there
is no ``market_cap`` or ``shares_outstanding`` column anywhere, and the broker
dump reports ``last_price = 0`` for every row, so it cannot even be derived. A
real size filter needs a new versioned data source (design §1.1).

Liquidity is not a consolation prize, though. Market cap says how large a company
is; **traded value says whether the position can be exited**, which is the
question conviction actually rests on. Measured across the discovery universe it
spans ₹0.07 crore/day at the 10th percentile to ₹143.89 crore at the 90th — a
factor of 2,000, so it discriminates.

Pure functions over candles. No clock, no config, no IO.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from decimal import Decimal

from athena.domain.market import Candle

#: Sessions the median is taken over. Twenty is roughly a trading month — long
#: enough that one frenzied day cannot promote an illiquid name, short enough to
#: still describe the present.
LIQUIDITY_WINDOW_BARS = 20

#: Minimum sessions required to report a figure at all. Below this the median is
#: describing too little trading to mean anything, and reporting it would let a
#: newly listed symbol look as liquid as an established one.
LIQUIDITY_MIN_BARS = 10


def traded_value(candles: Sequence[Candle]) -> Decimal | None:
    """Median daily traded value over the last :data:`LIQUIDITY_WINDOW_BARS`.

    **Median, not mean.** A single block deal or a listing-day frenzy moves a
    mean by an order of magnitude; the point of the measure is what trades on an
    ordinary day, and that is what a trader needs in order to size a position
    they can exit.

    Returns ``None`` when there is too little history, which is reported as
    unknown rather than as zero — an unmeasured symbol and an untradeable one are
    different, and a filter that conflated them would silently hide new listings.
    """
    if len(candles) < LIQUIDITY_MIN_BARS:
        return None
    window = candles[-LIQUIDITY_WINDOW_BARS:]
    values = [c.close * Decimal(c.volume) for c in window if c.volume > 0]
    if len(values) < LIQUIDITY_MIN_BARS:
        return None
    return Decimal(statistics.median(values)).quantize(Decimal("1"))


def in_crore(value: Decimal | None) -> Decimal | None:
    """Rupees to crore, the unit an Indian trader reads liquidity in."""
    if value is None:
        return None
    return (value / Decimal(10_000_000)).quantize(Decimal("0.01"))
