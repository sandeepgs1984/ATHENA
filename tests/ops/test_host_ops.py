"""Tests for R5 failure alerts and host due-runner (no live network)."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from athena.config.models import FailureAlertsConfig, HostOpsConfig
from athena.domain.enums import RunStatus, RunTrigger, SessionType
from athena.domain.run import RunRecord
from athena.errors import AthenaError
from athena.ops.canary import CanaryResult
from athena.ops.failure_alerts import FailureAlertDispatcher, resolve_alert_webhook_url
from athena.ops.scheduled_run import HostDueRunner
from athena.scheduling.dry_run import DryRunCycleResult

IST = ZoneInfo("Asia/Kolkata")
REPO_CONFIG = Path(__file__).resolve().parents[2] / "config"


def test_resolve_alert_webhook_prefers_dedicated(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ATHENA_ALERT_WEBHOOK_URL", "https://alerts.example/hook")
    monkeypatch.setenv("ATHENA_WEBHOOK_URL", "https://brief.example/hook")
    assert resolve_alert_webhook_url() == "https://alerts.example/hook"


def test_resolve_alert_webhook_falls_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ATHENA_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("ATHENA_WEBHOOK_URL", "https://brief.example/hook")
    assert resolve_alert_webhook_url() == "https://brief.example/hook"


def test_failure_alert_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ATHENA_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("ATHENA_WEBHOOK_URL", raising=False)
    cfg = FailureAlertsConfig(
        enabled=True,
        file_enabled=True,
        output_dir=str(tmp_path / "alerts"),
        webhook_enabled=True,
    )
    dispatcher = FailureAlertDispatcher(cfg, repo_root=tmp_path, tzinfo=IST)
    alert, receipts = dispatcher.dispatch(
        title="boom",
        detail="ingest failed",
        source="run-due",
        as_of=datetime(2026, 7, 23, 10, 0, tzinfo=IST),
    )
    assert alert.title == "boom"
    assert any(r.channel == "file" and r.ok for r in receipts)
    assert any(r.channel == "webhook" and not r.ok for r in receipts)  # no URL
    files = list((tmp_path / "alerts").glob("alert-*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "athena_failure_alert"
    assert payload["detail"] == "ingest failed"


def test_failure_alert_webhook_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ATHENA_ALERT_WEBHOOK_URL", "https://example.test/alert")
    cfg = FailureAlertsConfig(
        enabled=True,
        file_enabled=False,
        output_dir=str(tmp_path / "alerts"),
        webhook_enabled=True,
    )
    dispatcher = FailureAlertDispatcher(cfg, repo_root=tmp_path, tzinfo=IST)
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    mock_resp.status = 200
    mock_resp.getcode.return_value = 200
    with patch("athena.ops.failure_alerts.urllib.request.urlopen", return_value=mock_resp):
        alert, receipts = dispatcher.dispatch(
            title="boom",
            detail="x",
            source="test",
            as_of=datetime(2026, 7, 23, 10, 0, tzinfo=IST),
        )
    assert alert.alert_id.startswith("alert-")
    assert receipts[0].ok is True
    assert receipts[0].channel == "webhook"


def _run_record(status: RunStatus = RunStatus.COMPLETED) -> RunRecord:
    return RunRecord(
        run_id="run-1",
        cycle_id="c-1",
        trigger=RunTrigger.REFRESH,
        started_ts=datetime(2026, 7, 23, 10, 0, tzinfo=IST),
        status=status,
        software_version="0.1.0",
        blueprint_version="ATHENA-002",
        strategy_profile="p",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg",
        finished_ts=datetime(2026, 7, 23, 10, 0, tzinfo=IST),
    )


def test_host_due_runner_idle_no_alert():
    repo = MagicMock()
    repo.latest_run.return_value = None
    cfg = MagicMock()
    cfg.market.sessions.open = __import__("datetime").time(9, 15)
    cfg.market.sessions.close = __import__("datetime").time(15, 30)
    cfg.base.refresh_interval_minutes = 15
    sched = MagicMock()
    sched.premarket.enabled = True
    sched.premarket.run_at = __import__("datetime").time(8, 15)
    sched.refresh.enabled = True
    sched.refresh.interval_minutes = 15

    # Night — nothing due
    as_of = datetime(2026, 7, 23, 22, 0, tzinfo=IST)
    runner = HostDueRunner(
        cfg=cfg,
        sched=sched,
        host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()):
        result = runner.run(as_of=as_of, alert=True)
    assert result.idle is True
    assert result.cycles == ()


# Owner-reported (2026-08-10): ingest_engine used to be built eagerly by
# every caller before HostDueRunner even ran, so every 60s cycle-worker
# tick paid for a live Kite catalog fetch even on the common idle tick.
# HostDueRunner now also accepts a zero-arg factory and must only call it
# once it actually knows a cycle is due.
def test_host_due_runner_idle_tick_never_builds_ingest_engine():
    repo = MagicMock()
    repo.latest_run.return_value = None
    factory = MagicMock(side_effect=AssertionError("ingest_engine factory must not be called"))

    runner = HostDueRunner(
        cfg=MagicMock(),
        sched=MagicMock(),
        host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=factory,
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
    )
    as_of = datetime(2026, 7, 23, 22, 0, tzinfo=IST)
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()):
        result = runner.run(as_of=as_of, alert=True)
    assert result.idle is True
    factory.assert_not_called()


def test_host_due_runner_due_tick_builds_ingest_engine_exactly_once():
    repo = MagicMock()
    repo.latest_run.return_value = None
    cycle = DryRunCycleResult(
        run=_run_record(), ingestion=None,
        pipeline_detail={"mode": "ingest_only"}, duration_seconds=0.1,
    )
    orchestrator = MagicMock()
    orchestrator.run_cycle.return_value = cycle
    built_engine = MagicMock()
    factory = MagicMock(return_value=built_engine)

    runner = HostDueRunner(
        cfg=MagicMock(),
        sched=MagicMock(),
        host_ops=HostOpsConfig(brief_after_cycles=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=factory,
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
    )
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator) as orch_cls,
    ):
        result = runner.run(as_of=as_of, alert=True)
    assert result.idle is False
    factory.assert_called_once()
    orch_cls.assert_called_once_with(
        built_engine, repo, pipeline=None, strategy_profile="p", config_snapshot_id="cfg-host-ops",
        # ID-7P0: opt-in, observational-only cycle-phase timing enabled on
        # the real scheduled path.
        enable_timing=True,
    )


# 2026-09-08 scheduler correctness correction: `latest_run()` never filters
# by status, so a `RUNNING` row left behind by a process that died mid-cycle
# (a genuine, observed production occurrence -- not hypothetical) kept
# `last_refresh_ts` pinned to a dead attempt's `started_ts`, delaying the
# next due REFRESH by up to a full `refresh_interval_minutes` for no
# reason. `HostDueRunner._reconcile_if_orphaned` reconciles such a row to
# `FAILED` for durable audit truth (proven dead by cycle-runner lock
# ownership, never a guessed timeout) but treats it as absent for *this*
# invocation's own cadence inputs only -- an already-terminal FAILED/
# COMPLETED run is completely unaffected, preserving today's existing
# (separate, unresolved) policy of letting FAILED participate in cadence
# exactly like COMPLETED.
def _orphaned_run_record(trigger: RunTrigger, *, started_ts: datetime) -> RunRecord:
    return RunRecord(
        run_id=f"run-{trigger.value.lower()}-orphan",
        cycle_id="c-orphan",
        trigger=trigger,
        started_ts=started_ts,
        status=RunStatus.RUNNING,
        software_version="0.1.0",
        blueprint_version="ATHENA-002",
        strategy_profile="p",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg-host-ops",
        input_digest="digest-1",
    )


def test_orphaned_refresh_run_is_reconciled_to_failed():
    """A: latest RUNNING REFRESH is reconciled to FAILED."""
    orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]  # PREMARKET, REFRESH, CLOSING, FAST

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    as_of = datetime(2026, 9, 8, 10, 48, tzinfo=IST)
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()):
        runner.run(as_of=as_of, alert=True)

    repo.save_run.assert_called_once()
    reconciled, kwargs = repo.save_run.call_args.args[0], repo.save_run.call_args.kwargs
    assert reconciled.status is RunStatus.FAILED
    assert reconciled.finished_ts == as_of
    assert kwargs["detail"]["phase"] == "reconciled_orphan"


def test_orphan_reconciliation_preserves_identity_and_audit_fields():
    """B: reconciliation preserves original run identity/audit fields."""
    orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()):
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)

    reconciled = repo.save_run.call_args.args[0]
    for field in (
        "run_id", "cycle_id", "trigger", "started_ts", "software_version",
        "blueprint_version", "strategy_profile", "strategy_profile_version",
        "indicator_versions", "config_snapshot_id", "input_digest",
    ):
        assert getattr(reconciled, field) == getattr(orphan, field), field


def test_orphan_reconciliation_detail_is_machine_readable():
    """C: reconciliation supplies a terminal finished_ts and explicit detail_json."""
    orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    as_of = datetime(2026, 9, 8, 10, 48, tzinfo=IST)
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()):
        runner.run(as_of=as_of, alert=True)

    reconciled = repo.save_run.call_args.args[0]
    detail = repo.save_run.call_args.kwargs["detail"]
    assert reconciled.finished_ts == as_of
    assert reconciled.status is RunStatus.FAILED
    assert detail["phase"] == "reconciled_orphan"
    assert "cycle-runner lock" in detail["reason"]


def test_orphaned_refresh_does_not_advance_last_refresh_ts_this_invocation():
    """D: newly reconciled REFRESH orphan does NOT advance the current
    invocation's last_refresh_ts."""
    orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)
    assert mock_due.call_args.kwargs["last_refresh_ts"] is None


