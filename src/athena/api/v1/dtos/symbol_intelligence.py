"""Symbol Intelligence composition DTOs (SI-P1)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.decisions import (
    DecisionDepthDTO,
    GateResultDTO,
    TradePlanDTO,
    TradePlanFreshnessDTO,
)
from athena.api.v1.dtos.intraday_intelligence import IntradayIntelligenceDTO

SiFreshnessStatus = Literal["CURRENT", "STALE", "UNAVAILABLE", "NOT_READ"]
SiOverallFreshness = Literal["READY", "PARTIAL", "STALE", "UNAVAILABLE"]
SiHoldingStatus = Literal["HELD", "NOT_HELD"]


class SiFreshnessDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    status: SiFreshnessStatus
    lineage: str
    as_of: datetime | None = None
    expected_session: date | None = None
    explanation: str


class SiUnavailableDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    detail: str
    lineage: str


class SiNamedEvidenceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    value: str | None
    lineage: str
    horizon: str | None = None
    is_coherent: bool | None = None
    reason: str | None = None


class SiIdentityDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    resolved: bool
    instrument_id: str | None = None
    symbol: str | None = None
    exchange: str | None = None
    name: str | None = None
    sector: str | None = None
    unresolved_reason: str | None = None
    resolution_code: str | None = None
    catalog: str | None = None
    ingested: bool | None = None


class SiSearchHitDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    symbol: str
    exchange: str
    name: str | None = None
    sector: str | None = None


class SiSearchResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    hits: tuple[SiSearchHitDTO, ...]


class SiZoneDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    lower: Decimal
    upper: Decimal
    role: str
    lineage: str = "PORTFOLIO_STRUCTURAL_REVIEW"


class SiD1EvidenceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    null_reason: str | None = None
    lineage: str = "D1_CANDLES"
    latest_session: datetime | None = None
    expected_session: date | None = None
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: int | None = None
    adjusted: bool | None = None
    candles_used: int = 0
    rsi14: Decimal | None = None
    rsi_reason: str | None = None
    rsi_is_coherent: bool | None = None
    supertrend_direction: str | None = None
    supertrend_value: Decimal | None = None
    supertrend_reason: str | None = None
    supertrend_version: str | None = None
    supertrend_is_coherent: bool | None = None
    volume_ma20: Decimal | None = None
    volume_reason: str | None = None
    volume_is_coherent: bool | None = None
    available_history_high: Decimal | None = Field(
        default=None,
        description="Prior available-history high from persisted D1 bars, not an official 52-week high.",
    )
    available_history_high_session: datetime | None = None
    latest_high_exceeds_prior_history: bool | None = None
    latest_close_above_prior_history_high: bool | None = None
    ath_reason: str | None = None
    ath_is_coherent: bool | None = None
    symbol_trend: str | None = None
    symbol_trend_reason: str | None = None
    symbol_trend_is_coherent: bool | None = None
    fast_sma: Decimal | None = None
    slow_sma: Decimal | None = None
    support_1: SiZoneDTO | None = None
    major_support: SiZoneDTO | None = None
    review_trigger: SiZoneDTO | None = None
    target_1: SiZoneDTO | None = None
    target_2: SiZoneDTO | None = None
    target_3: SiZoneDTO | None = None
    structural_reason_codes: tuple[str, ...] = ()
    structural_is_coherent: bool | None = None
    adapter_version: str | None = None


class SiDecisionSummaryDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    null_reason: str | None = None
    lineage: str = "ATHENA_DECISION"
    decision_id: str | None = None
    decision_type: str | None = None
    direction: str | None = None
    ts: datetime | None = None
    run_id: str | None = None
    cycle_id: str | None = None
    explanation: str | None = None
    confidence_level: str | None = None
    gates: tuple[GateResultDTO, ...] = ()
    trade_plan: TradePlanDTO | None = None
    plan_freshness: TradePlanFreshnessDTO | None = None
    depth: DecisionDepthDTO | None = None
    intraday: IntradayIntelligenceDTO | None = None
    intraday_horizon: str | None = None


class SiPortfolioContextDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: SiHoldingStatus
    lineage: str = "PORTFOLIO"
    quantity: int | None = None
    avg_price: Decimal | None = None
    last_price: Decimal | None = None
    current_value: Decimal | None = None
    investment: Decimal | None = None
    pnl: Decimal | None = None
    pnl_pct: Decimal | None = None
    snapshot_id: str | None = None
    snapshot_currentness: str | None = None
    snapshot_currentness_reason: str | None = None
    interpretation_status: str | None = None
    conviction: str | None = None
    trend_setup: str | None = None
    next_action: str | None = None
    daily_review_status: str | None = None
    display_weight_pct: Decimal | None = Field(
        default=None,
        description="current_value / total_current_value from the existing snapshot, not a new risk weight.",
    )


class SiDarvaxPresentationDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    status: Literal["ENABLED_IFRAME", "DISABLED", "UNAVAILABLE"]
    experimental_label: str = "EXPERIMENTAL_UNVALIDATED"
    lineage: str = "DARVAX"
    iframe_url: str | None = None
    explanation: str


class SiQualityPlaceholderDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: None = None
    status: Literal["NOT_YET_METHODOLOGICALLY_DEFINED"] = "NOT_YET_METHODOLOGICALLY_DEFINED"
    reason: str
    named_evidence: tuple[SiNamedEvidenceDTO, ...] = ()


class SiNotIngestedDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["NOT_INGESTED"] = "NOT_INGESTED"
    reason: str


class SiHydrationDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempted: bool
    status: str
    detail: str
    candles_written: int = 0


SiQuoteKind = Literal["LIVE", "LATEST_QUOTE", "UNAVAILABLE"]
SiMarketState = Literal["MARKET OPEN", "MARKET CLOSED"]


class SiLiveQuoteDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    quote_kind: SiQuoteKind = "UNAVAILABLE"
    market_state: SiMarketState = "MARKET CLOSED"
    label: str = "MARKET CLOSED"
    last_price: Decimal | None = None
    change_pct: Decimal | None = None
    volume: int | None = None
    session_open: Decimal | None = None
    session_high: Decimal | None = None
    session_low: Decimal | None = None
    previous_close: Decimal | None = None
    as_of: datetime | None = None
    null_reason: str | None = None


class SiOverallFreshnessDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: SiOverallFreshness
    explanation: str


class SymbolIntelligenceBundleDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: SiIdentityDTO
    read_as_of: datetime
    overall_freshness: SiOverallFreshnessDTO
    sources: tuple[SiFreshnessDTO, ...]
    decision: SiDecisionSummaryDTO
    d1: SiD1EvidenceDTO
    portfolio: SiPortfolioContextDTO | None = None
    darvax: SiDarvaxPresentationDTO
    momentum_quality: SiQualityPlaceholderDTO
    entry_quality: SiQualityPlaceholderDTO
    fundamentals: SiNotIngestedDTO
    news: SiNotIngestedDTO
    unavailable: tuple[SiUnavailableDTO, ...] = ()
    hydration: SiHydrationDTO | None = None
    live: SiLiveQuoteDTO | None = None
