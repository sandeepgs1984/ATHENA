"""EM-7B: the isolated EMR live-shadow scheduling/invocation layer
(ADR-014 §§9-23, owner-authorized 2026-09-03).

Fully owned by `athena.explosive_move` (ADR-012/ADR-014's frozen
dependency direction: `EMR worker -> EMR scanner -> EMR repository ->
EMR read-only market-data port`, never the reverse, never through
canonical `ops`/`scheduling`). Structurally mirrors
`athena.ops.serve_runtime.CycleWorker` (a daemon thread, a
`threading.Event`-gated interval loop, a try/except-wrapped tick) and
DarvaX's config-gated mount pattern -- WITHOUT importing either. This is
the same small-duplication trade-off `EmrScanLock` already made against
`CycleRunnerLock` (EM-7A).

Two layers, deliberately kept separate:

* `run_once` -- a pure, synchronous, fully injectable single tick. No
  thread, no sleep, no `datetime.now()` inside it. This is the layer
  every test in `test_em7b_worker.py` exercises directly.
* `EmrWorker` -- a thin daemon-thread wrapper around repeated `run_once`
  calls, for eventual unattended operation. Gated on
  `operational_config.enabled` at `start()` itself, not only inside
  `run_once`, so a disabled worker never even creates a thread.

Every EM-7A/EM-7A.1/EM-7A.2 contract (`run_scan_cycle`,
`run_scan_cycle_with_lock`, `EmrScanLock`, `commit_scan_result`,
`mark_scan_failed`, the `RUNNING -> COMPLETE | FAILED` lifecycle, the
in-memory-only `SKIPPED_SESSION_TYPE` eligibility outcome, mandatory
`regime_lookup`) is used exactly as frozen -- this module adds
scheduling/invocation around them, never redesigns them.

**Checkpoint-due / catch-up policy (ADR-014 §7-8 of the EM-7B
authorization; audited before deciding, not assumed):** a source search
of ADR-014, the EM-5 design contract, `docs/research/EM-7-DISCOVERY.md`,
and the EM-5 Track B live-capture record found zero methodological
requirement that every one of the 9 daily checkpoints be independently
captured by an ongoing shadow worker -- Track B's own one-time,
all-9-checkpoint capture was a deliberate historical exercise validating
settlement/provisional-price semantics for one specific date, not a
standing operational contract for a restarting worker. No evidence
contradicts the owner's own stated preference, so `run_once` implements
it directly: on every tick, derive at most the single LATEST due
checkpoint not yet represented in `emr_scan_runs`; never attempt to
back-fill earlier missed checkpoints in a burst. "Not yet represented"
means the checkpoint's deterministic `run_id` has no persisted `COMPLETE`
or `FAILED` row -- both are treated as terminal for the worker's own
automatic scheduling purposes (avoiding an automatic FAILED-retry storm
on every poll interval, per §20 of the authorization); a `RUNNING` row
is NOT pre-filtered here -- the worker still attempts, and
`run_scan_cycle`'s own dispatch raises `EmrScanAlreadyRunningError`,
caught below and treated as "checkpoint already owned," never spun on
faster than the normal poll cadence.

**Universe-policy wiring (ADR-014 §11):** `run_scan_cycle`'s frozen
`ScanCycleConfig.universe` field is a plain name resolved internally,
with no parameter for an explicit instrument-id list, and the read-only
`EmrMarketDataPort` has no write method to materialize a new persisted
universe (correctly, by ADR-012 isolation). `_MatureHistoryMarketDataPort`
below is the resolution: a worker-owned wrapper implementing the same
`EmrMarketDataPort` Protocol, whose `resolved_universe()` returns the
already-computed `select_mature_history_instruments()` output for one
worker-chosen label -- `run_scan_cycle` itself is never touched, never
gains a new parameter, and behaves exactly as before from its own
perspective.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type
from pathlib import Path

from athena.calendar.engine import CalendarEngine
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument
from athena.explosive_move.contracts import CANDIDATE_CHECKPOINTS_IST
from athena.explosive_move.live.canary_gate import select_mature_history_instruments
from athena.explosive_move.live.eligibility import session_is_scannable
from athena.explosive_move.live.market_data_port import EmrMarketDataPort, SqliteEmrMarketDataAdapter
from athena.explosive_move.live.operational_config import EmrOperationalConfig
from athena.explosive_move.live.regime_source import build_canonical_regime_lookup
from athena.explosive_move.live.scan_lock import EmrScanLock, EmrScanLockBusyError, default_emr_scan_lock_path
from athena.explosive_move.live.scanner import (
    EmrScanAlreadyRunningError,
    ScanCycleConfig,
    ScanCycleResult,
    compute_run_id,
    run_scan_cycle_with_lock,
)
from athena.explosive_move.store.repository import EmrRepository

logger = logging.getLogger(__name__)

#: The vocabulary `EmrWorkerTickOutcome.action` is restricted to --
#: exhaustive, checked by tests, so a new outcome case can't silently
#: appear without also being tested/documented.
EMR_WORKER_TICK_ACTIONS: frozenset[str] = frozenset({
    "DISABLED", "NON_SCANNABLE_SESSION", "NO_CHECKPOINT_DUE", "ALREADY_REPRESENTED",
    "INVOKED", "ALREADY_RUNNING", "LOCK_BUSY", "UNEXPECTED_ERROR",
})

#: Suffix distinguishing the worker's mature-history-filtered label from
#: the raw base universe name -- ADR-014 §11 confirms the two are
#: factually distinct populations; using a different label keeps a
#: hypothetical future full-universe scan's run_id from ever colliding
#: with this one for the same (session_date, checkpoint, model_version).
_LIVE_SHADOW_UNIVERSE_LABEL_SUFFIX = "-mature-history"


def _universe_label(base_universe: str) -> str:
    return f"{base_universe}{_LIVE_SHADOW_UNIVERSE_LABEL_SUFFIX}"


def _parse_checkpoint_time(checkpoint: str) -> time_of_day:
    hour_str, minute_str = checkpoint.split(":")
    return time_of_day(int(hour_str), int(minute_str))


def _latest_due_checkpoint(
    *, now: datetime, session_date: date, tzinfo: tzinfo_type, checkpoints: tuple[str, ...],
) -> str | None:
    """`checkpoints` is already chronologically ascending
    (`CANDIDATE_CHECKPOINTS_IST`'s own frozen order) -- the last entry
    whose instant has arrived is the latest due one."""
    due = [
        cp for cp in checkpoints
        if datetime.combine(session_date, _parse_checkpoint_time(cp), tzinfo=tzinfo) <= now
    ]
    return due[-1] if due else None


class _MatureHistoryMarketDataPort:
    """Wraps a real, read-only `EmrMarketDataPort` so the scanner sees
    exactly the frozen mature-history population (ADR-014 §11) for the
    one universe label this worker owns. `resolved_universe` intercepts
    and returns the precomputed mature subset; `list_instruments`/
    `candles_for_instruments` delegate straight through, unchanged. No
    new eligibility rule -- `select_mature_history_instruments` is reused
    exactly as `canary_gate.py`'s own already-approved canary uses it,
    computed fresh each checkpoint from real, already-ingested D1
    candles -- never a persisted write, never a second universe
    materialized in `db/athena.db`."""

    def __init__(self, *, real_port: EmrMarketDataPort, universe_label: str, mature_ids: tuple[str, ...]) -> None:
        self._real = real_port
        self._universe_label = universe_label
        self._mature_ids = mature_ids

    def list_instruments(self) -> Sequence[Instrument]:
        return self._real.list_instruments()

    def resolved_universe(self, universe: str) -> Sequence[str]:
        if universe != self._universe_label:
            raise ValueError(
                f"_MatureHistoryMarketDataPort is scoped to universe label {self._universe_label!r}, "
                f"got {universe!r} -- this indicates a worker wiring bug, not a data issue"
            )
        return self._mature_ids

    def candles_for_instruments(
        self, instrument_ids: Sequence[str], timeframe: Timeframe, start: datetime, end: datetime,
    ) -> dict[str, list[Candle]]:
        return self._real.candles_for_instruments(instrument_ids, timeframe, start, end)


@dataclass(frozen=True, slots=True)
class EmrWorkerTickOutcome:
    """The result of one `run_once` call. `action` is always one of
    `EMR_WORKER_TICK_ACTIONS`. `scan_result` is populated only when
    `action == "INVOKED"` (its own `.status` then distinguishes
    COMPLETE/FAILED/the in-memory-only SKIPPED_SESSION_TYPE defense-in-
    depth case)."""

    action: str
    session_date: date | None = None
    checkpoint: str | None = None
    detail: str = ""
    scan_result: ScanCycleResult | None = None


def run_once(
    *,
    now: datetime,
    operational_config: EmrOperationalConfig,
    athena_repo: SqliteRepository,
    emr_repo: EmrRepository,
    calendar_engine: CalendarEngine,
    config_dir: Path,
    tzinfo: tzinfo_type,
    collect_checkpoint_prices: Callable[..., tuple[dict, tuple[str, ...], int]],
    checkpoints: tuple[str, ...] = CANDIDATE_CHECKPOINTS_IST,
    lock: EmrScanLock | None = None,
) -> EmrWorkerTickOutcome:
    """One EM-7B worker tick: pure, synchronous, fully injectable (`now`
    is a parameter, never `datetime.now()` internally) -- deterministically
    unit-testable without threads or real sleeps. Never raises: every
    exception from the hardened scanner entrypoint is caught and reported
    as part of the returned outcome, so one bad checkpoint never kills
    the worker loop (Section 19 of the authorization).

    `collect_checkpoint_prices` has no default, mirroring
    `run_scan_cycle`'s own mandatory-`regime_lookup` pattern -- EM-7B
    makes no live provider call itself and ships no silent default that
    could reach one; every caller (test or otherwise) must inject it
    explicitly.
    """
    if not operational_config.enabled:
        return EmrWorkerTickOutcome(
            action="DISABLED", detail="EMR worker is disabled (operational_config.enabled=False)",
        )

    session_date = now.date()
    context = calendar_engine.context_for(session_date)

    # EM-7A.2: session non-scannability is a pre-execution eligibility
    # outcome, never a persisted lifecycle state -- checked here too
    # (worker-level, using the read-only calendar the scanner would
    # otherwise have to be invoked just to learn the same fact from),
    # with the scanner's own identical preflight (unchanged) remaining
    # defense-in-depth against a worker-level bug, not the only guard.
    if not session_is_scannable(context.session_type):
        return EmrWorkerTickOutcome(
            action="NON_SCANNABLE_SESSION", session_date=session_date,
            detail=f"session_type={context.session_type.value}",
        )

    checkpoint = _latest_due_checkpoint(now=now, session_date=session_date, tzinfo=tzinfo, checkpoints=checkpoints)
    if checkpoint is None:
        return EmrWorkerTickOutcome(
            action="NO_CHECKPOINT_DUE", session_date=session_date, detail=f"now={now.isoformat()}",
        )

    universe_label = _universe_label(operational_config.base_universe)
    run_id = compute_run_id(
        session_date=session_date, checkpoint=checkpoint,
        universe=universe_label, model_version=operational_config.model_version,
    )
    existing = emr_repo.get_scan_run(run_id)
    if existing is not None and existing["status"] in ("COMPLETE", "FAILED"):
        # Terminal from the worker's own automatic-scheduling perspective
        # (Section 20): never re-invoke a COMPLETE (the scanner's own
        # short-circuit would make that cheap but pointless) or
        # auto-retry a FAILED checkpoint (that would actually re-run the
        # full scan -- a real retry storm on every poll interval if left
        # unguarded). Manual/owner-triggered retry of a FAILED run
        # remains possible by calling the scanner directly; this worker
        # simply never does so on its own.
        return EmrWorkerTickOutcome(
            action="ALREADY_REPRESENTED", session_date=session_date, checkpoint=checkpoint,
            detail=f"run_id={run_id} status={existing['status']}",
        )

    if context.open_time is None:
        return EmrWorkerTickOutcome(
            action="UNEXPECTED_ERROR", session_date=session_date, checkpoint=checkpoint,
            detail=f"calendar declared session_type={context.session_type.value} scannable but open_time is None",
        )

    real_port = SqliteEmrMarketDataAdapter(athena_repo)
    base_universe_ids = tuple(real_port.resolved_universe(operational_config.base_universe))
    mature_ids = select_mature_history_instruments(
        market_port=real_port, universe_ids=base_universe_ids, session_date=session_date, tzinfo=tzinfo,
    )
    if not mature_ids:
        return EmrWorkerTickOutcome(
            action="UNEXPECTED_ERROR", session_date=session_date, checkpoint=checkpoint,
            detail=(
                f"0 of {len(base_universe_ids)} '{operational_config.base_universe}' instruments meet the "
                "mature-history bar -- refusing to invoke rather than scan an empty/degenerate population"
            ),
        )
    mature_port = _MatureHistoryMarketDataPort(
        real_port=real_port, universe_label=universe_label, mature_ids=mature_ids,
    )
    regime_lookup = build_canonical_regime_lookup(market_port=real_port, config_dir=config_dir, tzinfo=tzinfo)
    checkpoint_instant = datetime.combine(session_date, _parse_checkpoint_time(checkpoint), tzinfo=tzinfo)

    scan_config = ScanCycleConfig(
        universe=universe_label, session_date=session_date, checkpoint=checkpoint,
        checkpoint_instant=checkpoint_instant, session_open_time=context.open_time,
        model_version=operational_config.model_version, config_dir=config_dir,
        max_staleness_minutes=operational_config.max_staleness_minutes,
        max_checkpoint_price_delay_seconds=operational_config.max_checkpoint_price_delay_seconds,
    )

    try:
        result = run_scan_cycle_with_lock(
            lock=lock, config=scan_config, market_port=mature_port, emr_repo=emr_repo,
            calendar_context_session_type=context.session_type,
            collect_checkpoint_prices=collect_checkpoint_prices, regime_lookup=regime_lookup,
            now=lambda: now,
        )
        return EmrWorkerTickOutcome(
            action="INVOKED", session_date=session_date, checkpoint=checkpoint,
            detail=f"run_id={result.run_id} status={result.status}", scan_result=result,
        )
    except EmrScanAlreadyRunningError as exc:
        logger.info("EM-7B: checkpoint %s already owned -- %s", checkpoint, exc)
        return EmrWorkerTickOutcome(
            action="ALREADY_RUNNING", session_date=session_date, checkpoint=checkpoint, detail=str(exc),
        )
    except EmrScanLockBusyError as exc:
        logger.info("EM-7B: EMR scan lock busy -- %s", exc)
        return EmrWorkerTickOutcome(
            action="LOCK_BUSY", session_date=session_date, checkpoint=checkpoint, detail=str(exc),
        )
    except Exception as exc:
        logger.exception("EM-7B: worker tick failed unexpectedly for checkpoint %s", checkpoint)
        return EmrWorkerTickOutcome(
            action="UNEXPECTED_ERROR", session_date=session_date, checkpoint=checkpoint, detail=str(exc),
        )


def _log_outcome(outcome: EmrWorkerTickOutcome) -> None:
    logger.info(
        "EM-7B tick: action=%s session_date=%s checkpoint=%s detail=%s",
        outcome.action, outcome.session_date, outcome.checkpoint, outcome.detail,
    )


class EmrWorker:
    """Background poller invoking `run_once` at a fixed interval.
    Structurally mirrors `athena.ops.serve_runtime.CycleWorker` (a daemon
    thread, a `threading.Event`-gated interval loop, a try/except-wrapped
    tick) WITHOUT importing it (ADR-014 §6/§9) -- the same small
    duplicated shape `EmrScanLock` already accepted against
    `CycleRunnerLock`.

    `start()` is itself gated on `operational_config.enabled` -- a
    disabled worker never creates a background thread at all, so its
    startup has zero EMR persistence side effects at every level, not
    only inside `run_once`. `tick()` is the same synchronous core every
    test calls directly; the thread wrapper adds nothing but timing.
    """

    def __init__(
        self,
        *,
        operational_config: EmrOperationalConfig,
        athena_repo: SqliteRepository,
        emr_repo: EmrRepository,
        calendar_engine: CalendarEngine,
        config_dir: Path,
        tzinfo: tzinfo_type,
        collect_checkpoint_prices: Callable[..., tuple[dict, tuple[str, ...], int]],
        lock_path: Path | None = None,
        now: Callable[[], datetime] | None = None,
        checkpoints: tuple[str, ...] = CANDIDATE_CHECKPOINTS_IST,
    ) -> None:
        self._operational_config = operational_config
        self._athena_repo = athena_repo
        self._emr_repo = emr_repo
        self._calendar_engine = calendar_engine
        self._config_dir = config_dir
        self._tzinfo = tzinfo
        self._collect_checkpoint_prices = collect_checkpoint_prices
        self._lock_path = lock_path or default_emr_scan_lock_path()
        self._now = now or (lambda: datetime.now(tz=tzinfo))
        self._checkpoints = checkpoints
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_outcome: EmrWorkerTickOutcome | None = None

    def tick(self) -> EmrWorkerTickOutcome:
        """One synchronous tick -- safe to call directly without starting
        the background thread; this is what every worker test uses."""
        outcome = run_once(
            now=self._now(), operational_config=self._operational_config,
            athena_repo=self._athena_repo, emr_repo=self._emr_repo,
            calendar_engine=self._calendar_engine, config_dir=self._config_dir, tzinfo=self._tzinfo,
            collect_checkpoint_prices=self._collect_checkpoint_prices, checkpoints=self._checkpoints,
            lock=EmrScanLock(self._lock_path),
        )
        self.last_outcome = outcome
        _log_outcome(outcome)
        return outcome

    def start(self) -> None:
        if not self._operational_config.enabled:
            logger.info("EM-7B: worker disabled (operational_config.enabled=False) -- not starting")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="emr-worker", daemon=True)
        self._thread.start()
        logger.info("EM-7B: worker started (interval=%ss)", self._operational_config.poll_interval_seconds)

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=join_timeout)
        self._thread = None

    def _loop(self) -> None:
        self._safe_tick()
        while not self._stop.wait(self._operational_config.poll_interval_seconds):
            self._safe_tick()

    def _safe_tick(self) -> None:
        try:
            self.tick()
        except Exception:
            logger.exception(
                "EM-7B: worker tick raised past run_once's own boundary -- indicates a bug in run_once itself"
            )
