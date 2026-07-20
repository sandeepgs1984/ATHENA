"""Calendar Engine acceptance tests — Phase 0 exit criterion:
correct CalendarContext for 10 dates including a holiday and Muhurat."""

from __future__ import annotations

from datetime import date

import pytest

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.domain.enums import SessionType
from athena.errors import CalendarError


@pytest.fixture()
def engine(config_dir) -> CalendarEngine:
    config = load_config(config_dir)
    return CalendarEngine.from_config_dir(config_dir, config.market)


# The 10 acceptance dates (fixture expiries: weekly 2026-07-23, monthly 2026-07-30).
ACCEPTANCE_DATES = [
    ("2026-07-20", SessionType.NORMAL, None, False, False),          # ordinary Monday
    ("2026-07-18", SessionType.WEEKEND, None, False, False),         # Saturday
    ("2026-07-19", SessionType.WEEKEND, None, False, False),         # Sunday
    ("2026-01-26", SessionType.HOLIDAY, "Republic Day", False, False),
    ("2026-03-03", SessionType.HOLIDAY, "Holi", False, False),
    ("2026-12-25", SessionType.HOLIDAY, "Christmas", False, False),
    ("2026-11-08", SessionType.MUHURAT,
     "Diwali Laxmi Pujan (Muhurat Trading)", False, False),          # Sunday + Muhurat
    ("2026-07-23", SessionType.NORMAL, None, True, False),           # weekly expiry (fixture)
    ("2026-07-30", SessionType.NORMAL, None, False, True),           # monthly expiry (fixture)
    ("2026-02-01", SessionType.WEEKEND, None, False, False),         # Sunday + BUDGET event
]


@pytest.mark.parametrize("iso, session, holiday, weekly, monthly", ACCEPTANCE_DATES)
def test_acceptance_dates(engine, iso, session, holiday, weekly, monthly):
    ctx = engine.context_for(date.fromisoformat(iso))
    assert ctx.session_type is session
    assert ctx.holiday_name == holiday
    assert ctx.is_weekly_expiry is weekly
    assert ctx.is_monthly_expiry is monthly


def test_normal_day_has_nse_timings(engine):
    ctx = engine.context_for(date(2026, 7, 20))
    assert ctx.is_trading_session
    assert ctx.open_time.strftime("%H:%M") == "09:15"
    assert ctx.close_time.strftime("%H:%M") == "15:30"


def test_holiday_is_not_a_trading_session(engine):
    ctx = engine.context_for(date(2026, 1, 26))
    assert not ctx.is_trading_session
    assert ctx.open_time is None and ctx.close_time is None


def test_muhurat_is_trading_session_with_unnotified_timings(engine):
    ctx = engine.context_for(date(2026, 11, 8))
    assert ctx.is_trading_session
    assert ctx.open_time is None  # NSE notifies timings later; we never invent them


def test_budget_event_attached(engine):
    ctx = engine.context_for(date(2026, 2, 1))
    assert any(e.kind == "BUDGET" for e in ctx.events)


def test_uncovered_year_fails_loudly(engine):
    with pytest.raises(CalendarError, match="No calendar data for 2027"):
        engine.context_for(date(2027, 1, 1))


def test_determinism_same_input_same_output(engine):
    a = engine.context_for(date(2026, 7, 20))
    b = engine.context_for(date(2026, 7, 20))
    assert a == b
