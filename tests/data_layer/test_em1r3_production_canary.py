"""EM-1r3 production canary gate (owner-mandated 2026-08-24, after the
2026-08-22 production sweep ran to completion -- ~49 hours, real Kite
quota -- against a defective provider boundary and produced ~0% admission):
a small, cheap, real-provider check that must pass before an expensive
full-cohort sweep is allowed to proceed."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from athena.data.em1r3_production_canary import canary_dates, run_canary
from athena.data.intraday_reconstruction_ingestion import (
    IntradayReconstructionIngestionService,
)
from athena.domain.enums import SessionType, Timeframe
from athena.domain.market import CalendarContext, Candle

TZ = ZoneInfo("Asia/Kolkata")
STUDY_START = date(2026, 6, 1)  # a Monday
STUDY_END = date(2026, 8, 21)  # a Friday


class _WeekdayCalendar:
    """Real Sat/Sun weekend classification, NORMAL otherwise, small
    9:15-9:25 session window (2 slots) matching this project's other
    EM-1r3 fixture tests -- fast, deterministic, no calendar-year gaps."""

    def context_for(self, session_date: date) -> CalendarContext:
        session_type = SessionType.WEEKEND if session_date.weekday() >= 5 else SessionType.NORMAL
        return CalendarContext(
            context_date=session_date, session_type=session_type,
            exchange="NSE", timezone="Asia/Kolkata",
            open_time=time(9, 15) if session_type is SessionType.NORMAL else None,
            close_time=time(9, 25) if session_type is SessionType.NORMAL else None,
        )


class _CalendarWithOneSpecialSaturday(_WeekdayCalendar):
    """Otherwise identical, but treats one specific Saturday as a real,
    capturable SPECIAL full session (e.g. a Budget-day live session)."""

    def __init__(self, special_saturday: date) -> None:
        self._special_saturday = special_saturday

    def context_for(self, session_date: date) -> CalendarContext:
        if session_date == self._special_saturday:
            return CalendarContext(
                context_date=session_date, session_type=SessionType.SPECIAL,
                exchange="NSE", timezone="Asia/Kolkata",
                open_time=time(9, 15), close_time=time(9, 25),
            )
        return super().context_for(session_date)


def _candle(instrument_id: str, ts_open: datetime) -> Candle:
    return Candle(
        instrument_id=instrument_id, timeframe=Timeframe.M5, ts_open=ts_open,
        open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
        close=Decimal("100"), volume=1_000, source="kite", adjusted=False,
    )


class _HealthyProvider:
    """Returns a complete 2-slot session for every date -- models a
    correctly-behaving provider."""

    name = "fake-kite"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        del timeframe, end
        return [_candle(instrument_id, start), _candle(instrument_id, start.replace(minute=20))]


class _SystemicallyDefectiveProvider:
    """Always drops the final expected slot -- reproduces the exact shape
    of the 2026-08-22 incident (every session missing its last candle)."""

    name = "fake-kite"

    def intraday_candles(self, instrument_id, timeframe, start, end):
        del timeframe, end
        return [_candle(instrument_id, start)]  # only the first of 2 expected slots


class _RecentTailOnlyDefectiveProvider:
    """Healthy for everything except a single date -- models the real,
    expected, non-systemic recent-history-truncation pattern."""

    name = "fake-kite"

    def __init__(self, truncated_date: date) -> None:
        self._truncated_date = truncated_date

    def intraday_candles(self, instrument_id, timeframe, start, end):
        del timeframe, end
        if start.date() == self._truncated_date:
            return [_candle(instrument_id, start)]
        return [_candle(instrument_id, start), _candle(instrument_id, start.replace(minute=20))]


def _service(tmp_path: Path, provider, calendar=None) -> IntradayReconstructionIngestionService:
    return IntradayReconstructionIngestionService(
        calendar=calendar or _WeekdayCalendar(), evidence_root=tmp_path / "evidence",
        timezone_name="Asia/Kolkata", provider=provider,
        clock=lambda: datetime(2026, 8, 24, 12, 0, tzinfo=TZ),
    )


def test_canary_dates_never_lands_on_a_weekend():
    dates = canary_dates(_WeekdayCalendar(), STUDY_START, STUDY_END)
    assert dates
    for d in dates:
        assert d.weekday() < 5


def test_canary_dates_marks_only_the_newest_as_recent_tail():
    dates = canary_dates(_WeekdayCalendar(), STUDY_START, STUDY_END)
    recent_tail_dates = [d for d, is_tail in dates.items() if is_tail]
    assert len(recent_tail_dates) == 1
    assert max(dates) == recent_tail_dates[0]


def test_canary_passes_against_a_healthy_provider(tmp_path: Path):
    service = _service(tmp_path, _HealthyProvider())
    result = run_canary(
        service=service, calendar=_WeekdayCalendar(),
        instrument_ids=("NSE:AAA", "NSE:BBB"),
        study_start=STUDY_START, study_end=STUDY_END,
    )
    assert result.passed
    assert result.historical_admission_rate == 1.0


def test_canary_fails_fast_against_a_systemically_defective_provider(tmp_path: Path):
    """Reproduces the exact 2026-08-22 incident shape: every session
    missing its final expected slot -- the canary must catch this in a
    handful of calls, not after a 49-hour sweep."""
    service = _service(tmp_path, _SystemicallyDefectiveProvider())
    result = run_canary(
        service=service, calendar=_WeekdayCalendar(),
        instrument_ids=("NSE:AAA", "NSE:BBB"),
        study_start=STUDY_START, study_end=STUDY_END,
    )
    assert not result.passed
    assert result.historical_admission_rate == 0.0


def test_canary_never_penalizes_the_known_recent_tail_pattern(tmp_path: Path):
    """A provider that is only ever incomplete on the single most-recent
    date (the real, documented recent-history-truncation pattern) must
    still pass -- the threshold exists for systemic defects, not this
    known, separately-tracked limitation."""
    dates = canary_dates(_WeekdayCalendar(), STUDY_START, STUDY_END)
    recent_tail_date = max(dates)
    service = _service(tmp_path, _RecentTailOnlyDefectiveProvider(recent_tail_date))

    result = run_canary(
        service=service, calendar=_WeekdayCalendar(),
        instrument_ids=("NSE:AAA", "NSE:BBB"),
        study_start=STUDY_START, study_end=STUDY_END,
    )

    assert result.passed
    assert result.historical_admission_rate == 1.0
    assert result.recent_tail_admitted == 0
    assert result.recent_tail_requested > 0


def test_canary_includes_extra_dates_as_additional_historical_checks(tmp_path: Path):
    """A caller-supplied fixed date (e.g. a known SPECIAL full-session day,
    which canary_dates() itself would never auto-select since it only
    scans study_start/mid/study_end) is checked alongside the auto ones."""
    special_saturday = date(2026, 7, 4)
    calendar = _CalendarWithOneSpecialSaturday(special_saturday)
    service = _service(tmp_path, _HealthyProvider(), calendar=calendar)

    result = run_canary(
        service=service, calendar=calendar,
        instrument_ids=("NSE:AAA",),
        study_start=STUDY_START, study_end=STUDY_END,
        extra_dates={special_saturday: False},
    )

    assert any(o.session_date == special_saturday for o in result.outcomes)
    assert result.passed
