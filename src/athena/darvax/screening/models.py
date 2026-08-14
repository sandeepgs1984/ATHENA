"""Screener domain objects (DX-6a, ADR-010 Amendment 2).

The central design commitment, stated here because every other choice follows
from it: **eligibility is a classification, never a score.**

DarvaX output is ``EXPERIMENTAL_UNVALIDATED`` and the source deck ships no
backtest evidence of any kind. A composite 0-100 "DarvaX score" would
manufacture precision the methodology cannot support, so none exists. A tier is
a pure function of the signal's structural state mapped onto Darvas' own
DAR-CARD rules, and ranking uses individually named, individually displayed
measurements — no blended index, no hidden weighting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from athena.darvax.signals.models import DarvasRule, DarvaxSignalType


class DarvaxTier(str, Enum):
    """Eligibility tier — a rename of the DAR-CARD rule, adding no judgement."""

    ACTIONABLE = "ACTIONABLE"
    """Price cleared the topmost box ceiling. Darvas rule B territory."""
    WATCH = "WATCH"
    """Coiled inside the topmost box — a breakout candidate. Rule A territory."""
    EXIT_RELEVANT = "EXIT_RELEVANT"
    """Fell beneath the box floor. Rule C territory; matters only if held."""
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    """No Darvas reason to act — rule D, or no box formed at all."""


#: The whole taxonomy, in one place. Every state the DX-3 engine can emit maps
#: to exactly one tier, so a new state cannot be silently unclassified — the
#: lookup in ``tier_for`` raises rather than defaulting.
_TIER_BY_STATE: dict[DarvaxSignalType, DarvaxTier] = {
    DarvaxSignalType.BREAKOUT: DarvaxTier.ACTIONABLE,
    DarvaxSignalType.BREAKOUT_RETEST: DarvaxTier.ACTIONABLE,
    DarvaxSignalType.INSIDE_TOPMOST_BOX: DarvaxTier.WATCH,
    DarvaxSignalType.BELOW_BOX_BOTTOM: DarvaxTier.EXIT_RELEVANT,
    DarvaxSignalType.NOT_IN_TOPMOST_BOX: DarvaxTier.NOT_ELIGIBLE,
    DarvaxSignalType.NO_BOX: DarvaxTier.NOT_ELIGIBLE,
}


@dataclass(frozen=True, slots=True)
class ScreenResult:
    """One instrument's place in one screen.

    Every field here is **computed once and persisted** (ADR-005): the API
    serialises it and the UI renders it, and neither recomputes a tier or a
    distance. That is what makes a screen replayable and auditable rather than
    merely re-runnable.
    """

    sweep_id: str
    instrument_id: str
    signal_id: str
    tier: DarvaxTier
    signal_type: DarvaxSignalType
    darvas_rule: DarvasRule | None
    rank: int
    """Position within the tier under the default ordering. 1-based."""
    close: Decimal
    explanation: str
    box_top: Decimal | None = None
    box_bottom: Decimal | None = None
    trigger_price: Decimal | None = None
    distance_to_trigger_pct: Decimal | None = None
    """``(trigger - close) / close * 100``. Negative means price is already
    through the trigger. ``None`` when the signal carries no trigger."""
    box_height_pct: Decimal | None = None
    """``(top - bottom) / bottom * 100``. Darvas favoured tight boxes."""


@dataclass(frozen=True, slots=True)
class SweepRecord:
    """One screening run, recorded so the screen it produced can be reproduced.

    ``methodology_digest`` is captured per sweep because changing any
    methodology value changes it. Without that, an old screen would silently
    appear to have been produced by the current settings — a 10% stop screen
    read as though it were a 1% stop screen.
    """

    sweep_id: str
    started_at: datetime
    state: str
    """``running`` | ``completed`` | ``cancelled`` | ``failed``."""
    methodology_digest: str
    darvax_version: str
    requested: int
    evaluated: int
    tier_counts: dict[DarvaxTier, int]
    skipped: tuple[tuple[str, str], ...] = ()
    """``(instrument_id, reason)`` pairs — surfaced, never silently dropped."""
    finished_at: datetime | None = None
    as_of: datetime | None = None
    partial: bool = False
    """True when the sweep was cancelled: results are kept and labelled, since
    discarding completed work would be worse than reporting it as partial."""
