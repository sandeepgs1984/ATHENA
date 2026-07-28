"""Tests for owner-triggered full-universe validation (ADR-007 / MI-5)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from athena.data.store.repository import SqliteRepository
from athena.ops.full_validation import CycleBusyError, start_full_validation
from athena.ops.owner_candidates import SqliteCandidateStore
from athena.ops.serve_runtime import (
    CycleRunnerLock,
    FullValidationProgress,
    ServeRuntime,
    set_serve_runtime,
)


@pytest.fixture()
def runtime() -> ServeRuntime:
    rt = ServeRuntime(cycles_enabled=False, host="127.0.0.1", port=8000)
    set_serve_runtime(rt)
    yield rt
    set_serve_runtime(None)


def test_start_refuses_without_serve_runtime(tmp_path: Path) -> None:
    set_serve_runtime(None)
    with pytest.raises(CycleBusyError, match="athena serve"):
        start_full_validation(
            repo_root=tmp_path,
            config_dir=tmp_path / "config",
            db_path=tmp_path / "t.db",
        )


def test_start_refuses_when_lock_held(tmp_path: Path, runtime: ServeRuntime) -> None:
    db = tmp_path / "t.db"
    repo = SqliteRepository(db)
    repo.initialize()
    SqliteCandidateStore(repo).upsert_candidate(symbol="INFY")
    repo.close()

    lock_path = tmp_path / "cycle.lock"
    holder = CycleRunnerLock(lock_path)
    assert holder.acquire()
    try:
        with pytest.raises(CycleBusyError, match="cycle lock busy"):
            start_full_validation(
                repo_root=tmp_path,
                config_dir=tmp_path / "config",
                db_path=db,
                lock_path=lock_path,
            )
    finally:
        holder.release()


def test_start_refuses_when_already_running(tmp_path: Path, runtime: ServeRuntime) -> None:
    runtime.set_full_validation(
        FullValidationProgress(
            state="running",
            stage="ingesting",
            symbols_total=10,
            started_at=datetime.now(tz=timezone.utc),
        )
    )
    with pytest.raises(CycleBusyError, match="already running"):
        start_full_validation(
            repo_root=tmp_path,
            config_dir=tmp_path / "config",
            db_path=tmp_path / "t.db",
            lock_path=tmp_path / "cycle.lock",
        )
