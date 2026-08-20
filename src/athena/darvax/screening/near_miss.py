"""DarvaX's own near-miss digest (AUX-4b).

**Not a new computation.** ``distance_to_breakout_pct`` is already computed
and persisted on every ``ScreenResult`` (DX-3) -- it is the same field the
Levels view's "Approaching their level" zone already reads (``darvax.js``'s
``LEVELS_APPROACHING``). That zone is a top-N slice for a live UI; this is a
threshold for a written digest, so the two intentionally differ in shape
while reading the same underlying number.

**The buy level uses the same trigger-then-ceiling fallback as everywhere
else in DarvaX** (``engine.py``'s ``distance_to_breakout``): DX-3 only sets
``trigger_price`` alongside a stop, so it is populated on almost no WATCH row
-- measured on a real sweep, 484 WATCH rows carry a distance and precisely
zero of them carry a trigger_price; all 484 are measured to the box ceiling.
An earlier version of this filter required ``trigger_price`` specifically and
silently discarded all 37 real near-misses a real sweep actually had --
caught only by checking the real distribution, not by any unit test, since a
synthetic fixture can supply whichever field a test author happens to think
of. ``buy_level_basis`` records which one was used, exactly like
``breakout_reference`` does upstream, so the digest never states a level
without saying where it came from.

Scoped to WATCH-tier signals that have **not yet crossed** the buy level
(``distance_to_breakout_pct >= 0``): a negative distance means price is
already through it, which is what the ACTIONABLE tier already reports --
repeating it here as a "near miss" would misdescribe something that already
happened as something about to happen.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from athena.darvax.screening.models import DarvaxTier, ScreenResult


@dataclass(frozen=True, slots=True)
class NearMissCandidate:
    """One WATCH-tier signal sitting within the configured margin of its
    buy level, carrying nothing beyond what ScreenResult already persisted."""

    instrument_id: str
    symbol: str
    close: Decimal
    buy_level: Decimal
    buy_level_basis: str
    """``"trigger_price"`` or ``"box_top"`` -- mirrors ScreenResult's own
    ``breakout_reference`` so the digest never states a level without saying
    which one it is."""
    distance_to_breakout_pct: Decimal


def near_miss_candidates(
    results: Sequence[ScreenResult], *, max_pct: Decimal,
) -> tuple[NearMissCandidate, ...]:
    """WATCH-tier results within ``max_pct`` of their buy level, nearest first.

    The buy level is ``trigger_price`` when DX-3 set one, else the box
    ceiling -- the same fallback ``distance_to_breakout_pct`` was itself
    measured against, so the level shown and the distance shown always agree
    about what they are describing.
    """
    out: list[NearMissCandidate] = []
    for r in results:
        if r.tier is not DarvaxTier.WATCH:
            continue
        if r.distance_to_breakout_pct is None:
            continue
        buy_level = r.trigger_price if r.trigger_price is not None else r.box_top
        if buy_level is None:
            continue
        pct = r.distance_to_breakout_pct
        if pct < 0 or pct > max_pct:
            continue
        out.append(NearMissCandidate(
            instrument_id=r.instrument_id,
            symbol=r.instrument_id.split(":")[-1],
            close=r.close,
            buy_level=buy_level,
            buy_level_basis=r.breakout_reference or "trigger_price",
            distance_to_breakout_pct=pct,
        ))
    out.sort(key=lambda c: c.distance_to_breakout_pct)
    return tuple(out)
