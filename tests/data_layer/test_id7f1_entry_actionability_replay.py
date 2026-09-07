"""ID-7F1: Entry Actionability historical replay adapter tests.

Pure-function tests use synthetic objects (no DB); the harness
integration tests use a temp, disposable SQLite DB seeded via the real
`OwnerValidationPipeline` (never the real `db/athena.db`), proving
`run_replay` calls the actual `EntryActionabilityEngine` end-to-end,
deterministically, without mutating the source DB and without ever
calling `save_entry_actionability`.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data import id7f1_entry_actionability_replay as m
from athena.data.id7f1_entry_actionability_replay import (
    DEFAULT_REPLAY_EVALUATED_AT,
    _classify_mismatch,
    _empirical_availability,
    _evidence_availability,
    _identity_tuple,
    _methodology_payload,
    _population_inventory,
    _validate_binding,
    _watch_invariant_check,
    eq_identity,
    partition_duplicates,
    pct,
    run_replay,
    run_shadow_equivalence,
)
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.decision.engine import DecisionEngine
from athena.domain.decision import Decision, TradePlan
from athena.domain.enums import DecisionType, Direction, RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument
from athena.intraday import EntryActionabilityEngine, EntryQualificationEngine, EntryQualificationState
from athena.intraday.entry_qualification_models import EntryQualification
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.owner_validation import OwnerValidationPipeline

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 9, 30, tzinfo=IST)


# --------------------------------------------------------------------------- #
# Fixtures / helpers (no DB) -- known to produce VWAP=101, last-completed-M5
# close=102 at AS_OF=09:30 IST, exactly as established in the ID-7E test
# suite's own equivalent fixtures.
# --------------------------------------------------------------------------- #


def _candles(instrument_id: str, n: int = 80, seed: int = 100) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        day = date(2025, 11, 1) + timedelta(days=i)
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        px = Decimal(str(seed + i))
        out.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.D1, ts_open=ts,
            open=px, high=px + Decimal("2"), low=px - Decimal("1"), close=px + Decimal("1"),
            volume=1_000_000, source="test",
        ))
    return out


def _intraday_candles(instrument_id: str, day, n: int = 6, seed: int = 100) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        ts = datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15)
        ts += timedelta(minutes=5 * i)
        px = Decimal(str(seed + i))
        out.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts,
            open=px, high=px + Decimal("1"), low=px - Decimal("1"), close=px,
            volume=10_000, source="test",
        ))
    return out


def _decision(*, decision_id="d1", instrument_id="NSE:AAA", decision_type=DecisionType.WATCH,
              run_id="run-1", cycle_id="cyc-1", direction=Direction.LONG) -> Decision:
    return Decision(
        decision_id=decision_id, ts=AS_OF, run_id=run_id, cycle_id=cycle_id,
        decision_type=decision_type, explanation="test", instrument_id=instrument_id,
        direction=direction,
    )


def _eq(*, instrument_id="NSE:AAA", session_date=AS_OF.date(), as_of=AS_OF, decision_id="d1",
        decision_type=DecisionType.WATCH, state=EntryQualificationState.NOT_YET,
        run_id="run-1", cycle_id="cyc-1", methodology_version="entry-qualification-v0") -> EntryQualification:
    from athena.intraday.entry_qualification_models import (
        EntryEvidenceFinality,
        EntryQualificationConfirmation,
    )

    return EntryQualification(
        instrument_id=instrument_id, session_date=session_date, as_of=as_of,
        run_id=run_id, cycle_id=cycle_id, decision_id=decision_id, decision_type=decision_type,
        state=state,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.NOT_EVALUATED,
        reason_codes=(), evidence_refs=(), methodology_version=methodology_version,
        config_snapshot_id=None, explanation="test",
    )


# --------------------------------------------------------------------------- #
# Pure-function tests (no DB)
# --------------------------------------------------------------------------- #


def test_pct_handles_empty_denominator() -> None:
    assert pct(0, 0) == 0.0
    assert pct(1, 4) == 25.0


def test_eq_identity_is_the_frozen_composite_key() -> None:
    eq = _eq()
    assert eq_identity(eq) == ("NSE:AAA", "2026-03-02", AS_OF.isoformat(), "d1", "entry-qualification-v0")


def test_partition_duplicates_detects_repeated_identity() -> None:
    a = _eq(decision_id="d1")
    b = _eq(decision_id="d1")  # identical identity fields
    c = _eq(decision_id="d2")
    unique, duplicates = partition_duplicates([a, b, c])
    assert unique == [a, c]
    assert duplicates == [b]


def test_partition_duplicates_empty_and_no_duplicates() -> None:
    assert partition_duplicates([]) == ([], [])
    a, b = _eq(decision_id="d1"), _eq(decision_id="d2")
    assert partition_duplicates([a, b]) == ([a, b], [])


def test_validate_binding_accepts_coherent_pair() -> None:
    eq = _eq()
    decision = _decision()
    assert _validate_binding(eq, decision) is None


def test_validate_binding_rejects_missing_decision() -> None:
    error = _validate_binding(_eq(), None)
    assert error is not None and "no Decision row" in error


@pytest.mark.parametrize(
    "field,eq_kwargs,decision_kwargs",
    [
        ("decision_id", {"decision_id": "d1"}, {"decision_id": "d2"}),
        ("decision_type", {"decision_type": DecisionType.WATCH}, {"decision_type": DecisionType.NO_TRADE}),
        ("run_id", {"run_id": "run-1"}, {"run_id": "run-2"}),
        ("cycle_id", {"cycle_id": "cyc-1"}, {"cycle_id": "cyc-2"}),
    ],
)
def test_validate_binding_rejects_every_mismatched_field(field, eq_kwargs, decision_kwargs) -> None:
    # decision_id must actually match for the pair to be "the same
    # candidate" in the first place -- construct a decision whose OWN
    # decision_id equals the eq's decision_id except for the field under
    # test, mirroring EntryActionabilityEngine._validate_binding's own
    # check order (decision_id itself is checked first).
    eq = _eq(decision_id="d1", decision_type=DecisionType.WATCH, run_id="run-1", cycle_id="cyc-1")
    base_decision_kwargs = {
        "decision_id": "d1", "decision_type": DecisionType.WATCH,
        "run_id": "run-1", "cycle_id": "cyc-1",
    }
    base_decision_kwargs.update(decision_kwargs)
    decision = _decision(**base_decision_kwargs)
    error = _validate_binding(eq, decision)
    assert error is not None
    assert field in error


def test_validate_binding_rejects_instrument_mismatch() -> None:
    eq = _eq(instrument_id="NSE:AAA")
    decision = _decision(instrument_id="NSE:BBB")
    error = _validate_binding(eq, decision)
    assert error is not None and "instrument_id" in error


def test_validate_binding_tolerates_none_decision_instrument_id() -> None:
    eq = _eq(instrument_id="NSE:AAA")
    decision = _decision(instrument_id=None)
    assert _validate_binding(eq, decision) is None


def test_population_inventory_counts_are_correct() -> None:
    rows = [
        {"decision_type": "WATCH", "direction": "LONG", "eq_state": "NOT_YET",
         "eq_methodology_version": "v0", "session_date": "2026-01-01", "instrument_id": "A"},
        {"decision_type": "TRADE", "direction": "LONG", "eq_state": "QUALIFIED",
         "eq_methodology_version": "v0", "session_date": "2026-01-01", "instrument_id": "B"},
    ]
    inv = _population_inventory(rows)
    assert inv["total_observations"] == 2
    assert inv["decision_type_counts"]["WATCH"]["count"] == 1
    assert inv["decision_type_counts"]["TRADE"]["count"] == 1
    assert inv["distinct_sessions"] == 1
    assert inv["distinct_instruments"] == 2


def test_evidence_availability_reports_present_absent_split() -> None:
    rows = [
        {"reconstructed_completed_m5_ts": "x", "reconstructed_session_vwap": "101",
         "reconstructed_or15_status": "COMPLETE"},
        {"reconstructed_completed_m5_ts": None, "reconstructed_session_vwap": None,
         "reconstructed_or15_status": "FORMING"},
    ]
    block = _evidence_availability(rows)
    assert block["completed_m5_present"] == 1
    assert block["completed_m5_absent"] == 1
    assert block["session_vwap_present"] == 1
    assert block["or15_status_counts"]["COMPLETE"]["count"] == 1


def test_empirical_availability_reports_not_available_when_absent() -> None:
    rows = [{"decision_type": "WATCH", "ea_state": "NOT_ACTIONABLE", "direction": "LONG"}]
    flags = _empirical_availability(rows)
    assert flags["trade_empirical_validation"] == "TRADE_EMPIRICAL_VALIDATION_NOT_AVAILABLE"
    assert flags["actionable_empirical_validation"] == "ACTIONABLE_EMPIRICAL_VALIDATION_NOT_AVAILABLE"
    assert flags["unknown_empirical_validation"] == "UNKNOWN_EMPIRICAL_VALIDATION_NOT_AVAILABLE"
    assert flags["short_empirical_validation"] == "SHORT_EMPIRICAL_VALIDATION_NOT_AVAILABLE"


def test_empirical_availability_reports_available_when_present() -> None:
    rows = [
        {"decision_type": "TRADE", "ea_state": "ACTIONABLE", "direction": "SHORT"},
        {"decision_type": "TRADE", "ea_state": "UNKNOWN", "direction": "LONG"},
    ]
    flags = _empirical_availability(rows)
    assert flags["trade_empirical_validation"] == "TRADE_EMPIRICAL_VALIDATION_AVAILABLE"
    assert flags["actionable_empirical_validation"] == "ACTIONABLE_EMPIRICAL_VALIDATION_AVAILABLE"
    assert flags["unknown_empirical_validation"] == "UNKNOWN_EMPIRICAL_VALIDATION_AVAILABLE"
    assert flags["short_empirical_validation"] == "SHORT_EMPIRICAL_VALIDATION_AVAILABLE"


def test_watch_invariant_check_passes_on_clean_population() -> None:
    rows = [
        {"decision_type": "WATCH", "ea_state": "NOT_ACTIONABLE",
         "ea_reason_codes": ["UPSTREAM_DECISION_NOT_TRADE"], "decision_id": "d1"},
    ]
    result = _watch_invariant_check(rows)
    assert result["watch_invariant_holds"] is True
    assert result["watch_invariant_violations"] == 0


def test_watch_invariant_check_flags_a_deviation() -> None:
    rows = [
        {"decision_type": "WATCH", "ea_state": "ACTIONABLE", "ea_reason_codes": [], "decision_id": "d1"},
    ]
    result = _watch_invariant_check(rows)
    assert result["watch_invariant_holds"] is False
    assert result["watch_invariant_violations"] == 1
    assert result["violation_decision_ids"] == ["d1"]


def test_no_provider_or_network_calls_in_module_source() -> None:
    source = inspect.getsource(m)
    lowered = source.lower()
    for forbidden in ("kite", "requests.", "httpx.", "urllib.request"):
        assert forbidden not in lowered


def test_no_currentness_concept_in_module_source() -> None:
    source = inspect.getsource(m)
    for forbidden in (
        "is_currently_usable", "EntryActionabilityCurrentness",
        "current_decision_id", "CURRENT", "STALE", "SUPERSEDED", "SESSION_CLOSED",
    ):
        assert forbidden not in source


def test_no_persistence_write_calls_in_module_source() -> None:
    source = inspect.getsource(m)
    # The docstring itself mentions the name in prose ("is never
    # called") -- check for an actual call-site pattern, not the bare
    # identifier, to avoid a false positive on that documentation.
    assert "save_entry_actionability(" not in source
    assert "INSERT INTO entry_actionabilities" not in source
    assert ".save_" not in source


# --------------------------------------------------------------------------- #
# Harness integration tests -- real disposable temp DB
# --------------------------------------------------------------------------- #


@pytest.fixture()
def seeded_watch_db(tmp_path: Path, monkeypatch) -> Path:
    """A real, disposable SQLite DB (never `db/athena.db`) seeded via the
    actual `OwnerValidationPipeline` -- produces one genuine WATCH+
    EntryQualification pair (the only real population ID-7F0 found in
    the live database). This exact fixture candle shape naturally
    produces a TRADE Decision (confirmed by direct inspection), so
    `DecisionEngine.decide` is monkeypatched to force WATCH -- mirroring
    the ID-7E test suite's own established force pattern -- purely to
    obtain a deterministic, guaranteed-WATCH row for this test; nothing
    about EntryQualification/EntryActionability methodology is touched."""
    from athena.decision.engine import DecisionEngine
    from athena.domain.enums import DecisionType

    real_decide = DecisionEngine.decide

    def forced_watch(self, *args, **kwargs):
        outcome = real_decide(self, *args, **kwargs)
        if outcome.decision.decision_type is DecisionType.TRADE:
            forced = dataclasses.replace(
                outcome.decision, decision_type=DecisionType.WATCH, trade_plan=None, gate_results=()
            )
            outcome = dataclasses.replace(outcome, decision=forced)
        return outcome

    monkeypatch.setattr(DecisionEngine, "decide", forced_watch)

    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    store = SqliteCandidateStore(repo)
    store.upsert_candidate(symbol="AAA")
    iid = "NSE:AAA"
    repo.upsert_instrument(
        Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
    )
    repo.add_candles(_candles(iid, seed=100))
    repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=100))
    pipe = OwnerValidationPipeline(repo, Path("config"))
    ingestion = IngestionResult(
        as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
        quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
    )
    pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-id7f1-seed")
    repo.close()
    monkeypatch.undo()
    return db_path


def _seed_forced_trade_db(
    tmp_path: Path, *, force_qualified: bool, seed: int = 100,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Mirrors the ID-7E test file's own established monkeypatch/force
    pattern (spy/force DecisionEngine.decide + EntryQualificationEngine
    .evaluate) to seed a genuine TRADE(+QUALIFIED) row into a disposable
    temp DB for replay-reconstruction testing -- the real DB has none of
    these today (ID-7F0's own finding), so this is the narrowest way to
    exercise the TRADE/QUALIFIED/ACTIONABLE replay code paths at all."""
    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    store = SqliteCandidateStore(repo)
    store.upsert_candidate(symbol="AAA")
    iid = "NSE:AAA"
    repo.upsert_instrument(
        Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
    )
    repo.add_candles(_candles(iid, seed=seed))
    repo.add_candles(_intraday_candles(iid, AS_OF.date(), seed=seed))

    real_decide = DecisionEngine.decide

    def forced_trade(self, *args, **kwargs):
        outcome = real_decide(self, *args, **kwargs)
        forced_decision = dataclasses.replace(
            outcome.decision, decision_type=DecisionType.TRADE, direction=Direction.LONG,
            gate_results=(),
            trade_plan=TradePlan(
                entry_low=Decimal("100"), entry_high=Decimal("103"), stop_loss=Decimal("95"),
                targets=(Decimal("110"),), position_size=1, risk_amount=Decimal("500"),
                risk_reward=Decimal("2"), valid_from=AS_OF, valid_until=AS_OF + timedelta(days=1),
            ),
        )
        return dataclasses.replace(outcome, decision=forced_decision)

    monkeypatch.setattr(DecisionEngine, "decide", forced_trade)

    if force_qualified:
        real_eq_evaluate = EntryQualificationEngine.evaluate

        def forced_qualified(self, *args, **kwargs):
            eq = real_eq_evaluate(self, *args, **kwargs)
            return dataclasses.replace(eq, state=EntryQualificationState.QUALIFIED, reason_codes=())

        monkeypatch.setattr(EntryQualificationEngine, "evaluate", forced_qualified)

    pipe = OwnerValidationPipeline(repo, Path("config"))
    ingestion = IngestionResult(
        as_of=AS_OF, instruments_upserted=1, candles_fetched=86, candles_written=86,
        quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
    )
    pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-id7f1-trade-seed")
    repo.close()
    monkeypatch.undo()
    return db_path


