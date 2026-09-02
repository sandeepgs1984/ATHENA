"""EntryQualification persistence tests (ID-6C).

Persists what EntryQualificationEngine (ID-6B.2) already concluded; these
tests prove round-trip fidelity, idempotency, conflict detection, and
append-only/latest-lookup semantics -- never re-derive or reinterpret the
methodology itself.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.data.store import serialization as ser
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType
from athena.domain.market import Instrument
from athena.errors import RepositoryError
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationEvidenceKind,
    EntryQualificationEvidenceRef,
    EntryQualificationReasonCode,
    EntryQualificationState,
)

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 9, 2)
AS_OF = datetime(2026, 9, 2, 10, 0, tzinfo=IST)


@pytest.fixture()
def repo(tmp_path: Path):
    repository = SqliteRepository(tmp_path / "athena.db")
    repository.initialize()
    repository.upsert_instrument(
        Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ")
    )
    yield repository
    repository.close()


def _decision(decision_id: str = "decision-1") -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id="run-1",
        cycle_id="cycle-1",
        decision_type=DecisionType.WATCH,
        explanation="test decision",
        instrument_id=IID,
    )


def _eq(
    *,
    decision_id: str = "decision-1",
    as_of: datetime = AS_OF,
    state: EntryQualificationState = EntryQualificationState.QUALIFIED,
    evidence_finality: EntryEvidenceFinality = EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
    confirmation: EntryQualificationConfirmation = EntryQualificationConfirmation.NOT_EVALUATED,
    reason_codes: tuple[EntryQualificationReasonCode, ...] = (
        EntryQualificationReasonCode.VWAP_CONDITION_MET,
        EntryQualificationReasonCode.TREND_CONDITION_MET,
        EntryQualificationReasonCode.SUPPORT_CONDITION_MET,
        EntryQualificationReasonCode.V0_READINESS_POLICY_SATISFIED,
    ),
    evidence_refs: tuple[EntryQualificationEvidenceRef, ...] | None = None,
    methodology_version: str = "entry-qualification-v0",
    config_snapshot_id: str | None = None,
    run_id: str = "run-1",
    cycle_id: str = "cycle-1",
    explanation: str = "QUALIFIED: positive VWAP, bullish M5/M15 trend, and RS/RVOL support.",
) -> EntryQualification:
    if evidence_refs is None:
        evidence_refs = (
            EntryQualificationEvidenceRef(
                kind=EntryQualificationEvidenceKind.DECISION,
                ref_id=decision_id,
                as_of=AS_OF,
                explanation="Canonical Decision referenced.",
            ),
            EntryQualificationEvidenceRef(
                kind=EntryQualificationEvidenceKind.SESSION_CONTEXT,
                ref_id=None,
                as_of=AS_OF,
                explanation="SessionContext referenced.",
            ),
        )
    return EntryQualification(
        instrument_id=IID,
        session_date=DAY,
        as_of=as_of,
        run_id=run_id,
        cycle_id=cycle_id,
        decision_id=decision_id,
        decision_type=DecisionType.WATCH,
        state=state,
        evidence_finality=evidence_finality,
        confirmation=confirmation,
        reason_codes=reason_codes,
        evidence_refs=evidence_refs,
        methodology_version=methodology_version,
        config_snapshot_id=config_snapshot_id,
        explanation=explanation,
    )


# --------------------------------------------------------------------------- #
# 1-9: state / finality / confirmation round-trip
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "state",
    [
        EntryQualificationState.QUALIFIED,
        EntryQualificationState.NOT_YET,
        EntryQualificationState.UNKNOWN,
        EntryQualificationState.OUT_OF_SCOPE,
        EntryQualificationState.EXPIRED,
    ],
)
def test_state_round_trips_exactly(repo, state) -> None:
    repo.save_decision(_decision())
    eq = _eq(state=state)
    assert repo.save_entry_qualification(eq, persisted_at=AS_OF) is True
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got == eq


@pytest.mark.parametrize(
    "finality",
    [
        EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
        EntryEvidenceFinality.UNKNOWN_PROVENANCE,
        EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
    ],
)
def test_evidence_finality_round_trips_exactly(repo, finality) -> None:
    repo.save_decision(_decision())
    eq = _eq(evidence_finality=finality)
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.evidence_finality is finality


def test_confirmation_not_evaluated_round_trips(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq(confirmation=EntryQualificationConfirmation.NOT_EVALUATED)
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.confirmation is EntryQualificationConfirmation.NOT_EVALUATED


def test_qualified_provisional_finality_not_evaluated_confirmation_exact(repo) -> None:
    """Owner's exact combination: QUALIFIED + LIVE_M5_PROVISIONAL + NOT_EVALUATED."""
    repo.save_decision(_decision())
    eq = _eq(
        state=EntryQualificationState.QUALIFIED,
        evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
        confirmation=EntryQualificationConfirmation.NOT_EVALUATED,
    )
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got == eq


