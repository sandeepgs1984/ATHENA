"""Trading Calendar Engine (R-3, ATHENA-002 §2).

One responsibility: turn a date into a CalendarContext every downstream
module can trust. Data lives in config/calendar/*.json — never in code.
Fails loudly (CalendarError) when asked about a year it has no data for.
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

from athena.config.loader import load_calendar_files
from athena.config.models import MarketConfig
from athena.domain.enums import SessionType
from athena.domain.market import CalendarContext, CalendarEvent
from athena.errors import CalendarError

_SATURDAY, _SUNDAY = 5, 6


def _parse_date(raw: str, source: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise CalendarError(f"Invalid date '{raw}' in {source}: {exc}") from exc


class CalendarEngine:
    """Answers: what kind of trading day is <date>, and what should modules know about it?"""

    def __init__(
        self,
        market: MarketConfig,
        holidays: dict[date, str],
        special_sessions: dict[date, tuple[str, time | None, time | None]],
        weekly_expiries: frozenset[date],
        monthly_expiries: frozenset[date],
        events: dict[date, tuple[CalendarEvent, ...]],
        covered_years: frozenset[int],
    ) -> None:
        self._market = market
        self._holidays = holidays
        self._special = special_sessions
        self._weekly = weekly_expiries
        self._monthly = monthly_expiries
        self._events = events
        self._years = covered_years

    @classmethod
    def from_config_dir(cls, config_dir: Path, market: MarketConfig) -> CalendarEngine:
        holidays_file, expiries_file, events_file = load_calendar_files(config_dir)

        holidays = {
            _parse_date(h.date, "holidays.json"): h.name for h in holidays_file.holidays
        }
        special = {
            _parse_date(s.date, "holidays.json"): (s.name, s.open, s.close)
            for s in holidays_file.special_sessions
        }
        weekly = frozenset(_parse_date(d, "expiries.json") for d in expiries_file.weekly)
        monthly = frozenset(_parse_date(d, "expiries.json") for d in expiries_file.monthly)

        events: dict[date, tuple[CalendarEvent, ...]] = {}
        for item in events_file.events:
            d = _parse_date(item.date, "events.json")
            events[d] = (*events.get(d, ()), CalendarEvent(event_date=d, kind=item.kind, name=item.name))

        return cls(
            market=market,
            holidays=holidays,
            special_sessions=special,
            weekly_expiries=weekly,
            monthly_expiries=monthly,
            events=events,
            covered_years=frozenset(holidays_file.years),
        )

    def context_for(self, d: date) -> CalendarContext:
        if d.year not in self._years:
            raise CalendarError(
                f"No calendar data for {d.year} (covered: {sorted(self._years)}). "
                "Update config/calendar/holidays.json from the current NSE circular."
            )

        common = dict(
            context_date=d,
            exchange=self._market.exchange,
            timezone=self._market.timezone,
            is_weekly_expiry=d in self._weekly,
            is_monthly_expiry=d in self._monthly,
            events=self._events.get(d, ()),
        )

        # Special sessions (e.g. Muhurat) take precedence — they can fall on weekends.
        if d in self._special:
            name, open_t, close_t = self._special[d]
            return CalendarContext(
                session_type=SessionType.MUHURAT,
                open_time=open_t,
                close_time=close_t,
                holiday_name=name,
                **common,
            )

        if d in self._holidays:
            return CalendarContext(
                session_type=SessionType.HOLIDAY,
                open_time=None,
                close_time=None,
                holiday_name=self._holidays[d],
                **common,
            )

        if d.weekday() in (_SATURDAY, _SUNDAY):
            return CalendarContext(
                session_type=SessionType.WEEKEND,
                open_time=None,
                close_time=None,
                **common,
            )

        return CalendarContext(
            session_type=SessionType.NORMAL,
            open_time=self._market.sessions.open,
            close_time=self._market.sessions.close,
            **common,
        )