def test_orphaned_refresh_allows_immediate_real_retry():
    """E: an otherwise-due REFRESH can retry immediately -- real,
    unmocked due_triggers/is_refresh_due, one minute after the orphan's
    own started_ts (well inside the 15-minute interval that would
    otherwise still be blocking a retry)."""
    started = datetime(2026, 9, 8, 10, 24, tzinfo=IST)
    as_of = datetime(2026, 9, 8, 10, 25, tzinfo=IST)
    orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=started)
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]
    cfg, sched = _cfg_and_sched_for_due_at_daytime()

    cycle = DryRunCycleResult(
        run=_run_record(), ingestion=None,
        pipeline_detail={"mode": "ingest_only"}, duration_seconds=0.1,
    )
    orchestrator = MagicMock()
    orchestrator.run_cycle.return_value = cycle

    runner = HostDueRunner(
        cfg=cfg, sched=sched, host_ops=HostOpsConfig(brief_after_cycles=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator):
        result = runner.run(as_of=as_of, alert=True)
    assert result.idle is False
    assert RunTrigger.REFRESH in result.due
    orchestrator.run_cycle.assert_called_once_with(RunTrigger.REFRESH, as_of=as_of)


def test_existing_failed_refresh_keeps_existing_cadence_behavior():
    """F: an already-terminal FAILED REFRESH is untouched and continues to
    participate in cadence exactly as it does today -- this correction
    makes no policy decision about FAILED."""
    failed = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    failed = dataclasses.replace(failed, status=RunStatus.FAILED, finished_ts=datetime(2026, 9, 8, 10, 26, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, failed, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)
    assert mock_due.call_args.kwargs["last_refresh_ts"] == failed.started_ts
    repo.save_run.assert_not_called()


def test_completed_refresh_keeps_existing_cadence_behavior():
    """G: COMPLETED REFRESH continues existing cadence behavior."""
    completed = _run_record(status=RunStatus.COMPLETED)
    repo = MagicMock()
    repo.latest_run.side_effect = [None, completed, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)
    assert mock_due.call_args.kwargs["last_refresh_ts"] == completed.started_ts
    repo.save_run.assert_not_called()


def test_orphaned_premarket_reconciliation_lets_due_logic_decide():
    """H: PREMARKET orphan reconciliation excludes the dead attempt from
    this invocation's cadence input; existing_due_triggers() (real,
    unmocked) then decides retry eligibility on its own -- same-day
    07:00, before the configured 08:15 premarket run_at, so PREMARKET is
    correctly still NOT due yet regardless of the orphan (proving this
    fix defers to, rather than overrides, existing cadence logic)."""
    orphan = _orphaned_run_record(RunTrigger.PREMARKET, started_ts=datetime(2026, 9, 8, 6, 0, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [orphan, None, None, None]
    cfg, sched = _cfg_and_sched_for_due_at_daytime()

    runner = HostDueRunner(
        cfg=cfg, sched=sched, host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    result = runner.run(as_of=datetime(2026, 9, 8, 7, 0, tzinfo=IST), alert=True)
    assert RunTrigger.PREMARKET not in result.due
    reconciled = repo.save_run.call_args.args[0]
    assert reconciled.status is RunStatus.FAILED
    assert reconciled.trigger is RunTrigger.PREMARKET


def test_orphaned_closing_reconciliation_lets_due_logic_decide():
    """I: CLOSING orphan reconciliation behaves equivalently to PREMARKET/REFRESH."""
    orphan = _orphaned_run_record(RunTrigger.CLOSING, started_ts=datetime(2026, 9, 8, 15, 45, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, None, orphan, None]
    cfg, sched = _cfg_and_sched_for_due_at_daytime()
    sched.closing.enabled = True
    sched.closing.run_at = __import__("datetime").time(15, 45)
    cycle = DryRunCycleResult(
        run=_run_record(), ingestion=None,
        pipeline_detail={"mode": "ingest_only"}, duration_seconds=0.1,
    )
    orchestrator = MagicMock()
    orchestrator.run_cycle.return_value = cycle

    runner = HostDueRunner(
        cfg=cfg, sched=sched, host_ops=HostOpsConfig(brief_when_idle=False, brief_after_cycles=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator):
        result = runner.run(as_of=datetime(2026, 9, 8, 15, 46, tzinfo=IST), alert=True)
    assert RunTrigger.CLOSING in result.due
    reconciled = repo.save_run.call_args.args[0]
    assert reconciled.status is RunStatus.FAILED
    assert reconciled.trigger is RunTrigger.CLOSING


def test_orphaned_fast_reconciliation_lets_due_logic_decide():
    """J: FAST orphan reconciliation behaves equivalently."""
    orphan = _orphaned_run_record(RunTrigger.FAST, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, None, None, orphan]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)
    assert mock_due.call_args.kwargs["last_fast_ts"] is None
    reconciled = repo.save_run.call_args.args[0]
    assert reconciled.status is RunStatus.FAILED
    assert reconciled.trigger is RunTrigger.FAST


def test_orphan_reconciliation_is_independent_per_trigger():
    """K: trigger reconciliation is independent -- only the orphaned
    REFRESH row is touched; healthy PREMARKET/CLOSING/FAST latest-run
    rows are left completely alone."""
    refresh_orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    premarket_completed = dataclasses.replace(_run_record(status=RunStatus.COMPLETED), trigger=RunTrigger.PREMARKET)
    closing_completed = dataclasses.replace(_run_record(status=RunStatus.COMPLETED), trigger=RunTrigger.CLOSING)
    fast_completed = dataclasses.replace(_run_record(status=RunStatus.COMPLETED), trigger=RunTrigger.FAST)
    repo = MagicMock()
    repo.latest_run.side_effect = [premarket_completed, refresh_orphan, closing_completed, fast_completed]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)

    repo.save_run.assert_called_once()
    assert repo.save_run.call_args.args[0].trigger is RunTrigger.REFRESH
    assert mock_due.call_args.kwargs["last_premarket_date"] == premarket_completed.started_ts.date()
    assert mock_due.call_args.kwargs["last_closing_date"] == closing_completed.started_ts.date()
    assert mock_due.call_args.kwargs["last_fast_ts"] == fast_completed.started_ts


def test_orphan_reconciliation_runs_the_due_trigger_exactly_once():
    """L: no duplicate/overlapping execution -- reconciling the dead
    REFRESH attempt and then running the now-eligible real REFRESH within
    the SAME invocation results in exactly one `run_cycle` call, never two."""
    orphan = _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 24, tzinfo=IST))
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]
    cycle = DryRunCycleResult(
        run=_run_record(), ingestion=None,
        pipeline_detail={"mode": "ingest_only"}, duration_seconds=0.1,
    )
    orchestrator = MagicMock()
    orchestrator.run_cycle.return_value = cycle

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_after_cycles=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
    ):
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)
    orchestrator.run_cycle.assert_called_once()


