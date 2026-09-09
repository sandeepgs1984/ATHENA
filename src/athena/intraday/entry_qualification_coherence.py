"""EntryQualification read-time coherence (ID-11).

`resolve_entry_qualification_coherence(...)` answers a strictly read-time
question -- "does this persisted EntryQualification row still describe the
exact current canonical Decision?" -- for a caller (the ID-11 read-only API
service) that, unlike the canonical per-cycle workflow, cannot assume the EQ
it just fetched came from the very same synchronous cycle as the Decision it
is paired with.

This is semantics extraction, not new methodology: every check below is the
same identity/session/point-in-time coherence
`portfolio/sync.py::_latest_coherent_entry_qualification` already performs
(Owner-approved Portfolio Sync track), minus that function's own
Portfolio-specific `_decision_matches_price_session` precondition -- ID-11
resolves its Decision directly by `decision_id` and has no separate "holding
price session" to reconcile against, so that precondition does not
generalize here.

Deliberately named COHERENCE, not CURRENTNESS: unlike `EntryActionability`'s
own `is_currently_usable(...)` (`entry_actionability_currentness.py`), there
is no frozen age-based staleness threshold for `EntryQualification` anywhere
in approved methodology, and none is invented here. The result is a plain
binary identity/session/point-in-time fact, never a graded staleness label.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, tzinfo
from enum import Enum, unique

from athena.domain.decision import Decision
from athena.intraday.entry_qualification_models import EntryQualification


@unique
class EntryQualificationCoherence(str, Enum):
    """Read-time-only classification -- never persisted, mirrors
    `EntryActionabilityCurrentness`'s own "derived, not a domain state"
    discipline. Exactly two values: this is an identity/session/PIT fact,
    not a graded staleness spectrum."""

    COHERENT = "COHERENT"
    INCOHERENT = "INCOHERENT"


@dataclass(frozen=True, slots=True)
class EntryQualificationCoherenceResult:
    """The read-time verdict plus a human-readable, non-persisted
    explanation -- mirrors `entry_actionability_currentness.CurrentnessResult`'s
    own shape exactly."""

    status: EntryQualificationCoherence
    explanation: str


def _incoherent(reason: str) -> EntryQualificationCoherenceResult:
    return EntryQualificationCoherenceResult(
        status=EntryQualificationCoherence.INCOHERENT, explanation=reason
    )


def resolve_entry_qualification_coherence(
    eq: EntryQualification | None,
    decision: Decision,
    *,
    read_checkpoint: datetime,
    market_timezone: tzinfo,
) -> EntryQualificationCoherenceResult:
    """Pure, deterministic. Performs no repository query, no provider call,
    no hidden clock read -- `eq` and `decision` must already be resolved by
    the caller (mirrors `is_currently_usable`'s own "caller resolves
    identity, this function only compares" discipline).

    Checks, exact frozen order (semantics-extracted from
    `portfolio/sync.py::_latest_coherent_entry_qualification`):

    1. `eq` exists.
    2. instrument identity matches `decision`.
    3. `decision_id` matches.
    4. `run_id`/`cycle_id` match.
    5. `decision_type` matches.
    6. `eq.session_date` matches the read-checkpoint's own market-local
       session date.
    7. `eq.as_of`'s market-local date matches that same session date.
    8. `eq.as_of <= read_checkpoint` (point-in-time / not-future check).
    """
    if read_checkpoint.tzinfo is None:
        raise ValueError(
            "resolve_entry_qualification_coherence read_checkpoint must be timezone-aware"
        )

    if eq is None:
        return _incoherent("no EntryQualification observation is bound to this Decision")

    if eq.instrument_id != decision.instrument_id:
        return _incoherent(
            f"instrument mismatch (eq={eq.instrument_id!r}, decision={decision.instrument_id!r})"
        )
    if eq.decision_id != decision.decision_id:
        return _incoherent(
            f"decision_id mismatch (eq={eq.decision_id!r}, decision={decision.decision_id!r})"
        )
    if eq.run_id != decision.run_id or eq.cycle_id != decision.cycle_id:
        return _incoherent(
            f"run_id/cycle_id mismatch (eq=({eq.run_id!r}, {eq.cycle_id!r}), "
            f"decision=({decision.run_id!r}, {decision.cycle_id!r}))"
        )
    if eq.decision_type is not decision.decision_type:
        return _incoherent(
            f"decision_type mismatch (eq={eq.decision_type.value!r}, "
            f"decision={decision.decision_type.value!r})"
        )

    session_date = read_checkpoint.astimezone(market_timezone).date()
    if eq.session_date != session_date:
        return _incoherent(
            f"eq.session_date ({eq.session_date}) does not match the read-checkpoint's own "
            f"session date ({session_date})"
        )
    if eq.as_of.astimezone(market_timezone).date() != session_date:
        return _incoherent(
            f"eq.as_of's own market-local date does not match session date ({session_date})"
        )
    if eq.as_of > read_checkpoint:
        return _incoherent(
            f"eq.as_of ({eq.as_of.isoformat()}) is later than read_checkpoint "
            f"({read_checkpoint.isoformat()}) -- temporally impossible read context"
        )

    return EntryQualificationCoherenceResult(
        status=EntryQualificationCoherence.COHERENT,
        explanation="instrument/decision/run/cycle/decision_type/session/PIT all coherent",
    )
