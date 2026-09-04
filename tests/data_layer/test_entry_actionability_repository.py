"""EntryActionability persistence tests (ID-7A).

Persists whatever EntryActionability object a caller constructs (no
evaluator exists yet — ID-7C). These tests prove round-trip fidelity
(including nested value-object JSON columns), idempotency, conflict
detection, the two independent binding validations (canonical Decision,
exact upstream EntryQualification), append-only/latest-lookup semantics,
and schema migration — never re-derive or reinterpret the V0 methodology
itself.
"""

from __future__ import annotations

import dataclasses
import inspect
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.data.store import serialization as ser
from athena.data.store.schema import SCHEMA_VERSION
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction
from athena.domain.market import Instrument
from athena.errors import RepositoryError
from athena.intraday.entry_actionability_models import (
    DEFAULT_METHODOLOGY_VERSION as EA_DEFAULT_METHODOLOGY_VERSION,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryLocationContext,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OpeningRangeContextBasis,
    OpeningRangeContextReference,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)
from athena.intraday.entry_qualification_engine import (
    DEFAULT_METHODOLOGY_VERSION as EQ_DEFAULT_METHODOLOGY_VERSION,
)
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationState,
)

IST = ZoneInfo("Asia/Kolkata")
IID = "NSE:TEST"
DAY = date(2026, 9, 4)
EQ_AS_OF = datetime(2026, 9, 4, 9, 45, tzinfo=IST)
EA_AS_OF = datetime(2026, 9, 4, 9, 50, tzinfo=IST)


@pytest.fixture()
def repo(tmp_path: Path):
    repository = SqliteRepository(tmp_path / "athena.db")
    repository.initialize()
    repository.upsert_instrument(
        Instrument(instrument_id=IID, symbol="TEST", exchange="NSE", series="EQ")
    )
    yield repository
    repository.close()


def _plan() -> TradePlan:
    return TradePlan(
        entry_low=Decimal("99"), entry_high=Decimal("101"), stop_loss=Decimal("97"),
        targets=(Decimal("105"),), position_size=10, risk_amount=Decimal("20"),
        risk_reward=Decimal("2"), valid_from=EQ_AS_OF, valid_until=EQ_AS_OF + timedelta(days=1),
    )


def _decision(
    decision_id: str = "decision-1",
    *,
    run_id: str = "run-1",
    cycle_id: str = "cycle-1",
    decision_type: DecisionType = DecisionType.TRADE,
    instrument_id: str | None = IID,
) -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=EQ_AS_OF,
        run_id=run_id,
        cycle_id=cycle_id,
        decision_type=decision_type,
        explanation="test decision",
        instrument_id=instrument_id,
        direction=Direction.LONG,
        trade_plan=_plan() if decision_type is DecisionType.TRADE else None,
    )


def _eq(
    *,
    decision_id: str = "decision-1",
    as_of: datetime = EQ_AS_OF,
    state: EntryQualificationState = EntryQualificationState.QUALIFIED,
    run_id: str = "run-1",
    cycle_id: str = "cycle-1",
    decision_type: DecisionType = DecisionType.TRADE,
    instrument_id: str = IID,
    methodology_version: str = EQ_DEFAULT_METHODOLOGY_VERSION,
) -> EntryQualification:
    return EntryQualification(
        instrument_id=instrument_id,
        session_date=DAY,
        as_of=as_of,
        run_id=run_id,
        cycle_id=cycle_id,
        decision_id=decision_id,
        decision_type=decision_type,
        state=state,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.CONFIRMED_BY_POLICY,
        reason_codes=(),
        evidence_refs=(),
        methodology_version=methodology_version,
        config_snapshot_id=None,
        explanation="qualified test",
    )


