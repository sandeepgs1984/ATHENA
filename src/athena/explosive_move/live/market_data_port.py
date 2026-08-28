"""EM-5's read-only view of ATHENA's canonical market data (ADR-012
Section 10) -- mirrors ``DarvaxMarketDataPort``/``SqliteMarketDataAdapter``
(`src/athena/darvax/ports.py`, `adapters.py`) exactly: a narrow
``Protocol`` over already-ingested ``SqliteRepository`` data, with no
write method of any kind, so "EM-5 never mutates ATHENA state" is a
structural property of the contract rather than a convention.

All bulk reads go through ``SqliteRepository.candles_for_instruments``
(one grouped query, chunked at ~500 -- never one query per symbol),
same as ``candle_coverage``'s own established pattern.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument

#: Every method name this Protocol is permitted to expose -- mirrors
#: DARVAX_MARKET_DATA_READ_METHODS's role: the isolation suite asserts
#: the Protocol's actual members equal this set, so a write-shaped
#: method added later fails the test rather than passing unnoticed.
EMR_MARKET_DATA_READ_METHODS: frozenset[str] = frozenset(
    {"list_instruments", "resolved_universe", "candles_for_instruments"}
)


@runtime_checkable
class EmrMarketDataPort(Protocol):
    """Read-only view of ATHENA's persisted market data, scoped to what
    EM-5's evidence assembly needs."""

    def list_instruments(self) -> Sequence[Instrument]:
        """Every instrument ATHENA currently knows about."""
        ...

    def resolved_universe(self, universe: str) -> Sequence[str]:
        """Instrument IDs materialised for a named ADR-011 universe,
        intersected with ingested instruments (a symbol with no candles
        cannot be scanned)."""
        ...

    def candles_for_instruments(
        self, instrument_ids: Sequence[str], timeframe: Timeframe, start: datetime, end: datetime,
    ) -> dict[str, list[Candle]]:
        """Candles for many instruments in one inclusive range, grouped
        by instrument -- one query (or a handful of chunked queries) per
        scan cycle, never one per symbol."""
        ...


class SqliteEmrMarketDataAdapter:
    """Implements ``EmrMarketDataPort`` over ATHENA's live repository.

    The only place EM-5 touches ATHENA's data layer. Owned by EMR (not
    by ATHENA), same coupling-direction discipline as DarvaX's own
    adapter: if EM-5 is deleted, this file goes with it and ATHENA is
    unchanged. Read-only -- holds no write handle; EM-5's own writes go
    to its own ``db/emr.db`` via ``athena.explosive_move.store``.
    """

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def list_instruments(self) -> Sequence[Instrument]:
        return self._repo.list_instruments()

    def resolved_universe(self, universe: str) -> Sequence[str]:
        ingested = {i.instrument_id for i in self._repo.list_instruments()}
        resolved = self._repo.list_resolved_universe(universe)
        return tuple(iid for iid in resolved if iid in ingested)

    def candles_for_instruments(
        self, instrument_ids: Sequence[str], timeframe: Timeframe, start: datetime, end: datetime,
    ) -> dict[str, list[Candle]]:
        return self._repo.candles_for_instruments(instrument_ids, timeframe, start, end)
