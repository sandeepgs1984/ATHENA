"""50/100-session EMA trend context (DX-12a).

**Not a Darvas rule.** The DAR-CARD is pure price-action — a box, a ceiling, a
break. Nowhere does it mention a moving average as a trend filter (the deck's
*only* EMA usage is the 5/10/20/200 stop ladder in ``signals/ema.py``/
``stops.py``, which is an *exit* rule, not this). This module exists because
the owner asked for it directly, exactly like DX-10a's liquidity and box-height
filters — a conviction overlay layered on top of the classification, never
folded into it. ``ScreenResult.tier``/``action`` stay a pure function of the
DAR-CARD states; trend is a separate, filterable dimension a reader can ignore
entirely.

**Reuses DarvaX's own EMA primitive** (``signals/ema.py``) rather than
introducing a second implementation — same Decimal arithmetic, same
insufficient-history-returns-None contract as the stop ladder already relies on.

**Accuracy caveat, inherited not introduced.** An EMA seeded from a short
window under-converges relative to one computed over years of history — the
existing EMA(200) "investor" stop rung already carries this same approximation,
fed from whatever ``scan.lookback_bars`` supplies (400 by default, a ~2x
warm-up for a 200-period EMA). This module's 50/100-period EMAs get the same
window and the same tradeoff; it is not a new problem, and previously it was
simply never surfaced as a value the owner reads at a glance the way this one
will be.

Pure functions over candles. No clock, no config, no IO.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from athena.darvax.signals.ema import latest_ema
from athena.domain.market import Candle

#: Trend-context periods. Distinct from ema_stop_ladder's 5/10/20/200 rungs —
#: those size an exit; these read a medium/long-term trend.
EMA_TREND_PERIOD_MEDIUM = 50
EMA_TREND_PERIOD_LONG = 100

#: The longer of the two, so callers reading one candle window can serve both
#: this module and liquidity.traded_value from a single per-instrument fetch.
TREND_LOOKBACK_BARS = EMA_TREND_PERIOD_LONG


@dataclass(frozen=True, slots=True)
class TrendReading:
    """Both EMAs for one instrument, or ``None`` fields where history is short."""

    ema_50: Decimal | None
    ema_100: Decimal | None


def trend_reading(candles: Sequence[Candle]) -> TrendReading:
    """EMA(50) and EMA(100) of closes at the final bar.

    Either field is ``None`` independently when there is not yet enough history
    for that period — a newly listed instrument may have 60 days of trading,
    enough for EMA(50) but not EMA(100), and both are reported honestly rather
    than either withheld together or guessed.
    """
    return TrendReading(
        ema_50=latest_ema(candles, EMA_TREND_PERIOD_MEDIUM),
        ema_100=latest_ema(candles, EMA_TREND_PERIOD_LONG),
    )


def trend_state(close: Decimal, reading: TrendReading) -> str | None:
    """Plain classification of where price sits relative to both EMAs.

    Returns ``None`` when either EMA is unmeasured — a partial reading (e.g.
    EMA(50) known, EMA(100) not) cannot honestly be called "above both" or
    "below both", so the filter and any badge must treat it as unmeasured
    rather than silently classifying on half the picture.

    Three states, not a score: ``"above_both"``, ``"below_both"``, ``"mixed"``.
    """
    if reading.ema_50 is None or reading.ema_100 is None:
        return None
    if close > reading.ema_50 and close > reading.ema_100:
        return "above_both"
    if close < reading.ema_50 and close < reading.ema_100:
        return "below_both"
    return "mixed"
