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


class DarvaxAction(str, Enum):
    """What the owner would do about this instrument, in trading words (DX-7a).

    A tier says *what the price is doing*; an action says *what that implies*.
    They are separate because the mapping is not always one-to-one — the same
    ``EXIT_RELEVANT`` tier means "get out" if the instrument is held and nothing
    at all if it is not.

    **Still not a score.** Each action is a pure function of the signal state
    (plus, from DX-7b, whether a position is recorded), so it carries exactly
    the judgement the DAR-CARD rules carry and no more.
    """

    ENTER = "ENTER"
    """Rule B satisfied — price cleared the topmost box ceiling."""
    ENTER_ON_RETEST = "ENTER_ON_RETEST"
    """Broke out and has returned to test the ceiling as support."""
    WAIT = "WAIT"
    """Rule A — coiled inside the topmost box. Nothing to do until it clears."""
    EXIT_IF_HELD = "EXIT_IF_HELD"
    """Rule C fired. Deliberately conditional: DarvaX does not know what is
    held until DX-7b, and an unconditional "EXIT" for an instrument the owner
    never bought would be advice about a position that does not exist.

    DX-7b **adds** ``HOLD`` and a position-confirmed ``EXIT`` beside this value
    rather than renaming it, so sweeps stored by DX-7a stay readable."""
    NO_ENTRY = "NO_ENTRY"
    """Rule D, or no box at all. No Darvas reason to act."""
    HOLD = "HOLD"
    """Held, and rule A applies — *"As long as it remains [in its topmost box]
    its price fluctuations should be ignored and the stock is a HOLD."* (DX-7b)"""
    EXIT = "EXIT"
    """Held, and the methodology says get out: the stop was breached, rule C
    fired, or rule D applies — *"There is no reason to HOLD or BUY a stock that
    is not in its topmost box."* Distinct from ``EXIT_IF_HELD``, which is what
    DarvaX says when it has no position on record. (DX-7b)"""


#: Action per signal state. Kept beside the tier map, and total for the same
#: reason: an unmapped state must raise rather than default to something
#: actionable.
_ACTION_BY_STATE: dict[DarvaxSignalType, DarvaxAction] = {
    DarvaxSignalType.BREAKOUT: DarvaxAction.ENTER,
    DarvaxSignalType.BREAKOUT_RETEST: DarvaxAction.ENTER_ON_RETEST,
    DarvaxSignalType.INSIDE_TOPMOST_BOX: DarvaxAction.WAIT,
    DarvaxSignalType.BELOW_BOX_BOTTOM: DarvaxAction.EXIT_IF_HELD,
    DarvaxSignalType.NOT_IN_TOPMOST_BOX: DarvaxAction.NO_ENTRY,
    DarvaxSignalType.NO_BOX: DarvaxAction.NO_ENTRY,
}