# --------------------------------------------------------------------------- #
# 10-16: reason codes, evidence refs, timestamps, provenance
# --------------------------------------------------------------------------- #


def test_reason_codes_order_is_preserved(repo) -> None:
    repo.save_decision(_decision())
    ordered = (
        EntryQualificationReasonCode.VWAP_CONDITION_NOT_MET,
        EntryQualificationReasonCode.TREND_CONDITION_NOT_MET,
    )  # deliberately NOT alphabetical -- a genuine order-preservation proof
    eq = _eq(state=EntryQualificationState.NOT_YET, reason_codes=ordered)
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.reason_codes == ordered  # exact tuple equality, not just set equality


def test_evidence_refs_preserved_losslessly(repo) -> None:
    repo.save_decision(_decision())
    refs = (
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.DECISION, ref_id="decision-1",
            as_of=AS_OF, explanation="decision ref",
        ),
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.INTRADAY_SIGNAL_SET, ref_id=None,
            as_of=AS_OF, explanation="signal set ref",
        ),
    )
    eq = _eq(evidence_refs=refs)
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.evidence_refs == refs


def test_evidence_ref_with_none_ref_id_preserved(repo) -> None:
    repo.save_decision(_decision())
    refs = (
        EntryQualificationEvidenceRef(
            kind=EntryQualificationEvidenceKind.SESSION_CONTEXT, ref_id=None,
            as_of=AS_OF, explanation="live value object, no persisted id",
        ),
    )
    eq = _eq(evidence_refs=refs)
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.evidence_refs[0].ref_id is None


