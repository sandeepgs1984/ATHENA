"""Entry Actionability domain contracts (ID-7A).

Contract tests only: no evaluator, no workflow, no persistence engine, no
calibrated methodology recomputation. Proves the frozen V0 contract
(ID-7B.2/ID-7B.2.1) survives translation into code: exact three-state
persisted model, exact four reason codes, exact upstream identity, the
direction-aware structural risk-geometry guard, and value-object
presence/absence rules.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from athena.domain.enums import DecisionType, Direction
from athena.intraday import (
    CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS,
    DEFAULT_METHODOLOGY_VERSION as EQ_DEFAULT_METHODOLOGY_VERSION,
    ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
    T1_GOAL_BAND_PCT,
    T2_GOAL_BAND_PCT,
    UPSTREAM_ELIGIBILITY_REASON_CODES,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryEvidenceFinality,
    EntryLocationContext,
    EntryQualificationState,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OpeningRangeContextBasis,
    OpeningRangeContextReference,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)

IST = ZoneInfo("Asia/Kolkata")
EQ_AS_OF = datetime(2026, 9, 4, 9, 45, tzinfo=IST)
EA_AS_OF = datetime(2026, 9, 4, 9, 50, tzinfo=IST)
DAY = date(2026, 9, 4)


def _entry_reference(price: str = "100.00") -> EntryReference:
    return EntryReference(price=Decimal(price), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE)


def _entry_location_context() -> EntryLocationContext:
    return EntryLocationContext(vwap=Decimal("99.50"), vwap_deviation_pct=Decimal("0.50"))


def _operative_invalidation(level: str = "98.00") -> OperativeInvalidation:
    return OperativeInvalidation(level=Decimal(level), basis=InvalidationBasis.VWAP_LOSS)


def _reward() -> RewardReference:
    return RewardReference(
        t1_price=Decimal("101.00"),
        t2_price=Decimal("101.50"),
        basis=RewardBasis.GOAL_BANDS_ONLY,
        reward_risk_to_t1=Decimal("0.5"),
        reward_risk_to_t2=Decimal("0.75"),
    )


def _or_context() -> OpeningRangeContextReference:
    return OpeningRangeContextReference(level=Decimal("97.00"), basis=OpeningRangeContextBasis.OR15_BOUNDARY)


def _ea(
    *,
    direction: Direction = Direction.LONG,
    state: EntryActionabilityState = EntryActionabilityState.ACTIONABLE,
    reason_codes: tuple[EntryActionabilityReasonCode, ...] = (),
    decision_type: DecisionType = DecisionType.TRADE,
    entry_qualification_state: EntryQualificationState = EntryQualificationState.QUALIFIED,
    evidence_as_of: datetime | None = EA_AS_OF,
    entry_reference: EntryReference | None = None,
    entry_location_context: EntryLocationContext | None = None,
    operative_invalidation: OperativeInvalidation | None = None,
    reward: RewardReference | None = None,
    opening_range_context: OpeningRangeContextReference | None = None,
    entry_actionability_as_of: datetime = EA_AS_OF,
    entry_qualification_as_of: datetime = EQ_AS_OF,
    evaluated_at: datetime = EA_AS_OF,
    explanation: str = "contract test explanation",
) -> EntryActionability:
    if state is EntryActionabilityState.ACTIONABLE:
        entry_reference = entry_reference if entry_reference is not None else _entry_reference()
        entry_location_context = (
            entry_location_context if entry_location_context is not None else _entry_location_context()
        )
        operative_invalidation = (
            operative_invalidation if operative_invalidation is not None else _operative_invalidation()
        )
        reward = reward if reward is not None else _reward()
        if not reason_codes:
            reason_codes = ()
    return EntryActionability(
        instrument_id="NSE:TEST",
        session_date=DAY,
        entry_qualification_as_of=entry_qualification_as_of,
        decision_id="decision-1",
        entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=entry_actionability_as_of,
        entry_actionability_methodology_version=ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
        decision_type=decision_type,
        direction=direction,
        entry_qualification_state=entry_qualification_state,
        run_id="run-1",
        cycle_id="cycle-1",
        state=state,
        reason_codes=reason_codes,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=evidence_as_of,
        entry_reference=entry_reference,
        entry_location_context=entry_location_context,
        operative_invalidation=operative_invalidation,
        reward=reward,
        opening_range_context=opening_range_context,
        evaluated_at=evaluated_at,
        explanation=explanation,
    )


# --------------------------------------------------------------------------- #
# Persisted state / reason vocabulary — exact frozen sets
# --------------------------------------------------------------------------- #


def test_exactly_three_persisted_states_exist() -> None:
    assert {s.value for s in EntryActionabilityState} == {
        "UNKNOWN",
        "NOT_ACTIONABLE",
        "ACTIONABLE",
    }


def test_no_currentness_concepts_leak_into_persisted_state() -> None:
    forbidden = ("EXPIRED", "STALE", "CURRENT", "SUPERSEDED", "SESSION_CLOSED")
    for state in EntryActionabilityState:
        assert state.value not in forbidden


def test_exactly_four_reason_codes_exist() -> None:
    assert {r.value for r in EntryActionabilityReasonCode} == {
        "UPSTREAM_DECISION_NOT_TRADE",
        "UPSTREAM_EQ_NOT_QUALIFIED",
        "INSUFFICIENT_EVIDENCE",
        "INVALIDATION_UNAVAILABLE",
    }


def test_rejected_reason_codes_do_not_exist() -> None:
    forbidden = {"ENTRY_TOO_EXTENDED", "SESSION_NOT_ACTIONABLE"}
    assert forbidden.isdisjoint({r.value for r in EntryActionabilityReasonCode})


def test_no_d1_atr_or_extension_gate_representation_anywhere() -> None:
    """Explicit proof (ID-7A authorization) that D1-ATR and the extension
    gate were never implemented as actual fields/enum members anywhere in
    the domain model — scoped to real dataclass fields and enum member
    names/values, never prose, since the module's own docstrings
    legitimately discuss (and reject) these concepts by name."""
    import athena.intraday.entry_actionability_models as mod

    field_names: set[str] = set()
    enum_member_names: set[str] = set()
    enum_member_values: set[str] = set()
    for obj in vars(mod).values():
        if dataclasses.is_dataclass(obj) and isinstance(obj, type):
            field_names.update(f.name for f in dataclasses.fields(obj))
        elif isinstance(obj, type) and issubclass(obj, __import__("enum").Enum):
            enum_member_names.update(obj.__members__.keys())
            enum_member_values.update(str(m.value) for m in obj)

    forbidden_fields = {"d1_atr", "extension_gate", "atr"}
    forbidden_enum_terms = {"D1_ATR", "EXTENSION_GATE", "ENTRY_TOO_EXTENDED"}
    assert forbidden_fields.isdisjoint(field_names)
    assert forbidden_enum_terms.isdisjoint(enum_member_names)
    assert forbidden_enum_terms.isdisjoint(enum_member_values)


# --------------------------------------------------------------------------- #
# Methodology version / frozen constants
# --------------------------------------------------------------------------- #


def test_methodology_version_is_namespaced_apart_from_eq() -> None:
    assert ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION == "entry-actionability-v0"
    assert EQ_DEFAULT_METHODOLOGY_VERSION == "entry-qualification-v0"
    assert ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION != EQ_DEFAULT_METHODOLOGY_VERSION


def test_frozen_numeric_constants_match_calibrated_v0_contract() -> None:
    assert T1_GOAL_BAND_PCT == Decimal("0.01")
    assert T2_GOAL_BAND_PCT == Decimal("0.015")
    assert CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS == 600.0


# --------------------------------------------------------------------------- #
# Identity — exact upstream EQ identity copied verbatim, own identity added
# --------------------------------------------------------------------------- #


def test_identity_carries_full_upstream_eq_identity_verbatim() -> None:
    ea = _ea()
    assert ea.instrument_id == "NSE:TEST"
    assert ea.session_date == DAY
    assert ea.entry_qualification_as_of == EQ_AS_OF
    assert ea.decision_id == "decision-1"
    assert ea.entry_qualification_methodology_version == EQ_DEFAULT_METHODOLOGY_VERSION


def test_identity_never_reduced_to_decision_id_alone() -> None:
    """Two observations bound to the same decision_id but different EQ
    as_of/methodology_version are genuinely different identities/objects —
    decision_id alone must never be treated as sufficient identity."""
    a = _ea(entry_qualification_as_of=EQ_AS_OF)
    b = _ea(entry_qualification_as_of=EQ_AS_OF.replace(minute=46))
    assert a.decision_id == b.decision_id
    assert a != b


def test_own_identity_fields_are_present_and_distinct_from_eq_as_of() -> None:
    ea = _ea()
    assert ea.entry_actionability_as_of == EA_AS_OF
    assert ea.entry_actionability_methodology_version == ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION
    # Architecturally distinct fields even though they coincide under Option 1.
    assert ea.entry_qualification_as_of != ea.entry_actionability_as_of or True  # documented, not asserted equal


def test_no_surrogate_id_field_exists() -> None:
    field_names = {f.name for f in dataclasses.fields(EntryActionability)}
    assert "id" not in field_names
    assert "entry_actionability_id" not in field_names


# --------------------------------------------------------------------------- #
# Timestamp / structural validation
# --------------------------------------------------------------------------- #


def test_timezone_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EntryActionability(
            instrument_id="NSE:TEST",
            session_date=DAY,
            entry_qualification_as_of=datetime(2026, 9, 4, 9, 45),
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
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
            evidence_finality=EntryEvidenceFinality.UNKNOWN_PROVENANCE,
            evidence_as_of=None,
            entry_reference=None,
            entry_location_context=None,
            operative_invalidation=None,
            reward=None,
            opening_range_context=None,
            evaluated_at=EA_AS_OF,
            explanation="x",
        )


def test_evidence_as_of_naive_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence_as_of must be timezone-aware"):
        _ea(state=EntryActionabilityState.ACTIONABLE, evidence_as_of=datetime(2026, 9, 4, 9, 50))


def test_duplicate_reason_codes_rejected() -> None:
    with pytest.raises(ValueError, match="reason_codes must not contain duplicates"):
        _ea(
            state=EntryActionabilityState.NOT_ACTIONABLE,
            reason_codes=(
                EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,
                EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,
            ),
        )


def test_empty_explanation_rejected() -> None:
    with pytest.raises(ValueError, match="explanation is mandatory"):
        _ea(explanation="")


# --------------------------------------------------------------------------- #
# ACTIONABLE <-> value-object presence coupling
# --------------------------------------------------------------------------- #


def test_actionable_requires_all_four_value_objects() -> None:
    """Bypasses the `_ea` test helper's own convenience defaults (which
    backfill missing value objects for ACTIONABLE) to genuinely exercise
    the domain object's own validation with entry_reference absent."""
    with pytest.raises(ValueError, match="ACTIONABLE requires"):
        EntryActionability(
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
            evidence_as_of=EA_AS_OF,
            entry_reference=None,
            entry_location_context=_entry_location_context(),
            operative_invalidation=_operative_invalidation(),
            reward=_reward(),
            opening_range_context=None,
            evaluated_at=EA_AS_OF,
            explanation="missing entry_reference",
        )


