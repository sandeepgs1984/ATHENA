"""Session Context Engine (ID-1).

Answers: "what part of the trading day is this, and what trustworthy
intraday data do we actually have right now?" — descriptive only, never a
signal, never a gate. Consumes already-fetched ``Candle``/``Quote`` objects
and the existing ``CalendarEngine``/market-session config; never reads a
provider, never reads the wall clock, never fabricates a value.

Reuses ATHENA's existing calendar-expectations contract
(``data.validation.calendar_expectations.expected_intraday_opens``) for
missing-bar detection instead of inventing a parallel gap-detection scheme —
the same calendar authority ingestion-time gap validation already trusts.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.config.models import SessionsConfig
from athena.data.validation.calendar_expectations import expected_intraday_opens
from athena.domain.enums import Timeframe
from athena.domain.market import CalendarContext, Candle
from athena.session.models import SessionContext, SessionDataQualityStatus, SessionPhase, TimeframeProvenance

#: Bar duration in minutes. Intentionally a small, local constant rather than
#: importing `data.validation.validators`'s module-private `_STEP_MINUTES` —
#: that name is private by convention (leading underscore); duplicating a
#: 3-entry unit-conversion table is preferable to reaching into another
#: module's private state. Not "indicator math" (nothing forecasted/derived).
_TIMEFRAME_MINUTES = {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15}


def is_candle_completed(candle: Candle, *, as_of: datetime) -> bool:
    """A bar is completed once its full duration has elapsed at-or-before
    ``as_of`` — deterministic from ``ts_open``/``timeframe``/``as_of`` alone,
    per ID-1 §5. Never true for a bar still forming at ``as_of``."""
    minutes = _TIMEFRAME_MINUTES.get(candle.timeframe)
    if minutes is None:
        raise ValueError(
            f"completed-candle semantics are undefined for timeframe {candle.timeframe!r}"
        )
    return candle.ts_open + timedelta(minutes=minutes) <= as_of


def latest_completed_candle(
    candles: Sequence[Candle], timeframe: Timeframe, *, as_of: datetime
) -> Candle | None:
    """The most recent candle of ``timeframe`` whose full bar has elapsed at
    ``as_of`` — or ``None`` if none has. Never returns a still-forming bar."""
    completed = [
        c for c in candles if c.timeframe is timeframe and is_candle_completed(c, as_of=as_of)
    ]
    if not completed:
        return None
    return max(completed, key=lambda c: c.ts_open)


def classify_session_phase(
    ctx: CalendarContext, sessions: SessionsConfig, *, as_of: datetime, tzinfo: ZoneInfo
) -> SessionPhase:
    """Objective phase from the calendar's own day-specific open/close (which
    correctly varies for a special session, e.g. Muhurat) plus the global
    pre-open window (`config/market.nse.json`'s `sessions` block — the
    calendar contract has no per-day pre-open concept to vary it by)."""
    if not ctx.is_trading_session:
        return SessionPhase.NOT_A_TRADING_SESSION
    local_time = as_of.astimezone(tzinfo).time()
    if local_time < sessions.preopen_start:
        return SessionPhase.CLOSED
    if ctx.open_time is None or ctx.close_time is None:
        # A real trading day (e.g. an unconfirmed Muhurat) whose exact
        # open/close NSE has not yet notified — cannot distinguish
        # PRE_OPEN/REGULAR/CLOSED further; not guessed either way.
        return SessionPhase.PRE_OPEN
    if local_time < ctx.open_time:
        return SessionPhase.PRE_OPEN
    if local_time >= ctx.close_time:
        return SessionPhase.CLOSED
    return SessionPhase.REGULAR


class SessionContextEngine:
    """Deterministic, replayable session-awareness assessment. No I/O, no
    clock reads — every input (candles, quote timestamp, calendar, as_of) is
    injected by the caller, matching every other engine in this codebase."""

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        exchange: str,
        calendar: CalendarEngine,
        sessions: SessionsConfig,
        tzinfo: ZoneInfo,
        five_min_candles: Sequence[Candle],
        fifteen_min_candles: Sequence[Candle],
        latest_quote_ts: datetime | None,
    ) -> SessionContext:
        if as_of.tzinfo is None:
            raise ValueError("SessionContextEngine.assess as_of must be timezone-aware")
        session_date = as_of.astimezone(tzinfo).date()
        ctx = calendar.context_for(session_date)
        phase = classify_session_phase(ctx, sessions, as_of=as_of, tzinfo=tzinfo)

        session_open_ts = (
            datetime.combine(session_date, ctx.open_time, tzinfo=tzinfo)
            if ctx.is_trading_session and ctx.open_time is not None
            else None
        )
        session_close_ts = (
            datetime.combine(session_date, ctx.close_time, tzinfo=tzinfo)
            if ctx.is_trading_session and ctx.close_time is not None
            else None
        )
        elapsed_seconds, remaining_seconds = self._elapsed_remaining(
            as_of, session_open_ts, session_close_ts
        )

        five_min = self._provenance(
            instrument_id, Timeframe.M5, five_min_candles,
            calendar=calendar, session_date=session_date, ctx=ctx,
            as_of=as_of, tzinfo=tzinfo,
        )
        fifteen_min = self._provenance(
            instrument_id, Timeframe.M15, fifteen_min_candles,
            calendar=calendar, session_date=session_date, ctx=ctx,
            as_of=as_of, tzinfo=tzinfo,
        )

        overall_quality, overall_reason = self._combine_quality(
            ctx, five_min.quality, fifteen_min.quality, latest_quote_ts
        )

        return SessionContext(
            instrument_id=instrument_id,
            session_date=session_date,
            exchange=exchange,
            timezone=str(tzinfo),
            as_of=as_of,
            session_type=ctx.session_type,
            phase=phase,
            session_open_ts=session_open_ts,
            session_close_ts=session_close_ts,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=remaining_seconds,
            latest_quote_ts=latest_quote_ts,
            five_min=five_min,
            fifteen_min=fifteen_min,
            data_quality=overall_quality,
            explanation=(
                f"{instrument_id} session {session_date.isoformat()}: phase={phase.value}, "
                f"5m={five_min.quality.value}, 15m={fifteen_min.quality.value} -> {overall_reason}"
            ),
        )

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _elapsed_remaining(
        as_of: datetime, open_ts: datetime | None, close_ts: datetime | None
    ) -> tuple[int | None, int | None]:
        if open_ts is None or close_ts is None:
            return None, None
        total = int((close_ts - open_ts).total_seconds())
        elapsed = int((as_of - open_ts).total_seconds())
        elapsed = max(0, min(total, elapsed))
        return elapsed, total - elapsed

    def _provenance(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        candles: Sequence[Candle],
        *,
        calendar: CalendarEngine,
        session_date: date,
        ctx: CalendarContext,
        as_of: datetime,
        tzinfo: ZoneInfo,
    ) -> TimeframeProvenance:
        if not ctx.is_trading_session:
            return TimeframeProvenance(
                instrument_id=instrument_id, timeframe=timeframe, session_date=session_date,
                as_of=as_of, window_start=None, window_end=None,
                latest_completed_bar_ts=None, bar_count=0,
                quality=SessionDataQualityStatus.SESSION_NOT_ACTIVE,
                explanation=(
                    f"{session_date.isoformat()} is not a trading session ({ctx.session_type.value})"
                ),
            )
        if not candles:
            return TimeframeProvenance(
                instrument_id=instrument_id, timeframe=timeframe, session_date=session_date,
                as_of=as_of, window_start=None, window_end=None,
                latest_completed_bar_ts=None, bar_count=0,
                quality=SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE,
                explanation=(
                    f"no {timeframe.value} candles exist for {instrument_id} at all"
                ),
            )
        today = [c for c in candles if c.ts_open.astimezone(tzinfo).date() == session_date]
        if not today:
            return TimeframeProvenance(
                instrument_id=instrument_id, timeframe=timeframe, session_date=session_date,
                as_of=as_of, window_start=None, window_end=None,
                latest_completed_bar_ts=None, bar_count=0,
                quality=SessionDataQualityStatus.NO_CURRENT_SESSION_DATA,
                explanation=(
                    f"{timeframe.value} history exists for {instrument_id}, "
                    f"but none for session {session_date.isoformat()}"
                ),
            )
        window_start = min(c.ts_open for c in today)
        window_end = max(c.ts_open for c in today)
        latest_completed = latest_completed_candle(today, timeframe, as_of=as_of)
        quality, explanation = self._timeframe_quality(
            timeframe, today, calendar=calendar, session_date=session_date,
            as_of=as_of, tzinfo=tzinfo,
        )
        return TimeframeProvenance(
            instrument_id=instrument_id, timeframe=timeframe, session_date=session_date,
            as_of=as_of, window_start=window_start, window_end=window_end,
            latest_completed_bar_ts=(latest_completed.ts_open if latest_completed else None),
            bar_count=len(today), quality=quality, explanation=explanation,
        )

    @staticmethod
    def _timeframe_quality(
        timeframe: Timeframe,
        today_candles: Sequence[Candle],
        *,
        calendar: CalendarEngine,
        session_date: date,
        as_of: datetime,
        tzinfo: ZoneInfo,
    ) -> tuple[SessionDataQualityStatus, str]:
        # `ctx.is_trading_session is False` is already handled by `_provenance`
        # before this is ever called -- no `ctx` param needed here.
        step = _TIMEFRAME_MINUTES[timeframe]
        expected = expected_intraday_opens(calendar, session_date, step, tzinfo)
        if not expected:
            return (
                SessionDataQualityStatus.INSUFFICIENT_HISTORY,
                f"a trading session but {timeframe.value} expectations are not computable "
                f"yet (open/close time not notified for {session_date.isoformat()})",
            )
        due = [ts for ts in expected if ts + timedelta(minutes=step) <= as_of]
        if not due:
            # Session has started but no bar is due-complete yet (e.g. right at
            # open) -- zero expected, zero missing, genuinely sufficient so far.
            return (
                SessionDataQualityStatus.SUFFICIENT,
                f"no {timeframe.value} bar is due complete yet as of {as_of.isoformat()}",
            )
        present = {c.ts_open for c in today_candles}
        missing = [ts for ts in due if ts not in present]
        if missing:
            return (
                SessionDataQualityStatus.EXPECTED_BAR_MISSING,
                f"{len(missing)}/{len(due)} expected {timeframe.value} bar(s) missing "
                f"as of {as_of.isoformat()}, earliest missing {missing[0].isoformat()}",
            )
        return (
            SessionDataQualityStatus.SUFFICIENT,
            f"all {len(due)} expected {timeframe.value} bar(s) present as of {as_of.isoformat()}",
        )

    @staticmethod
    def _combine_quality(
        ctx: CalendarContext,
        five_min_quality: SessionDataQualityStatus,
        fifteen_min_quality: SessionDataQualityStatus,
        latest_quote_ts: datetime | None,
    ) -> tuple[SessionDataQualityStatus, str]:
        """Deterministic combination: worse of the two timeframe qualities,
        by an explicit priority order (not enum declaration order), then
        quote availability. Documented, not left implicit."""
        priority = (
            SessionDataQualityStatus.SESSION_NOT_ACTIVE,
            SessionDataQualityStatus.TIMEFRAME_UNAVAILABLE,
            SessionDataQualityStatus.NO_CURRENT_SESSION_DATA,
            SessionDataQualityStatus.INSUFFICIENT_HISTORY,
            SessionDataQualityStatus.EXPECTED_BAR_MISSING,
            SessionDataQualityStatus.QUOTE_UNAVAILABLE,
            SessionDataQualityStatus.SUFFICIENT,
        )
        candidates = [five_min_quality, fifteen_min_quality]
        if latest_quote_ts is None and ctx.is_trading_session:
            candidates.append(SessionDataQualityStatus.QUOTE_UNAVAILABLE)
        worst = min(candidates, key=priority.index)
        return worst, f"combined from 5m={five_min_quality.value}, 15m={fifteen_min_quality.value}"
