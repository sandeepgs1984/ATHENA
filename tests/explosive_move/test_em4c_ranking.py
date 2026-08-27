"""EM-4C ranking scaffolding: deterministic tie-breaking, Precision@K,
Lift@K, base-rate comparison -- tested against synthetic fixtures only,
per the Owner/Chief Architect's explicit evaluation-scaffolding scope
(no real VALIDATION outcomes)."""

from __future__ import annotations

from athena.explosive_move.em4c_ranking import (
    ScoredObservation,
    base_rate,
    lift_at_k,
    precision_at_k,
    rank_observations,
)


def _obs(instrument_id: str, score: float | None, label: bool) -> ScoredObservation:
    return ScoredObservation(instrument_id=instrument_id, score=score, label=label)


def test_rank_observations_excludes_unknown_scores():
    obs = (_obs("A", 0.9, True), _obs("B", None, False), _obs("C", 0.5, False))
    ranked = rank_observations(obs)
    assert [o.instrument_id for o in ranked] == ["A", "C"]


def test_rank_observations_ties_break_by_instrument_id_ascending():
    obs = (_obs("ZZZ", 0.7, False), _obs("AAA", 0.7, True), _obs("MMM", 0.9, True))
    ranked = rank_observations(obs)
    assert [o.instrument_id for o in ranked] == ["MMM", "AAA", "ZZZ"]


def test_rank_observations_is_deterministic_across_repeated_calls():
    obs = tuple(_obs(f"I{i}", float(i % 5), i % 2 == 0) for i in range(30))
    assert rank_observations(obs) == rank_observations(obs)


def test_base_rate_includes_unknown_scored_observations():
    obs = (_obs("A", 0.9, True), _obs("B", None, False), _obs("C", 0.5, True))
    assert base_rate(obs) == 2 / 3


def test_base_rate_empty_is_none():
    assert base_rate(()) is None


def test_precision_at_k_basic():
    obs = (
        _obs("A", 0.9, True), _obs("B", 0.8, True), _obs("C", 0.7, False),
        _obs("D", 0.6, False), _obs("E", 0.5, True),
    )
    result = precision_at_k(obs, k=3)
    assert result.k_effective == 3
    assert result.positive_in_top_k == 2
    assert result.precision == 2 / 3
    assert result.population_below_k is False


def test_precision_at_k_population_smaller_than_k_still_computes_over_effective():
    obs = (_obs("A", 0.9, True), _obs("B", 0.8, False))
    result = precision_at_k(obs, k=5)
    assert result.k_effective == 2
    assert result.population_below_k is True
    assert result.precision == 1 / 2


def test_precision_at_k_no_known_scores_is_unknown():
    obs = (_obs("A", None, True), _obs("B", None, False))
    result = precision_at_k(obs, k=5)
    assert result.precision is None
    assert result.unknown_reason is not None


def test_precision_at_k_rejects_nonpositive_k():
    import pytest

    with pytest.raises(ValueError):
        precision_at_k((), k=0)


def test_lift_at_k_computed_against_base_rate():
    obs = (
        _obs("A", 0.9, True), _obs("B", 0.8, True), _obs("C", 0.7, False),
        _obs("D", 0.6, False), _obs("E", 0.5, False), _obs("F", 0.4, False),
        _obs("G", 0.3, False), _obs("H", 0.2, False), _obs("I", 0.1, False), _obs("J", 0.05, False),
    )
    result = lift_at_k(obs, k=2)
    # precision@2 = 1.0 (both top-2 positive); base_rate = 2/10 = 0.2
    assert result.precision_at_k == 1.0
    assert result.base_rate == 0.2
    assert result.lift == 5.0


def test_lift_at_k_zero_base_rate_is_undefined():
    obs = (_obs("A", 0.9, False), _obs("B", 0.8, False))
    result = lift_at_k(obs, k=1)
    assert result.lift is None
    assert result.unknown_reason is not None


def test_lift_at_k_propagates_unknown_precision():
    obs = (_obs("A", None, True),)
    result = lift_at_k(obs, k=1)
    assert result.lift is None
    assert result.precision_at_k is None