def test_orphan_reconciliation_never_touches_unlocked_provenance_refresh():
    """Mandatory false-reconciliation regression (Owner source review,
    2026-09-08): a `cfg-symbol-validate` REFRESH row -- the dashboard's
    on-demand single-symbol "Validate", which never acquires
    CycleRunnerLock -- can be genuinely, legitimately RUNNING at the exact
    moment a lock-holding HostDueRunner invocation checks `latest_run`.
    That row must NEVER be reconciled to FAILED, and must continue to
    participate in cadence exactly as before this correction (unchanged
    pre-existing behavior, not a new provenance filter on cadence
    itself)."""
    live_symbol_validate_run = dataclasses.replace(
        _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 47, tzinfo=IST)),
        config_snapshot_id="cfg-symbol-validate",
    )
    repo = MagicMock()
    repo.latest_run.side_effect = [None, live_symbol_validate_run, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)

    repo.save_run.assert_not_called()
    assert mock_due.call_args.kwargs["last_refresh_ts"] == live_symbol_validate_run.started_ts


def test_orphan_reconciliation_never_touches_cfg_cli_provenance():
    """Same danger, `athena cycle` (`cfg-cli`) provenance -- also never
    acquires CycleRunnerLock."""
    live_cli_run = dataclasses.replace(
        _orphaned_run_record(RunTrigger.CLOSING, started_ts=datetime(2026, 9, 8, 15, 45, tzinfo=IST)),
        config_snapshot_id="cfg-cli",
    )
    repo = MagicMock()
    repo.latest_run.side_effect = [None, None, live_cli_run, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 15, 46, tzinfo=IST), alert=True)

    repo.save_run.assert_not_called()
    assert mock_due.call_args.kwargs["last_closing_date"] == live_cli_run.started_ts.date()


