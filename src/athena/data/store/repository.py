"""SqliteRepository — ATHENA's persistent ledger (M1.5).

Persistence is its ONLY responsibility. It contains no provider, validation, or
market-intelligence logic; it stores and returns canonical domain objects with
transaction safety, WAL mode, and enforced foreign keys.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from athena.data.store import serialization as ser
from athena.data.store.schema import SCHEMA_VERSION, ddl_statements
from athena.data.validation.quarantine import QuarantineRecord
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, CorporateAction, Instrument, MarketSnapshot, Quote
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
    """A trusted local ledger over a single SQLite file."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        try:
            self._conn = sqlite3.connect(self._path, isolation_level="DEFERRED")
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as exc:
            raise RepositoryError(f"cannot open database at {self._path}: {exc}") from exc

    # ------------------------------------------------------------- lifecycle

    def initialize(self) -> None:
        """Create the schema (idempotent) and record/upgrade the schema version."""
        try:
            with self._conn:
                for statement in ddl_statements():
                    self._conn.execute(statement)
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

    def close(self) -> None:
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
        """The live connection. Intended for maintenance (online backup) only."""
        return self._conn

    def record_counts(self) -> dict[str, int]:
        """Row counts per persisted table — used for backup/restore recovery checks."""
        tables = ("instruments", "candles", "quotes", "market_snapshots",
                  "corporate_actions", "quarantine_records", "runs")
        try:
            return {t: int(self._conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
                    for t in tables}
        except sqlite3.Error as exc:
            raise RepositoryError(f"record count query failed: {exc}") from exc

    @property
    def journal_mode(self) -> str:
        return str(self._conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    @property
    def foreign_keys_enabled(self) -> bool:
        return bool(self._conn.execute("PRAGMA foreign_keys").fetchone()[0])

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        """Explicit transaction: commit on success, rollback on any exception."""
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
            "(instrument_id, isin, symbol, exchange, series, lot_size, tick_size, status, "
            " listed_date, delisted_date) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(instrument_id) DO UPDATE SET "
            "isin=excluded.isin, symbol=excluded.symbol, exchange=excluded.exchange, "
            "series=excluded.series, lot_size=excluded.lot_size, tick_size=excluded.tick_size, "
            "status=excluded.status, listed_date=excluded.listed_date, "
            "delisted_date=excluded.delisted_date",
            ser.instrument_to_row(instrument),
        )

    def get_instrument(self, instrument_id: str) -> Instrument | None:
        row = self._query_one(
            "SELECT instrument_id, isin, symbol, exchange, series, lot_size, tick_size, "
            "status, listed_date, delisted_date FROM instruments WHERE instrument_id=?",
            (instrument_id,),
        )
        return ser.row_to_instrument(row) if row else None

    def list_instruments(self) -> list[Instrument]:
        rows = self._query_all(
            "SELECT instrument_id, isin, symbol, exchange, series, lot_size, tick_size, "
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

    # ------------------------------------------------------------- integrity

    def verify_integrity(self) -> IntegrityReport:
        try:
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
            with self._conn:
                self._conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"write failed: {exc}") from exc

    def _write_many(self, sql: str, rows: Sequence[tuple]) -> None:
        try:
            with self._conn:
                self._conn.executemany(sql, rows)
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"integrity violation: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"write failed: {exc}") from exc

    def _query_one(self, sql: str, params: tuple) -> tuple | None:
        try:
            return self._conn.execute(sql, params).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"query failed: {exc}") from exc

    def _query_all(self, sql: str, params: tuple = ()) -> list[tuple]:
        try:
            return self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"query failed: {exc}") from exc
