"""DarvaX's own EMA, for the stop ladder (DX-3).

ATHENA already computes EMAs. DarvaX deliberately re-derives its own instead of
reading ATHENA's persisted indicator artifacts — ADR-010 §Consequences records
this duplication as an accepted, deliberate cost:

    Cost of isolation, accepted deliberately: DarvaX re-derives some indicator
    values ATHENA already computes (EMAs in particular) rather than reading
    ATHENA's persisted indicator artifacts. This duplication is the price of the
    one-way dependency rule and is preferred to coupling.

Standard EMA, in exact ``Decimal`` arithmetic:

* multiplier ``k = 2 / (period + 1)``
* seed = simple mean of the first ``period`` closes
* thereafter ``ema = close * k + previous_ema * (1 - k)``

Pure function: no clock, no config, no state.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax.primitives import DarvaxPrimitiveError
from athena.darvax.primitives._guards import require_chronological_candles
from athena.domain.market import Candle


def ema_series(closes: Sequence[Decimal], period: int) -> tuple[Decimal, ...]:
    """EMA values aligned to ``closes``, with ``None``-free tail semantics.

    The returned tuple has one entry per input from index ``period - 1``
    onward — i.e. length ``len(closes) - period + 1``. Nothing is emitted for
    bars before the seed window, because no EMA exists there and inventing one
    would fabricate a level a stop could be placed at.
    """
    if period < 1:
        raise DarvaxPrimitiveError(f"EMA period must be >= 1, got {period}")
    if len(closes) < period:
        raise DarvaxPrimitiveError(
            f"EMA({period}) needs at least {period} closes, got {len(closes)}"
        )

    k = Decimal(2) / Decimal(period + 1)
    seed = sum(closes[:period], Decimal(0)) / Decimal(period)
    values = [seed]
    for close in closes[period:]:
        values.append(close * k + values[-1] * (Decimal(1) - k))
    return tuple(values)


def latest_ema(candles: Sequence[Candle], period: int) -> Decimal | None:
    """EMA of closes at the final bar, or ``None`` when history is too short.

    Returns ``None`` rather than raising for insufficient history: "we cannot
    know this EMA yet" is a legitimate state a caller must be able to report
    honestly, not a programming error.
    """
    if period < 1:
        raise DarvaxPrimitiveError(f"EMA period must be >= 1, got {period}")
    require_chronological_candles(candles, minimum=1, what="latest_ema")
    if len(candles) < period:
        return None
    return ema_series([bar.close for bar in candles], period)[-1]
