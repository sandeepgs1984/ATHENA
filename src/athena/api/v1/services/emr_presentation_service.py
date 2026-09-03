"""EM-6B: the thin service mapping EM-6A's read-only presentation
contract onto EM-6B's typed API response models.

This is the *only* file in the API layer that imports from
``athena.explosive_move`` -- the router below depends on this service
alone, never on ``athena.explosive_move.live.presentation`` directly,
and this service never imports anything from ``athena.decision``,
``athena.risk``, ``athena.portfolio``, ``athena.scoring``,
``athena.intraday``, or ``athena.darvax`` (ADR-012; mechanically
verified by ``tests/api/v1/test_emr_router.py``'s own isolation checks).

No business logic lives here beyond field mapping and the one-clock-per-
response discipline (Section 6 of the EM-6B authorization): the caller
(the router) captures a single ``request_as_of`` and passes it through
unchanged, so every field in one response is computed relative to the
same instant.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from athena.api.v1.dtos.emr import (
    EmrCandidateDTO,
    EmrCoverageDTO,
    EmrScanAgeDTO,
    EmrScanContextDTO,
    EmrTouch10RadarDTO,
)
from athena.explosive_move.live import presentation as emr_presentation


class EmrPresentationService:
    """Read-only. Owns exactly one responsibility: turn EM-6A's
    presentation contract into `EmrTouch10RadarDTO`, with the entire
    response scoped to one scan/run identity and one captured clock
    instant."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._db_path = db_path
        self._clock = clock or (lambda: datetime.now(tz=timezone.utc))

    def get_touch_10_radar(self, *, session_date: str | None = None) -> EmrTouch10RadarDTO:
        request_as_of = self._clock()
        snapshot = emr_presentation.build_touch_10_radar_snapshot(
            self._db_path, session_date=session_date,
        )

        if snapshot.scan is None:
            return EmrTouch10RadarDTO(
                label=snapshot.label,
                disclaimer="No completed EMR scan is available. The Experimental "
                           "radar displays persisted scanner output only.",
                scan=None, scan_age=None, touch_10=(), coverage=None,
            )

        scan_dto = EmrScanContextDTO(
            run_id=snapshot.scan.run_id, session_date=snapshot.scan.session_date,
            checkpoint=snapshot.scan.checkpoint, frozen_model_version=snapshot.scan.frozen_model_version,
            started_ts=snapshot.scan.started_ts, finished_ts=snapshot.scan.finished_ts,
            eligible_count=snapshot.scan.eligible_count, ineligible_count=snapshot.scan.ineligible_count,
        )
        freshness = emr_presentation.describe_scan_freshness(snapshot.scan, as_of=request_as_of)
        scan_age_dto = EmrScanAgeDTO(
            age_seconds=freshness.age_seconds, age_minutes=freshness.age_minutes, as_of=freshness.as_of,
        )
        candidate_dtos = tuple(
            EmrCandidateDTO(
                instrument_id=c.instrument_id, family=c.family, threshold_percent=c.threshold_percent,
                rank=c.rank, calibrated_probability=c.calibrated_probability,
                deterministic_score=c.deterministic_score, probability_language=c.probability_language,
                em4b_model_version=c.em4b_model_version, em4d_calibration_version=c.em4d_calibration_version,
                evidence_completeness_known=c.evidence_completeness_known,
                evidence_completeness_total=c.evidence_completeness_total,
                data_freshness=c.data_freshness, feasibility=c.feasibility,
                feasibility_reason=c.feasibility_reason, state=c.state, state_reason=c.state_reason,
                checkpoint_price=c.checkpoint_price, checkpoint_price_semantic=c.checkpoint_price_semantic,
            )
            for c in snapshot.touch_10
        )
        coverage_dto = None
        if snapshot.coverage is not None:
            coverage_dto = EmrCoverageDTO(
                family=snapshot.coverage.family, threshold_percent=snapshot.coverage.threshold_percent,
                evaluated_count=snapshot.coverage.evaluated_count, ranked_count=snapshot.coverage.ranked_count,
                unranked_count=snapshot.coverage.unranked_count,
                unranked_reason_counts=snapshot.coverage.unranked_reason_counts,
            )

        return EmrTouch10RadarDTO(
            label=snapshot.label,
            disclaimer="Research signal -- not a trade recommendation.",
            scan=scan_dto, scan_age=scan_age_dto, touch_10=candidate_dtos, coverage=coverage_dto,
        )