def _ea(
    *,
    decision_id: str = "decision-1",
    entry_qualification_as_of: datetime = EQ_AS_OF,
    entry_qualification_methodology_version: str = EQ_DEFAULT_METHODOLOGY_VERSION,
    entry_actionability_as_of: datetime = EA_AS_OF,
    entry_actionability_methodology_version: str = EA_DEFAULT_METHODOLOGY_VERSION,
    run_id: str = "run-1",
    cycle_id: str = "cycle-1",
    decision_type: DecisionType = DecisionType.TRADE,
    direction: Direction = Direction.LONG,
    entry_qualification_state: EntryQualificationState = EntryQualificationState.QUALIFIED,
    state: EntryActionabilityState = EntryActionabilityState.ACTIONABLE,
    reason_codes: tuple[EntryActionabilityReasonCode, ...] = (),
    evidence_as_of: datetime | None = EA_AS_OF,
    entry_reference: EntryReference | None = None,
    entry_location_context: EntryLocationContext | None = None,
    operative_invalidation: OperativeInvalidation | None = None,
    reward: RewardReference | None = None,
    opening_range_context: OpeningRangeContextReference | None = None,
    instrument_id: str = IID,
    explanation: str = "actionable test",
) -> EntryActionability:
    if state is EntryActionabilityState.ACTIONABLE:
        entry_reference = entry_reference if entry_reference is not None else EntryReference(
            price=Decimal("100.00"), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE
        )
        entry_location_context = entry_location_context if entry_location_context is not None else (
            EntryLocationContext(vwap=Decimal("99.50"), vwap_deviation_pct=Decimal("0.50"))
        )
        operative_invalidation = operative_invalidation if operative_invalidation is not None else (
            OperativeInvalidation(level=Decimal("98.00"), basis=InvalidationBasis.VWAP_LOSS)
        )
        reward = reward if reward is not None else RewardReference(
            t1_price=Decimal("101.00"), t2_price=Decimal("101.50"), basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=Decimal("0.5"), reward_risk_to_t2=Decimal("0.75"),
        )
    return EntryActionability(
        instrument_id=instrument_id,
        session_date=DAY,
        entry_qualification_as_of=entry_qualification_as_of,
        decision_id=decision_id,
        entry_qualification_methodology_version=entry_qualification_methodology_version,
        entry_actionability_as_of=entry_actionability_as_of,
        entry_actionability_methodology_version=entry_actionability_methodology_version,
        decision_type=decision_type,
        direction=direction,
        entry_qualification_state=entry_qualification_state,
        run_id=run_id,
        cycle_id=cycle_id,
        state=state,
        reason_codes=reason_codes,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        evidence_as_of=evidence_as_of,
        entry_reference=entry_reference,
        entry_location_context=entry_location_context,
        operative_invalidation=operative_invalidation,
        reward=reward,
        opening_range_context=opening_range_context,
        evaluated_at=entry_actionability_as_of,
        explanation=explanation,
    )


def _seed(repo, *, decision_type: DecisionType = DecisionType.TRADE) -> None:
    repo.save_decision(_decision(decision_type=decision_type))
    repo.save_entry_qualification(_eq(decision_type=decision_type), persisted_at=EQ_AS_OF)


# --------------------------------------------------------------------------- #
# 1-6: round-trip fidelity, including nested value-object JSON columns
# --------------------------------------------------------------------------- #


def test_actionable_round_trips_exactly_with_all_value_objects(repo) -> None:
    _seed(repo)
    ea = _ea(
        opening_range_context=OpeningRangeContextReference(
            level=Decimal("97.00"), basis=OpeningRangeContextBasis.OR15_BOUNDARY
        )
    )
    assert repo.save_entry_actionability(ea, persisted_at=EA_AS_OF) is True
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got == ea


def test_not_actionable_round_trips_with_no_value_objects(repo) -> None:
    _seed(repo)
    ea = _ea(
        state=EntryActionabilityState.NOT_ACTIONABLE,
        reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
        evidence_as_of=None,
    )
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got == ea
    assert got.entry_reference is None
    assert got.evidence_as_of is None


def test_reason_codes_order_is_preserved(repo) -> None:
    _seed(repo)
    ordered = (
        EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,
        EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,
    )
    ea = _ea(state=EntryActionabilityState.NOT_ACTIONABLE, reason_codes=ordered)
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got.reason_codes == ordered


