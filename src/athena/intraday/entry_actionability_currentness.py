"""Entry Actionability read-time currentness (ID-7A; ADR-015/ID-7A0.1's
dimension B, frozen further by ID-7B.2/ID-7B.2.1).

`is_currently_usable(...)` is a pure, deterministic, injectable-clock
function — never a repository query, provider call, or hidden global
clock read (ID-7A authorization item 19). It answers a strictly
read-time question ("is this historical artifact still usable right
now?") that is architecturally independent of, and never mutates, the
persisted `EntryActionabilityState` (dimension A, `entry_actionability_models.py`)
— a persisted `ACTIONABLE` row remains `ACTIONABLE` forever; only this
function's own return value changes as `now` advances. No currentness
label is ever written back into the domain object or any table column.

Frozen rule (ID-7B.2 §14, corrected by ID-7B.2.1 §29; ID-7A.2 made the
current-Decision half of this rule an explicit, independent check rather
than one inferred merely from EQ-identity agreement):

    persisted state == ACTIONABLE
    AND entry_actionability.decision_id == current_decision_id
    AND bound EntryQualification identity is still the exact current
        one (full composite-key equality — never decision_id alone,
        per ID-7A authorization item 20)
    AND now - evidence_as_of <= CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS
        (10 minutes / 2 completed M5 intervals)
    AND current session phase == REGULAR

Both identity checks are mandatory and independent (ID-7A.2): a real
canonical-cycle transition can persist a new Decision `D2` before a
fresh `EntryQualification` for it has been produced, so a caller
resolving "latest EQ" during that transient window may still receive
`EQ1` bound to the now-superseded `D1`. Comparing EQ identity alone
would then incorrectly classify an artifact bound to `D1`/`EQ1` as
current merely because `EQ1` still reads back as "the latest EQ" —
`current_decision_id` closes that gap by requiring the artifact's own
`decision_id` to independently agree with whatever Decision the caller
asserts is current right now.

The exact-identity comparisons are deliberately structured so that
mixing `A1` (bound to `D1`/`EQ1`) with a caller-supplied "latest"
`D2`/`EQ2` identity is either impossible or fully explicit (ID-7A
authorization item 20) — callers must supply both the *current*
Decision id and the *current* EQ identity themselves (via, e.g., a
`latest_entry_qualification_for_instrument_session` repository call and
whatever resolves the current canonical Decision, both made outside
this pure function); this module never resolves either itself, and
never queries a repository or provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, unique

from athena.intraday.entry_actionability_models import (
    CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS,
    EntryActionability,
    EntryActionabilityState,
)
from athena.session.models import SessionPhase


@dataclass(frozen=True, slots=True)
class EntryQualificationIdentity:
    """The exact composite identity of one `EntryQualification`
    observation — the same 5-column key the real
    `entry_qualifications` table's primary key uses. Passed explicitly
    by the caller as "the current one" for comparison; never resolved
    by this module."""

    instrument_id: str
    session_date: date
    as_of: datetime
    decision_id: str
    methodology_version: str

    def __post_init__(self) -> None:
        """ID-7A.1: structural validation matching the persisted EQ
        identity's own conventions — a caller-supplied "current" identity
        that is itself malformed must fail loudly here, never silently
        produce a SUPERSEDED verdict via a spurious equality mismatch."""
        for name in ("instrument_id", "decision_id", "methodology_version"):
            if not getattr(self, name):
                raise ValueError(f"EntryQualificationIdentity.{name} is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("EntryQualificationIdentity.as_of must be timezone-aware")


def bound_entry_qualification_identity(
    entry_actionability: EntryActionability,
) -> EntryQualificationIdentity:
    """The exact upstream `EntryQualification` identity `entry_actionability`
    itself is bound to (its own copied-verbatim EQ key) — for comparison
    against a caller-supplied *current* identity via `is_currently_usable`."""
    return EntryQualificationIdentity(
        instrument_id=entry_actionability.instrument_id,
        session_date=entry_actionability.session_date,
        as_of=entry_actionability.entry_qualification_as_of,
        decision_id=entry_actionability.decision_id,
        methodology_version=entry_actionability.entry_qualification_methodology_version,
    )


@unique
class EntryActionabilityCurrentness(str, Enum):
    """Derived, read-time-only classification (dimension B). Never
    persisted — see this module's own docstring. Naming is illustrative
    per ADR-015/ID-7A0.1; a future ID-7A/ID-7E consumer may rename these
    without touching the persisted `EntryActionabilityState` vocabulary,
    since the two are architecturally independent."""

    #: Persisted state != ACTIONABLE — the question "is it currently
    #: usable" does not apply; there was never an actionable verdict.
    METHODOLOGY_NOT_ACTIONABLE = "METHODOLOGY_NOT_ACTIONABLE"
    #: All four conditions hold right now.
    CURRENT = "CURRENT"
    #: Bound EQ identity no longer matches the current one for this
    #: instrument/session — a newer Decision/EQ pair has since appeared.
    SUPERSEDED = "SUPERSEDED"
    #: now - evidence_as_of exceeds CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS.
    STALE = "STALE"
    #: Current session phase is not REGULAR right now.
    SESSION_CLOSED = "SESSION_CLOSED"


@dataclass(frozen=True, slots=True)
class CurrentnessResult:
    """The read-time verdict plus a human-readable, non-persisted
    explanation (never an `EntryActionabilityReasonCode` — that
    vocabulary describes persisted methodology only)."""

    status: EntryActionabilityCurrentness
    explanation: str


def is_currently_usable(
    entry_actionability: EntryActionability,
    *,
    current_decision_id: str,
    current_entry_qualification_identity: EntryQualificationIdentity,
    current_session_phase: SessionPhase,
    now: datetime,
) -> CurrentnessResult:
    """Pure, deterministic, injected-clock currentness evaluation.

    Performs no repository query, no provider call, and no hidden
    ``datetime.now()``/global-clock read — every input the rule needs
    (the current canonical Decision id, the current EQ identity, the
    current session phase, and ``now``) must be supplied explicitly by
    the caller. Never mutates or re-derives ``entry_actionability``
    itself.

    ``current_decision_id`` and ``current_entry_qualification_identity``
    are validated and compared independently (ID-7A.2) — EQ-identity
    agreement alone does not prove the artifact's Decision is still
    current, since a canonical-cycle transition can persist a new
    Decision before a fresh EQ for it exists (see this module's own
    docstring for the concrete lag scenario).

    Validation order (deterministic): input shape/timestamp validation,
    then the temporal-impossibility check, then persisted-state
    applicability, then current-Decision identity, then current-EQ
    identity, then evidence freshness, then session usability.
    """
    if not current_decision_id:
        raise ValueError("is_currently_usable current_decision_id is mandatory")
    if now.tzinfo is None:
        raise ValueError("is_currently_usable now must be timezone-aware")

    # ID-7A.1: a caller asking currentness with `now` earlier than the
    # artifact's own evidence checkpoint has supplied a temporally
    # impossible read context — computing `now - evidence_as_of` would
    # yield a negative age that never exceeds the staleness threshold,
    # silently misclassifying future evidence as CURRENT. Reject the
    # invocation outright rather than inventing a new currentness label.
    if (
        entry_actionability.evidence_as_of is not None
        and now < entry_actionability.evidence_as_of
    ):
        raise ValueError(
            f"is_currently_usable now ({now.isoformat()}) precedes "
            f"evidence_as_of ({entry_actionability.evidence_as_of.isoformat()}) — "
            "temporally impossible read context"
        )

    if entry_actionability.state is not EntryActionabilityState.ACTIONABLE:
        return CurrentnessResult(
            status=EntryActionabilityCurrentness.METHODOLOGY_NOT_ACTIONABLE,
            explanation=(
                f"persisted state is {entry_actionability.state.value}, not ACTIONABLE — "
                "currentness is not applicable"
            ),
        )

    # ID-7A.2: current-Decision identity is checked independently of, and
    # before, current-EQ identity — never inferred merely from EQ
    # agreement (see module docstring's Decision->EQ lag scenario).
    if entry_actionability.decision_id != current_decision_id:
        return CurrentnessResult(
            status=EntryActionabilityCurrentness.SUPERSEDED,
            explanation=(
                "bound Decision no longer matches the current one for this "
                f"instrument (bound_decision_id={entry_actionability.decision_id!r}, "
                f"current_decision_id={current_decision_id!r})"
            ),
        )

    bound_identity = bound_entry_qualification_identity(entry_actionability)
    if bound_identity != current_entry_qualification_identity:
        return CurrentnessResult(
            status=EntryActionabilityCurrentness.SUPERSEDED,
            explanation=(
                "bound EntryQualification identity no longer matches the current "
                f"one for this instrument/session (bound={bound_identity!r}, "
                f"current={current_entry_qualification_identity!r})"
            ),
        )

    # ACTIONABLE requires evidence_as_of (enforced by
    # EntryActionability.__post_init__), so this is never None here.
    assert entry_actionability.evidence_as_of is not None
    age_seconds = (now - entry_actionability.evidence_as_of).total_seconds()
    if age_seconds > CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS:
        return CurrentnessResult(
            status=EntryActionabilityCurrentness.STALE,
            explanation=(
                f"now - evidence_as_of = {age_seconds:.1f}s exceeds the frozen "
                f"{CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS:.1f}s currentness band"
            ),
        )

    if current_session_phase is not SessionPhase.REGULAR:
        return CurrentnessResult(
            status=EntryActionabilityCurrentness.SESSION_CLOSED,
            explanation=f"current session phase is {current_session_phase.value}, not REGULAR",
        )

    return CurrentnessResult(
        status=EntryActionabilityCurrentness.CURRENT,
        explanation=(
            "persisted ACTIONABLE, current Decision and exact EQ identity both "
            "current, within freshness band, REGULAR session"
        ),
    )
