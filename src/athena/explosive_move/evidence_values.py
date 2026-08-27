"""Shared evidence-value type + daily-bar derivation for EM-2. Pure, no I/O.

``DailyBar`` is EM-2's own per-session OHLCV aggregate, deliberately
derived from EM-1r3's already-audited M5 intraday evidence rather than
read from the canonical `candles` D1 table (whose provenance has not
been through this workstream's acquisition/validation rigor) -- see the
EM-2 Evidence Contract Proposal's warm-up discussion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from athena.domain.market import Candle


@dataclass(frozen=True, slots=True)
class EvidenceValue:
    """A single evidence field's outcome: either a value, or an explicit,
    persisted reason it is UNKNOWN. Never both; never a silent None."""

    value: Decimal | str | None
    unknown_reason: str | None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.unknown_reason is None):
            raise ValueError("EvidenceValue must set exactly one of value / unknown_reason")

    @staticmethod
    def known(value: Decimal | str) -> EvidenceValue:
        return EvidenceValue(value=value, unknown_reason=None)

    @staticmethod
    def unknown(reason: str) -> EvidenceValue:
        return EvidenceValue(value=None, unknown_reason=reason)

    @property
    def is_known(self) -> bool:
        return self.value is not None


@dataclass(frozen=True, slots=True)
class DailyBar:
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def daily_bar_from_session_candles(session_date: date, m5_candles: tuple[Candle, ...]) -> DailyBar:
    """Derive one session's OHLCV daily bar from its own M5 intraday
    candles. Caller supplies exactly one session's candles (any ordering);
    this raises on an empty input rather than silently returning a
    degenerate bar."""

    if not m5_candles:
        raise ValueError(f"no candles supplied for session {session_date.isoformat()}")
    ordered = tuple(sorted(m5_candles, key=lambda c: c.ts_open))
    return DailyBar(
        session_date=session_date,
        open=ordered[0].open,
        high=max(c.high for c in ordered),
        low=min(c.low for c in ordered),
        close=ordered[-1].close,
        volume=sum(c.volume for c in ordered),
    )
