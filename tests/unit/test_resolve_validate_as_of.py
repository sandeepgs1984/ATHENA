"""Tests for owner-validate as_of resolution (live vs last session close)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.engine import CalendarEngine
from athena.calendar.resolve_as_of import resolve_validate_as_of
from athena.config.loader import load_config

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture()
def engine(config_dir) -> CalendarEngine:
    config = load_config(config_dir)
    return CalendarEngine.from_config_dir(config_dir, config.market)


def test_live_during_regular_session(engine: CalendarEngine) -> None:
    # Monday 2026-07-20 11:00 IST — inside 09:15–15:30
    now = datetime(2026, 7, 20, 11, 0, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "live"
    assert as_of == now


def test_session_close_after_regular_close(engine: CalendarEngine) -> None:
    # Monday 2026-07-20 23:00 IST — after close
    now = datetime(2026, 7, 20, 23, 0, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "session_close"
    assert as_of == datetime(2026, 7, 20, 15, 30, tzinfo=IST)


def test_premarket_uses_prior_session_close(engine: CalendarEngine) -> None:
    # Tuesday 2026-07-21 08:00 IST — before open; prior day was Monday
    now = datetime(2026, 7, 21, 8, 0, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "session_close"
    assert as_of == datetime(2026, 7, 20, 15, 30, tzinfo=IST)


def test_weekend_uses_friday_close(engine: CalendarEngine) -> None:
    # Saturday 2026-07-18 22:00 IST → prior trading day Friday 2026-07-17
    now = datetime(2026, 7, 18, 22, 0, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "session_close"
    assert as_of.date() == date(2026, 7, 17)
    assert as_of.hour == 15 and as_of.minute == 30


def test_holiday_uses_prior_session_close(engine: CalendarEngine) -> None:
    # Republic Day 2026-01-26 (Monday holiday) → prior Friday 2026-01-23
    now = datetime(2026, 1, 26, 12, 0, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "session_close"
    assert as_of == datetime(2026, 1, 23, 15, 30, tzinfo=IST)


def test_naive_now_rejected(engine: CalendarEngine) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        resolve_validate_as_of(datetime(2026, 7, 20, 11, 0), engine, IST)


def test_boundary_open_is_live(engine: CalendarEngine) -> None:
    now = datetime(2026, 7, 20, 9, 15, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "live"
    assert as_of == now


def test_boundary_close_is_session_close(engine: CalendarEngine) -> None:
    # close is exclusive for live window: local >= close → session_close
    now = datetime(2026, 7, 20, 15, 30, tzinfo=IST)
    as_of, mode = resolve_validate_as_of(now, engine, IST)
    assert mode == "session_close"
    assert as_of == now
