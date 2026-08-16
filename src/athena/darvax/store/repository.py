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
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from athena.darvax.screening.models import (
    DarvaxAction,
    DarvaxTier,
    ScreenResult,
    SweepRecord,
)
from athena.darvax.signals.models import (
    DarvasRule,
    DarvaxSignal,
    DarvaxSignalType,
    DarvaxStop,
    SignalEvidence,
    StopBasis,
)
from athena.darvax.store.schema import (
    DARVAX_SCHEMA_VERSION,
    darvax_added_columns,
    darvax_ddl_statements,
)
from athena.errors import RepositoryError


def _optional_decimal(raw: str | None) -> Decimal | None:
    return Decimal(raw) if raw is not None else None


def _optional_str(value: Decimal | None) -> str | None:
    """Decimals are stored as text, never as REAL — binary floats would make
    persisted money and percentages non-reproducible across a round trip."""
    return str(value) if value is not None else None


def _row_to_sweep(row: tuple) -> SweepRecord:
    raw_counts = _json.loads(row[10])
    return SweepRecord(
        sweep_id=row[0],
        started_at=datetime.fromisoformat(row[1]),
        finished_at=datetime.fromisoformat(row[2]) if row[2] else None,
        state=row[3],
        as_of=datetime.fromisoformat(row[4]) if row[4] else None,
        methodology_digest=row[5],
        darvax_version=row[6],
        requested=int(row[7]),
        evaluated=int(row[8]),
        skipped=tuple(
            (entry["instrument_id"], entry["reason"]) for entry in _json.loads(row[9])
        ),
        tier_counts={DarvaxTier(k): int(v) for k, v in raw_counts.items()},
        partial=bool(row[11]),
    )