def test_decimal_and_timezone_round_trip_exactly(repo) -> None:
    _seed(repo)
    ea = _ea(
        entry_reference=EntryReference(price=Decimal("1234.5678"), basis=EntryReferenceBasis.QUALIFYING_M5_CLOSE),
        operative_invalidation=OperativeInvalidation(level=Decimal("1200.1234"), basis=InvalidationBasis.VWAP_LOSS),
    )
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got.entry_reference.price == Decimal("1234.5678")
    assert isinstance(got.entry_reference.price, Decimal)
    assert got.operative_invalidation.level == Decimal("1200.1234")
    assert got.entry_qualification_as_of == EQ_AS_OF
    assert got.entry_qualification_as_of.tzinfo is not None
    assert got.entry_actionability_as_of == EA_AS_OF
    assert got.entry_actionability_as_of.tzinfo is not None
    assert got.evidence_as_of == EA_AS_OF
    assert got.evidence_as_of.tzinfo is not None


def test_reward_none_ratios_round_trip(repo) -> None:
    _seed(repo)
    ea = _ea(
        reward=RewardReference(
            t1_price=Decimal("101.00"), t2_price=Decimal("101.50"), basis=RewardBasis.GOAL_BANDS_ONLY,
            reward_risk_to_t1=None, reward_risk_to_t2=None,
        )
    )
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got.reward.reward_risk_to_t1 is None
    assert got.reward.reward_risk_to_t2 is None


def test_direction_and_denormalized_context_preserved(repo) -> None:
    _seed(repo)
    ea = _ea()
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got.direction is Direction.LONG
    assert got.entry_qualification_state is EntryQualificationState.QUALIFIED
    assert got.decision_type is DecisionType.TRADE
    assert got.run_id == "run-1"
    assert got.cycle_id == "cycle-1"


# --------------------------------------------------------------------------- #
# 7-12: two independent bindings (Decision, exact upstream EQ identity)
# --------------------------------------------------------------------------- #


def test_missing_decision_raises_repository_error(repo) -> None:
    ea = _ea(decision_id="nonexistent-decision")
    with pytest.raises(RepositoryError, match="references unknown decision_id"):
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)


def test_decision_type_mismatch_fails(repo) -> None:
    repo.save_decision(_decision(decision_type=DecisionType.TRADE))
    repo.save_entry_qualification(_eq(), persisted_at=EQ_AS_OF)
    with pytest.raises(RepositoryError, match="decision binding mismatch: decision_type"):
        repo.save_entry_actionability(_ea(decision_type=DecisionType.WATCH), persisted_at=EA_AS_OF)


def test_run_id_mismatch_against_canonical_decision_fails(repo) -> None:
    _seed(repo)
    with pytest.raises(RepositoryError, match="decision binding mismatch: run_id"):
        repo.save_entry_actionability(_ea(run_id="run-2"), persisted_at=EA_AS_OF)


def test_cycle_id_mismatch_against_canonical_decision_fails(repo) -> None:
    _seed(repo)
    with pytest.raises(RepositoryError, match="decision binding mismatch: cycle_id"):
        repo.save_entry_actionability(_ea(cycle_id="cycle-2"), persisted_at=EA_AS_OF)


def test_instrument_mismatch_against_canonical_decision_fails(repo) -> None:
    _seed(repo)
    with pytest.raises(RepositoryError, match="decision binding mismatch: instrument_id"):
        repo.save_entry_actionability(_ea(instrument_id="NSE:OTHER"), persisted_at=EA_AS_OF)


def test_missing_upstream_eq_identity_raises_repository_error(repo) -> None:
    """The referenced Decision exists, but no EntryQualification was ever
    persisted at the exact identity `ea` claims to bind to."""
    repo.save_decision(_decision())
    ea = _ea()
    with pytest.raises(RepositoryError, match="references unknown EntryQualification identity"):
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)


def test_eq_state_mismatch_against_real_persisted_eq_fails(repo) -> None:
    """`ea.entry_qualification_state` must agree with the real, persisted
    EntryQualification row it claims to bind to — a single-column
    reference alone does not prove that."""
    repo.save_decision(_decision())
    repo.save_entry_qualification(_eq(state=EntryQualificationState.QUALIFIED), persisted_at=EQ_AS_OF)
    contradictory = _ea(entry_qualification_state=EntryQualificationState.NOT_YET)
    with pytest.raises(RepositoryError, match="EntryQualification binding mismatch"):
        repo.save_entry_actionability(contradictory, persisted_at=EA_AS_OF)


