"""ID-5B live current-session M5 semantics canary.

This is the Intraday Intelligence wrapper around the shared, read-only
``live_m5_provisional_settlement_diagnostic`` primitives. It deliberately keeps
ID-5B's canary scope, manifest, request budget, and CASE A/B/C/D reporting
separate from EM-5 Track B while reusing the same raw provider capture and
content-only comparison machinery.

No database writes. No timestamp rounding, flooring, nearest-match mapping,
resampling, forward-fill, or synthesis. Captures are persisted as immutable JSON
files only.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as time_of_day
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.env import load_dotenv
from athena.config.loader import load_config
from athena.data.live_m5_provisional_settlement_diagnostic import (
    DiagnosisOutcome,
    PreflightError,
    ProvisionalCapture,
    capture_provisional_m5,
    classify_diagnosis,
    compare_provisional_to_settled,
    disk_space_preflight,
    read_capture,
    write_capture,
)
from athena.data.providers.kite_provider import KiteProvider
from athena.domain.enums import SessionType, Timeframe
from athena.domain.interfaces import MarketDataProvider
from athena.domain.market import Candle
from athena.session import is_candle_completed

IST = ZoneInfo("Asia/Kolkata")

ID5B_CANARY_INSTRUMENTS: dict[str, str] = {
    "NSE:NIFTY 50": "benchmark_index",
    "NSE:NIFTY BANK": "sector_index",
    "NSE:NIFTY IT": "sector_index",
    "NSE:RELIANCE": "equity",
    "NSE:INFY": "equity",
}

ID5B_CHECKPOINT_SCHEDULE: tuple[str, ...] = (
    "09:20",
    "09:30",
    "09:45",
    "10:00",
    "10:30",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
)

DEFAULT_MINIMUM_DISK_FREE_GB = 2.0
LATE_CHECKPOINT_GRACE_SECONDS = 300
DEFAULT_OUTPUT_ROOT = Path("artifacts/live/id5b")
SCANNABLE_SESSION_TYPES = {SessionType.NORMAL, SessionType.SPECIAL}


class ID5BCase(str, Enum):
    CASE_A_TIMESTAMP_ONLY = "CASE_A_TIMESTAMP_ONLY"
    CASE_B_CONTENT_CHANGES = "CASE_B_CONTENT_CHANGES"
    CASE_C_MIXED = "CASE_C_MIXED"
    CASE_D_INSUFFICIENT_EVIDENCE = "CASE_D_INSUFFICIENT_EVIDENCE"


class CheckpointCaptureStatus(str, Enum):
    CAPTURED = "CAPTURED"
    ALREADY_CAPTURED = "ALREADY_CAPTURED"
    NOT_YET_DUE = "NOT_YET_DUE"
    NOT_OBSERVED_LIVE = "NOT_OBSERVED_LIVE"


class ID5BEvidenceBucket(str, Enum):
    FORMING_AT_CAPTURE = "FORMING_AT_CAPTURE"
    CLOSED_AT_CAPTURE = "CLOSED_AT_CAPTURE"
    OFF_GRID_PROVISIONAL = "OFF_GRID_PROVISIONAL"


@dataclass(frozen=True, slots=True)
class ID5BRequestBudget:
    instrument_count: int = len(ID5B_CANARY_INSTRUMENTS)
    checkpoint_count: int = len(ID5B_CHECKPOINT_SCHEDULE)

    @property
    def provisional_capture_requests(self) -> int:
        return self.instrument_count * self.checkpoint_count

    @property
    def settlement_comparison_requests(self) -> int:
        return self.instrument_count

    @property
    def total_requests(self) -> int:
        return self.provisional_capture_requests + self.settlement_comparison_requests


@dataclass(frozen=True, slots=True)
class ID5BPreflightResult:
    session_type: SessionType
    resolved_symbol_count: int
    disk_free_gb: float
    provider: MarketDataProvider


@dataclass(frozen=True, slots=True)
class ID5BComparisonEvidence:
    instrument_id: str
    checkpoint: str
    provisional_ts: datetime
    provisional_interval_close_ts: datetime
    provisional_request_ts: datetime
    bucket: ID5BEvidenceBucket
    provisional_was_on_grid: bool
    provisional_ohlcv: tuple
    settled_ts: datetime | None
    settled_ohlcv: tuple | None
    ohlcv_exact_match: bool
    candidate_match_count: int
    mapping_unique: bool
    timestamp_offset_seconds: float | None

    @property
    def eligible_for_settlement_semantics(self) -> bool:
        return self.bucket in (ID5BEvidenceBucket.CLOSED_AT_CAPTURE, ID5BEvidenceBucket.OFF_GRID_PROVISIONAL)

    def to_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id,
            "checkpoint": self.checkpoint,
            "provisional_ts": self.provisional_ts.isoformat(),
            "provisional_interval_close_ts": self.provisional_interval_close_ts.isoformat(),
            "provisional_request_ts": self.provisional_request_ts.isoformat(),
            "bucket": self.bucket.value,
            "eligible_for_settlement_semantics": self.eligible_for_settlement_semantics,
            "provisional_was_on_grid": self.provisional_was_on_grid,
            "provisional_ohlcv": [str(v) for v in self.provisional_ohlcv],
            "settled_ts": self.settled_ts.isoformat() if self.settled_ts else None,
            "settled_ohlcv": [str(v) for v in self.settled_ohlcv] if self.settled_ohlcv else None,
            "ohlcv_exact_match": self.ohlcv_exact_match,
            "candidate_match_count": self.candidate_match_count,
            "mapping_unique": self.mapping_unique,
            "timestamp_offset_seconds": self.timestamp_offset_seconds,
        }


def _evidence_bucket(candle: Candle, *, request_ts: datetime) -> ID5BEvidenceBucket:
    if not is_candle_completed(candle, as_of=request_ts):
        return ID5BEvidenceBucket.FORMING_AT_CAPTURE
    if candle.ts_open.second != 0 or candle.ts_open.microsecond != 0 or candle.ts_open.minute % 5 != 0:
        return ID5BEvidenceBucket.OFF_GRID_PROVISIONAL
    return ID5BEvidenceBucket.CLOSED_AT_CAPTURE


def build_id5b_comparison_evidence(
    *, provisional: ProvisionalCapture, settled: ProvisionalCapture
) -> tuple[ID5BComparisonEvidence, ...]:
    rows = compare_provisional_to_settled(provisional=provisional, settled=settled)
    evidence = []
    for candle, comparison in zip(provisional.candles, rows, strict=True):
        evidence.append(ID5BComparisonEvidence(
            instrument_id=comparison.instrument_id,
            checkpoint=provisional.checkpoint,
            provisional_ts=comparison.provisional_ts,
            provisional_interval_close_ts=candle.ts_open + timedelta(minutes=5),
            provisional_request_ts=provisional.request_ts,
            bucket=_evidence_bucket(candle, request_ts=provisional.request_ts),
            provisional_was_on_grid=comparison.provisional_was_on_grid,
            provisional_ohlcv=comparison.provisional_ohlcv,
            settled_ts=comparison.settled_ts,
            settled_ohlcv=comparison.settled_ohlcv,
            ohlcv_exact_match=comparison.ohlcv_exact_match,
            candidate_match_count=comparison.candidate_match_count,
            mapping_unique=comparison.mapping_unique,
            timestamp_offset_seconds=comparison.timestamp_offset_seconds,
        ))
    return tuple(evidence)


def calendar_preflight(*, config_dir: Path, session_date: date) -> SessionType:
    cfg = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, cfg.market)
    session_type = calendar.context_for(session_date).session_type
    if session_type not in SCANNABLE_SESSION_TYPES:
        raise PreflightError(
            f"calendar preflight failed: {session_date.isoformat()} is {session_type.value}, "
            f"not a live scannable NSE session"
        )
    return session_type


def run_preflight(
    *,
    config_dir: Path,
    session_date: date,
    instrument_ids: tuple[str, ...] = tuple(ID5B_CANARY_INSTRUMENTS),
    min_disk_free_gb: float = DEFAULT_MINIMUM_DISK_FREE_GB,
) -> ID5BPreflightResult:
    session_type = calendar_preflight(config_dir=config_dir, session_date=session_date)
    load_dotenv()
    bare_symbols = sorted({iid.split(":", 1)[1] for iid in instrument_ids})
    provider = KiteProvider.from_config_dir(config_dir, symbols=bare_symbols)
    resolved = provider.instruments()
    resolved_symbols = {i.symbol.upper() for i in resolved}
    unresolved = tuple(s for s in bare_symbols if s.upper() not in resolved_symbols)
    if unresolved:
        raise PreflightError(f"Kite catalog preflight failed: symbol(s) not resolvable: {unresolved}")
    free_gb = disk_space_preflight(minimum_free_gb=min_disk_free_gb)
    return ID5BPreflightResult(
        session_type=session_type,
        resolved_symbol_count=len(resolved_symbols),
        disk_free_gb=free_gb,
        provider=provider,
    )


def _capture_file_path(output_dir: Path, run_id: str, checkpoint: str, instrument_id: str) -> Path:
    safe_checkpoint = checkpoint.replace(":", "")
    safe_instrument = instrument_id.replace(":", "_").replace(" ", "-")
    return output_dir / f"{run_id}__{safe_checkpoint}__{safe_instrument}.json"


def _manifest_path(output_dir: Path, run_id: str) -> Path:
    return output_dir / f"{run_id}__manifest.json"


def run_capture_phase(
    *,
    provider: MarketDataProvider,
    session_date: date,
    output_dir: Path,
    run_id: str,
    now: datetime,
    session_open_time: time_of_day = time_of_day(9, 15),
    instrument_roles: dict[str, str] = ID5B_CANARY_INSTRUMENTS,
    checkpoints: tuple[str, ...] = ID5B_CHECKPOINT_SCHEDULE,
    disk_free_gb_at_start: float = 0.0,
    session_type: str = "",
) -> dict:
    if now.tzinfo is None:
        raise ValueError("run_capture_phase: `now` must be timezone-aware")

    output_dir.mkdir(parents=True, exist_ok=True)
    instrument_ids = tuple(instrument_roles)
    capture_paths: list[str] = []
    status_by_checkpoint: dict[str, str] = {}

    for checkpoint in checkpoints:
        checkpoint_instant = datetime.combine(session_date, time_of_day.fromisoformat(checkpoint), tzinfo=IST)
        existing = [_capture_file_path(output_dir, run_id, checkpoint, iid) for iid in instrument_ids]
        if all(path.is_file() for path in existing):
            status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.ALREADY_CAPTURED.value
            capture_paths.extend(str(path) for path in existing)
            continue
        if checkpoint_instant > now:
            status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.NOT_YET_DUE.value
            continue
        if (now - checkpoint_instant).total_seconds() > LATE_CHECKPOINT_GRACE_SECONDS:
            status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.NOT_OBSERVED_LIVE.value
            continue

        captures = capture_provisional_m5(
            provider=provider,
            instrument_ids=instrument_ids,
            session_date=session_date,
            session_open_time=session_open_time,
            tzinfo=IST,
            checkpoint_instant=checkpoint_instant,
            checkpoint=checkpoint,
            run_id=run_id,
            now=lambda: now,
        )
        for capture in captures:
            path = _capture_file_path(output_dir, run_id, checkpoint, capture.instrument_id)
            write_capture(capture, path)
            capture_paths.append(str(path))
        status_by_checkpoint[checkpoint] = CheckpointCaptureStatus.CAPTURED.value

    manifest = {
        "track": "ID-5B",
        "run_id": run_id,
        "session_date": session_date.isoformat(),
        "session_type": session_type,
        "started_at": now.isoformat(),
        "finished_at": now.isoformat(),
        "instrument_roles": dict(instrument_roles),
        "checkpoints": list(checkpoints),
        "checkpoint_status": status_by_checkpoint,
        "capture_file_paths": capture_paths,
        "disk_free_gb_at_start": disk_free_gb_at_start,
        "request_budget": ID5BRequestBudget().provisional_capture_requests,
        "settlement_request_budget": ID5BRequestBudget().settlement_comparison_requests,
        "rules": {
            "timestamp_rounding": "forbidden",
            "nearest_match_mapping": "forbidden",
            "resampling": "forbidden",
            "database_writes": "forbidden",
            "comparison_rule": "exact_ohlcv_content_match_only",
        },
    }
    _manifest_path(output_dir, run_id).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def run_watch_phase(
    *,
    provider: MarketDataProvider,
    session_date: date,
    output_dir: Path,
    run_id: str,
    session_type: str,
    disk_free_gb_at_start: float,
    checkpoints: tuple[str, ...] = ID5B_CHECKPOINT_SCHEDULE,
) -> dict:
    manifest = {}
    for checkpoint in checkpoints:
        checkpoint_instant = datetime.combine(session_date, time_of_day.fromisoformat(checkpoint), tzinfo=IST)
        now = datetime.now(IST)
        if checkpoint_instant > now:
            time.sleep((checkpoint_instant - now).total_seconds() + 1.0)
        manifest = run_capture_phase(
            provider=provider,
            session_date=session_date,
            output_dir=output_dir,
            run_id=run_id,
            now=datetime.now(IST),
            checkpoints=checkpoints,
            disk_free_gb_at_start=disk_free_gb_at_start,
            session_type=session_type,
        )
        print(json.dumps({
            "checkpoint": checkpoint,
            "observed_at": datetime.now(IST).isoformat(),
            "checkpoint_status": manifest["checkpoint_status"],
            "capture_file_count": len(manifest["capture_file_paths"]),
        }, indent=2, sort_keys=True), flush=True)
    return manifest


def _map_diagnosis_to_case(outcome: DiagnosisOutcome | None) -> ID5BCase:
    if outcome is DiagnosisOutcome.TIMESTAMP_ONLY_PROVISIONAL_DRIFT:
        return ID5BCase.CASE_A_TIMESTAMP_ONLY
    if outcome is DiagnosisOutcome.PROVISIONAL_OHLCV_ALSO_CHANGES:
        return ID5BCase.CASE_B_CONTENT_CHANGES
    if outcome is DiagnosisOutcome.MAPPING_AMBIGUOUS:
        return ID5BCase.CASE_C_MIXED
    return ID5BCase.CASE_D_INSUFFICIENT_EVIDENCE


def classify_id5b_case(evidence_rows: tuple[ID5BComparisonEvidence, ...]) -> ID5BCase:
    """ID-5B CASE A/B/C/D classification from exact-content comparisons.

    The shared EMR primitive classifies only off-grid provisional drift. ID-5B
    also cares whether a completed current-session row's OHLCV later changes.
    A forming candle changing later is normal market behavior, so it is
    reported for operational understanding but never counted as CASE B.
    """

    if not evidence_rows:
        return ID5BCase.CASE_D_INSUFFICIENT_EVIDENCE

    eligible = [row for row in evidence_rows if row.eligible_for_settlement_semantics]
    off_grid = [row for row in eligible if row.bucket is ID5BEvidenceBucket.OFF_GRID_PROVISIONAL]
    content_changed = [row for row in eligible if row.candidate_match_count == 0]
    ambiguous = [row for row in eligible if row.candidate_match_count > 1]
    timestamp_only = [row for row in off_grid if row.mapping_unique and row.ohlcv_exact_match]

    if ambiguous and (content_changed or timestamp_only):
        return ID5BCase.CASE_C_MIXED
    if ambiguous:
        return ID5BCase.CASE_C_MIXED
    if content_changed and timestamp_only:
        return ID5BCase.CASE_C_MIXED
    if content_changed:
        return ID5BCase.CASE_B_CONTENT_CHANGES
    if off_grid and len(timestamp_only) == len(off_grid):
        return ID5BCase.CASE_A_TIMESTAMP_ONLY
    return ID5BCase.CASE_D_INSUFFICIENT_EVIDENCE


def run_settlement_comparison_phase(
    *,
    provider: MarketDataProvider,
    manifest_path: Path,
    force: bool = False,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    session_date = date.fromisoformat(manifest["session_date"])
    if not force:
        raise PreflightError(
            "ID-5B settlement comparison is intentionally manual-gated; pass --force only after the owner "
            "confirms the provider session should be treated as settled"
        )

    session_start = datetime.combine(session_date, time_of_day(0, 0), tzinfo=IST)
    session_end = datetime.combine(session_date, time_of_day(23, 59, 59), tzinfo=IST)
    captures_by_instrument: dict[str, list[ProvisionalCapture]] = {}
    for path_str in manifest["capture_file_paths"]:
        capture = read_capture(Path(path_str))
        captures_by_instrument.setdefault(capture.instrument_id, []).append(capture)

    evidence = {}
    all_comparisons = []
    for instrument_id, captures in captures_by_instrument.items():
        settled_candles = provider.intraday_candles(instrument_id, Timeframe.M5, session_start, session_end)
        settled = ProvisionalCapture(
            run_id=manifest["run_id"],
            instrument_id=instrument_id,
            checkpoint="SETTLED_FULL_SESSION",
            session_date=session_date,
            requested_start=session_start,
            requested_end=session_end,
            request_ts=datetime.now(IST),
            provider_name=getattr(provider, "name", provider.__class__.__name__),
            success=True,
            error=None,
            retry_count=None,
            candles=tuple(sorted(settled_candles, key=lambda c: c.ts_open)),
        )
        comparisons = []
        for provisional in captures:
            if provisional.success:
                comparisons.extend(build_id5b_comparison_evidence(provisional=provisional, settled=settled))
        all_comparisons.extend(comparisons)
        evidence[instrument_id] = [comparison.to_dict() for comparison in comparisons]

    diagnosis = classify_diagnosis(tuple(all_comparisons)) if any(
        not comparison.provisional_was_on_grid for comparison in all_comparisons
    ) else None
    case = classify_id5b_case(tuple(all_comparisons))
    report = {
        "track": "ID-5B",
        "run_id": manifest["run_id"],
        "session_date": manifest["session_date"],
        "case": case.value,
        "diagnosis": diagnosis.value if diagnosis else None,
        "field_by_field_evidence": evidence,
    }
    report_path = manifest_path.with_name(f"{manifest['run_id']}__settlement_comparison.json")
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _default_run_id(session_date: date) -> str:
    return f"id5b-live-m5-{session_date:%Y%m%d}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ID-5B live M5 semantics canary.")
    parser.add_argument("phase", choices=("preflight", "capture", "watch", "settlement"))
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--session-date", type=date.fromisoformat, default=datetime.now(IST).date())
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    run_id = args.run_id or _default_run_id(args.session_date)
    output_dir = args.output_root / args.session_date.isoformat()

    if args.phase == "preflight":
        result = run_preflight(config_dir=args.config_dir, session_date=args.session_date)
        print(json.dumps({
            "session_type": result.session_type.value,
            "resolved_symbol_count": result.resolved_symbol_count,
            "disk_free_gb": result.disk_free_gb,
            "request_budget": ID5BRequestBudget().total_requests,
            "instruments": ID5B_CANARY_INSTRUMENTS,
        }, indent=2, sort_keys=True))
        return 0

    result = run_preflight(config_dir=args.config_dir, session_date=args.session_date)
    if args.phase == "capture":
        manifest = run_capture_phase(
            provider=result.provider,
            session_date=args.session_date,
            output_dir=output_dir,
            run_id=run_id,
            now=datetime.now(IST),
            disk_free_gb_at_start=result.disk_free_gb,
            session_type=result.session_type.value,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.phase == "watch":
        manifest = run_watch_phase(
            provider=result.provider,
            session_date=args.session_date,
            output_dir=output_dir,
            run_id=run_id,
            session_type=result.session_type.value,
            disk_free_gb_at_start=result.disk_free_gb,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    manifest_path = args.manifest or _manifest_path(output_dir, run_id)
    report = run_settlement_comparison_phase(provider=result.provider, manifest_path=manifest_path, force=args.force)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