def test_orphan_reconciliation_does_touch_full_validation_provenance():
    """The mirror-image proof: a genuinely dead `cfg-full-validation`
    (owner-triggered "Validate All") REFRESH row IS reconciled, since that
    path explicitly acquires the same CycleRunnerLock before running."""
    orphan = dataclasses.replace(
        _orphaned_run_record(RunTrigger.REFRESH, started_ts=datetime(2026, 9, 8, 10, 0, tzinfo=IST)),
        config_snapshot_id="cfg-full-validation",
    )
    repo = MagicMock()
    repo.latest_run.side_effect = [None, orphan, None, None]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)

    repo.save_run.assert_called_once()
    assert mock_due.call_args.kwargs["last_refresh_ts"] is None


def test_orphan_reconciliation_does_touch_fast_revalidation_provenance():
    """Same mirror-image proof for the FAST tier's own lock-transitive
    provenance."""
    orphan = dataclasses.replace(
        _orphaned_run_record(RunTrigger.FAST, started_ts=datetime(2026, 9, 8, 10, 0, tzinfo=IST)),
        config_snapshot_id="cfg-fast-revalidation",
    )
    repo = MagicMock()
    repo.latest_run.side_effect = [None, None, None, orphan]

    runner = HostDueRunner(
        cfg=MagicMock(), sched=MagicMock(), host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(), repo=repo, ingest_engine=MagicMock(), repo_root=Path("/tmp"),
        tzinfo=IST, strategy_profile="p", alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers", return_value=()) as mock_due:
        runner.run(as_of=datetime(2026, 9, 8, 10, 48, tzinfo=IST), alert=True)

    repo.save_run.assert_called_once()
    assert mock_due.call_args.kwargs["last_fast_ts"] is None


def test_orphan_reconciliation_producer_inventory_is_complete_and_correctly_scoped():
    """Architecture contract (replaces the narrower, now-insufficient
    'HostDueRunner construction sites are lock-guarded' check): this test
    fails if a future producer of a `RUNNING` PREMARKET/REFRESH/CLOSING/
    FAST row is added without a conscious decision about whether it
    belongs in `_LOCK_PROTECTED_CONFIG_SNAPSHOT_IDS`.

    Enumerates every real `DryRunCycleOrchestrator(` construction site in
    the repository (there are exactly five today) and proves, by source
    scan, which ones actually acquire `CycleRunnerLock` -- then cross-
    checks that set against the reconciliation allowlist exactly, in both
    directions: every lock-protected provenance is allow-listed, and
    every allow-listed provenance is genuinely lock-protected."""
    import ast
    import inspect
    import pathlib

    import athena.cli as cli_module
    import athena.ops.full_validation as full_validation_module
    import athena.ops.scheduled_run as scheduled_run_module
    import athena.ops.serve_runtime as serve_runtime_module
    from athena.ops.scheduled_run import _LOCK_PROTECTED_CONFIG_SNAPSHOT_IDS

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    src_root = repo_root / "src" / "athena"
    construction_sites: list[tuple[str, str]] = []  # (file, config_snapshot_id)
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "DryRunCycleOrchestrator(" not in text:
            continue
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "DryRunCycleOrchestrator"
            ):
                snapshot_id = None
                for kw in node.keywords:
                    if kw.arg == "config_snapshot_id" and isinstance(kw.value, ast.Constant):
                        snapshot_id = kw.value.value
                construction_sites.append((str(path.relative_to(repo_root)), snapshot_id))

    # Exactly five known construction sites today -- a new one changes
    # this count, forcing a conscious update of this test (and, before
    # that, of the allowlist above) rather than silently inheriting an
    # unreviewed lock assumption.
    assert len(construction_sites) == 5, construction_sites
    snapshot_ids = {sid for _, sid in construction_sites}
    assert snapshot_ids == {
        "cfg-host-ops", "cfg-fast-revalidation", "cfg-full-validation",
        "cfg-cli", "cfg-symbol-validate",
    }

    # `HostDueRunner` ("cfg-host-ops") is reachable only through its two
    # known, lock-guarded callers.
    cli_source = inspect.getsource(cli_module)
    assert cli_source.count("HostDueRunner(") == 1
    assert "CycleRunnerLock" in inspect.getsource(cli_module._cmd_run_due)
    assert "self._lock.acquire()" in inspect.getsource(serve_runtime_module.CycleWorker._safe_tick)

    # "cfg-fast-revalidation" has exactly one CALL site anywhere (its own
    # `def` doesn't count), inside HostDueRunner.run() itself --
    # transitively lock-protected by the same two callers above.
    run_fast_call_sites = 0
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "run_fast_revalidation_cycle(" not in text:
            continue
        tree = ast.parse(text)
        run_fast_call_sites += sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_fast_revalidation_cycle"
        )
    assert run_fast_call_sites == 1
    assert "run_fast_revalidation_cycle(" in inspect.getsource(scheduled_run_module.HostDueRunner.run)

    # "cfg-full-validation" explicitly acquires CycleRunnerLock in its own
    # background job function before ever calling run_cycle.
    assert "lock.acquire()" in inspect.getsource(full_validation_module._run_job)

    # "cfg-cli" and "cfg-symbol-validate" must remain provably lock-free --
    # if either ever gains CycleRunnerLock usage, this assertion (not the
    # allowlist) is the thing that should force a reconsideration of
    # whether it now belongs in `_LOCK_PROTECTED_CONFIG_SNAPSHOT_IDS`.
    assert "CycleRunnerLock" not in inspect.getsource(cli_module._cmd_cycle)
    import athena.ops.symbol_validate as symbol_validate_module
    assert "CycleRunnerLock" not in inspect.getsource(symbol_validate_module)

    lock_protected_provenances = {"cfg-host-ops", "cfg-fast-revalidation", "cfg-full-validation"}
    assert _LOCK_PROTECTED_CONFIG_SNAPSHOT_IDS == lock_protected_provenances
    assert lock_protected_provenances <= snapshot_ids
    assert snapshot_ids - lock_protected_provenances == {"cfg-cli", "cfg-symbol-validate"}


