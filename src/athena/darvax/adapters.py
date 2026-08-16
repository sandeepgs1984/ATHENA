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

    def __init__(self, repo: SqliteRepository, *, universe: str | None = None) -> None:
        self._repo = repo
        #: Optional ATHENA universe to discover over (SU-6). ``None`` keeps the
        #: original behaviour — every ingested instrument.
        self._universe = universe

    def list_instruments(self) -> Sequence[Instrument]:
        """Instruments DarvaX may discover over.

        With a universe configured, membership is read from ATHENA's
        *materialised* resolution — plain rows, exactly like candles. DarvaX
        calls no resolver and imports no ATHENA logic, which is what keeps
        ADR-011's wider universe available without widening ADR-010's pinned
        import surface.

        The universe is **intersected with ingested instruments**, because a
        symbol with no candles cannot be screened. Membership without data is a
        coverage gap for SU-5's planner to report, not something to hand the
        engine and let it fail per symbol.
        """
        ingested = self._repo.list_instruments()
        if self._universe is None:
            return ingested
        allowed = set(self._repo.list_resolved_universe(self._universe))
        if not allowed:
            # An unresolved universe means "nobody has resolved this yet", not
            # "no symbols qualify". Returning everything would silently ignore
            # the configured scope, so return nothing and let the caller's own
            # empty-result handling surface it.
            return []
        return [i for i in ingested if i.instrument_id in allowed]

    def with_universe(self, universe: str | None) -> SqliteMarketDataAdapter:
        """A copy scoped to an ATHENA universe.

        Applied by DarvaX's own app from DarvaX's own config, never by the mount
        seam: ATHENA reads exactly one key from `darvax.json` (`enabled`), and
        having it read a universe name would breach that boundary for no gain.
        """
        return SqliteMarketDataAdapter(self._repo, universe=universe)

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