def test_valid_binding_persists(repo) -> None:
    _seed(repo)
    assert repo.save_entry_actionability(_ea(), persisted_at=EA_AS_OF) is True


# --------------------------------------------------------------------------- #
# 13-17: idempotency, conflict detection, multiple observations
# --------------------------------------------------------------------------- #


def test_repeated_identical_save_is_idempotent(repo) -> None:
    _seed(repo)
    ea = _ea()
    assert repo.save_entry_actionability(ea, persisted_at=EA_AS_OF) is True
    assert repo.save_entry_actionability(ea, persisted_at=EA_AS_OF) is False
    history = repo.list_entry_actionabilities_for_instrument_session(IID, DAY)
    assert len(history) == 1


def test_conflicting_payload_at_same_logical_identity_fails(repo) -> None:
    _seed(repo)
    repo.save_entry_actionability(_ea(explanation="first"), persisted_at=EA_AS_OF)
    with pytest.raises(RepositoryError, match="integrity conflict"):
        repo.save_entry_actionability(_ea(explanation="different"), persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got.explanation == "first"  # original untouched


def test_different_evaluated_at_same_methodology_conclusion_is_still_idempotent(repo) -> None:
    """evaluated_at is documented as diagnostic-only, never identity — a
    re-evaluation reaching the identical methodology conclusion at a
    different wall-clock instant must be treated as the same observation,
    never a conflict."""
    _seed(repo)
    first = _ea()
    assert repo.save_entry_actionability(first, persisted_at=EA_AS_OF) is True
    replayed = dataclasses.replace(first, evaluated_at=EA_AS_OF + timedelta(seconds=5))
    assert repo.save_entry_actionability(replayed, persisted_at=EA_AS_OF) is False


def test_two_different_entry_actionability_as_of_observations_both_persist(repo) -> None:
    _seed(repo)
    later = EA_AS_OF.replace(minute=55)
    repo.save_entry_actionability(_ea(entry_actionability_as_of=EA_AS_OF), persisted_at=EA_AS_OF)
    repo.save_entry_actionability(
        _ea(
            entry_actionability_as_of=later,
            state=EntryActionabilityState.NOT_ACTIONABLE,
            reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,),
            evidence_as_of=None,
        ),
        persisted_at=later,
    )
    history = repo.list_entry_actionabilities_for_instrument_session(IID, DAY)
    assert len(history) == 2


def test_invalid_duplicate_cannot_hide_behind_idempotency(repo) -> None:
    _seed(repo)
    valid = _ea()
    assert repo.save_entry_actionability(valid, persisted_at=EA_AS_OF) is True
    contradictory = _ea(run_id="run-2")
    with pytest.raises(RepositoryError, match="decision binding mismatch: run_id"):
        repo.save_entry_actionability(contradictory, persisted_at=EA_AS_OF)
    got = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert got.run_id == "run-1"


# --------------------------------------------------------------------------- #
# 18-22: latest-lookup and append-only history
# --------------------------------------------------------------------------- #


def test_latest_for_entry_qualification_returns_most_recent_ea_as_of(repo) -> None:
    _seed(repo)
    earlier, later = EA_AS_OF, EA_AS_OF.replace(minute=59)
    repo.save_entry_actionability(_ea(entry_actionability_as_of=earlier), persisted_at=earlier)
    repo.save_entry_actionability(
        _ea(
            entry_actionability_as_of=later, state=EntryActionabilityState.NOT_ACTIONABLE,
            reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,), evidence_as_of=None,
        ),
        persisted_at=later,
    )
    latest = repo.latest_entry_actionability_for_entry_qualification(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
    )
    assert latest.entry_actionability_as_of == later
    assert latest.state is EntryActionabilityState.NOT_ACTIONABLE