def _row_to_screen_result(row: tuple) -> ScreenResult:
    """Rehydrate a screen result. The tier and both measurements are read back
    as stored — never recomputed here, which is what keeps a screen replayable
    rather than merely re-runnable (ADR-005)."""
    return ScreenResult(
        sweep_id=row[0],
        instrument_id=row[1],
        signal_id=row[2],
        tier=DarvaxTier(row[3]),
        signal_type=DarvaxSignalType(row[4]),
        darvas_rule=DarvasRule(row[5]) if row[5] else None,
        rank=int(row[6]),
        close=Decimal(row[7]),
        box_top=_optional_decimal(row[8]),
        box_bottom=_optional_decimal(row[9]),
        trigger_price=_optional_decimal(row[10]),
        distance_to_trigger_pct=_optional_decimal(row[11]),
        distance_to_breakout_pct=_optional_decimal(row[12]),
        breakout_reference=row[13],
        box_height_pct=_optional_decimal(row[14]),
        explanation=row[15],
        # Pre-DX-7a rows carry NULL here. Falling back to the enum default would
        # present NO_ENTRY as though the engine had concluded it; the empty
        # reason is what tells a reader the action was never recorded.
        action=DarvaxAction(row[16]) if row[16] else DarvaxAction.NO_ENTRY,
        action_reason=row[17] or "",
    )


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
                    # Columns added after a table's CREATE shipped: CREATE TABLE
                    # IF NOT EXISTS is a no-op on an existing table, so an
                    # already-created table would silently miss them.
                    for table, column, column_type in darvax_added_columns():
                        existing = {
                            r[1]
                            for r in conn.execute(f"PRAGMA table_info({table})")
                        }
                        if column not in existing:
                            conn.execute(
                                f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
                            )
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

    # -------------------------------------------------------- screening (DX-6a)

    def save_sweep(self, sweep: SweepRecord) -> None:
        """Upsert one sweep record. Idempotent by ``sweep_id``.

        Upsert rather than insert because a sweep is written at least twice —
        once when it starts (``running``) and again when it finishes or is
        cancelled — and a crash between the two must leave a readable row
        rather than a missing one.
        """
        try:
            with self._lock:
                conn = self._connect()
                with conn:
                    conn.execute(
                        "INSERT INTO darvax_sweeps ("
                        "sweep_id, started_at, finished_at, state, as_of, "
                        "methodology_digest, darvax_version, requested, evaluated, "
                        "skipped_json, tier_counts_json, partial"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(sweep_id) DO UPDATE SET "
                        "finished_at=excluded.finished_at, state=excluded.state, "
                        "as_of=excluded.as_of, requested=excluded.requested, "
                        "evaluated=excluded.evaluated, skipped_json=excluded.skipped_json, "
                        "tier_counts_json=excluded.tier_counts_json, "
                        "partial=excluded.partial",
                        (
                            sweep.sweep_id,
                            sweep.started_at.isoformat(),
                            sweep.finished_at.isoformat() if sweep.finished_at else None,
                            sweep.state,
                            sweep.as_of.isoformat() if sweep.as_of else None,
                            sweep.methodology_digest,
                            sweep.darvax_version,
                            int(sweep.requested),
                            int(sweep.evaluated),
                            _json.dumps(
                                [
                                    {"instrument_id": i, "reason": r}
                                    for i, r in sweep.skipped
                                ]
                            ),
                            _json.dumps(
                                {t.value: c for t, c in sweep.tier_counts.items()}
                            ),
                            1 if sweep.partial else 0,
                        ),
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX sweep save failed: {exc}") from exc

    def save_screen_results(self, results: Sequence[ScreenResult]) -> int:
        """Upsert screen results. Idempotent by ``(sweep_id, instrument_id)``.

        Written in one transaction so a screen is never half-visible: a reader
        sees either the previous sweep's results or this one's, never a mix.
        """
        if not results:
            return 0
        try:
            with self._lock:
                conn = self._connect()
                with conn:
                    conn.executemany(
                        "INSERT INTO darvax_screen_results ("
                        "sweep_id, instrument_id, signal_id, tier, signal_type, "
                        "darvas_rule, rank, close, box_top, box_bottom, "
                        "trigger_price, distance_to_trigger_pct, distance_to_breakout_pct, "
                        "breakout_reference, box_height_pct, explanation, action, action_reason"
                        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(sweep_id, instrument_id) DO UPDATE SET "
                        "signal_id=excluded.signal_id, tier=excluded.tier, "
                        "signal_type=excluded.signal_type, "
                        "darvas_rule=excluded.darvas_rule, rank=excluded.rank, "
                        "close=excluded.close, box_top=excluded.box_top, "
                        "box_bottom=excluded.box_bottom, "
                        "trigger_price=excluded.trigger_price, "
                        "distance_to_trigger_pct=excluded.distance_to_trigger_pct, "
                        "distance_to_breakout_pct=excluded.distance_to_breakout_pct, "
                        "breakout_reference=excluded.breakout_reference, "
                        "box_height_pct=excluded.box_height_pct, "
                        "explanation=excluded.explanation, action=excluded.action, "
                        "action_reason=excluded.action_reason",
                        [
                            (
                                r.sweep_id,
                                r.instrument_id,
                                r.signal_id,
                                r.tier.value,
                                r.signal_type.value,
                                r.darvas_rule.value if r.darvas_rule else None,
                                int(r.rank),
                                str(r.close),
                                _optional_str(r.box_top),
                                _optional_str(r.box_bottom),
                                _optional_str(r.trigger_price),
                                _optional_str(r.distance_to_trigger_pct),
                                _optional_str(r.distance_to_breakout_pct),
                                r.breakout_reference,
                                _optional_str(r.box_height_pct),
                                r.explanation,
                                r.action.value,
                                r.action_reason,
                            )
                            for r in results
                        ],
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX screen results save failed: {exc}") from exc
        return len(results)

    def latest_sweep(self) -> SweepRecord | None:
        """Most recently started sweep, whatever its state."""
        rows = self._sweep_rows("ORDER BY started_at DESC LIMIT 1", ())
        return rows[0] if rows else None

    def get_sweep(self, sweep_id: str) -> SweepRecord | None:
        rows = self._sweep_rows("WHERE sweep_id=?", (sweep_id,))
        return rows[0] if rows else None

    def list_sweeps(self, *, limit: int = 50) -> list[SweepRecord]:
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        return self._sweep_rows("ORDER BY started_at DESC LIMIT ?", (limit,))

    def list_screen_results(
        self, sweep_id: str, *, tier: DarvaxTier | None = None, limit: int = 1000
    ) -> list[ScreenResult]:
        """One sweep's results in rank order, optionally one tier only."""
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        clause = "WHERE sweep_id=?"
        params: tuple = (sweep_id,)
        if tier is not None:
            clause += " AND tier=?"
            params = (sweep_id, tier.value)
        clause += " ORDER BY tier, rank LIMIT ?"
        return self._screen_rows(clause, (*params, limit))

    def prune_sweeps(self, keep: int) -> int:
        """Delete all but the ``keep`` most recent sweeps, and their results.

        Bounded history from the start, per the owner's DX-6b decision: each
        sweep writes roughly one result row per instrument, so unbounded growth
        would repeat ATHENA's decisions-table problem — far cheaper to prevent
        than to unwind. Returns the number of sweeps removed.
        """
        if keep < 1:
            raise ValueError(f"keep must be >= 1, got {keep}")
        try:
            with self._lock:
                conn = self._connect()
                with conn:
                    doomed = [
                        row[0]
                        for row in conn.execute(
                            "SELECT sweep_id FROM darvax_sweeps "
                            "ORDER BY started_at DESC LIMIT -1 OFFSET ?",
                            (keep,),
                        ).fetchall()
                    ]
                    if not doomed:
                        return 0
                    marks = ",".join("?" * len(doomed))
                    # Results first: a crash between the two statements must not
                    # leave orphaned results pointing at a deleted sweep.
                    conn.execute(
                        f"DELETE FROM darvax_screen_results WHERE sweep_id IN ({marks})",
                        doomed,
                    )
                    conn.execute(
                        f"DELETE FROM darvax_sweeps WHERE sweep_id IN ({marks})", doomed
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX sweep prune failed: {exc}") from exc
        return len(doomed)

    def list_signals_by_type(
        self, signal_type: DarvaxSignalType, *, limit: int = 200
    ) -> list[DarvaxSignal]:
        """Newest-first signals of one structural state.

        Closes a real gap found during DX-6 design: ``GET /api/signals`` filtered
        on nothing, so "show me only the breakouts" could not be answered from
        the API at all — only by eyeballing an unfiltered list.
        """
        if limit < 1:
            raise ValueError(f"limit must be >= 1, got {limit}")
        return self._signal_rows(
            "WHERE signal_type=? ORDER BY as_of DESC LIMIT ?",
            (signal_type.value, limit),
        )

    def _sweep_rows(self, clause: str, params: tuple) -> list[SweepRecord]:
        try:
            with self._lock:
                rows = self._connect().execute(
                    "SELECT sweep_id, started_at, finished_at, state, as_of, "
                    "methodology_digest, darvax_version, requested, evaluated, "
                    f"skipped_json, tier_counts_json, partial FROM darvax_sweeps {clause}",
                    params,
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX sweep query failed: {exc}") from exc
        return [_row_to_sweep(row) for row in rows]

    def _screen_rows(self, clause: str, params: tuple) -> list[ScreenResult]:
        try:
            with self._lock:
                rows = self._connect().execute(
                    "SELECT sweep_id, instrument_id, signal_id, tier, signal_type, "
                    "darvas_rule, rank, close, box_top, box_bottom, trigger_price, "
                    "distance_to_trigger_pct, distance_to_breakout_pct, "
                    "breakout_reference, box_height_pct, explanation, "
                    "action, action_reason "
                    f"FROM darvax_screen_results {clause}",
                    params,
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"DarvaX screen query failed: {exc}") from exc
        return [_row_to_screen_result(row) for row in rows]

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
