"""Intraday Analytics (ID-2/ID-3/ID-4/ID-5C/ID-5D) — typed analytical evidence, NOT trade signals.

Formalizes ATHENA's already-live VWAP/5m-15m-confluence evidence into
`IntradaySignalSet`/`IntradayTrendContext`, and adds genuinely new
`OpeningRangeEvidence` (OR15/OR30), `RelativeStrengthContext`
(stock-vs-sector/market point-in-time comparative performance — not RSI),
`GapContext` (previous-session-close -> current-session-open price
transition — not an intraday return, not gap-fill/-hold/-rejection/
-continuation), and `RelativeVolumeContext` (cumulative same-time-of-day
relative volume — not a surge/spike label, no magnitude threshold). No
BUY/SELL score, no trade probability, no EntryQualification — see
`docs/research/ID-2-*`/`ID-3-*`/`ID-4-*`/`ID-5C-*`/`ID-5D-*`
for the full design rationale.
"""

from athena.intraday.engine import IntradayAnalyticsEngine
from athena.intraday.gap_engine import GapEngine
from athena.intraday.gap_models import GapContext, GapDirection
from athena.intraday.models import (
    IntradaySignalSet,
    IntradayTrendContext,
    IntradayTrendLabel,
    TimeframeTrendEvidence,
    VwapEvidence,
    VwapRelation,
)
from athena.intraday.opening_range_engine import OpeningRangeEngine
from athena.intraday.opening_range_models import (
    BreakoutEvent,
    OpeningRangeEvidence,
    OpeningRangeFormation,
    OpeningRangeFormationStatus,
    OpeningRangeRelation,
    OpeningRangeWindow,
)
from athena.intraday.relative_strength_engine import RelativeStrengthEngine
from athena.intraday.relative_strength_models import RelativeStrengthContext, RelativeStrengthRelation
from athena.intraday.relative_volume_engine import RelativeVolumeEngine
from athena.intraday.relative_volume_models import RelativeVolumeContext, RelativeVolumeRelation

__all__ = [
    "BreakoutEvent",
    "GapContext",
    "GapDirection",
    "GapEngine",
    "IntradayAnalyticsEngine",
    "IntradaySignalSet",
    "IntradayTrendContext",
    "IntradayTrendLabel",
    "OpeningRangeEngine",
    "OpeningRangeEvidence",
    "OpeningRangeFormation",
    "OpeningRangeFormationStatus",
    "OpeningRangeRelation",
    "OpeningRangeWindow",
    "RelativeStrengthContext",
    "RelativeStrengthEngine",
    "RelativeStrengthRelation",
    "RelativeVolumeContext",
    "RelativeVolumeEngine",
    "RelativeVolumeRelation",
    "TimeframeTrendEvidence",
    "VwapEvidence",
    "VwapRelation",
]
