"""EM-4A deterministic evidence score: predeclared vote semantics, no
lift-magnitude weighting, UNKNOWN/unsupported evidence never votes."""

from __future__ import annotations

from decimal import Decimal

import pytest

from athena.explosive_move.deterministic_score import (
    DeterministicScoreResult,
    VoteRule,
    compile_deterministic_rules,
    score_observation,
)

KEY = ("TOUCH", 10, "09:20")


def _register_entry(feature, bin_, family, threshold, checkpoint, classification, abs_diff):
    return {
        "feature": feature, "bin": bin_, "family": family, "threshold": threshold,
        "checkpoint": checkpoint, "classification": classification, "absolute_difference": abs_diff,
    }


def test_compile_skips_insufficient_support():
    register = [_register_entry("rsi14", "Q5(>=70)", *KEY, "INSUFFICIENT_SUPPORT", 0.05)]
    rules = compile_deterministic_rules(register)
    assert rules == {}


def test_compile_skips_unknown_bin():
    register = [_register_entry("rsi14", "UNKNOWN", *KEY, "EXPLORATORY_CANDIDATE", 0.05)]
    assert compile_deterministic_rules(register) == {}


def test_compile_skips_zero_difference():
    register = [_register_entry("rsi14", "Q3(...)", *KEY, "EXPLORATORY_CANDIDATE", 0.0)]
    assert compile_deterministic_rules(register) == {}


def test_compile_direction_matches_sign_of_absolute_difference():
    register = [
        _register_entry("rsi14", "Q5(>=70)", *KEY, "EXPLORATORY_CANDIDATE", 0.02),
        _register_entry("atr14_norm", "Q1(<0.01)", *KEY, "EXPLORATORY_CANDIDATE", -0.01),
    ]
    rules = compile_deterministic_rules(register)
    assert rules[KEY] == (
        VoteRule("rsi14", "Q5(>=70)", 1),
        VoteRule("atr14_norm", "Q1(<0.01)", -1),
    )


def test_score_with_no_admitted_evidence_is_unknown():
    result = score_observation(rules=(), evidence={}, bin_edges={})
    assert result.score is None
    assert result.vote_count == 0
    assert result.unknown_reason is not None


def test_score_unknown_valued_feature_does_not_vote():
    rules = (VoteRule("rsi14", "Q5(>=70)", 1),)
    result = score_observation(rules=rules, evidence={"rsi14": None}, bin_edges={})
    assert result.score is None
    assert result.vote_count == 0


def test_score_positive_vote_when_bin_matches():
    edges = (Decimal("20"), Decimal("40"), Decimal("60"), Decimal("80"))
    rules = (VoteRule("rsi14", "Q5(>=80)", 1),)
    result = score_observation(
        rules=rules, evidence={"rsi14": Decimal("85")}, bin_edges={"rsi14": edges},
    )
    assert result.score == 1.0
    assert result.vote_count == 1
    assert result.positive_vote_count == 1
    assert result.negative_vote_count == 0


def test_score_no_vote_when_bin_does_not_match():
    edges = (Decimal("20"), Decimal("40"), Decimal("60"), Decimal("80"))
    rules = (VoteRule("rsi14", "Q5(>=80)", 1),)
    result = score_observation(
        rules=rules, evidence={"rsi14": Decimal("10")}, bin_edges={"rsi14": edges},
    )
    assert result.score is None
    assert result.vote_count == 0


def test_score_categorical_feature_matches_by_value_not_bin_edges():
    rules = (VoteRule("regime_trend", "BULL_TREND", 1),)
    result = score_observation(
        rules=rules, evidence={"regime_trend": "BULL_TREND"}, bin_edges={},
    )
    assert result.score == 1.0


def test_score_mixed_votes_produces_net_normalized_score():
    edges_rsi = (Decimal("20"), Decimal("40"), Decimal("60"), Decimal("80"))
    rules = (
        VoteRule("rsi14", "Q5(>=80)", 1),
        VoteRule("atr14_norm", "Q1(<0.01)", -1),
        VoteRule("regime_gap", "GAP_UP", 1),
    )
    result = score_observation(
        rules=rules,
        evidence={"rsi14": Decimal("85"), "atr14_norm": Decimal("0.005"), "regime_gap": "NO_GAP"},
        bin_edges={"rsi14": edges_rsi, "atr14_norm": (Decimal("0.01"), Decimal("0.02"))},
    )
    # rsi14 -> +1, atr14_norm -> -1, regime_gap doesn't match ("NO_GAP" != "GAP_UP") -> no vote
    assert result.vote_count == 2
    assert result.positive_vote_count == 1
    assert result.negative_vote_count == 1
    assert result.score == 0.0


def test_score_ten_positive_votes_distinguishable_from_one_positive_vote():
    """A score of +1.0 from one vote must remain distinguishable from
    +1.0 from ten votes -- via vote_count, not the score value itself."""
    one_vote = DeterministicScoreResult(
        score=1.0, vote_count=1, positive_vote_count=1, negative_vote_count=0, unknown_reason=None,
    )
    ten_votes = DeterministicScoreResult(
        score=1.0, vote_count=10, positive_vote_count=10, negative_vote_count=0, unknown_reason=None,
    )
    assert one_vote.score == ten_votes.score
    assert one_vote.vote_count != ten_votes.vote_count


def test_result_invariant_score_unknown_iff_zero_votes():
    with pytest.raises(ValueError):
        DeterministicScoreResult(
            score=0.5, vote_count=0, positive_vote_count=0, negative_vote_count=0, unknown_reason=None,
        )
    with pytest.raises(ValueError):
        DeterministicScoreResult(
            score=None, vote_count=1, positive_vote_count=1, negative_vote_count=0, unknown_reason=None,
        )


def test_result_invariant_vote_count_matches_pos_plus_neg():
    with pytest.raises(ValueError):
        DeterministicScoreResult(
            score=0.5, vote_count=5, positive_vote_count=1, negative_vote_count=1, unknown_reason=None,
        )
