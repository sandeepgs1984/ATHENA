"""Interactive workstation supervisor (Live Entry M-E2).

``athena serve`` starts the localhost API and optionally a background
due-cycle worker that reuses ``HostDueRunner`` (same path as ``run-due``).

This complements launchd/cron for unattended ticks; it does not replace them.
A non-blocking file lock prevents overlapping cycle runs with ``run-due``.
"""

from __future__ import annotations

import fcntl
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

logger = logging.getLogger(__name__)

KiteTokenStatus = Literal["missing", "present", "unknown"]
FullValidationState = Literal["idle", "running", "completed", "failed"]
FullValidationStage = Literal[
    "idle",
    "acquiring_lock",
    "seeding",
    "ingesting",
    "validating",
    "completed",
    "failed",
]


@dataclass(frozen=True, slots=True)
class LastCycleSnapshot:
    """Last interactive/worker due-cycle outcome for health surfaces."""

    as_of: datetime
    idle: bool
    due: tuple[str, ...]
    status: str
    run_id: str | None = None
    trigger: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class FullValidationProgress:
    """Transient progress for the owner-triggered full-universe job (ADR-007)."""

    state: FullValidationState = "idle"
    stage: FullValidationStage = "idle"
    symbols_total: int = 0
    symbols_completed: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    run_id: str | None = None
    detail: str | None = None


@dataclass
class ServeRuntime:
    """Process-local serve state (readable by health providers)."""

    cycles_enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_cycle: LastCycleSnapshot | None = None
    last_error: str | None = None
    full_validation: FullValidationProgress = field(default_factory=FullValidationProgress)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_cycle(self, snapshot: LastCycleSnapshot) -> None:
        with self._lock:
            self.last_cycle = snapshot
            self.last_error = None

    def record_error(self, detail: str) -> None:
        with self._lock:
            self.last_error = detail

    def set_full_validation(self, progress: FullValidationProgress) -> None:
        with self._lock:
            self.full_validation = progress

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            last = self.last_cycle
            return {
                "cycles_enabled": self.cycles_enabled,
                "host": self.host,
                "port": self.port,
                "started_at": self.started_at,
                "last_cycle": last,
                "last_error": self.last_error,
                "full_validation": self.full_validation,
            }


_RUNTIME: ServeRuntime | None = None
_RUNTIME_GUARD = threading.Lock()


def get_serve_runtime() -> ServeRuntime | None:
    with _RUNTIME_GUARD:
        return _RUNTIME


def set_serve_runtime(runtime: ServeRuntime | None) -> None:
    global _RUNTIME
    with _RUNTIME_GUARD:
        _RUNTIME = runtime


def kite_token_status_from_env() -> KiteTokenStatus:
    """Env-only kite token presence (full profile verify is M-E3)."""
    key = (os.environ.get("KITE_API_KEY") or "").strip()
    token = (os.environ.get("KITE_ACCESS_TOKEN") or "").strip()
    if not key and not token:
        return "unknown"
    if key and token:
        return "present"
    return "missing"


class CycleRunnerLock:
    """Advisory exclusive lock so serve worker and launchd ``run-due`` do not overlap."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._fh: object | None = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self._path, "a+", encoding="utf-8")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.close()
            return False
        self._fh = fh
        fh.seek(0)
        fh.truncate()
        fh.write(f"pid={os.getpid()} ts={datetime.now(tz=timezone.utc).isoformat()}\n")
        fh.flush()
        return True

    def release(self) -> None:
        fh = self._fh
        self._fh = None
        if fh is None:
            return
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


class CycleWorker:
    """Background poller that invokes a due-cycle tick function."""

    def __init__(
        self,
        *,
        runtime: ServeRuntime,
        interval_seconds: float,
        tick_fn: Callable[[], LastCycleSnapshot],
        lock_path: Path,
    ) -> None:
        if interval_seconds < 5:
            raise ValueError("cycle interval must be >= 5 seconds")
        self._runtime = runtime
        self._interval = float(interval_seconds)
        self._tick_fn = tick_fn
        self._lock = CycleRunnerLock(lock_path)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="athena-cycle-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Cycle worker started (interval=%ss, lock=%s)",
            self._interval,
            self._lock._path,
        )

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=join_timeout)
        self._thread = None

    def _loop(self) -> None:
        # Run once soon after start so the desk is live without waiting a full interval.
        self._safe_tick()
        while not self._stop.wait(self._interval):
            self._safe_tick()

    def _safe_tick(self) -> None:
        if not self._lock.acquire():
            logger.info("Cycle tick skipped — another runner holds the lock")
            self._runtime.record_error("cycle lock busy (another run-due in progress)")
            return
        try:
            snapshot = self._tick_fn()
            self._runtime.record_cycle(snapshot)
        except Exception as exc:
            logger.exception("Cycle worker tick failed")
            self._runtime.record_error(str(exc))
        finally:
            self._lock.release()


def default_cycle_lock_path(repo_root: Path) -> Path:
    return Path(repo_root) / "artifacts" / "locks" / "cycle-runner.lock"
