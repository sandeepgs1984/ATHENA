"""Logging, metrics/budgets, and system-health pre-flight tests."""

from __future__ import annotations

import json
import logging
from datetime import date

from athena.domain.enums import HealthStatus
from athena.observability.health import run_system_checks
from athena.observability.logging import log_event, set_run_context, setup_logging
from athena.observability.metrics import MetricsRegistry


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
