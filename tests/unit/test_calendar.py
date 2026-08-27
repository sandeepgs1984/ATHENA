"""Calendar Engine acceptance tests — Phase 0 exit criterion:
correct CalendarContext for 10 dates including a holiday and Muhurat."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import pytest
from tests.conftest import rewrite_json

from athena.calendar.engine import CalendarEngine
from athena.config.loader import load_config
from athena.data.validation.calendar_expectations import expected_intraday_opens
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
    # Sunday + BUDGET event; real NSE/CMTR/72349 full standard-hours session
    # discovered 2026-08-27 during EM-1c's regime-evidence acquisition --
    # was WEEKEND before that date's real special session was known.
    ("2026-02-01", SessionType.SPECIAL, "Live Trading Session -- Presentation of Union Budget", False, False),
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
    with pytest.raises(CalendarError, match=r"No calendar data for 2027"):
        engine.context_for(date(2027, 1, 1))


def test_determinism_same_input_same_output(engine):
    a = engine.context_for(date(2026, 7, 20))
    b = engine.context_for(date(2026, 7, 20))
    assert a == b


# --------------------------------------------------------------------------- #
# Calendar-contract correction (2026-08-22): a configured special session's
# own declared type is respected instead of every entry being hardcoded to
# MUHURAT, and a real trading day the model cannot faithfully represent
# (a split-window DR drill) is classified distinctly from an ordinary WEEKEND.
# --------------------------------------------------------------------------- #


def test_configured_full_session_saturday_overrides_weekend(engine):
    """2025-02-01 (Saturday): NSE/CMTR/65729 ran a full standard-hours live
    session for the Union Budget -- must be SPECIAL, not WEEKEND, and must
    carry the real open/close boundaries, not invented or null ones."""

    ctx = engine.context_for(date(2025, 2, 1))
    assert ctx.session_type is SessionType.SPECIAL
    assert ctx.is_trading_session
    assert ctx.open_time.strftime("%H:%M") == "09:15"
    assert ctx.close_time.strftime("%H:%M") == "15:30"


def test_special_session_slot_generation_matches_a_full_regular_session(engine):
    opens = expected_intraday_opens(engine, date(2025, 2, 1), 5, ZoneInfo("Asia/Kolkata"))
    assert len(opens) == 75
    assert opens[0].strftime("%H:%M") == "09:15"
    assert opens[-1].strftime("%H:%M") == "15:25"


def test_known_unsupported_special_session_is_not_weekend(engine):
    """2024-01-20 (Saturday): a real, live DR-drill session with a
    split-window shape the single open/close-window model cannot express.
    Must be classified distinctly, never silently as WEEKEND, and must not
    be treated as an assertable trading session."""

    ctx = engine.context_for(date(2024, 1, 20))
    assert ctx.session_type is SessionType.KNOWN_UNSUPPORTED_SPECIAL_SESSION
    assert ctx.session_type is not SessionType.WEEKEND
    assert not ctx.is_trading_session
    assert ctx.holiday_name is not None


def test_muhurat_type_still_resolves_to_muhurat_after_the_type_fix(engine):
    """A configured MUHURAT entry must still resolve to MUHURAT now that the
    engine reads ``type`` from configuration instead of hardcoding it --
    guards against the fix silently defaulting every entry to SPECIAL."""

    ctx = engine.context_for(date(2024, 11, 1))
    assert ctx.session_type is SessionType.MUHURAT


def test_invalid_special_session_type_fails_loudly(config_dir):
    rewrite_json(config_dir / "calendar" / "holidays.json", lambda data: data["special_sessions"].append(
        {"date": "2025-01-01", "type": "NORMAL", "name": "bogus special session"}
    ))
    config = load_config(config_dir)
    with pytest.raises(CalendarError, match="must be one of"):
        CalendarEngine.from_config_dir(config_dir, config.market)


def test_2023_bakri_id_revision_overrides_the_original_annual_circular(engine):
    """NSE's original 2023 annual holiday circular (NSE/CMTR/54757) listed
    Bakri Id on June 28; NSE Clearing circular NCL/CMPT/57291 (2023-06-27)
    revised it to June 29 the day before it took effect. Discovered
    2026-08-27 via a real Kite candle on June 28 contradicting the
    then-current calendar. The FINAL effective calendar must reflect the
    revision, not the original annual publication -- June 28 is a normal
    trading day, June 29 is the holiday."""

    june_28 = engine.context_for(date(2023, 6, 28))
    assert june_28.session_type is SessionType.NORMAL
    assert june_28.is_trading_session

    june_29 = engine.context_for(date(2023, 6, 29))
    assert june_29.session_type is SessionType.HOLIDAY
    assert june_29.holiday_name == "Bakri Id"
    assert not june_29.is_trading_session


def test_2024_05_18_dr_drill_is_known_unsupported_special_session(engine):
    """A third real DR-drill Saturday (in addition to 2024-01-20,
    2024-03-02), discovered 2026-08-27 via a real Kite candle during EM-1c's
    regime-evidence acquisition -- this file's own 2026-08-22 note had
    anticipated this date but not yet enumerated it. Same split-window
    shape (09:15-10:00, 11:30-12:30 IST) as the other two."""

    ctx = engine.context_for(date(2024, 5, 18))
    assert ctx.session_type is SessionType.KNOWN_UNSUPPORTED_SPECIAL_SESSION
    assert ctx.session_type is not SessionType.WEEKEND
    assert not ctx.is_trading_session
    assert ctx.holiday_name is not None
