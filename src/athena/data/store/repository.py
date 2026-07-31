"""SqliteRepository — ATHENA's persistent ledger (M1.5).

Persistence is its ONLY responsibility. It contains no provider, validation, or
market-intelligence logic; it stores and returns canonical domain objects with
transaction safety, WAL mode, and enforced foreign keys.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
    Instrument,
    InstitutionalFlowSession,
    MarketSnapshot,
    Quote,
)
from athena.domain.run import RunRecord
from athena.errors import RepositoryError


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Result of a repository integrity verification. Immutable and explainable."""

    ok: bool
    integrity_check: str
    foreign_key_violations: int
    schema_version_ok: bool
    issues: tuple[str, ...] = ()


class SqliteRepository:
    """A trusted local ledger over a single SQLite file.

    The connection is created with ``check_same_thread=False`` so FastAPI (and
    other multi-threaded callers) may share one repository instance. All access
    is serialized through an ``RLock`` because a sqlite3 connection is not
    otherwise thread-safe.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._lock = threading.RLock()
        try:
            # check_same_thread=False: API process opens repo at startup, then
            # request threads reuse it. Access is still serialized via _lock.
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

    def close(self) -> None:
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
                  "owner_positions", "owner_candidates", "saved_symbols", "ops_meta")
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
        rows = [ser.candle_to_row(c) for c in candles]
        self._write_many(
            "INSERT INTO candles "
            "(instrument_id, timeframe, ts_open, open, high, low, close, volume, source, adjusted) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        return len(rows)

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

    # ------------------------------------------------------------- market snapshots

    def add_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._write(
            "INSERT INTO market_snapshots (ts, payload_json) VALUES (?,?)",
            (snapshot.ts.isoformat(), ser.snapshot_to_payload(snapshot)),
        )

    def get_latest_snapshot(self) -> MarketSnapshot | None:
        row = self._query_one(
            "SELECT payload_json FROM market_snapshots ORDER BY ts DESC LIMIT 1", ()
        )
        return ser.payload_to_snapshot(row[0]) if row else None

    def get_latest_snapshot_before(self, before: datetime) -> MarketSnapshot | None:
        """Return the newest persisted snapshot strictly before ``before``."""
        row = self._query_one(
            "SELECT payload_json FROM market_snapshots "
            "WHERE datetime(ts) < datetime(?) ORDER BY datetime(ts) DESC LIMIT 1",
            (before.isoformat(),),
        )
        return ser.payload_to_snapshot(row[0]) if row else None

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
    ) -> list[Candle]:
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

    def _query_one(self, sql: str, params: tuple) -> tuple | None:
        try:
            with self._lock:
                return self._conn.execute(sql, params).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"query failed: {exc}") from exc

    def _query_all(self, sql: str, params: tuple = ()) -> list[tuple]:
        try:
            with self._lock:
                return self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"query failed: {exc}") from exc
