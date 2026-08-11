"""DarvaX deterministic methodology primitives (DX-2, ADR-010).

Exactly the seven primitives ADR-010's DX-2 milestone names, and nothing else:

============================  ==========================================
Primitive                      Source-deck anchor
============================  ==========================================
:func:`darvas_boxes`           Darvas DAR-CARD rules, p.67
:func:`zigzag_swings`          ZigZag trading setup, p.32
:func:`distance_to_ath`        All-Time-High / Uncharted Territory, pp.4, 51
:func:`range_contraction`      "baby candles" base, p.41
:func:`volume_expansion`       "Gigantic/Massive Volumes", pp.51-52
:func:`inside_bar`             Inside Bar pattern, pp.24, 49
:func:`fibonacci_levels`       Fibonacci retracement levels, p.30
============================  ==========================================

Every function here is **pure**: same inputs, same outputs, no clock, no
configuration, no I/O, no hidden state. Prices and ratios are ``Decimal``, never
float. Inputs must be chronological (oldest-first) single-instrument,
single-timeframe candle series, and that is validated rather than assumed —
``list_candles_recent()`` returns newest-first and would silently invert every
measurement here.

**These are measurements, not signals.** Nothing in this package decides
anything, scores anything, or recommends anything. Composing these into
breakout/retest state machines, stop policies, and signals is DX-3, behind its
own owner approval gate. Insufficient history returns an explicit empty/None
result — "cannot know yet" is reported honestly, never papered over with a
default value.
"""

from __future__ import annotations

from athena.darvax.primitives._guards import DarvaxPrimitiveError
from athena.darvax.primitives.boxes import (
    DEFAULT_CONFIRMATION_BARS,
    current_box,
    darvas_boxes,
)
from athena.darvax.primitives.levels import (
    FIBONACCI_RETRACEMENT_PERCENTS,
    classify_retracement,
    fibonacci_levels,
)
from athena.darvax.primitives.measures import (
    DEFAULT_CONTRACTION_BASELINE_BARS,
    DEFAULT_CONTRACTION_RATIO,
    DEFAULT_CONTRACTION_RECENT_BARS,
    DEFAULT_VOLUME_BASELINE_BARS,
    DEFAULT_VOLUME_EXPANSION_RATIO,
    DEFAULT_VOLUME_RECENT_BARS,
    distance_to_ath,
    inside_bar,
    range_contraction,
    volume_expansion,
)
from athena.darvax.primitives.models import (
    AthDistance,
    DarvasBox,
    FibonacciLevels,
    InsideBar,
    RangeContraction,
    RetracementZone,
    SwingKind,
    SwingPoint,
    VolumeExpansion,
)
from athena.darvax.primitives.swings import (
    DEFAULT_SWING_THRESHOLD_PCT,
    last_completed_swing_leg,
    zigzag_swings,
)

__all__ = [
    "DEFAULT_CONFIRMATION_BARS",
    "DEFAULT_CONTRACTION_BASELINE_BARS",
    "DEFAULT_CONTRACTION_RATIO",
    "DEFAULT_CONTRACTION_RECENT_BARS",
    "DEFAULT_SWING_THRESHOLD_PCT",
    "DEFAULT_VOLUME_BASELINE_BARS",
    "DEFAULT_VOLUME_EXPANSION_RATIO",
    "DEFAULT_VOLUME_RECENT_BARS",
    "FIBONACCI_RETRACEMENT_PERCENTS",
    "AthDistance",
    "DarvasBox",
    "DarvaxPrimitiveError",
    "FibonacciLevels",
    "InsideBar",
    "RangeContraction",
    "RetracementZone",
    "SwingKind",
    "SwingPoint",
    "VolumeExpansion",
    "classify_retracement",
    "current_box",
    "darvas_boxes",
    "distance_to_ath",
    "fibonacci_levels",
    "inside_bar",
    "last_completed_swing_leg",
    "range_contraction",
    "volume_expansion",
    "zigzag_swings",
]
