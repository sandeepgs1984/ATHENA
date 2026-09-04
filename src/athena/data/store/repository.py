"""SqliteRepository — ATHENA's persistent ledger (M1.5).

Persistence is its ONLY responsibility. It contains no provider, validation, or
market-intelligence logic; it stores and returns canonical domain objects with
transaction safety, WAL mode, and enforced foreign keys.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import ClassVar

from athena.data.store import serialization as ser
from athena.data.store.schema import SCHEMA_VERSION, ddl_statements
from athena.data.validation.quarantine import QuarantineRecord
from athena.domain.decision import (
    Decision,
    DecisionJournalEntry,
    DecisionTrace,
    Position,
    TradeOutcome,
)
from athena.domain.enums import Timeframe
from athena.domain.market import (
    Candle,
    CorporateAction,
    InstitutionalFlowSession,
    Instrument,
    MarketSnapshot,
    Quote,
)
from athena.domain.run import RunRecord
from athena.errors import RepositoryError
from athena.intraday.entry_actionability_models import EntryActionability
from athena.intraday.entry_qualification_models import EntryQualification
from athena.portfolio.my_portfolio_contracts import (
    CanonicalPortfolioHolding,
    ImportStatus,
    ReconciliationAction,
    ReconciliationChange,
    SymbolMappingState,
    SyncRunStatus,
    reconcile_current_holdings,
)
from athena.symbols.groups import GroupMembership
from athena.symbols.models import Board, SeriesSource, SymbolRecord


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Result of a repository integrity verification. Immutable and explainable."""

    ok: bool
    integrity_check: str
    foreign_key_violations: int
    schema_version_ok: bool
    issues: tuple[str, ...] = ()



def _entry_qualification_payload(eq: EntryQualification) -> tuple:
    """The methodology-relevant subset of an EntryQualification used to
    detect a genuine conflict at the same logical (instrument/session/
    as_of/decision/methodology) identity. Excludes ``run_id``/``cycle_id``
    NOT because they may legitimately differ across writes to the same
    identity, but because ``save_entry_qualification`` (ID-6C.1) already
    validates them against the referenced canonical Decision via
    ``_validate_entry_qualification_decision_binding`` before this
    comparison ever runs — by the time two rows reach here, both are
    already independently proven to agree with the same Decision's
    run_id/cycle_id, so comparing them again would be redundant, not
    permissive."""
    return (
        eq.decision_type,
        eq.state,
        eq.evidence_finality,
        eq.confirmation,
        eq.reason_codes,
        eq.evidence_refs,
        eq.config_snapshot_id,
        eq.explanation,
    )


def _validate_entry_qualification_decision_binding(
    eq: EntryQualification, decision: Decision
) -> None:
    """Prove ``eq`` truthfully describes the canonical ``decision`` it
    claims to bind to (ID-6C.1) — a foreign key on ``decision_id`` alone
    only proves the Decision *exists*, not that ``eq``'s Decision-derived
    fields (``decision_type``, ``run_id``, ``cycle_id``, and, when the
    Decision specifies one, ``instrument_id``) actually agree with it.

    Mirrors ``EntryQualificationEngine``'s own established contract
    exactly (`athena.intraday.entry_qualification_engine._resolve_instrument_id`):
    when ``decision.instrument_id`` is ``None``, the engine falls back to
    another source instead of comparing — so persistence applies no
    instrument constraint in that case either, rather than inventing a new
    rule. In practice, the real production ``DecisionEngine`` always sets
    ``instrument_id`` for WATCH/TRADE Decisions
    (`src/athena/decision/engine.py`), so this ``None`` branch is a
    defensive completeness path for the generic ``Decision`` contract, not
    an exercised real path.

    Does NOT decide whether ``decision`` is still the current/
    non-superseded Decision for its instrument — that remains a
    caller/workflow responsibility (ID-6D), unchanged from ID-6B.2A.
    """
    if eq.decision_type != decision.decision_type:
        raise RepositoryError(
            "EntryQualification decision binding mismatch: decision_type "
            f"(EntryQualification={eq.decision_type.value!r}, "
            f"Decision={decision.decision_type.value!r})"
        )
    if eq.run_id != decision.run_id:
        raise RepositoryError(
            "EntryQualification decision binding mismatch: run_id "
            f"(EntryQualification={eq.run_id!r}, Decision={decision.run_id!r})"
        )
    if eq.cycle_id != decision.cycle_id:
        raise RepositoryError(
            "EntryQualification decision binding mismatch: cycle_id "
            f"(EntryQualification={eq.cycle_id!r}, Decision={decision.cycle_id!r})"
        )
    if decision.instrument_id is not None and eq.instrument_id != decision.instrument_id:
        raise RepositoryError(
            "EntryQualification decision binding mismatch: instrument_id "
            f"(EntryQualification={eq.instrument_id!r}, "
            f"Decision={decision.instrument_id!r})"
        )


def _entry_actionability_payload(ea: EntryActionability) -> tuple:
    """The methodology-relevant subset of an EntryActionability used to
    detect a genuine conflict at the same logical identity (mirrors
    ``_entry_qualification_payload``'s own rationale exactly). Excludes
    ``run_id``/``cycle_id`` for the identical reason (already proven
    against the canonical Decision by
    ``_validate_entry_actionability_decision_binding`` before this
    comparison ever runs), and additionally excludes ``evaluated_at`` —
    that field is documented on ``EntryActionability`` itself as
    diagnostic wall-clock-only, never identity, never a substitute for
    ``evidence_as_of``; a deterministic re-evaluation that reaches the
    identical methodology conclusion at a different wall-clock instant is
    still the same logical observation, not a conflict."""
    return (
        ea.decision_type,
        ea.direction,
        ea.entry_qualification_state,
        ea.state,
        ea.reason_codes,
        ea.evidence_finality,
        ea.evidence_as_of,
        ea.entry_reference,
        ea.entry_location_context,
        ea.operative_invalidation,
        ea.reward,
        ea.opening_range_context,
        ea.explanation,
    )


def _validate_entry_actionability_decision_binding(
    ea: EntryActionability, decision: Decision
) -> None:
    """Prove ``ea`` truthfully describes the canonical ``decision`` it
    claims to bind to — mirrors
    ``_validate_entry_qualification_decision_binding`` exactly (ID-7A
    reuses EQ's own established persistence pattern rather than
    inventing a new one). A foreign key on ``decision_id`` alone only
    proves the Decision exists, not that ``ea``'s Decision-derived fields
    actually agree with it.
    """
    if ea.decision_type != decision.decision_type:
        raise RepositoryError(
            "EntryActionability decision binding mismatch: decision_type "
            f"(EntryActionability={ea.decision_type.value!r}, "
            f"Decision={decision.decision_type.value!r})"
        )
    if ea.run_id != decision.run_id:
        raise RepositoryError(
            "EntryActionability decision binding mismatch: run_id "
            f"(EntryActionability={ea.run_id!r}, Decision={decision.run_id!r})"
        )
    if ea.cycle_id != decision.cycle_id:
        raise RepositoryError(
            "EntryActionability decision binding mismatch: cycle_id "
            f"(EntryActionability={ea.cycle_id!r}, Decision={decision.cycle_id!r})"
        )
    if decision.instrument_id is not None and ea.instrument_id != decision.instrument_id:
        raise RepositoryError(
            "EntryActionability decision binding mismatch: instrument_id "
            f"(EntryActionability={ea.instrument_id!r}, "
            f"Decision={decision.instrument_id!r})"
        )


def _validate_entry_actionability_eq_binding(
    ea: EntryActionability, eq: EntryQualification
) -> None:
    """Prove ``ea`` truthfully describes the exact upstream
    ``EntryQualification`` observation it claims to bind to. The full EQ
    composite identity (``instrument_id, session_date,
    entry_qualification_as_of, decision_id,
    entry_qualification_methodology_version``) has already been used to
    look ``eq`` up by the time this runs (a lookup miss is reported
    separately, before this is called) — this additionally proves the
    denormalized fields ``ea`` carries about that EQ observation
    (``entry_qualification_state``) actually agree with it, exactly
    mirroring the Decision-binding check's own rationale: a single-column
    reference only proves existence, never truthful description.
    """
    if ea.entry_qualification_state != eq.state:
        raise RepositoryError(
            "EntryActionability EntryQualification binding mismatch: "
            f"entry_qualification_state (EntryActionability="
            f"{ea.entry_qualification_state.value!r}, EntryQualification="
            f"{eq.state.value!r})"
        )


def _row_to_symbol_record(row: tuple) -> SymbolRecord:
    """Rehydrate a canonical symbol. The classification and its provenance are
    read back as stored — never re-inferred here, so a record always reports the
    reasoning that actually produced it (ADR-005's principle)."""
    return SymbolRecord(
        instrument_id=row[0],
        symbol=row[1],
        exchange=row[2],
        name=row[3],
        series=row[4],
        series_source=SeriesSource(row[5]),
        board=Board(row[6]),
        lot_size=int(row[7]),
        tick_size=Decimal(row[8]),
        status=row[9],
        first_seen=datetime.fromisoformat(row[10]),
        last_seen=datetime.fromisoformat(row[11]),
        source=row[12],
        classification_reason=row[13],
    )