def test_latest_for_instrument_session_returns_most_recent(repo) -> None:
    _seed(repo)
    earlier, later = EA_AS_OF, EA_AS_OF.replace(minute=59)
    repo.save_entry_actionability(_ea(entry_actionability_as_of=earlier), persisted_at=earlier)
    repo.save_entry_actionability(
        _ea(
            entry_actionability_as_of=later, state=EntryActionabilityState.NOT_ACTIONABLE,
            reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,), evidence_as_of=None,
        ),
        persisted_at=later,
    )
    latest = repo.latest_entry_actionability_for_instrument_session(IID, DAY)
    assert latest.entry_actionability_as_of == later
    assert latest.state is EntryActionabilityState.NOT_ACTIONABLE


def test_latest_lookup_is_never_confused_with_decision_id_alone(repo) -> None:
    """latest_entry_actionability_for_entry_qualification must match the
    FULL exact EQ identity, not decision_id alone — a second EQ
    observation at a different as_of for the same decision_id must not be
    conflated with the first (ID-7A authorization item 20)."""
    repo.save_decision(_decision())
    repo.save_entry_qualification(_eq(as_of=EQ_AS_OF), persisted_at=EQ_AS_OF)
    later_eq_as_of = EQ_AS_OF.replace(minute=46)
    repo.save_entry_qualification(_eq(as_of=later_eq_as_of), persisted_at=later_eq_as_of)

    repo.save_entry_actionability(
        _ea(entry_qualification_as_of=EQ_AS_OF, entry_actionability_as_of=EA_AS_OF),
        persisted_at=EA_AS_OF,
    )
    later_ea_as_of = EA_AS_OF.replace(minute=1)
    repo.save_entry_actionability(
        _ea(entry_qualification_as_of=later_eq_as_of, entry_actionability_as_of=later_ea_as_of),
        persisted_at=later_ea_as_of,
    )

    bound_to_first = repo.latest_entry_actionability_for_entry_qualification(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
    )
    assert bound_to_first.entry_qualification_as_of == EQ_AS_OF
    assert bound_to_first.entry_actionability_as_of == EA_AS_OF


def test_append_only_history_is_never_overwritten(repo) -> None:
    _seed(repo)
    checkpoints = [EA_AS_OF, EA_AS_OF.replace(minute=55), EA_AS_OF.replace(hour=10, minute=15)]
    for as_of in checkpoints:
        repo.save_entry_actionability(_ea(entry_actionability_as_of=as_of), persisted_at=as_of)
    history = repo.list_entry_actionabilities_for_instrument_session(IID, DAY)
    assert [h.entry_actionability_as_of for h in history] == checkpoints


def test_historical_actionable_row_state_unaffected_by_a_later_write(repo) -> None:
    """Append-only immutability: an ACTIONABLE row persisted earlier keeps
    reading ACTIONABLE even after a later, unrelated NOT_ACTIONABLE row is
    persisted for the same instrument/session."""
    _seed(repo)
    repo.save_entry_actionability(_ea(entry_actionability_as_of=EA_AS_OF), persisted_at=EA_AS_OF)
    later = EA_AS_OF.replace(minute=59)
    repo.save_entry_actionability(
        _ea(
            entry_actionability_as_of=later, state=EntryActionabilityState.NOT_ACTIONABLE,
            reason_codes=(EntryActionabilityReasonCode.INVALIDATION_UNAVAILABLE,), evidence_as_of=None,
        ),
        persisted_at=later,
    )
    original = repo.get_entry_actionability(
        instrument_id=IID, session_date=DAY, entry_qualification_as_of=EQ_AS_OF,
        decision_id="decision-1", entry_qualification_methodology_version=EQ_DEFAULT_METHODOLOGY_VERSION,
        entry_actionability_as_of=EA_AS_OF, entry_actionability_methodology_version=EA_DEFAULT_METHODOLOGY_VERSION,
    )
    assert original.state is EntryActionabilityState.ACTIONABLE


# --------------------------------------------------------------------------- #
# 23-25: schema / migration
# --------------------------------------------------------------------------- #


def test_schema_version_bumped_to_18() -> None:
    assert SCHEMA_VERSION == 18


