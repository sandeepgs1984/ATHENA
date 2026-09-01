"""EM-5 Track B live capture operator flow (Owner/Chief Architect
authorization, 2026-08-28 weekend hardening + final pre-live operator audit).
Ties together
`live_m5_provisional_settlement_diagnostic.py`'s already-tested pieces
into one executable-with-minimal-decisions script.

Two phases, run as two separate invocations, potentially weeks apart:

  1. `run_capture_phase(...)` -- during the live session, at each of the 9
     frozen checkpoints (`TRACK_B_CHECKPOINT_SCHEDULE`). Makes real Kite
     calls; writes nothing to `db/athena.db`; persists every raw response
     window unchanged as immutable JSON, with full provenance
     (`ProvisionalCapture`). Idempotent: rerunning after a restart never
     re-captures (and never overwrites) a checkpoint already on disk, and
     never fabricates a checkpoint whose live window has already passed --
     see `_capture_status` for the exact three-way classification
     (CAPTURED / ALREADY_CAPTURED / NOT_OBSERVED_LIVE / NOT_YET_DUE).
  2. `run_settlement_comparison_phase(...)` -- only once the day should
     reasonably be treated as settled (see `is_likely_settled` -- refuses
     to run otherwise unless explicitly overridden), re-fetches the same
     sessions through the normal historical route and produces the
     populated classification report via content-only OHLCV matching.

Preflight (`run_preflight`: calendar, Kite auth + real symbol-catalog
resolution, disk space) must pass before phase 1 commits to anything --
any failure raises `PreflightError`, and the caller must not start a
partial capture. No labels/outcomes. No FINAL_TEST access. No timestamp
rounding/flooring/nearest-match anywhere in this file or its dependencies.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.data.live_m5_provisional_settlement_diagnostic import (
    TRACK_B_CHECKPOINT_SCHEDULE,
    DiagnosisOutcome,
    PreflightError,
    ProvisionalCapture,
    TrackBRunManifest,
    build_classification_report_skeleton,
    capture_provisional_m5,
    compare_provisional_to_settled,
    disk_space_preflight,
    populate_classification_report,
    read_capture,
    write_capture,
)
from athena.domain.enums import SessionType, Timeframe
from athena.domain.interfaces import MarketDataProvider
from athena.explosive_move.live.checkpoint_reference_price import (
    MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS,
)

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
DEFAULT_SESSION_OPEN_TIME = time_of_day(9, 15)
DEFAULT_TZ = ZoneInfo("Asia/Kolkata")
DEFAULT_ARTIFACT_ROOT = Path("artifacts/live/em5_track_b")

#: A checkpoint captured no later than this many seconds after its own
#: instant counts as a genuine live observation. Reused, not reinvented:
#: the same frozen `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS` (300s) EM-5's
#: real checkpoint-price collector already uses for the identical
#: question ("how late can an observation be and still count as this
#: checkpoint's own"). A late process start, a system sleep/wake, or a
#: restart that only gets to a checkpoint after this window has elapsed
#: must record NOT_OBSERVED_LIVE for it, never a fabricated "live" capture.
LATE_CHECKPOINT_GRACE_SECONDS = MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS

#: A settled-comparison fetch is refused by default before this many days
#: have passed since the session -- the settlement-repair investigation's
#: own real evidence (`IMPLEMENTATION_SUMMARY.md`, 2026-08-28) found data
#: as recent as ~1-4 weeks old still off-grid/incomplete, and a genuinely
#: old (14+ month) date fully clean. This is a caution threshold, not a
#: proof of settlement -- `force=True` exists for a deliberate override,
#: never a default.
MINIMUM_DAYS_BEFORE_LIKELY_SETTLED = 21


class CheckpointCaptureStatus(str, Enum):
    CAPTURED = "CAPTURED"
    ALREADY_CAPTURED = "ALREADY_CAPTURED"
    NOT_YET_DUE = "NOT_YET_DUE"
    NOT_OBSERVED_LIVE = "NOT_OBSERVED_LIVE"


@dataclass(frozen=True, slots=True)
class RequestBudget:
    """Precise accounting for "81 provisional-capture requests": 9 symbols
    x 9 checkpoints = 81 real `intraday_candles` calls, one per
    (symbol, checkpoint) pair, made sequentially through a single shared,
    already-catalog-resolved provider instance -- never nested, never
    multiplied. A transient failure on one call may be retried by the
    wrapping `RetryingMarketDataProvider` (bounded, real backoff), which
    adds to that ONE call's own retry count but never issues additional
    base requests beyond the 81. The later settlement-comparison phase
    adds exactly one more request per symbol (9), for 90 total across the
    whole two-phase campaign."""

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


def calendar_preflight(*, config_dir: Path, session_date: date) -> SessionType:
    """Confirms `session_date` through ATHENA's own canonical
    `CalendarEngine` -- never a hardcoded assumption. Raises
    `PreflightError` unless the session is genuinely scannable (NORMAL or
    SPECIAL, the same set `eligibility.SCANNABLE_SESSION_TYPES` already
    freezes) -- a MUHURAT, WEEKEND, HOLIDAY, or unsupported-special session
    must stop the run rather than silently capturing anyway."""

    from athena.calendar.engine import CalendarEngine
    from athena.config.loader import load_config
    from athena.explosive_move.live.eligibility import SCANNABLE_SESSION_TYPES

    cfg = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    session_type = calendar.context_for(session_date).session_type
    if session_type not in SCANNABLE_SESSION_TYPES:
        raise PreflightError(
            f"calendar preflight failed: {session_date.isoformat()} is {session_type.value}, "
            f"not a scannable session ({sorted(t.value for t in SCANNABLE_SESSION_TYPES)})"
        )
    return session_type


@dataclass(frozen=True, slots=True)
class PreflightResult:
    session_type: SessionType
    resolved_symbol_count: int
    unresolved_symbols: tuple[str, ...]
    disk_free_gb: float
    provider: MarketDataProvider


def run_preflight(
    *,
    config_dir: Path,
    session_date: date,
    instrument_ids: tuple[str, ...] = tuple(DEFAULT_SYMBOL_LIQUIDITY_BUCKETS),
    min_disk_free_gb: float = DEFAULT_MINIMUM_DISK_FREE_GB,
) -> PreflightResult:
    """All required preflight checks, in order: calendar, Kite auth +
    real catalog resolution of the ACTUAL Monday symbol list (not a
    generic canary symbol), disk space. Raises `PreflightError` on the
    first failure -- the caller must not start any capture if this
    raises. Building the provider here (once, with the real symbol scope)
    and returning it for reuse in `run_capture_phase` is exactly the
    "pre-resolve/cache the nine instrument tokens during preflight"
    requirement: `KiteProvider._ensure_catalog()` caches on this single
    successful resolution, so every one of the 81 later capture calls
    reuses it -- no repeated catalog downloads. If catalog resolution
    itself fails (e.g. one bad symbol), that failure is isolated and
    reported here, before any real capture is attempted, rather than
    silently re-triggering a fresh catalog fetch on every subsequent call
    (the `NSE:E2E` incident this guards against)."""

    from athena.config.env import load_dotenv
    from athena.data.providers.kite_provider import KiteProvider
    from athena.errors import ProviderError

    session_type = calendar_preflight(config_dir=config_dir, session_date=session_date)

    load_dotenv()
    bare_symbols = sorted({iid.split(":", 1)[1] for iid in instrument_ids})
    try:
        provider = KiteProvider.from_config_dir(config_dir, symbols=bare_symbols)
        resolved = provider.instruments()
    except ProviderError as exc:
        raise PreflightError(f"Kite auth/catalog preflight failed: {exc}") from exc
    resolved_symbols = {i.symbol.upper() for i in resolved}
    unresolved = tuple(s for s in bare_symbols if s.upper() not in resolved_symbols)
    if unresolved:
        raise PreflightError(
            f"Kite catalog preflight failed: symbol(s) not resolvable: {unresolved} -- "
            f"isolated here, before any capture; not a reason to retry the whole catalog"
        )

    free_gb = disk_space_preflight(minimum_free_gb=min_disk_free_gb)
    return PreflightResult(
        session_type=session_type, resolved_symbol_count=len(resolved_symbols), unresolved_symbols=(),
        disk_free_gb=free_gb, provider=provider,
    )


def _capture_file_path(output_dir: Path, run_id: str, checkpoint: str, instrument_id: str) -> Path:
    safe_checkpoint = checkpoint.replace(":", "")
    safe_instrument = instrument_id.replace(":", "_").replace(" ", "-")
    return output_dir / f"{run_id}__{safe_checkpoint}__{safe_instrument}.json"


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
    """Idempotent and restart-safe. For each checkpoint, per instrument:

    - if a capture file already exists on disk for (run_id, checkpoint,
      instrument), it is never re-fetched or overwritten (ALREADY_CAPTURED);
    - if the checkpoint is still in the future relative to `now`, it is
      skipped entirely this call (NOT_YET_DUE) -- rerun later the same day;
    - if the checkpoint has already elapsed by more than
      `LATE_CHECKPOINT_GRACE_SECONDS`, it is never captured at all --
      recorded as NOT_OBSERVED_LIVE, exactly like a genuinely missed
      checkpoint, never reconstructed after the fact (a late process
      start, or a system sleep/wake spanning the checkpoint, must not
      let a now-stale request masquerade as a live one);
    - otherwise it is captured for real (CAPTURED).

    `now` must be timezone-aware in `tzinfo` (or comparably aware) --
    comparing it against the timezone-aware `checkpoint_instant` values
    this function builds fails loudly (a naive/aware comparison raises
    `TypeError`) rather than silently misordering checkpoints."""

    if now.tzinfo is None:
        raise ValueError("run_capture_phase: `now` must be timezone-aware")

    output_dir.mkdir(parents=True, exist_ok=True)
    instrument_ids = tuple(symbol_liquidity_buckets)
    capture_paths: list[str] = []
    status_by_checkpoint: dict[str, str] = {}

    for checkpoint in checkpoints:
        checkpoint_instant = datetime.combine(
            session_date, time_of_day.fromisoformat(checkpoint), tzinfo=tzinfo,
        )
        existing = [
            _capture_file_path(output_dir, run_id, checkpoint, iid) for iid in instrument_ids
        ]
        if all(p.is_file() for p in existing):
            status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.ALREADY_CAPTURED.value
            capture_paths.extend(str(p) for p in existing)
            continue
        existing_by_instrument = {
            iid: path for iid, path in zip(instrument_ids, existing, strict=True) if path.is_file()
        }
        if checkpoint_instant > now:
            status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.NOT_YET_DUE.value
            capture_paths.extend(str(path) for path in existing_by_instrument.values())
            continue
        seconds_late = (now - checkpoint_instant).total_seconds()
        if seconds_late > LATE_CHECKPOINT_GRACE_SECONDS:
            status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.NOT_OBSERVED_LIVE.value
            capture_paths.extend(str(path) for path in existing_by_instrument.values())
            continue

        missing_instruments = tuple(iid for iid in instrument_ids if iid not in existing_by_instrument)
        captures = capture_provisional_m5(
            provider=provider, instrument_ids=missing_instruments, session_date=session_date,
            session_open_time=session_open_time, tzinfo=tzinfo, checkpoint_instant=checkpoint_instant,
            checkpoint=checkpoint, run_id=run_id, now=lambda: now,
        )
        capture_paths.extend(str(path) for path in existing_by_instrument.values())
        for capture in captures:
            path = _capture_file_path(output_dir, run_id, checkpoint, capture.instrument_id)
            write_capture(capture, path)
            capture_paths.append(str(path))
        status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.CAPTURED.value

    manifest = TrackBRunManifest(
        run_id=run_id, session_date=session_date, checkpoints=checkpoints, instrument_ids=instrument_ids,
        liquidity_bucket_by_instrument=dict(symbol_liquidity_buckets),
        kite_auth_verified_symbol=kite_auth_verified_symbol, disk_free_gb_at_start=disk_free_gb_at_start,
        capture_file_paths=tuple(capture_paths), started_at=now, finished_at=now,
    )
    manifest_payload = manifest.to_dict()
    manifest_payload["checkpoint_status"] = status_by_checkpoint
    (output_dir / f"{run_id}__manifest.json").write_text(
        json.dumps(manifest_payload, indent=2), encoding="utf-8",
    )
    return manifest


def is_likely_settled(
    *, session_date: date, today: date, minimum_days: int = MINIMUM_DAYS_BEFORE_LIKELY_SETTLED,
) -> bool:
    """A caution check, not a proof: the settlement-repair investigation's
    real evidence never established an exact settle boundary, only that
    data 1-4 weeks old was still affected while 14+-month-old data was
    fully clean. Refusing the comparison phase before `minimum_days` have
    passed avoids repeating that same mistake with Track B's own evidence
    -- the market closing on session_date is NOT sufficient grounds on
    its own."""

    return (today - session_date).days >= minimum_days


def _is_on_grid(ts: datetime) -> bool:
    return ts.second == 0 and ts.microsecond == 0 and ts.minute % 5 == 0


def build_live_canary_completeness_report(manifest: TrackBRunManifest) -> dict:
    """Read the immutable raw captures and determine whether the live
    canary is complete enough for the zero-off-grid observational outcome.

    This is intentionally based on the manifest/capture files only. It
    performs no provider requests and writes no artifacts.
    """

    required_instruments = set(manifest.instrument_ids)
    required_checkpoints = set(manifest.checkpoints)
    captures_by_pair: dict[tuple[str, str], ProvisionalCapture] = {}
    failures: list[dict[str, str | None]] = []
    duplicate_pairs: list[dict[str, str]] = []
    missing_files: list[str] = []
    provisional_rows = 0
    off_grid_rows = 0

    for path_str in manifest.capture_file_paths:
        path = Path(path_str)
        if not path.is_file():
            missing_files.append(path_str)
            continue
        capture = read_capture(path)
        pair = (capture.instrument_id, capture.checkpoint)
        if pair in captures_by_pair:
            duplicate_pairs.append({"instrument_id": capture.instrument_id, "checkpoint": capture.checkpoint})
        captures_by_pair[pair] = capture
        if not capture.success:
            failures.append({
                "instrument_id": capture.instrument_id,
                "checkpoint": capture.checkpoint,
                "error": capture.error,
            })
        provisional_rows += len(capture.candles)
        off_grid_rows += sum(1 for candle in capture.candles if not _is_on_grid(candle.ts_open))

    observed_instruments = {instrument for instrument, _checkpoint in captures_by_pair}
    observed_checkpoints = {checkpoint for _instrument, checkpoint in captures_by_pair}
    missing_pairs = [
        {"instrument_id": instrument, "checkpoint": checkpoint}
        for instrument in manifest.instrument_ids
        for checkpoint in manifest.checkpoints
        if (instrument, checkpoint) not in captures_by_pair
    ]
    extra_pairs = [
        {"instrument_id": instrument, "checkpoint": checkpoint}
        for instrument, checkpoint in captures_by_pair
        if instrument not in required_instruments or checkpoint not in required_checkpoints
    ]

    reasons = []
    if missing_files:
        reasons.append("missing capture file(s)")
    if missing_pairs:
        reasons.append("missing required instrument/checkpoint capture(s)")
    if extra_pairs:
        reasons.append("unexpected instrument/checkpoint capture(s)")
    if failures:
        reasons.append("provider/raw capture failure(s)")
    if duplicate_pairs:
        reasons.append("duplicate instrument/checkpoint capture(s)")

    complete = not reasons
    return {
        "complete": complete,
        "reasons": reasons,
        "required_symbol_count": len(required_instruments),
        "required_checkpoint_count": len(required_checkpoints),
        "expected_capture_count": len(required_instruments) * len(required_checkpoints),
        "capture_file_count": len(manifest.capture_file_paths),
        "observed_symbol_count": len(observed_instruments),
        "observed_checkpoint_count": len(observed_checkpoints),
        "successful_capture_count": len(captures_by_pair) - len(failures),
        "failed_capture_count": len(failures),
        "provisional_row_count": provisional_rows,
        "off_grid_provisional_row_count": off_grid_rows,
        "missing_files": missing_files,
        "missing_pairs": missing_pairs,
        "extra_pairs": extra_pairs,
        "failed_captures": failures,
        "duplicate_pairs": duplicate_pairs,
    }


def classify_live_capture_zero_off_grid(manifest: TrackBRunManifest) -> DiagnosisOutcome | None:
    """Classify the fully observed zero-off-grid branch from immutable live
    evidence only. Returns None when completeness is not proven or when
    off-grid rows exist and the existing settled-comparison classifier must
    handle the three original outcomes."""

    completeness = build_live_canary_completeness_report(manifest)
    if completeness["complete"] and completeness["off_grid_provisional_row_count"] == 0:
        return DiagnosisOutcome.NO_OFF_GRID_PROVISIONAL_OBSERVED
    return None


def run_settlement_comparison_phase(
    *, provider: MarketDataProvider, manifest: TrackBRunManifest, tzinfo: tzinfo_type, today: date, force: bool = False,
) -> dict:
    """Re-fetches each instrument's whole session through the normal
    historical route and produces the populated classification report --
    content-based comparison only, per `compare_provisional_to_settled`.
    Refuses to run (raises `PreflightError`) unless `is_likely_settled`
    or `force=True` -- `force` exists for a deliberate, informed Owner
    override, never as this function's own default judgment."""

    if not force and not is_likely_settled(session_date=manifest.session_date, today=today):
        raise PreflightError(
            f"settlement comparison refused: only {(today - manifest.session_date).days} day(s) since "
            f"{manifest.session_date.isoformat()}, fewer than {MINIMUM_DAYS_BEFORE_LIKELY_SETTLED} -- "
            "this session may not be settled yet; pass force=True only as a deliberate, informed override"
        )

    session_start = datetime.combine(manifest.session_date, time_of_day(0, 0), tzinfo=tzinfo)
    session_end = datetime.combine(manifest.session_date, time_of_day(23, 59, 59), tzinfo=tzinfo)

    live_canary_completeness = build_live_canary_completeness_report(manifest)
    provisional_by_instrument: dict[str, list[ProvisionalCapture]] = {}
    for path_str in manifest.capture_file_paths:
        capture = read_capture(Path(path_str))
        provisional_by_instrument.setdefault(capture.instrument_id, []).append(capture)

    comparisons_by_instrument = {}
    for instrument_id, captures in provisional_by_instrument.items():
        settled_candles = provider.intraday_candles(instrument_id, Timeframe.M5, session_start, session_end)
        settled = ProvisionalCapture(
            run_id=manifest.run_id, instrument_id=instrument_id, checkpoint="SETTLED_FULL_SESSION",
            session_date=manifest.session_date, requested_start=session_start, requested_end=session_end,
            request_ts=session_end, provider_name=getattr(provider, "name", provider.__class__.__name__),
            success=True, error=None, retry_count=None,
            candles=tuple(sorted(settled_candles, key=lambda c: c.ts_open)),
        )
        all_comparisons = []
        for provisional in captures:
            if not provisional.success:
                continue  # a failed provisional capture has no candles to compare
            all_comparisons.extend(compare_provisional_to_settled(provisional=provisional, settled=settled))
        comparisons_by_instrument[instrument_id] = tuple(all_comparisons)

    skeleton = build_classification_report_skeleton(
        run_id=manifest.run_id, session_date=manifest.session_date, checkpoints=manifest.checkpoints,
        liquidity_bucket_by_instrument=manifest.liquidity_bucket_by_instrument,
    )
    report = populate_classification_report(
        skeleton,
        comparisons_by_instrument=comparisons_by_instrument,
        zero_off_grid_outcome_allowed=(
            live_canary_completeness["complete"]
            and live_canary_completeness["off_grid_provisional_row_count"] == 0
        ),
    )
    report["live_canary_completeness"] = live_canary_completeness
    return report


