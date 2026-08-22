"""Bounded retry/backoff for transient provider failures (EM-1r3 production capture).

``UrllibKiteTransport`` already retries HTTP 429 (rate-limit) responses with
exponential backoff and paces every request against
``historical_min_interval_seconds`` -- this module does not duplicate that.
It exists for the failure class the transport does NOT retry: network-level
failures (``urllib.error.URLError`` -- timeouts, connection resets, DNS
failures) and 5xx server errors, both wrapped as ``ProviderError`` by the
time they reach ``intraday_candles`` and therefore only distinguishable by
message, not by exception type. A 4xx error (other than 429, already
retried by the transport) is treated as permanent -- retrying a bad
request or an auth failure cannot fix it, and retrying blindly would just
burn API quota on the owner's live Kite session for no benefit.

Never used by EM-1r3's own core contract (``intraday_reconstruction.py``,
``intraday_reconstruction_ingestion.py``) -- both remain exactly as
approved. This wraps only the provider a production capture run hands to
that unmodified service.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

from athena.domain.enums import Timeframe
from athena.domain.interfaces import MarketDataProvider, ProviderCapabilities, ProviderHealth
from athena.domain.market import Candle, Instrument, MarketSnapshot, Quote
from athena.errors import ProviderError

_TRANSIENT_MESSAGE_PATTERNS = (
    re.compile(r"kite network failure", re.IGNORECASE),
    re.compile(r"kite HTTP 5\d\d", re.IGNORECASE),
)


def is_transient_provider_error(exc: ProviderError) -> bool:
    """A network-level failure or a 5xx response -- worth one more try.

    Everything else (4xx other than 429, malformed-response errors, an
    unsupported-timeframe/unknown-instrument logic error) is permanent:
    retrying cannot change the outcome, and treating it as retryable would
    only burn real API calls against the owner's live session.
    """

    message = str(exc)
    return any(pattern.search(message) for pattern in _TRANSIENT_MESSAGE_PATTERNS)


@dataclass
class RetryStats:
    """Mutable counters a production capture run reads after the fact."""

    requests_attempted: int = 0
    retries_performed: int = 0
    permanent_failures: int = 0
    retry_exhausted_failures: int = 0


@dataclass
class RetryingMarketDataProvider:
    """Wraps a real ``MarketDataProvider``, retrying only ``intraday_candles``
    (the sole method EM-1r3's capture path calls) on transient failure.

    Every other method is a pure pass-through -- this is a narrow,
    single-purpose wrapper for one production campaign, not a general
    resilience layer other callers should reach for.
    """

    inner: MarketDataProvider
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    sleep: Callable[[float], None] = field(default=time.sleep)
    stats: RetryStats = field(default_factory=RetryStats)

    @property
    def name(self) -> str:
        return self.inner.name

    def capabilities(self) -> ProviderCapabilities:
        return self.inner.capabilities()

    def instruments(self) -> list[Instrument]:
        return self.inner.instruments()

    def daily_candles(self, instrument_id: str, start: date, end: date) -> list[Candle]:
        return self.inner.daily_candles(instrument_id, start, end)

    def intraday_candles(
        self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        attempt = 0
        while True:
            self.stats.requests_attempted += 1
            try:
                return self.inner.intraday_candles(instrument_id, timeframe, start, end)
            except ProviderError as exc:
                if not is_transient_provider_error(exc) or attempt >= self.max_retries:
                    if is_transient_provider_error(exc):
                        self.stats.retry_exhausted_failures += 1
                    else:
                        self.stats.permanent_failures += 1
                    raise
                attempt += 1
                self.stats.retries_performed += 1
                self.sleep(self.backoff_base_seconds * (2 ** (attempt - 1)))

    def quotes(self, instrument_ids: list[str]) -> list[Quote]:
        return self.inner.quotes(instrument_ids)

    def market_snapshot(self) -> MarketSnapshot:
        return self.inner.market_snapshot()

    def health(self) -> ProviderHealth:
        return self.inner.health()
