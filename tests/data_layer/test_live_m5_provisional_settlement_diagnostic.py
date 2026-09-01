"""Track B live provisional-vs-settled M5 semantic diagnostic (Owner
authorization, 2026-08-28). No live Kite calls in any test -- capture is
exercised against a fake provider; comparison/classification are pure."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as time_of_day
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.live_m5_provisional_settlement_diagnostic import (
    TRACK_B_CHECKPOINT_SCHEDULE,
    DiagnosisOutcome,
    PreflightError,
    ProvisionalCapture,
    TrackBRunManifest,
    build_classification_report_skeleton,
    capture_provisional_m5,
    classify_diagnosis,
    compare_provisional_to_settled,
    disk_space_preflight,
    populate_classification_report,
    read_capture,
    write_capture,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
INST = "NSE:TEST"
SESSION = date(2026, 8, 31)


def _candle(ts: datetime, *, o="100", c="100", v=1000) -> Candle:
    open_val, close_val = Decimal(o), Decimal(c)
    return Candle(instrument_id=INST, timeframe=Timeframe.M5, ts_open=ts,
                  open=open_val, high=max(open_val, close_val) + 1, low=min(open_val, close_val) - 1,
                  close=close_val, volume=v, source="test")


def _capture(candles: list[Candle], captured_at: datetime, *, checkpoint: str = "09:30") -> ProvisionalCapture:
    start = datetime.combine(SESSION, time_of_day(9, 15), tzinfo=IST)
    return ProvisionalCapture(
        run_id="test-run", instrument_id=INST, checkpoint=checkpoint, session_date=SESSION,
        requested_start=start, requested_end=captured_at, request_ts=captured_at, provider_name="test",
        success=True, error=None, retry_count=0, candles=tuple(candles),
    )


@dataclass
class _FakeProvider:
    candles: list[Candle]
    name: str = "fake"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        return [c for c in self.candles if start <= c.ts_open <= end]


class TestCaptureProvisionalM5:
    def test_captures_and_sorts_by_timestamp(self):
        provider = _FakeProvider(candles=[
            _candle(datetime(2026, 8, 31, 9, 25, tzinfo=IST)),
            _candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST)),
        ])
        now = datetime(2026, 8, 31, 9, 30, tzinfo=IST)

        captures = capture_provisional_m5(
            provider=provider, instrument_ids=(INST,), session_date=SESSION,
            session_open_time=time_of_day(9, 15), tzinfo=IST, checkpoint_instant=now,
            checkpoint="09:30", run_id="test-run",
        )

        assert len(captures) == 1
        assert [c.ts_open.minute for c in captures[0].candles] == [15, 25]
        assert captures[0].captured_at == now
        assert captures[0].success is True
        assert captures[0].run_id == "test-run"


class TestCaptureRoundTrip:
    def test_write_then_read_reproduces_the_capture_exactly(self, tmp_path: Path):
        original = _capture([_candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST))],
                            datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        path = tmp_path / "capture.json"

        write_capture(original, path)
        restored = read_capture(path)

        assert restored == original
        assert json.loads(path.read_text())["instrument_id"] == INST


class TestCompareProvisionalToSettled:
    def test_unique_ohlcv_match_maps_a_drifted_row_to_its_settled_bucket(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102")],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102")],
                           datetime(2026, 9, 3, 0, 0, tzinfo=IST))

        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        assert len(comparisons) == 1
        r = comparisons[0]
        assert r.provisional_was_on_grid is False
        assert r.ohlcv_exact_match is True
        assert r.mapping_unique is True
        assert r.settled_ts == datetime(2026, 8, 31, 9, 40, tzinfo=IST)
        assert r.timestamp_offset_seconds == pytest.approx(235.0)  # 09:43:55 - 09:40:00

    def test_no_ohlcv_match_means_content_itself_changed(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102")],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="103")],  # different close
                           datetime(2026, 9, 3, 0, 0, tzinfo=IST))

        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        r = comparisons[0]
        assert r.ohlcv_exact_match is False
        assert r.candidate_match_count == 0
        assert r.settled_ts is None

    def test_multiple_identical_ohlcv_candidates_are_reported_as_non_unique(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102")],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([
            _candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102"),
            _candle(datetime(2026, 8, 31, 9, 45, tzinfo=IST), c="102"),
        ], datetime(2026, 9, 3, 0, 0, tzinfo=IST))

        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        r = comparisons[0]
        assert r.candidate_match_count == 2
        assert r.mapping_unique is False

    def test_an_on_grid_provisional_row_trivially_maps_to_itself(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                           datetime(2026, 9, 3, 0, 0, tzinfo=IST))

        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        assert comparisons[0].provisional_was_on_grid is True
        assert comparisons[0].mapping_unique is True

    def test_rejects_mismatched_instrument_or_session(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        other_session = ProvisionalCapture(
            run_id="test-run", instrument_id=INST, checkpoint="09:30", session_date=date(2026, 9, 1),
            requested_start=datetime(2026, 9, 1, 9, 15, tzinfo=IST), requested_end=datetime(2026, 9, 3, tzinfo=IST),
            request_ts=datetime(2026, 9, 3, tzinfo=IST), provider_name="test", success=True, error=None,
            retry_count=0, candles=(),
        )
        with pytest.raises(ValueError, match="must match"):
            compare_provisional_to_settled(provisional=provisional, settled=other_session)


class TestClassifyDiagnosis:
    def test_all_off_grid_rows_uniquely_mapped_is_timestamp_only_drift(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102")],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102")],
                           datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        assert classify_diagnosis(comparisons) is DiagnosisOutcome.TIMESTAMP_ONLY_PROVISIONAL_DRIFT

    def test_any_off_grid_row_with_no_content_match_is_ohlcv_also_changes(self):
        provisional = _capture([
            _candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102"),
            _candle(datetime(2026, 8, 31, 9, 48, 55, tzinfo=IST), c="105"),
        ], datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([
            _candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102"),
            _candle(datetime(2026, 8, 31, 9, 45, tzinfo=IST), c="999"),  # content changed
        ], datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        assert classify_diagnosis(comparisons) is DiagnosisOutcome.PROVISIONAL_OHLCV_ALSO_CHANGES

    def test_any_off_grid_row_with_multiple_candidates_is_ambiguous_even_if_others_are_clean(self):
        provisional = _capture([
            _candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102"),
            _candle(datetime(2026, 8, 31, 9, 48, 55, tzinfo=IST), c="105"),
        ], datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([
            _candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102"),
            _candle(datetime(2026, 8, 31, 9, 45, tzinfo=IST), c="105"),
            _candle(datetime(2026, 8, 31, 9, 50, tzinfo=IST), c="105"),
        ], datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        assert classify_diagnosis(comparisons) is DiagnosisOutcome.MAPPING_AMBIGUOUS

    def test_ambiguous_takes_priority_over_ohlcv_changed_when_both_present(self):
        """The Owner's decision rule checks ambiguity first -- an ambiguous
        mapping must never be silently reported as a clean OHLCV-changed
        finding, since we cannot even be sure the "changed" row wasn't
        itself a multi-candidate case elsewhere in the same set."""
        provisional = _capture([
            _candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102"),  # ambiguous
            _candle(datetime(2026, 8, 31, 9, 48, 55, tzinfo=IST), c="777"),  # no match at all
        ], datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([
            _candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102"),
            _candle(datetime(2026, 8, 31, 9, 45, tzinfo=IST), c="102"),
        ], datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        assert classify_diagnosis(comparisons) is DiagnosisOutcome.MAPPING_AMBIGUOUS

    def test_raises_when_the_capture_window_never_reached_the_drift_affected_tail(self):
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                               datetime(2026, 8, 31, 9, 20, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                           datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        with pytest.raises(ValueError, match="no off-grid provisional rows"):
            classify_diagnosis(comparisons)


class TestTrackBCheckpointSchedule:
    def test_pinned_to_the_artifact_verified_authoritative_set(self):
        """Verified 2026-08-28 directly against the promoted EM-4B
        checkpoint_ist one-hot categories, the EM-4D calibration keys (all
        18 combos, unanimous), and config/explosive_move.json's own
        checkpoints.candidate_ist/accepted_ist -- all three agree. This
        pins that finding so a future change to the contracts module can
        never silently desync Track B's schedule from what was proven."""
        assert TRACK_B_CHECKPOINT_SCHEDULE == (
            "09:20", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00", "14:00",
        )


