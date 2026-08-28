"""EM-5's checkpoint-reference-price collector -- the ONE narrow,
auditable, batched Kite `/quote` seam EM-5 is authorized to use (Owner
amendment, 2026-08-28, superseding the original "zero provider/network
calls" contract item: exact checkpoint-price semantics cannot be
reproduced from already-completed canonical candles at checkpoint C,
proven by the live parity diagnostic -- see
`docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` Section 2).

This is the only file under `athena.explosive_move` permitted to import
Kite provider/transport machinery (enforced by
`tests/explosive_move/test_em5_isolation.py`). It wraps the already-
tested dual-timestamp capture logic from the diagnostic module
unmodified -- reused, not reimplemented.

Frozen live semantic (Owner-approved, precise wording): the checkpoint
reference price is `FIRST_OBSERVED_POST_CHECKPOINT_TRADE` -- the
`last_price` belonging to the first Kite `/quote` snapshot THIS
COLLECTOR OBSERVED whose authoritative `last_trade_time >= C`. Not a
claim of the literal first exchange trade after C (a snapshot-based
poll cannot prove that), and never Kite's generic `timestamp` field,
which remains persisted separately as snapshot provenance only.

Frozen bound: `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS = 300` --
deliberately above the diagnostic's observed maximum real latency
(188s), not fitted to that small sample. EM-5 must not dynamically
retune this. No fallback to a prior candle's close, a stale/pre-C LTP,
the generic snapshot timestamp, a later completed candle, or any
fabricated/interpolated value: `NO_CHECKPOINT_PRICE` when the bound
elapses with no qualifying observation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from athena.data.em5_checkpoint_price_diagnostic import (
    DualTimestampObservation,
    build_diagnostic_transport,
    fetch_dual_timestamp_quotes,
)

CHECKPOINT_PRICE_SEMANTIC = "FIRST_OBSERVED_POST_CHECKPOINT_TRADE"
MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS = 300.0
DEFAULT_POLL_INTERVAL_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class CheckpointReferencePrice:
    """The narrow domain object EM-5's live path actually consumes --
    keeps `snapshot_timestamp` and `last_trade_time` explicitly
    separate, never conflated (the exact distinction the parity
    diagnostic found the shared `Quote` type collapses)."""

    instrument_id: str
    checkpoint_instant: datetime
    reference_price_semantic: str  # always CHECKPOINT_PRICE_SEMANTIC
    last_price: Decimal
    last_trade_time: datetime
    snapshot_timestamp: datetime | None
    latency_seconds: float
    provider: str


def _to_reference_price(
    iid: str, checkpoint_instant: datetime, obs: DualTimestampObservation,
) -> CheckpointReferencePrice:
    latency = (obs.last_trade_time - checkpoint_instant).total_seconds()
    return CheckpointReferencePrice(
        instrument_id=iid, checkpoint_instant=checkpoint_instant,
        reference_price_semantic=CHECKPOINT_PRICE_SEMANTIC,
        last_price=obs.last_price, last_trade_time=obs.last_trade_time,
        snapshot_timestamp=obs.api_timestamp, latency_seconds=latency, provider="kite",
    )


def collect_checkpoint_reference_prices(
    *,
    instrument_ids: tuple[str, ...], checkpoint_instant: datetime, config_dir: Path | None = None,
    max_delay_seconds: float = MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    fetch: object | None = None, now: object | None = None, sleep: object | None = None,
) -> tuple[dict[str, CheckpointReferencePrice], tuple[str, ...], int]:
    """Returns (qualified, no_checkpoint_price, quote_request_count).

    Batched: every poll is ONE `/quote` request covering every instrument
    still unqualified (never one request per symbol). Stops polling an
    instrument the moment it qualifies. `NO_CHECKPOINT_PRICE` (returned
    in `no_checkpoint_price`, never fabricated) for any instrument that
    never observes `last_trade_time >= checkpoint_instant` within
    `max_delay_seconds`.

    `fetch`/`now`/`sleep` are injectable (same seam the diagnostic module
    already established) so the polling loop itself is unit-testable
    without any live Kite call; production callers omit them and get a
    real transport built from `config_dir` plus real `time.monotonic`/
    `time.sleep`."""

    if fetch is None:
        if config_dir is None:
            raise ValueError("config_dir is required when fetch is not injected")
        transport = build_diagnostic_transport(config_dir)

        def fetch(ids, poll_ts):
            return fetch_dual_timestamp_quotes(transport, ids, poll_request_ts=poll_ts)

    now = now or time.monotonic
    sleep = sleep or time.sleep

    remaining = list(instrument_ids)
    qualified: dict[str, CheckpointReferencePrice] = {}
    request_count = 0
    started = now()

    while remaining and (now() - started) < max_delay_seconds:
        poll_ts = datetime.now(tz=checkpoint_instant.tzinfo)
        batch = fetch(tuple(remaining), poll_ts)
        request_count += 1
        still_remaining = []
        for iid in remaining:
            obs = batch.get(iid)
            if obs is not None and obs.last_trade_time is not None and obs.last_trade_time >= checkpoint_instant:
                qualified[iid] = _to_reference_price(iid, checkpoint_instant, obs)
            else:
                still_remaining.append(iid)
        remaining = still_remaining
        if remaining:
            sleep(poll_interval_seconds)

    return qualified, tuple(remaining), request_count
