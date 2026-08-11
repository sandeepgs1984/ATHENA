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

import sqlite3
import threading
from pathlib import Path

from athena.darvax.store.schema import DARVAX_SCHEMA_VERSION, darvax_ddl_statements
from athena.errors import RepositoryError


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
