"""EM-5 Track B Monday operator flow (Owner authorization, 2026-08-28).
No live Kite calls in any test -- the provider is a fully injected fake."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.data.em5_track_b_capture_cli import (
    DEFAULT_SYMBOL_LIQUIDITY_BUCKETS,
    calendar_preflight,
    estimate_request_budget,
    is_likely_settled,
    run_capture_phase,
    run_settlement_comparison_phase,
)
from athena.data.live_m5_provisional_settlement_diagnostic import (
    TRACK_B_CHECKPOINT_SCHEDULE,
    PreflightError,
)
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
    def test_future_checkpoints_are_not_yet_due_not_captured(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[
            (datetime.combine(SESSION_DATE, datetime.strptime(cp, "%H:%M").time(), tzinfo=IST), "100")
            for cp in TRACK_B_CHECKPOINT_SCHEDULE
        ])
        now = datetime(2026, 8, 31, 9, 22, tzinfo=IST)  # only 09:20 has happened, within grace

        manifest = run_capture_phase(
            provider=provider, session_date=SESSION_DATE, session_open_time=datetime(2026, 8, 31, 9, 15).time(),
            tzinfo=IST, output_dir=tmp_path, run_id="em5-trackb-test",
            symbol_liquidity_buckets={"NSE:TEST": "high"}, now=now,
        )

        assert manifest.checkpoints == TRACK_B_CHECKPOINT_SCHEDULE  # full schedule recorded...
        assert len(manifest.capture_file_paths) == 1  # ...but only 09:20 actually captured this call

    def test_a_checkpoint_more_than_the_grace_window_stale_is_not_observed_live_not_captured(self, tmp_path: Path):
        """A late process start (or a system sleep/wake spanning several
        checkpoints) must never let a now-stale request masquerade as a
        live capture of an already-elapsed checkpoint."""
        provider = _FakeProvider(ts_close_pairs=[
            (datetime.combine(SESSION_DATE, datetime.strptime(cp, "%H:%M").time(), tzinfo=IST), "100")
            for cp in TRACK_B_CHECKPOINT_SCHEDULE
        ])
        now = datetime(2026, 8, 31, 10, 5, tzinfo=IST)  # 09:20/09:30/09:45 are all >5min stale; 10:00 is exactly 5min

        manifest = run_capture_phase(
            provider=provider, session_date=SESSION_DATE, session_open_time=datetime(2026, 8, 31, 9, 15).time(),
            tzinfo=IST, output_dir=tmp_path, run_id="em5-trackb-test",
            symbol_liquidity_buckets={"NSE:TEST": "high"}, now=now,
        )

        # Only 10:00 (exactly at the 300s grace boundary) was captured;
        # 09:20/09:30/09:45 are all well past the grace window.
        assert len(manifest.capture_file_paths) == 1
        assert "1000" in manifest.capture_file_paths[0]

    def test_rerunning_after_a_restart_never_recaptures_or_overwrites_a_completed_checkpoint(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100")])
        first_now = datetime(2026, 8, 31, 9, 21, tzinfo=IST)
        run_capture_phase(
            provider=provider, session_date=SESSION_DATE, session_open_time=datetime(2026, 8, 31, 9, 15).time(),
            tzinfo=IST, output_dir=tmp_path, run_id="em5-trackb-test",
            symbol_liquidity_buckets={"NSE:TEST": "high"}, now=first_now,
        )
        first_capture_path = tmp_path / "em5-trackb-test__0920__NSE_TEST.json"
        original_bytes = first_capture_path.read_bytes()

        # A different provider (simulating a restart with a different live
        # connection) must never be consulted for a checkpoint already on disk.
        provider_after_restart = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "999")])
        later_now = datetime(2026, 8, 31, 9, 40, tzinfo=IST)  # 09:20 is now stale too, if it were re-attempted
        manifest = run_capture_phase(
            provider=provider_after_restart, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:TEST": "high"}, now=later_now,
        )

        assert first_capture_path.read_bytes() == original_bytes  # byte-identical, never overwritten
        assert str(first_capture_path) in manifest.capture_file_paths

    def test_now_must_be_timezone_aware(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[])
        try:
            run_capture_phase(
                provider=provider, session_date=SESSION_DATE,
                session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
                run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:TEST": "high"},
                now=datetime(2026, 8, 31, 9, 20),  # naive
            )
            raised = False
        except ValueError:
            raised = True
        assert raised

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
        report = run_settlement_comparison_phase(
            provider=settled_provider, manifest=manifest, tzinfo=IST,
            today=date(2026, 9, 25),  # comfortably past MINIMUM_DAYS_BEFORE_LIKELY_SETTLED
        )

        assert report["classification"] == "TIMESTAMP_ONLY_PROVISIONAL_DRIFT"
        assert report["ohlcv_exact_match_rate_overall"] == 1.0

    def test_refuses_to_run_before_the_session_is_likely_settled(self, tmp_path: Path):
        capture_provider = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100")])
        manifest = run_capture_phase(
            provider=capture_provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"},
            now=datetime(2026, 8, 31, 9, 21, tzinfo=IST),
        )

        with pytest.raises(PreflightError, match="not be settled yet"):
            run_settlement_comparison_phase(
                provider=capture_provider, manifest=manifest, tzinfo=IST,
                today=date(2026, 9, 2),  # only 2 days later
            )

    def test_force_overrides_the_settlement_timing_guard(self, tmp_path: Path):
        capture_provider = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100")])
        manifest = run_capture_phase(
            provider=capture_provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"},
            now=datetime(2026, 8, 31, 9, 21, tzinfo=IST),
        )

        report = run_settlement_comparison_phase(
            provider=capture_provider, manifest=manifest, tzinfo=IST, today=date(2026, 9, 2), force=True,
        )
        assert report is not None


def test_default_symbol_buckets_exclude_the_known_unresolvable_e2e_symbol():
    assert "NSE:E2E" not in DEFAULT_SYMBOL_LIQUIDITY_BUCKETS
    assert set(DEFAULT_SYMBOL_LIQUIDITY_BUCKETS.values()) == {"high", "medium", "low"}


class TestCalendarPreflight:
    """Real `CalendarEngine`, real `config/`, zero Kite/network calls --
    proves Monday (2026-08-31) is genuinely recognized as a normal trading
    session through ATHENA's own canonical calendar, not a hardcoded
    assumption, and that a real non-trading day is correctly refused."""

    CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

    def test_2026_08_31_is_recognized_as_a_normal_trading_session(self):
        from athena.domain.enums import SessionType

        session_type = calendar_preflight(config_dir=self.CONFIG_DIR, session_date=date(2026, 8, 31))
        assert session_type is SessionType.NORMAL

    def test_a_real_weekend_is_refused_rather_than_silently_overridden(self):
        with pytest.raises(PreflightError, match="not a scannable session"):
            calendar_preflight(config_dir=self.CONFIG_DIR, session_date=date(2026, 8, 30))  # real Sunday


class TestIsLikelySettled:
    def test_false_before_the_minimum_days_have_passed(self):
        assert is_likely_settled(session_date=date(2026, 8, 31), today=date(2026, 9, 10)) is False

    def test_true_once_the_minimum_days_have_passed(self):
        assert is_likely_settled(session_date=date(2026, 8, 31), today=date(2026, 9, 21)) is True