# Owner-reported (2026-08-01): on a weekend/holiday, Kite's quotes are
# legitimately frozen at the last real session's close, so the host's
# ~15-minute cron kept firing REFRESH/CLOSING cycles all day — every one
# failed the ingestion freshness check, since due_triggers() only ever
# checked wall-clock time-of-day, never whether the exchange was open at
# all that day. HostDueRunner now resolves is_trading_day via an
# injectable CalendarEngine before calling due_triggers().
def _cfg_and_sched_for_due_at_daytime():
    cfg = MagicMock()
    cfg.market.sessions.open = __import__("datetime").time(9, 15)
    cfg.market.sessions.close = __import__("datetime").time(15, 30)
    cfg.base.refresh_interval_minutes = 15
    sched = MagicMock()
    sched.premarket.enabled = True
    sched.premarket.run_at = __import__("datetime").time(8, 15)
    sched.refresh.enabled = True
    sched.refresh.interval_minutes = 15
    return cfg, sched


def test_host_due_runner_suppresses_cycles_on_weekend():
    repo = MagicMock()
    repo.latest_run.return_value = None
    cfg, sched = _cfg_and_sched_for_due_at_daytime()
    calendar = MagicMock()
    calendar.context_for.return_value.session_type = SessionType.WEEKEND

    # Midday on a Saturday — would fire REFRESH if only time-of-day mattered.
    as_of = datetime(2026, 8, 1, 12, 0, tzinfo=IST)
    runner = HostDueRunner(
        cfg=cfg,
        sched=sched,
        host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
        calendar=calendar,
    )
    with patch("athena.ops.scheduled_run.due_triggers") as mock_due:
        mock_due.return_value = ()
        result = runner.run(as_of=as_of, alert=True)
        assert mock_due.call_args.kwargs["is_trading_day"] is False
    calendar.context_for.assert_called_once_with(as_of.date())
    assert result.idle is True
    assert result.cycles == ()


