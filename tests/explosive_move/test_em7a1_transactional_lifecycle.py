"""EM-7A.1: transactional lifecycle & idempotency correction.

Proves the owner-ratified resolution to EM-7A's ADR-014 contradiction:
candidate persistence, transition persistence, and the terminal COMPLETE
write now form ONE atomic transaction (`EmrRepository.commit_scan_result`)
-- a failure anywhere inside it leaves zero newly-committed business
rows and the run terminates FAILED, never an orphaned RUNNING row with a
partial durable result. Also proves the three same-run_id idempotency
cases (existing COMPLETE / FAILED / RUNNING) and the EMR-owned lock
integration wrapper. Reuses `test_em5_scanner.py`'s own fixtures/helpers
rather than duplicating them.

Failure injection cannot use `unittest.mock`/`monkeypatch.setattr` on the
`sqlite3.Connection` object directly -- CPython's C-extension type
refuses both instance-level ("attribute is read-only") and class-level
("immutable type") patching of its `execute`/`commit`/etc. methods
(verified empirically, not assumed). Instead `_FailAfterConn` wraps the
real connection and is substituted for `EmrRepository._connect`'s
return value (`_connect` is a plain Python method, freely patchable);
`set_trace_callback` -- a real public sqlite3 API -- observes actual
BEGIN/COMMIT/ROLLBACK boundaries for the one-transaction proof.
"""

from __future__ import annotations

import sqlite3

import pytest
from tests.explosive_move.test_em5_scanner import (
    _STUB_REGIME_LOOKUP,
    CHECKPOINT_INSTANT,
    _config,
    _fake_collector,
    _seed_athena_repo,
)

from athena.domain.enums import SessionType
from athena.errors import RepositoryError
from athena.explosive_move.live.market_data_port import SqliteEmrMarketDataAdapter
from athena.explosive_move.live.scan_lock import EmrScanLock
from athena.explosive_move.live.scanner import (
    EmrScanAlreadyRunningError,
    run_scan_cycle,
    run_scan_cycle_with_lock,
)
from athena.explosive_move.store.repository import EmrRepository


@pytest.fixture()
def scan_setup(tmp_path):
    athena_repo = _seed_athena_repo(tmp_path / "athena")
    market_port = SqliteEmrMarketDataAdapter(athena_repo)
    emr_repo = EmrRepository(tmp_path / "emr" / "emr.db")
    emr_repo.initialize()
    yield market_port, emr_repo
    athena_repo.close()
    emr_repo.close()


def _run(market_port, emr_repo, *, collect_checkpoint_prices=_fake_collector):
    return run_scan_cycle(
        config=_config(), market_port=market_port, emr_repo=emr_repo,
        calendar_context_session_type=SessionType.NORMAL,
        collect_checkpoint_prices=collect_checkpoint_prices,
        regime_lookup=_STUB_REGIME_LOOKUP, now=lambda: CHECKPOINT_INSTANT,
    )