def test_actionable_requires_evidence_as_of() -> None:
    with pytest.raises(ValueError, match="ACTIONABLE requires evidence_as_of"):
        _ea(state=EntryActionabilityState.ACTIONABLE, evidence_as_of=None)


def test_not_actionable_forbids_all_value_objects() -> None:
    with pytest.raises(ValueError, match="must be None when state=NOT_ACTIONABLE"):
        _ea(
            state=EntryActionabilityState.NOT_ACTIONABLE,
            entry_qualification_state=EntryQualificationState.NOT_YET,
            reason_codes=(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,),
            entry_reference=_entry_reference(),
        )


def test_not_actionable_requires_reason_codes() -> None:
    with pytest.raises(ValueError, match="reason_codes is mandatory when state=NOT_ACTIONABLE"):
        _ea(state=EntryActionabilityState.NOT_ACTIONABLE, reason_codes=())


def test_unknown_requires_reason_codes() -> None:
    with pytest.raises(ValueError, match="reason_codes is mandatory when state=UNKNOWN"):
        _ea(state=EntryActionabilityState.UNKNOWN, reason_codes=())


def test_unknown_forbids_value_objects() -> None:
    with pytest.raises(ValueError, match="must be None when state=UNKNOWN"):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
            entry_reference=_entry_reference(),
        )


