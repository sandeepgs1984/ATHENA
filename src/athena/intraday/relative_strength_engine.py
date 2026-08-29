"""Relative Strength Engine (ID-4).

Computes ``RelativeStrengthContext`` from already-fetched candle series for
one instrument, the market benchmark, and (if mapped) the instrument's
sector index — no I/O, no clock reads, no randomness. See
``relative_strength_models`` for the full contract rationale.

Common-cutoff design (ID-4 §4/§5): for each constituent, an "opening
reference" candle is the one whose ``ts_open`` is EXACTLY the session's own
open instant (never a later canonical bar substituted in — a genuinely
missing opening slot means that constituent's return is unavailable, not
approximated). ``comparison_cutoff_ts`` is the minimum of whichever
constituents' own latest canonical completed bar IS available; each
constituent's own "closing" point is then the latest of ITS canonical bars
at-or-before that cutoff. A constituent whose closing point does not
genuinely fall after its opening point (e.g. real production data where an
index's canonical M5 coverage is only its own first bar — see ID-4's
real-data audit) is honestly reported unavailable rather than emitting a
zero-duration, near-meaningless "return".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from athena.calendar.engine import CalendarEngine
from athena.domain.enums import Timeframe
from athena.domain.market import Candle
from athena.intraday.relative_strength_models import RelativeStrengthContext, RelativeStrengthRelation
from athena.session.engine import canonical_slot_candles, completed_candles
from athena.session.models import SessionContext, SessionPhase

_BAR_STEP_MINUTES = 5  # RS is defined over 5m bars only, matching ORB's scope


@dataclass(frozen=True, slots=True)
class _ConstituentSeries:
    opening: Candle | None
    canonical: list[Candle]


class RelativeStrengthEngine:
    """Deterministic, replayable RelativeStrengthContext — measurement only."""

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        session_context: SessionContext,
        sector: str | None,
        market_benchmark_id: str,
        sector_benchmark_id: str | None,
        stock_five_min_candles: Sequence[Candle],
        market_five_min_candles: Sequence[Candle],
        sector_five_min_candles: Sequence[Candle],
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
    ) -> RelativeStrengthContext:
        if as_of.tzinfo is None:
            raise ValueError("RelativeStrengthEngine.assess as_of must be timezone-aware")
        if not market_benchmark_id:
            raise ValueError("RelativeStrengthEngine.assess market_benchmark_id is mandatory")

        if (
            session_context.phase is SessionPhase.NOT_A_TRADING_SESSION
            or session_context.session_open_ts is None
        ):
            return self._unavailable(
                instrument_id, sector, market_benchmark_id, sector_benchmark_id,
                session_context, as_of,
                f"{session_context.session_date.isoformat()} is not a trading session "
                "or its open time is not notified yet",
            )

        stock = self._series(stock_five_min_candles, session_context, calendar, tzinfo, as_of)
        market = self._series(market_five_min_candles, session_context, calendar, tzinfo, as_of)
        sector_series = (
            self._series(sector_five_min_candles, session_context, calendar, tzinfo, as_of)
            if sector_benchmark_id
            else _ConstituentSeries(opening=None, canonical=[])
        )

        stock_latest = stock.canonical[-1].ts_open if stock.canonical else None
        market_latest = market.canonical[-1].ts_open if market.canonical else None
        sector_latest = sector_series.canonical[-1].ts_open if sector_series.canonical else None
        available_latests = [t for t in (stock_latest, sector_latest, market_latest) if t is not None]
        cutoff = min(available_latests) if available_latests else None

        stock_return = self._return(stock, cutoff)
        market_return = self._return(market, cutoff)
        sector_return = self._return(sector_series, cutoff)

        stock_vs_sector = self._diff(stock_return, sector_return)
        stock_vs_market = self._diff(stock_return, market_return)
        sector_vs_market = self._diff(sector_return, market_return)

        return RelativeStrengthContext(
            instrument_id=instrument_id, sector=sector,
            market_benchmark_id=market_benchmark_id, sector_benchmark_id=sector_benchmark_id,
            session_date=session_context.session_date, as_of=as_of,
            comparison_start_ts=session_context.session_open_ts, comparison_cutoff_ts=cutoff,
            stock_return_pct=stock_return, sector_return_pct=sector_return,
            market_return_pct=market_return,
            stock_vs_sector_pct=stock_vs_sector, stock_vs_market_pct=stock_vs_market,
            sector_vs_market_pct=sector_vs_market,
            stock_vs_sector_relation=self._relation(stock_vs_sector),
            stock_vs_market_relation=self._relation(stock_vs_market),
            sector_vs_market_relation=self._relation(sector_vs_market),
            stock_available=stock_return is not None,
            sector_available=sector_return is not None,
            market_available=market_return is not None,
            explanation=self._explain(
                instrument_id, sector, stock_return, sector_return, market_return,
                session_context.session_open_ts, cutoff,
            ),
        )

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _series(
        candles: Sequence[Candle],
        session_context: SessionContext,
        calendar: CalendarEngine,
        tzinfo: ZoneInfo,
        as_of: datetime,
    ) -> _ConstituentSeries:
        completed = completed_candles(candles, Timeframe.M5, as_of=as_of)
        canonical = sorted(
            canonical_slot_candles(
                completed, Timeframe.M5, _BAR_STEP_MINUTES,
                session_open_ts=session_context.session_open_ts,
                session_close_ts=session_context.session_close_ts,
                calendar=calendar, session_date=session_context.session_date, tzinfo=tzinfo,
            ),
            key=lambda c: c.ts_open,
        )
        opening = next(
            (c for c in canonical if c.ts_open == session_context.session_open_ts), None
        )
        return _ConstituentSeries(opening=opening, canonical=canonical)

    @staticmethod
    def _return(series: _ConstituentSeries, cutoff: datetime | None) -> Decimal | None:
        if series.opening is None or cutoff is None:
            return None
        closing = max(
            (c for c in series.canonical if c.ts_open <= cutoff),
            key=lambda c: c.ts_open, default=None,
        )
        if closing is None or closing.ts_open <= series.opening.ts_open:
            # No genuinely later mutually-comparable point yet -- a
            # zero-duration "return" off a single bar would be
            # near-meaningless, not a session-relative measurement.
            return None
        opening_price = series.opening.open
        if opening_price == 0:
            return None
        return (closing.close - opening_price) / opening_price * Decimal(100)

    @staticmethod
    def _diff(a: Decimal | None, b: Decimal | None) -> Decimal | None:
        return a - b if a is not None and b is not None else None

    @staticmethod
    def _relation(diff: Decimal | None) -> RelativeStrengthRelation:
        if diff is None:
            return RelativeStrengthRelation.UNKNOWN
        if diff > 0:
            return RelativeStrengthRelation.OUTPERFORMING
        if diff < 0:
            return RelativeStrengthRelation.UNDERPERFORMING
        return RelativeStrengthRelation.MATCHING

    @staticmethod
    def _explain(
        instrument_id: str, sector: str | None,
        stock_return: Decimal | None, sector_return: Decimal | None, market_return: Decimal | None,
        start_ts: datetime | None, cutoff: datetime | None,
    ) -> str:
        parts = [
            f"stock={stock_return}%" if stock_return is not None else "stock=unavailable",
            f"sector({sector})={sector_return}%"
            if sector_return is not None
            else f"sector({sector})=unavailable",
            f"market={market_return}%" if market_return is not None else "market=unavailable",
        ]
        window = (
            f"comparison {start_ts.isoformat()} -> {cutoff.isoformat()}"
            if start_ts is not None and cutoff is not None
            else "no mutually comparable window yet"
        )
        return f"{instrument_id} relative strength ({window}): " + "; ".join(parts)

    @staticmethod
    def _unavailable(
        instrument_id: str, sector: str | None, market_benchmark_id: str,
        sector_benchmark_id: str | None, session_context: SessionContext, as_of: datetime,
        reason: str,
    ) -> RelativeStrengthContext:
        unknown = RelativeStrengthRelation.UNKNOWN
        return RelativeStrengthContext(
            instrument_id=instrument_id, sector=sector,
            market_benchmark_id=market_benchmark_id, sector_benchmark_id=sector_benchmark_id,
            session_date=session_context.session_date, as_of=as_of,
            comparison_start_ts=None, comparison_cutoff_ts=None,
            stock_return_pct=None, sector_return_pct=None, market_return_pct=None,
            stock_vs_sector_pct=None, stock_vs_market_pct=None, sector_vs_market_pct=None,
            stock_vs_sector_relation=unknown, stock_vs_market_relation=unknown,
            sector_vs_market_relation=unknown,
            stock_available=False, sector_available=False, market_available=False,
            explanation=f"{instrument_id} relative strength unavailable: {reason}",
        )