class SqliteRepository:
    """A trusted local ledger over a single SQLite file.

    The write connection is created with ``check_same_thread=False`` so
    FastAPI (and other multi-threaded callers) may share one repository
    instance; all writes are serialized through an ``RLock`` because a
    sqlite3 connection is not otherwise thread-safe. This class's own
    persisted schema uses ``journal_mode=WAL`` (ADR-009), which normally
    allows readers and writers to proceed concurrently and allows multiple
    readers to proceed concurrently with each other. Reads (``_query_one``/
    ``_query_all``) do not share the write connection/lock: each thread that
    performs a read lazily opens and reuses its own dedicated read-only
    connection (``mode=ro``, via ``threading.local()``), so concurrent reads
    are not serialized against each other or against an in-flight write.
    See ADR-009 (``docs/adr/ADR-009-repository-read-concurrency.md``) for the
    full rationale, the read-connection lifecycle, and its stated limits.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        # ADR-009: each thread's own lazily-created, read-only connection.
        # threading.local() already guarantees one thread never sees another
        # thread's `.conn` — see close_read_connection() for the cleanup
        # this pairs with.
        self._read_local = threading.local()
        try:
            # check_same_thread=False: API process opens repo at startup, then
            # request threads reuse it. Write access is still serialized via
            # _lock; reads use their own per-thread connection (ADR-009).
            self._conn = sqlite3.connect(
                self._path,
                isolation_level="DEFERRED",
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as exc:
            raise RepositoryError(f"cannot open database at {self._path}: {exc}") from exc

    # ------------------------------------------------------------- lifecycle

    def initialize(self) -> None:
        """Create the schema (idempotent) and record/upgrade the schema version."""
        try:
            with self._lock:
                with self._conn:
                    for statement in ddl_statements():
                        self._conn.execute(statement)
                    self._migrate_instruments_name_column()
                    self._migrate_instruments_sector_column()
                    # SCHEMA_VERSION 11 tables (institutional_flows) are created
                    # by CREATE TABLE IF NOT EXISTS in ddl_statements above.
                    row = self._conn.execute("SELECT version FROM schema_version").fetchone()
                    if row is None:
                        self._conn.execute(
                            "INSERT INTO schema_version(version) VALUES (?)",
                            (SCHEMA_VERSION,),
                        )
                    elif int(row[0]) < SCHEMA_VERSION:
                        self._conn.execute(
                            "UPDATE schema_version SET version = ?",
                            (SCHEMA_VERSION,),
                        )
        except sqlite3.Error as exc:
            raise RepositoryError(f"schema initialization failed: {exc}") from exc

    def _migrate_instruments_name_column(self) -> None:
        """SCHEMA_VERSION 9: instruments.name — the real company name Kite's
        instrument dump already carries but ingestion previously discarded.
        Additive, nullable column; existing rows read as None (rendered as
        absent, never fabricated) until the next instrument catalog refresh
        backfills them via upsert_instrument. `CREATE TABLE IF NOT EXISTS`
        above is a no-op against an already-existing instruments table, so
        this explicit, idempotent ALTER is what actually reaches it."""
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(instruments)")}
        if "name" not in cols:
            self._conn.execute("ALTER TABLE instruments ADD COLUMN name TEXT")

    def _migrate_instruments_sector_column(self) -> None:
        """SCHEMA_VERSION 10: instruments.sector — NSE Nifty-500 CSV Industry
        (MI-4), previously discarded by parse_nifty_constituent_csv. Additive
        nullable column; seed backfills via update_instrument_sector. Kite has
        no sector field, so kite upserts must not wipe a seed-written value."""
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(instruments)")}
        if "sector" not in cols:
            self._conn.execute("ALTER TABLE instruments ADD COLUMN sector TEXT")

    def close_read_connection(self) -> None:
        """Close *this calling thread's own* read-only connection, if it has
        one — never another thread's (ADR-009). This is the per-thread
        cleanup hook: call it from a thread that is done issuing reads
        through this repository (e.g. a short-lived worker/task, or the
        thread that is also calling ``close()``) before that thread exits.
        A thread that never calls this and terminates without one is
        reclaimed by normal Python/OS teardown, not by this method — see
        ADR-009's stated limitation; there is no central registry that
        could close it on the thread's behalf.
        """
        conn = getattr(self._read_local, "conn", None)
        if conn is not None:
            conn.close()
            self._read_local.conn = None

    def close(self) -> None:
        self.close_read_connection()
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SqliteRepository:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def path(self) -> str:
        """Filesystem path of the underlying database (for backup/maintenance)."""
        return self._path

    @property
    def connection(self) -> sqlite3.Connection:
        """The live connection. Intended for maintenance (online backup) only.

        Callers that use this must serialize access themselves (prefer repository
        methods). The API providers never use this property on request paths.
        """
        return self._conn

    def record_counts(self) -> dict[str, int]:
        """Row counts per persisted table — used for backup/restore recovery checks."""
        tables = ("instruments", "candles", "quotes", "market_snapshots",
                  "corporate_actions", "quarantine_records", "runs",
                  "decisions", "decision_traces", "decision_journal",
                  "owner_positions", "owner_candidates", "saved_symbols",
                  "entry_qualifications", "entry_actionabilities", "ops_meta")
        try:
            with self._lock:
                return {
                    t: int(self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
                    for t in tables
                }
        except sqlite3.Error as exc:
            raise RepositoryError(f"record count query failed: {exc}") from exc

    @property
    def journal_mode(self) -> str:
        with self._lock:
            return str(self._conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    @property
    def foreign_keys_enabled(self) -> bool:
        with self._lock:
            return bool(self._conn.execute("PRAGMA foreign_keys").fetchone()[0])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Explicit transaction: commit on success, rollback on any exception."""
        with self._lock:
            cursor = self._conn.cursor()
            try:
                yield cursor
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # ------------------------------------------------------------- instruments

    def upsert_instrument(self, instrument: Instrument) -> None:
        self._write(
            "INSERT INTO instruments "
            "(instrument_id, isin, symbol, exchange, series, name, sector, lot_size, tick_size, status, "
            " listed_date, delisted_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(instrument_id) DO UPDATE SET "
            "isin=excluded.isin, symbol=excluded.symbol, exchange=excluded.exchange, "
            "series=excluded.series, name=excluded.name, "
            "sector=CASE WHEN excluded.sector IS NOT NULL THEN excluded.sector ELSE instruments.sector END, "
            "lot_size=excluded.lot_size, "
            "tick_size=excluded.tick_size, status=excluded.status, "
            "listed_date=excluded.listed_date, delisted_date=excluded.delisted_date",
            ser.instrument_to_row(instrument),
        )

    def update_instrument_sector(
        self, symbol: str, sector: str, *, exchange: str = "NSE"
    ) -> int:
        """MI-4: write NSE Industry onto matching instrument rows (seed backfill).

        Returns the number of rows updated. Symbols with no instruments yet
        stay untouched — sector appears once the catalog row exists.
        """
        bare = symbol.strip().upper()
        clean = sector.strip()
        if not bare or not clean:
            return 0
        try:
            with self._lock:
                with self._conn:
                    cur = self._conn.execute(
                        "UPDATE instruments SET sector=? WHERE UPPER(symbol)=? AND UPPER(exchange)=?",
                        (clean, bare, exchange.strip().upper()),
                    )
                    return int(cur.rowcount or 0)
        except sqlite3.Error as exc:
            raise RepositoryError(f"write failed: {exc}") from exc

    def get_instrument(self, instrument_id: str) -> Instrument | None:
        row = self._query_one(
            "SELECT instrument_id, isin, symbol, exchange, series, name, sector, lot_size, tick_size, "
            "status, listed_date, delisted_date FROM instruments WHERE instrument_id=?",
            (instrument_id,),
        )
        return ser.row_to_instrument(row) if row else None

    def list_instruments(self) -> list[Instrument]:
        rows = self._query_all(
            "SELECT instrument_id, isin, symbol, exchange, series, name, sector, lot_size, tick_size, "
            "status, listed_date, delisted_date FROM instruments ORDER BY instrument_id"
        )
        return [ser.row_to_instrument(r) for r in rows]

    # ------------------------------------------------------------- candles (append-only)

    def add_candles(self, candles: Sequence[Candle]) -> int:
        # Upsert, not plain insert (owner-reported, 2026-08-04): the still-
        # forming daily candle for the current trading day is re-fetched on
        # every ingestion cycle by design (see LiveIngestionEngine.run_cycle)
        # because its OHLC keeps changing until the session closes. A plain
        # INSERT would raise on the second write of the same day; overwriting
        # via ON CONFLICT lets that re-fetch actually land the corrected
        # values instead of failing (or, with skip_existing filtering the
        # write out beforehand, never being attempted at all — the two
        # changes work together). A no-op for genuinely unchanged historical
        # rows, since the values written back are identical.
        rows = [ser.candle_to_row(c) for c in candles]
        self._write_many(
            "INSERT INTO candles "
            "(instrument_id, timeframe, ts_open, open, high, low, close, volume, source, adjusted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(instrument_id, timeframe, ts_open) DO UPDATE SET "
            "open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, "
            "volume=excluded.volume, source=excluded.source, adjusted=excluded.adjusted",
            rows,
        )
        return len(rows)

    def replace_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime,
        candles: Sequence[Candle],
    ) -> tuple[int, int]:
        """Atomically replace every candle for (instrument_id, timeframe)
        whose ts_open falls in [start, end] with exactly `candles` -- one
        DELETE + one INSERT in a single transaction, leaving one canonical
        sequence for that range rather than the old rows sitting alongside
        the new ones. `add_candles`'s upsert only overwrites a row sharing
        the exact same ts_open; a corrected candle at a different exact
        timestamp (the real symptom of the settlement-drift defect this
        exists to repair) would otherwise be added alongside the old one,
        not replace it.

        For the M5 settlement-repair path only (Owner-authorized
        2026-08-28) -- candles remain append-only-by-convention everywhere
        else in the codebase; this method's existence does not change that.

        Returns (rows_deleted, rows_inserted).
        """
        if any(c.instrument_id != instrument_id or c.timeframe is not timeframe for c in candles):
            raise ValueError("replace_candles: every candle must match instrument_id/timeframe")
        if any(not (start <= c.ts_open <= end) for c in candles):
            raise ValueError("replace_candles: every candle's ts_open must fall within [start, end]")
        rows = [ser.candle_to_row(c) for c in candles]
        try:
            with self._lock:
                with self._conn:
                    cur = self._conn.execute(
                        "DELETE FROM candles WHERE instrument_id=? AND timeframe=? "
                        "AND ts_open>=? AND ts_open<=?",
                        (instrument_id, timeframe.value, start.isoformat(), end.isoformat()),
                    )
                    deleted = cur.rowcount or 0
                    if rows:
                        self._conn.executemany(
                            "INSERT INTO candles "
                            "(instrument_id, timeframe, ts_open, open, high, low, close, volume, source, "
                            "adjusted) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            rows,
                        )
            return deleted, len(rows)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"replace_candles failed: {exc}") from exc

    def get_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        rows = self._query_all(
            "SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume, source, "
            "adjusted FROM candles WHERE instrument_id=? AND timeframe=? "
            "AND ts_open>=? AND ts_open<=? ORDER BY ts_open",
            (instrument_id, timeframe.value, start.isoformat(), end.isoformat()),
        )
        return [ser.row_to_candle(r) for r in rows]

    def earliest_candle_ts(self, instrument_id: str, timeframe: Timeframe) -> datetime | None:
        """The earliest persisted `ts_open` for one instrument/timeframe, or
        `None` if none exist -- an indexed MIN() seek on `idx_candles_range`
        (instrument_id, timeframe, ts_open), not a table scan. Added for
        ID-5D.1: lets a caller retrieve "all available history" for an
        instrument without hardcoding a lookback-day count that would
        silently become an undisclosed rolling-window policy once more
        history accumulates than the hardcoded bound covers."""
        row = self._query_one(
            "SELECT MIN(ts_open) FROM candles WHERE instrument_id=? AND timeframe=?",
            (instrument_id, timeframe.value),
        )
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def candles_for_instruments(
        self, instrument_ids: Sequence[str], timeframe: Timeframe, start: datetime, end: datetime
    ) -> dict[str, list[Candle]]:
        """Candles for many instruments in one inclusive range, grouped by
        instrument -- one query (or a handful of chunked queries) rather
        than one `get_candles` call per symbol. Added for EM-5's scan-cycle
        bulk read (ADR-012 Section 10: no per-symbol query across a scan's
        whole eligible universe), following `candle_coverage`'s own
        chunked-`IN(...)` pattern exactly. Instruments with no candles in
        range are omitted, not returned as an empty list."""

        result: dict[str, list[Candle]] = {}
        if not instrument_ids:
            return result
        chunk_size = 500
        ids = list(instrument_ids)
        for chunk_start in range(0, len(ids), chunk_size):
            chunk = ids[chunk_start : chunk_start + chunk_size]
            marks = ",".join("?" * len(chunk))
            rows = self._query_all(
                f"SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume, source, "
                f"adjusted FROM candles WHERE timeframe=? AND instrument_id IN ({marks}) "
                f"AND ts_open>=? AND ts_open<=? ORDER BY instrument_id, ts_open",
                (timeframe.value, *chunk, start.isoformat(), end.isoformat()),
            )
            for row in rows:
                candle = ser.row_to_candle(row)
                result.setdefault(candle.instrument_id, []).append(candle)
        return result

    # ------------------------------------------------------------- quotes (append-only)

    def add_quotes(self, quotes: Sequence[Quote]) -> int:
        rows = [ser.quote_to_row(q) for q in quotes]
        self._write_many(
            "INSERT INTO quotes (instrument_id, ts, last_price, volume, source) VALUES (?,?,?,?,?)",
            rows,
        )
        return len(rows)

    def get_quotes(self, instrument_id: str) -> list[Quote]:
        rows = self._query_all(
            "SELECT instrument_id, ts, last_price, volume, source FROM quotes "
            "WHERE instrument_id=? ORDER BY ts",
            (instrument_id,),
        )
        return [ser.row_to_quote(r) for r in rows]

    def get_latest_quote(
        self, instrument_id: str, *, as_of: datetime | None = None
    ) -> Quote | None:
        """Most recent quote only (ID-1: `SessionContext.latest_quote_ts`).

        `get_quotes()` returns the full unbounded history for an instrument —
        fine for the callers that already use it, but wrong for a per-cycle,
        per-instrument freshness read, which only ever needs the single
        latest row. Bounded by the existing `(instrument_id, ts)` primary
        key's index — no new index, no schema change.

        `as_of` (ID-5F, market-time point-in-time safety, same contract as
        `list_candles_recent`'s ID-5E fix): when given, only quotes with
        `ts<=as_of` are eligible -- applied in SQL BEFORE `ORDER BY ...
        LIMIT 1`, never as a Python filter after (which could return None
        or the wrong row once an eligible earlier quote exists but an
        unbounded fetch already returned a later, ineligible one).
        `as_of=None` (the default) preserves the exact pre-ID-5F behavior
        byte-for-byte for every existing live-current-state caller. This
        bounds MARKET-TIME (`ts`) only -- the `quotes` table already
        retains one row per distinct timestamp (append-only, PRIMARY KEY
        `(instrument_id, ts)`), so no schema change was needed to support
        this; it says nothing about whether a since-superseded quote at
        that exact market timestamp was ever itself later corrected
        (knowledge-time/bitemporal replay, still unsupported).
        """
        if as_of is not None:
            if as_of.tzinfo is None:
                raise ValueError("get_latest_quote as_of must be timezone-aware")
            rows = self._query_all(
                "SELECT instrument_id, ts, last_price, volume, source FROM quotes "
                "WHERE instrument_id=? AND ts<=? ORDER BY ts DESC LIMIT 1",
                (instrument_id, as_of.isoformat()),
            )
        else:
            rows = self._query_all(
                "SELECT instrument_id, ts, last_price, volume, source FROM quotes "
                "WHERE instrument_id=? ORDER BY ts DESC LIMIT 1",
                (instrument_id,),
            )
        return ser.row_to_quote(rows[0]) if rows else None

    # ------------------------------------------------------------- market snapshots

    def add_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Idempotent on ts (owner-reported, 2026-08-10): the caller used to
        guard this by comparing against only the single most-recent snapshot
        (get_latest_snapshot()), which misses any earlier row at the same ts
        once a later snapshot exists — exactly what happens on a second
        after-hours validate, since every after-hours as_of resolves to the
        same frozen session-close instant (resolve_validate_as_of). Once any
        live-mode snapshot from earlier in the day is the current "latest",
        that guard no longer catches the collision and the plain INSERT
        raised UNIQUE constraint failed: market_snapshots.ts. Making the
        write itself idempotent removes the whole class of bug regardless of
        caller logic."""
        self._write(
            "INSERT INTO market_snapshots (ts, payload_json) VALUES (?,?) "
            "ON CONFLICT(ts) DO NOTHING",
            (snapshot.ts.isoformat(), ser.snapshot_to_payload(snapshot)),
        )

    def get_latest_snapshot(self) -> MarketSnapshot | None:
        row = self._query_one(
            "SELECT payload_json FROM market_snapshots ORDER BY ts DESC LIMIT 1", ()
        )
        return ser.payload_to_snapshot(row[0]) if row else None

    def get_latest_snapshot_before(self, before: datetime) -> MarketSnapshot | None:
        """Return the newest persisted snapshot strictly before ``before``.

        ID-5G.1: uses `_latest_snapshot_at_or_before`'s full-precision
        Python-side comparison (adjacent fix -- this method shared the
        exact same `datetime()`-truncation precision bug ID-5G.1 fixed in
        `get_latest_snapshot_as_of`). Its own STRICT `<` semantics for its
        two real callers (`market_history_service`'s previous-trading-day
        snapshot lookup, `config_preview`'s pre-decision snapshot lookup)
        are completely unchanged -- only the comparison's precision is
        corrected.
        """
        if before.tzinfo is None:
            raise ValueError("get_latest_snapshot_before before must be timezone-aware")
        return self._latest_snapshot_at_or_before(before, inclusive=False)

    def get_latest_snapshot_as_of(self, as_of: datetime) -> MarketSnapshot | None:
        """Newest persisted snapshot with `ts<=as_of` (ID-5G, market-time
        point-in-time safety) -- INCLUSIVE at the exact boundary, deliberately
        distinct from `get_latest_snapshot_before`'s STRICT `<` semantics.
        The two answer different questions: `..._before` means "the state
        from strictly before this instant" (its own two callers want the
        PRIOR session's snapshot / the snapshot before a given decision was
        made -- same-instant coincidence must be excluded there). This
        method means "the state effective AT this analytical instant",
        matching every other ID-5E/ID-5F point-in-time contract's inclusive
        `<=` convention (a candle/quote/snapshot exactly at `as_of` is
        already known at `as_of`) -- so `get_latest_snapshot_before` itself
        is untouched, never repurposed or made inclusive.

        ID-5G.1: full-precision, offset-safe absolute-time comparison. The
        original ID-5G implementation wrapped both sides in SQLite's
        `datetime()` function (chosen because the file-based provider's
        `_aware_ts` permits a snapshot `ts` with any UTC offset, so raw
        TEXT comparison could not be assumed chronologically correct) --
        but `datetime()` TRUNCATES to whole seconds, so two snapshots
        0.9s and 0.1s into the same second are indistinguishable and can
        be misordered (confirmed empirically: `datetime('...:00.900+05:30')
        <= datetime('...:00.100+05:30')` evaluates true in SQLite). A
        `julianday()` alternative was also measured: offset-safe and
        millisecond-safe (zero collisions across all 1000 millisecond
        values in a full sweep), but demonstrably NOT microsecond-safe
        (two `ts` values 1 microsecond apart evaluated as equal) -- and
        Python's own `datetime.now()` (the real source of every
        production `as_of`/snapshot `ts`) carries microsecond resolution,
        so this residual gap was not acceptable. Fixed instead by
        `_latest_snapshot_at_or_before`: fetch every persisted row (this
        table holds one row per validation cycle, market-wide, never
        per-instrument -- measured at 1,872 rows in the real production
        database, fetched in ~13ms) and compare using Python's own
        `datetime` ordering, which has no floating-point precision loss
        at any sub-second granularity and is correct across mixed UTC
        offsets by construction (aware-datetime comparison is defined on
        absolute instants, not on textual representation).
        """
        if as_of.tzinfo is None:
            raise ValueError("get_latest_snapshot_as_of as_of must be timezone-aware")
        return self._latest_snapshot_at_or_before(as_of, inclusive=True)

    def _latest_snapshot_at_or_before(
        self, cutoff: datetime, *, inclusive: bool
    ) -> MarketSnapshot | None:
        """Shared full-precision selection for both snapshot point-in-time
        methods above -- never "fetch only the global latest, then reject
        in Python" (which would hide a valid earlier snapshot behind a
        later, ineligible one); every row is considered, and the true
        maximum eligible timestamp is selected directly."""
        rows = self._query_all("SELECT ts, payload_json FROM market_snapshots")
        best_ts: datetime | None = None
        best_payload: str | None = None
        for ts_str, payload in rows:
            ts = datetime.fromisoformat(ts_str)
            eligible = ts <= cutoff if inclusive else ts < cutoff
            if eligible and (best_ts is None or ts > best_ts):
                best_ts = ts
                best_payload = payload
        return ser.payload_to_snapshot(best_payload) if best_payload is not None else None

    def list_snapshots_recent(self, *, limit: int = 30) -> list[MarketSnapshot]:
        """Newest-first market snapshots, then returned oldest→newest for sparklines."""
        if limit < 1:
            raise ValueError(f"list_snapshots_recent limit must be >= 1, got {limit}")
        rows = self._query_all(
            "SELECT payload_json FROM market_snapshots ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        snaps = [ser.payload_to_snapshot(r[0]) for r in rows]
        snaps.reverse()
        return snaps

    # ------------------------------------------------------------- institutional flows

    def add_institutional_flow(self, session: InstitutionalFlowSession) -> None:
        """Append one FII/DII session row (never UPDATE — ADR-008 / DD-11)."""
        self._write(
            "INSERT INTO institutional_flows "
            "(session_date, fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net, "
            "provisional, source_id, fetched_at, run_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ser.institutional_flow_to_row(session),
        )

    def get_latest_institutional_flow(
        self, *, prefer_final: bool = True
    ) -> InstitutionalFlowSession | None:
        """Newest session date; when prefer_final, non-provisional beats provisional."""
        row = self._query_one(
            "SELECT session_date, fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net, "
            "provisional, source_id, fetched_at, run_id FROM institutional_flows "
            "ORDER BY session_date DESC, "
            "CASE WHEN ? = 1 THEN provisional ELSE 0 END ASC, "
            "fetched_at DESC LIMIT 1",
            (1 if prefer_final else 0,),
        )
        return ser.row_to_institutional_flow(row) if row else None

    def list_institutional_flows_recent(
        self, *, limit: int = 60
    ) -> list[InstitutionalFlowSession]:
        if limit < 1:
            raise ValueError(f"list_institutional_flows_recent limit must be >= 1, got {limit}")
        rows = self._query_all(
            "SELECT session_date, fii_buy, fii_sell, fii_net, dii_buy, dii_sell, dii_net, "
            "provisional, source_id, fetched_at, run_id FROM institutional_flows "
            "ORDER BY session_date DESC, fetched_at DESC LIMIT ?",
            (limit,),
        )
        return [ser.row_to_institutional_flow(r) for r in rows]

    # ------------------------------------------------------------- corporate actions

    def add_corporate_action(self, action: CorporateAction) -> None:
        self._write(
            "INSERT INTO corporate_actions "
            "(action_id, instrument_id, action_type, ex_date, details_json) VALUES (?,?,?,?,?)",
            ser.corporate_action_to_row(action),
        )

    def add_corporate_actions(self, actions: Sequence[CorporateAction]) -> int:
        """Insert an official action batch atomically and idempotently.

        Replaying identical evidence is a no-op. Reusing an action ID for
        different evidence fails the entire batch before any row is written.
        """

        rows_by_id: dict[str, tuple[object, ...]] = {}
        for action in actions:
            row = ser.corporate_action_to_row(action)
            current = rows_by_id.get(action.action_id)
            if current is not None and current != row:
                raise RepositoryError(
                    f"corporate-action conflict within batch for action_id={action.action_id}"
                )
            rows_by_id[action.action_id] = row
        rows = sorted(rows_by_id.values())
        if not rows:
            return 0
        try:
            with self._lock:
                with self._conn:
                    ids = tuple(row[0] for row in rows)
                    placeholders = ",".join("?" for _ in ids)
                    existing = {
                        row[0]: tuple(row)
                        for row in self._conn.execute(
                            "SELECT action_id, instrument_id, action_type, ex_date, details_json "
                            f"FROM corporate_actions WHERE action_id IN ({placeholders})",
                            ids,
                        ).fetchall()
                    }
                    for row in rows:
                        current = existing.get(row[0])
                        if current is not None and current != row:
                            raise RepositoryError(
                                f"corporate-action replay conflict for action_id={row[0]}"
                            )
                    pending = [row for row in rows if row[0] not in existing]
                    self._conn.executemany(
                        "INSERT INTO corporate_actions "
                        "(action_id, instrument_id, action_type, ex_date, details_json) "
                        "VALUES (?,?,?,?,?)",
                        pending,
                    )
                    return len(pending)
        except RepositoryError:
            raise
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"write failed: {exc}") from exc

    def get_corporate_actions(self, instrument_id: str) -> list[CorporateAction]:
        rows = self._query_all(
            "SELECT action_id, instrument_id, action_type, ex_date, details_json "
            "FROM corporate_actions WHERE instrument_id=? ORDER BY ex_date, action_id",
            (instrument_id,),
        )
        return [ser.row_to_corporate_action(r) for r in rows]

    # ------------------------------------------------------------- quarantine

    def save_quarantine(self, record: QuarantineRecord) -> None:
        self._write(
            "INSERT INTO quarantine_records (dataset_id, reason, quarantined_ts, reports_json) "
            "VALUES (?,?,?,?) ON CONFLICT(dataset_id) DO UPDATE SET "
            "reason=excluded.reason, quarantined_ts=excluded.quarantined_ts, "
            "reports_json=excluded.reports_json",
            (record.dataset_id, record.reason, record.quarantined_ts.isoformat(),
             ser.reports_to_json(record.failed_reports)),
        )

    def get_quarantine(self, dataset_id: str) -> QuarantineRecord | None:
        row = self._query_one(
            "SELECT dataset_id, reason, quarantined_ts, reports_json "
            "FROM quarantine_records WHERE dataset_id=?",
            (dataset_id,),
        )
        if not row:
            return None
        return QuarantineRecord(
            dataset_id=row[0], reason=row[1],
            failed_reports=ser.json_to_reports(row[3]),
            quarantined_ts=datetime.fromisoformat(row[2]),
        )

    def list_quarantine(self) -> list[QuarantineRecord]:
        rows = self._query_all(
            "SELECT dataset_id FROM quarantine_records ORDER BY dataset_id"
        )
        return [self.get_quarantine(r[0]) for r in rows]  # type: ignore[misc]

    # ------------------------------------------------------------- runs (M10.2)

    def save_run(self, run: RunRecord, *, detail: Mapping[str, object] | None = None) -> None:
        """Upsert a run ledger row (RUNNING then terminal status for one run_id)."""
        import json as _json

        detail_json = _json.dumps(detail or {}, sort_keys=True, default=str)
        self._write(
            "INSERT INTO runs ("
            "run_id, cycle_id, trigger, started_ts, finished_ts, status, "
            "software_version, blueprint_version, strategy_profile, "
            "strategy_profile_version, indicator_versions_json, config_snapshot_id, "
            "input_digest, detail_json"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(run_id) DO UPDATE SET "
            "cycle_id=excluded.cycle_id, trigger=excluded.trigger, "
            "started_ts=excluded.started_ts, finished_ts=excluded.finished_ts, "
            "status=excluded.status, software_version=excluded.software_version, "
            "blueprint_version=excluded.blueprint_version, "
            "strategy_profile=excluded.strategy_profile, "
            "strategy_profile_version=excluded.strategy_profile_version, "
            "indicator_versions_json=excluded.indicator_versions_json, "
            "config_snapshot_id=excluded.config_snapshot_id, "
            "input_digest=excluded.input_digest, detail_json=excluded.detail_json",
            ser.run_to_row(run, detail_json),
        )

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._query_one(
            "SELECT run_id, cycle_id, trigger, started_ts, finished_ts, status, "
            "software_version, blueprint_version, strategy_profile, "
            "strategy_profile_version, indicator_versions_json, config_snapshot_id, "
            "input_digest, detail_json FROM runs WHERE run_id=?",
            (run_id,),
        )
        return ser.row_to_run(row) if row else None

    def get_run_detail(self, run_id: str) -> dict:
        import json as _json

        row = self._query_one("SELECT detail_json FROM runs WHERE run_id=?", (run_id,))
        if not row:
            return {}
        return dict(_json.loads(row[0]))

    def list_runs(self, *, trigger: str | None = None, limit: int = 100) -> list[RunRecord]:
        if trigger is None:
            rows = self._query_all(
                "SELECT run_id, cycle_id, trigger, started_ts, finished_ts, status, "
                "software_version, blueprint_version, strategy_profile, "
                "strategy_profile_version, indicator_versions_json, config_snapshot_id, "
                "input_digest, detail_json FROM runs "
                "ORDER BY started_ts DESC, run_id DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self._query_all(
                "SELECT run_id, cycle_id, trigger, started_ts, finished_ts, status, "
                "software_version, blueprint_version, strategy_profile, "
                "strategy_profile_version, indicator_versions_json, config_snapshot_id, "
                "input_digest, detail_json FROM runs WHERE trigger=? "
                "ORDER BY started_ts DESC, run_id DESC LIMIT ?",
                (trigger, limit),
            )
        return [ser.row_to_run(r) for r in rows]

    def latest_run(self, trigger: str) -> RunRecord | None:
        rows = self.list_runs(trigger=trigger, limit=1)
        return rows[0] if rows else None

    # ------------------------------------------------------------- decisions (R2)

    def save_decision(
        self, decision: Decision, *, trace: DecisionTrace | None = None,
    ) -> None:
        """Upsert a Decision and optional DecisionTrace."""
        if trace is not None and trace.decision_ref != decision.decision_id:
            raise RepositoryError(
                f"trace.decision_ref '{trace.decision_ref}' does not match "
                f"decision_id '{decision.decision_id}'"
            )
        self._write(
            "INSERT INTO decisions ("
            "decision_id, ts, run_id, cycle_id, decision_type, explanation, "
            "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
            "gate_results_json, trade_plan_json"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(decision_id) DO UPDATE SET "
            "ts=excluded.ts, run_id=excluded.run_id, cycle_id=excluded.cycle_id, "
            "decision_type=excluded.decision_type, explanation=excluded.explanation, "
            "instrument_id=excluded.instrument_id, direction=excluded.direction, "
            "score_ref=excluded.score_ref, confidence_ref=excluded.confidence_ref, "
            "risk_ref=excluded.risk_ref, gate_results_json=excluded.gate_results_json, "
            "trade_plan_json=excluded.trade_plan_json",
            ser.decision_to_row(decision),
        )
        if trace is not None:
            self._write(
                "INSERT INTO decision_traces (decision_ref, stages_json) VALUES (?,?) "
                "ON CONFLICT(decision_ref) DO UPDATE SET stages_json=excluded.stages_json",
                ser.trace_to_row(trace),
            )

    def get_decision(self, decision_id: str) -> Decision | None:
        row = self._query_one(
            "SELECT decision_id, ts, run_id, cycle_id, decision_type, explanation, "
            "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
            "gate_results_json, trade_plan_json FROM decisions WHERE decision_id=?",
            (decision_id,),
        )
        return ser.row_to_decision(row) if row else None

    def get_trace(self, decision_ref: str) -> DecisionTrace | None:
        row = self._query_one(
            "SELECT decision_ref, stages_json FROM decision_traces WHERE decision_ref=?",
            (decision_ref,),
        )
        return ser.row_to_trace(row) if row else None

    def list_decisions(self, *, limit: int = 500) -> list[Decision]:
        rows = self._query_all(
            "SELECT decision_id, ts, run_id, cycle_id, decision_type, explanation, "
            "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
            "gate_results_json, trade_plan_json FROM decisions "
            "ORDER BY ts DESC, decision_id DESC LIMIT ?",
            (limit,),
        )
        return [ser.row_to_decision(r) for r in rows]

    _DECISION_SORT_COLUMNS: ClassVar[dict[str, str]] = {
        "ts": "ts",
        "instrument_id": "instrument_id",
        "decision_id": "decision_id",
    }

    def query_decisions(
        self,
        *,
        instrument_id: str | None = None,
        decision_type: str | None = None,
        direction: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        sort_by: str = "ts",
        sort_dir: str = "desc",
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Decision], int]:
        """Filter/sort/paginate decisions entirely in SQL.

        Replaces the API-layer pattern of pulling a fixed 5000-row window and
        re-filtering/sorting/slicing it in Python on every page request: that
        redid the same full-window fetch+parse per page and silently dropped
        decisions once history passed the window (owner-reported, 2026-08-04:
        Decisions & Trace slow to load with 13,900+ persisted decisions).
        """
        where: list[str] = []
        params: list[object] = []
        if instrument_id:
            where.append("instrument_id = ?")
            params.append(instrument_id)
        if decision_type:
            where.append("decision_type = ?")
            params.append(decision_type)
        if direction:
            where.append("direction = ?")
            params.append(direction)
        if from_date:
            where.append("ts >= ?")
            params.append(from_date.isoformat())
        if to_date:
            where.append("ts <= ?")
            params.append(to_date.isoformat())
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        column = self._DECISION_SORT_COLUMNS.get(sort_by, "ts")
        order_dir = "ASC" if sort_dir == "asc" else "DESC"
        order = f"ORDER BY {column} {order_dir}"
        if column != "decision_id":
            order += f", decision_id {order_dir}"

        count_row = self._query_one(f"SELECT COUNT(*) FROM decisions {clause}", tuple(params))
        total_count = int(count_row[0]) if count_row else 0

        rows = self._query_all(
            "SELECT decision_id, ts, run_id, cycle_id, decision_type, explanation, "
            "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
            f"gate_results_json, trade_plan_json FROM decisions {clause} {order} "
            "LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return [ser.row_to_decision(r) for r in rows], total_count

    def list_latest_decisions_by_instrument(self) -> list[Decision]:
        """Return exactly one newest persisted decision per instrument.

        Timestamp ties use decision_id descending, matching ``list_decisions``.
        The query is intentionally unbounded so index coverage cannot silently
        become incomplete as decision history grows.

        Owner-reported (2026-08-10): the original NOT EXISTS correlated
        subquery re-evaluates "is there a newer row for this instrument" once
        per decision row — 1.7s at 91,241 rows even with
        idx_decisions_instrument_ts. A single ROW_NUMBER() pass over the same
        index is ~30x faster (57ms at the same scale) for an identical result
        set (verified via EXCEPT against the old query — zero row diff).
        """
        rows = self._query_all(
            "SELECT decision_id, ts, run_id, cycle_id, decision_type, "
            "explanation, instrument_id, direction, score_ref, "
            "confidence_ref, risk_ref, gate_results_json, trade_plan_json "
            "FROM (SELECT *, ROW_NUMBER() OVER ("
            "PARTITION BY instrument_id ORDER BY ts DESC, decision_id DESC"
            ") AS rn FROM decisions WHERE instrument_id IS NOT NULL) "
            "WHERE rn = 1 ORDER BY instrument_id"
        )
        return [ser.row_to_decision(r) for r in rows]

    # ---------------------------------------------- entry qualifications (ID-6C)
    #
    # Durable, auditable persistence for EntryQualification (ID-6A domain
    # contract, ID-6B.2 pure engine). Persists what the engine already
    # concluded; introduces no methodology of its own. Append-only:
    # EntryQualification is a point-in-time, non-sticky observation (ID-6B
    # measured ~40% checkpoint-level flicker), so a later observation for
    # the same instrument/session is a NEW row, never an overwrite.
    #
    # Not wired into any production path by this milestone (ID-6D's job).

    _ENTRY_QUALIFICATION_COLUMNS = (
        "instrument_id, session_date, as_of, decision_id, methodology_version, "
        "run_id, cycle_id, decision_type, state, evidence_finality, confirmation, "
        "reason_codes_json, evidence_refs_json, config_snapshot_id, explanation"
    )

    def save_entry_qualification(
        self, eq: EntryQualification, *, persisted_at: datetime,
    ) -> bool:
        """Append-only, idempotent write of one EntryQualification observation.

        The logical/idempotency identity is (instrument_id, session_date,
        as_of, decision_id, methodology_version) — the table's composite
        primary key. ``run_id``/``cycle_id`` are deliberately NOT part of
        that key, because ``decision_id`` already functionally determines
        them — but (ID-6C.1) every call first loads the referenced
        canonical Decision and requires ``eq`` to agree with it exactly on
        ``decision_type``, ``run_id``, ``cycle_id``, and (when the Decision
        itself specifies one) ``instrument_id``. A foreign key on
        ``decision_id`` alone only proves the Decision exists; it cannot
        prove the supplied EntryQualification truthfully describes that
        Decision. See ``_validate_entry_qualification_decision_binding``.

        This binding check runs before EITHER an insert or an idempotency
        no-op — an already-persisted, internally-consistent row must never
        let a second, Decision-inconsistent call hide behind "identical
        identity => no-op".

        After binding validation, returns True if a new row was inserted,
        False if an identical logical observation already existed (no-op —
        the deterministic engine reproduced the same payload). Raises
        RepositoryError if the same logical identity already exists with a
        genuinely different payload: a deterministic engine must never
        produce two different payloads for the same logical evaluation, so
        that is an integrity problem, never silently overwritten. Because
        binding validation has already proven ``run_id``/``cycle_id``
        agree with the canonical Decision, they remain excluded from this
        payload comparison too — not because they may legitimately differ,
        but because they are already proven equal by the time this
        comparison runs. ``persisted_at`` is write/audit metadata only,
        never part of identity or comparison.

        This method never resolves whether the referenced Decision is
        still the current/non-superseded one for its instrument — that
        remains a caller/workflow responsibility (ID-6D), unchanged from
        ID-6B.2A's own frozen boundary.
        """
        try:
            with self._lock, self._conn:
                decision_row = self._conn.execute(
                    "SELECT decision_id, ts, run_id, cycle_id, decision_type, explanation, "
                    "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
                    "gate_results_json, trade_plan_json FROM decisions WHERE decision_id=?",
                    (eq.decision_id,),
                ).fetchone()
                if decision_row is None:
                    raise RepositoryError(
                        "EntryQualification references unknown "
                        f"decision_id={eq.decision_id!r}"
                    )
                decision = ser.row_to_decision(decision_row)
                _validate_entry_qualification_decision_binding(eq, decision)

                row = self._conn.execute(
                    f"SELECT {self._ENTRY_QUALIFICATION_COLUMNS} "
                    "FROM entry_qualifications WHERE instrument_id=? AND "
                    "session_date=? AND as_of=? AND decision_id=? AND "
                    "methodology_version=?",
                    (
                        eq.instrument_id, eq.session_date.isoformat(),
                        eq.as_of.isoformat(), eq.decision_id, eq.methodology_version,
                    ),
                ).fetchone()
                if row is not None:
                    existing = ser.row_to_entry_qualification(row)
                    if _entry_qualification_payload(existing) != _entry_qualification_payload(eq):
                        raise RepositoryError(
                            "EntryQualification integrity conflict: an observation "
                            f"already exists for instrument_id={eq.instrument_id!r} "
                            f"session_date={eq.session_date.isoformat()!r} "
                            f"as_of={eq.as_of.isoformat()!r} decision_id={eq.decision_id!r} "
                            f"methodology_version={eq.methodology_version!r} with a "
                            "different payload"
                        )
                    return False
                self._conn.execute(
                    "INSERT INTO entry_qualifications "
                    f"({self._ENTRY_QUALIFICATION_COLUMNS}, persisted_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*ser.entry_qualification_to_row(eq), persisted_at.isoformat()),
                )
                return True
        except RepositoryError:
            raise
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"save entry qualification failed: {exc}") from exc

    def get_entry_qualification(
        self,
        *,
        instrument_id: str,
        session_date: date,
        as_of: datetime,
        decision_id: str,
        methodology_version: str,
    ) -> EntryQualification | None:
        """Exact logical-identity lookup — the same key `save_entry_qualification`
        uses for idempotency, exposed for round-trip verification and audit."""
        row = self._query_one(
            f"SELECT {self._ENTRY_QUALIFICATION_COLUMNS} FROM entry_qualifications "
            "WHERE instrument_id=? AND session_date=? AND as_of=? AND decision_id=? "
            "AND methodology_version=?",
            (
                instrument_id, session_date.isoformat(), as_of.isoformat(),
                decision_id, methodology_version,
            ),
        )
        return ser.row_to_entry_qualification(row) if row else None

    def latest_entry_qualification_for_decision(
        self, decision_id: str
    ) -> EntryQualification | None:
        """Most recent observation bound to one canonical Decision.

        Does NOT resolve whether that Decision is still the current/
        non-superseded one for its instrument — that selection remains the
        caller/workflow's responsibility (ID-6B.2A/ID-6D boundary); this
        only retrieves what was persisted for the given decision_id.
        """
        row = self._query_one(
            f"SELECT {self._ENTRY_QUALIFICATION_COLUMNS} FROM entry_qualifications "
            "WHERE decision_id=? ORDER BY as_of DESC, methodology_version DESC LIMIT 1",
            (decision_id,),
        )
        return ser.row_to_entry_qualification(row) if row else None

    def latest_entry_qualification_for_instrument_session(
        self, instrument_id: str, session_date: date
    ) -> EntryQualification | None:
        """Most recent observation for one instrument's trading session,
        across whichever canonical Decision(s) were evaluated that day."""
        row = self._query_one(
            f"SELECT {self._ENTRY_QUALIFICATION_COLUMNS} FROM entry_qualifications "
            "WHERE instrument_id=? AND session_date=? "
            "ORDER BY as_of DESC, decision_id DESC, methodology_version DESC LIMIT 1",
            (instrument_id, session_date.isoformat()),
        )
        return ser.row_to_entry_qualification(row) if row else None

    def list_entry_qualifications_for_instrument_session(
        self, instrument_id: str, session_date: date
    ) -> list[EntryQualification]:
        """Full append-only observation history for one instrument/session,
        oldest first — the audit view of a candidate's checkpoint-by-
        checkpoint flicker across one trading day."""
        rows = self._query_all(
            f"SELECT {self._ENTRY_QUALIFICATION_COLUMNS} FROM entry_qualifications "
            "WHERE instrument_id=? AND session_date=? "
            "ORDER BY as_of ASC, decision_id ASC, methodology_version ASC",
            (instrument_id, session_date.isoformat()),
        )
        return [ser.row_to_entry_qualification(r) for r in rows]

    # ------------------------------------------------------- entry actionabilities (ID-7A)
    #
    # Durable, auditable persistence for EntryActionability (ADR-015,
    # ID-7A0/ID-7A0.1, V0 methodology frozen by ID-7B/ID-7B.1/ID-7B.2/
    # ID-7B.2.1). Persists what the (not-yet-built, ID-7C) evaluator will
    # conclude; introduces no methodology of its own. Append-only,
    # mirroring save_entry_qualification's own contract exactly: a later
    # observation for the same instrument/session is a NEW row, never an
    # overwrite. Read-time currentness (dimension B,
    # entry_actionability_currentness.is_currently_usable) is never
    # computed or stored by this class — only dimension A (persisted
    # methodology state) is persisted here.
    #
    # Not wired into any production path by this milestone (ID-7E's job).
    # No evaluator exists yet (ID-7C's job) — these methods only store and
    # retrieve whatever EntryActionability object a caller constructs.

    _ENTRY_ACTIONABILITY_COLUMNS = (
        "instrument_id, session_date, entry_qualification_as_of, decision_id, "
        "entry_qualification_methodology_version, entry_actionability_as_of, "
        "entry_actionability_methodology_version, run_id, cycle_id, decision_type, "
        "direction, entry_qualification_state, state, reason_codes_json, "
        "evidence_finality, evidence_as_of, entry_reference_json, "
        "entry_location_context_json, operative_invalidation_json, reward_json, "
        "opening_range_context_json, evaluated_at, explanation"
    )

    def save_entry_actionability(
        self, ea: EntryActionability, *, persisted_at: datetime,
    ) -> bool:
        """Append-only, idempotent write of one EntryActionability observation.

        The logical/idempotency identity is EntryActionability's own full
        composite key — the upstream EntryQualification's entire identity
        copied verbatim plus this artifact's own
        ``entry_actionability_as_of``/``entry_actionability_methodology_version``
        (the table's composite primary key; see ``schema.py``). Before
        either an insert or an idempotency no-op, this method proves two
        independent bindings, mirroring ``save_entry_qualification``'s own
        two-stage validation pattern:

        1. The referenced canonical ``Decision`` exists and ``ea`` agrees
           with it on ``decision_type``/``run_id``/``cycle_id``/
           ``instrument_id`` (``_validate_entry_actionability_decision_binding``).
        2. The referenced exact upstream ``EntryQualification`` observation
           (looked up by ``ea``'s own copied EQ identity) exists and
           ``ea``'s denormalized ``entry_qualification_state`` agrees with
           it (``_validate_entry_actionability_eq_binding``).

        Returns True if a new row was inserted, False if an identical
        logical observation already existed (no-op). Raises
        RepositoryError if the same logical identity already exists with a
        genuinely different payload — a deterministic evaluator must never
        produce two different payloads for the same logical evaluation.
        ``persisted_at`` is write/audit metadata only, never part of
        identity or comparison.

        This method never resolves whether the referenced Decision/EQ pair
        is still the current one for its instrument, and never computes
        read-time currentness — both remain a caller/workflow
        responsibility (ID-7E), unchanged from EQ's own established
        ID-6B.2A/ID-6D boundary.
        """
        try:
            with self._lock, self._conn:
                decision_row = self._conn.execute(
                    "SELECT decision_id, ts, run_id, cycle_id, decision_type, explanation, "
                    "instrument_id, direction, score_ref, confidence_ref, risk_ref, "
                    "gate_results_json, trade_plan_json FROM decisions WHERE decision_id=?",
                    (ea.decision_id,),
                ).fetchone()
                if decision_row is None:
                    raise RepositoryError(
                        "EntryActionability references unknown "
                        f"decision_id={ea.decision_id!r}"
                    )
                decision = ser.row_to_decision(decision_row)
                _validate_entry_actionability_decision_binding(ea, decision)

                eq_row = self._conn.execute(
                    f"SELECT {self._ENTRY_QUALIFICATION_COLUMNS} "
                    "FROM entry_qualifications WHERE instrument_id=? AND "
                    "session_date=? AND as_of=? AND decision_id=? AND "
                    "methodology_version=?",
                    (
                        ea.instrument_id, ea.session_date.isoformat(),
                        ea.entry_qualification_as_of.isoformat(), ea.decision_id,
                        ea.entry_qualification_methodology_version,
                    ),
                ).fetchone()
                if eq_row is None:
                    raise RepositoryError(
                        "EntryActionability references unknown EntryQualification "
                        f"identity (instrument_id={ea.instrument_id!r}, "
                        f"session_date={ea.session_date.isoformat()!r}, "
                        f"entry_qualification_as_of={ea.entry_qualification_as_of.isoformat()!r}, "
                        f"decision_id={ea.decision_id!r}, "
                        "entry_qualification_methodology_version="
                        f"{ea.entry_qualification_methodology_version!r})"
                    )
                eq = ser.row_to_entry_qualification(eq_row)
                _validate_entry_actionability_eq_binding(ea, eq)

                row = self._conn.execute(
                    f"SELECT {self._ENTRY_ACTIONABILITY_COLUMNS} "
                    "FROM entry_actionabilities WHERE instrument_id=? AND "
                    "session_date=? AND entry_qualification_as_of=? AND decision_id=? "
                    "AND entry_qualification_methodology_version=? AND "
                    "entry_actionability_as_of=? AND entry_actionability_methodology_version=?",
                    (
                        ea.instrument_id, ea.session_date.isoformat(),
                        ea.entry_qualification_as_of.isoformat(), ea.decision_id,
                        ea.entry_qualification_methodology_version,
                        ea.entry_actionability_as_of.isoformat(),
                        ea.entry_actionability_methodology_version,
                    ),
                ).fetchone()
                if row is not None:
                    existing = ser.row_to_entry_actionability(row)
                    if _entry_actionability_payload(existing) != _entry_actionability_payload(ea):
                        raise RepositoryError(
                            "EntryActionability integrity conflict: an observation "
                            f"already exists for instrument_id={ea.instrument_id!r} "
                            f"session_date={ea.session_date.isoformat()!r} "
                            "entry_qualification_as_of="
                            f"{ea.entry_qualification_as_of.isoformat()!r} "
                            f"decision_id={ea.decision_id!r} "
                            "entry_qualification_methodology_version="
                            f"{ea.entry_qualification_methodology_version!r} "
                            "entry_actionability_as_of="
                            f"{ea.entry_actionability_as_of.isoformat()!r} "
                            "entry_actionability_methodology_version="
                            f"{ea.entry_actionability_methodology_version!r} with a "
                            "different payload"
                        )
                    return False
                self._conn.execute(
                    "INSERT INTO entry_actionabilities "
                    f"({self._ENTRY_ACTIONABILITY_COLUMNS}, persisted_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*ser.entry_actionability_to_row(ea), persisted_at.isoformat()),
                )
                return True
        except RepositoryError:
            raise
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"save entry actionability failed: {exc}") from exc

    def get_entry_actionability(
        self,
        *,
        instrument_id: str,
        session_date: date,
        entry_qualification_as_of: datetime,
        decision_id: str,
        entry_qualification_methodology_version: str,
        entry_actionability_as_of: datetime,
        entry_actionability_methodology_version: str,
    ) -> EntryActionability | None:
        """Exact logical-identity lookup — the same key
        ``save_entry_actionability`` uses for idempotency, exposed for
        round-trip verification and audit."""
        row = self._query_one(
            f"SELECT {self._ENTRY_ACTIONABILITY_COLUMNS} FROM entry_actionabilities "
            "WHERE instrument_id=? AND session_date=? AND entry_qualification_as_of=? "
            "AND decision_id=? AND entry_qualification_methodology_version=? AND "
            "entry_actionability_as_of=? AND entry_actionability_methodology_version=?",
            (
                instrument_id, session_date.isoformat(),
                entry_qualification_as_of.isoformat(), decision_id,
                entry_qualification_methodology_version,
                entry_actionability_as_of.isoformat(),
                entry_actionability_methodology_version,
            ),
        )
        return ser.row_to_entry_actionability(row) if row else None

    def latest_entry_actionability_for_entry_qualification(
        self,
        *,
        instrument_id: str,
        session_date: date,
        entry_qualification_as_of: datetime,
        decision_id: str,
        entry_qualification_methodology_version: str,
    ) -> EntryActionability | None:
        """Most recent (latest ``entry_actionability_as_of``) observation
        bound to one *exact* upstream EntryQualification identity — never
        matched by ``decision_id`` alone (ID-7A authorization item 20).
        Does NOT resolve whether that EQ observation, or its bound
        Decision, is still the current one for its instrument — that
        selection remains the caller/workflow's responsibility (ID-7E).
        """
        row = self._query_one(
            f"SELECT {self._ENTRY_ACTIONABILITY_COLUMNS} FROM entry_actionabilities "
            "WHERE instrument_id=? AND session_date=? AND entry_qualification_as_of=? "
            "AND decision_id=? AND entry_qualification_methodology_version=? "
            "ORDER BY entry_actionability_as_of DESC, "
            "entry_actionability_methodology_version DESC LIMIT 1",
            (
                instrument_id, session_date.isoformat(),
                entry_qualification_as_of.isoformat(), decision_id,
                entry_qualification_methodology_version,
            ),
        )
        return ser.row_to_entry_actionability(row) if row else None

    def latest_entry_actionability_for_instrument_session(
        self, instrument_id: str, session_date: date
    ) -> EntryActionability | None:
        """Most recent historical observation for one instrument's trading
        session, across whichever EntryQualification/Decision pair(s) were
        evaluated that day. This is a latest-*historical* query, never a
        currently-usable one — a caller wanting a currentness verdict must
        separately evaluate ``entry_actionability_currentness.is_currently_usable``
        against whatever this returns."""
        row = self._query_one(
            f"SELECT {self._ENTRY_ACTIONABILITY_COLUMNS} FROM entry_actionabilities "
            "WHERE instrument_id=? AND session_date=? "
            "ORDER BY entry_actionability_as_of DESC, decision_id DESC, "
            "entry_actionability_methodology_version DESC LIMIT 1",
            (instrument_id, session_date.isoformat()),
        )
        return ser.row_to_entry_actionability(row) if row else None

    def list_entry_actionabilities_for_instrument_session(
        self, instrument_id: str, session_date: date
    ) -> list[EntryActionability]:
        """Full append-only observation history for one instrument/session,
        oldest first."""
        rows = self._query_all(
            f"SELECT {self._ENTRY_ACTIONABILITY_COLUMNS} FROM entry_actionabilities "
            "WHERE instrument_id=? AND session_date=? "
            "ORDER BY entry_actionability_as_of ASC, decision_id ASC, "
            "entry_actionability_methodology_version ASC",
            (instrument_id, session_date.isoformat()),
        )
        return [ser.row_to_entry_actionability(r) for r in rows]

    def save_journal_entry(self, entry: DecisionJournalEntry) -> None:
        self._write(
            "INSERT INTO decision_journal (entry_id, decision_ref, user_action, action_ts, notes) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(entry_id) DO UPDATE SET "
            "decision_ref=excluded.decision_ref, user_action=excluded.user_action, "
            "action_ts=excluded.action_ts, notes=excluded.notes",
            ser.journal_to_row(entry),
        )

    def list_journal(self, *, limit: int = 500) -> list[DecisionJournalEntry]:
        rows = self._query_all(
            "SELECT entry_id, decision_ref, user_action, action_ts, notes "
            "FROM decision_journal ORDER BY action_ts DESC, entry_id DESC LIMIT ?",
            (limit,),
        )
        return [ser.row_to_journal(r) for r in rows]

    def get_journal_entry(self, decision_ref: str) -> DecisionJournalEntry | None:
        """Most recent journal entry for one decision, or None if never recorded."""
        row = self._query_one(
            "SELECT entry_id, decision_ref, user_action, action_ts, notes "
            "FROM decision_journal WHERE decision_ref=? "
            "ORDER BY action_ts DESC, entry_id DESC LIMIT 1",
            (decision_ref,),
        )
        return ser.row_to_journal(row) if row else None

    def save_trade_outcome(self, outcome: TradeOutcome) -> None:
        self._write(
            "INSERT INTO trade_outcomes ("
            "outcome_id, decision_ref, entry_price, exit_price, quantity, pnl, "
            "holding_seconds, adherence_json, closed_ts"
            ") VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(outcome_id) DO UPDATE SET "
            "entry_price=excluded.entry_price, exit_price=excluded.exit_price, "
            "quantity=excluded.quantity, pnl=excluded.pnl, "
            "holding_seconds=excluded.holding_seconds, "
            "adherence_json=excluded.adherence_json, closed_ts=excluded.closed_ts",
            ser.trade_outcome_to_row(outcome),
        )

    def get_trade_outcome(self, decision_ref: str) -> TradeOutcome | None:
        """Most recent realized outcome for one decision, or None if never logged."""
        row = self._query_one(
            "SELECT outcome_id, decision_ref, entry_price, exit_price, quantity, pnl, "
            "holding_seconds, adherence_json, closed_ts "
            "FROM trade_outcomes WHERE decision_ref=? "
            "ORDER BY closed_ts DESC, outcome_id DESC LIMIT 1",
            (decision_ref,),
        )
        return ser.row_to_trade_outcome(row) if row else None

    def list_trade_outcomes(self, *, limit: int = 500) -> list[TradeOutcome]:
        rows = self._query_all(
            "SELECT outcome_id, decision_ref, entry_price, exit_price, quantity, pnl, "
            "holding_seconds, adherence_json, closed_ts "
            "FROM trade_outcomes ORDER BY closed_ts DESC, outcome_id DESC LIMIT ?",
            (limit,),
        )
        return [ser.row_to_trade_outcome(r) for r in rows]

    # ------------------------------------------------------------- owner positions (dashboard ledger)

    def save_owner_position(
        self,
        *,
        position_id: str,
        instrument_id: str,
        opened_ts: datetime,
        quantity: int,
        avg_price,
        closed_ts: datetime | None = None,
        exit_price=None,
        decision_ref: str | None = None,
        broker: str = "",
        notes: str = "",
        sector: str = "",
        meta: Mapping[str, object] | None = None,
    ) -> None:
        from decimal import Decimal as _Decimal

        avg = avg_price if isinstance(avg_price, _Decimal) else _Decimal(str(avg_price))
        exit_p = None
        if exit_price is not None:
            exit_p = (
                exit_price
                if isinstance(exit_price, _Decimal)
                else _Decimal(str(exit_price))
            )
        self._write(
            "INSERT INTO owner_positions ("
            "position_id, instrument_id, opened_ts, quantity, avg_price, "
            "closed_ts, exit_price, decision_ref, broker, notes, sector, meta_json"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(position_id) DO UPDATE SET "
            "instrument_id=excluded.instrument_id, opened_ts=excluded.opened_ts, "
            "quantity=excluded.quantity, avg_price=excluded.avg_price, "
            "closed_ts=excluded.closed_ts, exit_price=excluded.exit_price, "
            "decision_ref=excluded.decision_ref, broker=excluded.broker, "
            "notes=excluded.notes, sector=excluded.sector, meta_json=excluded.meta_json",
            ser.owner_position_to_row(
                position_id=position_id,
                instrument_id=instrument_id,
                opened_ts=opened_ts,
                quantity=quantity,
                avg_price=avg,
                closed_ts=closed_ts,
                exit_price=exit_p,
                decision_ref=decision_ref,
                broker=broker,
                notes=notes,
                sector=sector,
                meta=meta or {},
            ),
        )

    def get_owner_position(self, position_id: str) -> Position | None:
        row = self._query_one(
            "SELECT position_id, instrument_id, opened_ts, quantity, avg_price, "
            "closed_ts, exit_price, decision_ref, broker, notes, sector, meta_json "
            "FROM owner_positions WHERE position_id=?",
            (position_id,),
        )
        return ser.row_to_owner_position(row) if row else None

    def list_owner_positions(self, *, limit: int = 500) -> list[Position]:
        rows = self._query_all(
            "SELECT position_id, instrument_id, opened_ts, quantity, avg_price, "
            "closed_ts, exit_price, decision_ref, broker, notes, sector, meta_json "
            "FROM owner_positions ORDER BY opened_ts DESC, position_id DESC LIMIT ?",
            (limit,),
        )
        return [ser.row_to_owner_position(r) for r in rows]

    def delete_owner_positions(self, *, scope: str) -> int:
        """Delete owner fills. scope: 'open' (closed_ts IS NULL) or 'all'."""
        if scope not in ("open", "all"):
            raise RepositoryError(f"invalid owner position reset scope: {scope}")
        try:
            with self._lock:
                if scope == "open":
                    cur = self._conn.execute(
                        "DELETE FROM owner_positions WHERE closed_ts IS NULL"
                    )
                else:
                    cur = self._conn.execute("DELETE FROM owner_positions")
                self._conn.commit()
                return int(cur.rowcount)
        except sqlite3.Error as exc:
            raise RepositoryError(f"delete owner positions failed: {exc}") from exc

    # ------------------------------------------------------------- my portfolio (PS-P2)

    def save_portfolio_import_preview(
        self,
        *,
        import_id: str,
        filename: str,
        source: str,
        uploaded_at: datetime,
        holdings_as_of: datetime | None,
        parser_version: str,
        status: ImportStatus,
        total_rows: int,
        accepted_rows: int,
        rejected_rows: int,
        unresolved_rows: int,
        ambiguous_rows: int,
        provenance: Mapping[str, object],
        rows: Sequence[Mapping[str, object]],
    ) -> None:
        """Persist a My Portfolio import preview and its normalized rows."""

        if not isinstance(status, ImportStatus):
            raise RepositoryError(f"invalid portfolio import status: {status}")
        row_values = [
            (
                import_id,
                str(row["source_row_id"]),
                int(row["source_row_number"]),
                json.dumps(row.get("original_values", {}), sort_keys=True),
                str(row.get("normalized_symbol", "")),
                str(row.get("raw_symbol", "")),
                row.get("quantity"),
                None if row.get("avg_price") is None else str(row["avg_price"]),
                self._enum_value(row.get("mapping_state"), SymbolMappingState),
                row.get("resolved_instrument_id"),
                json.dumps(row.get("validation_errors", ()), sort_keys=True),
                json.dumps(row.get("warnings", ()), sort_keys=True),
                json.dumps(row.get("metadata", {}), sort_keys=True),
            )
            for row in rows
        ]
        try:
            with self._lock:
                with self._conn:
                    self._conn.execute(
                        "INSERT INTO portfolio_imports ("
                        "import_id, filename, source, uploaded_at, holdings_as_of, parser_version, "
                        "status, total_rows, accepted_rows, rejected_rows, unresolved_rows, "
                        "ambiguous_rows, provenance_json"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            import_id,
                            filename,
                            source,
                            uploaded_at.isoformat(),
                            holdings_as_of.isoformat() if holdings_as_of else None,
                            parser_version,
                            status.value,
                            total_rows,
                            accepted_rows,
                            rejected_rows,
                            unresolved_rows,
                            ambiguous_rows,
                            json.dumps(dict(provenance), sort_keys=True),
                        ),
                    )
                    self._conn.executemany(
                        "INSERT INTO portfolio_import_rows ("
                        "import_id, source_row_id, source_row_number, original_values_json, "
                        "normalized_symbol, raw_symbol, quantity, avg_price, mapping_state, "
                        "resolved_instrument_id, validation_errors_json, warnings_json, metadata_json"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        row_values,
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"save portfolio import preview failed: {exc}") from exc

    def get_portfolio_import(self, import_id: str) -> dict[str, object] | None:
        row = self._query_one(
            "SELECT import_id, filename, source, uploaded_at, holdings_as_of, parser_version, "
            "status, total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows, "
            "confirmed_at, provenance_json FROM portfolio_imports WHERE import_id=?",
            (import_id,),
        )
        return self._portfolio_import_from_row(row) if row else None

    def list_portfolio_imports(self, *, limit: int = 50) -> list[dict[str, object]]:
        rows = self._query_all(
            "SELECT import_id, filename, source, uploaded_at, holdings_as_of, parser_version, "
            "status, total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows, "
            "confirmed_at, provenance_json FROM portfolio_imports "
            "ORDER BY uploaded_at DESC, import_id DESC LIMIT ?",
            (limit,),
        )
        return [self._portfolio_import_from_row(row) for row in rows]

    def list_portfolio_import_rows(self, import_id: str) -> list[dict[str, object]]:
        rows = self._query_all(
            "SELECT import_id, source_row_id, source_row_number, original_values_json, "
            "normalized_symbol, raw_symbol, quantity, avg_price, mapping_state, "
            "resolved_instrument_id, validation_errors_json, warnings_json, metadata_json "
            "FROM portfolio_import_rows WHERE import_id=? "
            "ORDER BY source_row_number ASC, source_row_id ASC",
            (import_id,),
        )
        return [self._portfolio_import_row_from_row(row) for row in rows]

    def list_portfolio_holdings(self) -> list[CanonicalPortfolioHolding]:
        rows = self._query_all(
            "SELECT instrument_id, quantity, avg_price, imported_at, updated_at, "
            "source_import_id, source_row_id, provenance_json "
            "FROM portfolio_holdings ORDER BY instrument_id"
        )
        return [self._portfolio_holding_from_row(row) for row in rows]

    def get_portfolio_holding(self, instrument_id: str) -> CanonicalPortfolioHolding | None:
        row = self._query_one(
            "SELECT instrument_id, quantity, avg_price, imported_at, updated_at, "
            "source_import_id, source_row_id, provenance_json "
            "FROM portfolio_holdings WHERE instrument_id=?",
            (instrument_id,),
        )
        return self._portfolio_holding_from_row(row) if row else None

    def portfolio_holdings_digest(self) -> str:
        """Deterministic digest of current canonical My Portfolio holdings."""

        return self._holdings_digest(self.list_portfolio_holdings())

    def list_portfolio_reconciliations(self, import_id: str) -> list[dict[str, object]]:
        rows = self._query_all(
            "SELECT reconciliation_id, import_id, reconciled_at, action, instrument_id, "
            "before_json, after_json, provenance_json "
            "FROM portfolio_reconciliations WHERE import_id=? "
            "ORDER BY reconciled_at ASC, instrument_id ASC",
            (import_id,),
        )
        return [self._portfolio_reconciliation_from_row(row) for row in rows]

    def create_portfolio_sync_run(
        self,
        *,
        sync_run_id: str,
        started_at: datetime,
        total_holdings: int,
        analysis_version: str,
        status: SyncRunStatus = SyncRunStatus.QUEUED,
        progress: Mapping[str, object] | None = None,
        provenance: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Persist a new Portfolio Sync run record."""

        self._write(
            "INSERT INTO portfolio_sync_runs ("
            "sync_run_id, started_at, finished_at, status, total_holdings, "
            "succeeded_holdings, failed_holdings, market_data_through, "
            "validation_run_id, analysis_version, progress_json, per_symbol_json, "
            "error_json, provenance_json"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sync_run_id,
                started_at.isoformat(),
                None,
                status.value,
                total_holdings,
                0,
                0,
                None,
                None,
                analysis_version,
                json.dumps(dict(progress or {}), sort_keys=True, default=str),
                "{}",
                "{}",
                json.dumps(dict(provenance or {}), sort_keys=True, default=str),
            ),
        )
        record = self.get_portfolio_sync_run(sync_run_id)
        if record is None:
            raise RepositoryError("SYNC_RUN_NOT_FOUND_AFTER_CREATE")
        return record

    def update_portfolio_sync_run(
        self,
        sync_run_id: str,
        *,
        status: SyncRunStatus,
        finished_at: datetime | None = None,
        succeeded_holdings: int | None = None,
        failed_holdings: int | None = None,
        market_data_through: datetime | None = None,
        validation_run_id: str | None = None,
        progress: Mapping[str, object] | None = None,
        per_symbol: Mapping[str, object] | None = None,
        error: Mapping[str, object] | None = None,
        provenance: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Update a Portfolio Sync run record."""

        updates = ["status=?"]
        params: list[object] = [status.value]
        fields = {
            "finished_at": finished_at.isoformat() if finished_at is not None else None,
            "succeeded_holdings": succeeded_holdings,
            "failed_holdings": failed_holdings,
            "market_data_through": (
                market_data_through.isoformat() if market_data_through is not None else None
            ),
            "validation_run_id": validation_run_id,
            "progress_json": (
                json.dumps(dict(progress), sort_keys=True, default=str)
                if progress is not None
                else None
            ),
            "per_symbol_json": (
                json.dumps(dict(per_symbol), sort_keys=True, default=str)
                if per_symbol is not None
                else None
            ),
            "error_json": (
                json.dumps(dict(error), sort_keys=True, default=str)
                if error is not None
                else None
            ),
            "provenance_json": (
                json.dumps(dict(provenance), sort_keys=True, default=str)
                if provenance is not None
                else None
            ),
        }
        for column, value in fields.items():
            if value is None:
                continue
            updates.append(f"{column}=?")
            params.append(value)
        params.append(sync_run_id)
        self._write(
            f"UPDATE portfolio_sync_runs SET {', '.join(updates)} WHERE sync_run_id=?",
            tuple(params),
        )
        record = self.get_portfolio_sync_run(sync_run_id)
        if record is None:
            raise RepositoryError("SYNC_RUN_NOT_FOUND")
        return record

    def get_portfolio_sync_run(self, sync_run_id: str) -> dict[str, object] | None:
        row = self._query_one(
            "SELECT sync_run_id, started_at, finished_at, status, total_holdings, "
            "succeeded_holdings, failed_holdings, market_data_through, validation_run_id, "
            "analysis_version, progress_json, per_symbol_json, error_json, provenance_json "
            "FROM portfolio_sync_runs WHERE sync_run_id=?",
            (sync_run_id,),
        )
        return self._portfolio_sync_run_from_row(row) if row else None

    def get_active_portfolio_sync_run(self) -> dict[str, object] | None:
        row = self._query_one(
            "SELECT sync_run_id, started_at, finished_at, status, total_holdings, "
            "succeeded_holdings, failed_holdings, market_data_through, validation_run_id, "
            "analysis_version, progress_json, per_symbol_json, error_json, provenance_json "
            "FROM portfolio_sync_runs WHERE status IN (?,?) "
            "ORDER BY started_at DESC, sync_run_id DESC LIMIT 1",
            (SyncRunStatus.QUEUED.value, SyncRunStatus.RUNNING.value),
        )
        return self._portfolio_sync_run_from_row(row) if row else None

    def list_portfolio_sync_runs(self, *, limit: int = 50) -> list[dict[str, object]]:
        rows = self._query_all(
            "SELECT sync_run_id, started_at, finished_at, status, total_holdings, "
            "succeeded_holdings, failed_holdings, market_data_through, validation_run_id, "
            "analysis_version, progress_json, per_symbol_json, error_json, provenance_json "
            "FROM portfolio_sync_runs ORDER BY started_at DESC, sync_run_id DESC LIMIT ?",
            (limit,),
        )
        return [self._portfolio_sync_run_from_row(row) for row in rows]

    def mark_interrupted_portfolio_sync_runs(self, *, interrupted_at: datetime) -> int:
        """Fail stale QUEUED/RUNNING portfolio syncs from a previous process."""

        payload = json.dumps(
            {"code": "INTERRUPTED", "message": "Portfolio Sync interrupted before completion"},
            sort_keys=True,
        )
        try:
            with self._lock:
                with self._conn:
                    cur = self._conn.execute(
                        "UPDATE portfolio_sync_runs SET status=?, finished_at=?, error_json=? "
                        "WHERE status IN (?,?)",
                        (
                            SyncRunStatus.FAILED.value,
                            interrupted_at.isoformat(),
                            payload,
                            SyncRunStatus.QUEUED.value,
                            SyncRunStatus.RUNNING.value,
                        ),
                    )
                    return cur.rowcount or 0
        except sqlite3.Error as exc:
            raise RepositoryError(f"mark interrupted portfolio sync runs failed: {exc}") from exc

    def save_portfolio_analysis_snapshots(
        self,
        *,
        sync_run_id: str,
        rows: Sequence[Mapping[str, object]],
    ) -> None:
        """Persist immutable Portfolio Snapshot rows for one sync run."""

        payload = []
        for row in rows:
            payload.append(
                (
                    str(row["snapshot_id"]),
                    sync_run_id,
                    str(row["instrument_id"]),
                    str(row["symbol"]),
                    str(row["analyzed_at"]),
                    row.get("price_as_of"),
                    row.get("decision_as_of"),
                    row.get("market_data_through"),
                    str(row["analysis_version"]),
                    json.dumps(row["row"], sort_keys=True, default=str),
                    json.dumps(row["freshness"], sort_keys=True, default=str),
                    json.dumps(row["provenance"], sort_keys=True, default=str),
                    json.dumps(list(row.get("unavailable", [])), sort_keys=True, default=str),
                    json.dumps(list(row.get("failures", [])), sort_keys=True, default=str),
                )
            )
        try:
            with self._lock:
                with self._conn:
                    self._conn.executemany(
                        "INSERT INTO portfolio_analysis_snapshots ("
                        "snapshot_id, sync_run_id, instrument_id, symbol, analyzed_at, "
                        "price_as_of, decision_as_of, market_data_through, analysis_version, "
                        "row_json, freshness_json, provenance_json, unavailable_json, failure_json"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        payload,
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"save portfolio analysis snapshots failed: {exc}") from exc

    def list_portfolio_analysis_snapshots(
        self,
        sync_run_id: str,
    ) -> list[dict[str, object]]:
        rows = self._query_all(
            "SELECT snapshot_id, sync_run_id, instrument_id, symbol, analyzed_at, "
            "price_as_of, decision_as_of, market_data_through, analysis_version, "
            "row_json, freshness_json, provenance_json, unavailable_json, failure_json "
            "FROM portfolio_analysis_snapshots WHERE sync_run_id=? "
            "ORDER BY symbol ASC, snapshot_id ASC",
            (sync_run_id,),
        )
        return [self._portfolio_analysis_snapshot_from_row(row) for row in rows]

    def latest_portfolio_snapshot_sync_run(self) -> dict[str, object] | None:
        row = self._query_one(
            "SELECT r.sync_run_id, r.started_at, r.finished_at, r.status, r.total_holdings, "
            "r.succeeded_holdings, r.failed_holdings, r.market_data_through, "
            "r.validation_run_id, r.analysis_version, r.progress_json, r.per_symbol_json, "
            "r.error_json, r.provenance_json "
            "FROM portfolio_sync_runs r "
            "WHERE r.status IN (?,?) "
            "AND EXISTS (SELECT 1 FROM portfolio_analysis_snapshots s "
            "WHERE s.sync_run_id=r.sync_run_id) "
            "ORDER BY r.finished_at DESC, r.started_at DESC, r.sync_run_id DESC LIMIT 1",
            (SyncRunStatus.SUCCESS.value, SyncRunStatus.PARTIAL.value),
        )
        return self._portfolio_sync_run_from_row(row) if row else None

    def confirm_portfolio_import(
        self,
        *,
        import_id: str,
        expected_base_digest: str,
        confirmed_at: datetime,
    ) -> tuple[bool, tuple[ReconciliationChange, ...]]:
        """Atomically apply a clean persisted preview to canonical holdings.

        Returns ``(already_confirmed, changes)``. If the current holdings digest
        no longer matches the preview base, raises ``RepositoryError`` with a
        stable ``STALE_PREVIEW`` marker for the API layer.
        """

        try:
            with self._lock:
                with self._conn:
                    import_row = self._conn.execute(
                        "SELECT import_id, filename, source, uploaded_at, holdings_as_of, parser_version, "
                        "status, total_rows, accepted_rows, rejected_rows, unresolved_rows, ambiguous_rows, "
                        "confirmed_at, provenance_json FROM portfolio_imports WHERE import_id=?",
                        (import_id,),
                    ).fetchone()
                    if import_row is None:
                        raise RepositoryError("IMPORT_NOT_FOUND")
                    import_record = self._portfolio_import_from_row(import_row)
                    status = ImportStatus(str(import_record["status"]))
                    if status is ImportStatus.CONFIRMED:
                        existing_changes = tuple(
                            self._change_from_reconciliation(row)
                            for row in self.list_portfolio_reconciliations(import_id)
                        )
                        return True, existing_changes
                    if status is not ImportStatus.PREVIEWED:
                        raise RepositoryError("IMPORT_NOT_CONFIRMABLE")
                    if (
                        int(import_record["rejected_rows"])
                        or int(import_record["unresolved_rows"])
                        or int(import_record["ambiguous_rows"])
                    ):
                        raise RepositoryError("IMPORT_HAS_INVALID_ROWS")

                    current = {
                        holding.instrument_id: holding
                        for holding in self._list_portfolio_holdings_locked()
                    }
                    if self._holdings_digest(current.values()) != expected_base_digest:
                        raise RepositoryError("STALE_PREVIEW")

                    uploaded = self._uploaded_holdings_for_import_locked(import_id, confirmed_at)
                    if not uploaded:
                        raise RepositoryError("IMPORT_HAS_NO_HOLDINGS")
                    changes = reconcile_current_holdings(current, uploaded)
                    for index, change in enumerate(changes, start=1):
                        reconciliation_id = f"{import_id}-rec-{index:04d}"
                        self._conn.execute(
                            "INSERT INTO portfolio_reconciliations ("
                            "reconciliation_id, import_id, reconciled_at, action, instrument_id, "
                            "before_json, after_json, provenance_json"
                            ") VALUES (?,?,?,?,?,?,?,?)",
                            (
                                reconciliation_id,
                                import_id,
                                confirmed_at.isoformat(),
                                change.action.value,
                                change.instrument_id,
                                json.dumps(self._holding_to_json(change.before), sort_keys=True)
                                if change.before
                                else None,
                                json.dumps(self._holding_to_json(change.after), sort_keys=True)
                                if change.after
                                else None,
                                json.dumps({"base_digest": expected_base_digest}, sort_keys=True),
                            ),
                        )
                        if change.action is ReconciliationAction.REMOVED:
                            self._conn.execute(
                                "DELETE FROM portfolio_holdings WHERE instrument_id=?",
                                (change.instrument_id,),
                            )
                        elif change.action in (ReconciliationAction.ADDED, ReconciliationAction.UPDATED):
                            after = change.after
                            if after is None:
                                raise RepositoryError("RECONCILIATION_AFTER_MISSING")
                            self._conn.execute(
                                "INSERT INTO portfolio_holdings ("
                                "holding_id, instrument_id, quantity, avg_price, imported_at, updated_at, "
                                "source_import_id, source_row_id, reconciliation_id, provenance_json"
                                ") VALUES (?,?,?,?,?,?,?,?,?,?) "
                                "ON CONFLICT(instrument_id) DO UPDATE SET "
                                "quantity=excluded.quantity, avg_price=excluded.avg_price, "
                                "updated_at=excluded.updated_at, source_import_id=excluded.source_import_id, "
                                "source_row_id=excluded.source_row_id, "
                                "reconciliation_id=excluded.reconciliation_id, "
                                "provenance_json=excluded.provenance_json",
                                (
                                    f"hold-{after.instrument_id}",
                                    after.instrument_id,
                                    after.quantity,
                                    str(after.avg_price),
                                    after.imported_at.isoformat(),
                                    after.updated_at.isoformat(),
                                    after.source_import_id,
                                    after.source_row_id,
                                    reconciliation_id,
                                    json.dumps(dict(after.provenance), sort_keys=True),
                                ),
                            )
                    self._conn.execute(
                        "UPDATE portfolio_imports SET status=?, confirmed_at=? WHERE import_id=?",
                        (ImportStatus.CONFIRMED.value, confirmed_at.isoformat(), import_id),
                    )
                    return False, changes
        except sqlite3.Error as exc:
            raise RepositoryError(f"confirm portfolio import failed: {exc}") from exc

    def delete_decisions_data(self) -> dict[str, int]:
        """Owner-triggered full wipe of the Decisions & Trace domain: decisions,
        their reasoning traces, journal entries, and realized outcomes. Does
        not touch runs (shared with Market Intelligence's universe/regime
        history), portfolio positions, or owner candidates."""
        try:
            with self._lock:
                counts: dict[str, int] = {}
                # Children first (each REFERENCES decisions(decision_id)),
                # decisions last — deleting the parent first violates the
                # foreign key constraint.
                for table in ("decision_traces", "decision_journal", "trade_outcomes", "decisions"):
                    cur = self._conn.execute(f"DELETE FROM {table}")
                    counts[table] = int(cur.rowcount)
                self._conn.commit()
                return counts
        except sqlite3.Error as exc:
            raise RepositoryError(f"delete decisions data failed: {exc}") from exc

    # ------------------------------------------------------------- owner candidates (validation list)

    # ------------------------------------------------------- symbol master (SU-1)

    def upsert_symbol_records(self, records: Sequence[SymbolRecord]) -> int:
        """Upsert canonical symbol records. Idempotent by ``instrument_id``.

        ``first_seen`` is deliberately **not** overwritten on conflict: it
        records when a symbol was first catalogued, and resetting it on every
        refresh would erase the listing history the column exists to hold.
        ``last_seen`` is updated, which is what makes a disappeared symbol
        detectable later without deleting the row.
        """
        if not records:
            return 0
        self._write_many(
            "INSERT INTO symbol_master ("
            "instrument_id, symbol, exchange, name, series, series_source, board, "
            "lot_size, tick_size, status, first_seen, last_seen, source, "
            "classification_reason"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(instrument_id) DO UPDATE SET "
            "symbol=excluded.symbol, exchange=excluded.exchange, name=excluded.name, "
            "series=excluded.series, series_source=excluded.series_source, "
            "board=excluded.board, lot_size=excluded.lot_size, "
            "tick_size=excluded.tick_size, status=excluded.status, "
            "last_seen=excluded.last_seen, source=excluded.source, "
            "classification_reason=excluded.classification_reason",
            [
                (
                    r.instrument_id, r.symbol, r.exchange, r.name, r.series,
                    r.series_source.value, r.board.value, int(r.lot_size),
                    str(r.tick_size), r.status, r.first_seen.isoformat(),
                    r.last_seen.isoformat(), r.source, r.classification_reason,
                )
                for r in records
            ],
        )
        return len(records)

    def list_symbol_records(
        self,
        *,
        series: str | None = None,
        board: str | None = None,
        limit: int | None = None,
    ) -> list[SymbolRecord]:
        clause, params = "", []
        conditions = []
        if series is not None:
            conditions.append("series=?")
            params.append(series)
        if board is not None:
            conditions.append("board=?")
            params.append(board)
        if conditions:
            clause = " WHERE " + " AND ".join(conditions)
        clause += " ORDER BY instrument_id"
        if limit is not None:
            if limit < 1:
                raise ValueError(f"limit must be >= 1, got {limit}")
            clause += " LIMIT ?"
            params.append(limit)
        rows = self._query_all(
            "SELECT instrument_id, symbol, exchange, name, series, series_source, "
            "board, lot_size, tick_size, status, first_seen, last_seen, source, "
            f"classification_reason FROM symbol_master{clause}",
            tuple(params),
        )
        return [_row_to_symbol_record(row) for row in rows]

    def get_symbol_record(self, instrument_id: str) -> SymbolRecord | None:
        row = self._query_one(
            "SELECT instrument_id, symbol, exchange, name, series, series_source, "
            "board, lot_size, tick_size, status, first_seen, last_seen, source, "
            "classification_reason FROM symbol_master WHERE instrument_id=?",
            (instrument_id,),
        )
        return _row_to_symbol_record(row) if row else None

    def symbol_master_first_seen(self, instrument_id: str) -> datetime | None:
        """Existing ``first_seen`` for a symbol, so a rebuild can preserve it."""
        row = self._query_one(
            "SELECT first_seen FROM symbol_master WHERE instrument_id=?",
            (instrument_id,),
        )
        return datetime.fromisoformat(row[0]) if row else None

    # ----------------------------------------------------- resolved universe (SU-6)

    def save_resolved_universe(
        self, universe: str, instrument_ids: Sequence[str], *, resolved_at: datetime
    ) -> int:
        """Materialise a resolved universe so a scanner can read it as data.

        Replaces the previous membership for that universe in one transaction:
        a resolution is a complete statement of what the universe *is*, so
        leaving stale rows behind would let a scanner see symbols the current
        rules exclude.
        """
        stamp = resolved_at.isoformat()
        try:
            with self._lock:
                with self._conn:
                    self._conn.execute(
                        "DELETE FROM resolved_universe WHERE universe=?", (universe,)
                    )
                    self._conn.executemany(
                        "INSERT INTO resolved_universe (universe, instrument_id, "
                        "resolved_at) VALUES (?,?,?)",
                        [(universe, i, stamp) for i in instrument_ids],
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"resolved universe save failed: {exc}") from exc
        return len(instrument_ids)

    def list_resolved_universe(self, universe: str) -> list[str]:
        """Instrument ids in a materialised universe. Empty when never resolved."""
        rows = self._query_all(
            "SELECT instrument_id FROM resolved_universe WHERE universe=? "
            "ORDER BY instrument_id",
            (universe,),
        )
        return [r[0] for r in rows]

    # ------------------------------------------------------- candle coverage (SU-5)

    def candle_coverage(
        self, timeframe: Timeframe, instrument_ids: Sequence[str]
    ) -> dict[str, int]:
        """Bar counts per instrument for one timeframe.

        One grouped query rather than a count per symbol: a discovery universe
        is thousands of instruments, and asking individually would turn planning
        into the slow step it exists to avoid. Instruments with no candles are
        returned as ``0`` rather than omitted, so a caller cannot mistake
        "absent from the result" for "not requested".
        """
        if not instrument_ids:
            return {}
        counts = dict.fromkeys(instrument_ids, 0)
        # SQLite caps host parameters (999 on older builds), so chunk rather
        # than assume the universe fits in one statement.
        chunk_size = 500
        ids = list(instrument_ids)
        for start in range(0, len(ids), chunk_size):
            chunk = ids[start : start + chunk_size]
            marks = ",".join("?" * len(chunk))
            rows = self._query_all(
                f"SELECT instrument_id, COUNT(*) FROM candles "
                f"WHERE timeframe=? AND instrument_id IN ({marks}) "
                f"GROUP BY instrument_id",
                (timeframe.value, *chunk),
            )
            for instrument_id, count in rows:
                counts[instrument_id] = int(count)
        return counts

    # ------------------------------------------------------ group membership (SU-2)

    def upsert_group_memberships(self, memberships: Sequence[GroupMembership]) -> int:
        """Upsert dated group memberships. Idempotent per (symbol, group, date).

        Re-running a snapshot load rewrites that date's rows in place rather than
        accumulating duplicates, while a *new* effective date adds rows beside
        the old ones — which is what keeps a pre-rebalance screen reproducible.
        """
        if not memberships:
            return 0
        self._write_many(
            "INSERT INTO symbol_group (instrument_id, group_name, kind, "
            "effective_date, source) VALUES (?,?,?,?,?) "
            "ON CONFLICT(instrument_id, group_name, effective_date) DO UPDATE SET "
            "kind=excluded.kind, source=excluded.source",
            [
                (
                    m.instrument_id, m.group_name, m.kind.value,
                    m.effective_date.isoformat(), m.source,
                )
                for m in memberships
            ],
        )
        return len(memberships)

    def latest_group_effective_date(self, group_name: str) -> date | None:
        """Most recent effective date recorded for a group, if any."""
        row = self._query_one(
            "SELECT MAX(effective_date) FROM symbol_group WHERE group_name=?",
            (group_name,),
        )
        return date.fromisoformat(row[0]) if row and row[0] else None

    def list_group_members(
        self, group_name: str, *, as_of: date | None = None
    ) -> list[str]:
        """Instrument ids in a group, at its latest effective date by default.

        Passing ``as_of`` returns membership as it stood then — the whole reason
        membership is dated. Returns ``[]`` for an unknown group rather than
        raising: "this group has no members" is a legitimate answer, and a
        resolver asking about a group nobody has loaded yet should get an empty
        universe, not an exception.
        """
        if as_of is None:
            effective = self.latest_group_effective_date(group_name)
            if effective is None:
                return []
        else:
            row = self._query_one(
                "SELECT MAX(effective_date) FROM symbol_group "
                "WHERE group_name=? AND effective_date<=?",
                (group_name, as_of.isoformat()),
            )
            if not row or not row[0]:
                return []
            effective = date.fromisoformat(row[0])
        rows = self._query_all(
            "SELECT instrument_id FROM symbol_group "
            "WHERE group_name=? AND effective_date=? ORDER BY instrument_id",
            (group_name, effective.isoformat()),
        )
        return [r[0] for r in rows]

    def list_groups_for_symbol(self, instrument_id: str) -> list[tuple[str, date]]:
        """Every ``(group, effective_date)`` a symbol currently belongs to."""
        rows = self._query_all(
            "SELECT group_name, MAX(effective_date) FROM symbol_group "
            "WHERE instrument_id=? GROUP BY group_name ORDER BY group_name",
            (instrument_id,),
        )
        return [(r[0], date.fromisoformat(r[1])) for r in rows]

    def list_known_groups(self) -> list[str]:
        rows = self._query_all(
            "SELECT DISTINCT group_name FROM symbol_group ORDER BY group_name", ()
        )
        return [r[0] for r in rows]

    def upsert_owner_candidate(
        self,
        *,
        symbol: str,
        added_ts: datetime,
        notes: str = "",
        active: bool = True,
    ) -> None:
        self._write(
            "INSERT INTO owner_candidates (symbol, added_ts, notes, active) VALUES (?,?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "added_ts=excluded.added_ts, notes=excluded.notes, active=excluded.active",
            (symbol, added_ts.isoformat(), notes or "", 1 if active else 0),
        )

    def delete_owner_candidate(self, symbol: str) -> bool:
        try:
            with self._lock:
                cur = self._conn.execute(
                    "DELETE FROM owner_candidates WHERE symbol=?", (symbol,)
                )
                self._conn.commit()
                return int(cur.rowcount) > 0
        except sqlite3.Error as exc:
            raise RepositoryError(f"delete owner candidate failed: {exc}") from exc

    def list_owner_candidates(self, *, active_only: bool = True) -> list[tuple[str, datetime, str, bool]]:
        if active_only:
            rows = self._query_all(
                "SELECT symbol, added_ts, notes, active FROM owner_candidates "
                "WHERE active=1 ORDER BY symbol"
            )
        else:
            rows = self._query_all(
                "SELECT symbol, added_ts, notes, active FROM owner_candidates ORDER BY symbol"
            )
        return [
            (r[0], datetime.fromisoformat(r[1]), r[2] or "", bool(r[3]))
            for r in rows
        ]

    # ------------------------------------------------------------- saved symbols (owner watchlist)

    def add_saved_symbol(
        self,
        *,
        symbol: str,
        added_ts: datetime,
        notes: str = "",
    ) -> None:
        self._write(
            "INSERT INTO saved_symbols (symbol, added_ts, notes) VALUES (?,?,?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "added_ts=excluded.added_ts, notes=excluded.notes",
            (symbol, added_ts.isoformat(), notes or ""),
        )

    def remove_saved_symbol(self, symbol: str) -> bool:
        try:
            with self._lock:
                cur = self._conn.execute(
                    "DELETE FROM saved_symbols WHERE symbol=?", (symbol,)
                )
                self._conn.commit()
                return int(cur.rowcount) > 0
        except sqlite3.Error as exc:
            raise RepositoryError(f"remove saved symbol failed: {exc}") from exc

    def list_saved_symbols(self) -> list[tuple[str, datetime, str]]:
        rows = self._query_all(
            "SELECT symbol, added_ts, notes FROM saved_symbols ORDER BY added_ts DESC"
        )
        return [(r[0], datetime.fromisoformat(r[1]), r[2] or "") for r in rows]

    def get_ops_meta(self, key: str) -> str | None:
        row = self._query_one("SELECT value FROM ops_meta WHERE key=?", (key,))
        return None if row is None else str(row[0])

    def set_ops_meta(self, key: str, value: str, *, updated_ts: datetime | None = None) -> None:
        ts = (updated_ts or datetime.now()).isoformat()
        self._write(
            "INSERT INTO ops_meta (key, value, updated_ts) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
            (key, value, ts),
        )

    def list_candles_recent(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        *,
        limit: int = 500,
        as_of: datetime | None = None,
    ) -> list[Candle]:
        """The most recent `limit` candles, oldest-first.

        `as_of` (ID-5E, market-time point-in-time safety): when given, only
        candles with `ts_open<=as_of` are eligible -- applied in SQL BEFORE
        `ORDER BY ... LIMIT`, never as a Python filter after. Filtering
        after the fact would let candles dated after `as_of` (present in
        the database from later ingestion, e.g. during a historical replay
        of an earlier `as_of`) consume LIMIT slots that a correct query
        would have given to genuinely earlier rows -- silently starving a
        replay of real historical data it should have seen. `as_of=None`
        (the default) preserves the exact pre-ID-5E behavior byte-for-byte
        for every existing live-current-state caller.

        This bounds MARKET-TIME (`ts_open`) only -- it says nothing about
        when a row was actually persisted/known to ATHENA (knowledge-time/
        bitemporal replay), which this schema does not track. Analytical
        completed-candle semantics (`athena.session.completed_candles`)
        remain a separate, still-required concern: a row can satisfy this
        market-time cutoff and still be a forming bar.
        """
        if as_of is not None:
            if as_of.tzinfo is None:
                raise ValueError("list_candles_recent as_of must be timezone-aware")
            rows = self._query_all(
                "SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume, "
                "source, adjusted FROM candles WHERE instrument_id=? AND timeframe=? "
                "AND ts_open<=? ORDER BY ts_open DESC LIMIT ?",
                (instrument_id, timeframe.value, as_of.isoformat(), limit),
            )
        else:
            rows = self._query_all(
                "SELECT instrument_id, timeframe, ts_open, open, high, low, close, volume, source, "
                "adjusted FROM candles WHERE instrument_id=? AND timeframe=? "
                "ORDER BY ts_open DESC LIMIT ?",
                (instrument_id, timeframe.value, limit),
            )
        candles = [ser.row_to_candle(r) for r in rows]
        candles.reverse()
        return candles

    # ------------------------------------------------------------- integrity

    def verify_integrity(self) -> IntegrityReport:
        try:
            with self._lock:
                integrity = str(self._conn.execute("PRAGMA integrity_check").fetchone()[0])
                fk_violations = self._conn.execute("PRAGMA foreign_key_check").fetchall()
                version_row = self._conn.execute("SELECT version FROM schema_version").fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"integrity verification failed: {exc}") from exc

        version_ok = version_row is not None and int(version_row[0]) == SCHEMA_VERSION
        issues: list[str] = []
        if integrity != "ok":
            issues.append(f"integrity_check reported: {integrity}")
        if fk_violations:
            issues.append(f"{len(fk_violations)} foreign key violation(s)")
        if not version_ok:
            issues.append(
                f"schema version mismatch: found {version_row[0] if version_row else None}, "
                f"expected {SCHEMA_VERSION}")
        return IntegrityReport(
            ok=not issues, integrity_check=integrity,
            foreign_key_violations=len(fk_violations), schema_version_ok=version_ok,
            issues=tuple(issues),
        )

    # ------------------------------------------------------------- internals

    def _list_portfolio_holdings_locked(self) -> list[CanonicalPortfolioHolding]:
        rows = self._conn.execute(
            "SELECT instrument_id, quantity, avg_price, imported_at, updated_at, "
            "source_import_id, source_row_id, provenance_json "
            "FROM portfolio_holdings ORDER BY instrument_id"
        ).fetchall()
        return [self._portfolio_holding_from_row(row) for row in rows]

    def _uploaded_holdings_for_import_locked(
        self,
        import_id: str,
        confirmed_at: datetime,
    ) -> dict[str, CanonicalPortfolioHolding]:
        rows = self._conn.execute(
            "SELECT import_id, source_row_id, source_row_number, original_values_json, "
            "normalized_symbol, raw_symbol, quantity, avg_price, mapping_state, "
            "resolved_instrument_id, validation_errors_json, warnings_json, metadata_json "
            "FROM portfolio_import_rows WHERE import_id=? "
            "ORDER BY source_row_number ASC, source_row_id ASC",
            (import_id,),
        ).fetchall()
        holdings: dict[str, CanonicalPortfolioHolding] = {}
        for row in rows:
            item = self._portfolio_import_row_from_row(row)
            errors = tuple(item["validation_errors"])
            mapping_state = SymbolMappingState(str(item["mapping_state"]))
            if errors or mapping_state is not SymbolMappingState.RESOLVED:
                raise RepositoryError("IMPORT_HAS_INVALID_ROWS")
            instrument_id = str(item["resolved_instrument_id"])
            if instrument_id in holdings:
                raise RepositoryError("DUPLICATE_CANONICAL_INSTRUMENT")
            holdings[instrument_id] = CanonicalPortfolioHolding(
                instrument_id=instrument_id,
                quantity=int(item["quantity"]),
                avg_price=Decimal(str(item["avg_price"])),
                imported_at=confirmed_at,
                updated_at=confirmed_at,
                source_import_id=import_id,
                source_row_id=str(item["source_row_id"]),
                provenance={
                    "source_row_number": item["source_row_number"],
                    "raw_symbol": item["raw_symbol"],
                    "normalized_symbol": item["normalized_symbol"],
                },
            )
        return holdings

    def _holdings_digest(self, holdings: Iterable[CanonicalPortfolioHolding]) -> str:
        import hashlib

        payload = [
            {
                "instrument_id": holding.instrument_id,
                "quantity": holding.quantity,
                "avg_price": str(holding.avg_price),
            }
            for holding in sorted(holdings, key=lambda item: item.instrument_id)
        ]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _portfolio_import_from_row(self, row: tuple) -> dict[str, object]:
        return {
            "import_id": row[0],
            "filename": row[1],
            "source": row[2],
            "uploaded_at": datetime.fromisoformat(row[3]),
            "holdings_as_of": datetime.fromisoformat(row[4]) if row[4] else None,
            "parser_version": row[5],
            "status": row[6],
            "total_rows": int(row[7]),
            "accepted_rows": int(row[8]),
            "rejected_rows": int(row[9]),
            "unresolved_rows": int(row[10]),
            "ambiguous_rows": int(row[11]),
            "confirmed_at": datetime.fromisoformat(row[12]) if row[12] else None,
            "provenance": json.loads(row[13] or "{}"),
        }

    def _portfolio_import_row_from_row(self, row: tuple) -> dict[str, object]:
        return {
            "import_id": row[0],
            "source_row_id": row[1],
            "source_row_number": int(row[2]),
            "original_values": json.loads(row[3] or "{}"),
            "normalized_symbol": row[4],
            "raw_symbol": row[5],
            "quantity": int(row[6]) if row[6] is not None else None,
            "avg_price": Decimal(str(row[7])) if row[7] is not None else None,
            "mapping_state": row[8],
            "resolved_instrument_id": row[9],
            "validation_errors": tuple(json.loads(row[10] or "[]")),
            "warnings": tuple(json.loads(row[11] or "[]")),
            "metadata": json.loads(row[12] or "{}"),
        }

    def _portfolio_holding_from_row(self, row: tuple) -> CanonicalPortfolioHolding:
        return CanonicalPortfolioHolding(
            instrument_id=row[0],
            quantity=int(row[1]),
            avg_price=Decimal(str(row[2])),
            imported_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
            source_import_id=row[5],
            source_row_id=row[6],
            provenance=json.loads(row[7] or "{}"),
        )

    def _portfolio_reconciliation_from_row(self, row: tuple) -> dict[str, object]:
        return {
            "reconciliation_id": row[0],
            "import_id": row[1],
            "reconciled_at": datetime.fromisoformat(row[2]),
            "action": row[3],
            "instrument_id": row[4],
            "before": json.loads(row[5]) if row[5] else None,
            "after": json.loads(row[6]) if row[6] else None,
            "provenance": json.loads(row[7] or "{}"),
        }

    def _portfolio_sync_run_from_row(self, row: tuple) -> dict[str, object]:
        return {
            "sync_run_id": row[0],
            "started_at": datetime.fromisoformat(row[1]),
            "finished_at": datetime.fromisoformat(row[2]) if row[2] else None,
            "status": row[3],
            "total_holdings": int(row[4]),
            "succeeded_holdings": int(row[5]),
            "failed_holdings": int(row[6]),
            "market_data_through": datetime.fromisoformat(row[7]) if row[7] else None,
            "validation_run_id": row[8],
            "analysis_version": row[9],
            "progress": json.loads(row[10] or "{}"),
            "per_symbol": json.loads(row[11] or "{}"),
            "error": json.loads(row[12] or "{}"),
            "provenance": json.loads(row[13] or "{}"),
        }

    def _portfolio_analysis_snapshot_from_row(self, row: tuple) -> dict[str, object]:
        return {
            "snapshot_id": row[0],
            "sync_run_id": row[1],
            "instrument_id": row[2],
            "symbol": row[3],
            "analyzed_at": datetime.fromisoformat(row[4]),
            "price_as_of": datetime.fromisoformat(row[5]) if row[5] else None,
            "decision_as_of": datetime.fromisoformat(row[6]) if row[6] else None,
            "market_data_through": datetime.fromisoformat(row[7]) if row[7] else None,
            "analysis_version": row[8],
            "row": json.loads(row[9] or "{}"),
            "freshness": json.loads(row[10] or "{}"),
            "provenance": json.loads(row[11] or "{}"),
            "unavailable": tuple(json.loads(row[12] or "[]")),
            "failures": tuple(json.loads(row[13] or "[]")),
        }

    def _change_from_reconciliation(self, row: Mapping[str, object]) -> ReconciliationChange:
        return ReconciliationChange(
            instrument_id=str(row["instrument_id"]),
            action=ReconciliationAction(str(row["action"])),
            before=None,
            after=None,
        )

    def _holding_to_json(self, holding: CanonicalPortfolioHolding | None) -> dict[str, object] | None:
        if holding is None:
            return None
        return {
            "instrument_id": holding.instrument_id,
            "quantity": holding.quantity,
            "avg_price": str(holding.avg_price),
            "imported_at": holding.imported_at.isoformat(),
            "updated_at": holding.updated_at.isoformat(),
            "source_import_id": holding.source_import_id,
            "source_row_id": holding.source_row_id,
            "provenance": dict(holding.provenance),
        }

    def _enum_value(self, value: object, enum_type: type[Enum]) -> str:
        if isinstance(value, enum_type):
            return str(value.value)
        return str(enum_type(str(value)).value)

    def _write(self, sql: str, params: tuple) -> None:
        try:
            with self._lock:
                with self._conn:
                    self._conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"write failed: {exc}") from exc

    def _write_many(self, sql: str, rows: Sequence[tuple]) -> None:
        try:
            with self._lock:
                with self._conn:
                    self._conn.executemany(sql, rows)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"write failed: {exc}") from exc

    def _read_connection(self) -> sqlite3.Connection:
        """ADR-009: the calling thread's own lazily-created, read-only
        connection (``mode=ro`` — physically incapable of writing, not just
        by convention). Created on first use per thread and reused for the
        thread's lifetime; never shared across threads (``threading.local``
        guarantees this). Opening it here, on first actual read rather than
        at repository construction, means it only ever opens after
        ``initialize()`` has already run schema setup on the write
        connection.

        Not used for an in-memory (``:memory:``) database: a second
        connection to ``:memory:`` is a distinct, empty database, not
        another handle onto the same one — there is no file to attach a
        read-only connection to. ``_query_one``/``_query_all`` detect this
        and fall back to the shared write connection/lock instead, exactly
        as before ADR-009. This only affects the small number of
        deliberately throwaway, single-use, in-process shadow repos this
        codebase creates (e.g. config-preview and canary replay) — the
        concurrency benefit this ADR targets is for the real, file-backed
        database FastAPI and the scheduler share.
        """
        conn = getattr(self._read_local, "conn", None)
        if conn is None:
            try:
                conn = sqlite3.connect(
                    f"file:{self._path}?mode=ro", uri=True, check_same_thread=True
                )
            except sqlite3.Error as exc:
                raise RepositoryError(
                    f"cannot open read connection at {self._path}: {exc}"
                ) from exc
            self._read_local.conn = conn
        return conn

    def _query_one(self, sql: str, params: tuple) -> tuple | None:
        try:
            if self._path == ":memory:":
                with self._lock:
                    return self._conn.execute(sql, params).fetchone()
            return self._read_connection().execute(sql, params).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"query failed: {exc}") from exc

    def _query_all(self, sql: str, params: tuple = ()) -> list[tuple]:
        try:
            if self._path == ":memory:":
                with self._lock:
                    return self._conn.execute(sql, params).fetchall()
            return self._read_connection().execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"query failed: {exc}") from exc
