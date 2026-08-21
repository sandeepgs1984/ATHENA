"""Narrow EM-1r2 materialization service for official corporate actions."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from athena.data.providers.nse_corporate_actions_provider import (
    RetrievedCorporateActionPayload,
)
from athena.data.store.repository import SqliteRepository
from athena.explosive_move.corporate_action_coverage import (
    CorporateActionCoverageManifest,
    RetrievalSlice,
    build_survivor_cohort,
    normalize_official_actions,
    write_immutable_manifest,
)


class CorporateActionProvider(Protocol):
    def retrieve(self, start: date, end: date) -> RetrievedCorporateActionPayload: ...


@dataclass(frozen=True, slots=True)
class CorporateActionIngestionResult:
    manifest: CorporateActionCoverageManifest
    manifest_path: Path
    inserted_actions: int


class CorporateActionIngestionService:
    """Capture official evidence, normalize it, and fail closed on coverage gaps."""

    def __init__(
        self,
        *,
        repository: SqliteRepository,
        provider: CorporateActionProvider,
        evidence_root: Path,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._evidence_root = evidence_root

    def run(
        self,
        *,
        study_start: date,
        study_end: date,
        universe_name: str,
        cohort_resolution_date: date,
    ) -> CorporateActionIngestionResult:
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

        rows = []
        exclusions = []
        slices = []
        for start, end in _monthly_intervals(study_start, study_end):
            retrieved = self._provider.retrieve(start, end)
            raw_path = _write_immutable_bytes(
                self._evidence_root / "raw",
                retrieved.parsed.payload_sha256,
                retrieved.body,
            )
            rows.extend(retrieved.parsed.rows)
            exclusions.extend(retrieved.parsed.exclusions)
            slices.append(
                RetrievalSlice(
                    requested_start=start,
                    requested_end=end,
                    retrieved_at=retrieved.retrieved_at,
                    source_url=retrieved.source_url,
                    payload_sha256=retrieved.parsed.payload_sha256,
                    raw_artifact=str(raw_path.relative_to(self._evidence_root)),
                    record_count=len(retrieved.parsed.rows) + len(retrieved.parsed.exclusions),
                    complete=retrieved.complete,
                    completeness_basis=retrieved.completeness_basis,
                )
            )

        actions, normalization_exclusions = normalize_official_actions(
            tuple(rows), instruments=instruments, cohort=cohort
        )
        exclusions.extend(normalization_exclusions)
        manifest = CorporateActionCoverageManifest(
            study_start=study_start,
            study_end=study_end,
            cohort=cohort,
            retrieval_slices=tuple(slices),
            actions=actions,
            exclusions=tuple(
                sorted(
                    exclusions,
                    key=lambda item: (
                        item.ex_date or date.min,
                        item.symbol,
                        item.source_record_id,
                        item.reason.value,
                    ),
                )
            ),
        )
        manifest_path = write_immutable_manifest(self._evidence_root / "manifests", manifest)
        inserted = (
            self._repository.add_corporate_actions(manifest.actions)
            if manifest.authoritative_for_research
            else 0
        )
        return CorporateActionIngestionResult(
            manifest=manifest,
            manifest_path=manifest_path,
            inserted_actions=inserted,
        )


def _monthly_intervals(start: date, end: date) -> tuple[tuple[date, date], ...]:
    intervals: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        next_month = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
        interval_end = min(end, next_month - timedelta(days=1))
        intervals.append((cursor, interval_end))
        cursor = interval_end + timedelta(days=1)
    return tuple(intervals)


def _write_immutable_bytes(directory: Path, digest: str, payload: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{digest}.json"
    if target.exists():
        if target.read_bytes() != payload:
            raise FileExistsError(f"raw evidence conflict: {target}")
        return target
    descriptor, temporary = tempfile.mkstemp(prefix=".em1r2-", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as handle:
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
