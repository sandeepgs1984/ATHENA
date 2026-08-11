"""Stop-level computation for the three documented DarvaX policies (DX-3).

The source deck contradicts itself on stop sizing, and ADR-010 §8 deliberately
declines to settle it in code:

* **canonical_darvas** — "A 10 percent stop-loss should be set on the first
  breakout" (Darvas' own rule B, deck p.67). This is the shipped default because
  it is the attributable, canonical rule.
* **darvax_tight** — "Keep 1% Stop Loss Below Above Entry" (deck p.44). Noted in
  ADR-010's context as implausibly tight for a breakout entry: a 1% stop is
  removed by ordinary noise. Selectable, not recommended, and DX-5's evidence
  decides.
* **ema_ladder** — "Price Should Close Below EMA on DCB for Exits" across the
  5/10/20/200 rungs by horizon (deck p.9). Note this is a *close-below* exit
  rule, not an intraday stop level: the returned price is the EMA itself, and
  the exit condition is a close beneath it.

Both percentage policies measure from the **entry reference**, which is the
deck's own entry trigger — the prior bar's high (p.44) — falling back to the
latest close when no trigger is in view. The chosen reference is recorded on the
result so the derivation is never ambiguous.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax.config import DarvaxMethodologyConfig
from athena.darvax.signals.ema import latest_ema
from athena.darvax.signals.models import DarvaxStop, StopBasis
from athena.domain.market import Candle

_TWO_PLACES = Decimal("0.01")


def _quantize(value: Decimal) -> Decimal:
    """Round to paise. Stops are prices the owner may act on, so they are
    presented at real tick granularity rather than as long decimal tails."""
    return value.quantize(_TWO_PLACES)


def compute_stop(
    candles: Sequence[Candle],
    methodology: DarvaxMethodologyConfig,
    *,
    reference_price: Decimal,
) -> DarvaxStop | None:
    """The stop level implied by the configured policy.

    Returns ``None`` only for ``ema_ladder`` when history is shorter than the
    configured EMA period — an honest "cannot know this level yet" rather than a
    fabricated stop.
    """
    policy = methodology.stop_policy

    if policy == "canonical_darvas":
        pct = methodology.canonical_stop_pct
        price = _quantize(reference_price * (Decimal(1) - pct / Decimal(100)))
        return DarvaxStop(
            basis=StopBasis.CANONICAL_DARVAS_PCT,
            price=price,
            reference_price=reference_price,
            pct=pct,
            detail=(
                f"{pct}% below the entry reference {reference_price} = {price}. "
                "Darvas' canonical first-breakout stop (deck p.67)."
            ),
        )

    if policy == "darvax_tight":
        pct = methodology.tight_stop_pct
        price = _quantize(reference_price * (Decimal(1) - pct / Decimal(100)))
        return DarvaxStop(
            basis=StopBasis.DARVAX_TIGHT_PCT,
            price=price,
            reference_price=reference_price,
            pct=pct,
            detail=(
                f"{pct}% below the entry reference {reference_price} = {price}. "
                "DarvaX's tighter variant (deck p.44); note ADR-010 records this "
                "as implausibly tight for a breakout entry."
            ),
        )

    # ema_ladder
    horizon = methodology.breakout.stop_horizon
    period = methodology.ema_stop_ladder[horizon]
    ema = latest_ema(candles, period)
    if ema is None:
        return None
    price = _quantize(ema)
    return DarvaxStop(
        basis=StopBasis.EMA_LADDER,
        price=price,
        reference_price=reference_price,
        ema_period=period,
        detail=(
            f"{period} EMA = {price} for the {horizon!r} horizon. Exit rule is a "
            "close below this level on a daily closing basis, not an intraday "
            "trigger (deck p.9)."
        ),
    )
