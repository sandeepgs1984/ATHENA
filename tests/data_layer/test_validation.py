"""Validation Layer tests (M1.3): freshness, OHLC, duplicates, gaps, reports,
quarantine, config — provider-agnostic, deterministic (injected as_of)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config, load_validation_config
from athena.config.models import ValidationConfig
from athena.data.validation import (
    DatasetValidator,
    QuarantineRegistry,
    Severity,
    ValidationResult,
    ValidationType,
    validate_daily_gaps,
    validate_duplicates,
    validate_freshness,
    validate_intraday_gaps,
    validate_ohlc,
)
from athena.data.validation.reports import ValidationReport
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.errors import ConfigError

IST = ZoneInfo("Asia/Kolkata")
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def calendar(config_dir) -> CalendarEngine:
    return CalendarEngine.from_config_dir(config_dir, load_config(config_dir).market)


@pytest.fixture()
def vconfig(config_dir) -> ValidationConfig:
    return load_validation_config(config_dir)


@pytest.fixture()
def validator(calendar, vconfig) -> DatasetValidator:
    return DatasetValidator(calendar, vconfig, IST)


def _daily(day: date, *, o="100", h="102", low="99", c="101", vol=1000) -> Candle:
    return Candle(instrument_id="X", timeframe=Timeframe.D1,
                  ts_open=datetime.combine(day, datetime.min.time(), tzinfo=IST).replace(hour=9, minute=15),
                  open=Decimal(o), high=Decimal(h), low=Decimal(low), close=Decimal(c),
                  volume=vol, source="test")


def _intraday(ts: datetime, tf=Timeframe.M5) -> Candle:
    return Candle(instrument_id="X", timeframe=tf, ts_open=ts,
                  open=Decimal("100"), high=Decimal("100.5"), low=Decimal("99.5"),
                  close=Decimal("100"), volume=100, source="test")


# --- daily trading days in a known clean window (Feb 2026 has no holidays) ---
def _feb_trading_days(calendar) -> list[date]:
    from athena.data.validation.calendar_expectations import trading_days_between
    return trading_days_between(calendar, date(2026, 2, 2), date(2026, 2, 6))


AS_OF = datetime(2026, 2, 6, 18, 0, tzinfo=IST)


class TestOHLC:
    def test_positive_prices_pass(self):
        r = validate_ohlc([_daily(date(2026, 2, 2))], as_of=AS_OF)
        assert r.passed and r.validation_type is ValidationType.OHLC

    def test_non_positive_price_fails_critical(self):
        bad = _daily(date(2026, 2, 2), o="0", low="0")
        r = validate_ohlc([bad], as_of=AS_OF)
        assert not r.passed
        assert r.severity is Severity.CRITICAL
        assert r.statistics["non_positive_price_count"] == 1


class TestDuplicates:
    def test_clean_dataset(self):
        r = validate_duplicates([_daily(date(2026, 2, 2)), _daily(date(2026, 2, 3))], as_of=AS_OF)
        assert r.passed

    def test_cross_dataset_duplicate_detected(self):
        dup = _daily(date(2026, 2, 2))
        r = validate_duplicates([dup, dup], as_of=AS_OF)
        assert not r.passed
        assert r.statistics["duplicate_count"] == 1
        assert r.severity is Severity.ERROR


class TestFreshness:
    def test_fresh_daily(self, calendar, vconfig):
        candles = [_daily(d) for d in _feb_trading_days(calendar)]
        r = validate_freshness(candles, Timeframe.D1, calendar, vconfig, as_of=AS_OF)
        assert r.passed

    def test_stale_daily(self, calendar, vconfig):
        candles = [_daily(date(2026, 1, 5))]  # weeks behind
        r = validate_freshness(candles, Timeframe.D1, calendar, vconfig, as_of=AS_OF)
        assert not r.passed
        assert r.statistics["trading_days_behind"] > vconfig.freshness.max_trading_days_behind

    def test_empty_dataset_is_critical(self, calendar, vconfig):
        r = validate_freshness([], Timeframe.D1, calendar, vconfig, as_of=AS_OF)
        assert not r.passed and r.severity is Severity.CRITICAL

    def test_intraday_fresh(self, calendar, vconfig):
        latest = AS_OF - timedelta(minutes=5)
        r = validate_freshness([_intraday(latest)], Timeframe.M5, calendar, vconfig, as_of=AS_OF)
        assert r.passed

    def test_intraday_stale(self, calendar, vconfig):
        latest = AS_OF - timedelta(minutes=120)
        r = validate_freshness([_intraday(latest)], Timeframe.M5, calendar, vconfig, as_of=AS_OF)
        assert not r.passed


class TestDailyGaps:
    def test_no_gaps_when_all_sessions_present(self, calendar):
        days = _feb_trading_days(calendar)
        r = validate_daily_gaps([_daily(d) for d in days], calendar,
                                start=date(2026, 2, 2), end=date(2026, 2, 6), as_of=AS_OF)
        assert r.passed
        assert r.statistics["missing_sessions"] == 0

    def test_weekend_is_not_a_gap(self, calendar):
        # Range spans a weekend (Feb 7-8 2026 are Sat/Sun); only weekdays expected.
        days = [d for d in _feb_trading_days(calendar)]
        r = validate_daily_gaps([_daily(d) for d in days], calendar,
                                start=date(2026, 2, 2), end=date(2026, 2, 8), as_of=AS_OF)
        assert r.passed  # Sat/Sun never counted as missing

    def test_holiday_is_not_a_gap(self, calendar):
        # 2026-01-26 Republic Day holiday; surrounding weekdays present.
        from athena.data.validation.calendar_expectations import trading_days_between
        days = trading_days_between(calendar, date(2026, 1, 23), date(2026, 1, 28))
        assert date(2026, 1, 26) not in days  # holiday excluded from expectations
        r = validate_daily_gaps([_daily(d) for d in days], calendar,
                                start=date(2026, 1, 23), end=date(2026, 1, 28), as_of=AS_OF)
        assert r.passed

    def test_missing_session_detected(self, calendar):
        days = _feb_trading_days(calendar)
        present = [_daily(d) for d in days if d != date(2026, 2, 4)]  # drop a Wednesday
        r = validate_daily_gaps(present, calendar,
                                start=date(2026, 2, 2), end=date(2026, 2, 6), as_of=AS_OF)
        assert not r.passed
        assert "2026-02-04" in r.evidence


class TestIntradayGaps:
    def _session_opens(self, calendar):
        from athena.data.validation.calendar_expectations import expected_intraday_opens
        return expected_intraday_opens(calendar, date(2026, 2, 2), 5, IST)

    def test_complete_session_has_no_gaps(self, calendar):
        opens = self._session_opens(calendar)
        candles = [_intraday(t) for t in opens]
        r = validate_intraday_gaps(candles, Timeframe.M5, calendar,
                                   start=date(2026, 2, 2), end=date(2026, 2, 2),
                                   as_of=AS_OF, tzinfo=IST)
        assert r.passed
        assert r.statistics["expected_intervals"] == 75  # 09:15..15:25 inclusive, 5-min

    def test_intraday_gap_detected(self, calendar):
        opens = self._session_opens(calendar)
        candles = [_intraday(t) for t in opens if t.hour != 11]  # drop the 11:xx block
        r = validate_intraday_gaps(candles, Timeframe.M5, calendar,
                                   start=date(2026, 2, 2), end=date(2026, 2, 2),
                                   as_of=AS_OF, tzinfo=IST)
        assert not r.passed
        assert r.statistics["missing_intervals"] > 0


class TestReports:
    def test_report_is_immutable(self):
        r = validate_ohlc([_daily(date(2026, 2, 2))], as_of=AS_OF)
        with pytest.raises(Exception):
            r.statistics["candles_checked"] = 999  # frozen mapping

    def test_passed_report_cannot_be_critical(self):
        with pytest.raises(ValueError, match="PASSED report cannot carry"):
            ValidationReport(validation_type=ValidationType.OHLC, result=ValidationResult.PASSED,
                             severity=Severity.CRITICAL, explanation="x", ts=AS_OF)

    def test_summary_aggregates(self, validator, calendar):
        days = _feb_trading_days(calendar)
        summary = validator.validate_daily("X:1d", [_daily(d) for d in days],
                                           start=date(2026, 2, 2), end=date(2026, 2, 6), as_of=AS_OF)
        assert summary.passed
        assert {r.validation_type for r in summary.reports} == {
            ValidationType.OHLC, ValidationType.DUPLICATE,
            ValidationType.FRESHNESS, ValidationType.GAP,
        }


class TestQuarantine:
    def test_clean_dataset_not_quarantined(self, validator, calendar):
        days = _feb_trading_days(calendar)
        summary = validator.validate_daily("clean", [_daily(d) for d in days],
                                           start=date(2026, 2, 2), end=date(2026, 2, 6), as_of=AS_OF)
        registry = QuarantineRegistry()
        assert registry.review(summary) is None
        assert not registry.is_quarantined("clean")

    def test_invalid_dataset_quarantined_with_evidence(self, validator):
        bad = [_daily(date(2026, 2, 2), o="-1", low="-5")]
        summary = validator.validate_daily("bad", bad,
                                           start=date(2026, 2, 2), end=date(2026, 2, 2), as_of=AS_OF)
        registry = QuarantineRegistry()
        record = registry.review(summary)
        assert record is not None
        assert registry.is_quarantined("bad")
        assert record.failed_reports  # evidence preserved
        assert "OHLC" in record.reason

    def test_quarantine_records_collected(self, validator):
        registry = QuarantineRegistry()
        for i, price in enumerate(["-1", "-2"]):
            bad = [_daily(date(2026, 2, 2), o=price, low=price)]
            summary = validator.validate_daily(f"bad-{i}", bad,
                                               start=date(2026, 2, 2), end=date(2026, 2, 2), as_of=AS_OF)
            registry.review(summary)
        assert len(registry.records) == 2


class TestConfig:
    def test_loads_production_validation_config(self):
        cfg = load_validation_config(REPO / "config")
        assert cfg.freshness.max_trading_days_behind >= 0
        assert cfg.gaps.daily_enabled in (True, False)

    def test_missing_validation_config_fails(self, tmp_path):
        with pytest.raises(ConfigError, match="Missing configuration file.*validation.json"):
            load_validation_config(tmp_path)

    def test_negative_freshness_threshold_rejected(self, config_dir):
        (config_dir / "validation.json").write_text(
            '{"freshness":{"max_trading_days_behind":-1,"intraday_max_minutes_behind":20},'
            '"gaps":{"daily_enabled":true,"intraday_enabled":true}}', encoding="utf-8")
        with pytest.raises(ConfigError):
            load_validation_config(config_dir)

    def test_gaps_can_be_disabled(self, calendar, config_dir):
        (config_dir / "validation.json").write_text(
            '{"freshness":{"max_trading_days_behind":1,"intraday_max_minutes_behind":20},'
            '"gaps":{"daily_enabled":false,"intraday_enabled":false}}', encoding="utf-8")
        cfg = load_validation_config(config_dir)
        validator = DatasetValidator(calendar, cfg, IST)
        summary = validator.validate_daily("X", [_daily(date(2026, 2, 2))],
                                           start=date(2026, 2, 2), end=date(2026, 2, 6), as_of=AS_OF)
        assert ValidationType.GAP not in {r.validation_type for r in summary.reports}
