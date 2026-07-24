"""Resolve owner-validate ``as_of`` for live vs last completed session.

Manual Validate / Re-validate must not use wall-clock ``now`` after the regular
session ends: quote freshness is measured against ``as_of``, and overnight
``now`` falsely rejects completed-session data. CalendarEngine remains the only
source of trading-day truth (R-3).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.errors import CalendarError

ValidateAsOfMode = Literal["live", "session_close"]


def _session_close_dt(
    calendar: CalendarEngine,
    day: date,
    market_tz: ZoneInfo,
) -> datetime | None:
    ctx = calendar.context_for(day)
    if not ctx.is_trading_session or ctx.close_time is None:
        return None
    return datetime.combine(day, ctx.close_time, tzinfo=market_tz)


def _latest_session_close_on_or_before(
    calendar: CalendarEngine,
    ref: date,
    market_tz: ZoneInfo,
    *,
    lookback_days: int,
) -> datetime:
    day = ref
    for _ in range(lookback_days + 1):
        close = _session_close_dt(calendar, day, market_tz)
        if close is not None:
            return close
        day -= timedelta(days=1)
    raise CalendarError(
        f"cannot resolve session close for validate as_of on or before {ref.isoformat()} "
        f"(lookback {lookback_days} days)"
    )


def resolve_validate_as_of(
    now: datetime,
    calendar: CalendarEngine,
    market_tz: ZoneInfo,
    *,
    lookback_days: int = 30,
) -> tuple[datetime, ValidateAsOfMode]:
    """Choose live wall-clock or last completed session close for validate.

    - During a known regular/special session window → ``(local_now, \"live\")``.
    - After close, before open, weekend, holiday, or Muhurat with unknown
      timings → ``(last_session_close, \"session_close\")``.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if lookback_days < 1:
        raise ValueError("lookback_days must be >= 1")

    local = now.astimezone(market_tz)
    today = local.date()
    ctx = calendar.context_for(today)

    if (
        ctx.is_trading_session
        and ctx.open_time is not None
        and ctx.close_time is not None
    ):
        open_dt = datetime.combine(today, ctx.open_time, tzinfo=market_tz)
        close_dt = datetime.combine(today, ctx.close_time, tzinfo=market_tz)
        if open_dt <= local < close_dt:
            return local, "live"
        if local >= close_dt:
            return close_dt, "session_close"
        # Premarket: prior completed session
        return (
            _latest_session_close_on_or_before(
                calendar,
                today - timedelta(days=1),
                market_tz,
                lookback_days=lookback_days,
            ),
            "session_close",
        )

    # Weekend / holiday / Muhurat with null timings
    return (
        _latest_session_close_on_or_before(
            calendar,
            today,
            market_tz,
            lookback_days=lookback_days,
        ),
        "session_close",
    )
