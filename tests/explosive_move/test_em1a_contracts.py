import json
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import pytest

from athena.explosive_move.contracts import (
    CANDIDATE_CHECKPOINTS_IST,
    EVENT_FAMILIES,
    EVENT_THRESHOLDS_PERCENT,
    CorporateActionCoverage,
    EventRecordReadiness,
    ExclusionReason,
    assess_checkpoint_readiness,
    assess_symbol_day_readiness,
)

CONFIG_PATH = Path(__file__).parents[2] / "config" / "explosive_move.json"
STUDY_START = date(2024, 1, 1)
STUDY_END = date(2024, 12, 31)


def _readiness(**overrides: object) -> EventRecordReadiness:
    arguments: dict[str, object] = {
        "study_start": STUDY_START,
        "study_end": STUDY_END,
        "corporate_actions": CorporateActionCoverage(
            authoritative_start=STUDY_START,
            authoritative_end=STUDY_END,
            action_count=0,
        ),
        "corporate_action_in_reference_window": False,
        "candles_fully_adjusted": False,
        "point_in_time_membership_available": True,
    }
    arguments.update(overrides)
    return assess_symbol_day_readiness(**arguments)  # type: ignore[arg-type]


def test_frozen_config_matches_code_contract() -> None:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert payload["event_contract"]["families"] == [item.value for item in EVENT_FAMILIES]
    assert payload["event_contract"]["threshold_percent"] == list(EVENT_THRESHOLDS_PERCENT)
    assert payload["checkpoints"]["candidate_ist"] == list(CANDIDATE_CHECKPOINTS_IST)
    # EM-1r5 (owner-approved 2026-08-26): all 9 candidates promoted to
    # accepted_ist -- research-ready, not predictive-value-approved. See
    # config/explosive_move.json's _meta.checkpoint_acceptance for the full
    # semantic boundary and artifacts/research/em1r5/reaudit_result.json
    # for the measured evidence.
    assert payload["checkpoints"]["accepted_ist"] == list(CANDIDATE_CHECKPOINTS_IST)
    # EM-1b (owner-approved 2026-08-26/27): the deterministic production
    # label dataset has been generated and the approved chronological
    # partitions assigned. See _meta.partition_contract and
    # artifacts/research/em1b/dataset_index.json for the generated evidence.
    assert payload["study_scope"]["status"] == "LABEL_DATASET_GENERATED"


def test_zero_actions_without_authoritative_coverage_fails_closed() -> None:
    readiness = _readiness(
        corporate_actions=CorporateActionCoverage(None, None, action_count=0)
    )

    assert not readiness.allowed
    assert readiness.reasons == (
        ExclusionReason.CORPORATE_ACTION_COVERAGE_UNAVAILABLE,
    )


def test_incomplete_corporate_action_period_is_excluded() -> None:
    readiness = _readiness(
        corporate_actions=CorporateActionCoverage(
            authoritative_start=date(2024, 2, 1),
            authoritative_end=STUDY_END,
            action_count=2,
        )
    )

    assert ExclusionReason.CORPORATE_ACTION_COVERAGE_INCOMPLETE in readiness.reasons


def test_raw_corporate_action_window_is_excluded() -> None:
    readiness = _readiness(corporate_action_in_reference_window=True)

    assert readiness.reasons == (
        ExclusionReason.UNADJUSTED_CORPORATE_ACTION_WINDOW,
    )


def test_authoritative_no_action_window_can_enter_daily_research() -> None:
    assert _readiness().allowed


def test_missing_point_in_time_membership_is_excluded() -> None:
    readiness = _readiness(point_in_time_membership_available=False)

    assert readiness.reasons == (
        ExclusionReason.POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE,
    )


def test_checkpoint_requires_canonical_complete_intraday_evidence() -> None:
    readiness = assess_checkpoint_readiness(
        _readiness(),
        canonical_intraday_grid=False,
        complete_intraday_session=False,
    )

    assert readiness.reasons == (
        ExclusionReason.NON_CANONICAL_INTRADAY_GRID,
        ExclusionReason.INCOMPLETE_INTRADAY_SESSION,
    )


def test_readiness_contract_is_immutable() -> None:
    readiness = _readiness()

    with pytest.raises(FrozenInstanceError):
        readiness.allowed = False  # type: ignore[misc]
