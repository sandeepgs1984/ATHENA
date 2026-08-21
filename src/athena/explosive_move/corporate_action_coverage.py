"""EM-1r2 corporate-action coverage and survivor-cohort contracts.

The module is pure: official-source retrieval remains behind a provider adapter.
It turns captured source rows into deterministic domain records and provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from athena.domain.market import CorporateAction, Instrument

CONTRACT_VERSION = "EM-1R2_CA_COVERAGE_V1"
NORMALIZATION_VERSION = "EM-1R2_CA_NORMALIZATION_V2"
SURVIVOR_COHORT_NAME = "ATHENA_CURRENT_CANONICAL_SURVIVOR_COHORT_V1"
SURVIVOR_COHORT_LIMITATION = (
    "Survivor-cohort research based on ATHENA's current canonical universe; "
    "this is not point-in-time historical NSE-universe evidence."
)
OFFICIAL_NSE_SOURCE = "NSE_OFFICIAL_CORPORATE_ACTIONS"


class CorporateActionExclusionReason(str, Enum):
    MALFORMED_SOURCE_ROW = "MALFORMED_SOURCE_ROW"
    SYMBOL_OUTSIDE_COHORT = "SYMBOL_OUTSIDE_COHORT"
    INSTRUMENT_IDENTITY_CONFLICT = "INSTRUMENT_IDENTITY_CONFLICT"
    INSTRUMENT_RESOLUTION_AMBIGUOUS = "INSTRUMENT_RESOLUTION_AMBIGUOUS"
    ACTION_CLASSIFICATION_AMBIGUOUS = "ACTION_CLASSIFICATION_AMBIGUOUS"
    ACTION_TERMS_AMBIGUOUS = "ACTION_TERMS_AMBIGUOUS"
    RETRIEVAL_COVERAGE_INCOMPLETE = "RETRIEVAL_COVERAGE_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class SurvivorCohort:
    name: str
    universe_name: str
    resolution_date: date
    instrument_ids: tuple[str, ...]
    group_effective_dates: tuple[tuple[str, date], ...]
    limitation: str = SURVIVOR_COHORT_LIMITATION

    def __post_init__(self) -> None:
        if self.name != SURVIVOR_COHORT_NAME:
            raise ValueError(f"unsupported survivor cohort contract: {self.name}")
        if not self.instrument_ids:
            raise ValueError("survivor cohort cannot be empty")
        if self.instrument_ids != tuple(sorted(set(self.instrument_ids))):
            raise ValueError("survivor cohort instrument_ids must be unique and sorted")
        if self.limitation != SURVIVOR_COHORT_LIMITATION:
            raise ValueError("survivor cohort limitation is frozen")

    @property
    def cohort_id(self) -> str:
        return _digest(_jsonable(asdict(self)))


@dataclass(frozen=True, slots=True)
class OfficialCorporateActionRow:
    source_record_id: str
    symbol: str
    series: str
    ex_date: date
    subject: str
    source_url: str
    payload_sha256: str
    isin: str | None = None

    def __post_init__(self) -> None:
        if not self.source_record_id.strip():
            raise ValueError("official corporate-action row requires a source record id")
        if not self.symbol.strip() or not self.series.strip() or not self.subject.strip():
            raise ValueError("official corporate-action row is missing required source fields")
        if not _is_official_nse_url(self.source_url):
            raise ValueError("corporate-action source must be an official NSE URL")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256.lower()):
            raise ValueError("payload_sha256 must be a SHA-256 hex digest")
        if self.isin is not None and not re.fullmatch(r"[A-Z0-9]{12}", self.isin.upper()):
            raise ValueError("official corporate-action ISIN must contain 12 letters or digits")


@dataclass(frozen=True, slots=True)
class CorporateActionExclusion:
    source_record_id: str
    symbol: str
    ex_date: date | None
    reason: CorporateActionExclusionReason
    detail: str
    source_url: str
    payload_sha256: str

    def __post_init__(self) -> None:
        if not _is_official_nse_url(self.source_url):
            raise ValueError("corporate-action exclusion requires an official NSE URL")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256.lower()):
            raise ValueError("corporate-action exclusion requires a payload SHA-256")


@dataclass(frozen=True, slots=True)
class RetrievalSlice:
    requested_start: date
    requested_end: date
    retrieved_at: datetime
    source_url: str
    payload_sha256: str
    raw_artifact: str
    record_count: int
    complete: bool
    completeness_basis: str

    def __post_init__(self) -> None:
        if self.requested_start > self.requested_end:
            raise ValueError("retrieval slice start cannot be after end")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        if self.record_count < 0:
            raise ValueError("record_count cannot be negative")
        if not _is_official_nse_url(self.source_url):
            raise ValueError("corporate-action source must be an official NSE URL")
        if not re.fullmatch(r"[0-9a-f]{64}", self.payload_sha256.lower()):
            raise ValueError("payload_sha256 must be a SHA-256 hex digest")
        if not self.raw_artifact.strip():
            raise ValueError("retrieval slice requires an immutable raw artifact reference")
        if self.complete and not self.completeness_basis.strip():
            raise ValueError("complete slices require an explicit completeness basis")


@dataclass(frozen=True, slots=True)
class CorporateActionCoverageManifest:
    study_start: date
    study_end: date
    cohort: SurvivorCohort
    retrieval_slices: tuple[RetrievalSlice, ...]
    actions: tuple[CorporateAction, ...]
    exclusions: tuple[CorporateActionExclusion, ...]
    contract_version: str = CONTRACT_VERSION
    normalization_version: str = NORMALIZATION_VERSION
    authority: str = OFFICIAL_NSE_SOURCE

    def __post_init__(self) -> None:
        if self.study_start > self.study_end:
            raise ValueError("study_start cannot be after study_end")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported corporate-action coverage contract")
        if self.normalization_version != NORMALIZATION_VERSION:
            raise ValueError("unsupported corporate-action normalization contract")
        if self.authority != OFFICIAL_NSE_SOURCE:
            raise ValueError("Kite or another vendor cannot be corporate-action authority")
        action_keys = tuple((a.ex_date, a.instrument_id, a.action_id) for a in self.actions)
        if action_keys != tuple(sorted(set(action_keys))):
            raise ValueError("actions must be unique and deterministically sorted")

    @property
    def coverage_complete(self) -> bool:
        slices = sorted(self.retrieval_slices, key=lambda item: item.requested_start)
        if not slices or any(not item.complete for item in slices):
            return False
        cursor = self.study_start
        for item in slices:
            if item.requested_start != cursor or item.requested_end > self.study_end:
                return False
            cursor = item.requested_end + timedelta(days=1)
        return cursor == self.study_end + timedelta(days=1)

    @property
    def manifest_id(self) -> str:
        return _digest(self.to_dict())

    @property
    def replay_id(self) -> str:
        """Identify equivalent evidence independently of retrieval timestamps."""

        replay_slices = tuple(
            {
                "requested_start": item.requested_start,
                "requested_end": item.requested_end,
                "source_url": item.source_url,
                "payload_sha256": item.payload_sha256,
                "record_count": item.record_count,
                "complete": item.complete,
                "completeness_basis": item.completeness_basis,
            }
            for item in self.retrieval_slices
        )
        return _digest(
            {
                "study_start": self.study_start,
                "study_end": self.study_end,
                "cohort": self.cohort,
                "retrieval_slices": replay_slices,
                "actions": self.actions,
                "exclusions": self.exclusions,
                "contract_version": self.contract_version,
                "normalization_version": self.normalization_version,
                "authority": self.authority,
            }
        )

    @property
    def authoritative_for_research(self) -> bool:
        """Only gap-free, structurally usable official evidence admits research."""

        malformed = CorporateActionExclusionReason.MALFORMED_SOURCE_ROW
        return self.coverage_complete and all(item.reason is not malformed for item in self.exclusions)

    @property
    def raw_record_count(self) -> int:
        return sum(item.record_count for item in self.retrieval_slices)

    @property
    def accepted_action_count(self) -> int:
        return len(self.actions)

    @property
    def exclusion_count(self) -> int:
        return len(self.exclusions)

    @property
    def exclusion_counts(self) -> dict[str, int]:
        counts = {reason.value: 0 for reason in CorporateActionExclusionReason}
        for exclusion in self.exclusions:
            counts[exclusion.reason.value] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


def build_survivor_cohort(
    *,
    universe_name: str,
    resolution_date: date,
    instrument_ids: tuple[str, ...],
    group_effective_dates: tuple[tuple[str, date], ...],
) -> SurvivorCohort:
    """Freeze today's canonical population without projecting it backward."""

    return SurvivorCohort(
        name=SURVIVOR_COHORT_NAME,
        universe_name=universe_name,
        resolution_date=resolution_date,
        instrument_ids=tuple(sorted(set(instrument_ids))),
        group_effective_dates=tuple(sorted(group_effective_dates)),
    )


