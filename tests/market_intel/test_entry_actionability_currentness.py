"""Entry Actionability read-time currentness (ID-7A; ADR-015/ID-7A0.1
dimension B, frozen further by ID-7B.2/ID-7B.2.1).

Proves `is_currently_usable` is a pure, deterministic, injected-clock
function that never mutates or is confused with the persisted
`EntryActionabilityState`, and that the exact 10-minute freshness
boundary, exact-EQ-identity comparison, and REGULAR-session requirement
are all implemented faithfully.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.domain.enums import DecisionType, Direction
from athena.intraday import (
    CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS,
    DEFAULT_METHODOLOGY_VERSION as EQ_DEFAULT_METHODOLOGY_VERSION,
    ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
    EntryActionability,
    EntryActionabilityCurrentness,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryEvidenceFinality,
    EntryLocationContext,
    EntryQualificationIdentity,
    EntryQualificationState,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
    bound_entry_qualification_identity,
    is_currently_usable,
)
from athena.session.models import SessionPhase

IST = ZoneInfo("Asia/Kolkata")
EQ_AS_OF = datetime(2026, 9, 4, 9, 45, tzinfo=IST)
EA_AS_OF = datetime(2026, 9, 4, 9, 50, tzinfo=IST)
EVIDENCE_AS_OF = datetime(2026, 9, 4, 9, 50, tzinfo=IST)
DAY = date(2026, 9, 4)


def _actionable_ea(*, evidence_as_of: datetime = EVIDENCE_AS_OF) -> EntryActionability:
    return EntryActionability(
        instrument_id="NSE:TEST",
        session_date=DAY,
        entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1",
        entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF,
        entry_actionability_methodology_version=ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
        decision_type=DecisionType.TRADE,
        direction=Direction.LONG,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        run_id="run-1",
        cycle_id="cycle-1",
        state=EntryActionabilityState.ACTIONABLE,
        reason_codes=(),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=evidence_as_of,
        entry_reference=EntryReference(price=Decimal("100.00"), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE),
        entry_location_context=EntryLocationContext(vwap=Decimal("99.50"), vwap_deviation_pct=Decimal("0.50")),
        operative_invalidation=OperativeInvalidation(level=Decimal("98.00"), basis=InvalidationBasis.VWAP_LOSS),
        reward=RewardReference(
            t1_price=Decimal("101.00"), t2_price=Decimal("101.50"), basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("0.5"), reward_risk_to_t2=Decimal("0.75"),
        ),
        opening_range_context=None,
        evaluated_at=EA_AS_OF,
        explanation="actionable test",
    )


def _not_actionable_ea() -> EntryActionability:
    return EntryActionability(
        instrument_id="NSE:TEST",
        session_date=DAY,
        entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1",
        entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF,
        entry_actionability_methodology_version=ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
        decision_type=DecisionType.TRADE,
        direction=Direction.LONG,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        run_id="run-1",
        cycle_id="cycle-1",
        state=EntryActionabilityState.NOT_ACTIONABLE,
        reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=None,
        entry_reference=None,
        entry_location_context=None,
        operative_invalidation=None,
        reward=None,
        opening_range_context=None,
        evaluated_at=EA_AS_OF,
        explanation="not actionable test",
    )


def _current_identity(ea: EntryActionability) -> EntryQualificationIdentity:
    return bound_entry_qualification_identity(ea)


def test_methodology_not_actionable_short_circuits_before_identity_or_age() -> None:
    ea = _not_actionable_ea()
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=EntryQualificationIdentity(
            instrument_id="NSE:OTHER", session_date=DAY, as_of=EQ_AS_OF,
            decision_id="other", methodology_version="other-v0",
        ),
        current_session_phase=SessionPhase.CLOSED,
        now=EA_AS_OF,
    )
    assert result.status is EntryActionabilityCurrentness.METHODOLOGY_NOT_ACTIONABLE


def test_current_when_all_four_conditions_hold() -> None:
    ea = _actionable_ea()
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.REGULAR,
        now=EVIDENCE_AS_OF,
    )
    assert result.status is EntryActionabilityCurrentness.CURRENT


def test_superseded_when_bound_eq_identity_no_longer_current() -> None:
    ea = _actionable_ea()
    stale_identity = EntryQualificationIdentity(
        instrument_id="NSE:TEST", session_date=DAY, as_of=EQ_AS_OF.replace(minute=46),
        decision_id="decision-1", methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
    )
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=stale_identity,
        current_session_phase=SessionPhase.REGULAR,
        now=EVIDENCE_AS_OF,
    )
    assert result.status is EntryActionabilityCurrentness.SUPERSEDED


def test_superseded_comparison_uses_full_composite_identity_not_decision_id_alone() -> None:
    """A caller-supplied identity with the SAME decision_id but a
    different methodology_version must still be treated as not-current
    (ID-7A authorization item 20 — never decision_id-alone matching)."""
    ea = _actionable_ea()
    same_decision_different_methodology = EntryQualificationIdentity(
        instrument_id="NSE:TEST", session_date=DAY, as_of=EQ_AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v1",
    )
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=same_decision_different_methodology,
        current_session_phase=SessionPhase.REGULAR,
        now=EVIDENCE_AS_OF,
    )
    assert result.status is EntryActionabilityCurrentness.SUPERSEDED


def test_stale_when_evidence_age_exceeds_threshold() -> None:
    ea = _actionable_ea()
    now = EVIDENCE_AS_OF + timedelta(seconds=CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS + 1)
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.REGULAR,
        now=now,
    )
    assert result.status is EntryActionabilityCurrentness.STALE


def test_exact_boundary_at_599_seconds_is_still_current() -> None:
    ea = _actionable_ea()
    now = EVIDENCE_AS_OF + timedelta(seconds=CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS - 1)
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.REGULAR,
        now=now,
    )
    assert result.status is EntryActionabilityCurrentness.CURRENT


def test_exact_boundary_at_600_seconds_is_still_current_strict_inequality() -> None:
    """The frozen predicate is `age > threshold`, so exactly the threshold
    itself is still within the band (strict, not inclusive-exceeded)."""
    ea = _actionable_ea()
    now = EVIDENCE_AS_OF + timedelta(seconds=CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS)
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.REGULAR,
        now=now,
    )
    assert result.status is EntryActionabilityCurrentness.CURRENT


def test_just_past_boundary_is_stale() -> None:
    ea = _actionable_ea()
    now = EVIDENCE_AS_OF + timedelta(seconds=CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS + 0.001)
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.REGULAR,
        now=now,
    )
    assert result.status is EntryActionabilityCurrentness.STALE


def test_session_closed_when_phase_not_regular() -> None:
    ea = _actionable_ea()
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.CLOSED,
        now=EVIDENCE_AS_OF,
    )
    assert result.status is EntryActionabilityCurrentness.SESSION_CLOSED


def test_now_must_be_timezone_aware() -> None:
    ea = _actionable_ea()
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        is_currently_usable(
            ea,
            current_entry_qualification_identity=_current_identity(ea),
            current_session_phase=SessionPhase.REGULAR,
            now=datetime(2026, 9, 4, 10, 0),
        )


def test_is_currently_usable_never_mutates_or_persists_a_currentness_field() -> None:
    """Pure function proof: the input object is unchanged, and nothing it
    returns is a field on the domain object itself (frozen dataclass, so
    an identity check plus a lack of any settable currentness attribute
    is sufficient)."""
    ea = _actionable_ea()
    snapshot_state = ea.state
    is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.CLOSED,  # would be SESSION_CLOSED
        now=EVIDENCE_AS_OF,
    )
    assert ea.state is snapshot_state  # persisted state untouched by a read-time evaluation
    assert not hasattr(ea, "currentness")
    assert not hasattr(ea, "is_current")


def test_historical_actionable_row_stays_actionable_regardless_of_currentness() -> None:
    """A 10:00 ACTIONABLE row still reads ACTIONABLE at 15:00 — currentness
    is read-time-only and never mutates the persisted verdict, regardless
    of which currentness reason (here: STALE, since the age check runs
    before the session-phase check) explains why it is no longer usable."""
    ea = _actionable_ea()
    later_now = EVIDENCE_AS_OF + timedelta(hours=5)
    result = is_currently_usable(
        ea,
        current_entry_qualification_identity=_current_identity(ea),
        current_session_phase=SessionPhase.CLOSED,
        now=later_now,
    )
    assert result.status is EntryActionabilityCurrentness.STALE
    assert ea.state is EntryActionabilityState.ACTIONABLE  # unchanged
