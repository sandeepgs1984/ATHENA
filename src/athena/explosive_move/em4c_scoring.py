"""EM-4C: scores a real observation against an already-frozen EM-4B
logistic artifact.

Applying a FROZEN linear model (dot product + sigmoid) needs no
numerical library -- only FITTING one does. This module stays pure
Python deliberately, so EM-4C's VALIDATION scoring never requires the
optional ``emr-modeling`` dependency group, matching the rest of this
workstream's evaluation scaffolding (em4c_ranking/metrics/aggregation/
report). The frozen coefficients/intercept/preprocessing are read
straight from the EM-4B artifact JSON -- this module never refits,
never touches scikit-learn, and never inspects a row it wasn't handed.

Probability-language discipline (EM-4 Modeling Contract): the value
this module returns is the model's raw sigmoid output, not yet a
calibration-gated "probability" -- EM-4D's calibration step is what
earns that word. Callers must not call this a probability before then.
"""

from __future__ import annotations

import math

from athena.explosive_move.em4b_preprocessing import PreprocessingSpec, transform_row

EM4C_SCORING_CONTRACT_VERSION = "em4c-scoring-v1"


def sigmoid(x: float) -> float:
    """Numerically stable for both large-positive and large-negative x."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def score_logit(
    observation: dict, *, feature_names: tuple[str, ...], coefficients: tuple[float, ...],
    intercept: float, preprocessing: PreprocessingSpec,
) -> float:
    """The frozen model's raw pre-sigmoid linear score -- EM-4D's Platt
    scaling calibrates THIS value, never the already-squashed
    probability (double-sigmoiding a probability is not what Platt
    scaling means)."""

    transformed = transform_row(observation, preprocessing)
    if tuple(preprocessing.feature_names) != feature_names:
        raise ValueError("preprocessing.feature_names does not match the artifact's feature_names")
    return intercept + sum(c * x for c, x in zip(coefficients, transformed, strict=True))


def score_logistic(
    observation: dict, *, feature_names: tuple[str, ...], coefficients: tuple[float, ...],
    intercept: float, preprocessing: PreprocessingSpec,
) -> float:
    linear = score_logit(
        observation, feature_names=feature_names, coefficients=coefficients,
        intercept=intercept, preprocessing=preprocessing,
    )
    return sigmoid(linear)
