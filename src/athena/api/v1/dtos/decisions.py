"""Decisions resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from athena.api.v1.dtos.base import FilterParams, ResourceReference


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
    direction: str = "NONE"
    decision_type: str


class DecisionAnalysisDTO(BaseModel):
    """Composed DTO linking to analytical assessment files."""

    model_config = ConfigDict(frozen=True)

    score_ref: ResourceReference | None = None
    confidence_ref: ResourceReference | None = None
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

    instrument_id: str | None = Field(
        default=None, description="Filter by instrument identifier"
    )
    decision_type: str | None = Field(
        default=None, description="Filter by decision action type"
    )
    direction: str | None = Field(
        default=None, description="Filter by trade direction (LONG, SHORT)"
    )


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