def _checkpoint_instant(*, session_date: date, checkpoint: str, tzinfo: tzinfo_type) -> datetime:
    return datetime.combine(session_date, time_of_day.fromisoformat(checkpoint), tzinfo=tzinfo)


def _next_wake_seconds(
    *,
    now: datetime,
    session_date: date,
    tzinfo: tzinfo_type,
    checkpoints: tuple[str, ...],
) -> float | None:
    for checkpoint in checkpoints:
        instant = _checkpoint_instant(session_date=session_date, checkpoint=checkpoint, tzinfo=tzinfo)
        if now < instant:
            return (instant - now).total_seconds()
    return None


def _has_due_checkpoint(
    *,
    now: datetime,
    session_date: date,
    tzinfo: tzinfo_type,
    checkpoints: tuple[str, ...],
) -> bool:
    return any(
        _checkpoint_instant(session_date=session_date, checkpoint=checkpoint, tzinfo=tzinfo) <= now
        for checkpoint in checkpoints
    )


def run_unattended_capture(
    *,
    config_dir: Path,
    session_date: date,
    output_dir: Path,
    run_id: str,
    session_open_time: time_of_day = DEFAULT_SESSION_OPEN_TIME,
    tzinfo: tzinfo_type = DEFAULT_TZ,
    symbol_liquidity_buckets: dict[str, str] = DEFAULT_SYMBOL_LIQUIDITY_BUCKETS,
    checkpoints: tuple[str, ...] = TRACK_B_CHECKPOINT_SCHEDULE,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_sleep_seconds: float = 60.0,
    log: Callable[[str], None] = print,
) -> TrackBRunManifest:
    """Run the approved Track B capture flow unattended through 14:00.

    This is orchestration only: preflight once, wait efficiently, call the
    existing capture primitive inside each checkpoint's live window, and stop
    after the final capture attempt. It never calls settlement.
    """

    clock = now or (lambda: datetime.now(tz=tzinfo))
    preflight = run_preflight(
        config_dir=config_dir,
        session_date=session_date,
        instrument_ids=tuple(symbol_liquidity_buckets),
    )
    log(
        "EM-5 Track B preflight passed: "
        f"session_type={preflight.session_type.value}, "
        f"resolved_symbols={preflight.resolved_symbol_count}, "
        f"disk_free_gb={preflight.disk_free_gb:.2f}"
    )

    final_checkpoint = checkpoints[-1]
    final_instant = _checkpoint_instant(session_date=session_date, checkpoint=final_checkpoint, tzinfo=tzinfo)
    final_stop = final_instant
    manifest: TrackBRunManifest | None = None

    while True:
        current = clock()
        if current.tzinfo is None:
            raise ValueError("run_unattended_capture: clock must return a timezone-aware datetime")

        if not _has_due_checkpoint(now=current, session_date=session_date, tzinfo=tzinfo, checkpoints=checkpoints):
            wait_seconds = _next_wake_seconds(
                now=current,
                session_date=session_date,
                tzinfo=tzinfo,
                checkpoints=checkpoints,
            )
            if wait_seconds is None:
                raise PreflightError("unattended capture has no future checkpoint to wait for")
            nap = min(wait_seconds, max_sleep_seconds)
            if nap > 0:
                log(f"waiting {nap:.1f}s for next Track B checkpoint")
                sleep(nap)
                continue

        log(f"running Track B capture pass at {current.isoformat()}")
        manifest = run_capture_phase(
            provider=preflight.provider,
            session_date=session_date,
            session_open_time=session_open_time,
            tzinfo=tzinfo,
            output_dir=output_dir,
            run_id=run_id,
            now=current,
            symbol_liquidity_buckets=symbol_liquidity_buckets,
            checkpoints=checkpoints,
            disk_free_gb_at_start=preflight.disk_free_gb,
        )
        log(f"manifest updated: {output_dir / f'{run_id}__manifest.json'}")

        if current >= final_stop:
            log("final Track B checkpoint attempted; stopping without settlement")
            return manifest

        sleep(max_sleep_seconds)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EM-5 Track B capture tooling.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    unattended = subparsers.add_parser(
        "unattended",
        help="Preflight once, capture every frozen checkpoint, then stop without settlement.",
    )
    unattended.add_argument("--session-date", required=True, type=date.fromisoformat)
    unattended.add_argument("--config-dir", default=Path("config"), type=Path)
    unattended.add_argument("--output-dir", type=Path)
    unattended.add_argument("--run-id")
    unattended.add_argument("--max-sleep-seconds", default=60.0, type=float)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "unattended":
        output_dir = args.output_dir or (DEFAULT_ARTIFACT_ROOT / args.session_date.isoformat())
        run_id = args.run_id or f"em5-track-b-{args.session_date:%Y%m%d}"
        run_unattended_capture(
            config_dir=args.config_dir,
            session_date=args.session_date,
            output_dir=output_dir,
            run_id=run_id,
            max_sleep_seconds=args.max_sleep_seconds,
        )
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