def normalize_official_actions(
    rows: tuple[OfficialCorporateActionRow, ...],
    *,
    instruments: tuple[Instrument, ...],
    cohort: SurvivorCohort,
) -> tuple[tuple[CorporateAction, ...], tuple[CorporateActionExclusion, ...]]:
    """Resolve and classify official rows; ambiguity is evidence, never a guess."""

    isin_index: dict[str, list[Instrument]] = {}
    symbol_index: dict[tuple[str, str], list[Instrument]] = {}
    cohort_ids = set(cohort.instrument_ids)
    for instrument in instruments:
        if instrument.instrument_id in cohort_ids and instrument.exchange.upper() == "NSE":
            symbol_key = (instrument.symbol.upper(), instrument.series.upper())
            symbol_index.setdefault(symbol_key, []).append(instrument)
            if instrument.isin:
                isin_index.setdefault(instrument.isin.upper(), []).append(instrument)

    actions: list[CorporateAction] = []
    exclusions: list[CorporateActionExclusion] = []
    for row in sorted(rows, key=lambda item: (item.ex_date, item.symbol, item.source_record_id)):
        symbol_candidates = symbol_index.get((row.symbol.upper(), row.series.upper()), [])
        if row.isin:
            candidates = isin_index.get(row.isin.upper(), [])
            resolution_method = "ISIN"
            if not candidates and symbol_candidates:
                canonical_isins = {
                    candidate.isin.upper()
                    for candidate in symbol_candidates
                    if candidate.isin
                }
                if canonical_isins:
                    exclusions.append(
                        _exclusion(
                            row,
                            CorporateActionExclusionReason.INSTRUMENT_IDENTITY_CONFLICT,
                        )
                    )
                    continue
                candidates = symbol_candidates
                resolution_method = "SYMBOL_SERIES_CANONICAL_ISIN_UNAVAILABLE"
        else:
            candidates = symbol_candidates
            resolution_method = "SYMBOL_SERIES"
        if not candidates:
            exclusions.append(_exclusion(row, CorporateActionExclusionReason.SYMBOL_OUTSIDE_COHORT))
            continue
        if len(candidates) != 1:
            exclusions.append(
                _exclusion(row, CorporateActionExclusionReason.INSTRUMENT_RESOLUTION_AMBIGUOUS)
            )
            continue
        action_type, terms = _classify(row.subject)
        if action_type is None:
            exclusions.append(
                _exclusion(row, CorporateActionExclusionReason.ACTION_CLASSIFICATION_AMBIGUOUS)
            )
            continue
        if terms is None:
            exclusions.append(_exclusion(row, CorporateActionExclusionReason.ACTION_TERMS_AMBIGUOUS))
            continue
        instrument = candidates[0]
        details = {
            **terms,
            "official_subject": row.subject,
            "official_series": row.series,
            "official_record_id": row.source_record_id,
            "official_isin": row.isin,
            "official_source_url": row.source_url,
            "payload_sha256": row.payload_sha256,
            "cohort_id": cohort.cohort_id,
            "population_basis": "SURVIVOR_COHORT",
            "resolution_method": resolution_method,
            "normalization_version": NORMALIZATION_VERSION,
        }
        action_id = "nse-ca-" + _digest(
            {
                "source_record_id": row.source_record_id,
                "instrument_id": instrument.instrument_id,
                "ex_date": row.ex_date,
                "subject": row.subject,
            }
        )[:24]
        actions.append(
            CorporateAction(
                action_id=action_id,
                instrument_id=instrument.instrument_id,
                action_type=action_type,
                ex_date=row.ex_date,
                details=details,
            )
        )
    ordered_actions = tuple(sorted(actions, key=lambda a: (a.ex_date, a.instrument_id, a.action_id)))
    ordered_exclusions = tuple(
        sorted(exclusions, key=lambda e: (e.ex_date or date.min, e.symbol, e.source_record_id))
    )
    return ordered_actions, ordered_exclusions


