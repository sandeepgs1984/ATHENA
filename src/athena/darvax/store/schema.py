"""DarvaX's own SQLite schema, versioned independently of ATHENA (ADR-010 §2).

DarvaX keeps its own database file (``db/darvax.db``). ATHENA's
``SCHEMA_VERSION``, ``ddl_statements()``, ``record_counts()``, backup, restore,
and integrity checks remain untouched and unaware of anything here — which is
what makes "delete DarvaX" a clean, complete operation.

Version history:

* **1** (DX-1) — version table only; no artifacts existed yet.
* **2** (DX-3) — ``darvax_signals``, the first DarvaX artifact table.

``darvax_signals`` stores each signal's **computed explanation and evidence as
data** (ADR-005's principle applied inside the satellite), so the DX-4 surface
renders what the engine concluded rather than re-deriving it. ``methodology_digest``
records which config produced the row, keeping signals replayable.
"""

from __future__ import annotations

#: Bumped independently of ATHENA's SCHEMA_VERSION. They never interact.
DARVAX_SCHEMA_VERSION = 2

_DDL: tuple[str, ...] = (
    "CREATE TABLE IF NOT EXISTS darvax_schema_version (version INTEGER NOT NULL)",
    """
    CREATE TABLE IF NOT EXISTS darvax_signals (
        signal_id           TEXT PRIMARY KEY,
        instrument_id       TEXT NOT NULL,
        as_of               TEXT NOT NULL,
        signal_type         TEXT NOT NULL,
        darvas_rule         TEXT,
        close               TEXT NOT NULL,
        box_top             TEXT,
        box_bottom          TEXT,
        box_is_topmost      INTEGER,
        trigger_price       TEXT,
        stop_json           TEXT,
        explanation         TEXT NOT NULL,
        evidence_json       TEXT NOT NULL,
        methodology_digest  TEXT NOT NULL,
        darvax_version      TEXT NOT NULL,
        status              TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_darvax_signals_instrument_as_of "
    "ON darvax_signals(instrument_id, as_of DESC)",
    "CREATE INDEX IF NOT EXISTS idx_darvax_signals_as_of "
    "ON darvax_signals(as_of DESC)",
)


def darvax_ddl_statements() -> tuple[str, ...]:
    return _DDL