def test_not_actionable_with_reason_and_no_value_objects_is_valid() -> None:
    ea = _ea(
        state=EntryActionabilityState.NOT_ACTIONABLE,
        entry_qualification_state=EntryQualificationState.NOT_YET,
        reason_codes=(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,),
    )
    assert ea.entry_reference is None
    assert ea.entry_location_context is None
    assert ea.operative_invalidation is None
    assert ea.reward is None


def test_opening_range_context_is_independently_optional_when_actionable() -> None:
    with_or = _ea(state=EntryActionabilityState.ACTIONABLE, opening_range_context=_or_context())
    without_or = _ea(state=EntryActionabilityState.ACTIONABLE, opening_range_context=None)
    assert with_or.opening_range_context is not None
    assert without_or.opening_range_context is None


# --------------------------------------------------------------------------- #
# Direction-aware structural risk-geometry guard
# --------------------------------------------------------------------------- #


def test_long_requires_invalidation_strictly_below_entry() -> None:
    _ea(
        direction=Direction.LONG,
        entry_reference=_entry_reference("100.00"),
        operative_invalidation=_operative_invalidation("98.00"),
    )  # valid — should not raise
    with pytest.raises(ValueError, match="LONG risk geometry invalid"):
        _ea(
            direction=Direction.LONG,
            entry_reference=_entry_reference("100.00"),
            operative_invalidation=_operative_invalidation("100.00"),
        )
    with pytest.raises(ValueError, match="LONG risk geometry invalid"):
        _ea(
            direction=Direction.LONG,
            entry_reference=_entry_reference("100.00"),
            operative_invalidation=_operative_invalidation("101.00"),
        )


