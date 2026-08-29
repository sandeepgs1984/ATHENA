"""Intraday Analytics (ID-2) — typed analytical evidence, NOT trade signals.

Formalizes ATHENA's already-live VWAP/5m-15m-confluence evidence into
`IntradaySignalSet`/`IntradayTrendContext`. No BUY/SELL score, no trade
probability, no EntryQualification — see `docs/research/ID-2-*` for the
full design rationale.
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

__all__ = [
    "IntradayAnalyticsEngine",
    "IntradaySignalSet",
    "IntradayTrendContext",
    "IntradayTrendLabel",
    "TimeframeTrendEvidence",
    "VwapEvidence",
    "VwapRelation",
]