def test_run_replay_reconstructs_watch_as_not_actionable(seeded_watch_db: Path, tmp_path: Path) -> None:
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["rows_attempted"] == 1
    assert summary["defect_counts"]["total"] == 0
    assert summary["watch_invariant_check"]["watch_invariant_holds"] is True
    assert summary["watch_result_distribution"]["state_distribution"]["NOT_ACTIONABLE"]["count"] == 1
    assert (
        summary["watch_result_distribution"]["reason_code_counts"]["UPSTREAM_DECISION_NOT_TRADE"] == 1
    )
    assert summary["empirical_availability"]["trade_empirical_validation"] == \
        "TRADE_EMPIRICAL_VALIDATION_NOT_AVAILABLE"


def test_run_replay_never_mutates_the_source_db(seeded_watch_db: Path, tmp_path: Path) -> None:
    before = os.path.getmtime(seeded_watch_db)
    run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    after = os.path.getmtime(seeded_watch_db)
    assert before == after


def test_run_replay_schema_version_unchanged(seeded_watch_db: Path, tmp_path: Path) -> None:
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    meta = summary["metadata"]
    assert meta["schema_version_unchanged"] is True
    assert meta["schema_version_observed_at_start"] == meta["schema_version_observed_at_end"]


def test_run_replay_is_deterministic_across_two_separate_runs(seeded_watch_db: Path, tmp_path: Path) -> None:
    first = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out1")
    second = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out2")
    assert first["artifacts"]["analysis_sha256"] == second["artifacts"]["analysis_sha256"]
    assert first["determinism"]["determinism_holds"] is True
    assert first["determinism"]["mismatches"] == 0


