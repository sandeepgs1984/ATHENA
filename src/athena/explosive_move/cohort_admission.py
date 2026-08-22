"""EM-1r4 cohort admission and quote-timestamp hygiene contracts.

Applies the EM-1r2 survivor-cohort contract (``corporate_action_coverage``)
to per-symbol-day research admission, and enforces quote-timestamp hygiene,
without ever claiming current membership as point-in-time historical
evidence (ADR-012 s6; EM-1a's own explicit finding that the instrument
registry has no populated listing/delisting dates). This module performs
no ingestion, no provider I/O, and no calendar resolution of its own — it
is pure over already-resolved domain objects and calendar facts the caller
(the Data-layer ingestion service) hands down, mirroring the exact
separation ``intraday_reconstruction.py`` (EM-1r3) already established
between calendar resolution (orchestration) and admission logic (domain).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from athena.domain.market import Instrument, Quote
from athena.explosive_move.corporate_action_coverage import SurvivorCohort

CONTRACT_VERSION = "EM-1R4_COHORT_ADMISSION_V1"

#: Sector history is never point-in-time authoritative in this ledger
#: (EM-1a: sector is a single current, undated string seeded once from an
#: NSE Nifty-500 CSV, with no historical mapping mechanism at all) -- every
#: EM-1r4 record reports this constant rather than the instrument's live,
#: undated `sector` field, so a research consumer can never mistake it for
#: dated evidence.
RESEARCH_SECTOR_UNKNOWN = "UNKNOWN"

_UNIX_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CohortAdmissionExclusionReason(str, Enum):
    SYMBOL_OUTSIDE_SURVIVOR_COHORT = "SYMBOL_OUTSIDE_SURVIVOR_COHORT"
    LISTING_DELISTING_AMBIGUOUS = "LISTING_DELISTING_AMBIGUOUS"


class QuoteHygieneExclusionReason(str, Enum):
    EPOCH_DEFAULT_TIMESTAMP = "EPOCH_DEFAULT_TIMESTAMP"
    TIMESTAMP_OUTSIDE_STUDY_BOUNDS = "TIMESTAMP_OUTSIDE_STUDY_BOUNDS"
    TIMESTAMP_OUTSIDE_SESSION_BOUNDS = "TIMESTAMP_OUTSIDE_SESSION_BOUNDS"


@dataclass(frozen=True, slots=True)
class SymbolDayAdmission:
    """One symbol-day's admission decision under the frozen survivor-cohort contract.

    ``eligibility_evidence_date`` is always the cohort's own resolution
    date -- never the session date itself and never a claim that the
    symbol traded on that historical date -- so "current membership is
    never projected backward" (EM-1r4 acceptance) is a structural property
    of every record, not a convention callers must remember to uphold.
    """

    instrument_id: str
    session_date: date
    cohort_name: str
    cohort_id: str
    cohort_limitation: str
    eligibility_evidence_date: date
    sector: str
    admitted: bool
    reasons: tuple[CohortAdmissionExclusionReason, ...] = ()

    def __post_init__(self) -> None:
        if self.admitted == bool(self.reasons):
            raise ValueError("admitted records have no reasons; excluded records require reasons")
        if self.sector != RESEARCH_SECTOR_UNKNOWN:
            raise ValueError("sector history is never point-in-time authoritative in this ledger")


@dataclass(frozen=True, slots=True)
class QuoteHygieneAssessment:
    """One quote's admission decision under the EM-1r4 timestamp-hygiene contract."""

    instrument_id: str
    ts: datetime
    admitted: bool
    reasons: tuple[QuoteHygieneExclusionReason, ...] = ()

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("QuoteHygieneAssessment.ts must be timezone-aware")
        if self.admitted == bool(self.reasons):
            raise ValueError("admitted quotes have no reasons; excluded quotes require reasons")


def assess_symbol_day_cohort_admission(
    *,
    instrument_id: str,
    session_date: date,
    listed_date: date | None,
    delisted_date: date | None,
    cohort: SurvivorCohort,
) -> SymbolDayAdmission:
    """Admit a symbol-day only under the frozen survivor-cohort contract.

    Membership is decided by cohort presence, never by projecting today's
    universe backward as if it were historical fact -- the cohort's own
    frozen ``limitation`` string travels with every decision, admitted or
    not, so a downstream consumer can never read an admission record
    without also reading why it is not point-in-time evidence.
    """

    reasons: list[CohortAdmissionExclusionReason] = []
    if instrument_id not in cohort.instrument_ids:
        reasons.append(CohortAdmissionExclusionReason.SYMBOL_OUTSIDE_SURVIVOR_COHORT)
    if _listing_delisting_ambiguous(
        session_date=session_date, listed_date=listed_date, delisted_date=delisted_date
    ):
        reasons.append(CohortAdmissionExclusionReason.LISTING_DELISTING_AMBIGUOUS)
    return SymbolDayAdmission(
        instrument_id=instrument_id,
        session_date=session_date,
        cohort_name=cohort.name,
        cohort_id=cohort.cohort_id,
        cohort_limitation=cohort.limitation,
        eligibility_evidence_date=cohort.resolution_date,
        sector=RESEARCH_SECTOR_UNKNOWN,
        admitted=not reasons,
        reasons=tuple(reasons),
    )


