"""DarvaX's own SQLite schema, versioned independently of ATHENA (ADR-010 §2).

DarvaX keeps its own database file (``db/darvax.db``). ATHENA's
``SCHEMA_VERSION``, ``ddl_statements()``, ``record_counts()``, backup, restore,
and integrity checks remain untouched and unaware of anything here — which is
what makes "delete DarvaX" a clean, complete operation.

Version history:

* **1** (DX-1) — version table only; no artifacts existed yet.
* **2** (DX-3) — ``darvax_signals``, the first DarvaX artifact table.
* **3** (DX-6a) — ``darvax_sweeps`` and ``darvax_screen_results``, the screener's
  own artifacts (ADR-010 Amendment 2).
* **4** (DX-6b) — ``distance_to_breakout_pct`` and ``breakout_reference`` on
  ``darvax_screen_results``. Added after a live 528-instrument sweep showed the
  WATCH tier ordered alphabetically: DX-3 sets ``trigger_price`` only alongside
  a stop, so no inside-the-box signal had one to rank on.

``darvax_signals`` stores each signal's **computed explanation and evidence as
data** (ADR-005's principle applied inside the satellite), so the DX-4 surface
renders what the engine concluded rather than re-deriving it. ``methodology_digest``
records which config produced the row, keeping signals replayable.

``darvax_screen_results`` follows the same principle for the screener: the tier
and every ranking quantity are computed once and persisted, so the API
serialises and the UI renders — neither ever re-derives an eligibility. A sweep
is recorded as its own row rather than inferred from a pile of results, so a
screen can be reproduced and audited: ``methodology_digest`` is captured per
sweep because changing any methodology value changes it, and an old screen must
never appear to have been produced by current settings.
"""

from __future__ import annotations

#: Bumped independently of ATHENA's SCHEMA_VERSION. They never interact.
DARVAX_SCHEMA_VERSION = 10

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
    # ------------------------------------------------------------ DX-6a
    """
    CREATE TABLE IF NOT EXISTS darvax_sweeps (
        sweep_id            TEXT PRIMARY KEY,
        started_at          TEXT NOT NULL,
        finished_at         TEXT,
        state               TEXT NOT NULL,
        as_of               TEXT,
        methodology_digest  TEXT NOT NULL,
        darvax_version      TEXT NOT NULL,
        requested           INTEGER NOT NULL,
        evaluated           INTEGER NOT NULL,
        skipped_json        TEXT NOT NULL,
        tier_counts_json    TEXT NOT NULL,
        partial             INTEGER NOT NULL
    )
    """,
    # Sweep history is listed newest-first; this is also the index a retention
    # policy would prune against once one is decided (design §10 Q3).
    "CREATE INDEX IF NOT EXISTS idx_darvax_sweeps_started "
    "ON darvax_sweeps(started_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS darvax_screen_results (
        sweep_id                TEXT NOT NULL,
        instrument_id           TEXT NOT NULL,
        signal_id               TEXT NOT NULL,
        tier                    TEXT NOT NULL,
        signal_type             TEXT NOT NULL,
        darvas_rule             TEXT,
        rank                    INTEGER NOT NULL,
        close                   TEXT NOT NULL,
        box_top                 TEXT,
        box_bottom              TEXT,
        trigger_price           TEXT,
        distance_to_trigger_pct TEXT,
        distance_to_breakout_pct TEXT,
        breakout_reference      TEXT,
        box_height_pct          TEXT,
        explanation             TEXT NOT NULL,
        action                  TEXT,
        action_reason           TEXT,
        action_reason_plain     TEXT,
        stop_price              TEXT,
        stop_basis              TEXT,
        stop_vs_ceiling         TEXT,
        stop_vs_ceiling_note    TEXT,
        liquidity_value         TEXT,
        ema_50                  TEXT,
        ema_100                 TEXT,
        PRIMARY KEY (sweep_id, instrument_id)
    )
    """,
    # The screener's only read pattern: one sweep, one tier, in rank order.
    "CREATE INDEX IF NOT EXISTS idx_darvax_screen_sweep_tier_rank "
    "ON darvax_screen_results(sweep_id, tier, rank)",
    """
    CREATE TABLE IF NOT EXISTS darvax_positions (
        position_id         TEXT PRIMARY KEY,
        instrument_id       TEXT NOT NULL,
        quantity            INTEGER NOT NULL,
        entry_price         TEXT NOT NULL,
        entry_date          TEXT NOT NULL,
        opened_at           TEXT NOT NULL,
        stop_price          TEXT,
        stop_basis          TEXT,
        methodology_digest  TEXT NOT NULL DEFAULT '',
        closed_at           TEXT,
        note                TEXT NOT NULL DEFAULT ''
    )
    """,
    # At most one OPEN position per instrument. A partial unique index rather
    # than an application check: two open rows for one symbol would make "am I
    # holding this?" ambiguous, and the advisor answers that question on every
    # sweep. Closed rows are unconstrained so re-entering a name keeps history.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_darvax_positions_one_open "
    "ON darvax_positions(instrument_id) WHERE closed_at IS NULL",
)


#: Columns added to an existing table after its CREATE shipped. ``CREATE TABLE
#: IF NOT EXISTS`` cannot add a column to a table that already exists, so these
#: are applied with ALTER, guarded by a "does it already have it" check.
#: Additive only — no migration here drops or rewrites a column, so a downgrade
#: leaves data readable rather than destroyed.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("darvax_screen_results", "distance_to_breakout_pct", "TEXT"),
    ("darvax_screen_results", "breakout_reference", "TEXT"),
    # DX-7a. Nullable on purpose: sweeps stored before DX-7a have no action, and
    # backfilling one would invent advice for a screen nobody ran under these
    # rules. A reader must see "not recorded", not a plausible guess.
    ("darvax_screen_results", "action", "TEXT"),
    ("darvax_screen_results", "action_reason", "TEXT"),
    # DX-8a. The stop is what makes an entry survivable and the screener could
    # not show one; the plain reason is what makes the advice readable.
    ("darvax_screen_results", "action_reason_plain", "TEXT"),
    ("darvax_screen_results", "stop_price", "TEXT"),
    ("darvax_screen_results", "stop_basis", "TEXT"),
    # DX-9c. Where the stop lands relative to the breakout level — the same 10%
    # rule falls on either side of it, which is a materially different trade.
    ("darvax_screen_results", "stop_vs_ceiling", "TEXT"),
    ("darvax_screen_results", "stop_vs_ceiling_note", "TEXT"),
    # DX-10a. Liquidity stands in for market cap, which ATHENA has no data for.
    ("darvax_screen_results", "liquidity_value", "TEXT"),
    # DX-12a. Trend context — not a DAR-CARD rule, the owner asked for it
    # directly. Independent columns: a symbol may have enough history for one
    # EMA period and not the other.
    ("darvax_screen_results", "ema_50", "TEXT"),
    ("darvax_screen_results", "ema_100", "TEXT"),
)


def darvax_ddl_statements() -> tuple[str, ...]:
    return _DDL


def darvax_added_columns() -> tuple[tuple[str, str, str], ...]:
    """``(table, column, type)`` triples to ALTER in when upgrading in place."""
    return _ADDED_COLUMNS
