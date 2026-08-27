"""EM-4B: TRAIN-fitted-only preprocessing for the logistic baseline.

Owner/Chief Architect decision, 2026-08-27 (EM-4 Modeling Contract):
median imputation + missing indicator + standardization for continuous
candidate features; one-hot with an explicit UNKNOWN category for
categorical fields and checkpoint; zero-variance/degenerate columns
dropped deterministically, with provenance, decided ONLY from the fit
population supplied by the caller -- this module never inspects
VALIDATION and has no opinion on which rows constitute "TRAIN": the
caller passes exactly the population a given fit is allowed to see
(the full TRAIN partition for the frozen final model; one CV fold's
chronologically-prior "fit window" during regularization selection --
never the same population for both, which is exactly the leakage the
owner's temporal-CV correction exists to prevent).

Checkpoint is treated as an ordinary categorical field here (one-hot,
explicit UNKNOWN), which is precisely how "pool all 9 checkpoints via a
one-hot covariate, shared coefficients + checkpoint-specific intercept
shifts only" becomes a concrete linear-model design: each checkpoint's
own one-hot coefficient IS its intercept shift.

Categorical encoding uses the FULL category set (no reference level
dropped) -- well-defined under this contract's mandatory L2 penalty
(strictly convex, unlike unregularized OLS/MLE, so the joint
non-identifiability an undropped full one-hot would otherwise cause
does not arise).

Hand-rolled with the standard library's own `statistics` module, not
numpy -- matches this workstream's existing convention of hand-rolling
its own statistics (wilson_interval.py, conditional_analysis.py) rather
than reaching for a dependency this particular computation doesn't
need. numpy/scikit-learn stay scoped to the actual model fit
(em4b_model.py), never to this preprocessing layer.

Pure: no I/O, no randomness.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

EM4B_PREPROCESSING_CONTRACT_VERSION = "em4b-preprocessing-v1"

UNKNOWN_CATEGORY = "UNKNOWN"
_MISSING_SUFFIX = "__missing"


@dataclass(frozen=True, slots=True)
class ContinuousFieldStats:
    name: str
    median: float  # imputation value
    mean: float  # standardization center
    std: float  # standardization scale; 0.0 iff every known value was identical
    known_n: int


@dataclass(frozen=True, slots=True)
class CategoricalFieldSpec:
    name: str
    #: Observed categories (sorted, deterministic) plus a trailing
    #: explicit UNKNOWN_CATEGORY -- always present as a modeling concept
    #: even if this fit population never saw an UNKNOWN value (in which
    #: case its column is zero-variance and gets dropped downstream,
    #: which is itself a transparent, recorded outcome, not a bug).
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreprocessingSpec:
    contract_version: str
    continuous_fields: tuple[str, ...]
    categorical_fields: tuple[str, ...]
    checkpoint_field: str
    continuous_stats: dict[str, ContinuousFieldStats]
    categorical_specs: dict[str, CategoricalFieldSpec]
    checkpoint_spec: CategoricalFieldSpec
    #: Final column order AFTER dropping zero-variance columns -- the
    #: exact order `transform_row` emits values in.
    feature_names: tuple[str, ...]
    dropped_zero_variance_columns: tuple[str, ...]
    fit_row_count: int


def _candidate_column_names(
    continuous_fields: tuple[str, ...],
    categorical_specs: dict[str, CategoricalFieldSpec],
    checkpoint_spec: CategoricalFieldSpec,
) -> tuple[str, ...]:
    names: list[str] = []
    for name in continuous_fields:
        names.append(name)
        names.append(f"{name}{_MISSING_SUFFIX}")
    for name in categorical_specs:
        for category in categorical_specs[name].categories:
            names.append(f"{name}__{category}")
    for category in checkpoint_spec.categories:
        names.append(f"{checkpoint_spec.name}__{category}")
    return tuple(names)


def _raw_row_values(
    row: dict,
    *,
    continuous_fields: tuple[str, ...],
    continuous_stats: dict[str, ContinuousFieldStats],
    categorical_specs: dict[str, CategoricalFieldSpec],
    checkpoint_spec: CategoricalFieldSpec,
    column_names: tuple[str, ...],
) -> list[float]:
    values: dict[str, float] = {}
    for name in continuous_fields:
        stats = continuous_stats[name]
        raw = row.get(name)
        if raw is None:
            values[name] = stats.median
            values[f"{name}{_MISSING_SUFFIX}"] = 1.0
        else:
            values[name] = float(raw)
            values[f"{name}{_MISSING_SUFFIX}"] = 0.0
        if stats.std > 0:
            values[name] = (values[name] - stats.mean) / stats.std
        else:
            values[name] = 0.0  # degenerate field; standardized value is always 0

    for name, spec in categorical_specs.items():
        observed = row.get(name)
        chosen = observed if observed in spec.categories else UNKNOWN_CATEGORY
        for category in spec.categories:
            values[f"{name}__{category}"] = 1.0 if category == chosen else 0.0

    checkpoint_value = row.get(checkpoint_spec.name)
    chosen_cp = checkpoint_value if checkpoint_value in checkpoint_spec.categories else UNKNOWN_CATEGORY
    for category in checkpoint_spec.categories:
        values[f"{checkpoint_spec.name}__{category}"] = 1.0 if category == chosen_cp else 0.0

    return [values[name] for name in column_names]


def fit_preprocessing(
    rows: list[dict],
    *,
    continuous_fields: tuple[str, ...],
    categorical_fields: tuple[str, ...],
    checkpoint_field: str,
    checkpoint_categories: tuple[str, ...],
) -> PreprocessingSpec:
    """``rows`` is exactly the fit population the caller is allowed to
    use (see module docstring) -- a flat dict per observation, keyed by
    field name, values already real Decimal/str/None (evidence values),
    plus ``checkpoint_field``."""

    continuous_stats: dict[str, ContinuousFieldStats] = {}
    for name in continuous_fields:
        known = [float(r[name]) for r in rows if r.get(name) is not None]
        if known:
            median = statistics.median(known)
            mean = statistics.fmean(known)
            std = statistics.pstdev(known) if len(known) > 1 else 0.0
        else:
            median = mean = std = 0.0
        continuous_stats[name] = ContinuousFieldStats(name, median, mean, std, len(known))

    categorical_specs: dict[str, CategoricalFieldSpec] = {}
    for name in categorical_fields:
        observed = sorted({r[name] for r in rows if r.get(name) is not None})
        categorical_specs[name] = CategoricalFieldSpec(name, (*observed, UNKNOWN_CATEGORY))

    checkpoint_spec = CategoricalFieldSpec(checkpoint_field, (*checkpoint_categories, UNKNOWN_CATEGORY))

    candidate_names = _candidate_column_names(continuous_fields, categorical_specs, checkpoint_spec)

    variances: dict[str, list[float]] = {name: [] for name in candidate_names}
    for row in rows:
        raw = _raw_row_values(
            row, continuous_fields=continuous_fields, continuous_stats=continuous_stats,
            categorical_specs=categorical_specs, checkpoint_spec=checkpoint_spec,
            column_names=candidate_names,
        )
        for name, value in zip(candidate_names, raw, strict=True):
            variances[name].append(value)

    kept: list[str] = []
    dropped: list[str] = []
    for name in candidate_names:
        col = variances[name]
        variance = statistics.pvariance(col) if len(col) > 1 else 0.0
        (dropped if variance == 0.0 else kept).append(name)

    return PreprocessingSpec(
        contract_version=EM4B_PREPROCESSING_CONTRACT_VERSION,
        continuous_fields=continuous_fields, categorical_fields=categorical_fields,
        checkpoint_field=checkpoint_field, continuous_stats=continuous_stats,
        categorical_specs=categorical_specs, checkpoint_spec=checkpoint_spec,
        feature_names=tuple(kept), dropped_zero_variance_columns=tuple(dropped),
        fit_row_count=len(rows),
    )


def transform_row(row: dict, spec: PreprocessingSpec) -> list[float]:
    candidate_names = _candidate_column_names(spec.continuous_fields, spec.categorical_specs, spec.checkpoint_spec)
    raw = _raw_row_values(
        row, continuous_fields=spec.continuous_fields, continuous_stats=spec.continuous_stats,
        categorical_specs=spec.categorical_specs, checkpoint_spec=spec.checkpoint_spec,
        column_names=candidate_names,
    )
    by_name = dict(zip(candidate_names, raw, strict=True))
    return [by_name[name] for name in spec.feature_names]


def transform_rows(rows: list[dict], spec: PreprocessingSpec) -> list[list[float]]:
    return [transform_row(row, spec) for row in rows]
