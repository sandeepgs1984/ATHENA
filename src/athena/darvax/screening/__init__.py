"""DarvaX universe screening (DX-6a, ADR-010 Amendment 2).

Turns already-computed signals into an ordered, tiered screen. Eligibility is a
classification taken from Darvas' DAR-CARD rules — never a conviction score.
"""

from athena.darvax.screening.engine import (
    TIER_ORDER,
    box_height_pct,
    distance_to_breakout,
    distance_to_trigger_pct,
    rank_tier,
    screen_signal,
    screen_signals,
    tier_counts,
    tier_for,
)
from athena.darvax.screening.models import DarvaxTier, ScreenResult, SweepRecord

__all__ = [
    "TIER_ORDER",
    "DarvaxTier",
    "ScreenResult",
    "SweepRecord",
    "box_height_pct",
    "distance_to_breakout",
    "distance_to_trigger_pct",
    "rank_tier",
    "screen_signal",
    "screen_signals",
    "tier_counts",
    "tier_for",
]
