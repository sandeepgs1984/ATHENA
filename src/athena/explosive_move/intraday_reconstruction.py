"""Deterministic EM-1r3 reconstruction of captured five-minute sessions.

This module is deliberately provider-free.  Data adapters capture authoritative
rows; this module admits only exact exchange-calendar slots and never invents,
rounds, or interpolates market information.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from athena.domain.enums import Timeframe
from athena.domain.market import Candle

CONTRACT_VERSION = "EM-1R3_INTRADAY_RECONSTRUCTION_V1"
NORMALIZATION_VERSION = "EXACT_EXCHANGE_SLOTS_V1"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class SessionExclusionReason(str, Enum):
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    SOURCE_TIMEZONE_INVALID = "SOURCE_TIMEZONE_INVALID"
    OUT_OF_SESSION_ROW = "OUT_OF_SESSION_ROW"
    OFF_GRID_TIMESTAMP = "OFF_GRID_TIMESTAMP"
    CONFLICTING_SLOT = "CONFLICTING_SLOT"
    MISSING_SLOT = "MISSING_SLOT"


class RepairType(str, Enum):
    AUTHORITATIVE_REINGESTION = "AUTHORITATIVE_REINGESTION"
    IDENTICAL_DUPLICATE_COLLAPSE = "IDENTICAL_DUPLICATE_COLLAPSE"


@dataclass(frozen=True, slots=True)
class SessionRecord:
    instrument_id: str
    session_date: date
    status: str
    expected_slots: int
    source_rows: int
    admitted_rows: int
    identical_duplicates_collapsed: int
    content_sha256: str | None
    exclusion_reason: SessionExclusionReason | None = None
    exclusion_detail: str | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("session instrument_id cannot be empty")
        if self.status not in {"ADMITTED", "EXCLUDED"}:
            raise ValueError("session status must be ADMITTED or EXCLUDED")
        counts = (
            self.expected_slots,
            self.source_rows,
            self.admitted_rows,
            self.identical_duplicates_collapsed,
        )
        if any(count < 0 for count in counts):
            raise ValueError("session row counts cannot be negative")
        if self.expected_slots < 1:
            raise ValueError("session expected_slots must be positive")
        if self.status == "ADMITTED":
            if self.admitted_rows != self.expected_slots:
                raise ValueError("admitted session must contain every expected slot")
            if self.source_rows != self.admitted_rows + self.identical_duplicates_collapsed:
                raise ValueError("admitted session source-row accounting is inconsistent")
            _require_sha256(self.content_sha256, "session content_sha256")
            if self.exclusion_reason is not None or self.exclusion_detail is not None:
                raise ValueError("admitted session cannot carry exclusion metadata")
            return
        if self.admitted_rows != 0 or self.content_sha256 is not None:
            raise ValueError("excluded session cannot admit rows or content")
        if self.identical_duplicates_collapsed != 0:
            raise ValueError("excluded session cannot claim completed duplicate repair")
        if self.exclusion_reason is None or not self.exclusion_detail:
            raise ValueError("excluded session requires a reason and detail")


@dataclass(frozen=True, slots=True)
class SessionReconstruction:
    record: SessionRecord
    candles: tuple[Candle, ...]


@dataclass(frozen=True, slots=True)
class SourceCapture:
    instrument_id: str
    session_date: date
    requested_start: datetime
    requested_end: datetime
    captured_at: datetime
    provider: str
    artifact: str
    payload_sha256: str
    row_count: int
    retrieval_error: str | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id or not self.provider or not self.artifact:
            raise ValueError("source capture identity fields cannot be empty")
        if any(
            value.tzinfo is None
            for value in (self.requested_start, self.requested_end, self.captured_at)
        ):
            raise ValueError("source capture timestamps must be timezone-aware")
        if self.requested_start > self.requested_end:
            raise ValueError("source capture start cannot be after end")
        if self.requested_start.date() != self.session_date:
            raise ValueError("source capture start must belong to session_date")
        _require_sha256(self.payload_sha256, "source payload_sha256")
        if self.row_count < 0:
            raise ValueError("source capture row_count cannot be negative")
        if self.retrieval_error is not None and not self.retrieval_error.strip():
            raise ValueError("source capture retrieval_error cannot be blank")


@dataclass(frozen=True, slots=True)
class NormalizedArtifact:
    instrument_id: str
    artifact: str
    payload_sha256: str
    admitted_sessions: int
    row_count: int

    def __post_init__(self) -> None:
        if not self.instrument_id or not self.artifact:
            raise ValueError("normalized artifact identity fields cannot be empty")
        _require_sha256(self.payload_sha256, "normalized payload_sha256")
        if self.admitted_sessions < 0 or self.row_count < 0:
            raise ValueError("normalized artifact counts cannot be negative")


@dataclass(frozen=True, slots=True)
class IntradayReconstructionManifest:
    study_start: date
    study_end: date
    cohort_name: str
    cohort_id: str
    cohort_instrument_ids: tuple[str, ...]
    population_basis: str
    population_limitation: str
    source_captures: tuple[SourceCapture, ...]
    normalized_artifacts: tuple[NormalizedArtifact, ...]
    sessions: tuple[SessionRecord, ...]
    contract_version: str = CONTRACT_VERSION
    normalization_version: str = NORMALIZATION_VERSION

    def __post_init__(self) -> None:
        if self.study_start > self.study_end:
            raise ValueError("study_start cannot be after study_end")
        if not self.cohort_instrument_ids:
            raise ValueError("intraday reconstruction cohort cannot be empty")
        if self.cohort_instrument_ids != tuple(sorted(set(self.cohort_instrument_ids))):
            raise ValueError("cohort_instrument_ids must be unique and sorted")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported intraday reconstruction contract")
        if self.normalization_version != NORMALIZATION_VERSION:
            raise ValueError("unsupported intraday normalization contract")
        capture_ids = {item.instrument_id for item in self.source_captures}
        artifact_ids = tuple(item.instrument_id for item in self.normalized_artifacts)
        if capture_ids != set(self.cohort_instrument_ids):
            raise ValueError("source captures must cover the complete cohort")
        capture_keys = tuple(
            (item.instrument_id, item.session_date) for item in self.source_captures
        )
        if capture_keys != tuple(sorted(set(capture_keys))):
            raise ValueError("source captures must be unique and deterministically sorted")
        if artifact_ids != self.cohort_instrument_ids:
            raise ValueError(
                "normalized artifacts must cover the complete sorted cohort exactly once"
            )
        session_keys = tuple(
            (item.instrument_id, item.session_date) for item in self.sessions
        )
        if session_keys != tuple(sorted(set(session_keys))):
            raise ValueError("session records must be unique and deterministically sorted")
        if capture_keys != session_keys:
            raise ValueError(
                "source captures and session records must cover the same "
                "instrument/session matrix"
            )

    @property
    def replay_id(self) -> str:
        return _digest(
            {
                "study_start": self.study_start,
                "study_end": self.study_end,
                "cohort_name": self.cohort_name,
                "cohort_id": self.cohort_id,
                "cohort_instrument_ids": self.cohort_instrument_ids,
                "population_basis": self.population_basis,
                "source_payloads": [item.payload_sha256 for item in self.source_captures],
                "normalized_payloads": [item.payload_sha256 for item in self.normalized_artifacts],
                "sessions": self.sessions,
                "contract_version": self.contract_version,
                "normalization_version": self.normalization_version,
            }
        )

    @property
    def manifest_id(self) -> str:
        provenance_id = _digest(
            {
                "replay_id": self.replay_id,
                "source_captures": self.source_captures,
                "population_limitation": self.population_limitation,
            }
        )
        return f"em1r3-{provenance_id[:24]}"

    @property
    def admitted_session_count(self) -> int:
        return sum(item.status == "ADMITTED" for item in self.sessions)

    @property
    def excluded_session_count(self) -> int:
        return sum(item.status == "EXCLUDED" for item in self.sessions)

    @property
    def repair_counts(self) -> dict[str, int]:
        return {
            RepairType.AUTHORITATIVE_REINGESTION.value: sum(
                item.admitted_rows for item in self.sessions if item.status == "ADMITTED"
            ),
            RepairType.IDENTICAL_DUPLICATE_COLLAPSE.value: sum(
                item.identical_duplicates_collapsed for item in self.sessions
            ),
        }

    @property
    def exclusion_counts(self) -> dict[str, int]:
        counts = Counter(
            item.exclusion_reason.value
            for item in self.sessions
            if item.exclusion_reason is not None
        )
        return {reason.value: counts[reason.value] for reason in SessionExclusionReason}

    def to_dict(self) -> dict[str, Any]:
        payload = _jsonable(asdict(self))
        payload.update(
            replay_id=self.replay_id,
            manifest_id=self.manifest_id,
            admitted_session_count=self.admitted_session_count,
            excluded_session_count=self.excluded_session_count,
            repair_counts=self.repair_counts,
            exclusion_counts=self.exclusion_counts,
        )
        return payload


def reconstruct_regular_session(
    *,
    instrument_id: str,
    session_date: date,
    expected_slots: Iterable[datetime],
    source_rows: Iterable[Candle],
    retrieval_error: str | None = None,
) -> SessionReconstruction:
    """Admit one complete exact-slot session or exclude it with one stable reason."""

    expected = tuple(sorted(expected_slots))
    rows = tuple(source_rows)
    if not expected:
        raise ValueError("a regular session requires at least one expected exchange slot")
    if retrieval_error is not None:
        return _excluded(
            instrument_id,
            session_date,
            expected,
            rows,
            SessionExclusionReason.RETRIEVAL_FAILED,
            retrieval_error,
        )
    if any(slot.tzinfo is None for slot in expected) or any(row.ts_open.tzinfo is None for row in rows):
        return _excluded(
            instrument_id,
            session_date,
            expected,
            rows,
            SessionExclusionReason.SOURCE_TIMEZONE_INVALID,
            "all expected and source timestamps must be timezone-aware",
        )

    expected_set = set(expected)
    if any(row.ts_open.date() != session_date for row in rows):
        return _excluded(
            instrument_id,
            session_date,
            expected,
            rows,
            SessionExclusionReason.OUT_OF_SESSION_ROW,
            "capture contains a row outside the requested session date",
        )
    off_grid = sorted({row.ts_open for row in rows if row.ts_open not in expected_set})
    if off_grid:
        return _excluded(
            instrument_id,
            session_date,
            expected,
            rows,
            SessionExclusionReason.OFF_GRID_TIMESTAMP,
            f"{len(off_grid)} timestamp(s) do not match exact exchange slots",
        )

    grouped: dict[datetime, list[Candle]] = defaultdict(list)
    for row in rows:
        if row.instrument_id != instrument_id or row.timeframe is not Timeframe.M5:
            return _excluded(
                instrument_id,
                session_date,
                expected,
                rows,
                SessionExclusionReason.CONFLICTING_SLOT,
                "source row instrument/timeframe does not match reconstruction scope",
            )
        grouped[row.ts_open].append(row)

    collapsed = 0
    admitted: list[Candle] = []
    for slot in expected:
        candidates = grouped.get(slot, [])
        if not candidates:
            return _excluded(
                instrument_id,
                session_date,
                expected,
                rows,
                SessionExclusionReason.MISSING_SLOT,
                f"missing exact slot {slot.isoformat()}",
            )
        identities = {_candle_identity(row) for row in candidates}
        if len(identities) != 1:
            return _excluded(
                instrument_id,
                session_date,
                expected,
                rows,
                SessionExclusionReason.CONFLICTING_SLOT,
                f"conflicting observations at {slot.isoformat()}",
            )
        admitted.append(candidates[0])
        collapsed += len(candidates) - 1

    content_sha256 = _digest([_candle_payload(row) for row in admitted])
    record = SessionRecord(
        instrument_id=instrument_id,
        session_date=session_date,
        status="ADMITTED",
        expected_slots=len(expected),
        source_rows=len(rows),
        admitted_rows=len(admitted),
        identical_duplicates_collapsed=collapsed,
        content_sha256=content_sha256,
    )
    return SessionReconstruction(record=record, candles=tuple(admitted))


def write_immutable_manifest(directory: Path, manifest: IntradayReconstructionManifest) -> Path:
    payload = json.dumps(manifest.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
    return write_immutable_payload(directory, manifest.manifest_id, payload.encode())


def write_immutable_payload(directory: Path, identity: str, payload: bytes) -> Path:
    """Write content immutably; identical retries reuse, conflicts fail loudly."""

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{identity}.json"
    if target.exists():
        if target.read_bytes() != payload:
            raise FileExistsError(f"immutable evidence conflict: {target}")
        return target
    fd, temporary = tempfile.mkstemp(prefix=".em1r3-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != payload:
                raise
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def canonical_candle_payload(candles: Iterable[Candle]) -> bytes:
    serialized = json.dumps(
        [_candle_payload(row) for row in candles],
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{serialized}\n".encode()


def candles_from_payload(payload: bytes) -> tuple[Candle, ...]:
    """Parse a captured artifact through frozen Candle validation."""

    decoded = json.loads(payload)
    if not isinstance(decoded, list):
        raise ValueError("captured candle artifact must contain a JSON list")
    candles: list[Candle] = []
    for item in decoded:
        if not isinstance(item, dict):
            raise ValueError("captured candle rows must be JSON objects")
        adjusted = item["adjusted"]
        if not isinstance(adjusted, bool):
            raise ValueError("captured candle adjusted must be a JSON boolean")
        candles.append(
            Candle(
                instrument_id=str(item["instrument_id"]),
                timeframe=Timeframe(str(item["timeframe"])),
                ts_open=datetime.fromisoformat(str(item["ts_open"])),
                open=Decimal(str(item["open"])),
                high=Decimal(str(item["high"])),
                low=Decimal(str(item["low"])),
                close=Decimal(str(item["close"])),
                volume=int(item["volume"]),
                source=str(item["source"]),
                adjusted=adjusted,
            )
        )
    return tuple(candles)


def intraday_manifest_from_payload(payload: bytes) -> IntradayReconstructionManifest:
    """Load and verify an immutable EM-1r3 manifest."""

    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("intraday reconstruction manifest must be a JSON object")
    manifest = IntradayReconstructionManifest(
        study_start=date.fromisoformat(str(decoded["study_start"])),
        study_end=date.fromisoformat(str(decoded["study_end"])),
        cohort_name=str(decoded["cohort_name"]),
        cohort_id=str(decoded["cohort_id"]),
        cohort_instrument_ids=tuple(str(item) for item in decoded["cohort_instrument_ids"]),
        population_basis=str(decoded["population_basis"]),
        population_limitation=str(decoded["population_limitation"]),
        source_captures=tuple(_source_capture_from_dict(item) for item in decoded["source_captures"]),
        normalized_artifacts=tuple(
            _normalized_artifact_from_dict(item) for item in decoded["normalized_artifacts"]
        ),
        sessions=tuple(_session_record_from_dict(item) for item in decoded["sessions"]),
        contract_version=str(decoded["contract_version"]),
        normalization_version=str(decoded["normalization_version"]),
    )
    if decoded.get("replay_id") != manifest.replay_id:
        raise ValueError("intraday reconstruction manifest replay_id mismatch")
    if decoded.get("manifest_id") != manifest.manifest_id:
        raise ValueError("intraday reconstruction manifest_id mismatch")
    return manifest


def _source_capture_from_dict(item: Any) -> SourceCapture:
    if not isinstance(item, dict):
        raise ValueError("source capture must be a JSON object")
    return SourceCapture(
        instrument_id=str(item["instrument_id"]),
        session_date=date.fromisoformat(str(item["session_date"])),
        requested_start=datetime.fromisoformat(str(item["requested_start"])),
        requested_end=datetime.fromisoformat(str(item["requested_end"])),
        captured_at=datetime.fromisoformat(str(item["captured_at"])),
        provider=str(item["provider"]),
        artifact=str(item["artifact"]),
        payload_sha256=str(item["payload_sha256"]),
        row_count=int(item["row_count"]),
        retrieval_error=None if item.get("retrieval_error") is None else str(item["retrieval_error"]),
    )


def _normalized_artifact_from_dict(item: Any) -> NormalizedArtifact:
    if not isinstance(item, dict):
        raise ValueError("normalized artifact must be a JSON object")
    return NormalizedArtifact(
        instrument_id=str(item["instrument_id"]),
        artifact=str(item["artifact"]),
        payload_sha256=str(item["payload_sha256"]),
        admitted_sessions=int(item["admitted_sessions"]),
        row_count=int(item["row_count"]),
    )


def _session_record_from_dict(item: Any) -> SessionRecord:
    if not isinstance(item, dict):
        raise ValueError("session record must be a JSON object")
    raw_reason = item.get("exclusion_reason")
    return SessionRecord(
        instrument_id=str(item["instrument_id"]),
        session_date=date.fromisoformat(str(item["session_date"])),
        status=str(item["status"]),
        expected_slots=int(item["expected_slots"]),
        source_rows=int(item["source_rows"]),
        admitted_rows=int(item["admitted_rows"]),
        identical_duplicates_collapsed=int(item["identical_duplicates_collapsed"]),
        content_sha256=None if item.get("content_sha256") is None else str(item["content_sha256"]),
        exclusion_reason=None if raw_reason is None else SessionExclusionReason(str(raw_reason)),
        exclusion_detail=None
        if item.get("exclusion_detail") is None
        else str(item["exclusion_detail"]),
    )


def _excluded(
    instrument_id: str,
    session_date: date,
    expected: tuple[datetime, ...],
    rows: tuple[Candle, ...],
    reason: SessionExclusionReason,
    detail: str,
) -> SessionReconstruction:
    return SessionReconstruction(
        record=SessionRecord(
            instrument_id=instrument_id,
            session_date=session_date,
            status="EXCLUDED",
            expected_slots=len(expected),
            source_rows=len(rows),
            admitted_rows=0,
            identical_duplicates_collapsed=0,
            content_sha256=None,
            exclusion_reason=reason,
            exclusion_detail=detail,
        ),
        candles=(),
    )


def _candle_identity(candle: Candle) -> tuple[Any, ...]:
    return (
        candle.instrument_id,
        candle.timeframe.value,
        candle.ts_open.isoformat(),
        str(candle.open),
        str(candle.high),
        str(candle.low),
        str(candle.close),
        candle.volume,
        candle.source,
        candle.adjusted,
    )


def _candle_payload(candle: Candle) -> dict[str, Any]:
    return {
        "instrument_id": candle.instrument_id,
        "timeframe": candle.timeframe.value,
        "ts_open": candle.ts_open.isoformat(),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": candle.volume,
        "source": candle.source,
        "adjusted": candle.adjusted,
    }


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _require_sha256(value: str | None, field: str) -> None:
    if value is None or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
