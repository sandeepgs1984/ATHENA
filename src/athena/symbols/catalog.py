"""Build symbol-master records from a provider catalogue (SU-1, ADR-011).

Consumes ``Instrument`` objects — the frozen domain type every
``MarketDataProvider`` already returns — rather than a broker's raw CSV rows.
That keeps the symbol master **provider-independent** (ADR-002): a future
provider produces the same records without this module changing.

One consequence worth stating: the ``series`` a provider reports is ignored.
`KiteProvider` fabricates ``series="EQ"`` for every NSE row because the dump has
no series column, so trusting it would fill the master with a value that is
right for equities by accident and wrong for the ~7,000 rows that are not. The
series is re-derived from the trading symbol instead, and the record says so.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from athena.domain.market import Instrument
from athena.symbols.classify import classify_symbol
from athena.symbols.models import SymbolRecord


def build_symbol_records(
    instruments: Sequence[Instrument],
    *,
    observed_at: datetime,
    source: str,
    known_first_seen: Callable[[str], datetime | None] | None = None,
) -> tuple[SymbolRecord, ...]:
    """Turn a provider catalogue into canonical symbol records.

    Args:
        instruments: whatever the provider's ``instruments()`` returned.
        observed_at: snapshot timestamp — **injected, never read from a clock
            here**, so a rebuild over the same catalogue is reproducible.
        source: which catalogue this came from, e.g. ``"kite"``.
        known_first_seen: optional lookup of an existing ``first_seen`` for a
            symbol. Supplied so a re-run preserves the date a symbol was *first*
            catalogued instead of resetting it to today, which would erase the
            listing history the column exists to hold.
    """
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone-aware")

    records: list[SymbolRecord] = []
    for instrument in instruments:
        # An instrument with no tick size has no price increment, so it is not a
        # tradable listing and cannot be equity on any board — that is what keeps
        # index rows such as NIFTY 50 out of the board groups the discovery
        # universes are built from. Nothing new is fetched; the provider already
        # carries this.
        #
        # Deliberately *not* `lot_size`: the dump reports 0 for both on index
        # rows, but `Instrument` requires `lot_size >= 1`, so the provider clamps
        # it and that signal never arrives here.
        series, series_source, board, reason = classify_symbol(
            instrument.symbol, tradable=instrument.tick_size > 0
        )
        previous = known_first_seen(instrument.instrument_id) if known_first_seen else None
        records.append(
            SymbolRecord(
                symbol=instrument.symbol,
                exchange=instrument.exchange,
                instrument_id=instrument.instrument_id,
                name=instrument.name,
                series=series,
                series_source=series_source,
                board=board,
                lot_size=instrument.lot_size,
                tick_size=instrument.tick_size,
                status=instrument.status,
                first_seen=previous or observed_at,
                last_seen=observed_at,
                source=source,
                classification_reason=reason,
            )
        )
    return tuple(records)
