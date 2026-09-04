"""EM-7A: EMR-owned scan-execution lock (ADR-014 Sections 9 and 17).

Structurally mirrors `athena.ops.serve_runtime.CycleRunnerLock`'s own
proven `flock`-based pattern -- deliberately NOT importing it. ADR-014's
required dependency direction is

    EMR worker -> EMR scanner -> EMR repository -> EMR read-only
    market-data port

never `EMR worker -> canonical ops/CycleWorker`, so this small amount of
duplicated locking code is accepted as the cost of preserving ADR-012's
directional isolation guarantee exactly (see `regime_source.py`'s own
identical one-way rule for `athena.regime`).

This module provides the primitive only: acquire/release ownership of
"at most one EMR scan execution at a time." It is scanner-correctness
infrastructure (EM-7A), not scheduling -- no polling, no worker loop, no
checkpoint-due logic lives here. EM-7B's future worker is the intended
consumer, wrapping one `run_scan_cycle` invocation in this lock's context.

Never shared with ATHENA's canonical `CycleRunnerLock`
(`artifacts/locks/cycle-runner.lock`) or any DarvaX lock -- this lock is
EMR-scoped only, at its own path.
"""

from __future__ import annotations

import fcntl
import os
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType


class EmrScanLockBusyError(RuntimeError):
    """Raised by `EmrScanLock.__enter__` when another EMR scan execution
    already holds the lock."""


class EmrScanLock:
    """Advisory exclusive lock: at most one EMR scan execution may hold
    this lock at a time. A held lock that its owning process never
    releases (a crash, `kill -9`) is released automatically by the OS
    when that process's file descriptors close -- the same
    self-healing "stale process" behavior `CycleRunnerLock` already
    relies on; no separate staleness/TTL logic is needed or added here.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._fh: object | None = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> bool:
        """Non-blocking. Returns True iff this call obtained the lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Deliberately not a `with` block: the handle must stay open past
        # this method's return, held until `release()` -- mirrors
        # CycleRunnerLock.acquire()'s identical, already-accepted pattern.
        fh = open(self._path, "a+", encoding="utf-8")  # noqa: SIM115
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            return False
        self._fh = fh
        fh.seek(0)
        fh.truncate()
        fh.write(f"pid={os.getpid()} ts={datetime.now(tz=UTC).isoformat()}\n")
        fh.flush()
        return True

    def release(self) -> None:
        """Idempotent: safe to call even if `acquire()` was never called
        or already failed -- releasing an unheld lock is a no-op, never
        an error, so callers may always release in a `finally` block."""
        fh = self._fh
        self._fh = None
        if fh is None:
            return
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()

    def __enter__(self) -> EmrScanLock:
        if not self.acquire():
            raise EmrScanLockBusyError(
                f"another EMR scan execution already holds the lock at {self._path}"
            )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Always release, whether the guarded block succeeded or raised --
        # a scanner exception must never leave the lock held.
        self.release()


def default_emr_scan_lock_path() -> Path:
    """`<repo_root>/artifacts/locks/emr-scan.lock` -- deliberately
    parallel to, and never shared with, `default_cycle_lock_path()`
    (`athena.ops.serve_runtime`, ATHENA's own canonical lock) and any
    DarvaX lock path. Walks up from this module's own directory for
    `pyproject.toml`, matching `explosive_move.live.presentation`'s own
    `default_emr_db_path()` resolution pattern."""
    root = Path(__file__).resolve().parent
    for _ in range(8):
        if (root / "pyproject.toml").is_file():
            break
        root = root.parent
    return root / "artifacts" / "locks" / "emr-scan.lock"
