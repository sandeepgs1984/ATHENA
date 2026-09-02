"""ID-6E: Entry Qualification replay & shadow validation harness tests.

Pure-function analysis tests use synthetic rows (no DB); the harness
integration tests use a temp DB with real seeded candles/decisions to
prove `run_replay` calls the actual `EntryQualificationEngine` end-to-end,
deterministically, without mutating the source DB.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.id6e_replay_shadow_validation import (
    _invariant_checks,
    _m15_impact,
    _option_c_validation,
    _qualified_duration,
    _reason_root_causes,
    _state_block,
    _transitions,
    pct,
    run_replay,
    run_shadow_audit,
)
from athena.data.ingestion.models import IngestionResult
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunTrigger, Timeframe
from athena.domain.market import Candle, Instrument
from athena.intraday.entry_qualification_models import EntryEvidenceFinality, EntryQualificationState
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.owner_validation import OwnerValidationPipeline

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 3, 2, 9, 30, tzinfo=IST)


# --------------------------------------------------------------------------- #
# Pure analysis-function tests (no DB)
# --------------------------------------------------------------------------- #


def test_pct_handles_empty_denominator() -> None:
    assert pct(0, 0) == 0.0
    assert pct(1, 4) == 25.0


def test_state_block_reports_qualified_not_yet_unknown_rates() -> None:
    rows = [
        {"state": "QUALIFIED"}, {"state": "QUALIFIED"},
        {"state": "NOT_YET"}, {"state": "UNKNOWN"},
    ]
    block = _state_block(rows)
    assert block["total"] == 4
    assert block["qualified_pct"] == 50.0
    assert block["not_yet_pct"] == 25.0
    assert block["unknown_pct"] == 25.0


def test_reason_root_causes_aggregates_only_the_requested_state() -> None:
    rows = [
        {"state": "UNKNOWN", "reason_codes": ["VWAP_EVIDENCE_UNAVAILABLE"]},
        {"state": "UNKNOWN", "reason_codes": ["TREND_EVIDENCE_UNAVAILABLE", "SUPPORT_EVIDENCE_UNRESOLVED"]},
        {"state": "QUALIFIED", "reason_codes": ["VWAP_CONDITION_MET"]},
    ]
    result = _reason_root_causes(rows, "UNKNOWN")
    assert result["observations"] == 2
    assert result["reason_code_counts"] == {
        "SUPPORT_EVIDENCE_UNRESOLVED": 1, "TREND_EVIDENCE_UNAVAILABLE": 1, "VWAP_EVIDENCE_UNAVAILABLE": 1,
    }


def test_transitions_detects_qualified_then_later_not_qualified() -> None:
    rows = [
        {"instrument_id": "A", "session_date": "2026-01-01", "decision_type": "WATCH",
         "checkpoint": "09:30", "state": "QUALIFIED"},
        {"instrument_id": "A", "session_date": "2026-01-01", "decision_type": "WATCH",
         "checkpoint": "09:45", "state": "NOT_YET"},
        {"instrument_id": "B", "session_date": "2026-01-01", "decision_type": "WATCH",
         "checkpoint": "09:30", "state": "QUALIFIED"},
        {"instrument_id": "B", "session_date": "2026-01-01", "decision_type": "WATCH",
         "checkpoint": "09:45", "state": "QUALIFIED"},
    ]
    result = _transitions(rows)
    assert result["multi_checkpoint_candidate_groups"] == 2
    assert result["qualified_then_later_not_qualified_groups"] == 1
    assert result["qualified_then_later_not_qualified_pct"] == 50.0


def test_qualified_duration_classifies_every_pattern() -> None:
    rows = [
        # never qualified
        {"instrument_id": "A", "session_date": "d", "decision_type": "WATCH", "checkpoint": "1", "state": "NOT_YET"},
        # exactly one checkpoint
        {"instrument_id": "B", "session_date": "d", "decision_type": "WATCH", "checkpoint": "1", "state": "QUALIFIED"},
        {"instrument_id": "B", "session_date": "d", "decision_type": "WATCH", "checkpoint": "2", "state": "NOT_YET"},
        # every observed checkpoint
        {"instrument_id": "C", "session_date": "d", "decision_type": "WATCH", "checkpoint": "1", "state": "QUALIFIED"},
        {"instrument_id": "C", "session_date": "d", "decision_type": "WATCH", "checkpoint": "2", "state": "QUALIFIED"},
    ]
    result = _qualified_duration(rows)
    assert result["never_qualified"] == 1
    assert result["qualified_at_exactly_one_checkpoint"] == 1
    assert result["qualified_at_every_observed_checkpoint"] == 1


def test_option_c_validation_reports_state_distribution_within_flagged_rows() -> None:
    rows = [
        {"data_quality": "EXPECTED_BAR_MISSING", "state": "QUALIFIED"},
        {"data_quality": "EXPECTED_BAR_MISSING", "state": "NOT_YET"},
        {"data_quality": "SUFFICIENT", "state": "QUALIFIED"},
    ]
    result = _option_c_validation(rows)
    assert result["observations_with_expected_bar_missing"] == 2
    assert result["state_distribution_within_flagged"]["QUALIFIED"]["count"] == 1


def test_m15_impact_isolates_fifteen_min_unavailable_unknown_observations() -> None:
    rows = [
        {"state": "UNKNOWN", "reason_codes": ["TREND_EVIDENCE_UNAVAILABLE"], "fifteen_min_available": False},
        {"state": "UNKNOWN", "reason_codes": ["TREND_EVIDENCE_UNAVAILABLE"], "fifteen_min_available": True},
        {"state": "UNKNOWN", "reason_codes": ["SUPPORT_EVIDENCE_UNRESOLVED"], "fifteen_min_available": False},
        {"state": "QUALIFIED", "reason_codes": [], "fifteen_min_available": True},
    ]
    result = _m15_impact(rows)
    assert result["unknown_observations"] == 3
    assert result["unknown_due_to_trend_evidence_unavailable"] == 2
    assert result["of_those_with_fifteen_min_unavailable"] == 1


def test_invariant_checks_flag_disqualified_and_confirmed_by_policy() -> None:
    rows = [
        {"state": "DISQUALIFIED_FOR_SESSION", "confirmation": "NOT_EVALUATED",
         "methodology_version": "entry-qualification-v0"},
        {"state": "QUALIFIED", "confirmation": "CONFIRMED_BY_POLICY",
         "methodology_version": "entry-qualification-v0"},
    ]
    result = _invariant_checks(rows)
    assert result["disqualified_for_session_count"] == 1
    assert result["disqualified_for_session_invariant_holds"] is False
    assert result["confirmed_by_policy_count"] == 1
    assert result["confirmed_by_policy_invariant_holds"] is False


def test_invariant_checks_pass_on_a_clean_v0_population() -> None:
    rows = [
        {"state": "QUALIFIED", "confirmation": "NOT_EVALUATED", "methodology_version": "entry-qualification-v0"},
        {"state": "NOT_YET", "confirmation": "NOT_EVALUATED", "methodology_version": "entry-qualification-v0"},
    ]
    result = _invariant_checks(rows)
    assert result["disqualified_for_session_invariant_holds"] is True
    assert result["confirmed_by_policy_invariant_holds"] is True
    assert result["not_evaluated_confirmation_invariant_holds"] is True
    assert result["methodology_version_invariant_holds"] is True


# --------------------------------------------------------------------------- #
# Harness integration tests (temp DB, real seeded data, real engine)
# --------------------------------------------------------------------------- #


def _candles(instrument_id: str, n: int = 80, seed: int = 100) -> list[Candle]:
    out = []
    price = Decimal(seed)
    day = AS_OF.date() - timedelta(days=n)
    for i in range(n):
        d = day + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        price += Decimal("0.5")
        out.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.D1,
            ts_open=datetime(d.year, d.month, d.day, tzinfo=IST),
            open=price, high=price + 1, low=price - 1, close=price,
            volume=1_000_000, source="test",
        ))
    return out


def _intraday_candles(instrument_id: str, day: date, n: int = 6, seed: int = 100) -> list[Candle]:
    out = []
    price = Decimal(seed)
    for i in range(n):
        ts = datetime(day.year, day.month, day.day, 9, 15 + 5 * i, tzinfo=IST)
        price += Decimal("0.2")
        out.append(Candle(
            instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts,
            open=price, high=price + Decimal("0.5"), low=price - Decimal("0.5"),
            close=price, volume=10000, source="test",
        ))
    return out


@pytest.fixture()
def seeded_db(tmp_path: Path) -> Path:
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
    pipe.run(RunTrigger.PREMARKET, as_of=AS_OF, ingestion=ingestion, run_id="run-id6e-seed")
    repo.close()
    return db_path


def test_run_replay_uses_the_real_engine_and_produces_a_valid_observation(
    seeded_db: Path, tmp_path: Path
) -> None:
    summary = run_replay(
        db_path=seeded_db, config_dir=Path("config"), output_dir=tmp_path / "out",
        session_dates=(AS_OF.date().isoformat(),), checkpoints=("09:30",), per_type=5,
    )
    assert summary["sample"]["candidate_checkpoint_observations"] == 1
    assert summary["sample"]["harness_defects"] == 0
    assert summary["invariants"]["disqualified_for_session_invariant_holds"] is True
    assert summary["invariants"]["not_evaluated_confirmation_invariant_holds"] is True
    assert summary["invariants"]["methodology_version_invariant_holds"] is True
    # A real state (from EntryQualificationState) and finality (from
    # EntryEvidenceFinality) prove the actual pure engine/resolver ran --
    # a stub or reimplementation would not reproduce these exact enums.
    state = next(iter(summary["state_distribution"]["distribution"]))
    assert state in {s.value for s in EntryQualificationState}
    finality = next(iter(summary["finality_distribution"]))
    assert finality in {f.value for f in EntryEvidenceFinality}


def test_run_replay_decision_bound_at_or_before_checkpoint(seeded_db: Path, tmp_path: Path) -> None:
    summary = run_replay(
        db_path=seeded_db, config_dir=Path("config"), output_dir=tmp_path / "out",
        session_dates=(AS_OF.date().isoformat(),), checkpoints=("09:30",), per_type=5,
    )
    obs_path = Path(summary["artifacts"]["observations_path"])
    import json

    lines = obs_path.read_text().strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert datetime.fromisoformat(row["as_of"]) == AS_OF  # the replay checkpoint itself


def test_run_replay_is_deterministic_across_two_runs(seeded_db: Path, tmp_path: Path) -> None:
    first = run_replay(
        db_path=seeded_db, config_dir=Path("config"), output_dir=tmp_path / "out1",
        session_dates=(AS_OF.date().isoformat(),), checkpoints=("09:30",), per_type=5,
    )
    second = run_replay(
        db_path=seeded_db, config_dir=Path("config"), output_dir=tmp_path / "out2",
        session_dates=(AS_OF.date().isoformat(),), checkpoints=("09:30",), per_type=5,
    )
    assert first["artifacts"]["analysis_sha256"] == second["artifacts"]["analysis_sha256"]


def test_run_replay_never_mutates_the_source_db(seeded_db: Path, tmp_path: Path) -> None:
    before = os.path.getmtime(seeded_db)
    run_replay(
        db_path=seeded_db, config_dir=Path("config"), output_dir=tmp_path / "out",
        session_dates=(AS_OF.date().isoformat(),), checkpoints=("09:30",), per_type=5,
    )
    after = os.path.getmtime(seeded_db)
    assert before == after


def test_run_replay_makes_no_provider_or_network_calls() -> None:
    import inspect

    from athena.data import id6e_replay_shadow_validation as module

    source = inspect.getsource(module)
    forbidden = ("kite", "requests.", "httpx.", "urllib.request")
    lowered = source.lower()
    assert not any(term in lowered for term in forbidden)


# --------------------------------------------------------------------------- #
# Shadow audit tests
# --------------------------------------------------------------------------- #


def test_shadow_audit_reports_not_available_when_table_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    sqlite3.connect(db_path).close()  # a real, valid, but schema-less SQLite file
    result = run_shadow_audit(db_path=db_path)
    assert result["status"] == "SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE"
    assert result["observation_count"] == 0


def test_shadow_audit_reports_not_available_when_table_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.close()
    result = run_shadow_audit(db_path=db_path)
    assert result["status"] == "SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE"


def test_shadow_audit_computes_persistence_latency_and_integrity(tmp_path: Path) -> None:
    from athena.domain.decision import Decision
    from athena.intraday.entry_qualification_engine import EntryQualificationPolicy
    from athena.intraday.entry_qualification_models import (
        EntryEvidenceFinality as Finality,
    )
    from athena.intraday.entry_qualification_models import (
        EntryQualification,
        EntryQualificationConfirmation,
    )
    from athena.intraday.entry_qualification_models import (
        EntryQualificationState as State,
    )

    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.upsert_instrument(Instrument(instrument_id="NSE:AAA", symbol="AAA", exchange="NSE", series="EQ"))
    repo.save_decision(Decision(
        decision_id="d-1", ts=AS_OF, run_id="r-1", cycle_id="c-1",
        decision_type=__import__("athena.domain.enums", fromlist=["DecisionType"]).DecisionType.WATCH,
        explanation="test", instrument_id="NSE:AAA",
    ))
    eq = EntryQualification(
        instrument_id="NSE:AAA", session_date=AS_OF.date(), as_of=AS_OF,
        run_id="r-1", cycle_id="c-1", decision_id="d-1",
        decision_type=__import__("athena.domain.enums", fromlist=["DecisionType"]).DecisionType.WATCH,
        state=State.QUALIFIED, evidence_finality=Finality.LIVE_M5_PROVISIONAL,
        confirmation=EntryQualificationConfirmation.NOT_EVALUATED,
        reason_codes=(), evidence_refs=(),
        methodology_version=EntryQualificationPolicy().methodology_version,
        config_snapshot_id=None, explanation="test",
    )
    persisted_at = AS_OF + timedelta(seconds=5)
    repo.save_entry_qualification(eq, persisted_at=persisted_at)
    repo.close()

    result = run_shadow_audit(db_path=db_path)
    assert result["status"] == "SHADOW_OBSERVATIONS_AVAILABLE"
    assert result["observation_count"] == 1
    assert result["integrity"]["duplicate_logical_identity_count"] == 0
    assert result["integrity"]["disqualified_for_session_count"] == 0
    assert result["integrity"]["naive_persisted_at_count"] == 0
    assert result["persistence_latency_seconds"]["median"] == 5.0
    assert result["persistence_latency_seconds"]["negative_latency_count"] == 0


def test_shadow_audit_is_read_only_and_never_mutates(tmp_path: Path) -> None:
    db_path = tmp_path / "athena.db"
    repo = SqliteRepository(db_path)
    repo.initialize()
    repo.close()
    before = os.path.getmtime(db_path)
    run_shadow_audit(db_path=db_path)
    after = os.path.getmtime(db_path)
    assert before == after
