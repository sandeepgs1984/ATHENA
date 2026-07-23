"""M10.3 daily briefing: assemble from run ledger, dispatch via notifiers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena import BLUEPRINT_VERSION, __version__
from athena.config.loader import load_notifications_config
from athena.config.models import (
    FileNotifierConfig,
    NotificationChannelsConfig,
    NotificationsConfig,
    WebhookNotifierConfig,
)
from athena.data.store import SqliteRepository
from athena.domain.decision import Decision, DecisionTrace, TraceStage
from athena.domain.enums import DecisionType, Direction, RunStatus, RunTrigger
from athena.domain.run import RunRecord
from athena.errors import BriefingError, ConfigError
from athena.notifications import (
    BriefingDispatcher,
    BriefingStatus,
    DailyBriefingBuilder,
    WebhookNotifier,
)

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 2, 13, 16, 0, tzinfo=IST)


def _run(
    run_id: str,
    *,
    trigger: RunTrigger = RunTrigger.REFRESH,
    status: RunStatus = RunStatus.COMPLETED,
    started: datetime = AS_OF,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        cycle_id=f"cycle-{run_id}",
        trigger=trigger,
        started_ts=started,
        status=status,
        software_version=__version__,
        blueprint_version=BLUEPRINT_VERSION,
        strategy_profile="intraday-momentum",
        strategy_profile_version="1",
        indicator_versions={},
        config_snapshot_id="cfg-test",
        finished_ts=started,
    )


def _seed_run(repo: SqliteRepository, run: RunRecord, *, candles: int = 2, quotes: int = 1) -> None:
    repo.save_run(run, detail={
        "phase": "finished",
        "ingestion": {
            "candles_written": candles,
            "quotes_written": quotes,
            "candles_fetched": candles,
            "quotes_fetched": quotes,
            "datasets_validated": 1,
            "datasets_skipped_empty": 0,
        },
    })


class MemoryDecisions:
    def __init__(self, items):
        self._items = items

    def list_for_day(self, as_of):
        return self._items


def _decision(decision_id: str = "d-1") -> Decision:
    return Decision(
        decision_id=decision_id,
        ts=AS_OF,
        run_id="run-1",
        cycle_id="c-1",
        decision_type=DecisionType.WATCH,
        explanation="setup forming",
        instrument_id="SYN-AAA",
        direction=Direction.NONE,
    )


class TestConfig:
    def test_loads_notifications_config(self, config_dir):
        cfg = load_notifications_config(config_dir)
        assert cfg.enabled is True
        assert cfg.channels.file.enabled is True
        assert cfg.degrade_without_decisions is True

    def test_missing_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match=r"notifications.json"):
            load_notifications_config(tmp_path)


class TestBuilder:
    def test_ok_with_runs_and_decisions(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        _seed_run(repo, _run("run-1"))
        trace = DecisionTrace(
            decision_ref="d-1",
            stages=(TraceStage("decision", ("d-1",), "real"),),
        )
        cfg = NotificationsConfig()
        builder = DailyBriefingBuilder(
            repo, cfg, tzinfo=IST,
            decision_source=MemoryDecisions([(_decision(), trace)]),
        )
        briefing = builder.build(as_of=AS_OF)
        assert briefing.status is BriefingStatus.OK
        assert len(briefing.runs) == 1
        assert len(briefing.decisions) == 1
        assert briefing.decisions[0].trace_stage_count == 1
        again = builder.build(as_of=AS_OF)
        assert again.to_json() == briefing.to_json()
        repo.close()

    def test_degraded_without_decisions(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        _seed_run(repo, _run("run-1"))
        builder = DailyBriefingBuilder(repo, NotificationsConfig(), tzinfo=IST)
        briefing = builder.build(as_of=AS_OF)
        assert briefing.status is BriefingStatus.DEGRADED
        assert "no_decision_summaries" in briefing.degradation_reasons
        repo.close()

    def test_failed_without_runs(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        builder = DailyBriefingBuilder(repo, NotificationsConfig(), tzinfo=IST)
        with pytest.raises(BriefingError, match=r"no runs found"):
            builder.build(as_of=AS_OF)
        repo.close()


class TestNotifiers:
    def test_file_notifier_writes_artifacts(self, tmp_path):
        repo = SqliteRepository(tmp_path / "a.db")
        repo.initialize()
        _seed_run(repo, _run("run-1"))
        out = tmp_path / "briefings"
        cfg = NotificationsConfig(
            channels=NotificationChannelsConfig(
                file=FileNotifierConfig(enabled=True, output_dir=str(out)),
                webhook=WebhookNotifierConfig(enabled=False),
            ),
        )
        dispatcher = BriefingDispatcher(repo, cfg, tzinfo=IST, repo_root=tmp_path)
        result = dispatcher.dispatch(as_of=AS_OF, dry_run=True)
        assert result.briefing.status is BriefingStatus.DEGRADED
        assert (out / "brief-2026-02-13.json").exists()
        assert (out / "brief-2026-02-13.txt").exists()
        assert result.receipts[0].channel == "file"
        repo.close()

    def test_webhook_requires_env_url(self):
        from athena.notifications.models import BriefingStatus as BS, DailyBriefing

        notifier = WebhookNotifier(url="")
        minimal = DailyBriefing(
            briefing_id="brief-x",
            as_of=AS_OF,
            status=BS.DEGRADED,
            runs=(),
            decisions=(),
            text_summary="x\n",
            machine={"briefing_id": "brief-x"},
            degradation_reasons=("no_decision_summaries",),
        )
        with pytest.raises(BriefingError, match=r"ATHENA_WEBHOOK_URL"):
            notifier.notify(minimal)

    def test_webhook_posts_json(self, monkeypatch):
        from athena.notifications.models import DailyBriefing, BriefingStatus as BS

        captured: dict = {}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def getcode(self):
                return 200

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["body"] = request.data
            captured["timeout"] = timeout
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        notifier = WebhookNotifier(url="https://example.test/hook", timeout_seconds=5)
        briefing = DailyBriefing(
            briefing_id="brief-2026-02-13",
            as_of=AS_OF,
            status=BS.DEGRADED,
            runs=(),
            decisions=(),
            text_summary="summary\n",
            machine={"briefing_id": "brief-2026-02-13", "status": "DEGRADED"},
            degradation_reasons=("no_decision_summaries",),
        )
        receipt = notifier.notify(briefing)
        assert receipt.ok
        assert captured["url"] == "https://example.test/hook"
        assert b"brief-2026-02-13" in captured["body"]
        assert captured["timeout"] == 5