def test_migration_creates_entry_actionabilities_table(repo) -> None:
    counts = repo.record_counts()
    assert "entry_actionabilities" in counts
    assert counts["entry_actionabilities"] == 0


def test_existing_tables_unaffected_by_migration(repo) -> None:
    _seed(repo)
    before = repo.record_counts()
    repo.initialize()  # idempotent re-init
    after = repo.record_counts()
    assert before["decisions"] == after["decisions"] == 1
    assert before["entry_qualifications"] == after["entry_qualifications"] == 1


def test_unique_constraint_on_full_composite_identity(repo) -> None:
    """The schema's own PRIMARY KEY (not just repository-level idempotency
    logic) rejects a raw duplicate insert at the same identity."""
    _seed(repo)
    ea = _ea()
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    with pytest.raises(sqlite3.IntegrityError), repo.connection:
        repo.connection.execute(
            "INSERT INTO entry_actionabilities "
            "(instrument_id, session_date, entry_qualification_as_of, decision_id, "
            "entry_qualification_methodology_version, entry_actionability_as_of, "
            "entry_actionability_methodology_version, run_id, cycle_id, decision_type, "
            "direction, entry_qualification_state, state, reason_codes_json, "
            "evidence_finality, evidence_as_of, entry_reference_json, "
            "entry_location_context_json, operative_invalidation_json, reward_json, "
            "opening_range_context_json, evaluated_at, explanation, persisted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*ser.entry_actionability_to_row(ea), EA_AS_OF.isoformat()),
        )


def test_foreign_key_to_decisions_enforced_at_db_level(repo) -> None:
    ea = _ea(decision_id="nonexistent-decision")
    with pytest.raises(sqlite3.IntegrityError), repo.connection:
        repo.connection.execute(
            "INSERT INTO entry_actionabilities "
            "(instrument_id, session_date, entry_qualification_as_of, decision_id, "
            "entry_qualification_methodology_version, entry_actionability_as_of, "
            "entry_actionability_methodology_version, run_id, cycle_id, decision_type, "
            "direction, entry_qualification_state, state, reason_codes_json, "
            "evidence_finality, evidence_as_of, entry_reference_json, "
            "entry_location_context_json, operative_invalidation_json, reward_json, "
            "opening_range_context_json, evaluated_at, explanation, persisted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*ser.entry_actionability_to_row(ea), EA_AS_OF.isoformat()),
        )


# --------------------------------------------------------------------------- #
# 26-29: purity, determinism, isolation proofs
# --------------------------------------------------------------------------- #


def test_no_evaluator_workflow_or_provider_dependency() -> None:
    """Scoped to the new ID-7A methods themselves — no evaluator (that is
    ID-7C), no workflow/provider/network call anywhere in the new
    persistence code."""
    new_methods_source = "".join(
        inspect.getsource(getattr(SqliteRepository, name))
        for name in (
            "save_entry_actionability",
            "get_entry_actionability",
            "latest_entry_actionability_for_entry_qualification",
            "latest_entry_actionability_for_instrument_session",
            "list_entry_actionabilities_for_instrument_session",
        )
    )
    forbidden = (
        "kite", "zerodha", "requests.", "httpx.", "workflowstage", "provider",
        "entryactionabilityengine",
    )
    lowered = new_methods_source.lower()
    assert not any(term in lowered for term in forbidden)


def test_save_does_not_mutate_input_domain_object(repo) -> None:
    _seed(repo)
    ea = _ea()
    snapshot = ea
    repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    assert ea is snapshot
    assert ea == _ea()


def test_serialization_is_deterministic() -> None:
    ea = _ea()
    assert ser.entry_actionability_to_row(ea) == ser.entry_actionability_to_row(ea)


def test_missing_decision_check_fires_before_any_insert(repo) -> None:
    ea = _ea(decision_id="nonexistent-decision")
    with pytest.raises(RepositoryError, match="references unknown decision_id"):
        repo.save_entry_actionability(ea, persisted_at=EA_AS_OF)
    assert repo.record_counts()["entry_actionabilities"] == 0
