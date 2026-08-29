"""Relative Strength Context (ID-4).

Answers: "how is this stock performing intraday relative to its sector and
the broader market at this exact point in the session?" — descriptive
only, never "should I enter." A point-in-time COMPARATIVE MEASUREMENT, not
a market -> sector -> stock causal/gating chain, and NOT RSI (Relative
Strength Index) — this is price relative PERFORMANCE over a common
interval, i.e. stock session return vs. sector/market session return over
the same comparison window.

Reuses, never duplicates:
- ``SessionContext.session_open_ts``/``session_close_ts``/``session_date``
  (ID-1) — session semantics are identical for every instrument AND every
  index on a given trading day, so the stock's own ``SessionContext``
  governs the market benchmark's and the sector index's canonical
  filtering here too. No second session concept.
- ``athena.session.completed_candles``/``canonical_slot_candles`` (ID-1/
  ID-2.1/ID-3.1) as the one authoritative completed + canonical-slot
  filter for all three constituents — no forming bar, and no off-grid/
  unexpected timestamp, may enter a return calculation.
- The market benchmark identity already resolved once per run for regime
  (``OwnerValidationPipeline._resolve_index_candles``) and the existing
  ``Instrument.sector`` -> ``config/sector_index_mapping.json`` ->
  ``config/index_intelligence.json`` chain already used by
  ``SectorHealthEngine`` (SD-2/SD-3/ID-P0) — no second benchmark config,
  no second sector mapping.

Pure, immutable, explainable (ADR-005). No BUY/SELL, no probability, no
composite/ranked RS score, no STRONG/WEAK band — only the sign of the raw
differential (``RelativeStrengthRelation``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique


@unique
class RelativeStrengthRelation(str, Enum):
    """Zero-threshold sign-of-differential relation — deliberately no
    STRONGLY_OUTPERFORMING/band methodology. Presentation-layer threshold
    conventions elsewhere in ATHENA are NOT imported into this analytical
    contract (ID-4 §10). ``UNKNOWN`` is never treated as, or substituted
    with, ``MATCHING`` — it means the underlying differential could not be
    computed, not that it was computed as zero."""

    OUTPERFORMING = "OUTPERFORMING"
    UNDERPERFORMING = "UNDERPERFORMING"
    MATCHING = "MATCHING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RelativeStrengthContext:
    """Point-in-time price relative-performance evidence for one instrument
    — NOT RSI, NOT a scoring input, NOT a Decision gate, NOT a composite or
    cross-sectional ranking. Each of stock/sector/market is independently
    available or not (``*_available``); an unavailable dimension reports
    ``None``/``UNKNOWN`` explicitly rather than a fabricated zero, and does
    not prevent the OTHER two dimensions' own differential from being
    computed when both of ITS operands are available.

    ``comparison_start_ts``/``comparison_cutoff_ts`` are the single window
    every available return was measured over — the latest point all
    contributing constituents genuinely have in common, never an
    asynchronous per-constituent endpoint (ID-4 §4/§5)."""

    instrument_id: str
    sector: str | None
    market_benchmark_id: str
    sector_benchmark_id: str | None
    session_date: date
    as_of: datetime

    comparison_start_ts: datetime | None
    comparison_cutoff_ts: datetime | None

    stock_return_pct: Decimal | None
    sector_return_pct: Decimal | None
    market_return_pct: Decimal | None

    stock_vs_sector_pct: Decimal | None
    stock_vs_market_pct: Decimal | None
    sector_vs_market_pct: Decimal | None

    stock_vs_sector_relation: RelativeStrengthRelation
    stock_vs_market_relation: RelativeStrengthRelation
    sector_vs_market_relation: RelativeStrengthRelation

    stock_available: bool
    sector_available: bool
    market_available: bool

    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("RelativeStrengthContext.instrument_id is mandatory")
        if not self.market_benchmark_id:
            raise ValueError("RelativeStrengthContext.market_benchmark_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("RelativeStrengthContext.as_of must be timezone-aware")
        if not self.explanation:
            raise ValueError("RelativeStrengthContext.explanation is mandatory (ADR-005)")