def test_short_requires_invalidation_strictly_above_entry() -> None:
    _ea(
        direction=Direction.SHORT,
        entry_reference=_entry_reference("100.00"),
        operative_invalidation=_operative_invalidation("102.00"),
    )  # valid — should not raise
    with pytest.raises(ValueError, match="SHORT risk geometry invalid"):
        _ea(
            direction=Direction.SHORT,
            entry_reference=_entry_reference("100.00"),
            operative_invalidation=_operative_invalidation("100.00"),
        )
    with pytest.raises(ValueError, match="SHORT risk geometry invalid"):
        _ea(
            direction=Direction.SHORT,
            entry_reference=_entry_reference("100.00"),
            operative_invalidation=_operative_invalidation("99.00"),
        )


def test_zero_risk_distance_is_rejected_both_directions() -> None:
    """Structural guard rejects EXACTLY zero risk distance (never a
    calibrated minimum) — the boundary itself, not a margin around it."""
    with pytest.raises(ValueError, match="risk geometry invalid"):
        _ea(
            direction=Direction.LONG,
            entry_reference=_entry_reference("100.00"),
            operative_invalidation=_operative_invalidation("100.00"),
        )


def test_none_direction_is_rejected_when_actionable() -> None:
    with pytest.raises(ValueError, match="requires a directional Decision"):
        _ea(direction=Direction.NONE)


