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
from athena.intraday.entry_actionability_currentness import (
    CurrentnessResult,
    EntryActionabilityCurrentness,
    EntryQualificationIdentity,
    bound_entry_qualification_identity,
    is_currently_usable,
)
from athena.intraday.entry_actionability_engine import (
    EntryActionabilityEngine,
    EntryActionabilityMarketEvidence,
    EntryActionabilityPolicy,
)
from athena.intraday.entry_actionability_models import (
    CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS,
    EVIDENCE_SUFFICIENCY_REASON_CODES,
    T1_GOAL_BAND_PCT,
    T2_GOAL_BAND_PCT,
    UPSTREAM_ELIGIBILITY_REASON_CODES,
    EntryActionability,
    EntryActionabilityReasonCode,
    EntryActionabilityState,
    EntryLocationContext,
    EntryReference,
    EntryReferenceBasis,
    InvalidationBasis,
    OpeningRangeContextBasis,
    OpeningRangeContextReference,
    OperativeInvalidation,
    RewardBasis,
    RewardReference,
)
from athena.intraday.entry_actionability_models import (
    DEFAULT_METHODOLOGY_VERSION as ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION,
)
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
    "CURRENTNESS_MAX_EVIDENCE_AGE_SECONDS",
    "DEFAULT_METHODOLOGY_VERSION",
    "ENTRY_ACTIONABILITY_DEFAULT_METHODOLOGY_VERSION",
    "EVIDENCE_SUFFICIENCY_REASON_CODES",
    "T1_GOAL_BAND_PCT",
    "T2_GOAL_BAND_PCT",
    "UPSTREAM_ELIGIBILITY_REASON_CODES",
    "BreakoutEvent",
    "CurrentnessResult",
    "EntryActionability",
    "EntryActionabilityCurrentness",
    "EntryActionabilityEngine",
    "EntryActionabilityMarketEvidence",
    "EntryActionabilityPolicy",
    "EntryActionabilityReasonCode",
    "EntryActionabilityState",
    "EntryEvidenceFinality",
    "EntryLocationContext",
    "EntryQualification",
    "EntryQualificationConfirmation",
    "EntryQualificationEngine",
    "EntryQualificationEvidenceKind",
    "EntryQualificationEvidenceRef",
    "EntryQualificationIdentity",
    "EntryQualificationPolicy",
    "EntryQualificationReasonCode",
    "EntryQualificationState",
    "EntryReference",
    "EntryReferenceBasis",
    "GapContext",
    "GapDirection",
    "GapEngine",
    "IntradayAnalyticsEngine",
    "IntradaySignalSet",
    "IntradayTrendContext",
    "IntradayTrendLabel",
    "InvalidationBasis",
    "OpeningRangeContextBasis",
    "OpeningRangeContextReference",
    "OpeningRangeEngine",
    "OpeningRangeEvidence",
    "OpeningRangeFormation",
    "OpeningRangeFormationStatus",
    "OpeningRangeRelation",
    "OpeningRangeWindow",
    "OperativeInvalidation",
    "RelativeStrengthContext",
    "RelativeStrengthEngine",
    "RelativeStrengthRelation",
    "RelativeVolumeContext",
    "RelativeVolumeEngine",
    "RelativeVolumeRelation",
    "RewardBasis",
    "RewardReference",
    "TimeframeTrendEvidence",
    "VwapEvidence",
    "VwapRelation",
    "bound_entry_qualification_identity",
    "is_currently_usable",
    "resolve_evidence_finality",
]