def _listing_delisting_ambiguous(
    *, session_date: date, listed_date: date | None, delisted_date: date | None
) -> bool:
    """Fail closed on any listing/delisting evidence that cannot place the
    whole session cleanly inside the tradable period -- internally
    inconsistent dates, a listing after the session, or a delisting before
    it. ``None`` on both fields (the current state of every instrument in
    this ledger, per EM-1a) is absent evidence, not ambiguous evidence: it
    is not flagged here, and admission falls through to the survivor-cohort
    basis alone, honestly disclosed via ``cohort_limitation``.
    """

    if listed_date is not None and delisted_date is not None and delisted_date < listed_date:
        return True
    if listed_date is not None and listed_date > session_date:
        return True
    return delisted_date is not None and delisted_date < session_date


def assess_quote_timestamp_hygiene(
    quote: Quote,
    *,
    study_start: date,
    study_end: date,
    market_timezone: ZoneInfo,
    is_trading_session: bool,
    session_open: time | None,
    session_close: time | None,
) -> QuoteHygieneAssessment:
    """Reject Unix-epoch and out-of-study/out-of-session quote timestamps.

    Checked in order of specificity and returned on first match -- a quote
    with an epoch-default timestamp reveals nothing about study or session
    bounds, and a quote outside the study window has no meaningful session
    to check. The compared instant is the timestamp's own UTC moment, not
    a naive date string: NSE quotes with no recent trade come back from the
    provider as literal Unix-epoch zero (verified in production evidence
    as ``1970-01-01T05:30:00+05:30``, i.e. epoch zero rendered in IST), and
    comparing the UTC instant is correct regardless of which timezone a
    future provider renders that same sentinel in.
    """

    if quote.ts.astimezone(timezone.utc) == _UNIX_EPOCH_UTC:
        return QuoteHygieneAssessment(
            instrument_id=quote.instrument_id,
            ts=quote.ts,
            admitted=False,
            reasons=(QuoteHygieneExclusionReason.EPOCH_DEFAULT_TIMESTAMP,),
        )
    local_ts = quote.ts.astimezone(market_timezone)
    local_date = local_ts.date()
    if local_date < study_start or local_date > study_end:
        return QuoteHygieneAssessment(
            instrument_id=quote.instrument_id,
            ts=quote.ts,
            admitted=False,
            reasons=(QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_STUDY_BOUNDS,),
        )
    if not is_trading_session or session_open is None or session_close is None:
        return QuoteHygieneAssessment(
            instrument_id=quote.instrument_id,
            ts=quote.ts,
            admitted=False,
            reasons=(QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS,),
        )
    local_time = local_ts.time()
    if not (session_open <= local_time <= session_close):
        return QuoteHygieneAssessment(
            instrument_id=quote.instrument_id,
            ts=quote.ts,
            admitted=False,
            reasons=(QuoteHygieneExclusionReason.TIMESTAMP_OUTSIDE_SESSION_BOUNDS,),
        )
    return QuoteHygieneAssessment(instrument_id=quote.instrument_id, ts=quote.ts, admitted=True)


@dataclass(frozen=True, slots=True)
class InstrumentListingSnapshot:
    """A frozen (listed_date, delisted_date) pair, captured at manifest-build
    time so replay never depends on the live, mutable ``instruments`` table."""

    instrument_id: str
    listed_date: date | None
    delisted_date: date | None


