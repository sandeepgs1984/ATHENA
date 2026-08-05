"""Tests for R5 failure alerts and host due-runner (no live network)."""

from __future__ import annotations

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
