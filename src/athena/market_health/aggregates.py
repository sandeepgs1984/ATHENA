"""Pure market-metric input aggregates for F-5 (MH-1).

No I/O — callers pass canonical candles / snapshots. MH-2 maps these inputs
to MarketHealthScore component points.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from athena.domain.market import Candle


@dataclass(frozen=True, slots=True)
class UniverseBreadthResult:
    """Universe ADV/DEC/neutral from latest two D1 closes (F-5 §3.2)."""

    advances: int
    declines: int
    neutral: int
    universe_size: int
    scored: int

    @property
    def coverage(self) -> Decimal:
        if self.universe_size <= 0:
            return Decimal("0")
        return Decimal(self.scored) / Decimal(self.universe_size)

    @property
    def advance_ratio(self) -> Decimal | None:
        total = self.advances + self.declines
        if total == 0:
            return None
        return Decimal(self.advances) / Decimal(total)

    def to_payload(self) -> dict[str, object]:
        return {
            "advances": self.advances,
            "declines": self.declines,
            "neutral": self.neutral,
            "universe_size": self.universe_size,
            "scored": self.scored,
            "coverage": str(self.coverage),
            "advance_ratio": (
                None if self.advance_ratio is None else str(self.advance_ratio)
            ),
        }


@dataclass(frozen=True, slots=True)
class LiquidityAggregateResult:
    """Market-level participation liquidity (F-5 §3.3)."""

    member_count: int
    median_turnover: Decimal | None
    method: str

    def to_payload(self) -> dict[str, object]:
        return {
            "member_count": self.member_count,
            "median_turnover": (
                None if self.median_turnover is None else str(self.median_turnover)
            ),
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class GapStabilityResult:
    """Rolling opening-gap stability on an index (F-5 §3.6)."""

    gap_days: int
    scored_days: int
    stability_ratio: Decimal | None
    gap_pct_threshold: Decimal

    def to_payload(self) -> dict[str, object]:
        return {
            "gap_days": self.gap_days,
            "scored_days": self.scored_days,
            "stability_ratio": (
                None if self.stability_ratio is None else str(self.stability_ratio)
            ),
            "gap_pct_threshold": str(self.gap_pct_threshold),
        }


def compute_universe_breadth(
    candles_by_instrument: Mapping[str, Sequence[Candle]],
) -> UniverseBreadthResult:
    """Count advances/declines/neutral across instruments with ≥2 bars."""
    universe_size = len(candles_by_instrument)
    advances = declines = neutral = scored = 0
    for series in candles_by_instrument.values():
        ordered = sorted(series, key=lambda c: c.ts_open)
        if len(ordered) < 2:
            continue
        scored += 1
        last, prior = ordered[-1].close, ordered[-2].close
        if last > prior:
            advances += 1
        elif last < prior:
            declines += 1
        else:
            neutral += 1
    return UniverseBreadthResult(
        advances=advances,
        declines=declines,
        neutral=neutral,
        universe_size=universe_size,
        scored=scored,
    )


def compute_liquidity_aggregate(
    candles_by_instrument: Mapping[str, Sequence[Candle]],
    *,
    lookback_days: int = 20,
    method: str = "median",
) -> LiquidityAggregateResult:
    """Median (default) of per-member mean daily rupee turnover over lookback."""
    if lookback_days < 1:
        raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")
    if method != "median":
        raise ValueError(f"unsupported liquidity method {method!r}; only 'median'")
    turnovers: list[Decimal] = []
    for series in candles_by_instrument.values():
        ordered = sorted(series, key=lambda c: c.ts_open)[-lookback_days:]
        if not ordered:
            continue
        daily = [
            c.close * Decimal(c.volume)
            for c in ordered
            if c.volume > 0
        ]
        if not daily:
            continue
        turnovers.append(sum(daily) / Decimal(len(daily)))
    if not turnovers:
        return LiquidityAggregateResult(
            member_count=0, median_turnover=None, method=method
        )
    return LiquidityAggregateResult(
        member_count=len(turnovers),
        median_turnover=Decimal(str(median(turnovers))),
        method=method,
    )


def compute_gap_stability(
    index_candles: Sequence[Candle],
    *,
    window: int = 20,
    gap_pct_threshold: Decimal = Decimal("0.5"),
) -> GapStabilityResult:
    """Fraction of days without a large open-vs-prior-close gap."""
    if window < 2:
        raise ValueError(f"gap stability window must be >= 2, got {window}")
    ordered = sorted(index_candles, key=lambda c: c.ts_open)
    if len(ordered) < 2:
        return GapStabilityResult(
            gap_days=0,
            scored_days=0,
            stability_ratio=None,
            gap_pct_threshold=gap_pct_threshold,
        )
    # Need pairs: use last `window` gap observations (= window+1 bars preferred).
    pairs = list(zip(ordered[1:], ordered[:-1], strict=False))
    pairs = pairs[-window:]
    gap_days = 0
    for today, prior in pairs:
        if prior.close == 0:
            continue
        gap_pct = abs((today.open - prior.close) / prior.close) * Decimal(100)
        if gap_pct >= gap_pct_threshold:
            gap_days += 1
    scored = len(pairs)
    if scored == 0:
        ratio = None
    else:
        ratio = Decimal(1) - (Decimal(gap_days) / Decimal(scored))
    return GapStabilityResult(
        gap_days=gap_days,
        scored_days=scored,
        stability_ratio=ratio,
        gap_pct_threshold=gap_pct_threshold,
    )
