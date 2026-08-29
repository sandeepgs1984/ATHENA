"""Opening Range Engine (ID-3).

Answers: "what is this stock doing relative to its opening range right
now?" — descriptive only, never "should I enter." Computes OR15 and OR30
(first 15 / first 30 minutes of the regular session) as parallel evidence
windows; neither is treated as canonically superior here.

Reuses, never duplicates:
- ``SessionContext.session_open_ts`` (ID-1) as the sole window-start
  authority — never a hardcoded 09:15. Correctly varies for a real special
  session (e.g. a Sunday full-hours session); explicitly NOT_APPLICABLE/
  NOT_AVAILABLE when the calendar can't support it.
- ``athena.session.completed_candles``/``is_candle_completed`` (ID-1/ID-2.1)
  for the one authoritative completed-candle filter — no forming bar may
  alter a range's high/low, trigger a breakout, or change a relation.
- ``data.validation.calendar_expectations.expected_intraday_opens`` (already
  used by ID-1's own missing-bar detection) for `bars_expected` — the same
  calendar authority, not a second gap-detection scheme. ID-3.1: also used to
  build one canonical completed-session candle sequence up front (exact
  expected M5 slots only) — every downstream computation (formation,
  relation, breakout) derives from that one sequence, so an off-grid/
  unexpected timestamp can never substitute for a missing canonical slot or
  otherwise influence ORB evidence.

Pure and replayable: no I/O, no clock reads, no randomness — every input
(candles, `SessionContext`, `CalendarEngine`, `as_of`) is injected by the
caller, exactly like every other engine in this codebase.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.data.validation.calendar_expectations import expected_intraday_opens
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday.opening_range_models import (
    BreakoutEvent,
    OpeningRangeEvidence,
    OpeningRangeFormation,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
    OpeningRangeWindow,
)
from athena.session.engine import completed_candles
from athena.session.models import SessionContext, SessionPhase

_WINDOW_MINUTES = {OpeningRangeWindow.OR15: 15, OpeningRangeWindow.OR30: 30}
_BAR_STEP_MINUTES = 5  # ORB is defined over 5m bars only, per ID-3's scope


class OpeningRangeEngine:
    """Deterministic, replayable OR15/OR30 evidence — measurement only."""

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        session_context: SessionContext,
        five_min_candles: Sequence[Candle],
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
    ) -> dict[OpeningRangeWindow, OpeningRangeEvidence]:
        if as_of.tzinfo is None:
            raise ValueError("OpeningRangeEngine.assess as_of must be timezone-aware")
        completed = completed_candles(five_min_candles, Timeframe.M5, as_of=as_of)
        # ID-3.1 §7-10: one canonical completed-session sequence, filtered to
        # exact expected M5 opening slots, feeds EVERY downstream computation
        # (formation, relation, breakout) for both windows -- an off-grid/
        # unexpected timestamp (e.g. a settlement-drifted 09:43:55 instead of
        # the canonical 09:40:00) is excluded here, once, so it can never
        # substitute for a missing canonical slot, alter a range's high/low/
        # volume, or trigger a false breakout anywhere downstream.
        canonical = self._canonical_slots(completed, session_context, calendar, tzinfo)
        return {
            window: self._assess_window(
                window, instrument_id, as_of=as_of, session_context=session_context,
                completed=canonical, calendar=calendar, tzinfo=tzinfo,
            )
            for window in OpeningRangeWindow
        }

    @staticmethod
    def _canonical_slots(
        completed: Sequence[Candle],
        session_context: SessionContext,
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
    ) -> list[Candle]:
        """Restrict to candles whose ``ts_open`` is an exact expected M5
        opening slot for this session, per ``expected_intraday_opens`` (the
        same calendar authority ID-1's own missing-bar detection already
        trusts). Returns ``completed`` unfiltered when the session's own
        open/close aren't notified yet (e.g. an unconfirmed Muhurat) or the
        calendar can't compute expectations at all -- ``_formation``'s
        earlier NOT_APPLICABLE/NOT_AVAILABLE checks already return before any
        candle from this list is ever inspected in that case, so there is
        nothing to protect."""
        if session_context.session_open_ts is None or session_context.session_close_ts is None:
            return list(completed)
        expected = set(
            expected_intraday_opens(
                calendar, session_context.session_date, _BAR_STEP_MINUTES, tzinfo,
            )
        )
        if not expected:
            return list(completed)
        return [c for c in completed if c.ts_open in expected]

    # ------------------------------------------------------------- formation

    def _assess_window(
        self,
        window: OpeningRangeWindow,
        instrument_id: str,
        *,
        as_of: datetime,
        session_context: SessionContext,
        completed: Sequence[Candle],
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
    ) -> OpeningRangeEvidence:
        formation = self._formation(
            window, instrument_id, as_of=as_of, session_context=session_context,
            completed=completed, calendar=calendar, tzinfo=tzinfo,
        )
        if formation.status is not OpeningRangeFormationStatus.COMPLETE:
            return OpeningRangeEvidence(
                instrument_id=instrument_id, session_date=session_context.session_date,
                as_of=as_of, formation=formation,
                relation=OpeningRangeRelation.UNAVAILABLE,
                breakout_event=BreakoutEvent.NOT_OBSERVED,
                first_breakout_ts=None, bars_since_breakout=None,
                max_extension_from_range_pct=None, current_extension_pct=None,
                returned_inside_range=None,
                explanation=(
                    f"{instrument_id} {window.value}: relation/breakout unavailable — "
                    f"range status is {formation.status.value}, not COMPLETE"
                ),
            )

        post_range = sorted(
            (c for c in completed if c.ts_open >= formation.range_end),
            key=lambda c: c.ts_open,
        )
        # The range's own last bar anchors the first comparison, so a
        # breakout on the very first post-range bar is still detectable.
        range_bars = sorted(
            (c for c in completed if formation.range_start <= c.ts_open < formation.range_end),
            key=lambda c: c.ts_open,
        )
        anchor = range_bars[-1:] + list(post_range)

        relation = self._relation(anchor[-1].close if anchor else None, formation)
        (breakout_event, first_breakout_ts, bars_since, max_ext, cur_ext, returned_inside) = (
            self._breakout(anchor, formation)
        )

        return OpeningRangeEvidence(
            instrument_id=instrument_id, session_date=session_context.session_date, as_of=as_of,
            formation=formation, relation=relation, breakout_event=breakout_event,
            first_breakout_ts=first_breakout_ts, bars_since_breakout=bars_since,
            max_extension_from_range_pct=max_ext, current_extension_pct=cur_ext,
            returned_inside_range=returned_inside,
            explanation=(
                f"{instrument_id} {window.value}: relation={relation.value}, "
                f"breakout={breakout_event.value}"
            ),
        )

    def _formation(
        self,
        window: OpeningRangeWindow,
        instrument_id: str,
        *,
        as_of: datetime,
        session_context: SessionContext,
        completed: Sequence[Candle],
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
    ) -> OpeningRangeFormation:
        if session_context.phase is SessionPhase.NOT_A_TRADING_SESSION:
            return self._empty_formation(
                window, OpeningRangeFormationStatus.NOT_APPLICABLE,
                f"{session_context.session_date.isoformat()} is not a trading session",
            )
        if session_context.session_open_ts is None:
            return self._empty_formation(
                window, OpeningRangeFormationStatus.NOT_AVAILABLE,
                "a trading session, but its open time is not notified yet "
                "(e.g. an unconfirmed Muhurat) — opening-range expectations "
                "cannot be computed",
            )

        range_start = session_context.session_open_ts
        range_end = range_start + timedelta(minutes=_WINDOW_MINUTES[window])

        expected_opens = [
            ts for ts in expected_intraday_opens(
                calendar, session_context.session_date, _BAR_STEP_MINUTES, tzinfo,
            )
            if range_start <= ts < range_end
        ]
        bars_expected = len(expected_opens)
        window_bars = sorted(
            (c for c in completed if range_start <= c.ts_open < range_end),
            key=lambda c: c.ts_open,
        )
        bars_present = len(window_bars)

        high = low = high_ts = low_ts = range_width = range_width_pct = volume = None
        if window_bars:
            high_bar = max(window_bars, key=lambda c: c.high)
            low_bar = min(window_bars, key=lambda c: c.low)
            high, high_ts = high_bar.high, high_bar.ts_open
            low, low_ts = low_bar.low, low_bar.ts_open
            range_width = high - low
            range_width_pct = (range_width / low * Decimal(100)) if low > 0 else None
            volume = sum(c.volume for c in window_bars)

        if bars_expected == 0:
            status = OpeningRangeFormationStatus.NOT_AVAILABLE
            explanation = (
                f"{window.value} expectations are not computable from the calendar "
                f"for {session_context.session_date.isoformat()}"
            )
        elif as_of < range_end:
            status = OpeningRangeFormationStatus.FORMING
            explanation = (
                f"{window.value} window ({range_start.isoformat()}-{range_end.isoformat()}) "
                f"has not fully elapsed at {as_of.isoformat()} — {bars_present}/{bars_expected} "
                f"bar(s) so far"
            )
        elif bars_present >= bars_expected:
            status = OpeningRangeFormationStatus.COMPLETE
            explanation = (
                f"{window.value} window elapsed with all {bars_expected} expected bar(s) present"
            )
        else:
            status = OpeningRangeFormationStatus.INCOMPLETE_DATA
            present_ts = {c.ts_open for c in window_bars}
            missing = [ts for ts in expected_opens if ts not in present_ts]
            explanation = (
                f"{window.value} window elapsed with only {bars_present}/{bars_expected} "
                f"valid canonical bar(s) present ({len(missing)} expected slot(s) missing, "
                f"earliest missing {missing[0].isoformat()}) — not treated as a finished range"
            )

        return OpeningRangeFormation(
            window=window, range_start=range_start, range_end=range_end,
            high=high, low=low, high_ts=high_ts, low_ts=low_ts,
            range_width=range_width, range_width_pct=range_width_pct, volume=volume,
            bars_expected=bars_expected, bars_present=bars_present,
            status=status, explanation=explanation,
        )

    @staticmethod
    def _empty_formation(
        window: OpeningRangeWindow, status: OpeningRangeFormationStatus, reason: str,
    ) -> OpeningRangeFormation:
        return OpeningRangeFormation(
            window=window, range_start=None, range_end=None, high=None, low=None,
            high_ts=None, low_ts=None, range_width=None, range_width_pct=None, volume=None,
            bars_expected=None, bars_present=0, status=status,
            explanation=f"{window.value}: {reason}",
        )

    # -------------------------------------------------------------- relation

    @staticmethod
    def _relation(latest_close: Decimal | None, formation: OpeningRangeFormation) -> OpeningRangeRelation:
        if latest_close is None or formation.high is None or formation.low is None:
            return OpeningRangeRelation.UNAVAILABLE
        if latest_close == formation.high:
            return OpeningRangeRelation.AT_HIGH
        if latest_close == formation.low:
            return OpeningRangeRelation.AT_LOW
        if latest_close > formation.high:
            return OpeningRangeRelation.ABOVE_RANGE
        if latest_close < formation.low:
            return OpeningRangeRelation.BELOW_RANGE
        return OpeningRangeRelation.INSIDE_RANGE

    # -------------------------------------------------------------- breakout

    @staticmethod
    def _breakout(
        anchor: Sequence[Candle], formation: OpeningRangeFormation,
    ) -> tuple[BreakoutEvent, datetime | None, int | None, Decimal | None, Decimal | None, bool | None]:
        if len(anchor) < 2 or formation.high is None or formation.low is None:
            return BreakoutEvent.NOT_OBSERVED, None, None, None, None, None

        high, low = formation.high, formation.low
        event = BreakoutEvent.NO_EVENT
        first_ts: datetime | None = None
        for prev, curr in itertools.pairwise(anchor):
            if event is not BreakoutEvent.NO_EVENT:
                break
            if prev.close <= high and curr.close > high:
                event, first_ts = BreakoutEvent.UPSIDE_BREAKOUT_EVENT, curr.ts_open
            elif prev.close >= low and curr.close < low:
                event, first_ts = BreakoutEvent.DOWNSIDE_BREAKDOWN_EVENT, curr.ts_open

        if event is BreakoutEvent.NO_EVENT:
            return BreakoutEvent.NO_EVENT, None, None, None, None, None

        post_breakout = [c for c in anchor if c.ts_open >= first_ts]
        bars_since = len(post_breakout) - 1
        latest = anchor[-1]
        if event is BreakoutEvent.UPSIDE_BREAKOUT_EVENT:
            extensions = [(c.close - high) / high * Decimal(100) for c in post_breakout]
            current_extension = (latest.close - high) / high * Decimal(100)
            returned_inside = any(c.close <= high for c in post_breakout[1:])
        else:
            extensions = [(low - c.close) / low * Decimal(100) for c in post_breakout]
            current_extension = (low - latest.close) / low * Decimal(100)
            returned_inside = any(c.close >= low for c in post_breakout[1:])
        max_extension = max(extensions)

        return event, first_ts, bars_since, max_extension, current_extension, returned_inside
