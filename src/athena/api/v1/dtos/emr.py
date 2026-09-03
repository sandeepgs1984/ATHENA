"""EM-6B: typed API response models for the read-only, permanently
"Experimental" Explosive Move Radar (EMR) presentation surface.

Mechanically mirrors `athena.explosive_move.live.presentation`'s own
typed views (EM-6A) -- no business logic here, only serialization shape.
Every field name and semantic here is the EM-6A/EM-5 frozen research
contract's own vocabulary; nothing is renamed into canonical ATHENA
terms (WATCH/TRADE/BUY/SELL/confidence) anywhere in this module.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EmrScanContextDTO(BaseModel):
    """One persisted, `status == 'COMPLETE'` EMR scan run."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    session_date: str
    checkpoint: str
    frozen_model_version: str
    started_ts: str
    finished_ts: str | None
    eligible_count: int | None
    ineligible_count: int | None


class EmrScanAgeDTO(BaseModel):
    """How long ago the scan above completed/started, relative to this
    response's own single captured request time. A fact, never a
    FRESH/STALE classification -- no owner-approved threshold exists."""

    model_config = ConfigDict(frozen=True)

    age_seconds: float
    age_minutes: float
    as_of: str


class EmrCandidateDTO(BaseModel):
    """One EMR research candidate for the TOUCH family at the 10%
    threshold. `rank`/`calibrated_probability`/`deterministic_score` are
    `None`, never `0`, when genuinely unranked/unavailable."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    family: str
    threshold_percent: int
    rank: int | None
    calibrated_probability: float | None
    deterministic_score: float | None
    probability_language: str
    em4b_model_version: str
    em4d_calibration_version: str
    evidence_completeness_known: int
    evidence_completeness_total: int
    data_freshness: str
    feasibility: str
    feasibility_reason: str | None
    state: str
    state_reason: str
    checkpoint_price: str | None
    checkpoint_price_semantic: str | None


class EmrCoverageDTO(BaseModel):
    """Evaluated-vs-ranked coverage for TOUCH-10 within one scan, so a
    short candidate list is never mistaken for complete market
    coverage."""

    model_config = ConfigDict(frozen=True)

    family: str
    threshold_percent: int
    evaluated_count: int
    ranked_count: int
    unranked_count: int
    unranked_reason_counts: tuple[tuple[str, int], ...]


class EmrTouch10RadarDTO(BaseModel):
    """The single coherent EM-6B response: exactly one scan identity (or
    none), its TOUCH-10 candidates, its coverage, and the scan's age --
    all derived from that one frozen scan/run identity. Permanently
    "Experimental" -- `label`/`disclaimer` are always present."""

    model_config = ConfigDict(frozen=True)

    label: str
    disclaimer: str
    scan: EmrScanContextDTO | None
    scan_age: EmrScanAgeDTO | None
    touch_10: tuple[EmrCandidateDTO, ...]
    coverage: EmrCoverageDTO | None
