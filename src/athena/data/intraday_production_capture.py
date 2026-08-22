"""Resumable, checkpointed production-scale wrapper around EM-1r3's capture.

Owner-authorized (2026-08-22): a real intraday capture run across the full
survivor cohort and study window, using the live Kite API. This module adds
exactly what that authorization requires on top of the already-approved,
UNMODIFIED EM-1r3 contract (``intraday_reconstruction.py`` and
``intraday_reconstruction_ingestion.py``): resumability, retry/backoff for
transient provider failures (via ``RetryingMarketDataProvider``), and a
production-capture-specific summary report. It does not change EM-1r3's
admission criteria, session reconstruction, or manifest schema in any way --
each batch's manifest is a genuine, unmodified ``IntradayReconstructionManifest``,
independently valid and replayable exactly like EM-1r3's own fixture manifest.

Resumption granularity is per-instrument, not per-session: EM-1r3's own
``capture()`` processes one cohort (a set of instruments) against the full
study window in a single call and returns one manifest for that call. This
runner therefore batches the full cohort into small sub-cohorts, captures
one batch at a time, and checkpoints which instruments are done after each
batch succeeds -- a restart skips completed instruments and resumes with
the first incomplete batch, never re-issuing real API calls for
already-captured evidence.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from athena.data.intraday_reconstruction_ingestion import (
    IntradayReconstructionIngestionService,
)
from athena.data.retrying_provider import RetryingMarketDataProvider
from athena.explosive_move.corporate_action_coverage import SurvivorCohort
from athena.explosive_move.intraday_reconstruction import (
    IntradayReconstructionManifest,
    SessionExclusionReason,
    intraday_manifest_from_payload,
)


@dataclass
class ProductionCaptureCheckpoint:
    """Mutable, persisted progress for one production capture campaign.

    Identified by ``capture_run_id`` -- a value the caller supplies once
    (e.g. a fixed string for "the EM-1r3 production run"), not derived,
    since it must stay stable across every resumption regardless of what
    has or hasn't completed yet.
    """

    capture_run_id: str
    cohort_name: str
    cohort_id: str
    universe_name: str
    study_start: str
    study_end: str
    started_at: str
    completed_instrument_ids: list[str] = field(default_factory=list)
    batch_manifest_paths: list[str] = field(default_factory=list)
    finished_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> ProductionCaptureCheckpoint:
        return cls(**payload)


#: The diagnostic (2026-08-22) found this as the first missing slot in every
#: affected session -- a genuinely reproducible marker, not a guess.
_TRUNCATION_MARKER_TIME = "15:15:00"
_TRUNCATION_DETAIL_PATTERN = re.compile(
    r"missing exact slot (\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})"
)


@dataclass(frozen=True, slots=True)
class RecentHistoryTruncationObservation:
    """A neutral, evidence-only record of a real, reproducible pattern found
    during diagnostic investigation on 2026-08-22: some recent sessions'
    Kite 5-minute data ends at 15:10 (72 of the 75 expected slots) instead
    of the full session through 15:25.

    This is an OBSERVATION, not a claim about Kite's internal behavior.
    Confirmed by direct testing: (1) NOT an ATHENA request-construction
    defect -- widening the raw ``to`` boundary all the way to end-of-day
    returned the identical 72 rows every time; (2) resolves for sessions
    older than roughly 2-3 weeks at the time of the diagnostic, tested
    across a 2-instrument sample back to 1096 days. "Delayed provider
    backfill" is offered only as ``hypothesis`` below -- never asserted as
    Kite's documented or confirmed behavior, since no such documentation
    was consulted or exists in this repository.
    """

    label: str = "RECENT_PROVIDER_HISTORY_TRUNCATION"
    hypothesis: str = (
        "Unverified hypothesis, not confirmed by Kite documentation: recent "
        "sessions' 5-minute historical data may lag full backfill into "
        "Kite's historical series by roughly 2-3 weeks. Treat as an "
        "observed pattern only."
    )
    expected_slots_per_session: int = 75
    observed_slots_in_affected_sessions: int = 72
    final_observed_candle_time: str = "15:10:00"
    raw_response_confirmed: bool = True
    request_widening_has_no_effect: bool = True
    affected_session_count: int = 0
    affected_instrument_ids: tuple[str, ...] = ()
    earliest_affected_date: str | None = None
    latest_affected_date: str | None = None
    consistent_across_symbols: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProductionCaptureSummary:
    """Aggregate evidence across every batch manifest in one campaign --
    exactly the fields the owner's authorization required, computed from
    the batches' own already-immutable, already-validated manifests."""

    capture_run_id: str
    cohort_name: str
    cohort_id: str
    study_start: date
    study_end: date
    expected_symbol_count: int
    symbols_attempted: tuple[str, ...]
    expected_sessions: int
    requested_sessions: int
    successfully_retrieved_sessions: int
    admitted_sessions: int
    partial_sessions: int
    rejected_sessions: int
    missing_sessions: int
    repair_counts: dict[str, int]
    provider_failure_counts: dict[str, int]
    recent_history_truncation: RecentHistoryTruncationObservation
    retries_performed: int
    kite_requests_issued: int
    permanent_failures: int
    retry_exhausted_failures: int
    started_at: datetime
    finished_at: datetime | None
    resumption_count: int

    @property
    def admitted_percent(self) -> float:
        return 0.0 if self.expected_sessions == 0 else 100.0 * self.admitted_sessions / self.expected_sessions

    @property
    def excluded_percent(self) -> float:
        return 100.0 - self.admitted_percent if self.expected_sessions else 0.0

    @property
    def recent_truncation_percent_of_population(self) -> float:
        if self.expected_sessions == 0:
            return 0.0
        return 100.0 * self.recent_history_truncation.affected_session_count / self.expected_sessions
    batch_manifest_paths: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["study_start"] = self.study_start.isoformat()
        payload["study_end"] = self.study_end.isoformat()
        payload["started_at"] = self.started_at.isoformat()
        payload["finished_at"] = self.finished_at.isoformat() if self.finished_at else None
        return payload


