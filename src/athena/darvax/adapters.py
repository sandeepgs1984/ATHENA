"""DarvaX-owned adapter over ATHENA's repository (ADR-010 §3).

This is the *only* place DarvaX touches ATHENA's data layer, and it touches
exactly three read methods. The adapter is owned by DarvaX (not by ATHENA) so
that the coupling point stays on the satellite's side of the boundary: if
DarvaX is deleted, this file goes with it and ATHENA is unchanged.

The wrapped ``SqliteRepository`` is used for reads only. DarvaX holds no write
handle to ``db/athena.db`` — its own writes go to ``db/darvax.db`` via
``athena.darvax.store``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from athena.data.store.repository import SqliteRepository
from athena.domain.enums import Timeframe
from athena.domain.market import Candle, Instrument


class SqliteMarketDataAdapter:
    """Implements ``DarvaxMarketDataPort`` over ATHENA's live repository."""

    def __init__(self, repo: SqliteRepository) -> None:
        self._repo = repo

    def list_instruments(self) -> Sequence[Instrument]:
        return self._repo.list_instruments()

    def recent_candles(
        self, instrument_id: str, timeframe: Timeframe, *, limit: int = 500
    ) -> Sequence[Candle]:
        return self._repo.list_candles_recent(instrument_id, timeframe, limit=limit)

    def candles_between(
        self,
        instrument_id: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Sequence[Candle]:
        return self._repo.get_candles(instrument_id, timeframe, start, end)
