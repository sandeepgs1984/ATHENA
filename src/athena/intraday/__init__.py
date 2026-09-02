"""Intraday Analytics (ID-2/ID-3/ID-4/ID-5C/ID-5D/ID-6A) — typed evidence and contracts.

Formalizes ATHENA's already-live VWAP/5m-15m-confluence evidence into
`IntradaySignalSet`/`IntradayTrendContext`, and adds genuinely new
`OpeningRangeEvidence` (OR15/OR30), `RelativeStrengthContext`
(stock-vs-sector/market point-in-time comparative performance — not RSI),
`GapContext` (previous-session-close -> current-session-open price
transition — not an intraday return, not gap-fill/-hold/-rejection/
-continuation), and `RelativeVolumeContext` (cumulative same-time-of-day
relative volume — not a surge/spike label, no magnitude threshold). ID-6A
adds `EntryQualification` domain contracts only: no engine, no workflow
wiring, no persistence, no BUY/SELL score, no trade probability, and no
Decision/TradePlan mutation. See `docs/research/ID-2-*`/`ID-3-*`/
`ID-4-*`/`ID-5C-*`/`ID-5D-*` and ADR-013 for the full design rationale.
"""

from athena.intraday.engine import IntradayAnalyticsEngine
from athena.intraday.entry_qualification_engine import (
    DEFAULT_METHODOLOGY_VERSION,
    EntryQualificationEngine,
    EntryQualificationPolicy,
)
from athena.intraday.entry_qualification_models import (
    EntryEvidenceFinality,
    EntryQualification,
    EntryQualificationConfirmation,
    EntryQualificationEvidenceKind,
    EntryQualificationEvidenceRef,
    EntryQualificationReasonCode,
    EntryQualificationState,
)
from athena.intraday.entry_qualification_provenance import resolve_evidence_finality
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
    "DEFAULT_METHODOLOGY_VERSION",
    "BreakoutEvent",
    "EntryEvidenceFinality",
    "EntryQualification",
    "EntryQualificationConfirmation",
    "EntryQualificationEngine",
    "EntryQualificationEvidenceKind",
    "EntryQualificationEvidenceRef",
    "EntryQualificationPolicy",
    "EntryQualificationReasonCode",
    "EntryQualificationState",
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
    "resolve_evidence_finality",
]
