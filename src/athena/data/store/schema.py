"""SQLite schema for the ATHENA repository (M1.5).

Follows ATHENA-002 §5: one ``candles`` table keyed by (instrument_id, timeframe,
ts_open) serves both daily and intraday data. Adds ``quotes`` and
``quarantine_records`` (persistence for M1.3 results). Prices/decimals are stored
as TEXT to preserve exact Decimal precision (no float drift). History tables are
append-only by discipline (inserts only; duplicates rejected by primary key).
"""

from __future__ import annotations

#: Bump when the schema changes; enables future explicit migrations.
SCHEMA_VERSION = 14

_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",

    # ---------------------------------------------------------------- SU-1
    # The catalogue of what EXISTS on an exchange, kept deliberately separate
    # from `instruments`, which records what has been INGESTED. Conflating the
    # two is the defect ADR-011 exists to fix: today a symbol only "exists" to
    # ATHENA once somebody curates it into a candidate list.
    #
    # `series_source` and `classification_reason` are not decoration. The broker
    # dump types every NSE row "EQ" and ships no series column, so every series
    # here is inferred until an authoritative NSE list is obtained — and an
    # inference recorded without its provenance reads as a fact.
    """
    CREATE TABLE IF NOT EXISTS symbol_master (
        instrument_id         TEXT PRIMARY KEY,
        symbol                TEXT NOT NULL,
        exchange              TEXT NOT NULL,
        name                  TEXT,
        series                TEXT NOT NULL,
        series_source         TEXT NOT NULL,
        board                 TEXT NOT NULL,
        lot_size              INTEGER NOT NULL,
        tick_size             TEXT NOT NULL,
        status                TEXT NOT NULL,
        first_seen            TEXT NOT NULL,
        last_seen             TEXT NOT NULL,
        source                TEXT NOT NULL,
        classification_reason TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_symbol_master_series ON symbol_master(series)",
    "CREATE INDEX IF NOT EXISTS idx_symbol_master_board ON symbol_master(board)",

    # ---------------------------------------------------------------- SU-2
    # Group membership as metadata on the canonical symbol — many-to-many, and
    # deliberately NOT a duplicated symbol row per group (ADR-011 §2).
    #
    # Membership is dated because index constituents change: a screen run before
    # a rebalance must stay reproducible afterwards, which an undated membership
    # would silently break. The primary key therefore includes effective_date,
    # so a new snapshot adds rows rather than overwriting history.
    """
    CREATE TABLE IF NOT EXISTS symbol_group (
        instrument_id  TEXT NOT NULL,
        group_name     TEXT NOT NULL,
        kind           TEXT NOT NULL,
        effective_date TEXT NOT NULL,
        source         TEXT NOT NULL,
        PRIMARY KEY (instrument_id, group_name, effective_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_symbol_group_lookup "
    "ON symbol_group(group_name, effective_date DESC)",

    """
    CREATE TABLE IF NOT EXISTS instruments (
        instrument_id TEXT PRIMARY KEY,
        isin          TEXT,
        symbol        TEXT NOT NULL,
        exchange      TEXT NOT NULL,
        series        TEXT NOT NULL,
        name          TEXT,
        sector        TEXT,
        lot_size      INTEGER NOT NULL,
        tick_size     TEXT NOT NULL,
        status        TEXT NOT NULL,
        listed_date   TEXT,
        delisted_date TEXT
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS candles (
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        timeframe     TEXT NOT NULL,
        ts_open       TEXT NOT NULL,
        open          TEXT NOT NULL,
        high          TEXT NOT NULL,
        low           TEXT NOT NULL,
        close         TEXT NOT NULL,
        volume        INTEGER NOT NULL,
        source        TEXT NOT NULL,
        adjusted      INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (instrument_id, timeframe, ts_open)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_candles_range ON candles(instrument_id, timeframe, ts_open)",

    """
    CREATE TABLE IF NOT EXISTS quotes (
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        ts            TEXT NOT NULL,
        last_price    TEXT NOT NULL,
        volume        INTEGER NOT NULL,
        source        TEXT NOT NULL,
        PRIMARY KEY (instrument_id, ts)
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS market_snapshots (
        ts           TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS institutional_flows (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        session_date  TEXT NOT NULL,
        fii_buy       TEXT NOT NULL,
        fii_sell      TEXT NOT NULL,
        fii_net       TEXT NOT NULL,
        dii_buy       TEXT NOT NULL,
        dii_sell      TEXT NOT NULL,
        dii_net       TEXT NOT NULL,
        provisional   INTEGER NOT NULL,
        source_id     TEXT NOT NULL,
        fetched_at    TEXT NOT NULL,
        run_id        TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_institutional_flows_session "
    "ON institutional_flows(session_date, fetched_at)",

    """
    CREATE TABLE IF NOT EXISTS corporate_actions (
        action_id     TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        action_type   TEXT NOT NULL,
        ex_date       TEXT NOT NULL,
        details_json  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ca_instrument ON corporate_actions(instrument_id, ex_date)",

    """
    CREATE TABLE IF NOT EXISTS quarantine_records (
        dataset_id     TEXT PRIMARY KEY,
        reason         TEXT NOT NULL,
        quarantined_ts TEXT NOT NULL,
        reports_json   TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id                    TEXT PRIMARY KEY,
        cycle_id                  TEXT NOT NULL,
        trigger                   TEXT NOT NULL,
        started_ts                TEXT NOT NULL,
        finished_ts               TEXT,
        status                    TEXT NOT NULL,
        software_version          TEXT NOT NULL,
        blueprint_version         TEXT NOT NULL,
        strategy_profile          TEXT NOT NULL,
        strategy_profile_version  TEXT NOT NULL,
        indicator_versions_json   TEXT NOT NULL,
        config_snapshot_id        TEXT NOT NULL,
        input_digest              TEXT NOT NULL DEFAULT '',
        detail_json               TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_runs_trigger_started ON runs(trigger, started_ts)",
    # Perf fix (2026-08-03): list_runs(limit=N) with NO trigger filter — the
    # dashboard's pipeline-runs list, candidates/validate verdict lookups,
    # market summary, diagnostics, notifications, and
    # OwnerValidationPipeline._last_full_universe_summary() all call it this
    # way — had no usable index for `ORDER BY started_ts DESC, run_id DESC`,
    # forcing a full "SCAN runs" that materializes every row's `detail_json`
    # (individual blobs run into single-digit MB as the universe/report size
    # has grown) just to sort and take the top N. Confirmed via EXPLAIN QUERY
    # PLAN + direct timing against the real production database: ~650ms for
    # limit=50 before this index, ~8ms after (~80x) — the dominant cause of
    # the reported "symbol validation went from <10s to 50s+" regression,
    # since every one of those call sites pays this cost.
    "CREATE INDEX IF NOT EXISTS idx_runs_started_ts ON runs(started_ts DESC, run_id DESC)",

    """
    CREATE TABLE IF NOT EXISTS decisions (
        decision_id         TEXT PRIMARY KEY,
        ts                  TEXT NOT NULL,
        run_id              TEXT NOT NULL,
        cycle_id            TEXT NOT NULL,
        decision_type       TEXT NOT NULL,
        explanation         TEXT NOT NULL,
        instrument_id       TEXT,
        direction           TEXT NOT NULL,
        score_ref           TEXT,
        confidence_ref      TEXT,
        risk_ref            TEXT,
        gate_results_json   TEXT NOT NULL,
        trade_plan_json     TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts)",
    "CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id)",
    # SCHEMA_VERSION 12: list_latest_decisions_by_instrument()'s correlated
    # NOT EXISTS subquery (one "is there a newer row for this instrument"
    # check per row) had no supporting index — owner-reported (2026-08-10),
    # timed at 1.7s against 91,241 decisions. Covers both sides of that
    # correlation (the outer instrument_id/ts/decision_id and the inner
    # newer.instrument_id/ts/decision_id) in one index.
    "CREATE INDEX IF NOT EXISTS idx_decisions_instrument_ts "
    "ON decisions(instrument_id, ts, decision_id)",

    """
    CREATE TABLE IF NOT EXISTS decision_traces (
        decision_ref TEXT PRIMARY KEY REFERENCES decisions(decision_id),
        stages_json  TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS decision_journal (
        entry_id     TEXT PRIMARY KEY,
        decision_ref TEXT NOT NULL REFERENCES decisions(decision_id),
        user_action  TEXT NOT NULL,
        action_ts    TEXT NOT NULL,
        notes        TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_journal_action_ts ON decision_journal(action_ts)",

    """
    CREATE TABLE IF NOT EXISTS trade_outcomes (
        outcome_id      TEXT PRIMARY KEY,
        decision_ref    TEXT NOT NULL REFERENCES decisions(decision_id),
        entry_price     TEXT NOT NULL,
        exit_price      TEXT NOT NULL,
        quantity        INTEGER NOT NULL,
        pnl             TEXT NOT NULL,
        holding_seconds INTEGER NOT NULL,
        adherence_json  TEXT NOT NULL DEFAULT '{}',
        closed_ts       TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_decision ON trade_outcomes(decision_ref)",
    "CREATE INDEX IF NOT EXISTS idx_trade_outcomes_closed ON trade_outcomes(closed_ts)",

    """
    CREATE TABLE IF NOT EXISTS owner_positions (
        position_id   TEXT PRIMARY KEY,
        instrument_id TEXT NOT NULL,
        opened_ts     TEXT NOT NULL,
        quantity      INTEGER NOT NULL,
        avg_price     TEXT NOT NULL,
        closed_ts     TEXT,
        exit_price    TEXT,
        decision_ref  TEXT,
        broker        TEXT NOT NULL DEFAULT '',
        notes         TEXT NOT NULL DEFAULT '',
        sector        TEXT NOT NULL DEFAULT '',
        meta_json     TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_owner_positions_opened ON owner_positions(opened_ts)",
    "CREATE INDEX IF NOT EXISTS idx_owner_positions_symbol ON owner_positions(instrument_id)",

    """
    CREATE TABLE IF NOT EXISTS owner_candidates (
        symbol    TEXT PRIMARY KEY,
        added_ts  TEXT NOT NULL,
        notes     TEXT NOT NULL DEFAULT '',
        active    INTEGER NOT NULL DEFAULT 1
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_owner_candidates_active ON owner_candidates(active)",

    """
    CREATE TABLE IF NOT EXISTS saved_symbols (
        symbol    TEXT PRIMARY KEY,
        added_ts  TEXT NOT NULL,
        notes     TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_saved_symbols_added_ts ON saved_symbols(added_ts)",

    """
    CREATE TABLE IF NOT EXISTS ops_meta (
        key         TEXT PRIMARY KEY,
        value       TEXT NOT NULL,
        updated_ts  TEXT NOT NULL
    )
    """,
)


def ddl_statements() -> tuple[str, ...]:
    """The ordered DDL statements that build the schema (idempotent)."""
    return _DDL
