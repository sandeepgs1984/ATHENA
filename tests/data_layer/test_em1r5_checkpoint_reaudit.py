"""EM-1r5 re-audit: unit tests for the small pure extraction helpers.
The core admission logic (corporate_action_crosses_boundary) has its own
dedicated tests in test_corporate_action_boundary.py; this file covers
only the EM-1r2-manifest-shape wiring specific to this script."""

from __future__ import annotations

from datetime import date

from athena.data.em1r5_checkpoint_reaudit import (
    _action_type_by_instrument_and_date,
    _corporate_action_coverage,
    _ex_dates_by_instrument,
)


def _em1r2_fixture(*, complete: bool = True) -> dict:
    return {
        "study_start": "2023-08-11",
        "study_end": "2026-08-21",
        "retrieval_slices": [
            {"complete": complete},
            {"complete": True},
        ],
        "actions": [
            {"instrument_id": "NSE:AAA", "ex_date": "2024-01-10", "action_type": "DIVIDEND"},
            {"instrument_id": "NSE:AAA", "ex_date": "2024-06-01", "action_type": "SPLIT"},
            {"instrument_id": "NSE:BBB", "ex_date": "2024-01-10", "action_type": "BONUS"},
        ],
    }


def test_corporate_action_coverage_when_all_slices_complete():
    coverage = _corporate_action_coverage(_em1r2_fixture(complete=True))
    assert coverage.authoritative_start.isoformat() == "2023-08-11"
    assert coverage.authoritative_end.isoformat() == "2026-08-21"
    assert coverage.action_count == 3


def test_corporate_action_coverage_when_any_slice_incomplete_has_no_authority():
    """An incomplete retrieval slice must never be silently treated as full
    coverage -- this feeds CORPORATE_ACTION_COVERAGE_UNAVAILABLE upstream."""
    coverage = _corporate_action_coverage(_em1r2_fixture(complete=False))
    assert coverage.authoritative_start is None
    assert coverage.authoritative_end is None


def test_ex_dates_by_instrument_groups_multiple_actions_per_instrument():
    result = _ex_dates_by_instrument(_em1r2_fixture())
    assert result["NSE:AAA"] == {date(2024, 1, 10), date(2024, 6, 1)}
    assert result["NSE:BBB"] == {date(2024, 1, 10)}


def test_action_type_by_instrument_and_date_keys_correctly():
    result = _action_type_by_instrument_and_date(_em1r2_fixture())

    assert result[("NSE:AAA", date(2024, 1, 10))] == {"DIVIDEND"}
    assert result[("NSE:AAA", date(2024, 6, 1))] == {"SPLIT"}
    assert result[("NSE:BBB", date(2024, 1, 10))] == {"BONUS"}
