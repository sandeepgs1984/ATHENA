"""EM-5 contract Section 9's mandated test: sum(all logit contributions)
+ intercept must equal the persisted raw logit EXACTLY -- a direct
equality check, not an approximation. Run against the REAL promoted
TOUCH_10 artifact, not a synthetic fixture."""

from __future__ import annotations

from pathlib import Path

from athena.explosive_move.em4c_scoring import score_logit
from athena.explosive_move.live.explanation import compute_logit_contributions, top_contributions
from athena.explosive_move.live.frozen_inference import load_frozen_model

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _model():
    return load_frozen_model(config_dir=CONFIG_DIR, version="v1", family="TOUCH", threshold_percent=10)


def _partial_observation() -> dict:
    return {
        "session_date": "2026-08-28", "checkpoint_ist": "12:00",
        "sma20_rel": "0.03", "rsi14": "62.5", "regime_trend": "TREND_UP",
    }


def test_sum_of_contributions_equals_raw_logit_exactly_all_missing():
    model = _model()
    observation = {"session_date": "2026-08-28", "checkpoint_ist": "12:00"}
    raw_logit = score_logit(
        observation, feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    contributions = compute_logit_contributions(
        observation, feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    assert sum(c.contribution for c in contributions) == raw_logit


def test_sum_of_contributions_equals_raw_logit_exactly_partial_evidence():
    model = _model()
    observation = _partial_observation()
    raw_logit = score_logit(
        observation, feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    contributions = compute_logit_contributions(
        observation, feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    assert sum(c.contribution for c in contributions) == raw_logit


def test_intercept_is_listed_once_separately_not_folded_into_a_feature():
    model = _model()
    contributions = compute_logit_contributions(
        _partial_observation(), feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    intercept_terms = [c for c in contributions if c.term == "intercept"]
    assert len(intercept_terms) == 1
    assert intercept_terms[0].contribution == model.intercept
    assert len(contributions) == len(model.feature_names) + 1


def test_missing_indicator_terms_are_flagged():
    model = _model()
    contributions = compute_logit_contributions(
        {"session_date": "2026-08-28", "checkpoint_ist": "12:00"},
        feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    missing_terms = [c for c in contributions if c.is_missing_indicator]
    assert missing_terms  # every continuous field's __missing indicator fires when all evidence is absent
    assert all(c.term.endswith("__missing") for c in missing_terms)


def test_top_contributions_never_ranks_the_intercept_as_evidence():
    model = _model()
    contributions = compute_logit_contributions(
        _partial_observation(), feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    positive, negative = top_contributions(contributions, k=5)
    assert all(c.term != "intercept" for c in positive)
    assert all(c.term != "intercept" for c in negative)


def test_top_contributions_are_ranked_by_this_candidates_own_absolute_contribution():
    model = _model()
    contributions = compute_logit_contributions(
        _partial_observation(), feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    positive, _ = top_contributions(contributions, k=3)
    values = [c.contribution for c in positive]
    assert values == sorted(values, reverse=True)
    assert all(v > 0 for v in values)


def test_top_contributions_respects_k():
    model = _model()
    contributions = compute_logit_contributions(
        _partial_observation(), feature_names=model.feature_names, coefficients=model.coefficients,
        intercept=model.intercept, preprocessing=model.preprocessing,
    )
    positive, negative = top_contributions(contributions, k=2)
    assert len(positive) <= 2
    assert len(negative) <= 2