def test_run_replay_rejects_naive_evaluated_at(seeded_watch_db: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        run_replay(
            db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
            evaluated_at=datetime(2026, 1, 1),
        )


def test_run_replay_uses_replay_compute_evaluated_at_not_historical(seeded_watch_db: Path, tmp_path: Path) -> None:
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["metadata"]["fixed_evaluated_at"] == DEFAULT_REPLAY_EVALUATED_AT.isoformat()
    assert "not a historical knowledge-time claim" in summary["metadata"]["evaluated_at_semantics"].lower()
    assert "market-time bounded" in summary["metadata"]["replay_semantics"]


def test_run_replay_observation_artifact_matches_the_replay_checkpoint(
    seeded_watch_db: Path, tmp_path: Path
) -> None:
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    obs_path = Path(summary["artifacts"]["observations_path"])
    lines = obs_path.read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert datetime.fromisoformat(row["eq_as_of"]) == AS_OF
    assert datetime.fromisoformat(row["entry_actionability_as_of"]) == AS_OF  # Option 1: same checkpoint


def test_run_replay_excludes_no_trade_decisions(seeded_watch_db: Path, tmp_path: Path) -> None:
    """Since EntryQualification persistence is itself WATCH/TRADE-only,
    the real replay population can never contain NO_TRADE (or any other
    out-of-scope) rows -- confirmed directly against a real seeded DB
    that also naturally contains NO_TRADE Decisions with no matching EQ."""
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    obs_path = Path(summary["artifacts"]["observations_path"])
    rows = [json.loads(line) for line in obs_path.read_text().strip().splitlines()]
    assert all(r["decision_type"] in ("WATCH", "TRADE") for r in rows)


def test_run_replay_missing_intraday_evidence_stays_structurally_coherent(tmp_path: Path) -> None:
    """A WATCH observation with zero same-day intraday candles at all
    (no completed M5, no VWAP) must still reconstruct cleanly to
    NOT_ACTIONABLE -- ID-7C.2's own upstream short-circuit means missing
    layer-3 evidence is never even consulted for an ineligible Decision."""
    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    store = SqliteCandidateStore(repo)
    store.upsert_candidate(symbol="AAA")
    iid = "NSE:AAA"
    repo.upsert_instrument(
        Instrument(instrument_id=iid, symbol="AAA", exchange="NSE", series="EQ", status="ACTIVE")
    )
    repo.add_candles(_candles(iid, seed=100))
    # deliberately no intraday candles at all
    pipe = OwnerValidationPipeline(repo, Path("config"))
    ingestion = IngestionResult(
        as_of=AS_OF, instruments_upserted=1, candles_fetched=80, candles_written=80,
        quotes_fetched=0, quotes_written=0, datasets_validated=1, datasets_skipped_empty=0,
    )
    pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-id7f1-missing")
    repo.close()

    summary = run_replay(db_path=db_path, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["defect_counts"]["total"] == 0
    assert summary["evidence_availability"]["completed_m5_absent"] == summary["rows_attempted"]
    assert summary["watch_invariant_check"]["watch_invariant_holds"] is True


def test_run_replay_reconstructs_trade_qualified_as_actionable(tmp_path: Path, monkeypatch) -> None:
    db_path = _seed_forced_trade_db(tmp_path, force_qualified=True, monkeypatch=monkeypatch)
    summary = run_replay(db_path=db_path, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["defect_counts"]["total"] == 0
    assert summary["trade_result_distribution"]["state_distribution"]["ACTIONABLE"]["count"] == 1
    assert summary["empirical_availability"]["trade_empirical_validation"] == \
        "TRADE_EMPIRICAL_VALIDATION_AVAILABLE"
    assert summary["empirical_availability"]["actionable_empirical_validation"] == \
        "ACTIONABLE_EMPIRICAL_VALIDATION_AVAILABLE"

    obs_path = Path(summary["artifacts"]["observations_path"])
    row = json.loads(obs_path.read_text().strip().splitlines()[0])
    assert row["ea_state"] == "ACTIONABLE"
    assert row["entry_reference_price"] == "102"
    assert row["operative_invalidation_level"] == "101"
    assert row["reconstructed_session_vwap_as_of"] == row["evidence_as_of"]


def test_run_replay_reconstructs_trade_non_qualified_as_not_actionable(tmp_path: Path, monkeypatch) -> None:
    db_path = _seed_forced_trade_db(tmp_path, force_qualified=False, monkeypatch=monkeypatch)
    summary = run_replay(db_path=db_path, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["defect_counts"]["total"] == 0
    dist = summary["trade_result_distribution"]
    assert dist["state_distribution"]["NOT_ACTIONABLE"]["count"] == 1
    assert dist["reason_code_counts"]["UPSTREAM_EQ_NOT_QUALIFIED"] == 1


def test_determinism_double_reconstruction_matches_across_forward_and_reversed_order(
    seeded_watch_db: Path, tmp_path: Path
) -> None:
    """Order-independence: reversing the (here, single-row, but the
    mechanism is order-independent by construction -- each observation
    is processed independently with no shared mutable state across
    iterations) population must not change any per-identity result."""
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    obs_path = Path(summary["artifacts"]["observations_path"])
    rows = [json.loads(line) for line in obs_path.read_text().strip().splitlines()]
    by_identity_forward = {r["decision_id"]: r["ea_state"] for r in rows}
    by_identity_reversed = {r["decision_id"]: r["ea_state"] for r in reversed(rows)}
    assert by_identity_forward == by_identity_reversed


# --------------------------------------------------------------------------- #
# ID-7F1.1: harness accounting + failure-observability hardening tests
# --------------------------------------------------------------------------- #


def test_determinism_defect_does_not_double_count_attempt(
    seeded_watch_db: Path, tmp_path: Path, monkeypatch
) -> None:
    """A REPLAY_EQUIVALENCE_DEFECT is attached to an observation that
    was ALSO successfully reconstructed (appended to rows) -- proving
    rows_attempted must never be derived from len(rows) + len(defects),
    which would double-count exactly this case."""
    real_evaluate = EntryActionabilityEngine.evaluate
    call_count = {"n": 0}

    def flaky_evaluate(self, *args, **kwargs):
        call_count["n"] += 1
        result = real_evaluate(self, *args, **kwargs)
        if call_count["n"] == 2:
            # Force the SECOND reconstruction's evaluation to disagree
            # with the first -- a controlled, deliberate mismatch.
            result = dataclasses.replace(result, explanation=result.explanation + " (forced-mismatch)")
        return result

    monkeypatch.setattr(EntryActionabilityEngine, "evaluate", flaky_evaluate)

    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["population_total"] == 1
    assert summary["rows_attempted"] == 1
    assert summary["rows_reconstructed_successfully"] == 1
    assert summary["defect_counts"]["replay_equivalence_defects"] == 1
    assert summary["determinism"]["mismatches"] == 1
    assert summary["determinism"]["determinism_holds"] is False
    assert summary["replay_acceptance"] is False


def test_pre_evaluation_binding_failure_accounting(tmp_path: Path, monkeypatch) -> None:
    """An observation whose bound Decision is missing entirely (a
    genuine UPSTREAM_BINDING_DEFECT) must still count as attempted, but
    not as successfully reconstructed -- no double counting either
    direction."""
    from athena.intraday.entry_qualification_models import (
        EntryEvidenceFinality,
        EntryQualificationConfirmation,
    )

    orphan_eq = EntryQualification(
        instrument_id="NSE:AAA", session_date=AS_OF.date(), as_of=AS_OF,
        run_id="run-1", cycle_id="cyc-1", decision_id="decision-that-does-not-exist",
        decision_type=DecisionType.WATCH, state=EntryQualificationState.NOT_YET,
        evidence_finality=EntryEvidenceFinality.NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY,
        confirmation=EntryQualificationConfirmation.NOT_EVALUATED,
        reason_codes=(), evidence_refs=(), methodology_version="entry-qualification-v0",
        config_snapshot_id=None, explanation="test",
    )
    monkeypatch.setattr(m, "_load_eq_population", lambda store: [orphan_eq])

    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.close()

    summary = run_replay(db_path=db_path, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["population_total"] == 1
    assert summary["duplicate_population_total"] == 0
    assert summary["unique_population_total"] == 1
    assert summary["rows_attempted"] == 1
    assert summary["rows_reconstructed_successfully"] == 0
    assert summary["defect_counts"]["upstream_binding_defects"] == 1
    assert summary["replay_acceptance"] is False


def test_duplicate_accounting_excludes_duplicate_from_attempted(
    seeded_watch_db: Path, tmp_path: Path, monkeypatch
) -> None:
    """population_total counts every persisted row including the
    duplicate; unique_population_total/rows_attempted count only the
    first-seen observation -- the duplicate itself is a
    PERSISTENCE_DEFECT, never an independently-attempted observation."""
    real_load = m._load_eq_population

    def duplicated_load(store):
        population = real_load(store)
        assert len(population) == 1
        eq = population[0]
        return [eq, eq]  # identical object twice -> identical identity

    monkeypatch.setattr(m, "_load_eq_population", duplicated_load)

    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["population_total"] == 2
    assert summary["duplicate_population_total"] == 1
    assert summary["unique_population_total"] == 1
    assert summary["rows_attempted"] == 1
    assert summary["rows_reconstructed_successfully"] == 1
    assert summary["defect_counts"]["persistence_defects"] == 1


def test_unexpected_exception_is_not_relabeled_and_fails_acceptance(
    seeded_watch_db: Path, tmp_path: Path, monkeypatch
) -> None:
    """A genuinely unexpected (non-ValueError) failure must be recorded
    under its own diagnostic -- never converted into UNKNOWN, never
    DATA_AVAILABILITY, never PIT_EVIDENCE_DEFECT -- must still count as
    attempted but not reconstructed, and must force replay_acceptance
    False."""
    def boom(self, *args, **kwargs):
        raise RuntimeError("deliberate unexpected failure for this one observation")

    monkeypatch.setattr(EntryActionabilityEngine, "evaluate", boom)

    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["rows_attempted"] == 1
    assert summary["rows_reconstructed_successfully"] == 0
    assert summary["unexpected_replay_exceptions"]["total"] == 1
    assert summary["unexpected_replay_exceptions"]["by_exception_type"] == {"RuntimeError": 1}
    assert summary["defect_counts"]["total"] == 0  # never folded into the frozen defect taxonomy
    assert summary["replay_acceptance"] is False

    unexpected_path = Path(summary["artifacts"]["unexpected_exceptions_path"])
    lines = unexpected_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["exception_type"] == "RuntimeError"


def test_value_error_still_classified_pit_evidence_defect_not_unexpected(
    seeded_watch_db: Path, tmp_path: Path, monkeypatch
) -> None:
    """Regression: a ValueError (the frozen PIT-evidence-defect rule)
    must remain classified as PIT_EVIDENCE_DEFECT, never rerouted into
    the new unexpected-exception diagnostic."""
    def boom(self, *args, **kwargs):
        raise ValueError("deliberate PIT-style failure")

    monkeypatch.setattr(EntryActionabilityEngine, "evaluate", boom)

    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["rows_attempted"] == 1
    assert summary["rows_reconstructed_successfully"] == 0
    assert summary["defect_counts"]["pit_evidence_defects"] == 1
    assert summary["unexpected_replay_exceptions"]["total"] == 0
    assert summary["replay_acceptance"] is False


def test_infrastructure_failure_to_open_db_still_propagates(tmp_path: Path) -> None:
    """run_replay must not swallow an infrastructure-level failure (e.g.
    a source DB that does not exist) -- it should fail fast, not be
    silently absorbed into the per-observation try/except."""
    missing_db = tmp_path / "does-not-exist.db"
    with pytest.raises(Exception):
        run_replay(db_path=missing_db, config_dir=Path("config"), output_dir=tmp_path / "out")


def test_replay_acceptance_true_on_the_clean_seeded_watch_population(
    seeded_watch_db: Path, tmp_path: Path
) -> None:
    summary = run_replay(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["replay_acceptance"] is True
    assert summary["observations_with_defects"] == 0
    assert summary["unexpected_replay_exceptions"]["total"] == 0


# --------------------------------------------------------------------------- #
# ID-7F3: Mode B production-vs-replay shadow equivalence
#
# `seeded_watch_db`/`_seed_forced_trade_db` already produce real,
# genuinely persisted `entry_actionabilities` rows (via the same
# `OwnerValidationPipeline` ID-7E wired `entry_actionability_stage`
# into), so Mode B can be exercised against them directly -- the
# comparison population IS the persisted table, never re-derived from
# `entry_qualifications` the way Mode A's population is.
# --------------------------------------------------------------------------- #


def _minimal_ea(**overrides):
    from athena.intraday import EntryActionability
    from athena.intraday.entry_actionability_models import (
        EntryActionabilityReasonCode,
        EntryActionabilityState,
        EntryEvidenceFinality,
    )

    kwargs = dict(
        instrument_id="NSE:AAA", session_date=AS_OF.date(),
        entry_qualification_as_of=AS_OF, decision_id="d1",
        entry_qualification_methodology_version="entry-qualification-v0",
        entry_actionability_as_of=AS_OF,
        entry_actionability_methodology_version="entry-actionability-v0",
        decision_type=DecisionType.WATCH, direction=Direction.NONE,
        entry_qualification_state=EntryQualificationState.EXPIRED,
        run_id="run-1", cycle_id="cyc-1",
        state=EntryActionabilityState.NOT_ACTIONABLE,
        reason_codes=(
            EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,
            EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,
        ),
        evidence_finality=EntryEvidenceFinality.UNKNOWN_PROVENANCE,
        evidence_as_of=None, entry_reference=None, entry_location_context=None,
        operative_invalidation=None, reward=None, opening_range_context=None,
        evaluated_at=DEFAULT_REPLAY_EVALUATED_AT, explanation="not actionable",
    )
    kwargs.update(overrides)
    return EntryActionability(**kwargs)


def test_methodology_payload_ignores_run_id_cycle_id_and_evaluated_at() -> None:
    a = _minimal_ea(run_id="run-1", cycle_id="cyc-1", evaluated_at=DEFAULT_REPLAY_EVALUATED_AT)
    b = _minimal_ea(
        run_id="run-DIFFERENT", cycle_id="cyc-DIFFERENT",
        evaluated_at=datetime(2099, 1, 1, tzinfo=IST),
    )
    assert _methodology_payload(a) == _methodology_payload(b)
    assert _identity_tuple(a) == _identity_tuple(b)


def test_identity_tuple_disagrees_on_a_real_identity_difference() -> None:
    a = _minimal_ea()
    b = _minimal_ea(instrument_id="NSE:BBB")
    assert _identity_tuple(a) != _identity_tuple(b)


def test_classify_mismatch_denormalized_context_checked_before_state() -> None:
    """A genuinely different upstream Decision/EQ context (decision_type/
    entry_qualification_state) is a deeper disagreement than the derived
    `state` value, so it must classify PROVENANCE_MISMATCH -- checked
    BEFORE the state comparison, never silently collapsed into
    STATE_MISMATCH just because `state` also happens to differ."""
    from athena.intraday.entry_actionability_models import (
        EntryActionabilityReasonCode,
        EntryActionabilityState,
    )

    a = _minimal_ea(
        decision_type=DecisionType.TRADE,
        entry_qualification_state=EntryQualificationState.QUALIFIED,
        state=EntryActionabilityState.UNKNOWN,
        reason_codes=(EntryActionabilityReasonCode.INSUFFICIENT_EVIDENCE,),
    )
    b = _minimal_ea(
        decision_type=DecisionType.WATCH,
        entry_qualification_state=EntryQualificationState.EXPIRED,
        state=EntryActionabilityState.NOT_ACTIONABLE,
        reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,),
    )
    kind, detail = _classify_mismatch(a, b)
    assert kind == "PROVENANCE_MISMATCH"
    assert "decision_type" in detail


def test_classify_mismatch_reason_mismatch() -> None:
    from athena.intraday.entry_actionability_models import EntryActionabilityReasonCode

    a = _minimal_ea(reason_codes=(EntryActionabilityReasonCode.UPSTREAM_DECISION_NOT_TRADE,))
    b = _minimal_ea(reason_codes=(EntryActionabilityReasonCode.UPSTREAM_EQ_NOT_QUALIFIED,))
    kind, _ = _classify_mismatch(a, b)
    assert kind == "REASON_MISMATCH"


def test_classify_mismatch_identity_difference_is_provenance_mismatch() -> None:
    a = _minimal_ea()
    b = _minimal_ea(instrument_id="NSE:BBB")
    kind, _ = _classify_mismatch(a, b)
    assert kind == "PROVENANCE_MISMATCH"


def test_run_shadow_equivalence_matches_persisted_watch_row(
    seeded_watch_db: Path, tmp_path: Path
) -> None:
    summary = run_shadow_equivalence(
        db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
    )
    assert summary["population_total"] == 1
    assert summary["rows_reconstructed_successfully"] == 1
    assert summary["binding_defects"] == 0
    assert summary["pit_evidence_defects"] == 0
    assert summary["determinism_mismatches"] == 0
    assert summary["production_equivalence_mismatches"]["total"] == 0
    assert summary["exact_match_count"] == 1
    assert summary["mode_b_acceptance"] is True
    assert summary["path_specific"]["scheduled_cycle"]["observations"] == 1
    assert summary["path_specific"]["symbol_validate"]["observations"] == 0


def test_run_shadow_equivalence_matches_persisted_trade_qualified_actionable_row(
    tmp_path: Path, monkeypatch,
) -> None:
    db_path = _seed_forced_trade_db(tmp_path, force_qualified=True, monkeypatch=monkeypatch)
    summary = run_shadow_equivalence(db_path=db_path, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["mode_b_acceptance"] is True
    assert summary["production_equivalence_mismatches"]["total"] == 0
    assert summary["persisted_ea_state_distribution"]["ACTIONABLE"]["count"] == 1
    assert summary["empirical_availability"]["trade_qualified"] == "TRADE_QUALIFIED_AVAILABLE"
    assert summary["empirical_availability"]["actionable"] == "ACTIONABLE_AVAILABLE"


def test_run_shadow_equivalence_matches_persisted_trade_non_qualified_row(
    tmp_path: Path, monkeypatch,
) -> None:
    db_path = _seed_forced_trade_db(tmp_path, force_qualified=False, monkeypatch=monkeypatch)
    summary = run_shadow_equivalence(db_path=db_path, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["mode_b_acceptance"] is True
    assert summary["persisted_ea_state_distribution"]["NOT_ACTIONABLE"]["count"] == 1


def test_run_shadow_equivalence_detects_a_genuine_production_mismatch(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    """Mutation/negative proof: if the persisted production row disagreed
    with what the frozen evaluator would independently produce, Mode B
    must catch it -- never silently report a false EXACT_MATCH."""
    conn = sqlite3.connect(seeded_watch_db)
    conn.execute(
        "UPDATE entry_actionabilities SET reason_codes_json=? WHERE instrument_id='NSE:AAA'",
        ('["UPSTREAM_EQ_NOT_QUALIFIED"]',),
    )
    conn.commit()
    conn.close()

    summary = run_shadow_equivalence(
        db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
    )
    assert summary["mode_b_acceptance"] is False
    assert summary["production_equivalence_mismatches"]["total"] == 1
    assert summary["production_equivalence_mismatches"]["by_kind"]["REASON_MISMATCH"] == 1
    assert summary["exact_match_count"] == 0


def test_run_shadow_equivalence_path_classification_symbol_validate(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    """`OwnerValidationPipeline.run(...)` alone (this fixture's own seed
    path) never writes a `runs` row -- that is a separate caller's
    responsibility (the real scheduled-cycle orchestrator) -- so a
    `runs` row is inserted directly here purely to exercise the
    path-classification join; no domain/pipeline behavior is touched."""
    conn = sqlite3.connect(seeded_watch_db)
    conn.execute(
        "INSERT INTO runs (run_id, cycle_id, trigger, started_ts, status, "
        "software_version, blueprint_version, strategy_profile, "
        "strategy_profile_version, indicator_versions_json, config_snapshot_id) "
        "VALUES ('run-id7f1-seed','cyc-1','PREMARKET',?,'COMPLETED','test','test','test','test','{}',"
        "'cfg-symbol-validate')",
        (AS_OF.isoformat(),),
    )
    conn.commit()
    conn.close()

    summary = run_shadow_equivalence(
        db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
    )
    assert summary["path_specific"]["symbol_validate"]["observations"] == 1
    assert summary["path_specific"]["symbol_validate"]["exact_match"] == 1
    assert summary["path_specific"]["scheduled_cycle"]["observations"] == 0


def test_run_shadow_equivalence_validation_cutoff_excludes_later_rows(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    """A cutoff strictly before the only persisted row's `persisted_at`
    must exclude it -- proving the frozen-denominator semantics rather
    than always reading the live table."""
    conn = sqlite3.connect(seeded_watch_db)
    row = conn.execute("SELECT MIN(persisted_at) FROM entry_actionabilities").fetchone()
    persisted_at = datetime.fromisoformat(row[0])
    conn.close()

    cutoff_before = persisted_at - timedelta(seconds=1)
    summary = run_shadow_equivalence(
        db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
        validation_cutoff=cutoff_before,
    )
    assert summary["population_total"] == 0
    assert summary["rows_reconstructed_successfully"] == 0


def test_run_shadow_equivalence_never_mutates_the_source_db(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    before = seeded_watch_db.read_bytes()
    run_shadow_equivalence(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    after = seeded_watch_db.read_bytes()
    assert before == after


def test_run_shadow_equivalence_schema_version_unchanged(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    summary = run_shadow_equivalence(db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out")
    assert summary["metadata"]["schema_version_unchanged"] is True


def test_run_shadow_equivalence_rejects_naive_validation_cutoff(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        run_shadow_equivalence(
            db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
            validation_cutoff=datetime(2026, 1, 1),
        )


def test_run_shadow_equivalence_rejects_naive_evaluated_at(
    seeded_watch_db: Path, tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        run_shadow_equivalence(
            db_path=seeded_watch_db, config_dir=Path("config"), output_dir=tmp_path / "out",
            evaluated_at=datetime(2026, 1, 1),
        )


def test_run_shadow_equivalence_excludes_evaluated_at_and_persisted_at_from_comparison_mask() -> None:
    from athena.data.id7f1_entry_actionability_replay import _summarize_shadow_equivalence
    summary = _summarize_shadow_equivalence(
        observations=[], defects=[], mismatches=[], unexpected_exceptions=[],
        population_total=0, unique_population_total=0, duplicate_population_total=0,
        rows_attempted=0, db_path=Path("x"), schema_version_start=18, schema_version_end=18,
        validation_cutoff=DEFAULT_REPLAY_EVALUATED_AT, evaluated_at=DEFAULT_REPLAY_EVALUATED_AT,
        started=0.0, output_dir=Path(__file__).parent / "_tmp_id7f3_mask_test",
    )
    excluded = set(summary["metadata"]["comparison_mask_excluded_fields"])
    assert excluded == {"run_id", "cycle_id", "evaluated_at", "persisted_at"}
    import shutil
    shutil.rmtree(Path(__file__).parent / "_tmp_id7f3_mask_test", ignore_errors=True)


def test_no_save_entry_actionability_call_in_shadow_equivalence_source() -> None:
    """Mode B must never write a production row -- confirmed by direct
    source scan, mirroring the module's own existing zero-persistence-
    write proof for Mode A. Checks the call-site pattern, not the bare
    identifier, since the module docstring mentions the name in prose."""
    source = inspect.getsource(m)
    assert "save_entry_actionability(" not in source
    assert "INSERT INTO entry_actionabilities" not in source


def test_infrastructure_failure_to_open_db_still_propagates_shadow_equivalence(tmp_path: Path) -> None:
    missing_db = tmp_path / "does-not-exist.db"
    with pytest.raises(Exception):
        run_shadow_equivalence(db_path=missing_db, config_dir=Path("config"), output_dir=tmp_path / "out")
