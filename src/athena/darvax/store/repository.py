"""DarvaX's own ledger over its own SQLite file (ADR-010 §2).

Separate file, separate connection, separate schema version. Nothing here can
reach ``db/athena.db``, so DarvaX writes can never contend with ATHENA's write
connection/``RLock`` (ADR-009 is unaffected) and deleting one file removes every
trace of DarvaX's data.

Creation is lazy and enable-gated: ``initialize()`` runs only from the mounted
DarvaX sub-application, which is itself only constructed when
``enabled: true``. With DarvaX disabled the file is never created or opened
(ADR-010 DX-1 acceptance test 3).
"""

from __future__ import annotations

import json as _json
import sqlite3
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from athena.darvax.signals.models import (
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
    DarvaxStop,
    SignalEvidence,
    StopBasis,
)
from athena.darvax.store.schema import DARVAX_SCHEMA_VERSION, darvax_ddl_statements
from athena.errors import RepositoryError


def _optional_decimal(raw: str | None) -> Decimal | None:
    return Decimal(raw) if raw is not None else None


def _row_to_signal(row: tuple) -> DarvaxSignal:
    """Rehydrate a persisted signal. Explanation and evidence are read back as
    stored — never recomputed, per ADR-005's explainability-as-data principle."""
    stop = None
    if row[10] is not None:
        payload = _json.loads(row[10])
        stop = DarvaxStop(
            basis=StopBasis(payload["basis"]),
            price=Decimal(payload["price"]),
            reference_price=Decimal(payload["reference_price"]),
            detail=payload["detail"],
            ema_period=payload["ema_period"],
            pct=_optional_decimal(payload["pct"]),
        )
    evidence = tuple(
        SignalEvidence(name=e["name"], value=e["value"], detail=e["detail"])
        for e in _json.loads(row[12])
    )
    return DarvaxSignal(
        signal_id=row[0],
        instrument_id=row[1],
        as_of=datetime.fromisoformat(row[2]),
        signal_type=DarvaxSignalType(row[3]),
        darvas_rule=DarvasRule(row[4]) if row[4] else None,
        close=Decimal(row[5]),
        box_top=_optional_decimal(row[6]),
        box_bottom=_optional_decimal(row[7]),
        box_is_topmost=None if row[8] is None else bool(row[8]),
        trigger_price=_optional_decimal(row[9]),
        stop=stop,
        explanation=row[11],
        evidence=evidence,
        methodology_digest=row[13],
        darvax_version=row[14],
        status=row[15],
    )