def write_immutable_manifest(
    directory: Path, manifest: CorporateActionCoverageManifest
) -> Path:
    """Persist canonical JSON atomically and never overwrite conflicting evidence."""

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{manifest.manifest_id}.json"
    payload = json.dumps(manifest.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"manifest conflict: {target}")
        return target
    fd, temporary = tempfile.mkstemp(prefix=".em1r2-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_text(encoding="utf-8") != payload:
                raise
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


def _classify(subject: str) -> tuple[str | None, dict[str, Any] | None]:
    normalized = " ".join(subject.upper().split())
    if "DEMERGER" in normalized or "DE-MERGER" in normalized:
        return "DEMERGER", {}
    if "MERGER" in normalized or "AMALGAMATION" in normalized:
        return "MERGER", {}
    if "SPLIT" in normalized or "SUB-DIVISION" in normalized or "SUB DIVISION" in normalized:
        numbers = _numbers(normalized)
        if len(numbers) < 2 or numbers[-1] == 0:
            return "SPLIT", None
        ratio = Fraction(numbers[-2]) / Fraction(numbers[-1])
        return "SPLIT", {"from_shares": ratio.denominator, "to_shares": ratio.numerator}
    if "BONUS" in normalized:
        numbers = _numbers(normalized)
        if len(numbers) < 2 or numbers[1] == 0:
            return "BONUS", None
        return "BONUS", {"bonus_shares": str(numbers[0]), "held_shares": str(numbers[1])}
    if "DIVIDEND" in normalized:
        return "DIVIDEND", {}
    if "RIGHT" in normalized:
        return "RIGHTS", {}
    if "NAME CHANGE" in normalized or "CHANGE IN NAME" in normalized:
        return "RENAME", {}
    return None, None


def _numbers(value: str) -> list[Decimal]:
    found: list[Decimal] = []
    for candidate in re.findall(r"(?<![A-Z])\d+(?:\.\d+)?", value):
        try:
            found.append(Decimal(candidate))
        except InvalidOperation:
            continue
    return found


def _exclusion(
    row: OfficialCorporateActionRow, reason: CorporateActionExclusionReason
) -> CorporateActionExclusion:
    return CorporateActionExclusion(
        source_record_id=row.source_record_id,
        symbol=row.symbol,
        ex_date=row.ex_date,
        reason=reason,
        detail=f"{reason.value}: {row.subject}",
        source_url=row.source_url,
        payload_sha256=row.payload_sha256,
    )


def _is_official_nse_url(value: str) -> bool:
    host = (urlparse(value).hostname or "").lower()
    return host == "nseindia.com" or host.endswith(".nseindia.com")


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
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