def test_timezone_aware_timestamps_preserved(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq()
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.as_of == AS_OF
    assert got.as_of.tzinfo is not None
    assert got.evidence_refs[0].as_of.tzinfo is not None
    assert got.evidence_refs[0].as_of == AS_OF


def test_methodology_version_preserved(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq(methodology_version="entry-qualification-v0")
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.methodology_version == "entry-qualification-v0"


def test_config_snapshot_id_none_remains_valid(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq(config_snapshot_id=None)
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.config_snapshot_id is None


def test_non_null_config_snapshot_id_preserved(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq(config_snapshot_id="cfg-abc")
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.config_snapshot_id == "cfg-abc"


# --------------------------------------------------------------------------- #
# 17-20: idempotency, conflict, multiple observations
# --------------------------------------------------------------------------- #


def test_repeated_identical_save_is_idempotent(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq()
    assert repo.save_entry_qualification(eq, persisted_at=AS_OF) is True
    assert repo.save_entry_qualification(eq, persisted_at=AS_OF) is False  # no-op
    history = repo.list_entry_qualifications_for_instrument_session(IID, DAY)
    assert len(history) == 1  # not duplicated


def test_repeated_save_under_different_run_cycle_is_still_idempotent(repo) -> None:
    """run_id/cycle_id differ (a genuinely different pipeline invocation
    re-evaluating the identical logical candidate) but every
    methodology-relevant field agrees -- still a no-op, per owner's
    explicit exclusion of run/cycle identity from the conflict check."""
    repo.save_decision(_decision())
    first = _eq(run_id="run-1", cycle_id="cycle-1")
    second = _eq(run_id="run-2", cycle_id="cycle-2")
    assert repo.save_entry_qualification(first, persisted_at=AS_OF) is True
    assert repo.save_entry_qualification(second, persisted_at=AS_OF) is False
    history = repo.list_entry_qualifications_for_instrument_session(IID, DAY)
    assert len(history) == 1
    assert history[0].run_id == "run-1"  # first write's provenance wins, not overwritten


def test_conflicting_payload_at_same_logical_identity_fails(repo) -> None:
    repo.save_decision(_decision())
    repo.save_entry_qualification(_eq(state=EntryQualificationState.QUALIFIED), persisted_at=AS_OF)
    with pytest.raises(RepositoryError, match="integrity conflict"):
        repo.save_entry_qualification(_eq(state=EntryQualificationState.NOT_YET), persisted_at=AS_OF)
    # The original, unconflicted observation must remain untouched.
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got.state is EntryQualificationState.QUALIFIED


def test_two_different_as_of_observations_both_persist(repo) -> None:
    """ID-6B found ~40% checkpoint flicker -- a later checkpoint may
    legitimately differ from an earlier one for the same candidate."""
    repo.save_decision(_decision())
    later = AS_OF.replace(hour=10, minute=15)
    repo.save_entry_qualification(
        _eq(as_of=AS_OF, state=EntryQualificationState.QUALIFIED), persisted_at=AS_OF
    )
    repo.save_entry_qualification(
        _eq(as_of=later, state=EntryQualificationState.NOT_YET), persisted_at=later
    )
    history = repo.list_entry_qualifications_for_instrument_session(IID, DAY)
    assert len(history) == 2
    assert history[0].as_of == AS_OF
    assert history[0].state is EntryQualificationState.QUALIFIED
    assert history[1].as_of == later
    assert history[1].state is EntryQualificationState.NOT_YET


def test_two_different_decision_id_observations_both_persist(repo) -> None:
    repo.save_decision(_decision("decision-1"))
    repo.save_decision(_decision("decision-2"))
    repo.save_entry_qualification(_eq(decision_id="decision-1"), persisted_at=AS_OF)
    repo.save_entry_qualification(_eq(decision_id="decision-2"), persisted_at=AS_OF)
    history = repo.list_entry_qualifications_for_instrument_session(IID, DAY)
    assert len(history) == 2
    assert {h.decision_id for h in history} == {"decision-1", "decision-2"}


# --------------------------------------------------------------------------- #
# 21-23: latest-lookup and append-only history
# --------------------------------------------------------------------------- #


def test_latest_for_decision_returns_most_recent_as_of(repo) -> None:
    repo.save_decision(_decision())
    earlier, later = AS_OF, AS_OF.replace(hour=14, minute=30)
    repo.save_entry_qualification(
        _eq(as_of=earlier, state=EntryQualificationState.QUALIFIED), persisted_at=earlier
    )
    repo.save_entry_qualification(
        _eq(as_of=later, state=EntryQualificationState.NOT_YET), persisted_at=later
    )
    latest = repo.latest_entry_qualification_for_decision("decision-1")
    assert latest.as_of == later
    assert latest.state is EntryQualificationState.NOT_YET


def test_latest_for_instrument_session_returns_most_recent(repo) -> None:
    repo.save_decision(_decision("decision-1"))
    repo.save_decision(_decision("decision-2"))
    earlier, later = AS_OF, AS_OF.replace(hour=14, minute=30)
    repo.save_entry_qualification(
        _eq(decision_id="decision-1", as_of=earlier), persisted_at=earlier
    )
    repo.save_entry_qualification(
        _eq(decision_id="decision-2", as_of=later, state=EntryQualificationState.UNKNOWN),
        persisted_at=later,
    )
    latest = repo.latest_entry_qualification_for_instrument_session(IID, DAY)
    assert latest.as_of == later
    assert latest.decision_id == "decision-2"
    assert latest.state is EntryQualificationState.UNKNOWN


def test_append_only_history_is_never_overwritten(repo) -> None:
    repo.save_decision(_decision())
    checkpoints = [AS_OF, AS_OF.replace(hour=10, minute=15), AS_OF.replace(hour=14, minute=30)]
    states = [
        EntryQualificationState.QUALIFIED,
        EntryQualificationState.NOT_YET,
        EntryQualificationState.QUALIFIED,
    ]
    for as_of, state in zip(checkpoints, states, strict=True):
        repo.save_entry_qualification(_eq(as_of=as_of, state=state), persisted_at=as_of)
    history = repo.list_entry_qualifications_for_instrument_session(IID, DAY)
    assert [h.as_of for h in history] == checkpoints
    assert [h.state for h in history] == states  # full flicker history intact, oldest first


# --------------------------------------------------------------------------- #
# 24-25: migration / existing tables
# --------------------------------------------------------------------------- #


def test_migration_creates_entry_qualifications_table(repo) -> None:
    counts = repo.record_counts()
    assert "entry_qualifications" in counts
    assert counts["entry_qualifications"] == 0


def test_existing_tables_unaffected_by_migration(repo) -> None:
    repo.save_decision(_decision())
    before = repo.record_counts()
    repo.initialize()  # idempotent re-init, mirrors test_initialize... convention
    after = repo.record_counts()
    assert before["decisions"] == after["decisions"] == 1
    assert before["instruments"] == after["instruments"]


# --------------------------------------------------------------------------- #
# 26-30: DB integrity, purity, determinism
# --------------------------------------------------------------------------- #


def test_foreign_key_to_decisions_enforced(repo) -> None:
    """No matching decisions row -- a real DB-level required-relationship
    failure, not a domain-level check."""
    eq = _eq(decision_id="nonexistent-decision")
    with pytest.raises(RepositoryError, match="integrity violation"):
        repo.save_entry_qualification(eq, persisted_at=AS_OF)


def test_no_provider_or_workflow_dependency() -> None:
    """Scoped to the ID-6C methods themselves (not the whole pre-existing
    repository.py, which legitimately mentions "Kite" in unrelated
    historical column-provenance docstrings) -- no provider/network/
    workflow call anywhere in the new persistence code."""
    new_methods_source = "".join(
        inspect.getsource(getattr(SqliteRepository, name))
        for name in (
            "save_entry_qualification",
            "get_entry_qualification",
            "latest_entry_qualification_for_decision",
            "latest_entry_qualification_for_instrument_session",
            "list_entry_qualifications_for_instrument_session",
        )
    )
    forbidden = ("kite", "zerodha", "requests.", "httpx.", "workflowstage", "provider")
    lowered = new_methods_source.lower()
    assert not any(term in lowered for term in forbidden)


def test_save_does_not_mutate_input_domain_object(repo) -> None:
    repo.save_decision(_decision())
    eq = _eq()
    snapshot = eq  # frozen dataclass -- identity check is sufficient proof
    repo.save_entry_qualification(eq, persisted_at=AS_OF)
    assert eq is snapshot
    assert eq == _eq()  # field values genuinely unchanged, not just same object


def test_serialization_is_deterministic() -> None:
    eq = _eq()
    assert ser.entry_qualification_to_row(eq) == ser.entry_qualification_to_row(eq)


def test_save_read_of_owner_exact_combination_works(repo) -> None:
    """QUALIFIED + LIVE_M5_PROVISIONAL + NOT_EVALUATED, exact round-trip."""
    repo.save_decision(_decision())
    eq = _eq(
        state=EntryQualificationState.QUALIFIED,
        evidence_finality=EntryEvidenceFinality.LIVE_M5_PROVISIONAL,
        confirmation=EntryQualificationConfirmation.NOT_EVALUATED,
    )
    assert repo.save_entry_qualification(eq, persisted_at=AS_OF) is True
    got = repo.get_entry_qualification(
        instrument_id=IID, session_date=DAY, as_of=AS_OF,
        decision_id="decision-1", methodology_version="entry-qualification-v0",
    )
    assert got == eq
