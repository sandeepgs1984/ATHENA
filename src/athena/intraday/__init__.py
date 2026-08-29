"""Intraday Analytics (ID-2/ID-3) — typed analytical evidence, NOT trade signals.

Formalizes ATHENA's already-live VWAP/5m-15m-confluence evidence into
`IntradaySignalSet`/`IntradayTrendContext`, and adds genuinely new
`OpeningRangeEvidence` (OR15/OR30). No BUY/SELL score, no trade
probability, no EntryQualification — see `docs/research/ID-2-*`/`ID-3-*`
for the full design rationale.
"""

from athena.intraday.engine import IntradayAnalyticsEngine
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

__all__ = [
    "BreakoutEvent",
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
    "TimeframeTrendEvidence",
    "VwapEvidence",
    "VwapRelation",
]
