"""Decisions resource DTOs (P8.3)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

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