def test_host_due_runner_allows_cycles_on_normal_trading_day():
    repo = MagicMock()
    repo.latest_run.return_value = None
    cfg, sched = _cfg_and_sched_for_due_at_daytime()
    calendar = MagicMock()
    calendar.context_for.return_value.session_type = SessionType.NORMAL

    as_of = datetime(2026, 7, 31, 12, 0, tzinfo=IST)  # a Friday
    runner = HostDueRunner(
        cfg=cfg,
        sched=sched,
        host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
        calendar=calendar,
    )
    with patch("athena.ops.scheduled_run.due_triggers") as mock_due:
        mock_due.return_value = ()
        runner.run(as_of=as_of, alert=True)
        assert mock_due.call_args.kwargs["is_trading_day"] is True


def test_host_due_runner_defaults_to_trading_day_true_without_calendar():
    """No `calendar`/`config_dir` wired in — every existing caller must see
    exactly its pre-fix behavior, not a new failure mode."""
    repo = MagicMock()
    repo.latest_run.return_value = None
    cfg, sched = _cfg_and_sched_for_due_at_daytime()

    as_of = datetime(2026, 8, 1, 12, 0, tzinfo=IST)  # a Saturday
    runner = HostDueRunner(
        cfg=cfg,
        sched=sched,
        host_ops=HostOpsConfig(brief_when_idle=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
    )
    with patch("athena.ops.scheduled_run.due_triggers") as mock_due:
        mock_due.return_value = ()
        runner.run(as_of=as_of, alert=True)
        assert mock_due.call_args.kwargs["is_trading_day"] is True


def test_host_due_runner_alerts_on_cycle_failure(tmp_path: Path):
    repo = MagicMock()
    repo.latest_run.return_value = None
    alerts = MagicMock()
    cfg = MagicMock()
    cfg.base.refresh_interval_minutes = 15
    cfg.market.sessions = MagicMock()

    orchestrator = MagicMock()
    orchestrator.run_cycle.side_effect = AthenaError("quotes stale")

    runner = HostDueRunner(
        cfg=cfg,
        sched=MagicMock(),
        host_ops=HostOpsConfig(alert_on_failed_run=True),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=tmp_path,
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=alerts,
    )
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        pytest.raises(AthenaError, match=r"quotes stale"),
    ):
        runner.run(as_of=as_of, alert=True)
    alerts.dispatch.assert_called_once()
    kwargs = alerts.dispatch.call_args.kwargs
    assert "hard failure" in kwargs["title"]
    assert "quotes stale" in kwargs["detail"]


