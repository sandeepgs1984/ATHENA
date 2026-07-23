"""Host due-ops runner (R5): evaluate cadence → cycle(s) → optional brief → alert on hard fail.

Invoked by external launchd/cron via ``athena run-due``. No embedded scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.config.models import AthenaConfig, HostOpsConfig, NotificationsConfig, SchedulingConfig
from athena.data.ingestion.engine import LiveIngestionEngine
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunTrigger
from athena.errors import AthenaError
from athena.notifications import BriefingDispatcher
from athena.notifications.decision_source import SqliteDecisionSummarySource
from athena.ops.failure_alerts import FailureAlertDispatcher
from athena.scheduling import DryRunCycleOrchestrator, due_triggers
from athena.scheduling.dry_run import DryRunCycleResult


@dataclass(frozen=True, slots=True)
class HostDueRunResult:
    as_of: datetime
    due: tuple[RunTrigger, ...]
    cycles: tuple[DryRunCycleResult, ...]
    briefing_id: str | None
    idle: bool
    alerted: bool


class HostDueRunner:
    """Run whatever PREMARKET/REFRESH/CLOSING triggers are due, then optionally brief."""

    def __init__(
        self,
        *,
        cfg: AthenaConfig,
        sched: SchedulingConfig,
        host_ops: HostOpsConfig,
        notify_cfg: NotificationsConfig,
        repo: SqliteRepository,
        ingest_engine: LiveIngestionEngine,
        repo_root: Path,
        tzinfo: ZoneInfo,
        strategy_profile: str,
        alert_dispatcher: FailureAlertDispatcher | None = None,
    ) -> None:
        self._cfg = cfg
        self._sched = sched
        self._host_ops = host_ops
        self._notify_cfg = notify_cfg
        self._repo = repo
        self._ingest = ingest_engine
        self._repo_root = Path(repo_root)
        self._tzinfo = tzinfo
        self._strategy_profile = strategy_profile
        self._alerts = alert_dispatcher or FailureAlertDispatcher(
            host_ops.failure_alerts,
            repo_root=self._repo_root,
            tzinfo=tzinfo,
        )

    def run(self, *, as_of: datetime, send_brief: bool | None = None, alert: bool = True) -> HostDueRunResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        last_premarket_date = None
        last_refresh_ts = None
        last_closing_date = None
        pre = self._repo.latest_run(RunTrigger.PREMARKET.value)
        if pre is not None:
            last_premarket_date = pre.started_ts.astimezone(self._tzinfo).date()
        ref = self._repo.latest_run(RunTrigger.REFRESH.value)
        if ref is not None:
            last_refresh_ts = ref.started_ts
        closing = self._repo.latest_run(RunTrigger.CLOSING.value)
        if closing is not None:
            last_closing_date = closing.started_ts.astimezone(self._tzinfo).date()

        due = due_triggers(
            as_of,
            sessions=self._cfg.market.sessions,
            config=self._sched,
            base_interval_minutes=self._cfg.base.refresh_interval_minutes,
            last_premarket_date=last_premarket_date,
            last_refresh_ts=last_refresh_ts,
            last_closing_date=last_closing_date,
        )

        do_brief = self._host_ops.brief_after_cycles if send_brief is None else send_brief
        cycles: list[DryRunCycleResult] = []

        if not due:
            if self._host_ops.brief_when_idle and do_brief:
                briefing_id = self._dispatch_brief(as_of)
                return HostDueRunResult(
                    as_of=as_of, due=(), cycles=(), briefing_id=briefing_id, idle=True, alerted=False,
                )
            return HostDueRunResult(
                as_of=as_of, due=(), cycles=(), briefing_id=None, idle=True, alerted=False,
            )

        orchestrator = DryRunCycleOrchestrator(
            self._ingest,
            self._repo,
            strategy_profile=self._strategy_profile,
            config_snapshot_id="cfg-host-ops",
        )

        try:
            for trigger in due:
                result = orchestrator.run_cycle(trigger, as_of=as_of)
                cycles.append(result)

            briefing_id = None
            if do_brief:
                briefing_id = self._dispatch_brief(as_of)

            return HostDueRunResult(
                as_of=as_of,
                due=due,
                cycles=tuple(cycles),
                briefing_id=briefing_id,
                idle=False,
                alerted=False,
            )
        except AthenaError as exc:
            if (
                alert
                and self._host_ops.failure_alerts.enabled
                and self._host_ops.alert_on_failed_run
            ):
                self._alerts.dispatch(
                    title="athena run-due hard failure",
                    detail=str(exc),
                    source="run-due",
                    as_of=as_of,
                )
            raise
    def _dispatch_brief(self, as_of: datetime) -> str:
        dispatcher = BriefingDispatcher(
            self._repo,
            self._notify_cfg,
            tzinfo=self._tzinfo,
            repo_root=self._repo_root,
            decision_source=SqliteDecisionSummarySource(self._repo, tzinfo=self._tzinfo),
        )
        result = dispatcher.dispatch(as_of=as_of, dry_run=False)
        return result.briefing.briefing_id
