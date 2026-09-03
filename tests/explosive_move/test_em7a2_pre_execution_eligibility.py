"""EM-7A.2: session non-scannability is a pre-execution eligibility
outcome, not a persisted `emr_scan_runs` lifecycle state.

Owner/Chief Architect source review of EM-7A.1 found `run_scan_cycle`
still persisted a fourth status, `SKIPPED_SESSION_TYPE`, whenever
`session_is_scannable(...)` was `False` -- writing `RUNNING`, then
immediately overwriting it with `SKIPPED_SESSION_TYPE`. This
contradicted ADR-014 §15's accepted two-terminal-outcome model
(`RUNNING -> COMPLETE | FAILED`): a non-scannable session means the scan
was never eligible to start, not that a `RUNNING` scan executed and
terminated in a fourth state.

This suite proves the correction: session-scannability is now checked
as a true preflight -- after the existing-run-identity dispatch (so it
never overrides an already-COMPLETE result, reinterprets an
already-RUNNING row, or mutates an existing FAILED row) but before any
RUNNING write, provider call, or computation. New executions can persist
only RUNNING/COMPLETE/FAILED; a legacy pre-EM-7A.2 SKIPPED_SESSION_TYPE
row is still readable (backward-compatible same-run_id lookup only,
never written again).
"""

from __future__ import annotations

import pytest
from tests.explosive_move.test_em5_scanner import (
    _STUB_REGIME_LOOKUP,
    CHECKPOINT_INSTANT,
    _config,
    _fake_collector,
    _seed_athena_repo,
)

from athena.domain.enums import SessionType
from athena.explosive_move.live.market_data_port import SqliteEmrMarketDataAdapter
from athena.explosive_move.live.scanner import EmrScanAlreadyRunningError, run_scan_cycle
from athena.explosive_move.store.repository import EmrRepository

#: session_is_scannable() returns False for MUHURAT (a real, non-scannable
#: NSE session type) -- matches test_em5_scanner.py's own existing usage
#: for exactly this purpose.
_NON_SCANNABLE = SessionType.MUHURAT


@pytest.fixture()
def scan_setup(tmp_path):
    athena_repo = _seed_athena_repo(tmp_path / "athena")
    market_port = SqliteEmrMarketDataAdapter(athena_repo)
    emr_repo = EmrRepository(tmp_path / "emr" / "emr.db")
    emr_repo.initialize()
    yield market_port, emr_repo
    athena_repo.close()
    emr_repo.close()


