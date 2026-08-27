"""EM-1c regime-evidence acquisition: unit tests for the pure validation
and overlap-resolution logic, using the real (test-copied) production
calendar so the known-gap/known-special-session classification is
exercised against the actual dates this milestone discovered and fixed."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.em1c_regime_evidence_acquisition import (
    OverlapMismatch,
    resolve_overlap_mismatches,
    validate,
)
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")


def _candle(instrument_id: str, d: date, close: str) -> Candle:
    return Candle(
        instrument_id=instrument_id, timeframe=Timeframe.D1,
        ts_open=datetime.combine(d, datetime.min.time(), tzinfo=IST),
        open=Decimal(close), high=Decimal(close), low=Decimal(close),
        close=Decimal(close), volume=0, source="kite", adjusted=False,
    )


def test_known_missing_trading_day_does_not_block_acceptance(config_dir):
    """2024-01-22: the already-disclosed EM-1r3 zero-candle blackout day."""
    config = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, config.market)
    fetched = []  # no candle at all on this date
    report = validate(
        instrument_id="NSE:NIFTY 50", fetched=fetched, existing={}, calendar=calendar,
        study_start=date(2024, 1, 22), study_end=date(2024, 1, 22),
    )
    assert report.known_missing_trading_days == ("2024-01-22",)
    assert report.unexplained_missing_trading_days == ()
    assert report.passed


def test_unexplained_missing_trading_day_blocks_acceptance(config_dir):
    """Any OTHER real trading day with no candle is a genuine, unexplained
    gap and must still block acceptance."""
    config = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, config.market)
    report = validate(
        instrument_id="NSE:NIFTY 50", fetched=[], existing={}, calendar=calendar,
        study_start=date(2024, 1, 23), study_end=date(2024, 1, 23),
    )
    assert report.unexplained_missing_trading_days == ("2024-01-23",)
    assert not report.passed


def test_known_special_session_with_data_does_not_block_acceptance(config_dir):
    """2024-05-18: a real DR-drill Saturday -- KNOWN_UNSUPPORTED_SPECIAL_SESSION,
    so real candle data existing for it is expected, not an anomaly."""
    config = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, config.market)
    fetched = [_candle("NSE:NIFTY 50", date(2024, 5, 18), "22500")]
    report = validate(
        instrument_id="NSE:NIFTY 50", fetched=fetched, existing={}, calendar=calendar,
        study_start=date(2024, 5, 18), study_end=date(2024, 5, 18),
    )
    assert report.known_special_session_days_with_data == ("2024-05-18",)
    assert report.unexplained_non_trading_days_with_data == ()
    assert report.passed


def test_unexplained_data_on_a_real_weekend_blocks_acceptance(config_dir):
    """A real weekend (not a known special session) with fetched data is a
    genuine, unexplained anomaly and must block acceptance."""
    config = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, config.market)
    saturday = date(2024, 1, 27)  # an ordinary Saturday, no special session
    fetched = [_candle("NSE:NIFTY 50", saturday, "22000")]
    report = validate(
        instrument_id="NSE:NIFTY 50", fetched=fetched, existing={}, calendar=calendar,
        study_start=saturday, study_end=saturday,
    )
    assert report.unexplained_non_trading_days_with_data == (saturday.isoformat(),)
    assert not report.passed


def test_duplicate_dates_block_acceptance(config_dir):
    config = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, config.market)
    d = date(2024, 1, 23)
    fetched = [_candle("NSE:NIFTY 50", d, "22000"), _candle("NSE:NIFTY 50", d, "22001")]
    report = validate(
        instrument_id="NSE:NIFTY 50", fetched=fetched, existing={}, calendar=calendar,
        study_start=d, study_end=d,
    )
    assert report.duplicate_dates == (d.isoformat(),)
    assert not report.passed


def test_2023_06_28_29_revised_calendar_produces_no_anomaly(config_dir):
    """The corrected calendar (Bakri Id moved to 06-29) must make a real
    candle on 06-28 (trading day) and no candle on 06-29 (holiday) look
    completely normal -- exactly what Kite's real fetched data showed."""
    config = load_config(config_dir)
    calendar = CalendarEngine.from_config_dir(config_dir, config.market)
    fetched = [_candle("NSE:NIFTY 50", date(2023, 6, 28), "18908.15")]
    report = validate(
        instrument_id="NSE:NIFTY 50", fetched=fetched, existing={}, calendar=calendar,
        study_start=date(2023, 6, 28), study_end=date(2023, 6, 29),
    )
    assert report.unexplained_missing_trading_days == ()
    assert report.unexplained_non_trading_days_with_data == ()
    assert report.passed


def test_overlap_mismatch_uses_external_corroboration_when_found():
    mismatch = OverlapMismatch(
        instrument_id="NSE:INDIA VIX", session_date="2026-08-19", field="close",
        existing="11.31", fetched="11.32",
    )
    resolved = resolve_overlap_mismatches((mismatch,), retrieved_at="2026-08-27T00:00:00+05:30")
    assert len(resolved) == 1
    assert resolved[0].selected_value == "11.32"
    assert "corroboration found" in resolved[0].selection_reason


def test_overlap_mismatch_falls_back_to_fetched_value_when_uncorroborated():
    mismatch = OverlapMismatch(
        instrument_id="NSE:INDIA VIX", session_date="2026-08-04", field="close",
        existing="12.10", fetched="12.19",
    )
    resolved = resolve_overlap_mismatches((mismatch,), retrieved_at="2026-08-27T00:00:00+05:30")
    assert resolved[0].selected_value == "12.19"
    assert "not cleanly obtainable" in resolved[0].selection_reason
    assert resolved[0].absolute_difference == "0.09"


def test_overlap_mismatch_never_silently_overwrites_the_existing_value_field():
    """Provenance for both observations must always be preserved regardless
    of which value gets selected as the research value."""
    mismatch = OverlapMismatch(
        instrument_id="NSE:INDIA VIX", session_date="2026-08-04", field="close",
        existing="12.10", fetched="12.19",
    )
    resolved = resolve_overlap_mismatches((mismatch,), retrieved_at="2026-08-27T00:00:00+05:30")
    assert resolved[0].existing_value == "12.10"
    assert resolved[0].fetched_value == "12.19"
