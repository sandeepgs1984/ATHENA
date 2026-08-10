"""Host due-ops runner (R5): evaluate cadence → cycle(s) → optional brief → alert on hard fail.

Invoked by external launchd/cron via ``athena run-due``. No embedded scheduler.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.models import AthenaConfig, HostOpsConfig, NotificationsConfig, SchedulingConfig
from athena.data.ingestion.engine import LiveIngestionEngine
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunTrigger, SessionType
from athena.errors import AthenaError
from athena.notifications import BriefingDispatcher
from athena.notifications.decision_source import SqliteDecisionSummarySource
from athena.ops.canary import CanaryResult, run_canary
from athena.ops.failure_alerts import FailureAlertDispatcher
from athena.ops.fast_revalidation import run_fast_revalidation_cycle
from athena.scheduling import DryRunCycleOrchestrator, due_triggers
from athena.scheduling.dry_run import DryRunCycleResult, DryRunPipeline

# Session types where the exchange genuinely isn't open — no live quote can
# ever be "fresh" on these days, so no PREMARKET/REFRESH/CLOSING trigger
# should ever fire regardless of configured session hours.
_NON_TRADING_SESSION_TYPES = frozenset({SessionType.WEEKEND, SessionType.HOLIDAY})


@dataclass(frozen=True, slots=True)
class HostDueRunResult:
    as_of: datetime
    due: tuple[RunTrigger, ...]
    cycles: tuple[DryRunCycleResult, ...]
    briefing_id: str | None
    idle: bool
    alerted: bool
    # M-X8: additive, defaults to None for every existing caller/construction
    # site. None means "not run this tick" (idle tick, or no config_dir
    # wired) — not "ran and passed"; only a CanaryResult with ok=True means that.
    canary: CanaryResult | None = None


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
        ingest_engine: LiveIngestionEngine | Callable[[], LiveIngestionEngine],
        repo_root: Path,
        tzinfo: ZoneInfo,
        strategy_profile: str,
        alert_dispatcher: FailureAlertDispatcher | None = None,
        pipeline: DryRunPipeline | None = None,
        calendar: CalendarEngine | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self._cfg = cfg
        self._sched = sched
        self._host_ops = host_ops
        self._notify_cfg = notify_cfg
        self._repo = repo
        # Owner-reported (2026-08-10): building this eagerly meant every
        # 60s cycle-worker tick paid for a live Kite catalog fetch (~1s+)
        # to construct the engine, even on the common idle tick where
        # due_triggers() below finds nothing to do and self._ingest is
        # never touched. Accepting a zero-arg factory alongside a plain
        # instance (existing callers are unaffected) lets the caller defer
        # that cost to only the ticks where a cycle actually runs.
        self._ingest = ingest_engine
        self._repo_root = Path(repo_root)
        self._tzinfo = tzinfo
        self._strategy_profile = strategy_profile
        self._pipeline = pipeline
        # Owner-reported (2026-08-01): both optional and independently
        # injectable (matching `pipeline` above) so every existing caller
        # that passes neither keeps running exactly as before — this is an
        # opt-in fix, not a behavior change for anyone who hasn't wired the
        # calendar through yet. Pass `calendar` directly (e.g. from a test)
        # or `config_dir` to build one from `cfg.market` at call time.
        self._calendar = calendar
        self._config_dir = config_dir
        self._alerts = alert_dispatcher or FailureAlertDispatcher(
            host_ops.failure_alerts,
            repo_root=self._repo_root,
            tzinfo=tzinfo,
        )

    def _is_trading_day(self, as_of: datetime) -> bool:
        """True unless the calendar authority says today is a weekend/holiday.

        No calendar wired in (neither `calendar` nor `config_dir` given) —
        preserve the pre-fix behavior exactly rather than guessing.
        """
        calendar = self._calendar
        if calendar is None:
            if self._config_dir is None:
                return True
            calendar = CalendarEngine.from_config_dir(self._config_dir, self._cfg.market)
        context = calendar.context_for(as_of.date())
        return context.session_type not in _NON_TRADING_SESSION_TYPES

    def run(self, *, as_of: datetime, send_brief: bool | None = None, alert: bool = True) -> HostDueRunResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        last_premarket_date = None
        last_refresh_ts = None
        last_closing_date = None
        last_fast_ts = None
        pre = self._repo.latest_run(RunTrigger.PREMARKET.value)
        if pre is not None:
            last_premarket_date = pre.started_ts.astimezone(self._tzinfo).date()
        ref = self._repo.latest_run(RunTrigger.REFRESH.value)
        if ref is not None:
            last_refresh_ts = ref.started_ts
        closing = self._repo.latest_run(RunTrigger.CLOSING.value)
        if closing is not None:
            last_closing_date = closing.started_ts.astimezone(self._tzinfo).date()
        fast = self._repo.latest_run(RunTrigger.FAST.value)
        if fast is not None:
            last_fast_ts = fast.started_ts

        due = due_triggers(
            as_of,
            sessions=self._cfg.market.sessions,
            config=self._sched,
            base_interval_minutes=self._cfg.base.refresh_interval_minutes,
            last_premarket_date=last_premarket_date,
            last_refresh_ts=last_refresh_ts,
            last_closing_date=last_closing_date,
            last_fast_ts=last_fast_ts,
            is_trading_day=self._is_trading_day(as_of),
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

        ingest = self._ingest() if callable(self._ingest) else self._ingest
        orchestrator = DryRunCycleOrchestrator(
            ingest,
            self._repo,
            pipeline=self._pipeline,
            strategy_profile=self._strategy_profile,
            config_snapshot_id="cfg-host-ops",
        )

        try:
            for trigger in due:
                if trigger is RunTrigger.FAST:
                    # Scoped to the current decision list, not the shared
                    # full-universe self._ingest/self._pipeline used by every
                    # other trigger — see fast_revalidation's own docstring.
                    # No-ops (no config_dir wired, or no decisions to keep
                    # fresh yet) rather than raising, matching _run_canary's
                    # own best-effort fallback for callers that haven't
                    # threaded config_dir through.
                    if self._config_dir is None:
                        continue
                    fast_result = run_fast_revalidation_cycle(
                        self._repo,
                        self._config_dir,
                        as_of=as_of,
                        max_symbols=self._sched.fast.max_symbols,
                        timeframes=self._sched.fast.timeframes,
                        repo_root=self._repo_root,
                    )
                    if fast_result is not None:
                        cycles.append(fast_result)
                    continue
                result = orchestrator.run_cycle(trigger, as_of=as_of)
                cycles.append(result)

            canary = self._run_canary(as_of)

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
                canary=canary,
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
    def _run_canary(self, as_of: datetime) -> CanaryResult | None:
        """M-X8: fixed synthetic instrument through the real pipeline, to
        catch silent engine regressions. Best-effort and isolated by
        design — a canary failure (or the canary code itself raising) must
        never block or fail a real scheduled cycle, so every exception here
        is caught, never re-raised. Runs once per host tick (alongside
        whichever real triggers were due this tick), not once per trigger —
        this is a per-tick sanity check, not a per-cycle-type one. Skipped
        (returns None) when no config_dir is wired, matching
        `_is_trading_day`'s own backward-compatible fallback for callers
        that haven't threaded it through yet.
        """
        if self._config_dir is None:
            return None
        try:
            result = run_canary(
                self._config_dir, as_of=as_of, run_id=f"canary-{as_of.isoformat()}"
            )
        except Exception as exc:  # the canary must never break a real cycle
            result = CanaryResult(
                ok=False, reasons=(f"canary itself raised: {exc!r}",),
                decision_type=None, composite_value=None,
            )
        if result.ok or not self._host_ops.failure_alerts.enabled:
            return result
        with contextlib.suppress(Exception):  # alert delivery failing must not break the cycle
            self._alerts.dispatch(
                title="ATHENA canary regression detected",
                detail="; ".join(result.reasons) or "unknown canary failure",
                source="canary",
                as_of=as_of,
            )
        return result

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
