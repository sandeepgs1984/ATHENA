"""EM-5's own SQLite schema, versioned independently of ATHENA (ADR-012
Section 3, mirroring DarvaX's own established pattern -- ADR-010 Section
2). EM-5 keeps its own database file (``db/emr.db``). ATHENA's
``SCHEMA_VERSION``, ``ddl_statements()``, backup, restore, and integrity
checks remain untouched and unaware of anything here.

Version history:

* **1** (EM-5) -- version table, ``emr_scan_runs`` (one row per scan
  cycle), ``emr_candidates`` (one row per scored/ranked observation),
  ``emr_transitions`` (the state machine's immutable event log).

Every persisted candidate records enough to explain itself and to be
replayed without a live call: the frozen model/calibration versions it
used, the checkpoint reference-price observation it scored (per the
Owner's amendment -- ``FIRST_OBSERVED_POST_CHECKPOINT_TRADE``, with
``snapshot_timestamp`` and ``last_trade_time`` kept separate, never
conflated), and its own evidence-completeness/feasibility/state.
"""

from __future__ import annotations

#: Bumped independently of ATHENA's SCHEMA_VERSION. They never interact.
EMR_SCHEMA_VERSION = 1

_DDL: tuple[str, ...] = (
    "CREATE TABLE IF NOT EXISTS emr_schema_version (version INTEGER NOT NULL)",
    """
    CREATE TABLE IF NOT EXISTS emr_scan_runs (
        run_id                          TEXT PRIMARY KEY,
        session_date                    TEXT NOT NULL,
        checkpoint                      TEXT NOT NULL,
        frozen_model_version             TEXT NOT NULL,
        status                          TEXT NOT NULL,
        started_ts                      TEXT NOT NULL,
        finished_ts                     TEXT,
        eligible_count                  INTEGER,
        ineligible_count                INTEGER,
        evidence_generation_duration_ms  REAL,
        quote_capture_duration_ms        REAL,
        inference_duration_ms            REAL,
        total_duration_ms                REAL,
        quote_request_count             INTEGER,
        db_read_latency_ms               REAL,
        detail_json                     TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emr_scan_runs_session_checkpoint ON emr_scan_runs(session_date, checkpoint)",
    """
    CREATE TABLE IF NOT EXISTS emr_candidates (
        id                               INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id                          TEXT NOT NULL,
        instrument_id                   TEXT NOT NULL,
        family                          TEXT NOT NULL,
        threshold_percent               INTEGER NOT NULL,
        checkpoint                      TEXT NOT NULL,
        session_date                    TEXT NOT NULL,
        rank                            INTEGER,
        raw_logit                       REAL,
        raw_logistic_estimate           REAL NOT NULL,
        deterministic_score              REAL,
        calibrated_probability           REAL,
        probability_language            TEXT NOT NULL,
        em4b_model_version                TEXT NOT NULL,
        em4d_calibration_version          TEXT NOT NULL,
        checkpoint_price                 TEXT,
        checkpoint_price_semantic        TEXT,
        checkpoint_snapshot_timestamp     TEXT,
        checkpoint_last_trade_time        TEXT,
        checkpoint_price_latency_seconds  REAL,
        evidence_timestamp               TEXT NOT NULL,
        evidence_completeness_known       INTEGER NOT NULL,
        evidence_completeness_total       INTEGER NOT NULL,
        freshness                       TEXT NOT NULL,
        feasibility                     TEXT NOT NULL,
        feasibility_reason              TEXT,
        state                           TEXT NOT NULL,
        state_reason                    TEXT NOT NULL,
        logit_contributions_json         TEXT,
        created_ts                      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emr_candidates_run ON emr_candidates(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_emr_candidates_instrument "
    "ON emr_candidates(instrument_id, family, threshold_percent)",
    """
    CREATE TABLE IF NOT EXISTS emr_transitions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id              TEXT NOT NULL,
        instrument_id       TEXT NOT NULL,
        family              TEXT NOT NULL,
        threshold_percent   INTEGER NOT NULL,
        checkpoint          TEXT NOT NULL,
        session_date        TEXT NOT NULL,
        sequence_number     INTEGER NOT NULL,
        from_state          TEXT NOT NULL,
        to_state            TEXT NOT NULL,
        reason              TEXT NOT NULL,
        created_ts          TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emr_transitions_instrument "
    "ON emr_transitions(instrument_id, family, threshold_percent, session_date)",
)


def ddl_statements() -> tuple[str, ...]:
    return _DDL
