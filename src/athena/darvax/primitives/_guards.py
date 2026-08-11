"""Shared input validation for DarvaX primitives (DX-2).

Every primitive validates its input the same way and fails loudly rather than
returning a quietly-wrong answer. Two rules matter most:

* **Chronological order is required and checked.** Silently accepting a reversed
  series would invert every measurement here, so order is validated rather than
  trusted. Both of ATHENA's read methods already return oldest-first —
  ``get_candles`` orders ascending, and ``list_candles_recent`` selects the most
  recent N descending and then reverses them — so a caller passing either
  straight through is correct and must **not** reverse.
* **Single instrument, single timeframe.** Mixing instruments or timeframes into
  one series would produce a meaningless box or swing.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.domain.market import Candle
from athena.errors import AthenaError


class DarvaxPrimitiveError(AthenaError):
    """Invalid input to a DarvaX primitive. Never raised for a merely
    insufficient-history case — those return an explicit empty/None result so
    the caller can distinguish "cannot know yet" from "you called me wrong"."""


def require_chronological_candles(
    candles: Sequence[Candle], *, minimum: int = 1, what: str = "primitive"
) -> None:
    """Validate a candle series before measuring anything from it."""
    if len(candles) < minimum:
        raise DarvaxPrimitiveError(
            f"{what} needs at least {minimum} candle(s), got {len(candles)}"
        )
    first = candles[0]
    for i in range(1, len(candles)):
        current, previous = candles[i], candles[i - 1]
        if current.instrument_id != first.instrument_id:
            raise DarvaxPrimitiveError(
                f"{what} requires a single instrument; found "
                f"{first.instrument_id!r} and {current.instrument_id!r}"
            )
        if current.timeframe != first.timeframe:
            raise DarvaxPrimitiveError(
                f"{what} requires a single timeframe; found "
                f"{first.timeframe.value} and {current.timeframe.value}"
            )
        if current.ts_open <= previous.ts_open:
            raise DarvaxPrimitiveError(
                f"{what} requires candles oldest-first with strictly increasing "
                f"timestamps; index {i} ({current.ts_open.isoformat()}) is not "
                f"after index {i - 1} ({previous.ts_open.isoformat()}). "
                "ATHENA's get_candles() and list_candles_recent() both already "
                "return oldest-first — pass them through without reversing."
            )


def require_positive(value: Decimal | int, *, name: str) -> None:
    if value <= 0:
        raise DarvaxPrimitiveError(f"{name} must be > 0, got {value}")


def mean(values: Sequence[Decimal]) -> Decimal:
    """Exact Decimal mean — no float anywhere in the arithmetic."""
    if not values:
        raise DarvaxPrimitiveError("mean() of an empty sequence")
    return sum(values, Decimal(0)) / Decimal(len(values))
