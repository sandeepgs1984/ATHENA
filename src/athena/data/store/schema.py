"""SQLite schema for the ATHENA repository (M1.5).

Follows ATHENA-002 §5: one ``candles`` table keyed by (instrument_id, timeframe,
ts_open) serves both daily and intraday data. Adds ``quotes`` and
``quarantine_records`` (persistence for M1.3 results). Prices/decimals are stored
as TEXT to preserve exact Decimal precision (no float drift). History tables are
append-only by discipline (inserts only; duplicates rejected by primary key).
"""

from __future__ import annotations

#: Bump when the schema changes; enables future explicit migrations.
SCHEMA_VERSION = 2

_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)",

    """
    CREATE TABLE IF NOT EXISTS instruments (
        instrument_id TEXT PRIMARY KEY,
        isin          TEXT,
        symbol        TEXT NOT NULL,
        exchange      TEXT NOT NULL,
        series        TEXT NOT NULL,
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
)


def ddl_statements() -> tuple[str, ...]:
    """The ordered DDL statements that build the schema (idempotent)."""
    return _DDL
