"""Data-owned orchestration for EM-1r4 cohort admission and quote hygiene.

No provider and no network call exists anywhere in this module -- unlike
EM-1r2/EM-1r3, EM-1r4 introduces no new external evidence. It reads
canonical persisted records through the existing repository boundary
(``list_instruments``, ``list_resolved_universe``, ``get_quotes``) and
resolves calendar facts through the existing ``CalendarEngine``, then
hands plain data down into the pure ``athena.explosive_move.cohort_admission``
contracts. Calendar resolution stays here, in orchestration, exactly as
EM-1r3's ``IntradayReconstructionIngestionService`` already separates it
from its own pure reconstruction module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.data.store.repository import SqliteRepository
from athena.domain.enums import SessionType
from athena.domain.market import Quote
from athena.errors import CalendarError
from athena.explosive_move.cohort_admission import (
    CohortAdmissionExclusionReason,
    CohortAdmissionManifest,
    QuoteHygieneExclusionReason,
    assess_quote_timestamp_hygiene,
    assess_symbol_day_cohort_admission,
    canonical_quote_payload,
    cohort_admission_manifest_from_payload,
    instrument_listing_snapshot,
    quotes_from_payload,
    symbol_day_admission_digest,
    write_immutable_manifest,
    write_immutable_payload,
)
from athena.explosive_move.corporate_action_coverage import build_survivor_cohort


@dataclass(frozen=True, slots=True)
class CohortAdmissionResult:
    manifest: CohortAdmissionManifest
    manifest_path: Path
    replay_verified: bool


class CohortAdmissionIngestionService:
    """Apply the frozen survivor-cohort contract and quote-timestamp hygiene."""

    def __init__(
        self,
        *,
        repository: SqliteRepository,
        calendar: CalendarEngine,
        evidence_root: Path,
        timezone_name: str,
    ) -> None:
        self._repository = repository
        self._calendar = calendar
        self._evidence_root = evidence_root.resolve()
        self._timezone = ZoneInfo(timezone_name)

    def run(
        self,
        *,
        universe_name: str,
        cohort_resolution_date: date,
        study_start: date,
        study_end: date,
    ) -> CohortAdmissionResult:
        if study_start > study_end:
            raise ValueError("study_start cannot be after study_end")

        instruments = tuple(self._repository.list_instruments())
        instrument_ids = tuple(self._repository.list_resolved_universe(universe_name))
        known_ids = {instrument.instrument_id for instrument in instruments}
        unresolved = sorted(set(instrument_ids) - known_ids)
        if unresolved:
            raise ValueError(
                f"resolved universe contains {len(unresolved)} unknown instrument ids"
            )
        cohort = build_survivor_cohort(
            universe_name=universe_name,
            resolution_date=cohort_resolution_date,
            instrument_ids=instrument_ids,
            group_effective_dates=((universe_name, cohort_resolution_date),),
        )
        by_id = {instrument.instrument_id: instrument for instrument in instruments}
        listing_snapshot = instrument_listing_snapshot(
            tuple(by_id[instrument_id] for instrument_id in cohort.instrument_ids)
        )

        sessions = self._regular_sessions(study_start, study_end)
        admissions = self._assess_admissions(cohort, listing_snapshot, sessions)
        symbol_day_exclusion_counts = _count_by_reason(
            (reason for a in admissions for reason in a.reasons), CohortAdmissionExclusionReason
        )

        quotes = tuple(
            quote
            for instrument_id in cohort.instrument_ids
            for quote in self._repository.get_quotes(instrument_id)
        )
        quote_payload = canonical_quote_payload(quotes)
        quote_digest = hashlib.sha256(quote_payload).hexdigest()
        quote_path = write_immutable_payload(
            self._evidence_root / "quote-snapshots", quote_digest, quote_payload
        )
        rejections = self._assess_quote_rejections(quotes, study_start, study_end)
        quote_exclusion_counts = _count_by_reason(
            (reason for a in rejections for reason in a.reasons), QuoteHygieneExclusionReason
        )

        manifest = CohortAdmissionManifest(
            study_start=study_start,
            study_end=study_end,
            cohort=cohort,
            listing_snapshot=listing_snapshot,
            symbol_day_total=len(admissions),
            symbol_day_admitted=sum(1 for a in admissions if a.admitted),
            symbol_day_exclusion_counts=symbol_day_exclusion_counts,
            symbol_day_admission_digest=symbol_day_admission_digest(admissions),
            quote_snapshot_artifact=str(quote_path.resolve().relative_to(self._evidence_root)),
            quote_snapshot_sha256=quote_digest,
            quote_total=len(quotes),
            quote_admitted=len(quotes) - len(rejections),
            quote_exclusion_counts=quote_exclusion_counts,
            quote_rejections=rejections,
        )
        manifest_path = write_immutable_manifest(self._evidence_root / "manifests", manifest)
        return CohortAdmissionResult(manifest, manifest_path, False)

    def replay(self, manifest_path: Path) -> CohortAdmissionResult:
        """Recompute from the manifest's own frozen inputs (cohort, listing
        snapshot, quote-snapshot artifact) and confirm identical evidence --
        never from the live, mutable canonical tables, which may have grown
        since the manifest was written."""

        manifest = cohort_admission_manifest_from_payload(manifest_path.read_bytes())
        sessions = self._regular_sessions(manifest.study_start, manifest.study_end)
        admissions = self._assess_admissions(manifest.cohort, manifest.listing_snapshot, sessions)
        if len(admissions) != manifest.symbol_day_total:
            raise ValueError("replayed symbol-day total does not match manifest")
        if symbol_day_admission_digest(admissions) != manifest.symbol_day_admission_digest:
            raise ValueError("replayed symbol-day admission digest does not match manifest")

        quote_artifact = (self._evidence_root / manifest.quote_snapshot_artifact).resolve()
        quote_artifact.relative_to(self._evidence_root)
        quote_payload = quote_artifact.read_bytes()
        if hashlib.sha256(quote_payload).hexdigest() != manifest.quote_snapshot_sha256:
            raise ValueError("quote snapshot artifact digest mismatch")
        quotes = quotes_from_payload(quote_payload)
        if len(quotes) != manifest.quote_total:
            raise ValueError("replayed quote total does not match manifest")
        rejections = self._assess_quote_rejections(quotes, manifest.study_start, manifest.study_end)
        if rejections != manifest.quote_rejections:
            raise ValueError("replayed quote rejections do not match manifest")

        return CohortAdmissionResult(manifest, manifest_path, True)

    def _assess_admissions(self, cohort, listing_snapshot, sessions):
        listing_by_id = {item.instrument_id: item for item in listing_snapshot}
        admissions = []
        for instrument_id in cohort.instrument_ids:
            listing = listing_by_id[instrument_id]
            for session_date in sessions:
                admissions.append(
                    assess_symbol_day_cohort_admission(
                        instrument_id=instrument_id,
                        session_date=session_date,
                        listed_date=listing.listed_date,
                        delisted_date=listing.delisted_date,
                        cohort=cohort,
                    )
                )
        return tuple(admissions)

    def _assess_quote_rejections(
        self, quotes: tuple[Quote, ...], study_start: date, study_end: date
    ) -> tuple:
        rejections = []
        for quote in quotes:
            local_date = quote.ts.astimezone(self._timezone).date()
            # The calendar engine fails loudly (CalendarError) for a year it
            # has no data for -- expected for genuinely bad data (a Unix-
            # epoch default lands on 1970, far outside any calendar's
            # coverage) and for any quote study bounds should already have
            # excluded on their own. Either way, "no calendar authority for
            # this date" is exactly the kind of uncertainty ADR-012 s6/s7
            # says to fail closed on, not crash the whole ingestion run over.
            try:
                context = self._calendar.context_for(local_date)
                is_trading_session = context.is_trading_session
                session_open = context.open_time
                session_close = context.close_time
            except CalendarError:
                is_trading_session = False
                session_open = None
                session_close = None
            assessment = assess_quote_timestamp_hygiene(
                quote,
                study_start=study_start,
                study_end=study_end,
                market_timezone=self._timezone,
                is_trading_session=is_trading_session,
                session_open=session_open,
                session_close=session_close,
            )
            if not assessment.admitted:
                rejections.append(assessment)
        return tuple(sorted(rejections, key=lambda a: (a.instrument_id, a.ts.isoformat())))

    def _regular_sessions(self, start: date, end: date) -> tuple[date, ...]:
        result = []
        cursor = start
        while cursor <= end:
            if self._calendar.context_for(cursor).session_type is SessionType.NORMAL:
                result.append(cursor)
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return tuple(result)


def _count_by_reason(reasons, reason_enum) -> dict[str, int]:
    counts = {reason.value: 0 for reason in reason_enum}
    for reason in reasons:
        counts[reason.value] += 1
    return counts