class TestDiskSpacePreflight:
    def test_passes_when_free_space_exceeds_the_minimum(self, tmp_path: Path):
        free_gb = disk_space_preflight(path=tmp_path, minimum_free_gb=0.001)
        assert free_gb > 0.001

    def test_raises_when_free_space_is_below_the_minimum(self, tmp_path: Path):
        with pytest.raises(PreflightError, match="disk space preflight failed"):
            disk_space_preflight(path=tmp_path, minimum_free_gb=1_000_000.0)


class TestTrackBRunManifest:
    def test_round_trips_through_json(self, tmp_path: Path):
        manifest = TrackBRunManifest(
            run_id="em5-trackb-20260831", session_date=date(2026, 8, 31),
            checkpoints=TRACK_B_CHECKPOINT_SCHEDULE, instrument_ids=(INST,),
            liquidity_bucket_by_instrument={INST: "high"},
            kite_auth_verified_symbol="INFY", disk_free_gb_at_start=42.0,
            capture_file_paths=("a.json", "b.json"),
            started_at=datetime(2026, 8, 31, 9, 0, tzinfo=IST),
            finished_at=datetime(2026, 8, 31, 14, 5, tzinfo=IST),
        )
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

        restored = TrackBRunManifest.from_dict(json.loads(path.read_text()))

        assert restored == manifest