def test_host_due_runner_success_runs_brief():
    repo = MagicMock()
    repo.latest_run.return_value = None
    cycle = DryRunCycleResult(
        run=_run_record(),
        ingestion=None,
        pipeline_detail={"mode": "ingest_only"},
        duration_seconds=0.1,
    )
    orchestrator = MagicMock()
    orchestrator.run_cycle.return_value = cycle

    runner = HostDueRunner(
        cfg=MagicMock(),
        sched=MagicMock(),
        host_ops=HostOpsConfig(brief_after_cycles=True),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
    )
    brief_result = MagicMock()
    brief_result.briefing.briefing_id = "brief-1"
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        patch("athena.ops.scheduled_run.BriefingDispatcher") as brief_cls,
    ):
        brief_cls.return_value.dispatch.return_value = brief_result
        result = runner.run(as_of=as_of, alert=True)
    assert result.idle is False
    assert result.briefing_id == "brief-1"
    assert len(result.cycles) == 1


# M-X8: fixed synthetic instrument through the real pipeline each due tick,
# to catch silent engine regressions — see src/athena/ops/canary.py.
def _runner_for_canary(**overrides) -> HostDueRunner:
    repo = MagicMock()
    repo.latest_run.return_value = None
    cycle = DryRunCycleResult(
        run=_run_record(), ingestion=None,
        pipeline_detail={"mode": "ingest_only"}, duration_seconds=0.1,
    )
    orchestrator = MagicMock()
    orchestrator.run_cycle.return_value = cycle
    kwargs = dict(
        cfg=MagicMock(),
        sched=MagicMock(),
        host_ops=HostOpsConfig(brief_after_cycles=False),
        notify_cfg=MagicMock(),
        repo=repo,
        ingest_engine=MagicMock(),
        repo_root=Path("/tmp"),
        tzinfo=IST,
        strategy_profile="p",
        alert_dispatcher=MagicMock(),
    )
    kwargs.update(overrides)
    return HostDueRunner(**kwargs), orchestrator


def test_host_due_runner_runs_canary_when_config_dir_wired():
    """Real production config_dir wired in — the canary must actually run
    (not just be silently skipped) and pass against real production
    config, exactly like OwnerValidationPipeline's own real-config tests."""
    runner, orchestrator = _runner_for_canary(config_dir=REPO_CONFIG)
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    assert result.canary is not None
    assert result.canary.ok, result.canary.reasons


