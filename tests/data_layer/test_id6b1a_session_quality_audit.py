from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.id6b1a_session_quality_audit import _timeframe_audit
from athena.domain.enums import Timeframe
from athena.domain.market import Candle

IST = ZoneInfo("Asia/Kolkata")
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
DAY = date(2026, 8, 26)  # a real ordinary NSE trading Wednesday


def _m5(hh: int, mm: int) -> Candle:
    px = Decimal("100")
    return Candle(
        instrument_id="NSE:TEST", timeframe=Timeframe.M5,
        ts_open=datetime(DAY.year, DAY.month, DAY.day, hh, mm, tzinfo=IST),
        open=px, high=px + 1, low=px - 1, close=px, volume=1000, source="test",
    )


def _calendar() -> CalendarEngine:
    cfg = load_config(CONFIG_DIR)
    return CalendarEngine.from_config_dir(CONFIG_DIR, cfg.market)


def test_timeframe_audit_exact_due_count_matches_hand_calculation() -> None:
    """§6 of the ID-6B.1A report: at as_of=09:30, exactly 3 M5 bars are due
    (09:15, 09:20, 09:25) -- the bar opening at 09:30 itself is not yet due."""
    calendar = _calendar()
    as_of = datetime(2026, 8, 26, 9, 30, tzinfo=IST)
    candles = [_m5(9, 15), _m5(9, 20), _m5(9, 25)]
    audit = _timeframe_audit(
        candles, Timeframe.M5, calendar=calendar, session_date=DAY,
        as_of=as_of, tzinfo=IST, quality="SUFFICIENT", bar_count=3,
    )
    assert audit.expected_due_count == 3
    assert audit.present_due_count == 3
    assert audit.missing_count == 0


def test_timeframe_audit_reports_missing_bar_not_matching_off_grid_candle() -> None:
    """A candle timestamped off the canonical 5-minute grid must never
    satisfy the due-bar requirement -- mirrors the real M15 off-grid
    finding (§8) at M5 scale, non-vacuously proven against a synthetic
    fixture rather than only inferred from real data."""
    calendar = _calendar()
    as_of = datetime(2026, 8, 26, 9, 30, tzinfo=IST)
    off_grid = Candle(
        instrument_id="NSE:TEST", timeframe=Timeframe.M5,
        ts_open=datetime(2026, 8, 26, 9, 20, 48, tzinfo=IST),  # off-grid, not 09:20:00
        open=Decimal("100"), high=Decimal("101"), low=Decimal("99"),
        close=Decimal("100"), volume=1000, source="test",
    )
    candles = [_m5(9, 15), off_grid, _m5(9, 25)]
    audit = _timeframe_audit(
        candles, Timeframe.M5, calendar=calendar, session_date=DAY,
        as_of=as_of, tzinfo=IST, quality="EXPECTED_BAR_MISSING", bar_count=3,
    )
    assert audit.expected_due_count == 3
    assert audit.missing_count == 1
    assert audit.missing_ts == (datetime(2026, 8, 26, 9, 20, tzinfo=IST).isoformat(),)


def test_timeframe_audit_detects_terminal_vs_earlier_missing_bar() -> None:
    """§9's terminal-vs-earlier distinction: a missing bar at the START of
    the due window is not the terminal (most-recently-due) slot."""
    calendar = _calendar()
    as_of = datetime(2026, 8, 26, 9, 30, tzinfo=IST)
    candles = [_m5(9, 20), _m5(9, 25)]  # 09:15 missing -- not the terminal slot
    audit = _timeframe_audit(
        candles, Timeframe.M5, calendar=calendar, session_date=DAY,
        as_of=as_of, tzinfo=IST, quality="EXPECTED_BAR_MISSING", bar_count=2,
    )
    assert audit.missing_count == 1
    assert audit.latest_missing_is_terminal_bar is False
