"""EM-1b chronological partition contract (Owner/Chief Architect approval,
2026-08-26): frozen TRAIN/VALIDATION/CALIBRATION/FINAL_TEST cutoff dates.
Tests lock down the exact approved dates and the strictly-chronological,
contiguous, non-overlapping invariant the approval requires."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from athena.explosive_move.partitions import (
    PARTITION_BOUNDARIES,
    PARTITION_CONTRACT_VERSION,
    PartitionBoundary,
    PartitionRole,
    _validated,
    partition_for_session_date,
)

CONFIG_PATH = Path(__file__).parents[2] / "config" / "explosive_move.json"


def test_exact_approved_cutoff_dates_are_frozen():
    expected = {
        PartitionRole.TRAIN: (date(2023, 8, 14), date(2025, 5, 31)),
        PartitionRole.VALIDATION: (date(2025, 6, 1), date(2025, 9, 30)),
        PartitionRole.CALIBRATION: (date(2025, 10, 1), date(2025, 12, 31)),
        PartitionRole.FINAL_TEST: (date(2026, 1, 1), date(2026, 8, 21)),
    }
    actual = {b.role: (b.start_date, b.end_date) for b in PARTITION_BOUNDARIES}
    assert actual == expected


def test_boundaries_are_in_declared_chronological_order():
    roles = [b.role for b in PARTITION_BOUNDARIES]
    assert roles == [
        PartitionRole.TRAIN, PartitionRole.VALIDATION,
        PartitionRole.CALIBRATION, PartitionRole.FINAL_TEST,
    ]


def test_session_date_resolves_to_expected_partition():
    assert partition_for_session_date(date(2023, 8, 14)) is PartitionRole.TRAIN
    assert partition_for_session_date(date(2025, 5, 31)) is PartitionRole.TRAIN
    assert partition_for_session_date(date(2025, 6, 1)) is PartitionRole.VALIDATION
    assert partition_for_session_date(date(2025, 9, 30)) is PartitionRole.VALIDATION
    assert partition_for_session_date(date(2025, 10, 1)) is PartitionRole.CALIBRATION
    assert partition_for_session_date(date(2025, 12, 31)) is PartitionRole.CALIBRATION
    assert partition_for_session_date(date(2026, 1, 1)) is PartitionRole.FINAL_TEST
    assert partition_for_session_date(date(2026, 8, 21)) is PartitionRole.FINAL_TEST


def test_date_outside_the_frozen_contract_raises():
    with pytest.raises(ValueError):
        partition_for_session_date(date(2023, 8, 13))
    with pytest.raises(ValueError):
        partition_for_session_date(date(2026, 8, 22))


def test_contract_version_is_declared():
    assert PARTITION_CONTRACT_VERSION == "em1b-partition-v1"


# --------------------------------------------------------------------------- #
# Non-vacuous guard: reintroduce a real overlap and a real gap and confirm
# _validated actually rejects them, proving the frozen boundaries above are
# genuinely being checked and not just declared.
# --------------------------------------------------------------------------- #

def test_validation_rejects_an_overlapping_boundary_pair():
    overlapping = (
        PartitionBoundary(PartitionRole.TRAIN, date(2023, 8, 14), date(2025, 5, 31)),
        PartitionBoundary(PartitionRole.VALIDATION, date(2025, 5, 31), date(2025, 9, 30)),
    )
    with pytest.raises(ValueError, match="non-overlapping"):
        _validated(overlapping)


def test_validation_rejects_a_gap_between_boundaries():
    gapped = (
        PartitionBoundary(PartitionRole.TRAIN, date(2023, 8, 14), date(2025, 5, 31)),
        PartitionBoundary(PartitionRole.VALIDATION, date(2025, 6, 3), date(2025, 9, 30)),
    )
    with pytest.raises(ValueError, match="contiguous"):
        _validated(gapped)


def test_validation_accepts_the_real_approved_boundaries():
    # the exact production tuple must itself pass validation unmodified
    assert _validated(PARTITION_BOUNDARIES) == PARTITION_BOUNDARIES


def test_boundary_rejects_end_before_start():
    with pytest.raises(ValueError):
        PartitionBoundary(PartitionRole.TRAIN, date(2025, 1, 2), date(2025, 1, 1))


def test_validation_rejects_empty_contract():
    with pytest.raises(ValueError):
        _validated(())


def test_single_day_boundary_is_valid_and_contiguous_check_uses_one_day_step():
    one_day = PartitionBoundary(PartitionRole.TRAIN, date(2024, 1, 1), date(2024, 1, 1))
    next_day = PartitionBoundary(PartitionRole.VALIDATION, date(2024, 1, 2), date(2024, 1, 3))
    assert _validated((one_day, next_day)) == (one_day, next_day)
    assert one_day.end_date + timedelta(days=1) == next_day.start_date


# --------------------------------------------------------------------------- #
# Owner-mandated reproducibility properties (2026-08-26 approval): every
# admitted study date maps to exactly one partition; assignment is a pure,
# order-independent function of the date alone.
# --------------------------------------------------------------------------- #

def test_every_calendar_day_in_the_frozen_study_window_maps_to_exactly_one_partition():
    start = PARTITION_BOUNDARIES[0].start_date
    end = PARTITION_BOUNDARIES[-1].end_date
    day = start
    seen = 0
    while day <= end:
        role = partition_for_session_date(day)
        assert role in {b.role for b in PARTITION_BOUNDARIES}
        day += timedelta(days=1)
        seen += 1
    assert seen == (end - start).days + 1


def test_assignment_is_deterministic_across_repeated_calls():
    probe = date(2025, 6, 1)
    results = {partition_for_session_date(probe) for _ in range(50)}
    assert results == {PartitionRole.VALIDATION}


def test_assignment_is_independent_of_caller_iteration_order():
    dates = [
        date(2023, 8, 14), date(2025, 5, 31), date(2025, 6, 1), date(2025, 9, 30),
        date(2025, 10, 1), date(2025, 12, 31), date(2026, 1, 1), date(2026, 8, 21),
    ]
    forward = {d: partition_for_session_date(d) for d in dates}
    shuffled = {d: partition_for_session_date(d) for d in reversed(dates)}
    assert forward == shuffled


def test_frozen_config_matches_the_code_contract():
    """config/explosive_move.json's _meta.partition_contract is a
    human-readable mirror of this module's PARTITION_BOUNDARIES, frozen by
    the same 2026-08-26 Owner/Chief Architect approval -- the two must
    never silently drift apart."""
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    boundaries = payload["_meta"]["partition_contract"]["boundaries"]
    assert payload["_meta"]["partition_contract"]["contract_version"] == PARTITION_CONTRACT_VERSION
    assert [b["role"] for b in boundaries] == [r.role.value for r in PARTITION_BOUNDARIES]
    assert [b["start_date"] for b in boundaries] == [
        r.start_date.isoformat() for r in PARTITION_BOUNDARIES
    ]
    assert [b["end_date"] for b in boundaries] == [r.end_date.isoformat() for r in PARTITION_BOUNDARIES]