_HTTP_STATUS = re.compile(r"kite HTTP (\d)\d\d")


def _is_truncation_marker(exclusion_detail: str | None) -> bool:
    """True when a MISSING_SLOT exclusion's first-missing-slot time matches
    the exact marker the 2026-08-22 diagnostic found in every affected
    session (the first gap always at or after 15:15) -- distinguishing this
    specific, reproducible pattern from an unrelated mid-session data gap,
    which this function deliberately does NOT classify as truncation."""

    if not exclusion_detail:
        return False
    match = _TRUNCATION_DETAIL_PATTERN.search(exclusion_detail)
    if not match:
        return False
    return match.group(2) >= _TRUNCATION_MARKER_TIME


def _classify_failure_detail(detail: str) -> str:
    """Every real retrieval failure arrives as ``ProviderError`` regardless of
    cause (network timeout, HTTP status, unresolved instrument, ...), so
    grouping by exception type alone would collapse every failure into one
    useless "ProviderError" bucket. This pulls out a coarser, meaningful
    category instead."""

    if "kite network failure" in detail:
        return "network_failure"
    match = _HTTP_STATUS.search(detail)
    if match:
        return f"http_{match.group(1)}xx"
    return "other"


class ProductionIntradayCaptureRunner:
    """Batches a survivor cohort into resumable, checkpointed capture calls."""

    def __init__(
        self,
        *,
        service: IntradayReconstructionIngestionService,
        provider_stats: RetryingMarketDataProvider,
        checkpoint_path: Path,
        evidence_root: Path,
        batch_size: int = 5,
    ) -> None:
        self._service = service
        self._provider_stats = provider_stats
        self._checkpoint_path = checkpoint_path
        self._evidence_root = evidence_root.resolve()
        self._batch_size = batch_size

    def run(
        self,
        *,
        capture_run_id: str,
        cohort: SurvivorCohort,
        study_start: date,
        study_end: date,
        expected_session_count: int,
        on_batch_complete=None,
    ) -> ProductionCaptureSummary:
        checkpoint = self._load_or_init(capture_run_id, cohort, study_start, study_end)
        resumption_count = 1 if checkpoint.batch_manifest_paths else 0
        remaining = [
            instrument_id
            for instrument_id in cohort.instrument_ids
            if instrument_id not in checkpoint.completed_instrument_ids
        ]
        for start in range(0, len(remaining), self._batch_size):
            batch_ids = tuple(remaining[start : start + self._batch_size])
            batch_cohort = SurvivorCohort(
                name=cohort.name,
                universe_name=cohort.universe_name,
                resolution_date=cohort.resolution_date,
                instrument_ids=batch_ids,
                group_effective_dates=cohort.group_effective_dates,
                limitation=cohort.limitation,
            )
            result = self._service.capture(
                cohort=batch_cohort, study_start=study_start, study_end=study_end
            )
            checkpoint.completed_instrument_ids.extend(batch_ids)
            checkpoint.batch_manifest_paths.append(
                str(result.manifest_path.resolve().relative_to(self._evidence_root))
            )
            self._save(checkpoint)
            if on_batch_complete is not None:
                on_batch_complete(batch_ids, checkpoint)

        checkpoint.finished_at = datetime.now(tz=timezone.utc).isoformat()
        self._save(checkpoint)
        return self._summarize(checkpoint, cohort, expected_session_count, resumption_count)

    def _load_or_init(
        self, capture_run_id: str, cohort: SurvivorCohort, study_start: date, study_end: date
    ) -> ProductionCaptureCheckpoint:
        if self._checkpoint_path.exists():
            existing = ProductionCaptureCheckpoint.from_dict(
                json.loads(self._checkpoint_path.read_text(encoding="utf-8"))
            )
            if existing.capture_run_id != capture_run_id or existing.cohort_id != cohort.cohort_id:
                raise ValueError(
                    "checkpoint file belongs to a different capture_run_id/cohort -- "
                    "use a fresh checkpoint path for a genuinely new campaign"
                )
            return existing
        return ProductionCaptureCheckpoint(
            capture_run_id=capture_run_id,
            cohort_name=cohort.name,
            cohort_id=cohort.cohort_id,
            universe_name=cohort.universe_name,
            study_start=study_start.isoformat(),
            study_end=study_end.isoformat(),
            started_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _save(self, checkpoint: ProductionCaptureCheckpoint) -> None:
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(checkpoint.to_dict(), indent=2, sort_keys=True) + "\n"
        fd, temporary = tempfile.mkstemp(
            prefix=".checkpoint-", dir=self._checkpoint_path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._checkpoint_path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def _summarize(
        self,
        checkpoint: ProductionCaptureCheckpoint,
        cohort: SurvivorCohort,
        expected_session_count: int,
        resumption_count: int,
    ) -> ProductionCaptureSummary:
        manifests: list[IntradayReconstructionManifest] = []
        for relative_path in checkpoint.batch_manifest_paths:
            payload = (self._evidence_root / relative_path).read_bytes()
            manifests.append(intraday_manifest_from_payload(payload))

        requested = sum(len(m.source_captures) for m in manifests)
        retrieved = sum(
            1 for m in manifests for c in m.source_captures if c.retrieval_error is None
        )
        admitted = sum(m.admitted_session_count for m in manifests)
        repair_counter: Counter[str] = Counter()
        for m in manifests:
            repair_counter.update(m.repair_counts)

        partial = 0
        rejected = 0
        missing = 0
        provider_failure_counter: Counter[str] = Counter()
        truncation_dates: set[str] = set()
        truncation_instrument_ids: set[str] = set()
        truncation_count = 0
        for m in manifests:
            for record in m.sessions:
                if record.status != "EXCLUDED":
                    continue
                if record.exclusion_reason is SessionExclusionReason.RETRIEVAL_FAILED:
                    missing += 1
                    if record.exclusion_detail:
                        provider_failure_counter[_classify_failure_detail(record.exclusion_detail)] += 1
                elif record.exclusion_reason is SessionExclusionReason.MISSING_SLOT:
                    partial += 1
                    if _is_truncation_marker(record.exclusion_detail):
                        truncation_count += 1
                        truncation_dates.add(record.session_date.isoformat())
                        truncation_instrument_ids.add(record.instrument_id)
                else:
                    rejected += 1

        truncation = RecentHistoryTruncationObservation(
            affected_session_count=truncation_count,
            affected_instrument_ids=tuple(sorted(truncation_instrument_ids)),
            earliest_affected_date=min(truncation_dates) if truncation_dates else None,
            latest_affected_date=max(truncation_dates) if truncation_dates else None,
            consistent_across_symbols=(
                len(truncation_instrument_ids) > 1 if truncation_dates else None
            ),
        )

        return ProductionCaptureSummary(
            capture_run_id=checkpoint.capture_run_id,
            cohort_name=cohort.name,
            cohort_id=cohort.cohort_id,
            study_start=date.fromisoformat(checkpoint.study_start),
            study_end=date.fromisoformat(checkpoint.study_end),
            expected_symbol_count=len(cohort.instrument_ids),
            symbols_attempted=tuple(checkpoint.completed_instrument_ids),
            expected_sessions=expected_session_count,
            requested_sessions=requested,
            successfully_retrieved_sessions=retrieved,
            admitted_sessions=admitted,
            partial_sessions=partial,
            rejected_sessions=rejected,
            missing_sessions=missing,
            repair_counts=dict(repair_counter),
            provider_failure_counts=dict(provider_failure_counter),
            recent_history_truncation=truncation,
            retries_performed=self._provider_stats.stats.retries_performed,
            kite_requests_issued=self._provider_stats.stats.requests_attempted,
            permanent_failures=self._provider_stats.stats.permanent_failures,
            retry_exhausted_failures=self._provider_stats.stats.retry_exhausted_failures,
            started_at=datetime.fromisoformat(checkpoint.started_at),
            finished_at=(
                datetime.fromisoformat(checkpoint.finished_at) if checkpoint.finished_at else None
            ),
            resumption_count=resumption_count,
            batch_manifest_paths=tuple(checkpoint.batch_manifest_paths),
        )
