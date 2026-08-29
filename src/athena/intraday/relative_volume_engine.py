"""Relative Volume Engine (ID-5D).

Computes `RelativeVolumeContext` — cumulative same-time-of-day relative
volume — from one instrument's already-fetched multi-session M5 candle
history. No network/repository/provider access, no clock reads (matches
`OpeningRangeEngine`/`RelativeStrengthEngine`'s own established pattern:
`calendar`/`tzinfo` are pure, already-loaded config data, not I/O).

Reuses, never duplicates:
- `athena.session.completed_candles`/`canonical_slot_candles` (ID-1/
  ID-2.1/ID-3.1) — no forming bar, and no off-grid/unexpected timestamp,
  may enter either the current session's cumulative volume or any
  historical session's comparison figure.
- `data.validation.calendar_expectations.expected_intraday_opens` for each
  session's own canonical M5 grid (handles a special session's different
  duration/structure without any hardcoded clock literal).
- `athena.session.session_open_close_ts` for each historical session's
  own open/close instants (never assumes every day shares today's open
  time).

Same-time-of-day alignment (§9): if today has N canonical completed bars
since its own open, a historical session is comparable only if it (a) has
at least N canonical expected slots in its OWN session and (b) has EVERY
ONE of its own first N canonical slots genuinely present. Any historical
session failing either check is excluded entirely from the baseline —
never partial-credited, never forced in with a shorter window. Point-in-
time safety is structural: only sessions with `session_date < session_date`
(the target) are ever considered, by construction, not by a caller-trusted
filter.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.data.validation.calendar_expectations import expected_intraday_opens
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday.relative_volume_models import RelativeVolumeContext, RelativeVolumeRelation
from athena.session.engine import canonical_slot_candles, completed_candles, session_open_close_ts
from athena.session.models import SessionContext, SessionPhase

_BAR_STEP_MINUTES = 5  # RVOL is defined over 5m bars only, matching ORB's/RS's scope


class RelativeVolumeEngine:
    """Deterministic, replayable RelativeVolumeContext — measurement only."""

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        session_context: SessionContext,
        five_min_candles: Sequence[Candle],
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
    ) -> RelativeVolumeContext:
        if as_of.tzinfo is None:
            raise ValueError("RelativeVolumeEngine.assess as_of must be timezone-aware")

        session_date = session_context.session_date
        if (
            session_context.phase is SessionPhase.NOT_A_TRADING_SESSION
            or session_context.session_open_ts is None
        ):
            return self._unavailable(
                instrument_id, session_date, as_of, None, None, None, 0, (),
                f"{session_date.isoformat()} is not a trading session or its open "
                "time is not notified yet",
            )

        completed = completed_candles(five_min_candles, Timeframe.M5, as_of=as_of)
        by_date: dict[date, list[Candle]] = {}
        for c in completed:
            by_date.setdefault(c.ts_open.date(), []).append(c)

        current_canonical = sorted(
            canonical_slot_candles(
                by_date.get(session_date, []), Timeframe.M5, _BAR_STEP_MINUTES,
                session_open_ts=session_context.session_open_ts,
                session_close_ts=session_context.session_close_ts,
                calendar=calendar, session_date=session_date, tzinfo=tzinfo,
            ),
            key=lambda c: c.ts_open,
        )
        bar_count = len(current_canonical)
        start_ts = session_context.session_open_ts

        if bar_count == 0:
            return self._unavailable(
                instrument_id, session_date, as_of, start_ts, None, None, 0, (),
                "current session has no canonical completed M5 bars yet",
            )

        current_cumulative = sum(c.volume for c in current_canonical)
        cutoff_ts = current_canonical[-1].ts_open

        # Same-time-of-day baseline: every candidate day strictly before
        # session_date, by construction -- no look-ahead is possible here.
        historical_pairs: list[tuple[date, int]] = []
        for d, day_candles in by_date.items():
            if d >= session_date:
                continue
            d_ctx = calendar.context_for(d)
            d_open_ts, d_close_ts = session_open_close_ts(d_ctx, session_date=d, tzinfo=tzinfo)
            if d_open_ts is None or d_close_ts is None:
                continue
            expected_d = sorted(expected_intraday_opens(calendar, d, _BAR_STEP_MINUTES, tzinfo))
            if len(expected_d) < bar_count:
                continue  # a shorter/special session cannot host today's comparison window
            needed = expected_d[:bar_count]
            d_canonical = canonical_slot_candles(
                day_candles, Timeframe.M5, _BAR_STEP_MINUTES,
                session_open_ts=d_open_ts, session_close_ts=d_close_ts,
                calendar=calendar, session_date=d, tzinfo=tzinfo,
            )
            present_by_ts = {c.ts_open: c for c in d_canonical}
            if not all(ts in present_by_ts for ts in needed):
                continue  # exact comparability only -- never partial-credited
            historical_pairs.append((d, sum(present_by_ts[ts].volume for ts in needed)))

        baseline_dates = tuple(sorted(d for d, _ in historical_pairs))
        baseline_count = len(historical_pairs)

        if baseline_count == 0:
            return self._unavailable(
                instrument_id, session_date, as_of, start_ts, cutoff_ts,
                current_cumulative, bar_count, baseline_dates,
                "no comparable historical settled session is available",
            )

        historical_avg = Decimal(sum(v for _, v in historical_pairs)) / Decimal(baseline_count)
        if historical_avg == 0:
            return self._unavailable(
                instrument_id, session_date, as_of, start_ts, cutoff_ts,
                current_cumulative, bar_count, baseline_dates,
                "historical average cumulative volume is zero -- a ratio cannot be computed",
            )

        ratio = Decimal(current_cumulative) / historical_avg
        if ratio > 1:
            relation = RelativeVolumeRelation.ABOVE_BASELINE
        elif ratio < 1:
            relation = RelativeVolumeRelation.BELOW_BASELINE
        else:
            relation = RelativeVolumeRelation.AT_BASELINE

        return RelativeVolumeContext(
            instrument_id=instrument_id, session_date=session_date, as_of=as_of,
            comparison_start_ts=start_ts, comparison_cutoff_ts=cutoff_ts,
            current_cumulative_volume=current_cumulative, current_canonical_bar_count=bar_count,
            historical_average_cumulative_volume=historical_avg,
            baseline_session_count=baseline_count, baseline_session_dates=baseline_dates,
            rvol_ratio=ratio, relation=relation, available=True,
            explanation=(
                f"{instrument_id} cumulative volume {current_cumulative} through "
                f"{cutoff_ts.isoformat()} vs historical average {historical_avg} over "
                f"{baseline_count} comparable settled session(s): {ratio}x ({relation.value})"
            ),
        )

    @staticmethod
    def _unavailable(
        instrument_id: str, session_date: date, as_of: datetime,
        start_ts: datetime | None, cutoff_ts: datetime | None,
        current_cumulative: int | None, bar_count: int,
        baseline_dates: tuple[date, ...], reason: str,
    ) -> RelativeVolumeContext:
        return RelativeVolumeContext(
            instrument_id=instrument_id, session_date=session_date, as_of=as_of,
            comparison_start_ts=start_ts, comparison_cutoff_ts=cutoff_ts,
            current_cumulative_volume=current_cumulative, current_canonical_bar_count=bar_count,
            historical_average_cumulative_volume=None,
            baseline_session_count=len(baseline_dates), baseline_session_dates=baseline_dates,
            rvol_ratio=None, relation=RelativeVolumeRelation.UNKNOWN, available=False,
            explanation=f"{instrument_id} relative volume unavailable: {reason}",
        )