def _run_id() -> str:
    """The deterministic run_id `_config()` always produces -- re-derived
    here (not imported) as an independent pin on `scanner._fingerprint`'s
    formula, matching its own `json.dumps(sort_keys=True, default=str)` +
    sha256 construction exactly."""
    import hashlib
    import json

    config = _config()
    payload = {
        "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
        "universe": config.universe, "model_version": config.model_version,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"em5-scan-{hashlib.sha256(encoded).hexdigest()}"


class _RaisingCollector:
    """A `collect_checkpoint_prices` fake that raises on demand -- used to
    put a run into FAILED deterministically without touching persistence
    internals."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __call__(self, **_kwargs):
        raise self._exc


class _FailAfterConn:
    """Wraps a real `sqlite3.Connection` so a test can inject a failure at
    an exact point inside one transaction. `sqlite3.Connection`'s own
    `execute`/`commit`/etc. cannot be monkeypatched (CPython raises
    "attribute is read-only" at the instance level and "immutable type"
    at the class level -- verified, not assumed), so this proxy is
    substituted for `EmrRepository._connect()`'s return value instead.
    Delegates everything else transparently, including the
    `with conn:` commit/rollback protocol `commit_scan_result` relies on."""

    def __init__(self, real_conn: sqlite3.Connection, *, fail_sql_substring: str, exc: Exception) -> None:
        self._real = real_conn
        self._fail_sql_substring = fail_sql_substring
        self._exc = exc

    def execute(self, sql, params=()):
        if self._fail_sql_substring in sql:
            raise self._exc
        return self._real.execute(sql, params)

    def executemany(self, sql, params):
        if self._fail_sql_substring in sql:
            raise self._exc
        return self._real.executemany(sql, params)

    def __enter__(self):
        self._real.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._real.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._real, name)


def _inject_failure(emr_repo, monkeypatch, *, fail_sql_substring, exc):
    """Installs a `_FailAfterConn` in place of `emr_repo`'s real
    connection for the rest of the test. Returns the real connection so
    the caller can still attach `set_trace_callback` or run post-failure
    assertions against it directly."""
    real_conn = emr_repo._connect()
    proxy = _FailAfterConn(real_conn, fail_sql_substring=fail_sql_substring, exc=exc)
    monkeypatch.setattr(emr_repo, "_connect", lambda: proxy)
    return real_conn


class TestFailureInjection:
    def test_candidate_write_failure_leaves_no_committed_rows_and_marks_failed(self, scan_setup, monkeypatch):
        market_port, emr_repo = scan_setup
        _inject_failure(
            emr_repo, monkeypatch, fail_sql_substring="INSERT INTO emr_candidates",
            exc=sqlite3.OperationalError("synthetic candidate write failure"),
        )

        with pytest.raises(RepositoryError, match="cannot commit EM-5 scan result"):
            _run(market_port, emr_repo)

        run = emr_repo.get_scan_run(_run_id())
        assert run["status"] == "FAILED"
        assert emr_repo.list_candidates(run_id=_run_id()) == []
        assert emr_repo.list_transitions_for_run(run_id=_run_id()) == []

    def test_transition_write_failure_after_candidates_rolls_back_everything(self, scan_setup, monkeypatch):
        """The crucial atomicity proof: candidates' own INSERT executes
        first (inside the transaction), then transitions' INSERT fails --
        the whole transaction must still roll back, leaving zero
        candidate rows too, not just zero transition rows."""
        market_port, emr_repo = scan_setup
        _inject_failure(
            emr_repo, monkeypatch, fail_sql_substring="INSERT INTO emr_transitions",
            exc=sqlite3.OperationalError("synthetic transition write failure"),
        )

        with pytest.raises(RepositoryError, match="cannot commit EM-5 scan result"):
            _run(market_port, emr_repo)

        run = emr_repo.get_scan_run(_run_id())
        assert run["status"] == "FAILED"
        assert emr_repo.list_candidates(run_id=_run_id()) == [], (
            "candidates must be rolled back even though their own INSERT executed successfully"
        )
        assert emr_repo.list_transitions_for_run(run_id=_run_id()) == []

    def test_complete_update_failure_rolls_back_everything(self, scan_setup, monkeypatch):
        market_port, emr_repo = scan_setup
        # "status='COMPLETE'" appears only in commit_scan_result's own
        # terminal UPDATE -- never in mark_scan_failed's UPDATE (which
        # sets status='FAILED'), so this does not also block the
        # subsequent FAILED write in the except block.
        _inject_failure(
            emr_repo, monkeypatch, fail_sql_substring="status='COMPLETE'",
            exc=sqlite3.OperationalError("synthetic terminal-update failure"),
        )

        with pytest.raises(RepositoryError, match="cannot commit EM-5 scan result"):
            _run(market_port, emr_repo)

        run = emr_repo.get_scan_run(_run_id())
        assert run["status"] == "FAILED"
        assert emr_repo.list_candidates(run_id=_run_id()) == []
        assert emr_repo.list_transitions_for_run(run_id=_run_id()) == []

    def test_failed_persistence_failure_preserves_original_exception(self, scan_setup, monkeypatch):
        market_port, emr_repo = scan_setup
        original_exc = ValueError("original scan failure")

        def _mark_failed_raises(**_kwargs):
            raise RepositoryError("secondary: cannot write FAILED either")

        monkeypatch.setattr(emr_repo, "mark_scan_failed", _mark_failed_raises)

        with pytest.raises(ValueError, match="original scan failure") as excinfo:
            _run(market_port, emr_repo, collect_checkpoint_prices=_RaisingCollector(original_exc))

        assert excinfo.value is original_exc
        assert isinstance(excinfo.value.__cause__, RepositoryError)
        assert "secondary" in str(excinfo.value.__cause__)

    def test_successful_run_persists_complete_result(self, scan_setup):
        market_port, emr_repo = scan_setup
        result = _run(market_port, emr_repo)
        assert result.status == "COMPLETE"
        run = emr_repo.get_scan_run(result.run_id)
        assert run["status"] == "COMPLETE"
        assert len(emr_repo.list_candidates(run_id=result.run_id)) == result.candidates_persisted
        assert len(emr_repo.list_transitions_for_run(run_id=result.run_id)) == result.transitions_persisted
        assert result.candidates_persisted > 0
        assert result.transitions_persisted > 0


class TestIdempotency:
    def test_same_complete_run_called_twice_does_not_recompute_or_recall_provider(self, scan_setup):
        market_port, emr_repo = scan_setup
        collector_calls = {"n": 0}

        def counting_collector(**kwargs):
            collector_calls["n"] += 1
            return _fake_collector(**kwargs)

        first = _run(market_port, emr_repo, collect_checkpoint_prices=counting_collector)
        assert collector_calls["n"] == 1
        first_candidates = emr_repo.list_candidates(run_id=first.run_id)

        second = _run(market_port, emr_repo, collect_checkpoint_prices=counting_collector)
        assert collector_calls["n"] == 1, "an already-COMPLETE run must not re-invoke the checkpoint collector"
        assert second.run_id == first.run_id
        assert second.status == "COMPLETE"
        assert second.candidates_persisted == first.candidates_persisted
        assert second.transitions_persisted == first.transitions_persisted
        assert emr_repo.list_candidates(run_id=first.run_id) == first_candidates, "no duplicate rows"

    def test_failed_run_can_be_retried_to_success(self, scan_setup):
        market_port, emr_repo = scan_setup
        with pytest.raises(ValueError, match="synthetic failure"):
            _run(market_port, emr_repo, collect_checkpoint_prices=_RaisingCollector(ValueError("synthetic failure")))
        failed_run_id = _run_id()
        assert emr_repo.get_scan_run(failed_run_id)["status"] == "FAILED"

        result = _run(market_port, emr_repo)  # retry with the same deterministic identity
        assert result.run_id == failed_run_id
        assert result.status == "COMPLETE"
        run = emr_repo.get_scan_run(failed_run_id)
        assert run["status"] == "COMPLETE"
        # one coherent durable result set -- not doubled by the failed attempt
        assert len(emr_repo.list_candidates(run_id=failed_run_id)) == result.candidates_persisted

    def test_existing_running_row_rejects_second_execution(self, scan_setup):
        market_port, emr_repo = scan_setup
        emr_repo.save_scan_run({
            "run_id": _run_id(), "session_date": _config().session_date.isoformat(),
            "checkpoint": _config().checkpoint, "frozen_model_version": _config().model_version,
            "status": "RUNNING", "started_ts": CHECKPOINT_INSTANT.isoformat(),
        })
        with pytest.raises(EmrScanAlreadyRunningError, match=_run_id()):
            _run(market_port, emr_repo)

    def test_duplicate_candidate_insert_protection_mutation_proof(self, scan_setup):
        """Attempts a raw duplicate INSERT sharing an existing
        candidate's (run_id, instrument_id, family, threshold_percent)
        identity, proving the EM-7A.1 UNIQUE index (defense-in-depth
        alongside, never instead of, `commit_scan_result`'s own
        atomicity) actually rejects it. Reads only real, already-
        committed rows -- no code is mutated."""
        market_port, emr_repo = scan_setup
        _run(market_port, emr_repo)
        run_id = _run_id()
        conn = emr_repo._connect()
        row = conn.execute(
            "SELECT run_id, instrument_id, family, threshold_percent, checkpoint, session_date, "
            "raw_logistic_estimate, probability_language, em4b_model_version, em4d_calibration_version, "
            "evidence_timestamp, evidence_completeness_known, evidence_completeness_total, freshness, "
            "feasibility, state, state_reason, created_ts "
            "FROM emr_candidates WHERE run_id = ? LIMIT 1", (run_id,),
        ).fetchone()
        assert row is not None

        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
            conn.execute(
                "INSERT INTO emr_candidates (run_id, instrument_id, family, threshold_percent, checkpoint, "
                "session_date, raw_logistic_estimate, probability_language, em4b_model_version, "
                "em4d_calibration_version, evidence_timestamp, evidence_completeness_known, "
                "evidence_completeness_total, freshness, feasibility, state, state_reason, created_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )


class TestOneTransactionRegressionProof:
    """Proves `commit_scan_result` uses exactly one transaction boundary
    for candidates + transitions + COMPLETE together, using
    `set_trace_callback` (a real sqlite3 API) to observe actual
    BEGIN/COMMIT/ROLLBACK statements sent to SQLite -- not row-count
    inference. A future refactor back into three independently-committed
    calls would raise the observed COMMIT count and would fail these
    assertions."""

    def test_successful_result_uses_exactly_two_commits_total(self, scan_setup):
        market_port, emr_repo = scan_setup
        real_conn = emr_repo._connect()
        trace: list[str] = []
        real_conn.set_trace_callback(trace.append)
        try:
            result = _run(market_port, emr_repo)
        finally:
            real_conn.set_trace_callback(None)

        assert result.status == "COMPLETE"
        assert trace.count("COMMIT") == 2, (
            f"expected exactly 2 commits (RUNNING write + one atomic result transaction), got {trace}"
        )
        assert trace.count("ROLLBACK") == 0

    def test_failed_result_rolls_back_the_result_transaction_exactly_once(self, scan_setup, monkeypatch):
        market_port, emr_repo = scan_setup
        real_conn = _inject_failure(
            emr_repo, monkeypatch, fail_sql_substring="INSERT INTO emr_transitions",
            exc=sqlite3.OperationalError("synthetic failure"),
        )
        trace: list[str] = []
        real_conn.set_trace_callback(trace.append)
        try:
            with pytest.raises(RepositoryError):
                _run(market_port, emr_repo)
        finally:
            real_conn.set_trace_callback(None)

        # RUNNING write's own commit, and mark_scan_failed's own commit,
        # are each separate, intentional transactions (Sections 3-5 of
        # the owner's EM-7A.1 authorization) -- the result transaction
        # itself must never commit, only roll back exactly once.
        assert trace.count("COMMIT") == 2, f"expected RUNNING + FAILED-marking commits only, got {trace}"
        assert trace.count("ROLLBACK") == 1


class TestLockIntegration:
    def test_run_scan_cycle_with_lock_acquires_and_releases(self, scan_setup, tmp_path):
        market_port, emr_repo = scan_setup
        lock = EmrScanLock(tmp_path / "emr-scan.lock")
        result = run_scan_cycle_with_lock(
            lock=lock, config=_config(), market_port=market_port, emr_repo=emr_repo,
            calendar_context_session_type=SessionType.NORMAL, collect_checkpoint_prices=_fake_collector,
            regime_lookup=_STUB_REGIME_LOOKUP, now=lambda: CHECKPOINT_INSTANT,
        )
        assert result.status == "COMPLETE"
        # Lock must be released afterwards -- a fresh acquire succeeds.
        after = EmrScanLock(tmp_path / "emr-scan.lock")
        assert after.acquire() is True
        after.release()

    def test_run_scan_cycle_with_lock_releases_on_exception(self, scan_setup, tmp_path):
        market_port, emr_repo = scan_setup
        lock_path = tmp_path / "emr-scan.lock"
        with pytest.raises(ValueError, match="boom"):
            run_scan_cycle_with_lock(
                lock=EmrScanLock(lock_path), config=_config(), market_port=market_port, emr_repo=emr_repo,
                calendar_context_session_type=SessionType.NORMAL,
                collect_checkpoint_prices=_RaisingCollector(ValueError("boom")),
                regime_lookup=_STUB_REGIME_LOOKUP, now=lambda: CHECKPOINT_INSTANT,
            )
        after = EmrScanLock(lock_path)
        assert after.acquire() is True
        after.release()

    def test_run_scan_cycle_with_lock_rejects_concurrent_second_holder(self, scan_setup, tmp_path):
        """`run_scan_cycle_with_lock` must actually acquire the lock
        (not just release it afterwards) -- proven by holding the same
        lock path externally and confirming a second attempt is refused."""
        market_port, emr_repo = scan_setup
        lock_path = tmp_path / "emr-scan.lock"
        holder = EmrScanLock(lock_path)
        assert holder.acquire() is True
        try:
            with pytest.raises(Exception, match="already holds the lock"):
                run_scan_cycle_with_lock(
                    lock=EmrScanLock(lock_path), config=_config(), market_port=market_port, emr_repo=emr_repo,
                    calendar_context_session_type=SessionType.NORMAL, collect_checkpoint_prices=_fake_collector,
                    regime_lookup=_STUB_REGIME_LOOKUP, now=lambda: CHECKPOINT_INSTANT,
                )
        finally:
            holder.release()
