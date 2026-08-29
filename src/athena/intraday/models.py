"""Intraday Analytics domain artifacts (ID-2).

Analytical evidence containers, NOT trading signals — despite the name
`IntradaySignalSet`, nothing here means BUY/SELL/TRADE. It is a typed
formalization of intraday evidence ATHENA already computes (VWAP relation,
5m/15m trend-direction confluence), plus a transparent, zero-new-weights
aggregate trend read across the two intraday timeframes. Foundation only:
no BUY/SELL score, no trade probability, no EntryQualification — those are
later milestones' job.

Pure, immutable, explainable (ADR-005): every field carries a mandatory,
non-empty explanation, matching every other analytical result in this
codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, unique

from athena.domain.enums import Timeframe
from athena.session.models import SessionDataQualityStatus


@unique
class VwapRelation(str, Enum):
    """Objective price-vs-VWAP state — formalizes the existing
    `IndicatorResult` VWAP deviation ScoringEngine already consumes. No
    "near VWAP" band exists anywhere in the current frozen contract, so none
    is invented here — only the sign of the existing `deviation_pct`."""

    ABOVE_VWAP = "ABOVE_VWAP"
    BELOW_VWAP = "BELOW_VWAP"
    AT_VWAP = "AT_VWAP"
    VWAP_UNAVAILABLE = "VWAP_UNAVAILABLE"


@unique
class IntradayTrendLabel(str, Enum):
    """A zero-new-methodology aggregation of the two existing 5m/15m
    confluence-direction reads: unanimous agreement -> BULLISH/BEARISH,
    disagreement -> NEUTRAL (visible, not hidden), either missing ->
    UNKNOWN. No weights, no numeric threshold."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class TimeframeTrendEvidence:
    """One timeframe's directional read — formalizes the existing
    confluence SMA-direction check (`ScoringEngine`'s own
    `ConfluenceInputs.five_min_bullish`/`fifteen_min_bullish`), not a new
    computation."""

    timeframe: Timeframe
    bullish: bool | None
    sma_period: int
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("TimeframeTrendEvidence.explanation is mandatory (ADR-005)")


@dataclass(frozen=True, slots=True)
class IntradayTrendContext:
    """Objectively measured intraday directional structure across the
    timeframes ATHENA genuinely has live (5m, 15m) — descriptive only,
    never "should I buy this." Extensible to 60m later without redesign
    (a third `TimeframeTrendEvidence` field), not built out here since no
    60m data path exists yet."""

    instrument_id: str
    session_date: date
    as_of: datetime
    five_min: TimeframeTrendEvidence
    fifteen_min: TimeframeTrendEvidence
    trend_label: IntradayTrendLabel
    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("IntradayTrendContext.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("IntradayTrendContext.as_of must be timezone-aware")
        if not self.explanation:
            raise ValueError("IntradayTrendContext.explanation is mandatory (ADR-005)")


@dataclass(frozen=True, slots=True)
class VwapEvidence:
    """Formalized VWAP relation — the exact value ScoringEngine's
    `_technical_structure` already reads (`deviation_pct`), typed rather
    than reached into via a raw `IndicatorResult`."""

    relation: VwapRelation
    deviation_pct: Decimal | None
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation:
            raise ValueError("VwapEvidence.explanation is mandatory (ADR-005)")


@dataclass(frozen=True, slots=True)
class IntradaySignalSet:
    """Analytical evidence container for one instrument at one moment —
    NOT a trade signal. Composable: future milestones add typed evidence
    fields here (ORB state, relative volume, relative strength, …) without
    redesigning this contract or forcing a premature BUY/SELL/probability
    onto it."""

    instrument_id: str
    session_date: date
    as_of: datetime
    vwap: VwapEvidence
    trend: IntradayTrendContext
    data_quality: SessionDataQualityStatus
    explanation: str

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("IntradaySignalSet.instrument_id is mandatory")
        if self.as_of.tzinfo is None:
            raise ValueError("IntradaySignalSet.as_of must be timezone-aware")
        if not self.explanation:
            raise ValueError("IntradaySignalSet.explanation is mandatory (ADR-005)")
