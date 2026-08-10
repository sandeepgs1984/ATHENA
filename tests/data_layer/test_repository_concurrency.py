"""ADR-009 acceptance tests: per-thread read-only SQLite connections.

Verifies SqliteRepository's read path (_query_one/_query_all) no longer
serializes through the write connection/RLock, while the write path
(_write/_write_many) and every public method signature stay exactly as
they were. See docs/adr/ADR-009-repository-read-concurrency.md for the
full design, rationale, and the stated limits of the read-connection
cleanup model (items 6-9 in particular map directly to this file's tests).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.store import SqliteRepository
from athena.domain.decision import Decision
from athena.domain.enums import DecisionType, Direction

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 8, 10, 12, 0, tzinfo=IST)


def _decision(decision_id: str, instrument_id: str = "SYN-AAA") -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id="run-1",
        cycle_id="c-1",
        decision_type=DecisionType.WATCH,
        explanation="ADR-009 concurrency test",
        instrument_id=instrument_id,
        direction=Direction.NONE,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> SqliteRepository:
    r = SqliteRepository(tmp_path / "concurrency.db")
    r.initialize()
    yield r
    r.close()


# --------------------------------------------------------------------------- #
# 1. Concurrent reads do not wait on the Python write lock during a slow write
# --------------------------------------------------------------------------- #


def test_reads_do_not_wait_on_slow_write_transaction(repo: SqliteRepository):
    hold_seconds = 1.0
    write_started = threading.Event()

    def slow_write():
        # Mirrors _write()'s own lock+transaction shape exactly, with a
        # sleep before commit — "a write inside a transaction that sleeps
        # for N seconds before committing" (ADR-009 test item 1).
        with repo._lock:
            with repo._conn:
                repo._conn.execute(
                    "INSERT INTO decisions (decision_id, ts, run_id, cycle_id, "
                    "decision_type, explanation, instrument_id, direction, "
                    "gate_results_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    ("d-slow-write", AS_OF.isoformat(), "run-1", "c-1", "WATCH",
                     "slow write", "SYN-SLOW", "NONE", "[]"),
                )
                write_started.set()
                time.sleep(hold_seconds)

    t = threading.Thread(target=slow_write)
    t.start()
    assert write_started.wait(timeout=2.0)

    t0 = time.perf_counter()
    row = repo._query_one("SELECT COUNT(*) FROM decisions", ())
    elapsed = time.perf_counter() - t0
    t.join()

    assert row is not None
    # Native read time, not anywhere near the write's hold_seconds sleep —
    # proves _query_one does not depend on the write lock.
    assert elapsed < hold_seconds / 2


# --------------------------------------------------------------------------- #
# 2. Concurrent reads do not serialize behind one another
# --------------------------------------------------------------------------- #


def test_concurrent_reads_do_not_serialize(repo: SqliteRepository):
    n_workers = 6
    delay_seconds = 0.3

    def worker(_: int) -> float:
        conn = repo._read_connection()
        conn.create_function("adr009_test_sleep", 1, lambda secs: time.sleep(secs) or 0)
        t0 = time.perf_counter()
        conn.execute("SELECT adr009_test_sleep(?)", (delay_seconds,)).fetchone()
        return time.perf_counter() - t0

    t_batch0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        per_worker = list(pool.map(worker, range(n_workers)))
    batch_elapsed = time.perf_counter() - t_batch0

    # Every worker individually took ~delay_seconds.
    assert all(d >= delay_seconds * 0.8 for d in per_worker)
    # If serialized (old single-connection/lock model), the batch would take
    # roughly n_workers * delay_seconds (~1.8s here). True parallelism keeps
    # it close to a single delay_seconds; generous margin to avoid flakiness.
    assert batch_elapsed < delay_seconds * (n_workers / 2)


# --------------------------------------------------------------------------- #
# 3. Existing write serialization remains correct (no new retry/backoff)
# --------------------------------------------------------------------------- #


def test_concurrent_writes_still_serialize_with_no_lost_updates(repo: SqliteRepository):
    n_writers = 16

    def writer(i: int) -> None:
        repo.save_decision(_decision(f"d-concurrent-{i}"))

    with ThreadPoolExecutor(max_workers=n_writers) as pool:
        list(pool.map(writer, range(n_writers)))

    # Exactly what a fully serial execution would produce: every write
    # landed, none lost, none corrupted — same RLock-based guarantee as
    # before ADR-009, unchanged by the read-path split.
    assert repo.record_counts()["decisions"] == n_writers
    for i in range(n_writers):
        assert repo.get_decision(f"d-concurrent-{i}") is not None


# --------------------------------------------------------------------------- #
# 4. Committed writes are immediately visible to read connections
# --------------------------------------------------------------------------- #


def test_committed_write_visible_without_reconnect_or_checkpoint(repo: SqliteRepository):
    # Warm the calling thread's read connection *before* the write exists,
    # to prove a previously-opened, cached connection still sees it.
    assert repo.get_decision("d-visibility") is None

    repo.save_decision(_decision("d-visibility"))

    # Same thread, same cached read connection, no reconnect/checkpoint call.
    loaded = repo.get_decision("d-visibility")
    assert loaded is not None
    assert loaded.decision_id == "d-visibility"


def test_committed_write_visible_to_a_different_threads_read_connection(
    repo: SqliteRepository,
):
    repo.save_decision(_decision("d-cross-thread"))

    result: dict[str, object] = {}

    def reader():
        result["decision"] = repo.get_decision("d-cross-thread")

    t = threading.Thread(target=reader)
    t.start()
    t.join()

    assert result["decision"] is not None
    assert result["decision"].decision_id == "d-cross-thread"


# --------------------------------------------------------------------------- #
# 5. Read connections are physically read-only
# --------------------------------------------------------------------------- #


def test_read_connection_rejects_writes_at_sqlite_level(repo: SqliteRepository):
    conn = repo._read_connection()
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute(
            "INSERT INTO decisions (decision_id, ts, run_id, cycle_id, "
            "decision_type, explanation, direction, gate_results_json) "
            "VALUES ('x','x','x','x','WATCH','x','NONE','[]')"
        )
    # The write path itself is completely unaffected — same connection,
    # same lock, still works normally.
    repo.save_decision(_decision("d-after-ro-attempt"))
    assert repo.get_decision("d-after-ro-attempt") is not None


# --------------------------------------------------------------------------- #
# 6. Per-thread connection lifecycle: create, isolate, clean up, recreate
# --------------------------------------------------------------------------- #


def test_read_connection_lifecycle_per_controlled_worker_thread(repo: SqliteRepository):
    """Owner-approved semantics (ADR-009, corrected item 6): this proves
    per-thread create/use/cleanup/isolation/lazy-recreation for worker
    threads this test itself drives — it does NOT assert that a central
    shutdown thread can reach into and close another thread's connection,
    which ADR-009 explicitly states is out of scope (no global registry)."""
    connections_by_thread: dict[int, sqlite3.Connection] = {}
    closed_ok: dict[int, bool] = {}
    recreated_ok: dict[int, bool] = {}

    def worker(idx: int) -> None:
        conn_first = repo._read_connection()
        connections_by_thread[idx] = conn_first
        conn_first.execute("SELECT 1").fetchone()

        # Reused, not reopened, for a second read on the same thread.
        conn_again = repo._read_connection()
        assert conn_again is conn_first

        # This thread cleans up its own connection before "exiting".
        repo.close_read_connection()
        try:
            conn_first.execute("SELECT 1")
            closed_ok[idx] = False
        except sqlite3.ProgrammingError:
            closed_ok[idx] = True  # closed connections raise on use

        # A read after explicit cleanup lazily creates a fresh connection.
        conn_fresh = repo._read_connection()
        recreated_ok[idx] = conn_fresh is not conn_first
        conn_fresh.execute("SELECT 1").fetchone()
        repo.close_read_connection()  # leave the thread clean

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(closed_ok) == 4
    assert all(closed_ok.values())
    assert all(recreated_ok.values())
    # No two threads ever shared the same connection object.
    ids = [id(c) for c in connections_by_thread.values()]
    assert len(ids) == len(set(ids))


def test_close_read_connection_is_a_noop_when_none_open(repo: SqliteRepository):
    # A thread that never issued a read has nothing to clean up — must not
    # raise, and must not affect the write connection.
    def worker():
        repo.close_read_connection()

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    # Write path still fully functional afterwards.
    repo.save_decision(_decision("d-after-noop-cleanup"))
    assert repo.get_decision("d-after-noop-cleanup") is not None


def test_in_memory_repository_reads_see_writes_on_the_shared_connection():
    """A second connection to ':memory:' is a distinct, empty database, not
    another handle onto the same one (no file to attach a read-only
    connection to). This is a real, existing usage pattern — see
    config_preview.py's and canary.py's throwaway shadow repos — so
    _query_one/_query_all must fall back to the shared write
    connection/lock for ':memory:', exactly as before ADR-009."""
    repo = SqliteRepository(":memory:")
    repo.initialize()
    try:
        repo.save_decision(_decision("d-memory-visible"))
        assert repo.get_decision("d-memory-visible") is not None
        assert repo.record_counts()["decisions"] == 1
    finally:
        repo.close()


def test_repository_close_closes_calling_threads_read_connection_and_write_connection(
    tmp_path: Path,
):
    r = SqliteRepository(tmp_path / "close_test.db")
    r.initialize()
    r._query_one("SELECT 1", ())  # opens this (main) thread's read connection
    read_conn = r._read_local.conn
    write_conn = r._conn

    r.close()

    with pytest.raises(sqlite3.ProgrammingError):
        read_conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        write_conn.execute("SELECT 1")


# --------------------------------------------------------------------------- #
# 8/9. Real traced-scenario reproductions with before/after timings
# --------------------------------------------------------------------------- #


def _simulate_old_single_lock_read(repo: SqliteRepository, sql: str, params: tuple = ()):
    """Reproduces the pre-ADR-009 code path exactly (_query_one before this
    milestone): route the read through the shared write connection/lock
    instead of a per-thread read connection. Used only to produce a fair
    'before' timing baseline in the same process, not a code path any
    production caller can reach after this milestone."""
    with repo._lock:
        return repo._conn.execute(sql, params).fetchone()


def _run_market_intelligence_shaped_burst(read_fn, repo: SqliteRepository, n_reads: int):
    with ThreadPoolExecutor(max_workers=n_reads) as pool:
        list(pool.map(lambda _: read_fn(repo, "SELECT COUNT(*) FROM decisions", ()), range(n_reads)))


def test_ablbl_style_validate_concurrency_scenario_before_after(repo: SqliteRepository, capsys):
    """Reproduces the traced ABLBL pattern: a slow validate-shaped write
    transaction (backend POST /validate measured ~2-8s this session) running
    concurrently with a loadMarketIntelligence()-shaped burst of reads
    (~15-20 endpoint calls observed in the live server log). Compares the
    'before' code path (reads sharing the write lock) against 'after'
    (per-thread read connections) in the same process, same data, same
    machine — the only variable is which read path is used."""
    hold_seconds = 0.5
    n_reads = 18  # matches the live-traced loadMarketIntelligence() burst size

    def slow_validate_write(decision_id: str):
        with repo._lock:
            with repo._conn:
                repo._conn.execute(
                    "INSERT INTO decisions (decision_id, ts, run_id, cycle_id, "
                    "decision_type, explanation, instrument_id, direction, "
                    "gate_results_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    (decision_id, AS_OF.isoformat(), "run-1", "c-1", "WATCH",
                     "ablbl scenario", "NSE:ABLBL", "NONE", "[]"),
                )
                time.sleep(hold_seconds)

    # BEFORE: reads share the write connection/lock (pre-ADR-009 behavior).
    t = threading.Thread(target=slow_validate_write, args=("d-ablbl-sim-before",))
    t.start()
    time.sleep(0.05)
    t0 = time.perf_counter()
    _run_market_intelligence_shaped_burst(_simulate_old_single_lock_read, repo, n_reads)
    before_elapsed = time.perf_counter() - t0
    t.join()

    # AFTER: reads use their own per-thread read-only connections.
    def after_read(repo, sql, params=()):
        return repo._query_one(sql, params)

    t = threading.Thread(target=slow_validate_write, args=("d-ablbl-sim-after",))
    t.start()
    time.sleep(0.05)
    t0 = time.perf_counter()
    _run_market_intelligence_shaped_burst(after_read, repo, n_reads)
    after_elapsed = time.perf_counter() - t0
    t.join()

    with capsys.disabled():
        print(
            f"\n[ADR-009 evidence] ABLBL-style scenario ({n_reads} concurrent "
            f"reads vs a {hold_seconds}s write): before={before_elapsed:.3f}s "
            f"after={after_elapsed:.3f}s"
        )

    # Before: reads queue behind the held write lock (~hold_seconds or more).
    assert before_elapsed >= hold_seconds * 0.8
    # After: reads are not blocked by the write lock at all.
    assert after_elapsed < hold_seconds / 2
    assert after_elapsed < before_elapsed


def test_portfolio_overview_style_cold_load_scenario_before_after(
    repo: SqliteRepository, capsys
):
    """Reproduces the Portfolio Overview observation: a cheap, unrelated
    read (no Kite calls, no catalog resolution) queued behind a burst of
    other reads and a concurrent write purely because everything shared one
    connection/lock. 'Portfolio Overview' itself is simulated as one more
    cheap read racing to complete alongside the same cold-load burst used
    in the ABLBL-style test above."""
    hold_seconds = 0.5
    n_burst_reads = 18

    def slow_cold_start_write(decision_id: str):
        with repo._lock:
            with repo._conn:
                repo._conn.execute(
                    "INSERT INTO decisions (decision_id, ts, run_id, cycle_id, "
                    "decision_type, explanation, instrument_id, direction, "
                    "gate_results_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    (decision_id, AS_OF.isoformat(), "run-1", "c-1", "WATCH",
                     "portfolio cold load scenario", "NSE:PORTFOLIO", "NONE", "[]"),
                )
                time.sleep(hold_seconds)

    def portfolio_overview_read(read_fn):
        return read_fn(repo, "SELECT COUNT(*) FROM decisions", ())

    # BEFORE
    t = threading.Thread(target=slow_cold_start_write, args=("d-portfolio-sim-before",))
    t.start()
    time.sleep(0.05)
    with ThreadPoolExecutor(max_workers=n_burst_reads + 1) as pool:
        t0 = time.perf_counter()
        futures = [
            pool.submit(_simulate_old_single_lock_read, repo, "SELECT COUNT(*) FROM decisions", ())
            for _ in range(n_burst_reads)
        ]
        portfolio_future = pool.submit(portfolio_overview_read, _simulate_old_single_lock_read)
        for f in futures:
            f.result()
        portfolio_future.result()
        before_elapsed = time.perf_counter() - t0
    t.join()

    # AFTER
    def after_read(repo, sql, params=()):
        return repo._query_one(sql, params)

    t = threading.Thread(target=slow_cold_start_write, args=("d-portfolio-sim-after",))
    t.start()
    time.sleep(0.05)
    with ThreadPoolExecutor(max_workers=n_burst_reads + 1) as pool:
        t0 = time.perf_counter()
        futures = [
            pool.submit(after_read, repo, "SELECT COUNT(*) FROM decisions", ())
            for _ in range(n_burst_reads)
        ]
        portfolio_future = pool.submit(portfolio_overview_read, after_read)
        for f in futures:
            f.result()
        portfolio_future.result()
        after_elapsed = time.perf_counter() - t0
    t.join()

    with capsys.disabled():
        print(
            f"\n[ADR-009 evidence] Portfolio-Overview-style cold load "
            f"({n_burst_reads + 1} concurrent reads vs a {hold_seconds}s write): "
            f"before={before_elapsed:.3f}s after={after_elapsed:.3f}s"
        )

    assert before_elapsed >= hold_seconds * 0.8
    assert after_elapsed < hold_seconds / 2
    assert after_elapsed < before_elapsed
