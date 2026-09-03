"""EM-7A: EmrScanLock -- EMR-owned scan-execution concurrency primitive
(ADR-014 Sections 9, 17). No worker/scheduler exists yet; these tests
prove only the primitive itself, which EM-7B will later consume."""

from __future__ import annotations

from pathlib import Path

import pytest

from athena.explosive_move.live.scan_lock import (
    EmrScanLock,
    EmrScanLockBusyError,
    default_emr_scan_lock_path,
)


def test_acquire_succeeds_when_unheld(tmp_path):
    lock = EmrScanLock(tmp_path / "emr-scan.lock")
    assert lock.acquire() is True
    lock.release()


def test_second_concurrent_acquisition_is_denied(tmp_path):
    path = tmp_path / "emr-scan.lock"
    holder = EmrScanLock(path)
    assert holder.acquire() is True
    try:
        contender = EmrScanLock(path)
        assert contender.acquire() is False
    finally:
        holder.release()


def test_release_frees_the_lock_for_the_next_acquirer(tmp_path):
    path = tmp_path / "emr-scan.lock"
    first = EmrScanLock(path)
    assert first.acquire() is True
    first.release()

    second = EmrScanLock(path)
    assert second.acquire() is True
    second.release()


def test_release_is_idempotent_and_safe_without_a_prior_acquire(tmp_path):
    lock = EmrScanLock(tmp_path / "emr-scan.lock")
    lock.release()  # must not raise
    lock.release()  # calling twice must not raise either


def test_context_manager_acquires_and_releases_on_success(tmp_path):
    path = tmp_path / "emr-scan.lock"
    with EmrScanLock(path):
        contender = EmrScanLock(path)
        assert contender.acquire() is False

    after = EmrScanLock(path)
    assert after.acquire() is True
    after.release()


def test_context_manager_releases_on_exception(tmp_path):
    path = tmp_path / "emr-scan.lock"
    with pytest.raises(ValueError, match="boom"), EmrScanLock(path):
        raise ValueError("boom")

    after = EmrScanLock(path)
    assert after.acquire() is True
    after.release()


def test_context_manager_raises_busy_error_when_already_held(tmp_path):
    path = tmp_path / "emr-scan.lock"
    holder = EmrScanLock(path)
    assert holder.acquire() is True
    try:
        with pytest.raises(EmrScanLockBusyError, match=str(path)), EmrScanLock(path):
            pass  # pragma: no cover -- must never be entered
    finally:
        holder.release()


def test_lock_file_records_pid_and_timestamp(tmp_path):
    path = tmp_path / "emr-scan.lock"
    lock = EmrScanLock(path)
    lock.acquire()
    try:
        content = path.read_text(encoding="utf-8")
        assert "pid=" in content
        assert "ts=" in content
    finally:
        lock.release()


def test_default_path_is_scoped_to_emr_and_distinct_from_canonical_lock():
    path = default_emr_scan_lock_path()
    assert path.name == "emr-scan.lock"
    assert path.parent.name == "locks"
    # Never the same file as ATHENA's own canonical cycle-runner lock.
    assert path.name != "cycle-runner.lock"


def test_lock_never_imports_canonical_ops_or_scheduling():
    """ADR-014 Section 9/Section 6: the worker (and everything it
    depends on, including this lock) must never import
    athena.ops/athena.scheduling -- covered generally by
    test_em5_isolation.py's forbidden-import scan, pinned here too as a
    direct, fast, single-file regression guard on the lock module
    specifically."""
    import ast

    source_path = Path(__file__).resolve().parents[2] / "src" / "athena" / "explosive_move" / "live" / "scan_lock.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    forbidden = [m for m in imported_modules if m.startswith(("athena.ops", "athena.scheduling"))]
    assert forbidden == []
