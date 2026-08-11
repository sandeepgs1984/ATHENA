"""Bounded DarvaX scan: read → evaluate → persist (DX-4).

Thin composition over what already exists — DX-1's read-only port, DX-2's
primitives, DX-3's signal engine — adding no methodology of its own. Its whole
job is to turn "evaluate these instruments" into persisted signals the
``/darvax/`` surface can render.

Two properties worth noting:

* **Explicitly bounded.** The instrument list is capped by
  ``DarvaxScanConfig.max_instruments`` and per-instrument history by
  ``lookback_bars``. DarvaX shares a workstation with ATHENA, and ADR-010's
  performance guarantee is architectural (nothing in ATHENA waits on DarvaX),
  not a promise of zero host-level contention — so the satellite's read load
  stays capped rather than open-ended.
* **Failures are per-instrument, never fatal.** One instrument with unusable
  history is recorded as skipped with its reason; it does not abort the scan or
  discard the instruments already evaluated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from athena.darvax.config import DarvaxConfig
from athena.darvax.ports import DarvaxMarketDataPort
from athena.darvax.signals import DarvaxSignal, evaluate_signal
from athena.darvax.store import DarvaxRepository
from athena.domain.enums import Timeframe
from athena.errors import AthenaError


@dataclass(frozen=True, slots=True)
class SkippedInstrument:
    """One instrument the scan could not evaluate, and why."""

    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Outcome of one bounded scan."""

    signals: tuple[DarvaxSignal, ...]
    skipped: tuple[SkippedInstrument, ...]
    requested: int
    evaluated: int
    timeframe: Timeframe


def scan_instruments(
    *,
    market_data: DarvaxMarketDataPort,
    store: DarvaxRepository,
    config: DarvaxConfig,
    instrument_ids: Sequence[str],
    timeframe: Timeframe = Timeframe.D1,
) -> ScanResult:
    """Evaluate and persist a DarvaX signal per instrument.

    Raises:
        AthenaError: if more instruments are requested than the configured cap
            allows. Refusing loudly is better than silently truncating the
            caller's list and returning a partial answer that looks complete.
    """
    requested = len(instrument_ids)
    cap = config.scan.max_instruments
    if requested > cap:
        raise AthenaError(
            f"DarvaX scan requested {requested} instruments but the configured "
            f"cap is {cap} (darvax.json scan.max_instruments). Split the request "
            f"or raise the cap deliberately."
        )

    signals: list[DarvaxSignal] = []
    skipped: list[SkippedInstrument] = []

    for instrument_id in instrument_ids:
        try:
            candles = market_data.recent_candles(
                instrument_id, timeframe, limit=config.scan.lookback_bars
            )
        except Exception as exc:  # a bad read must not kill the whole scan
            skipped.append(SkippedInstrument(instrument_id, f"read failed: {exc}"))
            continue

        if not candles:
            skipped.append(
                SkippedInstrument(instrument_id, "no candles in the DarvaX lookback")
            )
            continue

        try:
            signal = evaluate_signal(candles, config.methodology)
            store.save_signal(signal)
        except Exception as exc:
            skipped.append(SkippedInstrument(instrument_id, f"evaluate failed: {exc}"))
            continue

        signals.append(signal)

    return ScanResult(
        signals=tuple(signals),
        skipped=tuple(skipped),
        requested=requested,
        evaluated=len(signals),
        timeframe=timeframe,
    )
