"""Canonical symbol master domain objects (SU-1, ADR-011).

The catalogue of what *exists* on an exchange, kept separate from the record of
what has been *ingested* (`instruments`). Conflating those two is the defect
ADR-011 was written to fix: a symbol currently "exists" to ATHENA only once
somebody curates it into a candidate list.

Every classification here carries **provenance**. The broker dump cannot
distinguish an equity from a treasury bill — on NSE it types all ~10,000 rows
`EQ` and ships no series column — so any series or board this module reports is
inferred until an authoritative NSE source is obtained. Recording *how* a value
was derived is what keeps an inference from being read as a fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SeriesSource(str, Enum):
    """How a symbol's series was determined. Never assume; always record."""

    NSE_OFFICIAL = "nse_official"
    """From an authoritative NSE equity/series list. Not yet available."""
    INFERRED_SUFFIX = "inferred_suffix"
    """Derived from the trading-symbol suffix (``-SG``, ``-SM``, …). A good
    first cut and explicitly not a contract."""
    BROKER = "broker"
    """Taken from the broker feed. On NSE this is uninformative — every row is
    typed ``EQ`` — so it is used only when nothing better applies."""


class Board(str, Enum):
    """Listing board. A board, not a threshold — hence a first-class value.

    ADR-011 §2.2: modelling SME as a board rather than an eligibility filter is
    what makes including or excluding it a visible decision rather than an
    accident of some suffix rule.
    """

    MAINBOARD = "MAINBOARD"
    SME = "SME"
    UNKNOWN = "UNKNOWN"
    """Neither established nor guessed — reported honestly rather than defaulted
    to MAINBOARD, which would quietly promote SME scrips into the main universe."""


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    """One canonical exchange-listed symbol.

    Deliberately carries **no broker instrument token**. A token is one vendor's
    identifier, and embedding it in the canonical model would bind the symbol
    master to Kite — precisely the coupling ADR-002 keeps behind the provider
    Protocol. Token lookup stays a provider concern. (ADR-011's column sketch
    listed one; see the SU-1 review summary for why it was dropped.)
    """

    symbol: str
    """Bare trading symbol, e.g. ``RATNAVEER``."""
    exchange: str
    instrument_id: str
    """``exchange:symbol`` — the identity every other ATHENA module already uses."""
    name: str | None
    series: str
    """NSE series code as best established, e.g. ``EQ``, ``BE``, ``SM``, ``SG``."""
    series_source: SeriesSource
    board: Board
    lot_size: int
    tick_size: Decimal
    status: str
    first_seen: datetime
    """When this symbol first appeared in a catalogue snapshot."""
    last_seen: datetime
    """Most recent snapshot it appeared in — the basis for spotting delistings
    later, without deleting history."""
    source: str
    """Which catalogue produced the row, e.g. ``kite``."""
    classification_reason: str
    """Why this series and board were chosen, in words. Explainability applies to
    the catalogue too: a symbol excluded from a universe later must be traceable
    to a stated reason rather than to an opaque rule (ADR-005's principle)."""
