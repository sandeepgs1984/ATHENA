"""The narrow, read-only surface DarvaX is allowed to see of ATHENA (ADR-010 §3).

``DarvaxMarketDataPort`` is deliberately tiny and exposes **no write method of
any kind**. That makes "DarvaX never writes to ATHENA's database" a structural
property of the contract rather than a convention someone has to remember:
there is simply nothing on this Protocol that could mutate ATHENA state.

Anything DarvaX needs to persist goes to its own ``db/darvax.db`` through
``athena.darvax.store``, never through here.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument

#: Every method name this Protocol is permitted to expose. The DX-1 isolation
#: suite asserts the Protocol's actual members equal this set, so adding a
#: write-shaped method later fails the test rather than passing unnoticed.
DARVAX_MARKET_DATA_READ_METHODS: frozenset[str] = frozenset(
    {"list_instruments", "recent_candles", "candles_between"}
)


@runtime_checkable
class DarvaxMarketDataPort(Protocol):
    """Read-only view of ATHENA's persisted market data."""

    def list_instruments(self) -> Sequence[Instrument]:
        """Every instrument ATHENA currently knows about."""
        ...

    def recent_candles(
        self, instrument_id: str, timeframe: Timeframe, *, limit: int = 500
    ) -> Sequence[Candle]:
        """The most recent ``limit`` candles for one instrument, **oldest-first**.

        Order matters: DarvaX's primitives require chronological input and
        validate it. The underlying repository selects the newest N descending
        and then reverses them, so what arrives here is already chronological and
        must not be reversed again.
        """
        ...

    def candles_between(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Sequence[Candle]:
        """Candles for one instrument in an inclusive range, **oldest-first**."""
        ...
