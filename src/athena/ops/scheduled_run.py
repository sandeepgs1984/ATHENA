"""Host due-ops runner (R5): evaluate cadence → cycle(s) → optional brief → alert on hard fail.

Invoked by external launchd/cron via ``athena run-due``. No embedded scheduler.
"""

from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.models import AthenaConfig, HostOpsConfig, NotificationsConfig, SchedulingConfig
from athena.data.ingestion.engine import LiveIngestionEngine
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import RunStatus, RunTrigger, SessionType
from athena.domain.run import RunRecord
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

# 2026-09-08 scheduler correctness correction: `DryRunCycleOrchestrator`
# (the only writer of a `RUNNING` run row) has five real construction
# sites in this repository -- `HostDueRunner.run()` itself
# ("cfg-host-ops"), `fast_revalidation.run_fast_revalidation_cycle`
# ("cfg-fast-revalidation", one call site, only reachable from inside
# `run()`), the owner-triggered "Validate All" job
# (`full_validation._run_job`, "cfg-full-validation", which explicitly
# acquires the same `CycleRunnerLock` before running), `athena cycle`
# (`cli._cmd_cycle`, "cfg-cli"), and the dashboard's on-demand
# single-symbol "Validate" (`symbol_validate.validate_symbols`,
# "cfg-symbol-validate"). Only the first three ever contend for
# `CycleRunnerLock` -- `_reconcile_if_orphaned` below may reconcile a
# `RUNNING` row ONLY when its `config_snapshot_id` is one of these three;
# a "cfg-cli"/"cfg-symbol-validate" (or any unrecognized) `RUNNING` row
# could be a genuinely live, unrelated run and must never be touched.
_LOCK_PROTECTED_CONFIG_SNAPSHOT_IDS = frozenset(
    {"cfg-host-ops", "cfg-fast-revalidation", "cfg-full-validation"}
)


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

    def _reconcile_if_orphaned(self, trigger: RunTrigger, *, as_of: datetime) -> RunRecord | None:
        """Resolve the latest run of ``trigger``, reconciling it first if it
        is a *provably* dead orphan.

        **The lock-ownership proof is scope-limited, not universal.**
        `DryRunCycleOrchestrator.run_cycle` -- the only place a `RUNNING`
        row for PREMARKET/REFRESH/CLOSING/FAST is ever written -- has five
        real construction sites in this repository, and only three of them
        acquire the same `CycleRunnerLock` (`artifacts/locks/cycle-runner.lock`)
        this invocation holds while `run()` executes:

        - `config_snapshot_id="cfg-host-ops"` (`HostDueRunner.run()` itself,
          `ops/scheduled_run.py`) -- locked, via its own two callers
          (`_cmd_run_due`, `CycleWorker._safe_tick`, the only two places
          `HostDueRunner` is ever constructed).
        - `config_snapshot_id="cfg-fast-revalidation"` (`run_fast_revalidation_cycle`,
          `ops/fast_revalidation.py`) -- locked transitively: it has exactly
          one call site anywhere in the repo, inside `run()`'s own FAST
          branch, so it can only ever run while `run()`'s own caller
          already holds the lock.
        - `config_snapshot_id="cfg-full-validation"` (the owner-triggered
          "Validate All" background job, `ops/full_validation.py`) --
          explicitly acquires the *same* `CycleRunnerLock`
          (`_run_job`'s own `lock.acquire()`) before calling `run_cycle`.

        Two more construction sites exist and are **not** lock-protected at
        all: `config_snapshot_id="cfg-cli"` (`athena cycle`, `_cmd_cycle` in
        `cli.py`) and `config_snapshot_id="cfg-symbol-validate"` (the
        dashboard's on-demand single-symbol "Validate", `ops/symbol_validate.py`)
        -- neither references `CycleRunnerLock` anywhere in its source, so
        either can be genuinely, legitimately `RUNNING` at the exact moment
        this invocation holds the lock (they simply don't contend for it).
        A `RUNNING` row from either of those must **never** be reconciled --
        doing so would falsely mark a live, unrelated run as `FAILED`.

        So: a `RUNNING` row is reconciled to `FAILED` for durable audit
        truth (never deleted, never silently reinterpreted as `COMPLETED`)
        -- and, only for *this invocation's own* due-calculation inputs,
        treated as absent so the now-eligible trigger can retry immediately
        instead of waiting out a full interval again -- **only when its
        `config_snapshot_id` is one of the three proven lock-protected
        values.** Any other `RUNNING` row (a known-unlocked provenance, or
        an unrecognized future one) is passed through completely unchanged
        -- exactly the pre-existing, pre-this-correction behavior for that
        row, since this correction has no basis to reason about it either
        way.

        A subsequent invocation always sees the durable result of whatever
        happened (a reconciled `FAILED`, or the row's own real outcome) and
        that row then participates in cadence exactly as any other
        `FAILED`/`COMPLETED` run already does today -- this method makes no
        change to that pre-existing, separate policy question, and it does
        not add a provenance filter to ordinary (non-`RUNNING`) cadence
        inputs, which continue to come from whichever run has the newest
        `started_ts` for that trigger regardless of `config_snapshot_id`
        (a pre-existing characteristic of `latest_run()`, unrelated to and
        unchanged by this correction).
        """
        row = self._repo.latest_run(trigger.value)
        if row is None:
            return None
        if row.status is not RunStatus.RUNNING:
            return row
        if row.config_snapshot_id not in _LOCK_PROTECTED_CONFIG_SNAPSHOT_IDS:
            return row
        reconciled = dataclasses.replace(row, status=RunStatus.FAILED, finished_ts=as_of)
        self._repo.save_run(
            reconciled,
            detail={
                "phase": "reconciled_orphan",
                "reason": "previous RUNNING run cannot still own the cycle-runner lock "
                "while this invocation holds it",
            },
        )
        return None

    def run(self, *, as_of: datetime, send_brief: bool | None = None, alert: bool = True) -> HostDueRunResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        last_premarket_date = None
        last_refresh_ts = None
        last_closing_date = None
        last_fast_ts = None
        pre = self._reconcile_if_orphaned(RunTrigger.PREMARKET, as_of=as_of)
        if pre is not None:
            last_premarket_date = pre.started_ts.astimezone(self._tzinfo).date()
        ref = self._reconcile_if_orphaned(RunTrigger.REFRESH, as_of=as_of)
        if ref is not None:
            last_refresh_ts = ref.started_ts
        closing = self._reconcile_if_orphaned(RunTrigger.CLOSING, as_of=as_of)
        if closing is not None:
            last_closing_date = closing.started_ts.astimezone(self._tzinfo).date()
        fast = self._reconcile_if_orphaned(RunTrigger.FAST, as_of=as_of)
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
            # ID-7P0: opt-in, observational-only cycle-phase timing (never
            # affects Decision/EntryQualification/business behavior) on the
            # real scheduled PREMARKET/REFRESH/CLOSING path, to attribute
            # the ~9-10 minute cycle duration between ingestion and the
            # analytical scan with measured evidence.
            enable_timing=True,
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
