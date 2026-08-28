"""EM-5 ranking -- thin wrapper over em4c_ranking.rank_observations;
proves the frozen tie-break rule (score descending, instrument_id
ascending) carries through unmodified into 1-indexed live rank
positions."""

from __future__ import annotations

from athena.explosive_move.live.ranking import rank_candidates


def test_higher_score_ranks_first():
    ranks = rank_candidates({"A": 0.10, "B": 0.90, "C": 0.50})
    assert ranks == {"B": 1, "C": 2, "A": 3}


def test_ties_broken_by_instrument_id_ascending():
    ranks = rank_candidates({"ZZZ": 0.5, "AAA": 0.5})
    assert ranks == {"AAA": 1, "ZZZ": 2}


def test_empty_scores_yields_empty_ranks():
    assert rank_candidates({}) == {}


def test_single_candidate_is_rank_1():
    assert rank_candidates({"A": 0.01}) == {"A": 1}
