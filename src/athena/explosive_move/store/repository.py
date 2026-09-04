"""EM-5's own ledger over its own SQLite file (ADR-012 Section 3).

Separate file, separate connection, separate schema version -- mirrors
DarvaX's own established isolation pattern (ADR-010 Section 2) exactly.
Nothing here can reach ``db/athena.db``.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from athena.errors import RepositoryError
from athena.explosive_move.store.schema import (
    EMR_SCHEMA_VERSION,
    ddl_statements,
    migration_alter_columns,
)

#: EM-7A.1: bounded failure diagnostics only -- never an unbounded
#: traceback, never secrets/tokens/headers/provider payloads.
_MAX_FAILURE_REASON_LENGTH = 2000


class EmrRepository:
    """Minimal EM-5 ledger: opens/creates ``emr.db`` and records its version."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> str:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            parent = Path(self._path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
            try:
                self._conn = sqlite3.connect(self._path, isolation_level="DEFERRED", check_same_thread=False)
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot open EMR database at {self._path}: {exc}") from exc
        return self._conn

    def initialize(self) -> None:
        """Create EM-5's schema (idempotent) and record its own version.

        EM-7A.1: also applies any `ALTER TABLE ... ADD COLUMN` migrations
        a pre-existing (schema v1) database needs -- `CREATE TABLE IF NOT
        EXISTS` alone cannot add a column to an already-existing table.
        A no-op against any database created fresh under the current DDL.
        """
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    for statement in ddl_statements():
                        conn.execute(statement)
                    for table, column_def in migration_alter_columns():
                        column_name = column_def.split()[0]
                        existing = {
                            row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                        }
                        if column_name not in existing:
                            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
                    row = conn.execute("SELECT version FROM emr_schema_version").fetchone()
                    if row is None:
                        conn.execute("INSERT INTO emr_schema_version(version) VALUES (?)", (EMR_SCHEMA_VERSION,))
                    elif int(row[0]) < EMR_SCHEMA_VERSION:
                        conn.execute("UPDATE emr_schema_version SET version = ?", (EMR_SCHEMA_VERSION,))
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot initialize EMR schema: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------ #
    # Scan runs
    # ------------------------------------------------------------------ #

    def save_scan_run(self, run: dict) -> None:
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO emr_scan_runs (
                            run_id, session_date, checkpoint, frozen_model_version, status,
                            started_ts, finished_ts, eligible_count, ineligible_count,
                            evidence_generation_duration_ms, quote_capture_duration_ms,
                            inference_duration_ms, total_duration_ms, quote_request_count,
                            db_read_latency_ms, detail_json, failure_type, failure_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(run_id) DO UPDATE SET
                            status=excluded.status, finished_ts=excluded.finished_ts,
                            eligible_count=excluded.eligible_count, ineligible_count=excluded.ineligible_count,
                            evidence_generation_duration_ms=excluded.evidence_generation_duration_ms,
                            quote_capture_duration_ms=excluded.quote_capture_duration_ms,
                            inference_duration_ms=excluded.inference_duration_ms,
                            total_duration_ms=excluded.total_duration_ms,
                            quote_request_count=excluded.quote_request_count,
                            db_read_latency_ms=excluded.db_read_latency_ms,
                            detail_json=excluded.detail_json,
                            failure_type=excluded.failure_type,
                            failure_reason=excluded.failure_reason
                        """,
                        (
                            run["run_id"], run["session_date"], run["checkpoint"], run["frozen_model_version"],
                            run["status"], run["started_ts"], run.get("finished_ts"),
                            run.get("eligible_count"), run.get("ineligible_count"),
                            run.get("evidence_generation_duration_ms"), run.get("quote_capture_duration_ms"),
                            run.get("inference_duration_ms"), run.get("total_duration_ms"),
                            run.get("quote_request_count"), run.get("db_read_latency_ms"),
                            json.dumps(run.get("detail", {}), sort_keys=True),
                            run.get("failure_type"), run.get("failure_reason"),
                        ),
                    )
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot save EM-5 scan run: {exc}") from exc

    def get_scan_run(self, run_id: str) -> dict | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT run_id, session_date, checkpoint, frozen_model_version, status, started_ts, finished_ts, "
            "eligible_count, ineligible_count, evidence_generation_duration_ms, quote_capture_duration_ms, "
            "inference_duration_ms, total_duration_ms, quote_request_count, db_read_latency_ms, "
            "failure_type, failure_reason, detail_json "
            "FROM emr_scan_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        cols = (
            "run_id", "session_date", "checkpoint", "frozen_model_version", "status", "started_ts", "finished_ts",
            "eligible_count", "ineligible_count", "evidence_generation_duration_ms", "quote_capture_duration_ms",
            "inference_duration_ms", "total_duration_ms", "quote_request_count", "db_read_latency_ms",
            "failure_type", "failure_reason",
        )
        result = dict(zip(cols, row[:-1], strict=True))
        result["detail"] = json.loads(row[-1]) if row[-1] else {}
        return result

    # ------------------------------------------------------------------ #
    # EM-7A.1: atomic result commit / failure marking
    # ------------------------------------------------------------------ #

    def commit_scan_result(
        self, *, run_id: str, candidates: list[dict], transitions: list[dict], run_update: dict,
    ) -> None:
        """The ONE transaction that makes a scan run's result durable.

        Requires `run_id` to already exist with `status='RUNNING'` (never
        silently completes an unknown or already-terminal run). Replaces
        any existing candidate/transition rows for this exact `run_id`
        (delete-then-insert, safe for a FAILED-run retry using the same
        deterministic identity, and a no-op for a fresh run with nothing
        to delete) with the freshly computed result, then marks the run
        `COMPLETE` -- all inside one SQLite transaction. Either the whole
        result becomes durable, or none of it does: on any failure the
        transaction rolls back in full, leaving zero new candidate rows,
        zero new transition rows, and the run still at `RUNNING` (the
        caller is expected to then mark it `FAILED` separately -- see
        `mark_scan_failed`). `COMPLETE` is therefore a trustworthy durable
        fact once this call returns, never merely "the last of three
        independently-committed calls happened to succeed."
        """
        now = datetime.now(tz=UTC).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    current = conn.execute(
                        "SELECT status FROM emr_scan_runs WHERE run_id = ?", (run_id,)
                    ).fetchone()
                    if current is None:
                        raise RepositoryError(
                            f"cannot commit EM-5 scan result: unknown run_id {run_id!r}"
                        )
                    if current[0] != "RUNNING":
                        raise RepositoryError(
                            f"cannot commit EM-5 scan result for run_id {run_id!r}: "
                            f"expected status RUNNING, found {current[0]!r}"
                        )

                    conn.execute("DELETE FROM emr_candidates WHERE run_id = ?", (run_id,))
                    conn.execute("DELETE FROM emr_transitions WHERE run_id = ?", (run_id,))

                    if candidates:
                        conn.executemany(
                            """
                            INSERT INTO emr_candidates (
                                run_id, instrument_id, family, threshold_percent, checkpoint, session_date,
                                rank, raw_logit, raw_logistic_estimate, deterministic_score, calibrated_probability,
                                probability_language, em4b_model_version, em4d_calibration_version,
                                checkpoint_price, checkpoint_price_semantic, checkpoint_snapshot_timestamp,
                                checkpoint_last_trade_time, checkpoint_price_latency_seconds,
                                evidence_timestamp, evidence_completeness_known, evidence_completeness_total,
                                freshness, feasibility, feasibility_reason, state, state_reason,
                                logit_contributions_json, created_ts
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                            )
                            """,
                            [
                                (
                                    c["run_id"], c["instrument_id"], c["family"], c["threshold_percent"],
                                    c["checkpoint"], c["session_date"], c.get("rank"), c.get("raw_logit"),
                                    c["raw_logistic_estimate"], c.get("deterministic_score"),
                                    c.get("calibrated_probability"), c["probability_language"],
                                    c["em4b_model_version"], c["em4d_calibration_version"],
                                    str(c["checkpoint_price"]) if c.get("checkpoint_price") is not None else None,
                                    c.get("checkpoint_price_semantic"), c.get("checkpoint_snapshot_timestamp"),
                                    c.get("checkpoint_last_trade_time"), c.get("checkpoint_price_latency_seconds"),
                                    c["evidence_timestamp"], c["evidence_completeness_known"],
                                    c["evidence_completeness_total"], c["freshness"], c["feasibility"],
                                    c.get("feasibility_reason"), c["state"], c["state_reason"],
                                    json.dumps(c.get("logit_contributions", {}), sort_keys=True), now,
                                )
                                for c in candidates
                            ],
                        )

                    if transitions:
                        conn.executemany(
                            """
                            INSERT INTO emr_transitions (
                                run_id, instrument_id, family, threshold_percent, checkpoint, session_date,
                                sequence_number, from_state, to_state, reason, created_ts
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                (
                                    t["run_id"], t["instrument_id"], t["family"], t["threshold_percent"],
                                    t["checkpoint"], t["session_date"], t["sequence_number"],
                                    t["from_state"], t["to_state"], t["reason"], now,
                                )
                                for t in transitions
                            ],
                        )

                    conn.execute(
                        """
                        UPDATE emr_scan_runs SET
                            status='COMPLETE', finished_ts=?, eligible_count=?, ineligible_count=?,
                            evidence_generation_duration_ms=?, quote_capture_duration_ms=?,
                            inference_duration_ms=?, total_duration_ms=?, quote_request_count=?,
                            db_read_latency_ms=?
                        WHERE run_id=?
                        """,
                        (
                            run_update["finished_ts"], run_update.get("eligible_count"),
                            run_update.get("ineligible_count"), run_update.get("evidence_generation_duration_ms"),
                            run_update.get("quote_capture_duration_ms"), run_update.get("inference_duration_ms"),
                            run_update.get("total_duration_ms"), run_update.get("quote_request_count"),
                            run_update.get("db_read_latency_ms"), run_id,
                        ),
                    )
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot commit EM-5 scan result: {exc}") from exc

    def mark_scan_failed(
        self, *, run_id: str, failure_type: str, failure_reason: str, finished_ts: str,
    ) -> None:
        """Best-effort terminal `FAILED` write -- its own single
        transaction, deliberately separate from `commit_scan_result`
        (a failure here must never be allowed to replace the real scan
        exception as the caller's primary error; see `run_scan_cycle`'s
        own exception-chaining contract). `failure_reason` is truncated
        to a bounded length -- never an unbounded traceback, never
        secrets/tokens/headers/provider payloads; callers are responsible
        for passing only a short, safe diagnostic string."""
        bounded_reason = failure_reason[:_MAX_FAILURE_REASON_LENGTH]
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    cur = conn.execute(
                        "UPDATE emr_scan_runs SET status='FAILED', finished_ts=?, "
                        "failure_type=?, failure_reason=? WHERE run_id=? AND status='RUNNING'",
                        (finished_ts, failure_type, bounded_reason, run_id),
                    )
                    if cur.rowcount == 0:
                        raise RepositoryError(
                            f"cannot mark EM-5 scan run {run_id!r} FAILED: no RUNNING row found"
                        )
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot mark EM-5 scan run failed: {exc}") from exc

    def list_transitions_for_run(self, *, run_id: str) -> list[dict]:
        """All transitions persisted for one run -- used to reconstruct a
        `ScanCycleResult` for an already-`COMPLETE` run without
        recomputing or re-calling any provider (EM-7A.1 idempotent-replay
        contract)."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT run_id, instrument_id, family, threshold_percent, checkpoint, session_date, "
            "sequence_number, from_state, to_state, reason, created_ts "
            "FROM emr_transitions WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        cols = (
            "run_id", "instrument_id", "family", "threshold_percent", "checkpoint", "session_date",
            "sequence_number", "from_state", "to_state", "reason", "created_ts",
        )
        return [dict(zip(cols, row, strict=True)) for row in rows]

    # ------------------------------------------------------------------ #
    # Candidates
    # ------------------------------------------------------------------ #

    def save_candidates(self, candidates: list[dict]) -> None:
        if not candidates:
            return
        now = datetime.now(tz=UTC).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.executemany(
                        """
                        INSERT INTO emr_candidates (
                            run_id, instrument_id, family, threshold_percent, checkpoint, session_date,
                            rank, raw_logit, raw_logistic_estimate, deterministic_score, calibrated_probability,
                            probability_language, em4b_model_version, em4d_calibration_version,
                            checkpoint_price, checkpoint_price_semantic, checkpoint_snapshot_timestamp,
                            checkpoint_last_trade_time, checkpoint_price_latency_seconds,
                            evidence_timestamp, evidence_completeness_known, evidence_completeness_total,
                            freshness, feasibility, feasibility_reason, state, state_reason,
                            logit_contributions_json, created_ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                c["run_id"], c["instrument_id"], c["family"], c["threshold_percent"],
                                c["checkpoint"], c["session_date"], c.get("rank"), c.get("raw_logit"),
                                c["raw_logistic_estimate"], c.get("deterministic_score"),
                                c.get("calibrated_probability"), c["probability_language"],
                                c["em4b_model_version"], c["em4d_calibration_version"],
                                str(c["checkpoint_price"]) if c.get("checkpoint_price") is not None else None,
                                c.get("checkpoint_price_semantic"), c.get("checkpoint_snapshot_timestamp"),
                                c.get("checkpoint_last_trade_time"), c.get("checkpoint_price_latency_seconds"),
                                c["evidence_timestamp"], c["evidence_completeness_known"],
                                c["evidence_completeness_total"], c["freshness"], c["feasibility"],
                                c.get("feasibility_reason"), c["state"], c["state_reason"],
                                json.dumps(c.get("logit_contributions", {}), sort_keys=True), now,
                            )
                            for c in candidates
                        ],
                    )
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot save EM-5 candidates: {exc}") from exc

    def list_candidates(self, *, run_id: str) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT instrument_id, family, threshold_percent, checkpoint, session_date, rank, raw_logit, "
            "raw_logistic_estimate, deterministic_score, calibrated_probability, probability_language, "
            "em4b_model_version, em4d_calibration_version, checkpoint_price, checkpoint_price_semantic, "
            "checkpoint_snapshot_timestamp, checkpoint_last_trade_time, checkpoint_price_latency_seconds, "
            "evidence_timestamp, evidence_completeness_known, evidence_completeness_total, freshness, "
            "feasibility, feasibility_reason, state, state_reason, logit_contributions_json "
            "FROM emr_candidates WHERE run_id = ? ORDER BY family, threshold_percent, rank",
            (run_id,),
        ).fetchall()
        cols = (
            "instrument_id", "family", "threshold_percent", "checkpoint", "session_date", "rank", "raw_logit",
            "raw_logistic_estimate", "deterministic_score", "calibrated_probability", "probability_language",
            "em4b_model_version", "em4d_calibration_version", "checkpoint_price", "checkpoint_price_semantic",
            "checkpoint_snapshot_timestamp", "checkpoint_last_trade_time", "checkpoint_price_latency_seconds",
            "evidence_timestamp", "evidence_completeness_known", "evidence_completeness_total", "freshness",
            "feasibility", "feasibility_reason", "state", "state_reason",
        )
        results = []
        for row in rows:
            record = dict(zip(cols, row[:-1], strict=True))
            record["logit_contributions"] = json.loads(row[-1]) if row[-1] else {}
            results.append(record)
        return results

    def list_candidates_for_symbol(
        self, *, instrument_id: str, family: str, threshold_percent: int, session_date: str,
    ) -> list[dict]:
        """One symbol's candidate history across every checkpoint/run this
        session -- what `determine_next_state` needs to derive `prior_rank`
        from the immediately preceding checkpoint, using the
        `idx_emr_candidates_instrument` index the schema already carries
        for exactly this lookup."""

        conn = self._connect()
        rows = conn.execute(
            "SELECT run_id, checkpoint, rank, raw_logit, raw_logistic_estimate, deterministic_score, "
            "calibrated_probability, probability_language, em4b_model_version, em4d_calibration_version, "
            "checkpoint_price, checkpoint_price_semantic, checkpoint_snapshot_timestamp, "
            "checkpoint_last_trade_time, checkpoint_price_latency_seconds, evidence_timestamp, "
            "evidence_completeness_known, evidence_completeness_total, freshness, feasibility, "
            "feasibility_reason, state, state_reason, created_ts, logit_contributions_json "
            "FROM emr_candidates WHERE instrument_id = ? AND family = ? AND threshold_percent = ? "
            "AND session_date = ? ORDER BY created_ts",
            (instrument_id, family, threshold_percent, session_date),
        ).fetchall()
        cols = (
            "run_id", "checkpoint", "rank", "raw_logit", "raw_logistic_estimate", "deterministic_score",
            "calibrated_probability", "probability_language", "em4b_model_version", "em4d_calibration_version",
            "checkpoint_price", "checkpoint_price_semantic", "checkpoint_snapshot_timestamp",
            "checkpoint_last_trade_time", "checkpoint_price_latency_seconds", "evidence_timestamp",
            "evidence_completeness_known", "evidence_completeness_total", "freshness", "feasibility",
            "feasibility_reason", "state", "state_reason", "created_ts",
        )
        results = []
        for row in rows:
            record = dict(zip(cols, row[:-1], strict=True))
            record["logit_contributions"] = json.loads(row[-1]) if row[-1] else {}
            results.append(record)
        return results

    # ------------------------------------------------------------------ #
    # State transitions
    # ------------------------------------------------------------------ #

    def save_transitions(self, transitions: list[dict]) -> None:
        if not transitions:
            return
        now = datetime.now(tz=UTC).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    conn.executemany(
                        """
                        INSERT INTO emr_transitions (
                            run_id, instrument_id, family, threshold_percent, checkpoint, session_date,
                            sequence_number, from_state, to_state, reason, created_ts
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                t["run_id"], t["instrument_id"], t["family"], t["threshold_percent"],
                                t["checkpoint"], t["session_date"], t["sequence_number"],
                                t["from_state"], t["to_state"], t["reason"], now,
                            )
                            for t in transitions
                        ],
                    )
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot save EM-5 transitions: {exc}") from exc

    def list_transitions(
        self, *, instrument_id: str, family: str, threshold_percent: int, session_date: str,
    ) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT run_id, checkpoint, sequence_number, from_state, to_state, reason, created_ts "
            "FROM emr_transitions WHERE instrument_id = ? AND family = ? AND threshold_percent = ? "
            "AND session_date = ? ORDER BY sequence_number",
            (instrument_id, family, threshold_percent, session_date),
        ).fetchall()
        cols = ("run_id", "checkpoint", "sequence_number", "from_state", "to_state", "reason", "created_ts")
        return [dict(zip(cols, row, strict=True)) for row in rows]
