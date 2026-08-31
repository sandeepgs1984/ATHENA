from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.id5b_live_m5_semantics_canary import (
    ID5B_CANARY_INSTRUMENTS,
    CheckpointCaptureStatus,
    ID5BCase,
    ID5BRequestBudget,
    calendar_preflight,
    classify_id5b_case,
    run_capture_phase,
    run_settlement_comparison_phase,
)
from athena.data.live_m5_provisional_settlement_diagnostic import (
    PreflightError,
    ProvisionalCapture,
    compare_provisional_to_settled,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
SESSION_DATE = date(2026, 8, 31)


@dataclass
class _FakeProvider:
    rows: list[tuple[str, datetime, str]]
    name: str = "fake"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        out = []
        for iid, ts, close in self.rows:
            if iid == instrument_id and start <= ts <= end:
                value = Decimal(close)
                out.append(Candle(
                    instrument_id=instrument_id,
                    timeframe=Timeframe.M5,
                    ts_open=ts,
                    open=value,
                    high=value + 1,
                    low=value - 1,
                    close=value,
                    volume=1000,
                    source="test",
                ))
        return out


def test_id5b_canary_scope_is_frozen_to_benchmark_two_sector_indexes_two_equities():
    assert ID5B_CANARY_INSTRUMENTS == {
        "NSE:NIFTY 50": "benchmark_index",
        "NSE:NIFTY BANK": "sector_index",
        "NSE:NIFTY IT": "sector_index",
        "NSE:RELIANCE": "equity",
        "NSE:INFY": "equity",
    }
    assert ID5BRequestBudget().provisional_capture_requests == 45
    assert ID5BRequestBudget().settlement_comparison_requests == 5
    assert ID5BRequestBudget().total_requests == 50


def test_calendar_preflight_accepts_2026_08_31_and_rejects_sunday():
    config_dir = Path(__file__).resolve().parents[2] / "config"
    assert calendar_preflight(config_dir=config_dir, session_date=SESSION_DATE).name == "NORMAL"
    with pytest.raises(PreflightError, match="not a live scannable NSE session"):
        calendar_preflight(config_dir=config_dir, session_date=date(2026, 8, 30))


def test_capture_phase_writes_id5b_manifest_and_does_not_capture_future_checkpoints(tmp_path: Path):
    provider = _FakeProvider(rows=[
        ("NSE:NIFTY 50", datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100"),
    ])

    manifest = run_capture_phase(
        provider=provider,
        session_date=SESSION_DATE,
        output_dir=tmp_path,
        run_id="id5b-test",
        now=datetime(2026, 8, 31, 9, 22, tzinfo=IST),
        instrument_roles={"NSE:NIFTY 50": "benchmark_index"},
    )

    assert manifest["track"] == "ID-5B"
    assert manifest["checkpoint_status"]["09:20"] == CheckpointCaptureStatus.CAPTURED.value
    assert manifest["checkpoint_status"]["09:30"] == CheckpointCaptureStatus.NOT_YET_DUE.value
    assert (tmp_path / "id5b-test__manifest.json").is_file()


def test_settlement_phase_maps_shared_diagnosis_to_id5b_case_a(tmp_path: Path):
    provisional_provider = _FakeProvider(rows=[
        ("NSE:NIFTY 50", datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), "102"),
    ])
    run_capture_phase(
        provider=provisional_provider,
        session_date=SESSION_DATE,
        output_dir=tmp_path,
        run_id="id5b-test",
        now=datetime(2026, 8, 31, 9, 45, tzinfo=IST),
        instrument_roles={"NSE:NIFTY 50": "benchmark_index"},
    )

    settled_provider = _FakeProvider(rows=[
        ("NSE:NIFTY 50", datetime(2026, 8, 31, 9, 40, tzinfo=IST), "102"),
    ])
    report = run_settlement_comparison_phase(
        provider=settled_provider,
        manifest_path=tmp_path / "id5b-test__manifest.json",
        force=True,
    )

    assert report["case"] == ID5BCase.CASE_A_TIMESTAMP_ONLY.value
    assert report["diagnosis"] == "TIMESTAMP_ONLY_PROVISIONAL_DRIFT"
    assert json.loads((tmp_path / "id5b-test__settlement_comparison.json").read_text())["track"] == "ID-5B"


def _capture(candles: list[Candle]) -> ProvisionalCapture:
    ts = datetime(2026, 8, 31, 10, 0, tzinfo=IST)
    return ProvisionalCapture(
        run_id="id5b-test",
        instrument_id="NSE:NIFTY 50",
        checkpoint="10:00",
        session_date=SESSION_DATE,
        requested_start=datetime(2026, 8, 31, 9, 15, tzinfo=IST),
        requested_end=ts,
        request_ts=ts,
        provider_name="test",
        success=True,
        error=None,
        retry_count=0,
        candles=tuple(candles),
    )


def _candle(ts: datetime, close: str) -> Candle:
    value = Decimal(close)
    return Candle(
        instrument_id="NSE:NIFTY 50",
        timeframe=Timeframe.M5,
        ts_open=ts,
        open=value,
        high=value + 1,
        low=value - 1,
        close=value,
        volume=1000,
        source="test",
    )


def test_id5b_classifier_marks_on_grid_content_change_as_case_b():
    provisional = _capture([_candle(datetime(2026, 8, 31, 10, 0, tzinfo=IST), "100")])
    settled = _capture([_candle(datetime(2026, 8, 31, 10, 0, tzinfo=IST), "101")])

    comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

    assert classify_id5b_case(comparisons) is ID5BCase.CASE_B_CONTENT_CHANGES


def test_id5b_classifier_marks_all_on_grid_exact_matches_as_insufficient():
    provisional = _capture([_candle(datetime(2026, 8, 31, 10, 0, tzinfo=IST), "100")])
    settled = _capture([_candle(datetime(2026, 8, 31, 10, 0, tzinfo=IST), "100")])

    comparisons = compare_provisional_to_settled(provisional=provisional, settled=settled)

    assert classify_id5b_case(comparisons) is ID5BCase.CASE_D_INSUFFICIENT_EVIDENCE