#: Actions that propose putting money at risk. The UI must carry the
#: `EXPERIMENTAL_UNVALIDATED` badge on these specifically (design §4, decision
#: 3b) — named here so "which chips need the warning" is answered by the domain
#: rather than re-decided in JavaScript.
RISK_BEARING_ACTIONS: frozenset[DarvaxAction] = frozenset(
    {DarvaxAction.ENTER, DarvaxAction.ENTER_ON_RETEST}
)


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
    action: DarvaxAction = DarvaxAction.NO_ENTRY
    """What to do about this instrument. Defaulted so the field can be added
    without rewriting every construction site, but always set by
    ``screen_signal``."""
    action_reason: str = ""
    """Why that action, citing the DAR-CARD rule and the numbers that drove it.

    Persisted rather than assembled in the browser: ADR-005 puts the explanation
    with the engine that produced the value. A UI that built this string would
    be free to drift from the rule the action actually came from."""
    action_reason_plain: str = ""
    """The same conclusion in plain English, naming no rule and no jargon.

    A second field rather than a rewrite (advisor UI design decision 1b): the
    technical sentence stays available for the reader who wants the methodology,
    and this one leads.

    **These two must not drift.** Both are produced at a single call site, and
    the invariant that keeps them honest is asserted in tests: the plain one
    contains no rule citation, the technical one does. Without that, they decay
    either into copies of each other or into two different claims about the same
    trade."""
    stop_price: Decimal | None = None
    """The level the methodology says to exit at, copied from the signal.

    Rule B **mandates** this — *"A 10 percent stop-loss should be set on the
    first breakout"* — and the screener could not show it: ``DarvaxSignal``
    carried a fully derived stop and ``ScreenResult`` never copied it, so a
    screen recommended entries without the exit that makes them survivable.
    Copied, never recomputed, so a stored screen keeps the level it was
    actually computed with (ADR-005)."""
    stop_basis: str | None = None
    """Which documented rule produced ``stop_price`` — so a stop is never a bare
    number whose origin nobody can state."""
    stop_vs_ceiling: Decimal | None = None
    """``stop_price - box_top``. Positive means the stop sits **above** the level
    price broke out from; negative means a stop-out gives the breakout back.

    Measured on a real sweep, the same 10% rule lands on both sides: XTRANET's
    stop was ₹4.40 above its ceiling, BI's ₹14.71 below. Materially different
    trades that DarvaX had no way to tell apart, because nothing compared the
    two levels it already held.

    Arithmetic on two persisted numbers, not a new rule — and persisted rather
    than derived in the browser because ADR-005 puts a computed value with the
    engine that computed it. ``None`` whenever either level is absent, which is
    every row that is not an entry."""
    stop_vs_ceiling_note: str = ""
    """The comparison in plain English, with no recommendation attached. It
    states where the stop lands; it does not say whether that is good."""
    liquidity_value: Decimal | None = None
    """Median daily traded value in rupees over the last 20 sessions (DX-10a).

    DarvaX's answer to "how big is this", because ATHENA holds no market-cap
    data at all — no capitalisation column, no share count, and a broker dump
    reporting ``last_price = 0`` for every row. Traded value is also the more
    useful question for a trader: capitalisation says how large the company is,
    this says whether the position can be exited.

    ``None`` means too little history to measure, which is distinct from
    illiquid and must not be filtered as though it were zero."""
    box_top: Decimal | None = None
    box_bottom: Decimal | None = None
    trigger_price: Decimal | None = None
    distance_to_trigger_pct: Decimal | None = None
    """``(trigger - close) / close * 100``. Negative means price is already
    through the trigger. ``None`` when the signal carries no trigger — which is
    most of the WATCH tier, since DX-3 only sets ``trigger_price`` alongside a
    stop. See ``distance_to_breakout_pct``."""
    distance_to_breakout_pct: Decimal | None = None
    """How far price is from the level that would satisfy Darvas rule B, as a
    percentage of close. **This is the ranking key.**

    Falls back from ``trigger_price`` to ``box_top`` because DX-3 leaves the
    trigger unset for inside-the-box signals: ranking on the trigger alone left
    the entire WATCH tier — the breakout candidates, the most useful tier —
    ordered alphabetically. The box ceiling is also the more faithful reference,
    since rule B is literally "a move above the topmost box top is a BUY"; the
    prior-day-high trigger is DarvaX's own entry refinement (deck p.44)."""
    breakout_reference: str | None = None
    """Which level ``distance_to_breakout_pct`` was measured to — ``trigger_price``
    or ``box_top``. Persisted so the UI can show what drove the order rather
    than leaving the reader to guess (ADR-005)."""
    box_height_pct: Decimal | None = None
    """``(top - bottom) / bottom * 100``. Darvas favoured tight boxes."""
    ema_50: Decimal | None = None
    """50-session EMA of the close (DX-12a). **Not a DAR-CARD rule** — a trend
    context the owner asked to add, layered on top of the classification the
    same way liquidity and box height are. ``None`` when fewer than 50 closes
    are available, never guessed."""
    ema_100: Decimal | None = None
    """100-session EMA of the close (DX-12a). Same independence from ``ema_50``
    as from every other field here: a newly listed instrument may have enough
    history for one and not the other, and each is reported on its own terms."""


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
