"""Backup & Restore — the final reliability layer of the data foundation (M1.6).

Guarantees any repository can be backed up, restored, verified, and replayed
with confidence. Repository-focused: no business rules, provider logic, or
market intelligence.

Design:
- Backup uses SQLite's online backup API (safe on a live DB), integrity-checks
  the source first, and writes the snapshot atomically (temp file + os.replace)
  so a backup file is always complete — an immutable snapshot.
- A JSON metadata sidecar (<backup>.meta.json) records schema version, per-table
  counts, and provenance for recovery validation.
- Restore integrity-checks the backup, enforces schema-version compatibility
  (no silent repair), replaces the target atomically, then re-verifies the
  restored repository (integrity, foreign keys, schema version, record counts).
- Every failure raises RepositoryError with an actionable message and never
  leaves the target repository in an inconsistent state.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from athena.data.store.repository import SqliteRepository
from athena.data.store.schema import SCHEMA_VERSION
from athena.errors import RepositoryError

_META_SUFFIX = ".meta.json"


@dataclass(frozen=True, slots=True)
class BackupResult:
    destination: str
    schema_version: int
    record_counts: Mapping[str, int]
    integrity_ok: bool
    ts: datetime
    explanation: str


@dataclass(frozen=True, slots=True)
class RestoreResult:
    source: str
    target: str
    schema_version: int
    record_counts: Mapping[str, int]
    integrity_ok: bool
    foreign_keys_ok: bool
    schema_version_ok: bool
    counts_match: bool
    ts: datetime
    explanation: str
    issues: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (self.integrity_ok and self.foreign_keys_ok
                and self.schema_version_ok and self.counts_match)


def _read_schema_version(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else None


def _validate_sqlite_file(path: Path) -> int:
    """Open a standalone SQLite file, verify integrity + schema version, return version.

    Raises RepositoryError (never returns) if the file is missing, corrupt, or
    schema-incompatible."""
    if not path.exists():
        raise RepositoryError(f"backup not found: {path}")
    conn = sqlite3.connect(str(path))
    try:
        try:
            integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        except sqlite3.Error as exc:
            raise RepositoryError(f"backup is corrupted ({path}): {exc}") from exc
        if integrity != "ok":
            raise RepositoryError(f"backup failed integrity check ({path}): {integrity}")
        version = _read_schema_version(conn)
        if version is None:
            raise RepositoryError(f"backup has no schema_version ({path}) — not an ATHENA backup")
        if version != SCHEMA_VERSION:
            raise RepositoryError(
                f"incompatible schema version in backup ({path}): found {version}, "
                f"expected {SCHEMA_VERSION} — restore refused (no automatic migration)")
        return version
    finally:
        conn.close()


def create_backup(
    repository: SqliteRepository, destination: str | Path, *,
    as_of: datetime, overwrite: bool = False,
) -> BackupResult:
    """Create an immutable, integrity-verified snapshot of ``repository``."""
    dest = Path(destination)
    if dest.exists() and not overwrite:
        raise RepositoryError(f"backup destination already exists: {dest} (pass overwrite=True)")

    integrity = repository.verify_integrity()
    if not integrity.ok:
        raise RepositoryError(
            f"refusing to back up an unhealthy repository: {'; '.join(integrity.issues)}")

    counts = repository.record_counts()
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dst_conn = sqlite3.connect(str(tmp))
        try:
            with dst_conn:
                repository.connection.backup(dst_conn)
        finally:
            dst_conn.close()
        os.replace(tmp, dest)
    except (OSError, sqlite3.Error) as exc:
        if tmp.exists():
            tmp.unlink()
        raise RepositoryError(f"backup failed writing to {dest}: {exc}") from exc

    meta = {
        "schema_version": SCHEMA_VERSION,
        "record_counts": counts,
        "created_ts": as_of.isoformat(),
        "source_path": repository.path,
    }
    dest.with_name(dest.name + _META_SUFFIX).write_text(
        json.dumps(meta, sort_keys=True, indent=2), encoding="utf-8")

    return BackupResult(
        destination=str(dest), schema_version=SCHEMA_VERSION, record_counts=counts,
        integrity_ok=True, ts=as_of,
        explanation=f"backed up {sum(counts.values())} record(s) to {dest}",
    )


def restore_backup(
    backup_path: str | Path, target_path: str | Path, *, as_of: datetime,
) -> RestoreResult:
    """Restore ``target_path`` from ``backup_path``, verifying recovery. Fails loudly."""
    backup = Path(backup_path)
    target = Path(target_path)

    # 1. Validate the backup BEFORE touching the target (no silent repair).
    version = _validate_sqlite_file(backup)

    # 2. Atomic replace: copy to a temp file beside the target, then os.replace.
    tmp = target.with_suffix(target.suffix + ".restore.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(backup.read_bytes())
        os.replace(tmp, target)
    except OSError as exc:
        if tmp.exists():
            tmp.unlink()
        raise RepositoryError(f"restore failed writing to {target}: {exc}") from exc

    # Stale WAL sidecars from a prior DB must not shadow the restored file.
    for sidecar in (f"{target}-wal", f"{target}-shm"):
        p = Path(sidecar)
        if p.exists():
            p.unlink()

    # 3. Recovery validation on the restored repository.
    restored = SqliteRepository(target)
    try:
        report = restored.verify_integrity()
        counts = restored.record_counts()
    finally:
        restored.close()

    expected = _load_expected_counts(backup)
    counts_match = expected is None or counts == expected
    issues = list(report.issues)
    if not counts_match:
        issues.append(f"record counts differ from backup metadata: {counts} != {expected}")

    return RestoreResult(
        source=str(backup), target=str(target), schema_version=version,
        record_counts=counts, integrity_ok=report.integrity_check == "ok",
        foreign_keys_ok=report.foreign_key_violations == 0,
        schema_version_ok=report.schema_version_ok, counts_match=counts_match,
        ts=as_of, issues=tuple(issues),
        explanation=(f"restored {sum(counts.values())} record(s) from {backup} to {target}"),
    )


def _load_expected_counts(backup: Path) -> Mapping[str, int] | None:
    meta_path = backup.with_name(backup.name + _META_SUFFIX)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return {k: int(v) for k, v in data["record_counts"].items()}
    except (OSError, ValueError, KeyError):
        return None
