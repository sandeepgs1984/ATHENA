"""EM-5 Track B Monday operator flow (Owner authorization, 2026-08-28).
No live Kite calls in any test -- the provider is a fully injected fake."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.data.em5_track_b_capture_cli import (
    DEFAULT_SYMBOL_LIQUIDITY_BUCKETS,
    estimate_request_budget,
    run_capture_phase,
    run_settlement_comparison_phase,
)
from athena.data.live_m5_provisional_settlement_diagnostic import TRACK_B_CHECKPOINT_SCHEDULE
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
SESSION_DATE = date(2026, 8, 31)


@dataclass
class _FakeProvider:
    """`ts_close_pairs` are (real_ts, close) -- the real_ts may be off-grid,
    simulating a provisional row observed at (but not exactly timestamped
    to) a checkpoint."""

    ts_close_pairs: list[tuple[datetime, str]]
    name: str = "fake"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        out = []
        for ts, close in self.ts_close_pairs:
            if start <= ts <= end:
                c = Decimal(close)
                out.append(Candle(instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts,
                                  open=c, high=c + 1, low=c - 1, close=c, volume=1000, source="test"))
        return out


class TestEstimateRequestBudget:
    def test_matches_the_default_9x9_symbol_checkpoint_grid_plus_settlement_fetch(self):
        budget = estimate_request_budget()
        assert budget.symbol_count == 9
        assert budget.checkpoint_count == 9
        assert budget.provisional_capture_requests == 81
        assert budget.settlement_comparison_requests == 9
        assert budget.total_requests == 90


class TestRunCapturePhase:
    def test_captures_only_checkpoints_that_have_already_elapsed(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[
            (datetime.combine(SESSION_DATE, datetime.strptime(cp, "%H:%M").time(), tzinfo=IST), "100")
            for cp in TRACK_B_CHECKPOINT_SCHEDULE
        ])
        now = datetime(2026, 8, 31, 10, 5, tzinfo=IST)  # only 09:20/09:30/09:45/10:00 have happened

        manifest = run_capture_phase(
            provider=provider, session_date=SESSION_DATE, session_open_time=datetime(2026, 8, 31, 9, 15).time(),
            tzinfo=IST, output_dir=tmp_path, run_id="em5-trackb-test",
            symbol_liquidity_buckets={"NSE:TEST": "high"}, now=now,
        )

        assert manifest.checkpoints == TRACK_B_CHECKPOINT_SCHEDULE  # full schedule recorded...
        assert len(manifest.capture_file_paths) == 4  # ...but only 4 actually captured this call

    def test_writes_one_immutable_capture_file_per_symbol_per_captured_checkpoint(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100")])
        now = datetime(2026, 8, 31, 9, 25, tzinfo=IST)

        manifest = run_capture_phase(
            provider=provider, session_date=SESSION_DATE, session_open_time=datetime(2026, 8, 31, 9, 15).time(),
            tzinfo=IST, output_dir=tmp_path, run_id="em5-trackb-test",
            symbol_liquidity_buckets={"NSE:A": "high", "NSE:B": "low"}, now=now,
        )

        assert len(manifest.capture_file_paths) == 2
        for path_str in manifest.capture_file_paths:
            payload = json.loads(Path(path_str).read_text())
            assert payload["instrument_id"] in ("NSE:A", "NSE:B")

    def test_manifest_file_itself_is_persisted_alongside_the_captures(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100")])
        now = datetime(2026, 8, 31, 9, 25, tzinfo=IST)

        run_capture_phase(
            provider=provider, session_date=SESSION_DATE, session_open_time=datetime(2026, 8, 31, 9, 15).time(),
            tzinfo=IST, output_dir=tmp_path, run_id="em5-trackb-test",
            symbol_liquidity_buckets={"NSE:A": "high"}, now=now,
            kite_auth_verified_symbol="INFY", disk_free_gb_at_start=40.0,
        )

        manifest_path = tmp_path / "em5-trackb-test__manifest.json"
        assert manifest_path.is_file()
        payload = json.loads(manifest_path.read_text())
        assert payload["kite_auth_verified_symbol"] == "INFY"
        assert payload["disk_free_gb_at_start"] == 40.0


class TestRunSettlementComparisonPhase:
    def test_produces_a_populated_report_from_a_real_capture_and_settled_refetch(self, tmp_path: Path):
        # Provisional: an off-grid row observed near the 09:45 checkpoint.
        capture_provider = _FakeProvider(ts_close_pairs=[
            (datetime(2026, 8, 31, 9, 43, 55, tzinfo=IST), "102"),
        ])
        now = datetime(2026, 8, 31, 9, 50, tzinfo=IST)
        manifest = run_capture_phase(
            provider=capture_provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"}, now=now,
        )

        # Settled: same content, real grid-aligned bucket.
        settled_provider = _FakeProvider(ts_close_pairs=[
            (datetime(2026, 8, 31, 9, 40, tzinfo=IST), "102"),
        ])
        report = run_settlement_comparison_phase(provider=settled_provider, manifest=manifest, tzinfo=IST)

        assert report["classification"] == "TIMESTAMP_ONLY_PROVISIONAL_DRIFT"
        assert report["ohlcv_exact_match_rate_overall"] == 1.0


def test_default_symbol_buckets_exclude_the_known_unresolvable_e2e_symbol():
    assert "NSE:E2E" not in DEFAULT_SYMBOL_LIQUIDITY_BUCKETS
    assert set(DEFAULT_SYMBOL_LIQUIDITY_BUCKETS.values()) == {"high", "medium", "low"}
