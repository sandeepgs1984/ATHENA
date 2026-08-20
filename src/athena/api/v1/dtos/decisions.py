"""Decisions resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import FilterParams, ResourceReference


class ResetDecisionsRequest(BaseModel):
    """Destructive wipe of the Decisions & Trace domain (CONFIRM-gated)."""

    model_config = ConfigDict(frozen=True)

    confirmation: str = Field(description="Must be the exact token CONFIRM")


class ResetDecisionsResultDTO(BaseModel):
    """Result of an owner-triggered Decisions & Trace reset."""

    model_config = ConfigDict(frozen=True)

    deleted_counts: dict[str, int]
    total_deleted: int
    backup_path: str | None = None


class TradePlanDTO(BaseModel):
    """Composed DTO representing entry, stop loss, targets, and sizing plans."""

    model_config = ConfigDict(frozen=True)

    entry_low: Decimal
    entry_high: Decimal
    stop_loss: Decimal
    targets: list[Decimal]
    position_size: int
    risk_amount: Decimal
    risk_reward: Decimal
    valid_from: datetime
    valid_until: datetime


class GateResultDTO(BaseModel):
    """Quality gate outcome representing safety checks."""

    model_config = ConfigDict(frozen=True)

    gate: str
    passed: bool
    detail: str


class DecisionMetadataDTO(BaseModel):
    """Composed DTO housing identifiers, dates, and types."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    ts: datetime
    run_id: str
    cycle_id: str
    instrument_id: str | None = None
    # Real company name from the instruments table (Kite's own instrument
    # dump), when the catalog has been refreshed since this field was added
    # — None (rendered as absent) for instruments not yet re-synced, never
    # a fabricated placeholder.
    instrument_name: str | None = None
    direction: str = "NONE"
    decision_type: str


class DecisionAnalysisDTO(BaseModel):
    """Composed DTO linking to analytical assessment files."""

    model_config = ConfigDict(frozen=True)

    score_ref: ResourceReference | None = None
    confidence_ref: ResourceReference | None = None
    confidence_level: Literal["HIGH", "MEDIUM", "LOW"] | None = None
    risk_ref: ResourceReference | None = None
    gate_results: list[GateResultDTO] = Field(default_factory=list)


class DecisionDTO(BaseModel):
    """Composed DTO representing system decisions."""

    model_config = ConfigDict(frozen=True)

    metadata: DecisionMetadataDTO
    analysis: DecisionAnalysisDTO
    trade_plan: TradePlanDTO | None = None
    explanation: str


class DecisionFilterParams(FilterParams):
    """Filter parameters for decisions collection queries."""

    instrument_id: str | None = Field(default=None, description="Filter by instrument identifier")
    decision_type: str | None = Field(default=None, description="Filter by decision action type")
    direction: str | None = Field(default=None, description="Filter by trade direction (LONG, SHORT)")


class TraceStageDTO(BaseModel):
    """DTO representing one stage/node in the decision trace DAG."""

    model_config = ConfigDict(frozen=True)

    stage_id: str
    name: str
    status: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class DecisionTraceDTO(BaseModel):
    """DTO representing the complete decision trace DAG flow."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    instrument_id: str
    stages: list[TraceStageDTO]


class AnalysisContributionDTO(BaseModel):
    """One persisted, source-attributed input to an analytical dimension."""

    model_config = ConfigDict(frozen=True)

    source: str
    reference: str = ""
    description: str
    points: Decimal | None = None


class AnalysisDimensionDTO(BaseModel):
    """One score/confidence/risk dimension rendered without recomputation."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    value: Decimal | None = None
    level: str | None = None
    weight: int | None = None
    weighted: Decimal | None = None
    explanation: str = ""
    contributions: list[AnalysisContributionDTO] = Field(default_factory=list)


class AnalysisBlockDTO(BaseModel):
    """Persisted score, confidence, or risk block."""

    model_config = ConfigDict(frozen=True)

    status: str
    value: Decimal | None = None
    level: str | None = None
    completeness: Decimal | None = None
    explanation: str = ""
    dimensions: list[AnalysisDimensionDTO] = Field(default_factory=list)


