"""ID-11 Owner-facing Intraday Intelligence read model.

`IntradayIntelligenceDTO` composes the already-frozen EntryQualification ->
EntryActionability -> PositionSizing -> LivePlanSupervision chain into one
coherent, read-only Owner-facing response for a single canonical Decision.
No irrelevant ID-8 research field (MFE/MAE, bootstrap, PR-AUC, validation
tables) ever appears here -- only production concepts already absorbed into
the frozen ID-7/ID-9/ID-10 runtime contracts.

Every nested `state`/`coherence`/`currentness` field's `Literal` includes an
explicit `"UNAVAILABLE"` value, following the exact `AdvisoryFreshnessDTO`/
`AthenaCycleStatusDTO` convention (`dtos/dashboard.py`) -- `UNAVAILABLE` is
reserved strictly for "the read model genuinely could not obtain/derive this
artifact" (no EQ row, EQ `INCOHERENT`, no EA row), never for a value a
frozen engine actually computed (e.g. a legitimate `NOT_SIZED`/
`NOT_APPLICABLE` verdict is rendered as itself, not folded into
`UNAVAILABLE` -- see the ID-11 design contract §1/§8).

`total_deployable_capital` and every other raw `CapitalPolicy` internal are
deliberately never fields on this DTO (§11 of the design contract) -- the
minimal Owner sizing presentation is quantity, lot size, binding
constraint, and policy version only.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntradayIdentityDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    instrument_id: str | None
    decision_type: str
    direction: str
    session_date: date | None
    run_id: str
    cycle_id: str
    eq_methodology_version: str | None = None
    ea_methodology_version: str | None = None


class IntradayQualificationDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal[
        "OUT_OF_SCOPE",
        "UNKNOWN",
        "NOT_YET",
        "QUALIFIED",
        "DISQUALIFIED_FOR_SESSION",
        "EXPIRED",
        "UNAVAILABLE",
    ]
    coherence: Literal["COHERENT", "INCOHERENT", "UNAVAILABLE"]
    reason_summary: str | None = None
    evidence_summary: str | None = None
    evidence_as_of: datetime | None = None


class IntradayOperativeInvalidationDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Decimal
    basis: str


class IntradayActionabilityDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal["UNKNOWN", "NOT_ACTIONABLE", "ACTIONABLE", "UNAVAILABLE"]
    reason: str | None = None
    entry_reference: Decimal | None = None
    operative_invalidation: IntradayOperativeInvalidationDTO | None = None
    t1: Decimal | None = None
    t2: Decimal | None = None
    reward_risk_informational: Decimal | None = None
    evidence_as_of: datetime | None = None
    entry_actionability_as_of: datetime | None = None
    currentness: Literal[
        "CURRENT",
        "STALE",
        "SUPERSEDED",
        "SESSION_CLOSED",
        "METHODOLOGY_NOT_ACTIONABLE",
        "UNAVAILABLE",
    ]
    currentness_explanation: str | None = None


class IntradaySizingDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal["SIZED", "NOT_SIZED", "ZERO_QUANTITY_UNDER_POLICY", "UNAVAILABLE"]
    reason: str | None = None
    suggested_quantity: Decimal | None = None
    lot_size: int | None = None
    binding_constraint: str | None = None
    policy_version: str | None = None


class IntradayVwapLossEvidenceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    triggered: bool
    first_triggered_as_of: datetime | None = None
    trigger_close: Decimal | None = None
    trigger_vwap: Decimal | None = None


class IntradaySupervisionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Literal["NOT_APPLICABLE", "VALID", "INVALIDATED", "UNAVAILABLE"]
    reason: str | None = None
    target_progress: Literal["NONE_REACHED", "T1_REACHED", "T2_REACHED", "UNAVAILABLE"]
    vwap_loss_evidence: IntradayVwapLossEvidenceDTO | None = None
    supervision_as_of: datetime | None = None
    evaluated_at: datetime | None = None


class IntradayAsOfSummaryDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    computed_at: datetime
    freshest_evidence_as_of: datetime | None = None


class IntradayIntelligenceDTO(BaseModel):
    """One coherent Owner-facing read model for the entire ID-6->ID-10
    Intraday Plan chain, anchored on a single canonical `decision_id`."""

    model_config = ConfigDict(frozen=True)

    identity: IntradayIdentityDTO
    qualification: IntradayQualificationDTO
    actionability: IntradayActionabilityDTO
    sizing: IntradaySizingDTO
    supervision: IntradaySupervisionDTO
    as_of_summary: IntradayAsOfSummaryDTO
