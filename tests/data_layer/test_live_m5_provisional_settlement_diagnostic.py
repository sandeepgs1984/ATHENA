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
    DiagnosisOutcome,
    ProvisionalCapture,
    capture_provisional_m5,
    classify_diagnosis,
    compare_provisional_to_settled,
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


def _capture(candles: list[Candle], captured_at: datetime) -> ProvisionalCapture:
    return ProvisionalCapture(instrument_id=INST, session_date=SESSION, captured_at=captured_at, candles=tuple(candles))


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
            session_open_time=time_of_day(9, 15), tzinfo=IST, captured_at=now,
        )

        assert len(captures) == 1
        assert [c.ts_open.minute for c in captures[0].candles] == [15, 25]
        assert captures[0].captured_at == now


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
            instrument_id=INST, session_date=date(2026, 9, 1), captured_at=datetime(2026, 9, 3, tzinfo=IST),
            candles=(),
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