class EligibilityRuleDTO(BaseModel):
    """One persisted universe eligibility rule result."""

    model_config = ConfigDict(frozen=True)

    rule: str
    passed: bool
    explanation: str
    inputs: dict[str, str] = Field(default_factory=dict)


class EligibilityDetailDTO(BaseModel):
    """Eligibility result captured in the decision's originating run."""

    model_config = ConfigDict(frozen=True)

    status: Literal["INCLUDED", "EXCLUDED", "UNKNOWN"]
    summary: str
    exclusion_reasons: list[str] = Field(default_factory=list)
    rules: list[EligibilityRuleDTO] = Field(default_factory=list)


class DecisionDepthDTO(BaseModel):
    """Persisted analytical depth for one decision; never recomputed by API."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    instrument_id: str | None = None
    eligibility: EligibilityDetailDTO
    score: AnalysisBlockDTO
    confidence: AnalysisBlockDTO
    risk: AnalysisBlockDTO


class CalendarEventDTO(BaseModel):
    """One scheduled market-moving event (M-D4)."""

    model_config = ConfigDict(frozen=True)

    kind: str
    name: str


class CalendarContextDTO(BaseModel):
    """Session/calendar awareness for the decision's trading day; computed live
    from the Calendar Engine, never persisted (R-3, M-D4)."""

    model_config = ConfigDict(frozen=True)

    context_date: str
    session_type: str
    exchange: str
    timezone: str
    open_time: str | None = None
    close_time: str | None = None
    holiday_name: str | None = None
    is_weekly_expiry: bool = False
    is_monthly_expiry: bool = False
    events: list[CalendarEventDTO] = Field(default_factory=list)


class ContextEvidenceDTO(BaseModel):
    """One persisted regime/market-health evidence item (M-D4)."""

    model_config = ConfigDict(frozen=True)

    dimension: str
    outcome: str
    explanation: str


class RegimeContextDTO(BaseModel):
    """Persisted regime assessment for the decision's originating cycle (M-D4)."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ASSESSED", "UNKNOWN"]
    labels: list[str] = Field(default_factory=list)
    explanation: str = ""
    evidence: list[ContextEvidenceDTO] = Field(default_factory=list)


class MarketHealthContextDTO(BaseModel):
    """Persisted market-health assessment for the decision's originating cycle (M-D4)."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ASSESSED", "UNKNOWN"]
    dimensions: dict[str, str] = Field(default_factory=dict)
    explanation: str = ""
    evidence: list[ContextEvidenceDTO] = Field(default_factory=list)


class ExternalLinkDTO(BaseModel):
    """One owner-curated external research link (M-D4). Static metadata only."""

    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    source: str
    added_by: str
    date_added: str


class DecisionContextDTO(BaseModel):
    """Session/calendar, regime/market-health, and curated links for a decision (M-D4).
    No news ingestion, no AI-generated rationale."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    instrument_id: str | None = None
    calendar: CalendarContextDTO
    regime: RegimeContextDTO
    market_health: MarketHealthContextDTO
    external_links: list[ExternalLinkDTO] = Field(default_factory=list)


class RecordJournalRequest(BaseModel):
    """Owner's response to a decision (M-X0, R-9). Nothing is unrecorded."""

    model_config = ConfigDict(frozen=True)

    user_action: Literal["ACCEPTED", "REJECTED", "IGNORED"]
    notes: str = Field(default="", max_length=500)


class JournalEntryDTO(BaseModel):
    """Persisted owner response for one decision."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    user_action: str
    action_ts: datetime
    notes: str = ""


class RecordOutcomeRequest(BaseModel):
    """Realized entry/exit for an accepted decision. PnL and adherence are
    computed server-side from the persisted TradePlan — never client-supplied,
    so every outcome is deterministic and explainable (ADR-005)."""

    model_config = ConfigDict(frozen=True)

    entry_price: Decimal
    exit_price: Decimal
    quantity: int = Field(..., ge=1)
    closed_ts: datetime | None = Field(default=None, description="Defaults to now if omitted")


class TradeOutcomeDTO(BaseModel):
    """Persisted realized outcome for one decision."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: int
    pnl: Decimal
    holding_seconds: int
    adherence: dict[str, bool] = Field(default_factory=dict)
    closed_ts: datetime