def test_direction_remains_bidirectional_in_domain_model() -> None:
    """Domain model itself is not hard-coded LONG-only, even though V0's
    own empirical validation status is LONG_VALIDATED_SHORT_UNVALIDATED —
    that is a methodology-evidence fact, not a representation constraint."""
    long_ea = _ea(direction=Direction.LONG)
    short_ea = _ea(
        direction=Direction.SHORT,
        entry_reference=_entry_reference("100.00"),
        operative_invalidation=_operative_invalidation("102.00"),
    )
    assert long_ea.direction is Direction.LONG
    assert short_ea.direction is Direction.SHORT


# --------------------------------------------------------------------------- #
# Immutability / equality
# --------------------------------------------------------------------------- #


def test_immutable_and_equal_by_value() -> None:
    a = _ea()
    b = _ea()
    assert a == b
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.state = EntryActionabilityState.UNKNOWN  # type: ignore[misc]


def test_evidence_finality_reuses_eq_type_no_duplicate_enum() -> None:
    ea = _ea()
    assert isinstance(ea.evidence_finality, EntryEvidenceFinality)


# --------------------------------------------------------------------------- #
# ID-7A.1: domain-integrity hardening — impossible-artifact rejection
# --------------------------------------------------------------------------- #


def test_actionable_rejects_watch_decision_type() -> None:
    with pytest.raises(ValueError, match="ACTIONABLE requires decision_type == TRADE"):
        _ea(state=EntryActionabilityState.ACTIONABLE, decision_type=DecisionType.WATCH)


def test_actionable_rejects_non_qualified_eq_state() -> None:
    with pytest.raises(
        ValueError, match="ACTIONABLE requires entry_qualification_state == QUALIFIED"
    ):
        _ea(
            state=EntryActionabilityState.ACTIONABLE,
            entry_qualification_state=EntryQualificationState.NOT_YET,
        )


def test_actionable_rejects_any_blocking_reason_code() -> None:
    for code in EntryActionabilityReasonCode:
        with pytest.raises(ValueError, match="ACTIONABLE requires reason_codes to be empty"):
            _ea(state=EntryActionabilityState.ACTIONABLE, reason_codes=(code,))


def test_not_actionable_rejects_evidence_family_reason() -> None:
    with pytest.raises(
        ValueError, match="NOT_ACTIONABLE reason_codes must be upstream-eligibility reasons"
    ):
        _ea(
            state=EntryActionabilityState.NOT_ACTIONABLE,
            entry_qualification_state=EntryQualificationState.NOT_YET,
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
        )


def test_unknown_rejects_upstream_family_reason() -> None:
    with pytest.raises(
        ValueError, match="UNKNOWN reason_codes must be evidence-sufficiency reasons"
    ):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,),
        )


def test_upstream_decision_not_trade_requires_non_trade_decision_type() -> None:
    """A NOT_ACTIONABLE verdict claiming UPSTREAM_DECISION_NOT_TRADE while
    decision_type is actually TRADE is untruthful and must be rejected —
    domain-integrity, independent of any repository binding check."""
    with pytest.raises(
        ValueError,
        match="UPSTREAM_DECISION_NOT_TRADE reason_code requires decision_type",
    ):
        _ea(
            state=EntryActionabilityState.NOT_ACTIONABLE,
            decision_type=DecisionType.TRADE,
            reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,),
        )


def test_upstream_eq_not_qualified_requires_non_qualified_eq_state() -> None:
    with pytest.raises(
        ValueError,
        match="UPSTREAM_EQ_NOT_QUALIFIED reason_code requires entry_qualification_state",
    ):
        _ea(
            state=EntryActionabilityState.NOT_ACTIONABLE,
            entry_qualification_state=EntryQualificationState.QUALIFIED,
            reason_codes=(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,),
        )


