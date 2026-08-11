"""DarvaX signal artifacts (DX-3).

A ``DarvaxSignal`` is **not** an ATHENA ``Decision`` and must never be converted
into one (ADR-010 §Consequences). The two lanes are visually comparable to the
owner but computationally disjoint: ATHENA's decision pipeline cannot read these
records, and DarvaX never writes an ATHENA artifact.

Every signal carries its own **computed, persisted explanation** plus a
structured evidence trace, following ADR-005's principle that the engine which
produced a value also produces its rationale as data. A UI renders these; it
never recomputes or reconstructs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class DarvaxSignalType(str, Enum):
    """Structural state of price relative to its topmost Darvas box.

    Names are deliberately **descriptive, not imperative** — ``BREAKOUT`` rather
    than ``BUY``. ATHENA is advisory-only and places no orders; DarvaX is an
    unvalidated experimental lane on top of that. The Darvas rule each state
    corresponds to is recorded separately in :class:`DarvasRule`, which keeps the
    attribution faithful without this module emitting order-like instructions.
    """

    NO_BOX = "NO_BOX"
    """Not enough structure yet for any box to have completed."""
    INSIDE_TOPMOST_BOX = "INSIDE_TOPMOST_BOX"
    """Price is within the topmost box — Darvas rule A territory."""
    BREAKOUT = "BREAKOUT"
    """Close cleared the topmost box ceiling — Darvas rule B territory."""
    BREAKOUT_RETEST = "BREAKOUT_RETEST"
    """Cleared the ceiling, came back to test it, and held above it (deck p.28)."""
    BELOW_BOX_BOTTOM = "BELOW_BOX_BOTTOM"
    """Close fell beneath the box floor — Darvas rule C territory."""
    NOT_IN_TOPMOST_BOX = "NOT_IN_TOPMOST_BOX"
    """The latest completed box is not the highest — Darvas rule D territory."""


class DarvasRule(str, Enum):
    """The DAR-CARD rule a state corresponds to, quoted from deck p.67."""

    A_HOLD_WHILE_IN_TOPMOST_BOX = "A"
    B_BUY_ABOVE_TOPMOST_BOX = "B"
    C_SELL_BELOW_NEW_BOX_BOTTOM = "C"
    D_NO_REASON_OUTSIDE_TOPMOST_BOX = "D"


#: Verbatim rule text from the deck's reproduction of Darvas' own DAR-CARD
#: (p.67), so a persisted explanation can quote its source rather than
#: paraphrase it.
DAR_CARD_TEXT: dict[DarvasRule, str] = {
    DarvasRule.A_HOLD_WHILE_IN_TOPMOST_BOX: (
        "A stock is in a rising trend when it is in its topmost box. As long as "
        "it remains there its price fluctuations should be ignored and the stock "
        "is a HOLD."
    ),
    DarvasRule.B_BUY_ABOVE_TOPMOST_BOX: (
        "If the price of the stock moves above the top of this topmost box the "
        "stock becomes a BUY. A 10 percent stop-loss should be set on the first "
        "breakout."
    ),
    DarvasRule.C_SELL_BELOW_NEW_BOX_BOTTOM: (
        "Having formed a new higher box, if the price falls below the bottom "
        "into the shaded area of this box the stock is a SELL."
    ),
    DarvasRule.D_NO_REASON_OUTSIDE_TOPMOST_BOX: (
        "There is no reason to HOLD or BUY a stock that is not in its topmost box."
    ),
}


class StopBasis(str, Enum):
    """Which documented stop rule produced a stop level."""

    CANONICAL_DARVAS_PCT = "CANONICAL_DARVAS_PCT"
    """Percentage below entry, Darvas' own rule B (deck p.67, 10%)."""
    DARVAX_TIGHT_PCT = "DARVAX_TIGHT_PCT"
    """Percentage below entry, DarvaX's tighter variant (deck p.44, 1%)."""
    EMA_LADDER = "EMA_LADDER"
    """Close-below-EMA for the configured horizon (deck p.9)."""


@dataclass(frozen=True, slots=True)
class DarvaxStop:
    """A computed stop level and exactly how it was derived."""

    basis: StopBasis
    price: Decimal
    reference_price: Decimal
    """The entry reference the stop was measured from."""
    detail: str
    """Human-readable derivation, persisted rather than recomputed."""
    ema_period: int | None = None
    """Populated only for EMA_LADDER."""
    pct: Decimal | None = None
    """Populated only for the percentage bases."""


@dataclass(frozen=True, slots=True)
class SignalEvidence:
    """One named measurement behind a signal.

    Persisted so the ``/darvax/`` surface (DX-4) can show *why* a signal reads
    the way it does without re-running any measurement — ADR-005's
    explainability-as-data principle, applied inside the satellite.
    """

    name: str
    value: str
    detail: str


@dataclass(frozen=True, slots=True)
class DarvaxSignal:
    """One DarvaX observation for one instrument at one bar.

    Never an ATHENA ``Decision``; never readable by ATHENA's pipeline.
    ``signal_id`` is derived deterministically from instrument + ``as_of``, so
    re-running the engine over the same data yields the same id and persistence
    is idempotent — a replay cannot silently duplicate history.
    """

    signal_id: str
    instrument_id: str
    as_of: datetime
    signal_type: DarvaxSignalType
    darvas_rule: DarvasRule | None
    close: Decimal
    explanation: str
    evidence: tuple[SignalEvidence, ...]
    methodology_digest: str
    """Digest of the DarvaX methodology config that produced this signal."""
    darvax_version: str
    box_top: Decimal | None = None
    box_bottom: Decimal | None = None
    box_is_topmost: bool | None = None
    trigger_price: Decimal | None = None
    """Entry trigger: the prior bar's high, per the deck's "Enter above the
    Previous Day High Price" rule (p.44). None when no entry is in view."""
    stop: DarvaxStop | None = None
    status: str = "EXPERIMENTAL_UNVALIDATED"
    """Fixed label until DX-5 produces validation evidence. The source deck
    ships none, so nothing here may present itself as validated."""