@dataclass(frozen=True, slots=True)
class CohortAdmissionManifest:
    """Immutable EM-1r4 evidence: cohort admission counts plus quote-hygiene
    counts and full rejected-quote evidence, over a frozen study window.

    Admitted symbol-days and admitted quotes are reported as counts plus a
    deterministic digest of the full computed set, not itemised in full --
    at survivor-cohort scale (hundreds of instruments times hundreds of
    sessions, hundreds of thousands of quotes) an itemised list of every
    admitted row would bloat the manifest without adding evidence beyond
    what the digest already proves reproducibly. Rejected quotes ARE
    itemised in full: they are the actual deliverable of the quote-hygiene
    gate, and are small enough (bounded by real data-quality defects, not
    by dataset size) to record completely.
    """

    study_start: date
    study_end: date
    cohort: SurvivorCohort
    listing_snapshot: tuple[InstrumentListingSnapshot, ...]
    symbol_day_total: int
    symbol_day_admitted: int
    symbol_day_exclusion_counts: dict[str, int]
    symbol_day_admission_digest: str
    quote_snapshot_artifact: str
    quote_snapshot_sha256: str
    quote_total: int
    quote_admitted: int
    quote_exclusion_counts: dict[str, int]
    quote_rejections: tuple[QuoteHygieneAssessment, ...]
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.study_start > self.study_end:
            raise ValueError("study_start cannot be after study_end")
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError("unsupported cohort-admission contract")
        if self.symbol_day_admitted > self.symbol_day_total:
            raise ValueError("symbol_day_admitted cannot exceed symbol_day_total")
        if self.quote_admitted > self.quote_total:
            raise ValueError("quote_admitted cannot exceed quote_total")
        if len(self.quote_rejections) != self.quote_total - self.quote_admitted:
            raise ValueError("quote_rejections count must equal quote_total - quote_admitted")
        listing_ids = tuple(item.instrument_id for item in self.listing_snapshot)
        if listing_ids != tuple(sorted(set(listing_ids))):
            raise ValueError("listing_snapshot instrument_ids must be unique and sorted")

    @property
    def replay_id(self) -> str:
        """Identify equivalent evidence from the fields that fully determine
        it -- unlike EM-1r2's manifest, no retrieval timestamp exists here
        to exclude, since EM-1r4 introduces no new external evidence."""

        return _digest(
            {
                "study_start": self.study_start,
                "study_end": self.study_end,
                "cohort": self.cohort,
                "listing_snapshot": self.listing_snapshot,
                "symbol_day_total": self.symbol_day_total,
                "symbol_day_admitted": self.symbol_day_admitted,
                "symbol_day_exclusion_counts": self.symbol_day_exclusion_counts,
                "symbol_day_admission_digest": self.symbol_day_admission_digest,
                "quote_snapshot_sha256": self.quote_snapshot_sha256,
                "quote_total": self.quote_total,
                "quote_admitted": self.quote_admitted,
                "quote_exclusion_counts": self.quote_exclusion_counts,
                "quote_rejections": self.quote_rejections,
                "contract_version": self.contract_version,
            }
        )

    @property
    def manifest_id(self) -> str:
        return f"em1r4-{self.replay_id[:24]}"

    @property
    def symbol_day_exclusion_rate(self) -> float:
        if self.symbol_day_total == 0:
            return 0.0
        return (self.symbol_day_total - self.symbol_day_admitted) / self.symbol_day_total

    @property
    def quote_exclusion_rate(self) -> float:
        if self.quote_total == 0:
            return 0.0
        return (self.quote_total - self.quote_admitted) / self.quote_total

    def to_dict(self) -> dict[str, Any]:
        payload = _jsonable(asdict(self))
        payload.update(
            manifest_id=self.manifest_id,
            replay_id=self.replay_id,
            symbol_day_exclusion_rate=self.symbol_day_exclusion_rate,
            quote_exclusion_rate=self.quote_exclusion_rate,
        )
        return payload


def write_immutable_manifest(directory: Path, manifest: CohortAdmissionManifest) -> Path:
    """Persist canonical JSON atomically and never overwrite conflicting evidence."""

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{manifest.manifest_id}.json"
    payload = json.dumps(manifest.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"manifest conflict: {target}")
        return target
    fd, temporary = tempfile.mkstemp(prefix=".em1r4-", dir=directory)
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


def write_immutable_payload(directory: Path, digest: str, payload: bytes) -> Path:
    """Content-addressed atomic write, matching EM-1r3's raw/normalized artifacts."""

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{digest}.json"
    if target.exists():
        if target.read_bytes() != payload:
            raise FileExistsError(f"artifact conflict: {target}")
        return target
    fd, temporary = tempfile.mkstemp(prefix=".em1r4-", dir=directory)
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


