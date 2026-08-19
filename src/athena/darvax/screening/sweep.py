"""Owner-triggered universe sweep (DX-6b, ADR-010 Amendment 2).

One sweep at a time, started by the owner, cancellable, running on a daemon
thread. Deliberately mirrors the *shape* of ATHENA's ADR-007 full-universe
validation job without importing any of it: ADR-010 permits DarvaX to import
frozen domain objects and read-only contracts, and reusing
``athena.ops.full_validation`` would couple the satellite's lifecycle to
ATHENA's cycle lock — exactly the dependency the satellite exists to avoid.

**Still forbidden, and not present here:** queues, schedulers, worker
processes, connection pools, async SQLite, retry/backoff. One thread, started
by a person, stoppable by a person.

Owner decisions this implements (2026-08-14):

* **Universe** — all ledger instruments via ``list_instruments()``, which is
  precisely what Amendment 2 authorised. DarvaX forms its own opinion on
  everything rather than inheriting ATHENA's eligibility view, which would have
  meant reading an ATHENA analytical concept and widening a pinned import
  surface.
* **Timeframe** — daily only, matching the deck and ATHENA's swing focus.
* **Retention** — keep the most recent ``screener.retain_sweeps`` sweeps
  (default 30), pruned on completion.

Sweeps are **never scheduled**. That is what keeps the DX-4a finding — a
realistically-used DarvaX imposes no measurable contention on ATHENA — true.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable, Sequence
from decimal import Decimal
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from athena.darvax.config import DarvaxConfig, methodology_digest
from athena.darvax.ports import DarvaxMarketDataPort
from athena.darvax.scan import scan_instruments
from athena.darvax.screening.engine import screen_signals, tier_counts
from athena.darvax.screening.liquidity import (
    LIQUIDITY_WINDOW_BARS,
    traded_value,
)
from athena.darvax.screening.models import SweepRecord
from athena.darvax.screening.trend import TREND_LOOKBACK_BARS, TrendReading, trend_reading
from athena.darvax.signals.models import DarvaxSignal
from athena.darvax.store.repository import DarvaxRepository
from athena.domain.enums import Timeframe
from athena.errors import AthenaError

logger = logging.getLogger(__name__)

#: Owner decision: sweeps are daily. Kept as a named constant rather than an
#: API parameter so the choice is visible and revisited deliberately.
SWEEP_TIMEFRAME = Timeframe.D1


class SweepBusyError(AthenaError):
    """A sweep is already running. Refused, never queued (Amendment 2)."""


@dataclass(frozen=True, slots=True)
class SweepProgress:
    """Transient progress. Never persisted — the sweep *record* is the artifact.

    Deliberately separate from :class:`SweepRecord`: progress is a live view of
    a thread that may not finish, while the record is what survives and can be
    replayed.
    """

    state: str = "idle"
    """``idle`` | ``running`` | ``completed`` | ``cancelled`` | ``failed``."""
    stage: str = "idle"
    sweep_id: str | None = None
    total: int = 0
    evaluated: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0.0
    error: str | None = None

    @property
    def is_running(self) -> bool:
        return self.state == "running"


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _batches(items: Sequence[str], size: int) -> list[Sequence[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


@dataclass
class SweepRunner:
    """Single-flight sweep coordinator, held on the DarvaX app's state.

    An instance rather than module globals: the runner's lifetime is the mounted
    sub-application's, so two apps (a test's and the owner's) cannot contend
    over one another's sweeps, and there is no hidden process-wide state.
    """

    market_data: DarvaxMarketDataPort
    store: DarvaxRepository
    config: DarvaxConfig
    darvax_version: str
    clock: Callable[[], datetime] = _utc_now
    """Injected so tests are deterministic — no hidden clock (ADR-010 §10)."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    _progress: SweepProgress = field(default_factory=SweepProgress, repr=False)

    # ---------------------------------------------------------------- public

    def progress(self) -> SweepProgress:
        with self._lock:
            return self._progress

    def start(self) -> str:
        """Begin a sweep, returning its id. Raises if one is already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise SweepBusyError(
                    "a DarvaX sweep is already running; wait for it to finish or "
                    "cancel it. Sweeps are single-flight and never queued."
                )
            started = self.clock()
            sweep_id = f"swp-{started.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            self._cancel.clear()
            self._progress = SweepProgress(
                state="running", stage="enumerating", sweep_id=sweep_id
            )
            thread = threading.Thread(
                target=self._run,
                args=(sweep_id, started),
                name=f"darvax-sweep-{sweep_id}",
                daemon=True,
            )
            self._thread = thread
        thread.start()
        logger.info("DarvaX sweep %s started (experimental)", sweep_id)
        return sweep_id

    def cancel(self) -> bool:
        """Ask the running sweep to stop. Returns whether one was running.

        Work already completed is kept and the sweep is recorded as partial —
        discarding it would waste real reads and tell the owner less than an
        honestly-labelled partial screen.
        """
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
        if running:
            self._cancel.set()
        return running

    def join(self, timeout: float | None = None) -> None:
        """Wait for the current sweep. For tests and orderly shutdown."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # --------------------------------------------------------------- internal

    def _set(self, **updates: object) -> None:
        with self._lock:
            self._progress = replace(self._progress, **updates)

    def _run(self, sweep_id: str, started: datetime) -> None:
        cancelled = False
        signals: list[DarvaxSignal] = []
        skipped: list[tuple[str, str]] = []
        requested = 0

        try:
            instruments = self.market_data.list_instruments()
            instrument_ids = [i.instrument_id for i in instruments]
            requested = len(instrument_ids)
            self._set(stage="scanning", total=requested)

            # The sweep batches *beneath* scan.max_instruments rather than
            # raising it, so the per-request cap keeps its refuse-not-truncate
            # meaning and no single call can silently misrepresent coverage.
            size = self.config.screener.batch_size or self.config.scan.max_instruments

            # Recorded before the first batch so a crashed sweep leaves a
            # readable row rather than a missing one.
            self.store.save_sweep(
                self._record(sweep_id, started, "running", signals, skipped, requested)
            )

            for batch in _batches(instrument_ids, size):
                if self._cancel.is_set():
                    cancelled = True
                    break
                result = scan_instruments(
                    market_data=self.market_data,
                    store=self.store,
                    config=self.config,
                    instrument_ids=batch,
                    timeframe=SWEEP_TIMEFRAME,
                )
                signals.extend(result.signals)
                skipped.extend((s.instrument_id, s.reason) for s in result.skipped)
                self._set(
                    evaluated=len(signals),
                    skipped=len(skipped),
                    elapsed_seconds=(self.clock() - started).total_seconds(),
                )

            self._set(stage="screening")
            # Holdings are resolved once per sweep, not per instrument, and
            # handed to the engine — which stays pure and does no lookups
            # (DX-7b). A sweep that read the position store per signal would
            # also let holdings change mid-sweep, so one screen could disagree
            # with itself about what is held.
            held = self.store.open_positions_by_instrument()
            # Liquidity and trend are measured here rather than in the engine:
            # both need candles, and the screening layer deliberately has no
            # market-data access. One read per instrument, on top of the
            # lookback the scan already performs, serves both (DX-12a).
            liquidity, trend = self._context_for(signals)
            results = screen_signals(
                signals,
                sweep_id=sweep_id,
                positions=held,
                liquidity=liquidity,
                trend=trend,
            )
            self.store.save_screen_results(results)

            state = "cancelled" if cancelled else "completed"
            self.store.save_sweep(
                self._record(
                    sweep_id, started, state, signals, skipped, requested,
                    finished=True, partial=cancelled,
                )
            )

            if not cancelled:
                pruned = self.store.prune_sweeps(self.config.screener.retain_sweeps)
                if pruned:
                    logger.info("DarvaX pruned %d old sweep(s)", pruned)

            self._set(
                state=state,
                stage=state,
                evaluated=len(signals),
                skipped=len(skipped),
                elapsed_seconds=(self.clock() - started).total_seconds(),
            )
            logger.info(
                "DarvaX sweep %s %s: %d evaluated, %d skipped",
                sweep_id, state, len(signals), len(skipped),
            )
        except Exception as exc:  # a failed sweep must say so, not vanish
            logger.exception("DarvaX sweep %s failed", sweep_id)
            self._set(state="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")
            try:
                self.store.save_sweep(
                    self._record(
                        sweep_id, started, "failed", signals, skipped, requested,
                        finished=True, partial=True,
                    )
                )
            except Exception:  # pragma: no cover - persistence already broken
                logger.exception("DarvaX sweep %s could not record its failure", sweep_id)

    def _context_for(
        self, signals: Sequence[DarvaxSignal]
    ) -> tuple[dict[str, Decimal], dict[str, TrendReading]]:
        """Liquidity and 50/100-EMA trend per instrument, from one candle read.

        Both need candles the screening engine cannot fetch itself (it has no
        market-data access by design), so both are measured here — sharing a
        single per-instrument read rather than two, now that DX-12a adds a
        second candle-derived measurement alongside DX-10a's liquidity. The
        window is sized to the longer requirement (100-session EMA); liquidity
        reads only the trailing slice of it it actually needs.

        A read failure on one instrument must not cost the sweep — the same
        per-instrument isolation the scan already applies — so a symbol whose
        candles cannot be read is simply absent from both maps and reports as
        unmeasured rather than as illiquid or trendless.
        """
        liquidity: dict[str, Decimal] = {}
        trend: dict[str, TrendReading] = {}
        window = max(LIQUIDITY_WINDOW_BARS, TREND_LOOKBACK_BARS)
        for signal in signals:
            try:
                candles = self.market_data.recent_candles(
                    signal.instrument_id,
                    SWEEP_TIMEFRAME,
                    limit=window,
                )
            except Exception:  # one instrument must never cost the run
                continue
            value = traded_value(candles)
            if value is not None:
                liquidity[signal.instrument_id] = value
            trend[signal.instrument_id] = trend_reading(candles)
        return liquidity, trend

    def _record(
        self,
        sweep_id: str,
        started: datetime,
        state: str,
        signals: Sequence[DarvaxSignal],
        skipped: Sequence[tuple[str, str]],
        requested: int,
        *,
        finished: bool = False,
        partial: bool = False,
    ) -> SweepRecord:
        screened = (
            screen_signals(
                signals,
                sweep_id=sweep_id,
                positions=self.store.open_positions_by_instrument(),
            )
            if signals
            else ()
        )
        return SweepRecord(
            sweep_id=sweep_id,
            started_at=started,
            finished_at=self.clock() if finished else None,
            state=state,
            # The newest bar any signal was computed from — what the screen is
            # "as of", and what the UI compares against the latest trading day.
            as_of=max((s.as_of for s in signals), default=None),
            methodology_digest=methodology_digest(self.config.methodology),
            darvax_version=self.darvax_version,
            requested=requested,
            evaluated=len(signals),
            tier_counts=tier_counts(screened),
            skipped=tuple(skipped),
            partial=partial,
        )