def _run_id() -> str:
    import hashlib
    import json

    config = _config()
    payload = {
        "session_date": config.session_date.isoformat(), "checkpoint": config.checkpoint,
        "universe": config.universe, "model_version": config.model_version,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return f"em5-scan-{hashlib.sha256(encoded).hexdigest()}"


def _run(market_port, emr_repo, *, session_type, collect_checkpoint_prices=_fake_collector):
    return run_scan_cycle(
        config=_config(), market_port=market_port, emr_repo=emr_repo,
        calendar_context_session_type=session_type,
        collect_checkpoint_prices=collect_checkpoint_prices,
        regime_lookup=_STUB_REGIME_LOOKUP, now=lambda: CHECKPOINT_INSTANT,
    )


class _CountingCollector:
    def __init__(self):
        self.calls = 0

    def __call__(self, **kwargs):
        self.calls += 1
        return _fake_collector(**kwargs)


class _RaisingCollector:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __call__(self, **_kwargs):
        raise self._exc


def test_fresh_non_scannable_session_returns_skip_and_persists_nothing(scan_setup):
    market_port, emr_repo = scan_setup
    collector = _CountingCollector()

    result = _run(market_port, emr_repo, session_type=_NON_SCANNABLE, collect_checkpoint_prices=collector)

    assert result.status == "SKIPPED_SESSION_TYPE"
    assert result.candidates_persisted == 0
    assert result.transitions_persisted == 0
    assert collector.calls == 0, "a non-scannable session must never call the checkpoint-price collector"
    assert emr_repo.get_scan_run(result.run_id) is None, "no emr_scan_runs row of any status must be written"
    assert emr_repo.list_candidates(run_id=result.run_id) == []
    assert emr_repo.list_transitions_for_run(run_id=result.run_id) == []


def test_existing_complete_run_is_authoritative_regardless_of_current_session_type(scan_setup):
    market_port, emr_repo = scan_setup
    collector = _CountingCollector()
    first = _run(market_port, emr_repo, session_type=SessionType.NORMAL, collect_checkpoint_prices=collector)
    assert first.status == "COMPLETE"
    assert collector.calls == 1

    second = _run(market_port, emr_repo, session_type=_NON_SCANNABLE, collect_checkpoint_prices=collector)

    assert second.status == "COMPLETE"
    assert second.run_id == first.run_id
    assert second.candidates_persisted == first.candidates_persisted
    assert collector.calls == 1, "an already-COMPLETE run must not be reclassified by a non-scannable input"
    run = emr_repo.get_scan_run(first.run_id)
    assert run["status"] == "COMPLETE", "no mutation of the persisted COMPLETE row"


def test_existing_running_row_still_rejects_non_scannable_input(scan_setup):
    market_port, emr_repo = scan_setup
    emr_repo.save_scan_run({
        "run_id": _run_id(), "session_date": _config().session_date.isoformat(),
        "checkpoint": _config().checkpoint, "frozen_model_version": _config().model_version,
        "status": "RUNNING", "started_ts": CHECKPOINT_INSTANT.isoformat(),
    })

    with pytest.raises(EmrScanAlreadyRunningError, match=_run_id()):
        _run(market_port, emr_repo, session_type=_NON_SCANNABLE)


def test_existing_failed_row_stays_failed_and_returns_skip_for_non_scannable_retry(scan_setup):
    market_port, emr_repo = scan_setup
    with pytest.raises(ValueError, match="synthetic failure"):
        _run(
            market_port, emr_repo, session_type=SessionType.NORMAL,
            collect_checkpoint_prices=_RaisingCollector(ValueError("synthetic failure")),
        )
    failed_run_id = _run_id()
    assert emr_repo.get_scan_run(failed_run_id)["status"] == "FAILED"

    collector = _CountingCollector()
    result = _run(market_port, emr_repo, session_type=_NON_SCANNABLE, collect_checkpoint_prices=collector)

    assert result.status == "SKIPPED_SESSION_TYPE"
    assert collector.calls == 0
    run = emr_repo.get_scan_run(failed_run_id)
    assert run["status"] == "FAILED", "a non-scannable retry attempt must not mutate the existing FAILED row"


def test_legacy_skipped_row_falls_through_to_fresh_execution_when_scannable(scan_setup):
    """A database created before EM-7A.2 may still contain a persisted
    SKIPPED_SESSION_TYPE row -- read-compatibility only. It must be
    treated like FAILED: a subsequent scannable call under the same
    run_id proceeds to a fresh RUNNING execution and can reach COMPLETE."""
    market_port, emr_repo = scan_setup
    legacy_run_id = _run_id()
    emr_repo.save_scan_run({
        "run_id": legacy_run_id, "session_date": _config().session_date.isoformat(),
        "checkpoint": _config().checkpoint, "frozen_model_version": _config().model_version,
        "status": "SKIPPED_SESSION_TYPE", "started_ts": CHECKPOINT_INSTANT.isoformat(),
        "finished_ts": CHECKPOINT_INSTANT.isoformat(), "eligible_count": 0, "ineligible_count": 0,
    })

    result = _run(market_port, emr_repo, session_type=SessionType.NORMAL)

    assert result.run_id == legacy_run_id
    assert result.status == "COMPLETE"
    run = emr_repo.get_scan_run(legacy_run_id)
    assert run["status"] == "COMPLETE"


def test_new_executions_never_persist_skipped_session_type(scan_setup):
    """Persistence-domain regression: across a scannable success and an
    independent (different checkpoint -> different deterministic run_id)
    non-scannable call, no emr_scan_runs row with status
    SKIPPED_SESSION_TYPE is ever created by run_scan_cycle itself."""
    import dataclasses

    market_port, emr_repo = scan_setup

    ok = _run(market_port, emr_repo, session_type=SessionType.NORMAL)
    assert ok.status == "COMPLETE"

    # A different checkpoint yields a different deterministic run_id
    # (§14, unchanged) -- otherwise this second call would hit the
    # existing-COMPLETE short-circuit already proven by
    # test_existing_complete_run_is_authoritative_regardless_of_current_session_type
    # rather than exercising a genuinely fresh non-scannable call.
    other_config = dataclasses.replace(_config(), checkpoint="11:00")
    skipped = run_scan_cycle(
        config=other_config, market_port=market_port, emr_repo=emr_repo,
        calendar_context_session_type=_NON_SCANNABLE, collect_checkpoint_prices=_fake_collector,
        regime_lookup=_STUB_REGIME_LOOKUP, now=lambda: CHECKPOINT_INSTANT,
    )
    assert skipped.status == "SKIPPED_SESSION_TYPE"
    assert skipped.run_id != ok.run_id

    conn = emr_repo._connect()
    statuses = {row[0] for row in conn.execute("SELECT DISTINCT status FROM emr_scan_runs").fetchall()}
    assert statuses <= {"RUNNING", "COMPLETE", "FAILED"}
    assert "SKIPPED_SESSION_TYPE" not in statuses
