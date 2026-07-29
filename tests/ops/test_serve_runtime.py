"""Tests for interactive serve supervisor (Live Entry M-E2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.ops.serve_runtime import (
    CycleRunnerLock,
    CycleWorker,
    LastCycleSnapshot,
    RestartUnavailableError,
    ServeRuntime,
    get_serve_runtime,
    kite_token_status_from_env,
    set_serve_runtime,
    trigger_restart,
)


def test_kite_token_status_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    assert kite_token_status_from_env() == "unknown"

    monkeypatch.setenv("KITE_API_KEY", "k")
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    assert kite_token_status_from_env() == "missing"

    monkeypatch.setenv("KITE_ACCESS_TOKEN", "t")
    assert kite_token_status_from_env() == "present"


def test_cycle_runner_lock_exclusive(tmp_path: Path) -> None:
    path = tmp_path / "cycle.lock"
    a = CycleRunnerLock(path)
    b = CycleRunnerLock(path)
    assert a.acquire() is True
    assert b.acquire() is False
    a.release()
    assert b.acquire() is True
    b.release()


def test_cycle_worker_records_snapshot(tmp_path: Path) -> None:
    runtime = ServeRuntime(cycles_enabled=True)
    calls = {"n": 0}

    def tick() -> LastCycleSnapshot:
        calls["n"] += 1
        return LastCycleSnapshot(
            as_of=datetime.now(tz=timezone.utc),
            idle=True,
            due=(),
            status="idle",
            detail="test",
        )

    worker = CycleWorker(
        runtime=runtime,
        interval_seconds=5,
        tick_fn=tick,
        lock_path=tmp_path / "lock",
    )
    worker.start()
    # First tick runs immediately in the worker thread.
    for _ in range(50):
        if runtime.last_cycle is not None:
            break
        import time

        time.sleep(0.05)
    worker.stop()
    assert calls["n"] >= 1
    assert runtime.last_cycle is not None
    assert runtime.last_cycle.status == "idle"


def test_health_includes_serve_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITE_API_KEY", "k")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "t")
    runtime = ServeRuntime(cycles_enabled=True, host="127.0.0.1", port=8000)
    runtime.record_cycle(
        LastCycleSnapshot(
            as_of=datetime(2026, 7, 24, 10, 0, tzinfo=timezone.utc),
            idle=True,
            due=(),
            status="idle",
        )
    )
    set_serve_runtime(runtime)
    try:
        client = TestClient(create_app(APISettings()), raise_server_exceptions=False)
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["kite_token_status"] == "present"
        assert data["cycles_enabled"] is True
        assert data["last_cycle"]["status"] == "idle"
    finally:
        set_serve_runtime(None)
        assert get_serve_runtime() is None


def test_serve_cli_help() -> None:
    from athena.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["serve", "--help"])
    assert exc.value.code == 0


def test_trigger_restart_raises_without_a_known_command() -> None:
    """Owner-requested "restart ATHENA" action (2026-07-29): a ServeRuntime
    not started via the CLI (e.g. default-constructed, as in most tests)
    has no restart_command — refuse rather than guess an invocation."""
    runtime = ServeRuntime()
    with pytest.raises(RestartUnavailableError):
        trigger_restart(runtime)


def test_trigger_restart_re_execs_with_the_recorded_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies the actual re-exec mechanism WITHOUT ever calling the real
    os.execv (which would replace this test process's own image) — patches
    it at the athena.ops.serve_runtime module level, where trigger_restart
    looks it up, and drives the background thread to completion via join()
    instead of relying on the real (short) delay."""
    import threading

    import athena.ops.serve_runtime as serve_runtime_module

    calls: list[list[str]] = []

    def fake_execv(executable: str, args: list[str]) -> None:
        calls.append(list(args))

    monkeypatch.setattr(serve_runtime_module.os, "execv", fake_execv)
    monkeypatch.setattr(serve_runtime_module.time, "sleep", lambda _seconds: None)

    runtime = ServeRuntime(
        restart_command=("python3", "-m", "athena.cli", "serve", "--with-cycles")
    )
    trigger_restart(runtime, delay_seconds=0)

    # trigger_restart starts a background (non-daemon) thread named
    # "athena-restart"; join it explicitly instead of sleeping, so the test
    # is fast and deterministic.
    for t in threading.enumerate():
        if t.name == "athena-restart":
            t.join(timeout=2)

    assert calls == [["python3", "-m", "athena.cli", "serve", "--with-cycles"]]
