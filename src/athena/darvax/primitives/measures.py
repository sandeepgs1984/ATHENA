"""Structural measures over a candle series (DX-2).

Four primitives, each mapping to something the source deck names explicitly:

* :func:`distance_to_ath` — "All Time High Price" (p.4), "Uncharted Territory"
  and "Life High" (pp.51-52). The deck's point is that a stock at its high has
  no overhead supply.
* :func:`range_contraction` — the "small baby candles cluttering together"
  base the deck describes on p.41 after an advance and correction.
* :func:`volume_expansion` — "Gigantic Multiyear Volumes" / "Huge Volumes" /
  "Massive Volumes" (pp.51-52).
* :func:`inside_bar` — the Inside Bar pattern (p.24), which the deck says is
  more meaningful on higher timeframes (p.49).

All four are measurements. None returns a verdict, a score, or a signal.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from athena.darvax.primitives._guards import (
    DarvaxPrimitiveError,
    mean,
    require_chronological_candles,
    require_positive,
)
from athena.darvax.primitives.models import (
    AthDistance,
    InsideBar,
    RangeContraction,
    VolumeExpansion,
)
from athena.domain.market import Candle

#: Bars in the "recent" window for range contraction. The deck describes the
#: base qualitatively only, so windows and thresholds are parameters.
DEFAULT_CONTRACTION_RECENT_BARS = 5
#: Bars in the baseline window contraction is measured against.
DEFAULT_CONTRACTION_BASELINE_BARS = 20
#: recent/baseline range ratio at or below which the series counts as contracting.
DEFAULT_CONTRACTION_RATIO = Decimal("0.6")

#: Bars in the "recent" window for volume expansion.
DEFAULT_VOLUME_RECENT_BARS = 5
#: Bars in the baseline window volume is measured against.
DEFAULT_VOLUME_BASELINE_BARS = 50
#: recent/baseline volume ratio at or above which the series counts as expanding.
DEFAULT_VOLUME_EXPANSION_RATIO = Decimal("2.0")


def distance_to_ath(candles: Sequence[Candle]) -> AthDistance:
    """How far the latest close sits below the highest high in this series.

    The result's ``ath`` is the highest high **within the candles provided** —
    ATHENA holds only ingested history, so this is not necessarily a true
    all-time high. :class:`AthDistance` documents that limitation rather than
    implying knowledge the data cannot support.
    """
    require_chronological_candles(candles, minimum=1, what="distance_to_ath")

    ath = candles[0].high
    ath_index = 0
    for i, bar in enumerate(candles):
        if bar.high > ath:
            ath = bar.high
            ath_index = i

    close = candles[-1].close
    distance_pct = (
        Decimal(0)
        if ath == 0
        else max(Decimal(0), (ath - close) / ath * Decimal(100))
    )

    return AthDistance(
        ath=ath,
        ath_index=ath_index,
        ath_ts=candles[ath_index].ts_open,
        close=close,
        distance_pct=distance_pct,
        at_ath=close >= ath,
        bars_examined=len(candles),
    )


def range_contraction(
    candles: Sequence[Candle],
    *,
    recent_bars: int = DEFAULT_CONTRACTION_RECENT_BARS,
    baseline_bars: int = DEFAULT_CONTRACTION_BASELINE_BARS,
    max_ratio: Decimal = DEFAULT_CONTRACTION_RATIO,
) -> RangeContraction:
    """Mean recent bar range against mean baseline bar range.

    Range is high-minus-low per bar (not true range), because the deck's "baby
    candles" observation is about visible bar size. The baseline window is the
    ``baseline_bars`` bars ending where the recent window begins, so the two
    windows never overlap — an overlapping baseline would dilute the very
    contraction being measured.
    """
    require_positive(recent_bars, name="recent_bars")
    require_positive(baseline_bars, name="baseline_bars")
    require_positive(max_ratio, name="max_ratio")
    needed = recent_bars + baseline_bars
    require_chronological_candles(candles, minimum=needed, what="range_contraction")

    ranges = [bar.high - bar.low for bar in candles]
    recent = ranges[-recent_bars:]
    baseline = ranges[-needed:-recent_bars]

    recent_mean = mean(recent)
    baseline_mean = mean(baseline)
    if baseline_mean == 0:
        raise DarvaxPrimitiveError(
            "range_contraction baseline mean range is 0 — every baseline bar had "
            "high == low, so contraction is not measurable against it"
        )
    ratio = recent_mean / baseline_mean

    return RangeContraction(
        recent_mean_range=recent_mean,
        baseline_mean_range=baseline_mean,
        ratio=ratio,
        is_contracting=ratio <= max_ratio,
        recent_bars=recent_bars,
        baseline_bars=baseline_bars,
    )


def volume_expansion(
    candles: Sequence[Candle],
    *,
    recent_bars: int = DEFAULT_VOLUME_RECENT_BARS,
    baseline_bars: int = DEFAULT_VOLUME_BASELINE_BARS,
    min_ratio: Decimal = DEFAULT_VOLUME_EXPANSION_RATIO,
) -> VolumeExpansion:
    """Mean recent volume against mean baseline volume.

    Windows are non-overlapping, on the same reasoning as
    :func:`range_contraction`.
    """
    require_positive(recent_bars, name="recent_bars")
    require_positive(baseline_bars, name="baseline_bars")
    require_positive(min_ratio, name="min_ratio")
    needed = recent_bars + baseline_bars
    require_chronological_candles(candles, minimum=needed, what="volume_expansion")

    volumes = [Decimal(bar.volume) for bar in candles]
    recent_mean = mean(volumes[-recent_bars:])
    baseline_mean = mean(volumes[-needed:-recent_bars])
    if baseline_mean == 0:
        raise DarvaxPrimitiveError(
            "volume_expansion baseline mean volume is 0 — no traded volume in "
            "the baseline window, so expansion is not measurable against it"
        )
    ratio = recent_mean / baseline_mean

    return VolumeExpansion(
        recent_mean_volume=recent_mean,
        baseline_mean_volume=baseline_mean,
        ratio=ratio,
        is_expanding=ratio >= min_ratio,
        recent_bars=recent_bars,
        baseline_bars=baseline_bars,
    )


def inside_bar(candles: Sequence[Candle], *, index: int = -1) -> InsideBar:
    """Whether the bar at ``index`` is contained within its predecessor's range.

    Containment is inclusive (``high <= prior_high and low >= prior_low``),
    the definition in common practical use and the one matching the deck's
    illustrations. A bar equalling its predecessor's high or low still counts as
    inside.
    """
    require_chronological_candles(candles, minimum=2, what="inside_bar")

    total = len(candles)
    resolved = index if index >= 0 else total + index
    if not 0 < resolved < total:
        raise DarvaxPrimitiveError(
            f"inside_bar index {index} resolves to {resolved}, which has no "
            f"predecessor in a series of {total} candles"
        )

    bar = candles[resolved]
    prior = candles[resolved - 1]
    return InsideBar(
        index=resolved,
        ts=bar.ts_open,
        is_inside=bar.high <= prior.high and bar.low >= prior.low,
        prior_high=prior.high,
        prior_low=prior.low,
        high=bar.high,
        low=bar.low,
    )