class DarvaxRepository:
    """Minimal DX-1 ledger: opens/creates ``darvax.db`` and records its version."""

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
                self._conn = sqlite3.connect(
                    self._path, isolation_level="DEFERRED", check_same_thread=False
                )
                self._conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.Error as exc:
                raise RepositoryError(
                    f"cannot open DarvaX database at {self._path}: {exc}"
                ) from exc
        return self._conn

    def initialize(self) -> None:
        """Create DarvaX's schema (idempotent) and record its own version."""
        try:
            with self._lock:
                conn = self._connect()
                with conn:
                    for statement in darvax_ddl_statements():
                        conn.execute(statement)
                    row = conn.execute(
                        "SELECT version FROM darvax_schema_version"
                    ).fetchone()
                    if row is None:
                        conn.execute(
                            "INSERT INTO darvax_schema_version(version) VALUES (?)",
                            (DARVAX_SCHEMA_VERSION,),
                        )
                    elif int(row[0]) < DARVAX_SCHEMA_VERSION:
                        conn.execute(
                            "UPDATE darvax_schema_version SET version = ?",
                            (DARVAX_SCHEMA_VERSION,),
                        )
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX schema initialization failed: {exc}") from exc

    # ----------------------------------------------------------- signals (DX-3)

    def save_signal(self, signal: DarvaxSignal) -> None:
        """Upsert one DarvaX signal, explanation and evidence included.

        Idempotent by ``signal_id`` (instrument + bar timestamp), so replaying
        the engine over the same candles updates the row in place rather than
        accumulating duplicates.
        """
        stop_json = (
            _json.dumps(
                {
                    "basis": signal.stop.basis.value,
                    "price": str(signal.stop.price),
                    "reference_price": str(signal.stop.reference_price),
                    "detail": signal.stop.detail,
                    "ema_period": signal.stop.ema_period,
                    "pct": str(signal.stop.pct) if signal.stop.pct is not None else None,
                },
                sort_keys=True,
            )
            if signal.stop is not None
            else None
        )
        evidence_json = _json.dumps(
            [
                {"name": e.name, "value": e.value, "detail": e.detail}
                for e in signal.evidence
            ],
            sort_keys=True,
        )
        try:
            with self._lock:
                conn = self._connect()
                with conn:
                    conn.execute(
                        "INSERT INTO darvax_signals ("
                        "signal_id, instrument_id, as_of, signal_type, darvas_rule, "
                        "close, box_top, box_bottom, box_is_topmost, trigger_price, "
                        "stop_json, explanation, evidence_json, methodology_digest, "
                        "darvax_version, status"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(signal_id) DO UPDATE SET "
                        "instrument_id=excluded.instrument_id, as_of=excluded.as_of, "
                        "signal_type=excluded.signal_type, "
                        "darvas_rule=excluded.darvas_rule, close=excluded.close, "
                        "box_top=excluded.box_top, box_bottom=excluded.box_bottom, "
                        "box_is_topmost=excluded.box_is_topmost, "
                        "trigger_price=excluded.trigger_price, "
                        "stop_json=excluded.stop_json, "
                        "explanation=excluded.explanation, "
                        "evidence_json=excluded.evidence_json, "
                        "methodology_digest=excluded.methodology_digest, "
                        "darvax_version=excluded.darvax_version, "
                        "status=excluded.status",
                        (
                            signal.signal_id,
                            signal.instrument_id,
                            signal.as_of.isoformat(),
                            signal.signal_type.value,
                            signal.darvas_rule.value if signal.darvas_rule else None,
                            str(signal.close),
                            str(signal.box_top) if signal.box_top is not None else None,
                            str(signal.box_bottom)
                            if signal.box_bottom is not None
                            else None,
                            None
                            if signal.box_is_topmost is None
                            else int(signal.box_is_topmost),
                            str(signal.trigger_price)
                            if signal.trigger_price is not None
                            else None,
                            stop_json,
                            signal.explanation,
                            evidence_json,
                            signal.methodology_digest,
                            signal.darvax_version,
                            signal.status,
                        ),
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX signal write failed: {exc}") from exc

    def latest_signal(self, instrument_id: str) -> DarvaxSignal | None:
        """Most recent persisted signal for one instrument, or None."""
        rows = self._signal_rows(
            "WHERE instrument_id=? ORDER BY as_of DESC LIMIT 1", (instrument_id,)
        )
        return rows[0] if rows else None

    def list_signals(self, *, limit: int = 200) -> list[DarvaxSignal]:
        """Newest-first signals across all instruments."""
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        return self._signal_rows("ORDER BY as_of DESC LIMIT ?", (limit,))

    def _signal_rows(self, clause: str, params: tuple) -> list[DarvaxSignal]:
        try:
            with self._lock:
                rows = self._connect().execute(
                    "SELECT signal_id, instrument_id, as_of, signal_type, "
                    "darvas_rule, close, box_top, box_bottom, box_is_topmost, "
                    "trigger_price, stop_json, explanation, evidence_json, "
                    f"methodology_digest, darvax_version, status FROM darvax_signals {clause}",
                    params,
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX signal query failed: {exc}") from exc
        return [_row_to_signal(row) for row in rows]

    def schema_version(self) -> int | None:
        with self._lock:
            row = self._connect().execute(
                "SELECT version FROM darvax_schema_version"
            ).fetchone()
            return int(row[0]) if row else None

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
