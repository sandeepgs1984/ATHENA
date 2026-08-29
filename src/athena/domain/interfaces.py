"""Cross-module Protocols (ATHENA-002 §7).

STRUCTURAL SAFETY: MarketDataProvider has NO order-placement methods, and none
may ever be added — order placement is impossible by construction (ADR-002,
ATHENA-000 non-objective 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from athena.domain.context import ContextDelta, PipelineContext
from athena.domain.enums import HealthStatus, Timeframe
from athena.domain.market import Candle, Instrument, InstitutionalFlowSession, MarketSnapshot, Quote


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """What a provider can actually serve — declared, not assumed."""

    timeframes: tuple[Timeframe, ...]
    max_history_days: int
    supports_quotes: bool
    supports_market_snapshot: bool

    def __post_init__(self) -> None:
        if not self.timeframes:
            raise ValueError("ProviderCapabilities.timeframes must declare at least one timeframe")
        if len(set(self.timeframes)) != len(self.timeframes):
            raise ValueError(f"ProviderCapabilities.timeframes contains duplicates: {self.timeframes}")
        if self.max_history_days < 1:
            raise ValueError(f"ProviderCapabilities.max_history_days must be >= 1, got {self.max_history_days}")


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Provider-side health: freshness and rate-limit state."""

    status: HealthStatus
    detail: str
    last_data_ts: datetime | None = None

    def __post_init__(self) -> None:
        if not self.detail:
            raise ValueError("ProviderHealth.detail is mandatory — health always explains itself")
        if self.last_data_ts is not None and self.last_data_ts.tzinfo is None:
            raise ValueError("ProviderHealth.last_data_ts must be timezone-aware")


@runtime_checkable
class MarketDataProvider(Protocol):
    """Broker/data-vendor abstraction (ADR-002). Read-only by construction.

    BEHAVIORAL CONTRACT (enforced by tests/contract/provider_contract.py —
    every implementation must pass the suite unchanged, ATHENA-002 §7.2):

    - Honesty: methods honor ``capabilities()``. Requests outside declared
      capabilities (unsupported timeframe, quotes when unsupported, …) raise
      ``ProviderError`` with a human-readable reason — never guess, never
      silently return empty.
    - Candles: sorted ascending by ``ts_open``, no duplicate timestamps,
      strictly within the requested range, tagged with the requested
      instrument and timeframe; timestamps timezone-aware. Daily candle
      ranges are inclusive of both endpoints.
    - Emptiness is not an error: a valid range containing no data returns
      an empty list.
    - Quotes: returned only for requested instrument ids, one per id at most.
    - Determinism: identical requests return identical results within a
      provider session (live providers may append new data over time, but
      historical ranges never mutate).
    - Unknown instrument ids raise ``ProviderError`` naming the id.
    - NO ORDER METHODS: implementations must not add order/trade placement
      of any kind; the contract suite rejects providers exposing any.
    """

    name: str

    def capabilities(self) -> ProviderCapabilities: ...

    def instruments(self) -> list[Instrument]: ...

    def daily_candles(self, instrument_id: str, start: date, end: date) -> list[Candle]: ...

    def intraday_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]: ...

    def quotes(self, instrument_ids: list[str]) -> list[Quote]: ...

    def market_snapshot(self) -> MarketSnapshot: ...

    def health(self) -> ProviderHealth: ...


@runtime_checkable
class InstitutionalFlowProvider(Protocol):
    """FII/DII cash-flow source (ADR-008 / DD-11). Read-only by construction.

    Separate from MarketDataProvider — institutional reports are not quotes/candles.
    NO ORDER METHODS. Engines consume persisted rows; adapters may perform I/O.
    """

    name: str

    def latest_session(self) -> InstitutionalFlowSession: ...

    def sessions(self, start: date, end: date) -> list[InstitutionalFlowSession]: ...

    def health(self) -> ProviderHealth: ...


@runtime_checkable
class IntelligenceModule(Protocol):
    """DORMANT/LEGACY (ADR-003 Amendment 1, ID-P0, 2026-08-29) — do not implement.

    Originally the universal module contract (ATHENA-002 §7.1, ADR-003).
    ID-0's runtime audit found no analytical engine implements this Protocol
    anywhere in production code. ATHENA's canonical live pipeline mechanism
    is ``athena.runtime.workflow.WorkflowStage`` — a stage declares
    ``depends_on``/``produces`` and a ``run(ctx) -> Mapping`` callable
    instead. See ADR-003 Amendment 1 for the canonical rule for new stages;
    do not implement this Protocol for any new production stage.
    """

    name: str
    consumes: frozenset[str]
    produces: frozenset[str]

    def evaluate(self, ctx: PipelineContext) -> ContextDelta: ...
