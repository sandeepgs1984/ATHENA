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
from athena.explosive_move.store.schema import EMR_SCHEMA_VERSION, ddl_statements


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
        """Create EM-5's schema (idempotent) and record its own version."""
        with self._lock:
            conn = self._connect()
            try:
                with conn:
                    for statement in ddl_statements():
                        conn.execute(statement)
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
                            db_read_latency_ms, detail_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(run_id) DO UPDATE SET
                            status=excluded.status, finished_ts=excluded.finished_ts,
                            eligible_count=excluded.eligible_count, ineligible_count=excluded.ineligible_count,
                            evidence_generation_duration_ms=excluded.evidence_generation_duration_ms,
                            quote_capture_duration_ms=excluded.quote_capture_duration_ms,
                            inference_duration_ms=excluded.inference_duration_ms,
                            total_duration_ms=excluded.total_duration_ms,
                            quote_request_count=excluded.quote_request_count,
                            db_read_latency_ms=excluded.db_read_latency_ms,
                            detail_json=excluded.detail_json
                        """,
                        (
                            run["run_id"], run["session_date"], run["checkpoint"], run["frozen_model_version"],
                            run["status"], run["started_ts"], run.get("finished_ts"),
                            run.get("eligible_count"), run.get("ineligible_count"),
                            run.get("evidence_generation_duration_ms"), run.get("quote_capture_duration_ms"),
                            run.get("inference_duration_ms"), run.get("total_duration_ms"),
                            run.get("quote_request_count"), run.get("db_read_latency_ms"),
                            json.dumps(run.get("detail", {}), sort_keys=True),
                        ),
                    )
            except sqlite3.Error as exc:
                raise RepositoryError(f"cannot save EM-5 scan run: {exc}") from exc

    def get_scan_run(self, run_id: str) -> dict | None:
        conn = self._connect()
        row = conn.execute(
            "SELECT run_id, session_date, checkpoint, frozen_model_version, status, started_ts, finished_ts, "
            "eligible_count, ineligible_count, evidence_generation_duration_ms, quote_capture_duration_ms, "
            "inference_duration_ms, total_duration_ms, quote_request_count, db_read_latency_ms, detail_json "
            "FROM emr_scan_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        cols = (
            "run_id", "session_date", "checkpoint", "frozen_model_version", "status", "started_ts", "finished_ts",
            "eligible_count", "ineligible_count", "evidence_generation_duration_ms", "quote_capture_duration_ms",
            "inference_duration_ms", "total_duration_ms", "quote_request_count", "db_read_latency_ms",
        )
        result = dict(zip(cols, row[:-1], strict=True))
        result["detail"] = json.loads(row[-1]) if row[-1] else {}
        return result

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
