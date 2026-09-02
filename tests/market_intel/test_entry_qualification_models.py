"""Entry Qualification domain contracts (ID-6A).

Contract tests only: no engine, no workflow, no persistence, no thresholds.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from athena.domain.enums import DecisionType
from athena.intraday import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationEvidenceKind,
    EntryQualificationEvidenceRef,
    EntryQualificationReasonCode,
    EntryQualificationState,
)

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=IST)
DAY = date(2026, 9, 2)


def _eq(
    *,
    state: EntryQualificationState = EntryQualificationState.UNKNOWN,
    evidence_finality: EntryEvidenceFinality = EntryEvidenceFinality.UNKNOWN_PROVENANCE,
    confirmation: EntryQualificationConfirmation = EntryQualificationConfirmation.UNKNOWN,
    decision_type: DecisionType = DecisionType.WATCH,
    reason_codes: tuple[EntryQualificationReasonCode, ...] = (),
    evidence_refs: tuple[EntryQualificationEvidenceRef, ...] = (),
) -> EntryQualification:
    return EntryQualification(
        instrument_id="NSE:TEST",
        session_date=DAY,
        as_of=AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_id="decision-1",
        decision_type=decision_type,
        state=state,
        evidence_finality=evidence_finality,
        confirmation=confirmation,
        reason_codes=reason_codes,
        evidence_refs=evidence_refs,
        methodology_version="id6a-contract",
        config_snapshot_id="cfg-1",
        explanation="contract test explanation",
    )


def test_all_six_qualification_states_exist() -> None:
    assert {state.value for state in EntryQualificationState} == {
        "OUT_OF_SCOPE",
        "UNKNOWN",
        "NOT_YET",
        "QUALIFIED",
        "DISQUALIFIED_FOR_SESSION",
        "EXPIRED",
    }


def test_state_names_do_not_encode_finality_or_confirmation() -> None:
    forbidden_fragments = ("PROVISIONAL", "CONFIRMED", "BUY", "SELL", "PASS", "TRADE", "WATCH")
    for state in EntryQualificationState:
        assert not any(fragment in state.value for fragment in forbidden_fragments)


def test_state_and_evidence_finality_are_independent() -> None:
    qualified_live = _eq(
        state=EntryQualificationState.QUALIFIED,
        evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
    )
    not_yet_stable = _eq(
        state=EntryQualificationState.NOT_YET,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
    )
    assert qualified_live.state is EntryQualificationState.QUALIFIED
    assert qualified_live.evidence_finality is EntryEvidenceFinality.LIVE_M5_PROVISIONAL
    assert not_yet_stable.state is EntryQualificationState.NOT_YET
    assert not_yet_stable.evidence_finality is EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY


def test_confirmation_and_evidence_finality_are_independent() -> None:
    eq = _eq(
        evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
    )
    assert eq.confirmation is EntryQualificationConfirmation.CONFIRMED_BY_POLICY
    assert eq.evidence_finality is EntryEvidenceFinality.LIVE_M5_PROVISIONAL


def test_adr_orthogonality_examples_are_representable() -> None:
    qualified_confirmed_provisional = _eq(
        state=EntryQualificationState.QUALIFIED,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
    )
    not_yet_not_confirmed_provisional = _eq(
        state=EntryQualificationState.NOT_YET,
        confirmation=EntryQualificationConfirmation.NOT_CONFIRMED,
        evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
    )
    qualified_confirmed_no_decisive_provisional = _eq(
        state=EntryQualificationState.QUALIFIED,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
    )

    assert qualified_confirmed_provisional.state is EntryQualificationState.QUALIFIED
    assert not_yet_not_confirmed_provisional.state is EntryQualificationState.NOT_YET
    assert (
        qualified_confirmed_no_decisive_provisional.evidence_finality
        is EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY
    )


def test_qualified_does_not_change_canonical_decision_type() -> None:
    watch_eq = _eq(state=EntryQualificationState.QUALIFIED, decision_type=DecisionType.WATCH)
    trade_eq = _eq(state=EntryQualificationState.QUALIFIED, decision_type=DecisionType.TRADE)
    assert watch_eq.decision_type is DecisionType.WATCH
    assert trade_eq.decision_type is DecisionType.TRADE


def test_decision_binding_and_run_cycle_identity_are_preserved() -> None:
    eq = _eq()
    assert eq.decision_id == "decision-1"
    assert eq.run_id == "run-1"
    assert eq.cycle_id == "cycle-1"
    assert eq.instrument_id == "NSE:TEST"


def test_structural_validation_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EntryQualification(
            instrument_id="NSE:TEST",
            session_date=DAY,
            as_of=datetime(2026, 9, 2, 10, 0),
            run_id="run-1",
            cycle_id="cycle-1",
            decision_id="decision-1",
            decision_type=DecisionType.WATCH,
            state=EntryQualificationState.UNKNOWN,
            evidence_finality=EntryEvidenceFinality.UNKNOWN_PROVENANCE,
            confirmation=EntryQualificationConfirmation.UNKNOWN,
            reason_codes=(),
            evidence_refs=(),
            methodology_version=None,
            config_snapshot_id=None,
            explanation="x",
        )


def test_evidence_reference_validation_preserves_explainability() -> None:
    ref = EntryQualificationEvidenceRef(
        kind=EntryQualificationEvidenceKind.INTRADAY_SIGNAL_SET,
        ref_id=None,
        as_of=AS_OF,
        explanation="live value object has no persisted ID in ID-6A",
    )
    eq = _eq(evidence_refs=(ref,))
    assert eq.evidence_refs == (ref,)

    with pytest.raises(ValueError, match="explanation is mandatory"):
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.DECISION,
            ref_id="decision-1",
            as_of=AS_OF,
            explanation="",
        )


def test_duplicate_reason_codes_are_rejected_without_methodology_rules() -> None:
    with pytest.raises(ValueError, match="reason_codes"):
        _eq(
            reason_codes=(
                EntryQualificationReasonCode.STALE_EVIDENCE,
                EntryQualificationReasonCode.STALE_EVIDENCE,
            )
        )
    assert "RVOL_TOO_LOW" not in {reason.value for reason in EntryQualificationReasonCode}
    assert "ORB_FAILED" not in {reason.value for reason in EntryQualificationReasonCode}
    assert "RS_TOO_WEAK" not in {reason.value for reason in EntryQualificationReasonCode}
    assert "VWAP_LOST" not in {reason.value for reason in EntryQualificationReasonCode}


def test_immutability_equality_and_dataclass_serialization_convention() -> None:
    a = _eq(state=EntryQualificationState.QUALIFIED)
    b = _eq(state=EntryQualificationState.QUALIFIED)
    assert a == b
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.state = EntryQualificationState.NOT_YET
    serialized = dataclasses.asdict(a)
    assert serialized["state"] is EntryQualificationState.QUALIFIED
    assert serialized["decision_id"] == "decision-1"