def cohort_admission_manifest_from_payload(payload: bytes) -> CohortAdmissionManifest:
    """Load and verify an immutable EM-1r4 manifest (mirrors EM-1r3's
    ``intraday_manifest_from_payload``: reconstruct, then confirm the
    recomputed identity matches what was persisted)."""

    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise ValueError("cohort admission manifest must be a JSON object")
    cohort_dict = decoded["cohort"]
    cohort = SurvivorCohort(
        name=str(cohort_dict["name"]),
        universe_name=str(cohort_dict["universe_name"]),
        resolution_date=date.fromisoformat(str(cohort_dict["resolution_date"])),
        instrument_ids=tuple(str(item) for item in cohort_dict["instrument_ids"]),
        group_effective_dates=tuple(
            (str(name), date.fromisoformat(str(iso)))
            for name, iso in cohort_dict["group_effective_dates"]
        ),
        limitation=str(cohort_dict["limitation"]),
    )
    listing_snapshot = tuple(
        InstrumentListingSnapshot(
            instrument_id=str(item["instrument_id"]),
            listed_date=date.fromisoformat(str(item["listed_date"])) if item["listed_date"] else None,
            delisted_date=(
                date.fromisoformat(str(item["delisted_date"])) if item["delisted_date"] else None
            ),
        )
        for item in decoded["listing_snapshot"]
    )
    quote_rejections = tuple(
        QuoteHygieneAssessment(
            instrument_id=str(item["instrument_id"]),
            ts=datetime.fromisoformat(str(item["ts"])),
            admitted=bool(item["admitted"]),
            reasons=tuple(QuoteHygieneExclusionReason(r) for r in item["reasons"]),
        )
        for item in decoded["quote_rejections"]
    )
    manifest = CohortAdmissionManifest(
        study_start=date.fromisoformat(str(decoded["study_start"])),
        study_end=date.fromisoformat(str(decoded["study_end"])),
        cohort=cohort,
        listing_snapshot=listing_snapshot,
        symbol_day_total=int(decoded["symbol_day_total"]),
        symbol_day_admitted=int(decoded["symbol_day_admitted"]),
        symbol_day_exclusion_counts=dict(decoded["symbol_day_exclusion_counts"]),
        symbol_day_admission_digest=str(decoded["symbol_day_admission_digest"]),
        quote_snapshot_artifact=str(decoded["quote_snapshot_artifact"]),
        quote_snapshot_sha256=str(decoded["quote_snapshot_sha256"]),
        quote_total=int(decoded["quote_total"]),
        quote_admitted=int(decoded["quote_admitted"]),
        quote_exclusion_counts=dict(decoded["quote_exclusion_counts"]),
        quote_rejections=quote_rejections,
        contract_version=str(decoded["contract_version"]),
    )
    if decoded.get("replay_id") != manifest.replay_id:
        raise ValueError("cohort admission manifest replay_id mismatch")
    if decoded.get("manifest_id") != manifest.manifest_id:
        raise ValueError("cohort admission manifest_id mismatch")
    return manifest


def canonical_quote_payload(quotes: tuple[Quote, ...]) -> bytes:
    """Deterministic JSON bytes for a frozen quote snapshot (content-addressed)."""

    rows = [
        {
            "instrument_id": q.instrument_id,
            "ts": q.ts.isoformat(),
            "last_price": str(q.last_price),
            "volume": q.volume,
            "source": q.source,
        }
        for q in sorted(quotes, key=lambda q: (q.instrument_id, q.ts.isoformat()))
    ]
    return (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def quotes_from_payload(payload: bytes) -> tuple[Quote, ...]:
    from decimal import Decimal

    rows = json.loads(payload.decode("utf-8"))
    return tuple(
        Quote(
            instrument_id=row["instrument_id"],
            ts=datetime.fromisoformat(row["ts"]),
            last_price=Decimal(row["last_price"]),
            volume=row["volume"],
            source=row["source"],
        )
        for row in rows
    )


def instrument_listing_snapshot(instruments: tuple[Instrument, ...]) -> tuple[InstrumentListingSnapshot, ...]:
    return tuple(
        sorted(
            (
                InstrumentListingSnapshot(
                    instrument_id=instrument.instrument_id,
                    listed_date=instrument.listed_date,
                    delisted_date=instrument.delisted_date,
                )
                for instrument in instruments
            ),
            key=lambda item: item.instrument_id,
        )
    )


def symbol_day_admission_digest(admissions: tuple[SymbolDayAdmission, ...]) -> str:
    """Deterministic fingerprint of a full admission set, for replay proof
    without inlining every row (see CohortAdmissionManifest's own note)."""

    rows = sorted(
        (
            {
                "instrument_id": a.instrument_id,
                "session_date": a.session_date.isoformat(),
                "admitted": a.admitted,
                "reasons": [r.value for r in a.reasons],
            }
            for a in admissions
        ),
        key=lambda row: (row["instrument_id"], row["session_date"]),
    )
    return _digest(rows)


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
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
