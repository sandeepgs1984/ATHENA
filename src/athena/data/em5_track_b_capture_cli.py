"""EM-5 Track B: the Monday (2026-08-31) live capture operator flow (Owner/
Chief Architect authorization, 2026-08-28 + weekend-prep authorization,
2026-08-28). Ties together `live_m5_provisional_settlement_diagnostic.py`'s
already-tested pieces into one executable-with-minimal-decisions script.

Two phases, run as two separate invocations on the day:

  1. `run_capture_phase(...)` -- during the live session, at each of the 9
     frozen checkpoints (`TRACK_B_CHECKPOINT_SCHEDULE`). Makes real Kite
     calls; writes nothing to `db/athena.db`; persists every raw response
     unchanged as immutable JSON.
  2. `run_settlement_comparison_phase(...)` -- once the day has settled
     (in practice: run this again a few weeks later, matching the
     settlement-repair investigation's own evidence), re-fetches the same
     sessions through the normal historical route and produces the
     populated classification report.

Preflight (`kite_auth_preflight`, `disk_space_preflight`) runs before
phase 1 commits to anything. No labels/outcomes. No FINAL_TEST access. No
timestamp rounding/flooring/nearest-match anywhere in this file or its
dependencies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type
from pathlib import Path

from athena.data.live_m5_provisional_settlement_diagnostic import (
    TRACK_B_CHECKPOINT_SCHEDULE,
    ProvisionalCapture,
    TrackBRunManifest,
    build_classification_report_skeleton,
    capture_provisional_m5,
    compare_provisional_to_settled,
    disk_space_preflight,
    kite_auth_preflight,
    populate_classification_report,
    read_capture,
    write_capture,
)
from athena.domain.interfaces import MarketDataProvider

#: Real, currently-active NSE instruments (verified during the 2026-08-28
#: investigation -- excludes NSE:E2E, which is separately known-unresolvable
#: in Kite's live catalog). Three per liquidity tier, derived from real
#: average traded volume over the trailing 90 days at investigation time --
#: "enough to establish whether the behavior is session-wide, comfortably
#: inside Kite rate limits" per the Owner's exact requirement.
DEFAULT_SYMBOL_LIQUIDITY_BUCKETS: dict[str, str] = {
    "NSE:IDEA": "high", "NSE:OLAELEC": "high", "NSE:YESBANK": "high",
    "NSE:BBTC": "medium", "NSE:IRCTC": "medium", "NSE:RITES": "medium",
    "NSE:JSWDULUX": "low", "NSE:ABBOTINDIA": "low", "NSE:HONAUT": "low",
}

DEFAULT_MINIMUM_DISK_FREE_GB = 2.0


@dataclass(frozen=True, slots=True)
class RequestBudget:
    """9 symbols x 9 checkpoints for the provisional capture; later, one
    settled-comparison fetch per symbol (each covers the whole session in
    one request, per the settlement-repair module's own established
    per-instrument-not-per-day discipline)."""

    symbol_count: int
    checkpoint_count: int

    @property
    def provisional_capture_requests(self) -> int:
        return self.symbol_count * self.checkpoint_count

    @property
    def settlement_comparison_requests(self) -> int:
        return self.symbol_count

    @property
    def total_requests(self) -> int:
        return self.provisional_capture_requests + self.settlement_comparison_requests


def estimate_request_budget(
    *, symbol_count: int = len(DEFAULT_SYMBOL_LIQUIDITY_BUCKETS),
    checkpoint_count: int = len(TRACK_B_CHECKPOINT_SCHEDULE),
) -> RequestBudget:
    return RequestBudget(symbol_count=symbol_count, checkpoint_count=checkpoint_count)


def run_preflight(*, config_dir: Path, min_disk_free_gb: float = DEFAULT_MINIMUM_DISK_FREE_GB) -> tuple[str, float]:
    """Both preflight checks, in the Owner-specified order. Raises
    `PreflightError` (from the diagnostic module) on the first failure --
    the caller must not proceed to any real capture if this raises."""

    verified_symbol = kite_auth_preflight(config_dir)
    free_gb = disk_space_preflight(minimum_free_gb=min_disk_free_gb)
    return verified_symbol, free_gb


def run_capture_phase(
    *,
    provider: MarketDataProvider,
    session_date: date,
    session_open_time: time_of_day,
    tzinfo: tzinfo_type,
    output_dir: Path,
    run_id: str,
    now: datetime,
    symbol_liquidity_buckets: dict[str, str] = DEFAULT_SYMBOL_LIQUIDITY_BUCKETS,
    checkpoints: tuple[str, ...] = TRACK_B_CHECKPOINT_SCHEDULE,
    kite_auth_verified_symbol: str = "",
    disk_free_gb_at_start: float = 0.0,
) -> TrackBRunManifest:
    """Captures every symbol at every checkpoint that has already elapsed
    by `now` (a checkpoint in the future is simply skipped this call --
    rerun later in the day to fill in the rest; never reconstruct a missed
    live checkpoint after the fact by fetching a later window and pretending
    it was captured at the checkpoint instant)."""

    output_dir.mkdir(parents=True, exist_ok=True)
    instrument_ids = tuple(symbol_liquidity_buckets)
    capture_paths: list[str] = []

    for checkpoint in checkpoints:
        checkpoint_instant = datetime.combine(
            session_date, time_of_day.fromisoformat(checkpoint), tzinfo=tzinfo,
        )
        if checkpoint_instant > now:
            continue  # do not fabricate a capture for a checkpoint that hasn't happened yet
        captures = capture_provisional_m5(
            provider=provider, instrument_ids=instrument_ids, session_date=session_date,
            session_open_time=session_open_time, tzinfo=tzinfo, captured_at=checkpoint_instant,
        )
        for capture in captures:
            safe_checkpoint = checkpoint.replace(":", "")
            safe_instrument = capture.instrument_id.replace(":", "_").replace(" ", "-")
            path = output_dir / f"{run_id}__{safe_checkpoint}__{safe_instrument}.json"
            write_capture(capture, path)
            capture_paths.append(str(path))

    manifest = TrackBRunManifest(
        run_id=run_id, session_date=session_date, checkpoints=checkpoints, instrument_ids=instrument_ids,
        liquidity_bucket_by_instrument=dict(symbol_liquidity_buckets),
        kite_auth_verified_symbol=kite_auth_verified_symbol, disk_free_gb_at_start=disk_free_gb_at_start,
        capture_file_paths=tuple(capture_paths), started_at=now, finished_at=now,
    )
    (output_dir / f"{run_id}__manifest.json").write_text(
        json.dumps(manifest.to_dict(), indent=2), encoding="utf-8",
    )
    return manifest


def run_settlement_comparison_phase(
    *, provider: MarketDataProvider, manifest: TrackBRunManifest, tzinfo: tzinfo_type,
) -> dict:
    """Re-fetches each instrument's whole session through the normal
    historical route (now that it should have settled) and produces the
    populated classification report -- content-based comparison only, per
    `compare_provisional_to_settled`."""

    from athena.domain.enums import Timeframe

    session_start = datetime.combine(manifest.session_date, time_of_day(0, 0), tzinfo=tzinfo)
    session_end = datetime.combine(manifest.session_date, time_of_day(23, 59, 59), tzinfo=tzinfo)

    provisional_by_instrument: dict[str, list[ProvisionalCapture]] = {}
    for path_str in manifest.capture_file_paths:
        capture = read_capture(Path(path_str))
        provisional_by_instrument.setdefault(capture.instrument_id, []).append(capture)

    comparisons_by_instrument = {}
    for instrument_id, captures in provisional_by_instrument.items():
        settled_candles = provider.intraday_candles(instrument_id, Timeframe.M5, session_start, session_end)
        settled = ProvisionalCapture(
            instrument_id=instrument_id, session_date=manifest.session_date,
            captured_at=session_end, candles=tuple(sorted(settled_candles, key=lambda c: c.ts_open)),
        )
        all_comparisons = []
        for provisional in captures:
            all_comparisons.extend(compare_provisional_to_settled(provisional=provisional, settled=settled))
        comparisons_by_instrument[instrument_id] = tuple(all_comparisons)

    skeleton = build_classification_report_skeleton(
        run_id=manifest.run_id, session_date=manifest.session_date, checkpoints=manifest.checkpoints,
        liquidity_bucket_by_instrument=manifest.liquidity_bucket_by_instrument,
    )
    return populate_classification_report(skeleton, comparisons_by_instrument=comparisons_by_instrument)
