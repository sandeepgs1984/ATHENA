"""Immutable result types for DarvaX's deterministic primitives (DX-2).

Every type here is a frozen dataclass carrying *measurements* only. None of
them is a signal, a recommendation, or a decision — turning measurements into
signals is DX-3's job, behind its own approval gate.

Prices are ``Decimal`` throughout (never float), matching ATHENA's money
discipline. Ratios and percentages are also ``Decimal`` so repeated arithmetic
cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class SwingKind(str, Enum):
    """Which extreme a confirmed ZigZag pivot marks."""

    HIGH = "HIGH"
    LOW = "LOW"


class RetracementZone(str, Enum):
    """Fibonacci retracement bands as the source deck names them (p.30).

    The deck's own wording: a retracement holding between 23.6% and 38.2%
    denotes a very strong trend, and 50%-61.8% is where it describes
    accumulating favourites during an extreme market crash. ``SHALLOW`` and
    ``DEEP`` cover the ranges outside those two named bands; ``UNDEFINED`` is
    used when the swing has no height to measure against.
    """

    SHALLOW = "SHALLOW"                    # < 23.6%
    VERY_STRONG_TREND = "VERY_STRONG_TREND"  # 23.6% - 38.2% (deck's term)
    MODERATE = "MODERATE"                  # 38.2% - 50%
    ACCUMULATION = "ACCUMULATION"          # 50% - 61.8% (deck's term)
    DEEP = "DEEP"                          # > 61.8%
    UNDEFINED = "UNDEFINED"                # zero-height swing


@dataclass(frozen=True, slots=True)
class DarvasBox:
    """One completed Darvas box: a confirmed ceiling and a confirmed floor.

    Index fields refer to positions in the chronological candle sequence the
    box was computed from, so a caller can always trace a box back to the exact
    bars that produced it.
    """

    top: Decimal
    bottom: Decimal
    top_index: int
    """Bar that set the ceiling."""
    bottom_index: int
    """Bar that set the floor."""
    top_confirmed_index: int
    """Bar at which the ceiling had survived `confirmation_bars` unbeaten."""
    bottom_confirmed_index: int
    """Bar at which the floor had survived `confirmation_bars` unbroken — the
    bar at which the box became complete."""
    top_ts: datetime
    bottom_ts: datetime
    is_topmost: bool
    """True when this box's ceiling is at least as high as every earlier box's.
    Darvas' DAR-CARD rule D (deck p.67) turns on this distinction; recording it
    here is a structural fact about the box series, not a trade signal."""

    @property
    def height(self) -> Decimal:
        return self.top - self.bottom


@dataclass(frozen=True, slots=True)
class SwingPoint:
    """One confirmed ZigZag pivot.

    Only *confirmed* pivots are ever emitted: an extreme becomes a swing point
    when price has reversed from it by the configured threshold. The most
    recent extreme is therefore deliberately absent until that reversal
    happens — reporting it early would be a guess dressed as a measurement.
    """

    kind: SwingKind
    index: int
    price: Decimal
    ts: datetime


@dataclass(frozen=True, slots=True)
class AthDistance:
    """How far price sits below the highest high in the series examined.

    ``ath`` is the highest high **within the candles provided**, not a true
    all-time high across the instrument's full listing history — ATHENA holds
    only the history it has ingested. The field name and this docstring say so
    explicitly rather than implying knowledge the data cannot support.
    """

    ath: Decimal
    ath_index: int
    ath_ts: datetime
    close: Decimal
    distance_pct: Decimal
    """Percent below the observed ATH; 0 when price is at or above it."""
    at_ath: bool
    """True when the latest close is at or above the observed ATH."""
    bars_examined: int


@dataclass(frozen=True, slots=True)
class RangeContraction:
    """Whether recent bar ranges are tighter than an earlier baseline.

    This is the computable core of what the deck (p.41) describes as "small
    baby candles cluttering together" after an advance and correction — a
    volatility-contraction base. The deck gives no numeric definition, so the
    windows and threshold are explicit parameters with cited defaults, never
    inferred values presented as the author's.
    """

    recent_mean_range: Decimal
    baseline_mean_range: Decimal
    ratio: Decimal
    """recent / baseline. Below 1 means contraction."""
    is_contracting: bool
    recent_bars: int
    baseline_bars: int


@dataclass(frozen=True, slots=True)
class VolumeExpansion:
    """Recent volume against a longer baseline average."""

    recent_mean_volume: Decimal
    baseline_mean_volume: Decimal
    ratio: Decimal
    """recent / baseline. Above 1 means expansion."""
    is_expanding: bool
    recent_bars: int
    baseline_bars: int


@dataclass(frozen=True, slots=True)
class InsideBar:
    """Whether one bar is fully contained within its predecessor's range."""

    index: int
    ts: datetime
    is_inside: bool
    prior_high: Decimal
    prior_low: Decimal
    high: Decimal
    low: Decimal


@dataclass(frozen=True, slots=True)
class FibonacciLevels:
    """Retracement prices for one swing, plus where a given price sits.

    Levels are the four the deck names explicitly (p.30): 23.6, 38.2, 50.0 and
    61.8 percent. ``levels`` maps each of those percentages to the retracement
    price measured down from ``swing_high`` toward ``swing_low``.
    """

    swing_low: Decimal
    swing_high: Decimal
    levels: tuple[tuple[Decimal, Decimal], ...]
    """Ordered ((percent, price), ...) pairs — a tuple, so the result stays
    immutable and its ordering is part of the contract."""
    price: Decimal | None
    retracement_pct: Decimal | None
    zone: RetracementZone

    @property
    def height(self) -> Decimal:
        return self.swing_high - self.swing_low
