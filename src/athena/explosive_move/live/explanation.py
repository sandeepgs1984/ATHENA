"""EM-5 contract Section 9: per-candidate logit-contribution
explanation -- "strongest positive/negative evidence" computed
honestly as THIS candidate's own `coefficient x transformed_value` per
term, never a "probability contribution" (Platt calibration is a
single 2-parameter transform applied to the SUMMED logit, §7 -- it
does not distribute linearly back across individual terms). Ranked by
this candidate's own absolute contribution, not by global coefficient
magnitude, which would misrepresent a candidate that doesn't actually
exhibit a large-coefficient feature.

Reuses `em4b_preprocessing.transform_row` unmodified, so the
contribution vector is guaranteed aligned, term-for-term, with
`em4c_scoring.score_logit`'s own dot product -- `sum(contributions) +
intercept == raw_logit` holds by construction, not by approximation.
"""

from __future__ import annotations

from dataclasses import dataclass

from athena.explosive_move.em4b_preprocessing import PreprocessingSpec, transform_row

_MISSING_SUFFIX = "__missing"


@dataclass(frozen=True, slots=True)
class LogitContribution:
    term: str
    coefficient: float
    transformed_value: float
    contribution: float  # coefficient * transformed_value
    is_missing_indicator: bool


def compute_logit_contributions(
    observation: dict, *, feature_names: tuple[str, ...], coefficients: tuple[float, ...],
    intercept: float, preprocessing: PreprocessingSpec,
) -> tuple[LogitContribution, ...]:
    """Every model term, in `feature_names` order, plus a separate
    `"intercept"` term appended last (never folded into any feature's
    contribution). Includes zero-valued one-hot terms too -- summing
    the full vector is what makes the auditability equality exact and
    trivial; callers select a display subset via `top_contributions`."""

    transformed = transform_row(observation, preprocessing)
    terms = [
        LogitContribution(
            term=name, coefficient=coef, transformed_value=value, contribution=coef * value,
            is_missing_indicator=name.endswith(_MISSING_SUFFIX),
        )
        for name, coef, value in zip(feature_names, coefficients, transformed, strict=True)
    ]
    terms.append(
        LogitContribution(
            term="intercept", coefficient=intercept, transformed_value=1.0,
            contribution=intercept, is_missing_indicator=False,
        )
    )
    return tuple(terms)


def top_contributions(
    contributions: tuple[LogitContribution, ...], *, k: int,
) -> tuple[tuple[LogitContribution, ...], tuple[LogitContribution, ...]]:
    """(top_k_positive, top_k_negative) by this candidate's own signed
    contribution -- the intercept is excluded (listed separately per
    the contract, not ranked as "evidence")."""

    non_intercept = [c for c in contributions if c.term != "intercept"]
    positive = sorted((c for c in non_intercept if c.contribution > 0), key=lambda c: -c.contribution)
    negative = sorted((c for c in non_intercept if c.contribution < 0), key=lambda c: c.contribution)
    return tuple(positive[:k]), tuple(negative[:k])
