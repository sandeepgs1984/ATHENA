"""Market-side canonical objects (ATHENA-002 §4). Frozen, pure, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Mapping, Optional, Tuple

from athena.domain.enums import SessionType, Timeframe


@dataclass(frozen=True, slots=True)
class Instrument:
    """Tradable security identity."""

    instrument_id: str
    symbol: str
    exchange: str
    series: str
    isin: Optional[str] = None
    lot_size: int = 1
    tick_size: Decimal = Decimal("0.05")
    status: str = "ACTIVE"
    listed_date: Optional[date] = None
    delisted_date: Optional[date] = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Instrument.symbol must be non-empty")
        if self.lot_size < 1:
            raise ValueError(f"Instrument.lot_size must be >= 1, got {self.lot_size}")


@dataclass(frozen=True, slots=True)
class Candle:
    """OHLCV bar. Prices are Decimal; timestamps are timezone-aware IST."""

    instrument_id: str
    timeframe: Timeframe
    ts_open: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str
    adjusted: bool = False

    def __post_init__(self) -> None:
        if self.ts_open.tzinfo is None:
            raise ValueError("Candle.ts_open must be timezone-aware")
        if self.volume < 0:
            raise ValueError(f"Candle.volume must be >= 0, got {self.volume}")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError(
                f"Impossible OHLC for {self.instrument_id} at {self.ts_open}: "
                f"O={self.open} H={self.high} L={self.low} C={self.close}"
            )


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """Split / bonus / dividend / rename — required for point-in-time correctness (Q-4)."""

    action_id: str
    instrument_id: str
    action_type: str
    ex_date: date
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    """A scheduled market-moving event (budget, RBI policy, election, …)."""

    event_date: date
    kind: str
    name: str


@dataclass(frozen=True, slots=True)
class CalendarContext:
    """Today's market awareness (R-3). Produced only by the Calendar Engine."""

    context_date: date
    session_type: SessionType
    exchange: str
    timezone: str
    open_time: Optional[time]
    close_time: Optional[time]
    holiday_name: Optional[str] = None
    is_weekly_expiry: bool = False
    is_monthly_expiry: bool = False
    events: Tuple[CalendarEvent, ...] = ()

    @property
    def is_trading_session(self) -> bool:
        return self.session_type in (SessionType.NORMAL, SessionType.MUHURAT, SessionType.SPECIAL)


@dataclass(frozen=True, slots=True)
class Quote:
    """Point-in-time quote snapshot from a provider poll."""

    instrument_id: str
    ts: datetime
    last_price: Decimal
    volume: int
    source: str

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("Quote.ts must be timezone-aware")


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Index-level market state at a moment."""

    ts: datetime
    indices: Mapping[str, Decimal]
    breadth_advances: int = 0
    breadth_declines: int = 0
    india_vix: Optional[Decimal] = None

    def __post_init__(self) -> None:
        if self.ts.tzinfo is None:
            raise ValueError("MarketSnapshot.ts must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SectorSnapshot:
    """Sector-level state at a moment."""

    ts: datetime
    sector: str
    relative_strength: Decimal
    leaders: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketHealthScore:
    """Market quality (F-5): consumed by scoring, confidence, risk, decision."""

    ts: datetime
    components: Mapping[str, int]
    total: int
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("MarketHealthScore.explanation is mandatory (ATHENA-000 p9)")
        if not 0 <= self.total <= 100:
            raise ValueError(f"MarketHealthScore.total must be 0..100, got {self.total}")


@dataclass(frozen=True, slots=True)
class SectorHealthScore:
    """Sector quality (F-6): consumed before individual stock evaluation."""

    ts: datetime
    sector: str
    components: Mapping[str, int]
    total: int
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("SectorHealthScore.explanation is mandatory (ATHENA-000 p9)")
        if not 0 <= self.total <= 100:
            raise ValueError(f"SectorHealthScore.total must be 0..100, got {self.total}")


@dataclass(frozen=True, slots=True)
class RegimeAssessment:
    """Output of the Market Regime Engine (R-2). Labels are config-defined strings."""

    assessment_id: str
    ts: datetime
    labels: Tuple[str, ...]
    evidence_ids: Tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.labels:
            raise ValueError("RegimeAssessment.labels must be non-empty")
        if not self.explanation:
            raise ValueError("RegimeAssessment.explanation is mandatory (ATHENA-000 p9)")


@dataclass(frozen=True, slots=True)
class UniverseMember:
    """One instrument in today's universe, with the trace of WHY it was included (R-4)."""

    instrument_id: str
    inclusion_trace: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.inclusion_trace:
            raise ValueError("UniverseMember.inclusion_trace is mandatory — no unexplained inclusions")


@dataclass(frozen=True, slots=True)
class Universe:
    """Today's trading universe (R-4). Scanners consume only this."""

    universe_id: str
    universe_date: date
    cycle_id: str
    members: Tuple[UniverseMember, ...]
