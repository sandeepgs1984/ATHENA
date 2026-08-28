"""EM-5's own SQLite store: isolated from db/athena.db, schema init,
scan-run/candidate/transition persistence round-trips."""

from __future__ import annotations

from athena.explosive_move.store.repository import EmrRepository
from athena.explosive_move.store.schema import EMR_SCHEMA_VERSION


def _repo(tmp_path):
    repo = EmrRepository(tmp_path / "emr.db")
    repo.initialize()
    return repo


def test_initialize_creates_schema_version_row(tmp_path):
    repo = _repo(tmp_path)
    conn = repo._connect()
    row = conn.execute("SELECT version FROM emr_schema_version").fetchone()
    assert row[0] == EMR_SCHEMA_VERSION


def test_initialize_is_idempotent(tmp_path):
    repo = _repo(tmp_path)
    repo.initialize()
    repo.initialize()  # must not raise or duplicate the version row
    conn = repo._connect()
    rows = conn.execute("SELECT version FROM emr_schema_version").fetchall()
    assert len(rows) == 1


def test_db_file_is_separate_from_athena_core(tmp_path):
    repo = EmrRepository(tmp_path / "emr.db")
    assert repo.path.endswith("emr.db")
    assert "athena.db" not in repo.path


def _scan_run(run_id="run-1", **overrides):
    base = {
        "run_id": run_id, "session_date": "2026-08-28", "checkpoint": "12:00",
        "frozen_model_version": "v1", "status": "RUNNING", "started_ts": "2026-08-28T12:00:00+05:30",
    }
    base.update(overrides)
    return base


def test_save_and_get_scan_run_round_trips(tmp_path):
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    loaded = repo.get_scan_run("run-1")
    assert loaded["session_date"] == "2026-08-28"
    assert loaded["checkpoint"] == "12:00"
    assert loaded["status"] == "RUNNING"


def test_save_scan_run_upserts_on_conflict(tmp_path):
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(status="RUNNING"))
    repo.save_scan_run(_scan_run(status="COMPLETE", finished_ts="2026-08-28T12:05:00+05:30"))
    loaded = repo.get_scan_run("run-1")
    assert loaded["status"] == "COMPLETE"
    assert loaded["finished_ts"] == "2026-08-28T12:05:00+05:30"


def test_get_scan_run_missing_returns_none(tmp_path):
    repo = _repo(tmp_path)
    assert repo.get_scan_run("missing") is None


def _candidate(**overrides):
    base = {
        "run_id": "run-1", "instrument_id": "NSE:INFY", "family": "TOUCH", "threshold_percent": 10,
        "checkpoint": "12:00", "session_date": "2026-08-28", "rank": 3, "raw_logit": -1.2,
        "raw_logistic_estimate": 0.05, "probability_language": "calibrated_probability",
        "em4b_model_version": "em4b-v1", "em4d_calibration_version": "em4d-v1",
        "evidence_timestamp": "2026-08-28T12:00:02+05:30", "evidence_completeness_known": 22,
        "evidence_completeness_total": 22, "freshness": "FRESH", "feasibility": "FEASIBLE",
        "state": "WATCH", "state_reason": "rank <= 20",
    }
    base.update(overrides)
    return base


def test_save_and_list_candidates_round_trips(tmp_path):
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(), _candidate(instrument_id="NSE:TCS", rank=1)])
    rows = repo.list_candidates(run_id="run-1")
    assert len(rows) == 2
    assert {r["instrument_id"] for r in rows} == {"NSE:INFY", "NSE:TCS"}
    assert rows[0]["rank"] == 1  # ordered by rank


def test_list_candidates_empty_run_returns_empty_list(tmp_path):
    repo = _repo(tmp_path)
    assert repo.list_candidates(run_id="no-such-run") == []


def test_list_candidates_for_symbol_returns_checkpoint_history_in_order(tmp_path):
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-1", checkpoint="11:00"))
    repo.save_scan_run(_scan_run(run_id="run-2", checkpoint="12:00"))
    repo.save_candidates([_candidate(run_id="run-1", checkpoint="11:00", rank=8)])
    repo.save_candidates([_candidate(run_id="run-2", checkpoint="12:00", rank=3)])
    history = repo.list_candidates_for_symbol(
        instrument_id="NSE:INFY", family="TOUCH", threshold_percent=10, session_date="2026-08-28",
    )
    assert [h["checkpoint"] for h in history] == ["11:00", "12:00"]
    assert [h["rank"] for h in history] == [8, 3]


def test_list_candidates_for_symbol_scoped_to_family_and_threshold(tmp_path):
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(family="TOUCH", threshold_percent=10),
        _candidate(family="CLOSE", threshold_percent=10),
    ])
    history = repo.list_candidates_for_symbol(
        instrument_id="NSE:INFY", family="TOUCH", threshold_percent=10, session_date="2026-08-28",
    )
    assert len(history) == 1
    assert history[0]["state"] == "WATCH"


def test_list_candidates_for_symbol_empty_when_no_history(tmp_path):
    repo = _repo(tmp_path)
    assert repo.list_candidates_for_symbol(
        instrument_id="NSE:INFY", family="TOUCH", threshold_percent=10, session_date="2026-08-28",
    ) == []


def _transition(**overrides):
    base = {
        "run_id": "run-1", "instrument_id": "NSE:INFY", "family": "TOUCH", "threshold_percent": 10,
        "checkpoint": "12:00", "session_date": "2026-08-28", "sequence_number": 1,
        "from_state": "INACTIVE", "to_state": "WATCH", "reason": "rank <= 20",
    }
    base.update(overrides)
    return base


def test_save_and_list_transitions_round_trips(tmp_path):
    repo = _repo(tmp_path)
    repo.save_transitions([
        _transition(sequence_number=1, from_state="INACTIVE", to_state="WATCH"),
        _transition(sequence_number=2, from_state="WATCH", to_state="CONFIRMED"),
    ])
    rows = repo.list_transitions(
        instrument_id="NSE:INFY", family="TOUCH", threshold_percent=10, session_date="2026-08-28",
    )
    assert [r["to_state"] for r in rows] == ["WATCH", "CONFIRMED"]
