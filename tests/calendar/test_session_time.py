"""remaining_session_minutes: pure, no hidden clock, negative after close."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from athena.calendar.session_time import remaining_session_minutes

IST = ZoneInfo("Asia/Kolkata")


def test_remaining_minutes_before_close():
    as_of = datetime(2026, 8, 28, 12, 0, tzinfo=IST)
    close = datetime(2026, 8, 28, 15, 30, tzinfo=IST)
    assert remaining_session_minutes(as_of, close) == pytest.approx(210.0)


def test_remaining_minutes_after_close_is_negative():
    as_of = datetime(2026, 8, 28, 15, 45, tzinfo=IST)
    close = datetime(2026, 8, 28, 15, 30, tzinfo=IST)
    assert remaining_session_minutes(as_of, close) == pytest.approx(-15.0)


def test_remaining_minutes_at_close_is_zero():
    as_of = datetime(2026, 8, 28, 15, 30, tzinfo=IST)
    close = datetime(2026, 8, 28, 15, 30, tzinfo=IST)
    assert remaining_session_minutes(as_of, close) == 0.0


def test_rejects_naive_as_of():
    with pytest.raises(ValueError, match="timezone-aware"):
        remaining_session_minutes(datetime(2026, 8, 28, 12, 0), datetime(2026, 8, 28, 15, 30, tzinfo=IST))


def test_rejects_naive_session_close():
    with pytest.raises(ValueError, match="timezone-aware"):
        remaining_session_minutes(datetime(2026, 8, 28, 12, 0, tzinfo=IST), datetime(2026, 8, 28, 15, 30))