class DecisionAnalogDTO(BaseModel):
    """One historical decision with a similar score/confidence/risk fingerprint,
    plus its logged human response and realized outcome, if any (M-X1). Pure
    factual retrieval from the persisted Decision Journal — no generated text."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    instrument_id: str | None = None
    ts: datetime
    decision_type: str
    direction: str
    score: Decimal | None = None
    confidence: Decimal | None = None
    risk: Decimal | None = None
    distance: Decimal
    user_action: str | None = None
    outcome_pnl: Decimal | None = None
    outcome_closed_ts: datetime | None = None
    outcome_return_pct: Decimal | None = None
    outcome_holding_days: Decimal | None = None


class DecisionAnalogsDTO(BaseModel):
    """Nearest-neighbor historical decisions for one decision's fingerprint,
    plus an aggregate read on how similar setups actually played out (UX-6
    Historical Validation) — exact arithmetic over the realized TradeOutcome
    of whichever returned analogs have one; None when none do, never a
    fabricated stand-in."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    analogs: list[DecisionAnalogDTO] = Field(default_factory=list)
    compared_count: int = 0
    win_rate_pct: Decimal | None = None
    avg_return_pct: Decimal | None = None
    avg_holding_days: Decimal | None = None
    min_holding_days: Decimal | None = None
    max_holding_days: Decimal | None = None
    outcomes_sample_size: int = 0


class TrackRecordDTO(BaseModel):
    """Rollup of the owner's full journal + realized-outcome history (AUX-5).
    Pure aggregation over already-persisted per-decision data — no new
    tracking, no new domain computation. Reuses the exact win-rate/avg-return/
    avg-holding arithmetic already established for decision analogs (M-X1);
    None (never a fabricated 0) when a sample is empty."""

    model_config = ConfigDict(frozen=True)

    journal_entry_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    ignored_count: int = 0
    accept_rate_pct: Decimal | None = None

    closed_trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    breakeven_count: int = 0
    win_rate_pct: Decimal | None = None
    total_pnl: Decimal = Decimal("0")
    avg_return_pct: Decimal | None = None
    avg_holding_days: Decimal | None = None

    adherence_check_count: int = 0
    adherence_pass_count: int = 0
    plan_adherence_rate_pct: Decimal | None = None


class CounterfactualGapDTO(BaseModel):
    """One failed quality gate's exact numeric distance to passing (M-X2).
    Computed from already-persisted values vs. current config thresholds —
    never a recomputed score/confidence/risk value."""

    model_config = ConfigDict(frozen=True)

    gate: str
    detail: str
    current: Decimal | None = None
    required: Decimal | None = None
    gap: Decimal | None = None


class DecisionCounterfactualDTO(BaseModel):
    """Exact quantified distance from a WATCH/NO_TRADE decision to the TRADE
    gate — never a generated rationale, only arithmetic over persisted values
    and current config thresholds (M-X2)."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    decision_type: str
    is_trade: bool
    score_current: Decimal | None = None
    score_required: Decimal | None = None
    score_gap: Decimal | None = None
    gates: list[CounterfactualGapDTO] = Field(default_factory=list)
    summary: str


class TradePlanFreshnessDTO(BaseModel):
    """Deterministic decay clock for a TradePlan's validity window (M-X3).
    Pure arithmetic over the plan's already-persisted valid_from/valid_until
    and an as_of instant — never a recomputed plan, never a hidden clock
    read inside an analytical engine."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    has_trade_plan: bool
    as_of: datetime
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    elapsed_seconds: int | None = None
    remaining_seconds: int | None = None
    total_seconds: int | None = None
    decay_fraction: Decimal | None = None
    status: Literal["NO_PLAN", "FRESH", "AGING", "STALE", "EXPIRED"]
    summary: str
