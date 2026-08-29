"""Gap Engine (ID-5C).

Computes `GapContext` from already-resolved prices — no I/O, no clock
reads, no provider/repository access of any kind. The caller (a workflow
stage) is responsible for resolving `previous_session_date`/
`previous_session_close`/`current_session_open` from the calendar and
already-fetched daily candle history; this engine only does the
arithmetic and honesty checks. See `gap_models` for the full contract
rationale.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from athena.intraday.gap_models import GapContext, GapDirection


class GapEngine:
    """Deterministic, replayable GapContext — measurement only."""

    def assess(
        self,
        instrument_id: str,
        *,
        as_of: datetime,
        session_date: date,
        previous_session_date: date | None,
        previous_session_close: Decimal | None,
        current_session_open: Decimal | None,
    ) -> GapContext:
        if as_of.tzinfo is None:
            raise ValueError("GapEngine.assess as_of must be timezone-aware")

        if previous_session_date is None or previous_session_close is None:
            return self._unavailable(
                instrument_id, session_date, as_of, previous_session_date,
                previous_session_close, current_session_open,
                "previous trading-session close is unavailable "
                + (
                    f"(no settled D1 candle for {previous_session_date.isoformat()})"
                    if previous_session_date is not None
                    else "(no prior trading session could be resolved from the calendar)"
                ),
            )
        if current_session_open is None:
            return self._unavailable(
                instrument_id, session_date, as_of, previous_session_date,
                previous_session_close, current_session_open,
                f"current session's own opening price is not available yet "
                f"(no D1 candle for {session_date.isoformat()} yet)",
            )
        if previous_session_close == 0:
            return self._unavailable(
                instrument_id, session_date, as_of, previous_session_date,
                previous_session_close, current_session_open,
                f"previous session ({previous_session_date.isoformat()}) close is zero "
                f"-- a gap percentage cannot be computed",
            )

        gap_pct = (current_session_open - previous_session_close) / previous_session_close * Decimal(100)
        if gap_pct > 0:
            direction = GapDirection.GAP_UP
        elif gap_pct < 0:
            direction = GapDirection.GAP_DOWN
        else:
            direction = GapDirection.FLAT

        return GapContext(
            instrument_id=instrument_id, session_date=session_date, as_of=as_of,
            previous_session_date=previous_session_date,
            previous_session_close=previous_session_close,
            current_session_open=current_session_open,
            gap_pct=gap_pct, direction=direction, available=True,
            explanation=(
                f"{instrument_id} opened {current_session_open} on {session_date.isoformat()} "
                f"vs previous trading-session ({previous_session_date.isoformat()}) close "
                f"{previous_session_close}: {gap_pct}% ({direction.value})"
            ),
        )

    @staticmethod
    def _unavailable(
        instrument_id: str, session_date: date, as_of: datetime,
        previous_session_date: date | None, previous_session_close: Decimal | None,
        current_session_open: Decimal | None, reason: str,
    ) -> GapContext:
        return GapContext(
            instrument_id=instrument_id, session_date=session_date, as_of=as_of,
            previous_session_date=previous_session_date,
            previous_session_close=previous_session_close,
            current_session_open=current_session_open,
            gap_pct=None, direction=GapDirection.UNKNOWN, available=False,
            explanation=f"{instrument_id} gap unavailable: {reason}",
        )
