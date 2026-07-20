"""Cross-module Protocols (ATHENA-002 §7).

STRUCTURAL SAFETY: MarketDataProvider has NO order-placement methods, and none
may ever be added — order placement is impossible by construction (ADR-002,
ATHENA-000 non-objective 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import FrozenSet, List, Protocol, Tuple, runtime_checkable

from athena.domain.context import ContextDelta, PipelineContext
from athena.domain.enums import HealthStatus, Timeframe
from athena.domain.market import Candle, Instrument, MarketSnapshot, Quote


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """What a provider can actually serve — declared, not assumed."""

    timeframes: Tuple[Timeframe, ...]
    max_history_days: int
    supports_quotes: bool
    supports_market_snapshot: bool


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Provider-side health: freshness and rate-limit state."""

    status: HealthStatus
    detail: str
    last_data_ts: datetime | None = None


@runtime_checkable
class MarketDataProvider(Protocol):
    """Broker/data-vendor abstraction (ADR-002). Read-only by construction."""

    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    def instruments(self) -> List[Instrument]: ...

    def daily_candles(self, instrument_id: str, start: date, end: date) -> List[Candle]: ...

    def intraday_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> List[Candle]: ...

    def quotes(self, instrument_ids: List[str]) -> List[Quote]: ...

    def market_snapshot(self) -> MarketSnapshot: ...

    def health(self) -> ProviderHealth: ...


@runtime_checkable
class IntelligenceModule(Protocol):
    """The universal module contract (ATHENA-002 §7.1, ADR-003).

    Modules declare what they read and write; the orchestrator derives the
    DAG, validates it at startup, and can later re-evaluate only affected
    modules (event-driven evolution, §8.4) without touching module code.
    """

    name: str
    consumes: FrozenSet[str]
    produces: FrozenSet[str]

    def evaluate(self, ctx: PipelineContext) -> ContextDelta: ...
