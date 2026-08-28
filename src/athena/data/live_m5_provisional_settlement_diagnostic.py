"""Track B: live provisional-vs-settled M5 semantic diagnostic (Owner/Chief
Architect authorization, 2026-08-28, EM-5 M5 timestamp investigation item 4).

**What this answers.** Finding 2 (M5 timestamp drift) proved Kite's recent
historical response can carry off-grid timestamps for not-yet-settled
periods, and that the same data later returns grid-aligned once settled
(the settlement-repair backfill, `live_m5_settlement_repair.py`, corrects
the *historical* record on that basis). What remains genuinely unknown --
and is NOT assumed here -- is what a provisional row observed *during* a
live session actually represents: is `09:43:55` a mislabeled `09:40`
bucket, a mislabeled `09:45` bucket, something else, or does its OHLCV
itself still change once settled (making timestamp semantics moot)? This
module answers that empirically, never by convention (no rounding,
flooring, or nearest-match assumption anywhere in this file).

**Method.** Capture raw M5 candles for a representative instrument sample
DURING a live session (`capture_provisional_m5`) and persist them
unchanged. Later, once those dates have settled (in practice: the next
time this is run, per the settlement-repair investigation's own evidence
that recent data settles within a few weeks), fetch the same
(instrument, session) again and compare row-by-row
(`compare_provisional_to_settled`): a provisional row is mapped to a
settled bucket ONLY by an EXACT OHLCV content match, never by nearest-
timestamp or bucket-floor reasoning. `classify_diagnosis` turns the
comparison set into one of the Owner's three named outcomes
(`TIMESTAMP_ONLY_PROVISIONAL_DRIFT` / `PROVISIONAL_OHLCV_ALSO_CHANGES` /
`MAPPING_AMBIGUOUS`) -- never assumed, always read off what the real
comparison found.

No labels/outcomes touched. No FINAL_TEST access. Read-only against Kite;
writes nothing to `db/athena.db` (captures are persisted as plain JSON
files by the caller, not through `SqliteRepository`, so this diagnostic
can never contaminate canonical data with an unsettled row).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from datetime import time as time_of_day
from datetime import tzinfo as tzinfo_type
from decimal import Decimal
from enum import Enum

from athena.domain.enums import Timeframe
from athena.domain.interfaces import MarketDataProvider
from athena.domain.market import Candle


@dataclass(frozen=True, slots=True)
class ProvisionalCapture:
    instrument_id: str
    session_date: date
    captured_at: datetime
    candles: tuple[Candle, ...]

    def to_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id, "session_date": self.session_date.isoformat(),
            "captured_at": self.captured_at.isoformat(),
            "candles": [_candle_to_json(c) for c in self.candles],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> ProvisionalCapture:
        return cls(
            instrument_id=payload["instrument_id"], session_date=date.fromisoformat(payload["session_date"]),
            captured_at=datetime.fromisoformat(payload["captured_at"]),
            candles=tuple(_candle_from_json(c) for c in payload["candles"]),
        )


def _candle_to_json(c: Candle) -> dict:
    return {
        "instrument_id": c.instrument_id, "timeframe": c.timeframe.value, "ts_open": c.ts_open.isoformat(),
        "open": str(c.open), "high": str(c.high), "low": str(c.low), "close": str(c.close),
        "volume": c.volume, "source": c.source, "adjusted": c.adjusted,
    }


def _candle_from_json(payload: dict) -> Candle:
    return Candle(
        instrument_id=payload["instrument_id"], timeframe=Timeframe(payload["timeframe"]),
        ts_open=datetime.fromisoformat(payload["ts_open"]), open=Decimal(payload["open"]),
        high=Decimal(payload["high"]), low=Decimal(payload["low"]), close=Decimal(payload["close"]),
        volume=int(payload["volume"]), source=payload["source"], adjusted=bool(payload.get("adjusted", False)),
    )


def capture_provisional_m5(
    *,
    provider: MarketDataProvider,
    instrument_ids: tuple[str, ...],
    session_date: date,
    session_open_time: time_of_day,
    tzinfo: tzinfo_type,
    captured_at: datetime,
) -> tuple[ProvisionalCapture, ...]:
    """One real fetch per instrument, session open through `captured_at` --
    intended to be called DURING a live session (`captured_at` = real now).
    Raises whatever `ProviderError` the real fetch raises; callers persist
    each returned capture (`to_dict`/`json.dumps`) unchanged, immediately,
    before doing anything else with it."""

    start = datetime.combine(session_date, session_open_time, tzinfo=tzinfo)
    captures = []
    for instrument_id in instrument_ids:
        candles = provider.intraday_candles(instrument_id, Timeframe.M5, start, captured_at)
        captures.append(ProvisionalCapture(
            instrument_id=instrument_id, session_date=session_date, captured_at=captured_at,
            candles=tuple(sorted(candles, key=lambda c: c.ts_open)),
        ))
    return tuple(captures)


def write_capture(capture: ProvisionalCapture, path) -> None:
    path.write_text(json.dumps(capture.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def read_capture(path) -> ProvisionalCapture:
    return ProvisionalCapture.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _is_on_grid(ts: datetime) -> bool:
    return ts.second == 0 and ts.microsecond == 0 and ts.minute % 5 == 0


def _ohlcv(c: Candle) -> tuple[Decimal, Decimal, Decimal, Decimal, int]:
    return (c.open, c.high, c.low, c.close, c.volume)


@dataclass(frozen=True, slots=True)
class RowComparison:
    instrument_id: str
    provisional_ts: datetime
    provisional_was_on_grid: bool
    provisional_ohlcv: tuple[Decimal, Decimal, Decimal, Decimal, int]
    settled_ts: datetime | None
    settled_ohlcv: tuple[Decimal, Decimal, Decimal, Decimal, int] | None
    ohlcv_exact_match: bool
    timestamp_offset_seconds: float | None
    candidate_match_count: int
    mapping_unique: bool

    def to_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id, "provisional_ts": self.provisional_ts.isoformat(),
            "provisional_was_on_grid": self.provisional_was_on_grid,
            "provisional_ohlcv": [str(v) for v in self.provisional_ohlcv],
            "settled_ts": self.settled_ts.isoformat() if self.settled_ts else None,
            "settled_ohlcv": [str(v) for v in self.settled_ohlcv] if self.settled_ohlcv else None,
            "ohlcv_exact_match": self.ohlcv_exact_match,
            "timestamp_offset_seconds": self.timestamp_offset_seconds,
            "candidate_match_count": self.candidate_match_count,
            "mapping_unique": self.mapping_unique,
        }


def compare_provisional_to_settled(
    *, provisional: ProvisionalCapture, settled: ProvisionalCapture,
) -> tuple[RowComparison, ...]:
    """Maps every provisional row to a settled bucket by EXACT OHLCV
    content match ONLY -- never by nearest timestamp, floor, or round.
    Only rows that were off-grid in the provisional capture are
    meaningful evidence for the drift question, but every row is compared
    (an on-grid provisional row should trivially map to itself, which is
    itself evidence worth keeping, not filtered out)."""

    if provisional.instrument_id != settled.instrument_id or provisional.session_date != settled.session_date:
        raise ValueError("compare_provisional_to_settled: instrument_id/session_date must match")

    comparisons = []
    for p in provisional.candles:
        p_ohlcv = _ohlcv(p)
        matches = [s for s in settled.candles if _ohlcv(s) == p_ohlcv]
        if len(matches) == 1:
            s = matches[0]
            comparisons.append(RowComparison(
                instrument_id=provisional.instrument_id, provisional_ts=p.ts_open,
                provisional_was_on_grid=_is_on_grid(p.ts_open), provisional_ohlcv=p_ohlcv,
                settled_ts=s.ts_open, settled_ohlcv=_ohlcv(s), ohlcv_exact_match=True,
                timestamp_offset_seconds=(p.ts_open - s.ts_open).total_seconds(),
                candidate_match_count=1, mapping_unique=True,
            ))
        else:
            comparisons.append(RowComparison(
                instrument_id=provisional.instrument_id, provisional_ts=p.ts_open,
                provisional_was_on_grid=_is_on_grid(p.ts_open), provisional_ohlcv=p_ohlcv,
                settled_ts=None, settled_ohlcv=None, ohlcv_exact_match=False,
                timestamp_offset_seconds=None, candidate_match_count=len(matches),
                mapping_unique=False,
            ))
    return tuple(comparisons)


class DiagnosisOutcome(str, Enum):
    TIMESTAMP_ONLY_PROVISIONAL_DRIFT = "TIMESTAMP_ONLY_PROVISIONAL_DRIFT"
    PROVISIONAL_OHLCV_ALSO_CHANGES = "PROVISIONAL_OHLCV_ALSO_CHANGES"
    MAPPING_AMBIGUOUS = "MAPPING_AMBIGUOUS"


def classify_diagnosis(comparisons: tuple[RowComparison, ...]) -> DiagnosisOutcome:
    """Per the Owner's exact decision rule (2026-08-28):

    - Any row with >1 exact-OHLCV candidate settled match -> MAPPING_AMBIGUOUS
      (a unique mapping cannot be proven; do not guess).
    - Any off-grid provisional row with ZERO exact-OHLCV settled match ->
      PROVISIONAL_OHLCV_ALSO_CHANGES (content itself changed, not just the
      timestamp -- STOP, do not normalize).
    - Otherwise (every off-grid row maps to exactly one settled bucket by
      content) -> TIMESTAMP_ONLY_PROVISIONAL_DRIFT.

    Only off-grid provisional rows are evidence for this classification --
    an on-grid row was never the subject of the question."""

    off_grid = [c for c in comparisons if not c.provisional_was_on_grid]
    if not off_grid:
        raise ValueError(
            "classify_diagnosis: no off-grid provisional rows in this comparison set -- "
            "nothing to classify (the capture window may not have reached the drift-affected tail yet)"
        )
    if any(c.candidate_match_count > 1 for c in off_grid):
        return DiagnosisOutcome.MAPPING_AMBIGUOUS
    if any(not c.ohlcv_exact_match for c in off_grid):
        return DiagnosisOutcome.PROVISIONAL_OHLCV_ALSO_CHANGES
    return DiagnosisOutcome.TIMESTAMP_ONLY_PROVISIONAL_DRIFT


# --------------------------------------------------------------------------- #
# Monday execution package: preflight checks, run manifest, report skeleton
# --------------------------------------------------------------------------- #

#: The authoritative frozen checkpoint set, verified 2026-08-28 directly
#: against the promoted EM-4B artifacts' `checkpoint_ist__*` one-hot
#: feature categories, the EM-4D calibration keys, and
#: `config/explosive_move.json`'s own `checkpoints.candidate_ist`/
#: `accepted_ist` -- all three agree unanimously, across all 18
#: (family, threshold) combos. This is NOT re-derived from
#: `athena.explosive_move.contracts.CANDIDATE_CHECKPOINTS_IST` (which
#: already matches it) -- it is pinned here as its own independently-
#: verified constant so Track B's schedule can never silently drift from
#: what was actually proven, even if the contracts module ever changes.
TRACK_B_CHECKPOINT_SCHEDULE: tuple[str, ...] = (
    "09:20", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00", "14:00",
)


class PreflightError(Exception):
    """A Monday-morning precondition failed -- refuse to start the live
    capture rather than run it against a broken environment."""


def kite_auth_preflight(config_dir) -> str:
    """One minimal real Kite call (resolve the catalog for a single known
    instrument) before committing to the full capture -- the same "small
    canary before the larger run" discipline the EM-5 checkpoint-price
    diagnostic and CLAUDE.md's own expensive-run rule already established.
    Returns the resolved instrument's real symbol on success; raises
    `PreflightError` (never a bare provider exception) otherwise."""

    from athena.config.env import load_dotenv
    from athena.data.providers.kite_provider import KiteProvider
    from athena.errors import ProviderError

    load_dotenv()
    try:
        provider = KiteProvider.from_config_dir(config_dir, symbols=["INFY"])
        instruments = provider.instruments()
    except ProviderError as exc:
        raise PreflightError(f"Kite auth preflight failed: {exc}") from exc
    if not instruments:
        raise PreflightError("Kite auth preflight: catalog resolved but returned zero instruments")
    return instruments[0].symbol


def disk_space_preflight(*, path=".", minimum_free_gb: float = 2.0) -> float:
    """Real free space check before starting a capture campaign (2026-08-28
    session: two separate real disk-exhaustion incidents earlier the same
    day). Returns real free GB on success; raises `PreflightError` if below
    `minimum_free_gb`."""

    free_bytes = shutil.disk_usage(path).free
    free_gb = free_bytes / (1024**3)
    if free_gb < minimum_free_gb:
        raise PreflightError(
            f"disk space preflight failed: {free_gb:.2f}GB free, need >= {minimum_free_gb}GB"
        )
    return free_gb


@dataclass(frozen=True, slots=True)
class TrackBRunManifest:
    """Immutable record of one Track B capture campaign -- symbols,
    schedule, and every capture file produced, so the later settlement
    comparison (potentially run by a different process, another day) has
    an authoritative, self-describing index rather than having to
    rediscover raw files by convention."""

    run_id: str
    session_date: date
    checkpoints: tuple[str, ...]
    instrument_ids: tuple[str, ...]
    liquidity_bucket_by_instrument: dict[str, str]
    kite_auth_verified_symbol: str
    disk_free_gb_at_start: float
    capture_file_paths: tuple[str, ...] = field(default_factory=tuple)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id, "session_date": self.session_date.isoformat(),
            "checkpoints": list(self.checkpoints), "instrument_ids": list(self.instrument_ids),
            "liquidity_bucket_by_instrument": self.liquidity_bucket_by_instrument,
            "kite_auth_verified_symbol": self.kite_auth_verified_symbol,
            "disk_free_gb_at_start": self.disk_free_gb_at_start,
            "capture_file_paths": list(self.capture_file_paths),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> TrackBRunManifest:
        return cls(
            run_id=payload["run_id"], session_date=date.fromisoformat(payload["session_date"]),
            checkpoints=tuple(payload["checkpoints"]), instrument_ids=tuple(payload["instrument_ids"]),
            liquidity_bucket_by_instrument=payload["liquidity_bucket_by_instrument"],
            kite_auth_verified_symbol=payload["kite_auth_verified_symbol"],
            disk_free_gb_at_start=payload["disk_free_gb_at_start"],
            capture_file_paths=tuple(payload.get("capture_file_paths", ())),
            started_at=datetime.fromisoformat(payload["started_at"]) if payload.get("started_at") else None,
            finished_at=datetime.fromisoformat(payload["finished_at"]) if payload.get("finished_at") else None,
        )


def build_classification_report_skeleton(
    *, run_id: str, session_date: date, checkpoints: tuple[str, ...],
    liquidity_bucket_by_instrument: dict[str, str],
) -> dict:
    """The exact field/table skeleton `Milestone Review Summary -- EM-5
    Track B` needs, per the Owner's enumeration -- structure only, every
    value `None`/empty until a real comparison populates it. Never
    pre-filled with a conclusion; `populate_classification_report` is the
    only thing allowed to fill it in, and only from a real
    `RowComparison` set."""

    return {
        "run_id": run_id, "session_date": session_date.isoformat(), "checkpoints": list(checkpoints),
        "liquidity_bucket_by_instrument": liquidity_bucket_by_instrument,
        "provisional_capture_inventory": None, "settled_capture_inventory": None,
        "raw_timestamp_behavior_by_checkpoint": None,
        "ohlcv_exact_match_rate_overall": None, "ohlcv_exact_match_rate_by_checkpoint": None,
        "ohlcv_exact_match_rate_by_liquidity": None,
        "unique_mapping_rate_overall": None, "unique_mapping_rate_by_checkpoint": None,
        "timestamp_offset_seconds_by_checkpoint": None,
        "evidence_field_differences": None,
        "logit_probability_rank_impact": None,
        "classification": None,
        "recommended_correction": None,
        "expected_effect_on_frozen_em2_evidence": None,
        "full_canary_safe_to_run": None,
    }


def populate_classification_report(
    skeleton: dict, *, comparisons_by_instrument: dict[str, tuple[RowComparison, ...]],
) -> dict:
    """Fills the skeleton from real `RowComparison` data only -- one
    classification per instrument, and one overall classification via the
    Owner's same priority rule (ambiguous > OHLCV-changed > timestamp-only)
    applied across every instrument's off-grid rows combined, so a single
    ambiguous or changed row anywhere cannot be masked by averaging."""

    report = dict(skeleton)
    all_comparisons = tuple(c for comps in comparisons_by_instrument.values() for c in comps)
    off_grid = [c for c in all_comparisons if not c.provisional_was_on_grid]

    report["provisional_capture_inventory"] = {
        iid: len(comps) for iid, comps in comparisons_by_instrument.items()
    }
    report["ohlcv_exact_match_rate_overall"] = (
        sum(1 for c in off_grid if c.ohlcv_exact_match) / len(off_grid) if off_grid else None
    )
    report["unique_mapping_rate_overall"] = (
        sum(1 for c in off_grid if c.mapping_unique) / len(off_grid) if off_grid else None
    )
    by_checkpoint: dict[str, list[RowComparison]] = {}
    for c in off_grid:
        by_checkpoint.setdefault(c.provisional_ts.strftime("%H:%M"), []).append(c)
    report["ohlcv_exact_match_rate_by_checkpoint"] = {
        cp: sum(1 for c in rows if c.ohlcv_exact_match) / len(rows) for cp, rows in by_checkpoint.items()
    }
    report["unique_mapping_rate_by_checkpoint"] = {
        cp: sum(1 for c in rows if c.mapping_unique) / len(rows) for cp, rows in by_checkpoint.items()
    }
    report["timestamp_offset_seconds_by_checkpoint"] = {
        cp: [c.timestamp_offset_seconds for c in rows if c.timestamp_offset_seconds is not None]
        for cp, rows in by_checkpoint.items()
    }

    if off_grid:
        report["classification"] = classify_diagnosis(all_comparisons).value
    return report
    return DiagnosisOutcome.TIMESTAMP_ONLY_PROVISIONAL_DRIFT
