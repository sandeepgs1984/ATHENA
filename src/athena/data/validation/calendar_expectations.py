"""Trading-session expectations derived from the Calendar Engine (M1.3).

Gap and freshness validation must NEVER infer trading sessions manually
(ATHENA-002, R-3). These helpers use only the CalendarEngine public API.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from athena.calendar.engine import CalendarEngine


def trading_days_between(calendar: CalendarEngine, start: date, end: date) -> List[date]:
    """Expected trading sessions in [start, end] inclusive, per the calendar."""
    days: List[date] = []
    day = start
    while day <= end:
        if calendar.context_for(day).is_trading_session:
            days.append(day)
        day += timedelta(days=1)
    return days


def latest_trading_day_on_or_before(
    calendar: CalendarEngine, ref: date, *, lookback_days: int = 15
) -> Optional[date]:
    """Most recent trading session on or before ``ref`` (None if none within lookback)."""
    day = ref
    for _ in range(lookback_days + 1):
        if calendar.context_for(day).is_trading_session:
            return day
        day -= timedelta(days=1)
    return None


def expected_intraday_opens(
    calendar: CalendarEngine, day: date, step_minutes: int, tzinfo
) -> List[datetime]:
    """Expected intraday candle open-times for one session (empty if timings unknown)."""
    ctx = calendar.context_for(day)
    if not ctx.is_trading_session or ctx.open_time is None or ctx.close_time is None:
        return []  # e.g. Muhurat before NSE notifies timings — cannot assert expectations
    opens: List[datetime] = []
    cursor = datetime.combine(day, ctx.open_time, tzinfo=tzinfo)
    session_close = datetime.combine(day, ctx.close_time, tzinfo=tzinfo)
    step = timedelta(minutes=step_minutes)
    while cursor < session_close:
        opens.append(cursor)
        cursor += step
    return opens
