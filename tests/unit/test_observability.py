"""Logging, metrics/budgets, and system-health pre-flight tests."""

from __future__ import annotations

import json
import logging
from datetime import date

import pytest

from athena.domain.enums import HealthStatus
from athena.observability.health import run_system_checks
from athena.observability.logging import log_event, set_run_context, setup_logging
from athena.observability.metrics import MetricsRegistry
from athena.observability.timing import CycleTimingRecorder


class _FakeClock:
    """Deterministic incrementing clock: each call advances by `step`."""

    def __init__(self, step: float = 1.0) -> None:
        self._t = 0.0
        self._step = step

    def __call__(self) -> float:
        self._t += self._step
        return self._t


class TestCycleTimingRecorder:
    def test_phase_is_deterministic_with_injected_clock(self):
        recorder = CycleTimingRecorder(clock=_FakeClock(step=2.5))
        with recorder.phase("ingestion_total"):
            pass
        assert recorder.phases["ingestion_total"] == pytest.approx(2.5)

    def test_repeated_phase_calls_accumulate(self):
        recorder = CycleTimingRecorder(clock=_FakeClock(step=1.0))
        with recorder.phase("scan_total"):
            pass
        with recorder.phase("scan_total"):
            pass
        assert recorder.phases["scan_total"] == pytest.approx(2.0)

    def test_phase_records_elapsed_even_when_body_raises(self):
        recorder = CycleTimingRecorder(clock=_FakeClock(step=3.0))
        with pytest.raises(ValueError), recorder.phase("ingestion_total"):
            raise ValueError("boom")
        assert recorder.phases["ingestion_total"] == pytest.approx(3.0)

    def test_record_call_rejects_negative_duration(self):
        recorder = CycleTimingRecorder()
        with pytest.raises(ValueError, match="non-negative"):
            recorder.record_call("ingestion.daily_candles", "NSE:INFY", -0.1)

    def test_call_group_summary_statistics(self):
        recorder = CycleTimingRecorder()
        for label, duration in [("A", 1.0), ("B", 2.0), ("C", 3.0), ("D", 4.0), ("E", 100.0)]:
            recorder.record_call("ingestion.daily_candles", label, duration)
        summary = recorder.as_dict()["call_groups"]["ingestion.daily_candles"]
        assert summary["count"] == 5
        assert summary["ok_count"] == 5
        assert summary["failed_count"] == 0
        assert summary["min_seconds"] == 1.0
        assert summary["max_seconds"] == 100.0
        assert summary["median_seconds"] == 3.0
        assert summary["slowest"][0] == {"label": "E", "duration_seconds": 100.0, "ok": True}

    def test_failed_calls_counted_separately_from_ok_calls(self):
        recorder = CycleTimingRecorder()
        recorder.record_call("ingestion.quotes", "batch", 1.0, ok=True)
        recorder.record_call("ingestion.quotes", "batch-retry", 0.5, ok=False)
        summary = recorder.as_dict()["call_groups"]["ingestion.quotes"]
        assert summary["ok_count"] == 1
        assert summary["failed_count"] == 1

    def test_empty_call_group_not_present_until_recorded(self):
        recorder = CycleTimingRecorder()
        assert recorder.as_dict()["call_groups"] == {}

    def test_as_dict_rounds_but_does_not_lose_phase_structure(self):
        recorder = CycleTimingRecorder(clock=_FakeClock(step=0.123456))
        with recorder.phase("finalization"):
            pass
        payload = recorder.as_dict()
        assert set(payload.keys()) == {"phases_seconds", "call_groups"}
        assert payload["phases_seconds"]["finalization"] == pytest.approx(0.123, abs=1e-3)


class TestLogging:
    def test_json_lines_with_run_context(self, tmp_path):
        log_path = setup_logging(tmp_path / "logs", "INFO")
        set_run_context("run-42", "cycle-7")
        log_event("test", "unit_test_event", {"value": 123})
        logging.getLogger("athena").handlers[0].flush()

        entry = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert entry["event"] == "unit_test_event"
        assert entry["run_id"] == "run-42"
        assert entry["cycle_id"] == "cycle-7"
        assert entry["payload"] == {"value": 123}

    def test_secrets_are_redacted(self, tmp_path):
        log_path = setup_logging(tmp_path / "logs", "INFO")
        log_event("test", "provider_call", {
            "api_key": "SUPER-SECRET", "nested": {"auth_token": "ALSO-SECRET"},
            "symbol": "RELIANCE",
        })
        logging.getLogger("athena").handlers[0].flush()

        raw = log_path.read_text(encoding="utf-8")
        assert "SUPER-SECRET" not in raw and "ALSO-SECRET" not in raw
        assert "RELIANCE" in raw


class TestMetricsBudgets:
    def test_budget_violation_detected(self):
        fake_time = iter([0.0, 20.0])  # 20s elapsed
        registry = MetricsRegistry(clock=lambda: next(fake_time))
        with registry.timer("refresh"):
            pass
        violations = registry.budget_violations({"refresh": 10.0, "decision": 3.0})
        assert len(violations) == 1
        assert violations[0].operation == "refresh"
        assert "budget 10s" in str(violations[0])

    def test_within_budget_is_clean(self):
        registry = MetricsRegistry()
        registry.record("decision", 0.5)
        assert registry.budget_violations({"decision": 3.0}) == ()


class TestSystemHealth:
    def test_healthy_phase0_reports_warn_for_future_modules(self, config_dir, tmp_path):
        report = run_system_checks(config_dir, tmp_path, for_date=date(2026, 7, 20))
        by_name = {c.name: c for c in report.checks}
        assert by_name["config"].status is HealthStatus.OK
        assert by_name["calendar_data"].status is HealthStatus.OK
        assert by_name["provider"].status is HealthStatus.WARN  # honest: Phase 1
        assert report.status is HealthStatus.WARN
        assert not report.blocking_issues

    def test_missing_calendar_year_blocks(self, config_dir, tmp_path):
        report = run_system_checks(config_dir, tmp_path, for_date=date(2031, 1, 1))
        assert report.status is HealthStatus.BLOCKED
        assert any("2031" in c.detail for c in report.blocking_issues)
