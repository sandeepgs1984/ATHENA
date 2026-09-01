"""EM-5 Track B live-session operator flow (Owner authorization, 2026-08-28).
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
    PreflightResult,
    build_live_canary_completeness_report,
    calendar_preflight,
    classify_live_capture_zero_off_grid,
    estimate_request_budget,
    is_likely_settled,
    main,
    run_capture_phase,
    run_settlement_comparison_phase,
    run_unattended_capture,
)
from athena.data.live_m5_provisional_settlement_diagnostic import (
    TRACK_B_CHECKPOINT_SCHEDULE,
    DiagnosisOutcome,
    PreflightError,
    ProvisionalCapture,
    TrackBRunManifest,
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

    def test_partial_checkpoint_restart_captures_only_missing_files(self, tmp_path: Path):
        provider = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100")])
        now = datetime(2026, 8, 31, 9, 21, tzinfo=IST)
        run_capture_phase(
            provider=provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"}, now=now,
        )
        existing_path = tmp_path / "em5-trackb-test__0920__NSE_A.json"
        original_bytes = existing_path.read_bytes()

        provider_after_restart = _FakeProvider(ts_close_pairs=[(datetime(2026, 8, 31, 9, 20, tzinfo=IST), "999")])
        manifest = run_capture_phase(
            provider=provider_after_restart, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high", "NSE:B": "high"}, now=now,
        )

        assert existing_path.read_bytes() == original_bytes
        assert (tmp_path / "em5-trackb-test__0920__NSE_B.json").is_file()
        assert sorted(Path(path).name for path in manifest.capture_file_paths) == [
            "em5-trackb-test__0920__NSE_A.json",
            "em5-trackb-test__0920__NSE_B.json",
        ]

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
    def test_zero_off_grid_complete_evidence_produces_new_observational_outcome(self, tmp_path: Path):
        capture_provider = _FakeProvider(ts_close_pairs=[
            (datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100"),
        ])
        manifest = run_capture_phase(
            provider=capture_provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"},
            checkpoints=("09:20",), now=datetime(2026, 8, 31, 9, 21, tzinfo=IST),
        )

        report = run_settlement_comparison_phase(
            provider=capture_provider, manifest=manifest, tzinfo=IST, today=date(2026, 9, 25),
        )

        assert report["classification"] == DiagnosisOutcome.NO_OFF_GRID_PROVISIONAL_OBSERVED.value
        assert report["live_canary_completeness"]["complete"] is True
        assert report["live_canary_completeness"]["off_grid_provisional_row_count"] == 0

    def test_zero_off_grid_missing_checkpoint_does_not_produce_new_outcome(self, tmp_path: Path):
        capture_provider = _FakeProvider(ts_close_pairs=[
            (datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100"),
        ])
        run_capture_phase(
            provider=capture_provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"},
            checkpoints=("09:20",), now=datetime(2026, 8, 31, 9, 21, tzinfo=IST),
        )
        manifest = TrackBRunManifest(
            run_id="em5-trackb-test", session_date=SESSION_DATE,
            checkpoints=("09:20", "09:30"), instrument_ids=("NSE:A",),
            liquidity_bucket_by_instrument={"NSE:A": "high"},
            kite_auth_verified_symbol="INFY", disk_free_gb_at_start=40.0,
            capture_file_paths=(str(tmp_path / "em5-trackb-test__0920__NSE_A.json"),),
        )

        report = run_settlement_comparison_phase(
            provider=capture_provider, manifest=manifest, tzinfo=IST, today=date(2026, 9, 25),
        )

        assert report["classification"] is None
        assert report["live_canary_completeness"]["complete"] is False
        assert report["live_canary_completeness"]["missing_pairs"] == [
            {"instrument_id": "NSE:A", "checkpoint": "09:30"}
        ]

    def test_zero_off_grid_provider_failure_does_not_produce_new_outcome(self, tmp_path: Path):
        failed_capture = ProvisionalCapture(
            run_id="em5-trackb-test", instrument_id="NSE:A", checkpoint="09:20",
            session_date=SESSION_DATE,
            requested_start=datetime(2026, 8, 31, 9, 15, tzinfo=IST),
            requested_end=datetime(2026, 8, 31, 9, 20, tzinfo=IST),
            request_ts=datetime(2026, 8, 31, 9, 20, tzinfo=IST),
            provider_name="fake", success=False, error="provider down",
            retry_count=0, candles=(),
        )
        path = tmp_path / "em5-trackb-test__0920__NSE_A.json"
        path.write_text(json.dumps(failed_capture.to_dict(), indent=2), encoding="utf-8")
        manifest = TrackBRunManifest(
            run_id="em5-trackb-test", session_date=SESSION_DATE,
            checkpoints=("09:20",), instrument_ids=("NSE:A",),
            liquidity_bucket_by_instrument={"NSE:A": "high"},
            kite_auth_verified_symbol="INFY", disk_free_gb_at_start=40.0,
            capture_file_paths=(str(path),),
        )

        report = run_settlement_comparison_phase(
            provider=_FakeProvider(ts_close_pairs=[]), manifest=manifest, tzinfo=IST, today=date(2026, 9, 25),
        )

        assert report["classification"] is None
        assert report["live_canary_completeness"]["complete"] is False
        assert report["live_canary_completeness"]["failed_capture_count"] == 1

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


class TestLiveZeroOffGridReplay:
    def test_deterministic_replay_from_immutable_raw_captures(self, tmp_path: Path):
        capture_provider = _FakeProvider(ts_close_pairs=[
            (datetime(2026, 8, 31, 9, 20, tzinfo=IST), "100"),
        ])
        manifest = run_capture_phase(
            provider=capture_provider, session_date=SESSION_DATE,
            session_open_time=datetime(2026, 8, 31, 9, 15).time(), tzinfo=IST, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:A": "high"},
            checkpoints=("09:20",), now=datetime(2026, 8, 31, 9, 21, tzinfo=IST),
        )

        first = build_live_canary_completeness_report(manifest)
        second = build_live_canary_completeness_report(manifest)

        assert first == second
        assert classify_live_capture_zero_off_grid(manifest) is DiagnosisOutcome.NO_OFF_GRID_PROVISIONAL_OBSERVED

    def test_tuesday_immutable_evidence_replays_to_zero_off_grid_without_provider_request(self):
        manifest_path = Path("artifacts/live/em5_track_b/2026-09-01/em5-track-b-20260901__manifest.json")
        if not manifest_path.is_file():
            pytest.skip("Tuesday live Track B artifacts are not present in this checkout")
        manifest = TrackBRunManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
        before = {
            path: Path(path).read_bytes()
            for path in manifest.capture_file_paths
        }

        outcome = classify_live_capture_zero_off_grid(manifest)
        completeness = build_live_canary_completeness_report(manifest)

        after = {
            path: Path(path).read_bytes()
            for path in manifest.capture_file_paths
        }
        assert outcome is DiagnosisOutcome.NO_OFF_GRID_PROVISIONAL_OBSERVED
        assert completeness["complete"] is True
        assert completeness["expected_capture_count"] == 81
        assert completeness["capture_file_count"] == 81
        assert completeness["provisional_row_count"] == 1768
        assert completeness["off_grid_provisional_row_count"] == 0
        assert before == after


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


class _Clock:
    def __init__(self, current: datetime):
        self.current = current
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        from datetime import timedelta

        self.current = self.current + timedelta(seconds=seconds)


class TestRunUnattendedCapture:
    def test_waits_for_each_checkpoint_and_stops_without_settlement(self, tmp_path: Path, monkeypatch):
        clock = _Clock(datetime(2026, 8, 31, 9, 19, 50, tzinfo=IST))
        provider = _FakeProvider(ts_close_pairs=[
            (datetime.combine(SESSION_DATE, datetime.strptime(cp, "%H:%M").time(), tzinfo=IST), "100")
            for cp in ("09:20", "09:30")
        ])

        def fake_preflight(**kwargs):
            from athena.domain.enums import SessionType

            return PreflightResult(
                session_type=SessionType.NORMAL, resolved_symbol_count=1, unresolved_symbols=(),
                disk_free_gb=40.0, provider=provider,
            )

        called_settlement = False

        def fake_settlement(**kwargs):
            nonlocal called_settlement
            called_settlement = True
            return {}

        monkeypatch.setattr("athena.data.em5_track_b_capture_cli.run_preflight", fake_preflight)
        monkeypatch.setattr("athena.data.em5_track_b_capture_cli.run_settlement_comparison_phase", fake_settlement)

        manifest = run_unattended_capture(
            config_dir=Path("config"), session_date=SESSION_DATE, output_dir=tmp_path,
            run_id="em5-trackb-test", symbol_liquidity_buckets={"NSE:TEST": "high"},
            checkpoints=("09:20", "09:30"), now=clock.now, sleep=clock.sleep,
            max_sleep_seconds=600.0, log=lambda _msg: None,
        )

        assert called_settlement is False
        assert clock.sleeps[:2] == [10.0, 600.0]
        assert manifest.checkpoints == ("09:20", "09:30")
        assert (tmp_path / "em5-trackb-test__0920__NSE_TEST.json").is_file()
        assert (tmp_path / "em5-trackb-test__0930__NSE_TEST.json").is_file()

    def test_preflight_failure_fails_closed_before_capture(self, tmp_path: Path, monkeypatch):
        def fake_preflight(**kwargs):
            raise PreflightError("no auth")

        monkeypatch.setattr("athena.data.em5_track_b_capture_cli.run_preflight", fake_preflight)
        with pytest.raises(PreflightError, match="no auth"):
            run_unattended_capture(
                config_dir=Path("config"), session_date=SESSION_DATE, output_dir=tmp_path,
                run_id="em5-trackb-test", now=lambda: datetime(2026, 8, 31, 9, 20, tzinfo=IST),
                sleep=lambda _seconds: None,
            )
        assert not list(tmp_path.glob("*.json"))

    def test_cli_unattended_uses_default_output_and_run_id(self, tmp_path: Path, monkeypatch):
        calls = {}
        artifact_root = tmp_path / "artifacts" / "live" / "em5_track_b"
        monkeypatch.setattr("athena.data.em5_track_b_capture_cli.DEFAULT_ARTIFACT_ROOT", artifact_root)

        def fake_unattended(**kwargs):
            calls.update(kwargs)
            provider = _FakeProvider(ts_close_pairs=[])
            return run_capture_phase(
                provider=provider, session_date=kwargs["session_date"],
                session_open_time=datetime(2026, 9, 1, 9, 15).time(), tzinfo=IST,
                output_dir=kwargs["output_dir"], run_id=kwargs["run_id"],
                now=datetime(2026, 9, 1, 14, 0, tzinfo=IST),
            )

        monkeypatch.setattr("athena.data.em5_track_b_capture_cli.run_unattended_capture", fake_unattended)

        rc = main([
            "unattended", "--session-date", "2026-09-01",
            "--config-dir", str(tmp_path / "config"),
            "--max-sleep-seconds", "5",
        ])

        assert rc == 0
        assert calls["session_date"] == date(2026, 9, 1)
        assert calls["run_id"] == "em5-track-b-20260901"
        assert calls["output_dir"] == artifact_root / "2026-09-01"
        assert calls["max_sleep_seconds"] == 5