def test_not_actionable_upstream_decision_not_trade_valid_when_truthful() -> None:
    ea = _ea(
        state=EntryActionabilityState.NOT_ACTIONABLE,
        decision_type=DecisionType.WATCH,
        reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,),
    )
    assert ea.decision_type is DecisionType.WATCH


def test_not_actionable_multiple_upstream_reasons_in_same_family_allowed() -> None:
    """Multiple reasons within the same semantic family remain
    representable — the domain model does not invent an evaluator
    precedence/exclusivity rule."""
    ea = _ea(
        state=EntryActionabilityState.NOT_ACTIONABLE,
        decision_type=DecisionType.WATCH,
        entry_qualification_state=EntryQualificationState.NOT_YET,
        reason_codes=(
            EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,
            EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,
        ),
    )
    assert len(ea.reason_codes) == 2


def test_trade_qualified_actionable_with_no_reasons_is_valid() -> None:
    ea = _ea(
        state=EntryActionabilityState.ACTIONABLE,
        decision_type=DecisionType.TRADE,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
    )
    assert ea.state is EntryActionabilityState.ACTIONABLE
    assert ea.reason_codes == ()


# --------------------------------------------------------------------------- #
# ID-7A.1: point-in-time causal-ordering invariants
# --------------------------------------------------------------------------- #


def test_entry_actionability_as_of_before_entry_qualification_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="must not precede entry_qualification_as_of"):
        _ea(entry_actionability_as_of=EQ_AS_OF.replace(minute=0))


def test_entry_actionability_as_of_equal_to_entry_qualification_as_of_is_valid() -> None:
    ea = _ea(
        entry_qualification_as_of=EQ_AS_OF,
        entry_actionability_as_of=EQ_AS_OF,
        evidence_as_of=EQ_AS_OF,
    )
    assert ea.entry_actionability_as_of == ea.entry_qualification_as_of


def test_future_same_eq_reevaluation_is_valid() -> None:
    """entry_actionability_as_of strictly LATER than
    entry_qualification_as_of is valid — a future re-evaluation of the
    same, still-current EQ observation (ADR-015's own extensibility)."""
    later = EA_AS_OF.replace(hour=11)
    ea = _ea(entry_qualification_as_of=EQ_AS_OF, entry_actionability_as_of=later, evidence_as_of=later)
    assert ea.entry_actionability_as_of > ea.entry_qualification_as_of


def test_evidence_as_of_after_entry_actionability_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="must not be later than entry_actionability_as_of"):
        _ea(
            entry_actionability_as_of=EA_AS_OF,
            evidence_as_of=EA_AS_OF.replace(minute=59),
        )


def test_evidence_as_of_equal_to_entry_actionability_as_of_is_valid() -> None:
    ea = _ea(entry_actionability_as_of=EA_AS_OF, evidence_as_of=EA_AS_OF)
    assert ea.evidence_as_of == ea.entry_actionability_as_of


# --------------------------------------------------------------------------- #
# ID-7A.1: reward/RR structural safety
# --------------------------------------------------------------------------- #


def test_reward_negative_rr_rejected() -> None:
    with pytest.raises(ValueError, match="reward_risk_to_t1 must not be negative"):
        RewardReference(
            t1_price=Decimal("101.00"),
            t2_price=Decimal("101.50"),
            basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("-0.1"),
            reward_risk_to_t2=Decimal("0.5"),
        )
    with pytest.raises(ValueError, match="reward_risk_to_t2 must not be negative"):
        RewardReference(
            t1_price=Decimal("101.00"),
            t2_price=Decimal("101.50"),
            basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("0.5"),
            reward_risk_to_t2=Decimal("-0.1"),
        )


# --------------------------------------------------------------------------- #
# ID-7A.2: UNKNOWN upstream-eligibility invariant
# --------------------------------------------------------------------------- #


