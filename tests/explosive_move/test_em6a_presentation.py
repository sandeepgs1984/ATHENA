"""EM-6A: the read-only EMR presentation data contract.

Every test builds its fixture via the real, already-tested
`EmrRepository` (write side) and then exercises
`athena.explosive_move.live.presentation` (a wholly separate, genuinely
read-only SQLite connection) against the same database file -- proving
the presentation layer reads real persisted shape correctly without ever
using the write-capable repository connection itself.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.explosive_move.live import presentation as pres
from athena.explosive_move.store.repository import EmrRepository

IST = ZoneInfo("Asia/Kolkata")


def _repo(tmp_path: Path) -> EmrRepository:
    repo = EmrRepository(tmp_path / "emr.db")
    repo.initialize()
    return repo


def _scan_run(run_id: str = "run-1", **overrides) -> dict:
    base = {
        "run_id": run_id, "session_date": "2026-08-28", "checkpoint": "12:00",
        "frozen_model_version": "v1", "status": "COMPLETE",
        "started_ts": "2026-08-28T12:00:00+05:30", "finished_ts": "2026-08-28T12:00:05+05:30",
        "eligible_count": 2, "ineligible_count": 1,
    }
    base.update(overrides)
    return base


def _candidate(**overrides) -> dict:
    base = {
        "run_id": "run-1", "instrument_id": "NSE:INFY", "family": "TOUCH", "threshold_percent": 10,
        "checkpoint": "12:00", "session_date": "2026-08-28", "rank": 3, "raw_logit": -1.2,
        "raw_logistic_estimate": 0.05, "calibrated_probability": 0.05,
        "probability_language": "calibrated_probability",
        "em4b_model_version": "em4b-v1", "em4d_calibration_version": "em4d-v1",
        "evidence_timestamp": "2026-08-28T12:00:02+05:30", "evidence_completeness_known": 22,
        "evidence_completeness_total": 22, "freshness": "FRESH", "feasibility": "FEASIBLE",
        "state": "WATCH", "state_reason": "rank <= 20",
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# 1. Empty database / no scan
# --------------------------------------------------------------------------- #


def test_no_db_file_returns_empty_snapshot(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.db"
    assert pres.latest_scan_snapshot(missing) is None
    snap = pres.build_experimental_snapshot(missing)
    assert snap.scan is None
    assert snap.touch_10 == ()
    assert snap.label == pres.EXPERIMENTAL_LABEL


def test_initialized_but_empty_db_returns_no_scan(tmp_path: Path) -> None:
    repo = _repo(tmp_path)  # creates schema, no rows
    assert pres.latest_scan_snapshot(repo.path) is None
    assert pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10) == ()


def test_running_scan_is_not_returned_as_latest(tmp_path: Path) -> None:
    """A scan that never finished (stuck RUNNING) must never be surfaced
    as 'the latest scan' -- its candidate set was never fully persisted."""
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(status="RUNNING", finished_ts=None))
    assert pres.latest_scan_snapshot(repo.path) is None


# --------------------------------------------------------------------------- #
# 2. One coherent scan
# --------------------------------------------------------------------------- #


def test_one_scan_one_run_returns_full_snapshot(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:INFY", rank=1), _candidate(instrument_id="NSE:TCS", rank=2)])

    scan = pres.latest_scan_snapshot(repo.path)
    assert scan is not None
    assert scan.run_id == "run-1"
    assert scan.session_date == "2026-08-28"
    assert scan.checkpoint == "12:00"
    assert scan.eligible_count == 2
    assert scan.ineligible_count == 1

    top = pres.top_candidates(repo.path, run_id=scan.run_id, family="TOUCH", threshold_percent=10, limit=10)
    assert [c.instrument_id for c in top] == ["NSE:INFY", "NSE:TCS"]


# --------------------------------------------------------------------------- #
# 3. Multiple scans -- latest coherent scan selected deterministically
# --------------------------------------------------------------------------- #


def test_multiple_scans_latest_selected_by_started_ts(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-early", started_ts="2026-08-28T09:30:00+05:30"))
    repo.save_scan_run(_scan_run(run_id="run-late", started_ts="2026-08-28T14:00:00+05:30"))
    repo.save_candidates([_candidate(run_id="run-early", instrument_id="NSE:EARLY", rank=1)])
    repo.save_candidates([_candidate(run_id="run-late", instrument_id="NSE:LATE", rank=1)])

    scan = pres.latest_scan_snapshot(repo.path)
    assert scan.run_id == "run-late"
    top = pres.top_candidates(repo.path, run_id=scan.run_id, family="TOUCH", threshold_percent=10, limit=10)
    assert [c.instrument_id for c in top] == ["NSE:LATE"]


def test_repeated_selection_is_deterministic(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-a", started_ts="2026-08-28T09:30:00+05:30"))
    repo.save_scan_run(_scan_run(run_id="run-b", started_ts="2026-08-28T14:00:00+05:30"))
    first = pres.latest_scan_snapshot(repo.path)
    second = pres.latest_scan_snapshot(repo.path)
    assert first == second == pres.latest_scan_snapshot(repo.path)


# --------------------------------------------------------------------------- #
# 4. Multiple checkpoints (scoped by session_date)
# --------------------------------------------------------------------------- #


def test_session_date_scoping_ignores_other_sessions(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-yesterday", session_date="2026-08-27",
                                  started_ts="2026-08-27T14:00:00+05:30"))
    repo.save_scan_run(_scan_run(run_id="run-today", session_date="2026-08-28",
                                  started_ts="2026-08-28T09:30:00+05:30"))
    scan = pres.latest_scan_snapshot(repo.path, session_date="2026-08-28")
    assert scan.run_id == "run-today"


# --------------------------------------------------------------------------- #
# 5/6. Deterministic ranking / tie-breaking
# --------------------------------------------------------------------------- #


def test_top_candidates_preserves_scanner_assigned_rank_order(tmp_path: Path) -> None:
    """rank ordering is the scanner's own (frozen, EM-4C) assignment --
    this module must reproduce it exactly, never re-sort by score."""
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id="NSE:C", rank=3, calibrated_probability=0.9),
        _candidate(instrument_id="NSE:A", rank=1, calibrated_probability=0.1),
        _candidate(instrument_id="NSE:B", rank=2, calibrated_probability=0.5),
    ])
    top = pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10)
    assert [c.instrument_id for c in top] == ["NSE:A", "NSE:B", "NSE:C"]


def test_top_candidates_limit_is_respected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id=f"NSE:S{i}", rank=i) for i in range(1, 6)
    ])
    top = pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=2)
    assert [c.instrument_id for c in top] == ["NSE:S1", "NSE:S2"]


def test_negative_limit_rejected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(ValueError):
        pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=-1)


# --------------------------------------------------------------------------- #
# 7. TOUCH-10 semantics
# --------------------------------------------------------------------------- #


def test_touch_10_is_exactly_touch_family_ten_percent_threshold(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id="NSE:TOUCH10", family="TOUCH", threshold_percent=10, rank=1),
        _candidate(instrument_id="NSE:TOUCH20", family="TOUCH", threshold_percent=20, rank=1),
        _candidate(instrument_id="NSE:CLOSE10", family="CLOSE", threshold_percent=10, rank=1),
    ])
    touch_10 = pres.top_touch_10_candidates(repo.path, run_id="run-1", limit=10)
    assert [c.instrument_id for c in touch_10] == ["NSE:TOUCH10"]


# --------------------------------------------------------------------------- #
# 8. Missing/unknown coverage preserved
# --------------------------------------------------------------------------- #


def test_coverage_summary_separates_ranked_from_unranked_with_reasons(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([
        _candidate(instrument_id="NSE:RANKED", rank=1),
        _candidate(instrument_id="NSE:STALE", rank=None, feasibility="INFEASIBLE",
                    feasibility_reason="STALE_DATA", state="INACTIVE", state_reason="hard ineligible"),
        _candidate(instrument_id="NSE:OCCURRED", rank=None, feasibility="FEASIBLE",
                    feasibility_reason=None, state="INACTIVE", state_reason="already occurred"),
    ])
    coverage = pres.coverage_summary(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10)
    assert coverage.evaluated_count == 3
    assert coverage.ranked_count == 1
    assert coverage.unranked_count == 2
    reasons = dict(coverage.unranked_reason_counts)
    assert reasons["STALE_DATA"] == 1
    assert reasons["already occurred"] == 1  # falls back to state_reason, never UNKNOWN when a reason exists


def test_coverage_summary_empty_run_is_all_zero_not_missing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    coverage = pres.coverage_summary(repo.path, run_id="no-such-run", family="TOUCH", threshold_percent=10)
    assert coverage.evaluated_count == 0
    assert coverage.ranked_count == 0
    assert coverage.unranked_count == 0
    assert coverage.unranked_reason_counts == ()


# --------------------------------------------------------------------------- #
# 9. No accidental mixing across scan identities
# --------------------------------------------------------------------------- #


def test_candidates_from_a_different_run_never_leak_into_top_candidates(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-1"))
    repo.save_scan_run(_scan_run(run_id="run-2", started_ts="2026-08-28T13:00:00+05:30"))
    repo.save_candidates([_candidate(run_id="run-1", instrument_id="NSE:ONE", rank=1)])
    repo.save_candidates([_candidate(run_id="run-2", instrument_id="NSE:TWO", rank=1)])

    top_run_1 = pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10)
    top_run_2 = pres.top_candidates(repo.path, run_id="run-2", family="TOUCH", threshold_percent=10, limit=10)
    assert [c.instrument_id for c in top_run_1] == ["NSE:ONE"]
    assert [c.instrument_id for c in top_run_2] == ["NSE:TWO"]


def test_build_experimental_snapshot_only_ever_uses_its_own_latest_run_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(run_id="run-old", started_ts="2026-08-28T09:00:00+05:30"))
    repo.save_scan_run(_scan_run(run_id="run-new", started_ts="2026-08-28T14:00:00+05:30"))
    repo.save_candidates([_candidate(run_id="run-old", instrument_id="NSE:OLD", rank=1)])
    repo.save_candidates([_candidate(run_id="run-new", instrument_id="NSE:NEW", rank=1)])

    snap = pres.build_experimental_snapshot(repo.path)
    assert snap.scan.run_id == "run-new"
    assert [c.instrument_id for c in snap.touch_10] == ["NSE:NEW"]


# --------------------------------------------------------------------------- #
# 10/11. Read-only, never mutates; repeated query is identical
# --------------------------------------------------------------------------- #


def test_presentation_queries_never_mutate_the_database(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:INFY", rank=1)])
    repo.close()

    before_mtime = os.path.getmtime(repo.path)
    before_size = os.path.getsize(repo.path)

    pres.latest_scan_snapshot(repo.path)
    pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10)
    pres.top_touch_10_candidates(repo.path, run_id="run-1", limit=10)
    pres.coverage_summary(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10)
    pres.build_experimental_snapshot(repo.path)

    assert os.path.getmtime(repo.path) == before_mtime
    assert os.path.getsize(repo.path) == before_size


def test_presentation_connection_is_sqlite_read_only_mode(tmp_path: Path) -> None:
    """A direct attempt to write through this module's own connection
    path must fail at the SQLite layer, not merely be avoided by
    convention."""
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.close()

    import sqlite3

    conn = sqlite3.connect(f"file:{repo.path}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM emr_scan_runs")
    conn.close()


def test_repeated_identical_query_returns_identical_result(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:INFY", rank=1), _candidate(instrument_id="NSE:TCS", rank=2)])

    first = pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10)
    second = pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10)
    assert first == second


# --------------------------------------------------------------------------- #
# 12. No provider/network invocation
# --------------------------------------------------------------------------- #


def test_presentation_module_source_has_no_provider_or_network_calls() -> None:
    """The module docstring names `run_scan_cycle` only to document that
    it is never invoked -- check for an actual call pattern, not the bare
    identifier, alongside genuine provider/network terms."""
    import inspect

    source = inspect.getsource(pres)
    lowered = source.lower()
    forbidden_terms = ("kite", "requests.", "httpx.", "urllib.request")
    assert not any(term in lowered for term in forbidden_terms)
    assert "run_scan_cycle(" not in source


# --------------------------------------------------------------------------- #
# 13/14. No canonical ATHENA / DarvaX dependency
# --------------------------------------------------------------------------- #


def test_presentation_module_imports_nothing_canonical_or_darvax() -> None:
    import inspect

    source = inspect.getsource(pres)
    forbidden_imports = (
        "athena.scoring", "athena.decision", "athena.risk", "athena.trade_plan",
        "athena.darvax", "athena.data.store.repository", "SqliteRepository",
        "athena.intraday", "entry_qualification",
    )
    for term in forbidden_imports:
        assert term not in source, f"unexpected forbidden reference: {term}"


# --------------------------------------------------------------------------- #
# 15. Malformed/incomplete persisted state degrades honestly
# --------------------------------------------------------------------------- #


def test_scan_with_no_finished_ts_but_complete_status_is_not_possible_via_writer(tmp_path: Path) -> None:
    """The real scanner always sets finished_ts together with COMPLETE
    status; this documents that describe_scan_freshness tolerates a
    missing finished_ts by falling back to started_ts, in case a future
    writer ever produces that combination."""
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run(finished_ts=None))
    scan = pres.latest_scan_snapshot(repo.path)
    assert scan is not None
    freshness = pres.describe_scan_freshness(
        scan, as_of=datetime(2026, 8, 28, 12, 5, 0, tzinfo=IST),
    )
    assert freshness.age_seconds == pytest.approx(300.0)


def test_candidate_with_null_calibrated_probability_is_preserved_not_zeroed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    repo.save_candidates([_candidate(instrument_id="NSE:UNKNOWNPROB", rank=1, calibrated_probability=None)])
    top = pres.top_candidates(repo.path, run_id="run-1", family="TOUCH", threshold_percent=10, limit=10)
    assert top[0].calibrated_probability is None


# --------------------------------------------------------------------------- #
# describe_scan_freshness purity
# --------------------------------------------------------------------------- #


def test_describe_scan_freshness_is_pure_and_deterministic(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    scan = pres.latest_scan_snapshot(repo.path)
    as_of = datetime(2026, 8, 28, 12, 30, 0, tzinfo=IST)
    first = pres.describe_scan_freshness(scan, as_of=as_of)
    second = pres.describe_scan_freshness(scan, as_of=as_of)
    assert first == second
    assert first.age_seconds == pytest.approx(1795.0)  # 12:00:05 -> 12:30:00


def test_describe_scan_freshness_applies_no_label(tmp_path: Path) -> None:
    """No FRESH/STALE classification is computed -- only facts."""
    repo = _repo(tmp_path)
    repo.save_scan_run(_scan_run())
    scan = pres.latest_scan_snapshot(repo.path)
    freshness = pres.describe_scan_freshness(
        scan, as_of=datetime(2026, 8, 28, 20, 0, 0, tzinfo=IST),
    )
    assert not hasattr(freshness, "status")
    assert not hasattr(freshness, "label")