def test_host_due_runner_skips_canary_without_config_dir():
    """No config_dir wired — matches _is_trading_day's own backward-
    compatible fallback: skipped (None), never attempted, never a new
    failure mode for callers who haven't threaded config_dir through."""
    runner, orchestrator = _runner_for_canary()
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    assert result.canary is None


def test_host_due_runner_canary_failure_never_breaks_a_real_cycle():
    """The canary code itself raising must not propagate — a diagnostic
    breaking must never take down the real scheduled cycle it's checking
    alongside."""
    runner, orchestrator = _runner_for_canary(config_dir=REPO_CONFIG)
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        patch("athena.ops.scheduled_run.run_canary", side_effect=RuntimeError("boom")),
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    assert result.idle is False
    assert result.canary is not None
    assert result.canary.ok is False
    assert "canary itself raised" in result.canary.reasons[0]


def test_host_due_runner_alerts_on_canary_regression():
    alerts = MagicMock()
    runner, orchestrator = _runner_for_canary(
        config_dir=REPO_CONFIG,
        host_ops=HostOpsConfig(brief_after_cycles=False, failure_alerts=FailureAlertsConfig(enabled=True)),
        alert_dispatcher=alerts,
    )
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    regression = CanaryResult(
        ok=False, reasons=("score status UNKNOWN (expected OK)",),
        decision_type=None, composite_value=None,
    )
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        patch("athena.ops.scheduled_run.run_canary", return_value=regression),
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    assert result.canary is regression
    alerts.dispatch.assert_called_once()
    kwargs = alerts.dispatch.call_args.kwargs
    assert kwargs["source"] == "canary"
    assert "UNKNOWN" in kwargs["detail"]


def test_host_due_runner_does_not_alert_on_canary_pass():
    alerts = MagicMock()
    runner, orchestrator = _runner_for_canary(config_dir=REPO_CONFIG, alert_dispatcher=alerts)
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.REFRESH,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
    ):
        runner.run(as_of=as_of, send_brief=False, alert=True)
    alerts.dispatch.assert_not_called()


# Milestone B (2026-08-04): fast decision-list-only revalidation tier —
# HostDueRunner must route RunTrigger.FAST through run_fast_revalidation_cycle
# (a separately-scoped ingest/pipeline pair), never through the shared
# full-universe orchestrator every other trigger uses.
def test_host_due_runner_runs_fast_tier_via_scoped_cycle():
    runner, orchestrator = _runner_for_canary(config_dir=REPO_CONFIG)
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    fast_result = DryRunCycleResult(
        run=_run_record(), ingestion=None,
        pipeline_detail={"mode": "ingest_only"}, duration_seconds=0.1,
    )
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.FAST,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        patch(
            "athena.ops.scheduled_run.run_fast_revalidation_cycle", return_value=fast_result,
        ) as mock_fast,
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    mock_fast.assert_called_once()
    assert mock_fast.call_args.kwargs["as_of"] == as_of
    orchestrator.run_cycle.assert_not_called()
    assert result.cycles == (fast_result,)


def test_host_due_runner_fast_tier_noop_when_no_decisions_yet():
    """run_fast_revalidation_cycle returns None (no decisions to keep
    fresh) — must not fabricate a cycle result."""
    runner, orchestrator = _runner_for_canary(config_dir=REPO_CONFIG)
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.FAST,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        patch("athena.ops.scheduled_run.run_fast_revalidation_cycle", return_value=None) as mock_fast,
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    mock_fast.assert_called_once()
    assert result.cycles == ()


def test_host_due_runner_skips_fast_tier_without_config_dir():
    """Matches _is_trading_day/_run_canary's own fallback: no config_dir
    wired means the fast tier can't build a scoped provider at all, so it's
    skipped rather than raising."""
    runner, orchestrator = _runner_for_canary()  # config_dir defaults to None
    as_of = datetime(2026, 7, 23, 10, 0, tzinfo=IST)
    with (
        patch("athena.ops.scheduled_run.due_triggers", return_value=(RunTrigger.FAST,)),
        patch("athena.ops.scheduled_run.DryRunCycleOrchestrator", return_value=orchestrator),
        patch("athena.ops.scheduled_run.run_fast_revalidation_cycle") as mock_fast,
    ):
        result = runner.run(as_of=as_of, send_brief=False, alert=True)
    mock_fast.assert_not_called()
    assert result.cycles == ()