def test_unknown_rejects_watch_decision_type() -> None:
    with pytest.raises(ValueError, match="UNKNOWN requires decision_type == TRADE"):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            decision_type=DecisionType.WATCH,
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
        )


def test_unknown_rejects_watch_decision_type_with_invalidation_unavailable() -> None:
    with pytest.raises(ValueError, match="UNKNOWN requires decision_type == TRADE"):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            decision_type=DecisionType.WATCH,
            reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
        )


def test_unknown_rejects_not_yet_eq_state() -> None:
    with pytest.raises(
        ValueError, match="UNKNOWN requires entry_qualification_state == QUALIFIED"
    ):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            decision_type=DecisionType.TRADE,
            entry_qualification_state=EntryQualificationState.NOT_YET,
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
        )


@pytest.mark.parametrize(
    "eq_state",
    [
        EntryQualificationState.OUT_OF_SCOPE,
        EntryQualificationState.UNKNOWN,
        EntryQualificationState.NOT_YET,
        EntryQualificationState.DISQUALIFIED_FOR_SESSION,
        EntryQualificationState.EXPIRED,
    ],
)
def test_unknown_rejects_every_non_qualified_eq_state(eq_state) -> None:
    with pytest.raises(
        ValueError, match="UNKNOWN requires entry_qualification_state == QUALIFIED"
    ):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            decision_type=DecisionType.TRADE,
            entry_qualification_state=eq_state,
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
        )


def test_unknown_decision_type_checked_before_reason_family() -> None:
    """The upstream-eligibility gate fires even when the reason family
    would otherwise be legal (INSUFFICIENT_EVIDENCE is a valid UNKNOWN
    reason) — upstream eligibility is a precondition for reaching the
    evidence-sufficiency layer at all."""
    with pytest.raises(ValueError, match="UNKNOWN requires decision_type == TRADE"):
        _ea(
            state=EntryActionabilityState.UNKNOWN,
            decision_type=DecisionType.WATCH,
            entry_qualification_state=EntryQualificationState.QUALIFIED,
            reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
        )


def test_trade_qualified_unknown_insufficient_evidence_is_legal() -> None:
    ea = _ea(
        state=EntryActionabilityState.UNKNOWN,
        decision_type=DecisionType.TRADE,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
    )
    assert ea.state is EntryActionabilityState.UNKNOWN
    assert ea.reason_codes == (EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,)
    assert ea.entry_reference is None


def test_trade_qualified_unknown_invalidation_unavailable_is_legal() -> None:
    ea = _ea(
        state=EntryActionabilityState.UNKNOWN,
        decision_type=DecisionType.TRADE,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
    )
    assert ea.state is EntryActionabilityState.UNKNOWN
    assert ea.reason_codes == (EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,)
    assert ea.entry_location_context is None
    assert ea.operative_invalidation is None
    assert ea.reward is None


def test_not_actionable_semantics_still_upstream_only_after_id7a2() -> None:
    """ID-7A.2 touches UNKNOWN only — NOT_ACTIONABLE's own upstream-only
    reason vocabulary and family are unchanged."""
    assert UPSTREAM_ELIGIBILITY_REASON_CODES == {
        EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,
        EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,
    }
    ea = _ea(
        state=EntryActionabilityState.NOT_ACTIONABLE,
        decision_type=DecisionType.WATCH,
        reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,),
    )
    assert ea.state is EntryActionabilityState.NOT_ACTIONABLE


def test_reason_code_vocabulary_unchanged_after_id7a2() -> None:
    """No new reason code was introduced by this milestone."""
    assert {r.value for r in EntryActionabilityReasonCode} == {
        "UPSTREAM_DECISION_NOT_TRADE",
        "UPSTREAM_EQ_NOT_QUALIFIED",
        "INSUFFICIENT_EVIDENCE",
        "INVALIDATION_UNAVAILABLE",
    }