class TestClassificationReportSkeleton:
    def test_skeleton_has_every_required_field_and_no_conclusion(self):
        skeleton = build_classification_report_skeleton(
            run_id="em5-trackb-20260831", session_date=date(2026, 8, 31),
            checkpoints=TRACK_B_CHECKPOINT_SCHEDULE, liquidity_bucket_by_instrument={INST: "high"},
        )

        required_fields = (
            "provisional_capture_inventory", "settled_capture_inventory",
            "raw_timestamp_behavior_by_checkpoint", "ohlcv_exact_match_rate_overall",
            "ohlcv_exact_match_rate_by_checkpoint", "ohlcv_exact_match_rate_by_liquidity",
            "unique_mapping_rate_overall", "unique_mapping_rate_by_checkpoint",
            "timestamp_offset_seconds_by_checkpoint", "evidence_field_differences",
            "logit_probability_rank_impact", "classification", "recommended_correction",
            "expected_effect_on_frozen_em2_evidence", "full_canary_safe_to_run",
        )
        for field_name in required_fields:
            assert field_name in skeleton
            assert skeleton[field_name] is None

    def test_populate_reports_timestamp_only_drift_from_real_comparisons(self):
        skeleton = build_classification_report_skeleton(
            run_id="em5-trackb-20260831", session_date=date(2026, 8, 31),
            checkpoints=TRACK_B_CHECKPOINT_SCHEDULE, liquidity_bucket_by_instrument={INST: "high"},
        )
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), c="102")],
                               datetime(2026, 8, 31, 10, 0, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 40, tzinfo=IST), c="102")],
                           datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        populated = populate_classification_report(skeleton, comparisons_by_instrument={INST: comparisons})

        assert populated["classification"] == DiagnosisOutcome.TIMESTAMP_ONLY_PROVISIONAL_DRIFT.value
        assert populated["ohlcv_exact_match_rate_overall"] == 1.0
        assert populated["unique_mapping_rate_overall"] == 1.0
        assert populated["timestamp_offset_seconds_by_checkpoint"]["09:43"] == [pytest.approx(235.0)]

    def test_populate_leaves_classification_none_when_no_off_grid_evidence_is_not_complete(self):
        skeleton = build_classification_report_skeleton(
            run_id="em5-trackb-20260831", session_date=date(2026, 8, 31),
            checkpoints=TRACK_B_CHECKPOINT_SCHEDULE, liquidity_bucket_by_instrument={INST: "high"},
        )
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                               datetime(2026, 8, 31, 9, 20, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                           datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        populated = populate_classification_report(skeleton, comparisons_by_instrument={INST: comparisons})

        assert populated["classification"] is None

    def test_populate_reports_zero_off_grid_when_caller_proves_complete_live_evidence(self):
        skeleton = build_classification_report_skeleton(
            run_id="em5-trackb-20260831", session_date=date(2026, 8, 31),
            checkpoints=TRACK_B_CHECKPOINT_SCHEDULE, liquidity_bucket_by_instrument={INST: "high"},
        )
        provisional = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                               datetime(2026, 8, 31, 9, 20, tzinfo=IST))
        settled = _capture([_candle(datetime(2026, 8, 31, 9, 15, tzinfo=IST))],
                           datetime(2026, 9, 3, tzinfo=IST))
        comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

        populated = populate_classification_report(
            skeleton,
            comparisons_by_instrument={INST: comparisons},
            zero_off_grid_outcome_allowed=True,
        )

        assert populated["classification"] == DiagnosisOutcome.NO_OFF_GRID_PROVISIONAL_OBSERVED.value
