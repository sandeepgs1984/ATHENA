"""EM-5 scanner state machine -- the frozen rank-tier transition table
from `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` Section 3. Every case
here is pure input/output on `determine_next_state`; nothing touches a
probability, a FINAL_TEST statistic, or any other fitted threshold --
transitions are driven only by ordinal rank cutoffs, hard eligibility,
and the `ever_reached`/`prior_state` history facts.
"""

from __future__ import annotations

import inspect

import pytest

from athena.explosive_move.live.state_machine import (
    DEFAULT_RANK_CUTOFFS,
    TERMINAL_STATES,
    RankCutoffs,
    ScannerState,
    determine_next_state,
)


def _next(**kwargs):
    defaults = {
        "rank": None,
        "hard_ineligible": False,
        "already_occurred": False,
        "prior_state": ScannerState.INACTIVE,
        "prior_rank": None,
        "ever_reached": ScannerState.INACTIVE,
    }
    defaults.update(kwargs)
    return determine_next_state(**defaults)


def test_default_rank_cutoffs_are_20_10_5():
    assert RankCutoffs(watch_rank=20, confirmed_rank=10, high_conviction_rank=5) == DEFAULT_RANK_CUTOFFS


def test_already_occurred_takes_priority_over_rank_and_ineligibility():
    result = _next(rank=1, hard_ineligible=True, already_occurred=True, prior_state=ScannerState.WATCH)
    assert result.to_state == ScannerState.TARGET_REACHED
    assert "ALREADY_OCCURRED" in result.reason


def test_hard_ineligible_invalidates_regardless_of_rank():
    result = _next(rank=1, hard_ineligible=True, hard_ineligible_reason="price band conclusively out of reach")
    assert result.to_state == ScannerState.INVALIDATED
    assert result.reason == "price band conclusively out of reach"


def test_hard_ineligible_without_explicit_reason_still_invalidates():
    result = _next(rank=1, hard_ineligible=True)
    assert result.to_state == ScannerState.INVALIDATED
    assert result.reason


@pytest.mark.parametrize("terminal", sorted(TERMINAL_STATES, key=lambda s: s.value))
def test_terminal_states_never_transition_again(terminal):
    result = _next(rank=1, prior_state=terminal, ever_reached=terminal)
    assert result.to_state == terminal
    assert result.from_state == terminal


def test_fresh_entry_into_watch_band_stays_watch_not_developing():
    result = _next(rank=15, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
    assert result.to_state == ScannerState.WATCH


def test_sustained_watch_progresses_to_developing():
    result = _next(rank=15, prior_rank=15, prior_state=ScannerState.WATCH, ever_reached=ScannerState.WATCH)
    assert result.to_state == ScannerState.DEVELOPING


def test_improved_rank_within_watch_band_progresses_to_developing_even_from_inactive():
    result = _next(rank=14, prior_rank=18, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
    assert result.to_state == ScannerState.DEVELOPING


def test_first_checkpoint_in_confirmed_tier_is_capped_at_watch():
    result = _next(rank=8, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
    assert result.to_state == ScannerState.WATCH


def test_confirmed_sustained_from_prior_watch_state():
    result = _next(rank=8, prior_state=ScannerState.WATCH, ever_reached=ScannerState.WATCH)
    assert result.to_state == ScannerState.CONFIRMED


def test_confirmed_sustained_from_ever_reached_even_if_prior_state_regressed():
    result = _next(rank=8, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.WATCH)
    assert result.to_state == ScannerState.CONFIRMED


def test_first_checkpoint_in_high_conviction_tier_is_capped_at_confirmed():
    result = _next(rank=3, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
    assert result.to_state == ScannerState.CONFIRMED


def test_high_conviction_sustained_from_prior_confirmed_state():
    result = _next(rank=3, prior_state=ScannerState.CONFIRMED, ever_reached=ScannerState.CONFIRMED)
    assert result.to_state == ScannerState.HIGH_CONVICTION


def test_high_conviction_sustained_from_ever_reached_confirmed():
    result = _next(rank=3, prior_state=ScannerState.WATCH, ever_reached=ScannerState.CONFIRMED)
    assert result.to_state == ScannerState.HIGH_CONVICTION


def test_dropping_out_of_all_bands_after_watch_plus_becomes_fading_not_inactive():
    result = _next(rank=None, prior_state=ScannerState.DEVELOPING, ever_reached=ScannerState.DEVELOPING)
    assert result.to_state == ScannerState.FADING


def test_dropping_out_from_high_tier_also_becomes_fading_never_invalidated():
    result = _next(rank=None, prior_state=ScannerState.CONFIRMED, ever_reached=ScannerState.HIGH_CONVICTION)
    assert result.to_state == ScannerState.FADING


def test_fading_recovers_into_developing_through_the_identical_watch_rule():
    result = _next(rank=15, prior_rank=None, prior_state=ScannerState.FADING, ever_reached=ScannerState.WATCH)
    assert result.to_state == ScannerState.DEVELOPING


def test_never_qualified_stays_inactive():
    result = _next(rank=None, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
    assert result.to_state == ScannerState.INACTIVE


def test_no_probability_or_confidence_parameter_exists_anywhere_in_the_signature():
    params = inspect.signature(determine_next_state).parameters
    forbidden_substrings = ("probability", "confidence", "final_test", "threshold_prob")
    for name in params:
        assert not any(bad in name.lower() for bad in forbidden_substrings), name


class TestExactRankCutoffBoundaries:
    """The frozen 20/10/5 cutoffs are inclusive (`rank <= cutoff`) --
    proven at the exact boundary values, not just interior ranks like the
    rest of this file uses (15, 8, 3)."""

    def test_rank_20_is_inside_watch_band_rank_21_is_not(self):
        inside = _next(rank=20, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
        outside = _next(rank=21, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
        assert inside.to_state == ScannerState.WATCH
        assert outside.to_state == ScannerState.INACTIVE

    def test_rank_10_is_inside_confirmed_band_rank_11_is_only_watch(self):
        inside = _next(rank=10, prior_state=ScannerState.WATCH, ever_reached=ScannerState.WATCH)
        outside = _next(rank=11, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE)
        assert inside.to_state == ScannerState.CONFIRMED
        assert outside.to_state == ScannerState.WATCH

    def test_rank_5_is_inside_high_conviction_band_rank_6_is_only_confirmed(self):
        inside = _next(rank=5, prior_state=ScannerState.CONFIRMED, ever_reached=ScannerState.CONFIRMED)
        outside = _next(rank=6, prior_state=ScannerState.WATCH, ever_reached=ScannerState.WATCH)
        assert inside.to_state == ScannerState.HIGH_CONVICTION
        assert outside.to_state == ScannerState.CONFIRMED

    def test_boundaries_hold_under_a_non_default_rank_cutoffs_configuration(self):
        """The inclusive-boundary rule itself is exercised, not just the
        default 20/10/5 magnitudes -- proves determine_next_state reads
        `rank_cutoffs` rather than having 20/10/5 baked in anywhere."""
        custom = RankCutoffs(watch_rank=30, confirmed_rank=15, high_conviction_rank=7)
        inside = _next(rank=30, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE,
                      rank_cutoffs=custom)
        outside = _next(rank=31, prior_state=ScannerState.INACTIVE, ever_reached=ScannerState.INACTIVE,
                       rank_cutoffs=custom)
        assert inside.to_state == ScannerState.WATCH
        assert outside.to_state == ScannerState.INACTIVE
