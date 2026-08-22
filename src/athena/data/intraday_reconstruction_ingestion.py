"""Data-owned acquisition and replay orchestration for EM-1r3."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.data.validation.calendar_expectations import expected_intraday_opens
from athena.domain.enums import SessionType, Timeframe
from athena.domain.interfaces import MarketDataProvider
from athena.explosive_move.corporate_action_coverage import SurvivorCohort
from athena.explosive_move.intraday_reconstruction import (
    IntradayReconstructionManifest,
    NormalizedArtifact,
    SourceCapture,
    candles_from_payload,
    canonical_candle_payload,
    intraday_manifest_from_payload,
    reconstruct_regular_session,
    write_immutable_manifest,
    write_immutable_payload,
)


@dataclass(frozen=True, slots=True)
class IntradayReconstructionResult:
    manifest: IntradayReconstructionManifest
    manifest_path: Path
    replay_verified: bool


class IntradayReconstructionIngestionService:
    """Capture authoritative 5-minute rows without mutating canonical candles."""

    def __init__(
        self,
        *,
        calendar: CalendarEngine,
        evidence_root: Path,
        timezone_name: str,
        provider: MarketDataProvider | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._calendar = calendar
        self._evidence_root = evidence_root.resolve()
        self._timezone = ZoneInfo(timezone_name)
        self._clock = clock or (lambda: datetime.now(tz=self._timezone))

    def capture(
        self,
        *,
        cohort: SurvivorCohort,
        study_start: date,
        study_end: date,
    ) -> IntradayReconstructionResult:
        if self._provider is None:
            raise ValueError("capture requires a market-data provider")
        if study_start > study_end:
            raise ValueError("study_start cannot be after study_end")
        sessions = self._regular_sessions(study_start, study_end)
        if not sessions:
            raise ValueError("study range contains no regular exchange sessions")
        captured_at = self._clock()
        if captured_at.tzinfo is None:
            raise ValueError("capture clock must return a timezone-aware timestamp")

        captures: list[SourceCapture] = []
        records = []
        admitted_by_instrument = defaultdict(list)
        for instrument_id in cohort.instrument_ids:
            for session_date, expected in sessions:
                rows = ()
                retrieval_error = None
                try:
                    rows = tuple(
                        self._provider.intraday_candles(
                            instrument_id,
                            Timeframe.M5,
                            expected[0],
                            expected[-1],
                        )
                    )
                except Exception as exc:  # Provider boundary must fail closed.
                    retrieval_error = f"{type(exc).__name__}: {exc}"
                payload = canonical_candle_payload(rows)
                digest = hashlib.sha256(payload).hexdigest()
                raw_path = write_immutable_payload(
                    self._evidence_root / "intraday-raw", digest, payload
                )
                captures.append(
                    SourceCapture(
                        instrument_id=instrument_id,
                        session_date=session_date,
                        requested_start=expected[0],
                        requested_end=expected[-1],
                        captured_at=captured_at,
                        provider=self._provider.name,
                        artifact=self._relative(raw_path),
                        payload_sha256=digest,
                        row_count=len(rows),
                        retrieval_error=retrieval_error,
                    )
                )
                reconstruction = reconstruct_regular_session(
                    instrument_id=instrument_id,
                    session_date=session_date,
                    expected_slots=expected,
                    source_rows=rows,
                    retrieval_error=retrieval_error,
                )
                records.append(reconstruction.record)
                admitted_by_instrument[instrument_id].extend(reconstruction.candles)

        artifacts = []
        for instrument_id in cohort.instrument_ids:
            candles = tuple(admitted_by_instrument[instrument_id])
            payload = canonical_candle_payload(candles)
            digest = hashlib.sha256(payload).hexdigest()
            path = write_immutable_payload(
                self._evidence_root / "intraday-normalized", digest, payload
            )
            artifacts.append(
                NormalizedArtifact(
                    instrument_id=instrument_id,
                    artifact=self._relative(path),
                    payload_sha256=digest,
                    admitted_sessions=sum(
                        record.instrument_id == instrument_id
                        and record.status == "ADMITTED"
                        for record in records
                    ),
                    row_count=len(candles),
                )
            )

        manifest = IntradayReconstructionManifest(
            study_start=study_start,
            study_end=study_end,
            cohort_name=cohort.name,
            cohort_id=cohort.cohort_id,
            cohort_instrument_ids=cohort.instrument_ids,
            population_basis="SURVIVOR_COHORT",
            population_limitation=cohort.limitation,
            source_captures=tuple(captures),
            normalized_artifacts=tuple(artifacts),
            sessions=tuple(records),
        )
        manifest_path = write_immutable_manifest(
            self._evidence_root / "intraday-manifests", manifest
        )
        return IntradayReconstructionResult(manifest, manifest_path, False)

    def replay(self, manifest_path: Path) -> IntradayReconstructionResult:
        manifest = intraday_manifest_from_payload(manifest_path.read_bytes())
        rebuilt_records = []
        admitted_by_instrument = defaultdict(list)
        for capture in manifest.source_captures:
            payload = self._read_verified(capture.artifact, capture.payload_sha256)
            rows = candles_from_payload(payload)
            if len(rows) != capture.row_count:
                raise ValueError("source artifact row count does not match manifest")
            expected = self._expected_slots(capture.session_date)
            reconstruction = reconstruct_regular_session(
                instrument_id=capture.instrument_id,
                session_date=capture.session_date,
                expected_slots=expected,
                source_rows=rows,
                retrieval_error=capture.retrieval_error,
            )
            rebuilt_records.append(reconstruction.record)
            admitted_by_instrument[capture.instrument_id].extend(reconstruction.candles)

        for artifact in manifest.normalized_artifacts:
            expected_payload = canonical_candle_payload(
                admitted_by_instrument[artifact.instrument_id]
            )
            actual_payload = self._read_verified(
                artifact.artifact, artifact.payload_sha256
            )
            if actual_payload != expected_payload:
                raise ValueError("normalized artifact does not match deterministic replay")
            if len(candles_from_payload(actual_payload)) != artifact.row_count:
                raise ValueError("normalized artifact row count does not match manifest")
        if tuple(rebuilt_records) != manifest.sessions:
            raise ValueError("replayed session records do not match manifest")
        return IntradayReconstructionResult(manifest, manifest_path, True)

    #: A configured full-shaped special session (e.g. a Saturday Budget-day
    #: live session) is exchange-confirmed and has real open/close boundaries
    #: -- treated exactly like a NORMAL day for capture purposes. A session
    #: the calendar cannot faithfully represent (KNOWN_UNSUPPORTED_SPECIAL_SESSION,
    #: e.g. a split-window DR drill) is deliberately excluded, not guessed at.
    _CAPTURABLE_SESSION_TYPES = (SessionType.NORMAL, SessionType.SPECIAL)

    def _regular_sessions(
        self, start: date, end: date
    ) -> tuple[tuple[date, tuple[datetime, ...]], ...]:
        result = []
        cursor = start
        while cursor <= end:
            if self._calendar.context_for(cursor).session_type in self._CAPTURABLE_SESSION_TYPES:
                result.append((cursor, self._expected_slots(cursor)))
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return tuple(result)

    def _expected_slots(self, session_date: date) -> tuple[datetime, ...]:
        slots = tuple(
            expected_intraday_opens(
                self._calendar, session_date, 5, self._timezone
            )
        )
        if not slots:
            raise ValueError(f"regular session {session_date} has no configured slots")
        return slots

    def _relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self._evidence_root))

    def _read_verified(self, artifact: str, expected_digest: str) -> bytes:
        path = (self._evidence_root / artifact).resolve()
        try:
            path.relative_to(self._evidence_root)
        except ValueError as exc:
            raise ValueError("artifact path escapes evidence root") from exc
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_digest:
            raise ValueError(f"artifact digest mismatch: {artifact}")
        return payload
