"""EM-4B preprocessing: TRAIN-fitted-only median imputation + missing
indicator + standardization (continuous) and explicit-UNKNOWN one-hot
(categorical/checkpoint), with deterministic zero-variance dropping --
tested against synthetic fixtures only."""

from __future__ import annotations

from decimal import Decimal

from athena.explosive_move.em4b_preprocessing import (
    UNKNOWN_CATEGORY,
    deserialize_preprocessing,
    fit_preprocessing,
    transform_row,
)

CONTINUOUS = ("rsi14",)
CATEGORICAL = ("regime_trend",)
CHECKPOINTS = ("09:20", "09:30")


def _row(rsi, regime, cp):
    return {"rsi14": rsi, "regime_trend": regime, "checkpoint_ist": cp}


def _fit(rows):
    return fit_preprocessing(
        rows, continuous_fields=CONTINUOUS, categorical_fields=CATEGORICAL,
        checkpoint_field="checkpoint_ist", checkpoint_categories=CHECKPOINTS,
    )


def test_continuous_median_used_for_imputation():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("30"), "BULL_TREND", "09:20"),
            _row(Decimal("50"), "BULL_TREND", "09:20")]
    spec = _fit(rows)
    assert spec.continuous_stats["rsi14"].median == 30.0


def test_missing_indicator_set_when_value_is_none():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(None, "BULL_TREND", "09:20")]
    spec = _fit(rows)
    transformed = transform_row(_row(None, "BULL_TREND", "09:20"), spec)
    idx = spec.feature_names.index("rsi14__missing")
    assert transformed[idx] == 1.0


def test_missing_value_imputed_then_standardized_to_zero_mean_contribution():
    # two known values -> median = mean; imputed row's standardized value should equal 0
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("30"), "BULL_TREND", "09:20"),
            _row(None, "BULL_TREND", "09:20")]
    spec = _fit(rows)
    transformed = transform_row(_row(None, "BULL_TREND", "09:20"), spec)
    idx = spec.feature_names.index("rsi14")
    # imputed with median=20 (of 10,30), standardized against mean=20 -> 0
    assert transformed[idx] == 0.0


def test_categorical_gets_explicit_unknown_category():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), "BEAR_TREND", "09:20")]
    spec = _fit(rows)
    assert UNKNOWN_CATEGORY in spec.categorical_specs["regime_trend"].categories


def test_unknown_regime_value_routes_to_unknown_column():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), None, "09:20"),
            _row(Decimal("30"), "BULL_TREND", "09:30")]
    spec = _fit(rows)
    transformed = transform_row(_row(Decimal("10"), None, "09:20"), spec)
    unk_idx = spec.feature_names.index("regime_trend__UNKNOWN")
    known_idx = spec.feature_names.index("regime_trend__BULL_TREND")
    assert transformed[unk_idx] == 1.0
    assert transformed[known_idx] == 0.0


def test_checkpoint_one_hot_encoded():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), "BULL_TREND", "09:30")]
    spec = _fit(rows)
    transformed = transform_row(_row(Decimal("10"), "BULL_TREND", "09:30"), spec)
    idx_0920 = spec.feature_names.index("checkpoint_ist__09:20")
    idx_0930 = spec.feature_names.index("checkpoint_ist__09:30")
    assert transformed[idx_0920] == 0.0
    assert transformed[idx_0930] == 1.0


def test_zero_variance_column_dropped_with_provenance():
    # regime_trend is constant across the whole fit population -> both
    # its BULL_TREND (always 1) and UNKNOWN (always 0) columns are
    # zero-variance and must be dropped.
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), "BULL_TREND", "09:30")]
    spec = _fit(rows)
    assert "regime_trend__BULL_TREND" not in spec.feature_names
    assert "regime_trend__BULL_TREND" in spec.dropped_zero_variance_columns
    assert "regime_trend__UNKNOWN" in spec.dropped_zero_variance_columns


def test_degenerate_continuous_field_standardizes_to_zero_and_gets_dropped():
    # rsi14 is constant (50) across the fit population -- std is 0 (no
    # division by zero), its standardized value is always 0, and the
    # resulting zero-variance column is dropped, same as a degenerate
    # categorical column.
    rows = [_row(Decimal("50"), "BULL_TREND", "09:20"), _row(Decimal("50"), "BEAR_TREND", "09:20")]
    spec = _fit(rows)
    assert spec.continuous_stats["rsi14"].std == 0.0
    assert "rsi14" not in spec.feature_names
    assert "rsi14" in spec.dropped_zero_variance_columns


def test_fit_row_count_recorded():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), "BEAR_TREND", "09:30")]
    spec = _fit(rows)
    assert spec.fit_row_count == 2


def test_deserialize_round_trips_to_identical_transform():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), "BEAR_TREND", "09:30"),
            _row(None, None, "09:20")]
    spec = _fit(rows)
    payload = {
        "contract_version": spec.contract_version,
        "continuous_fields": list(spec.continuous_fields),
        "categorical_fields": list(spec.categorical_fields),
        "checkpoint_field": spec.checkpoint_field,
        "continuous_stats": {
            n: {"median": s.median, "mean": s.mean, "std": s.std, "known_n": s.known_n}
            for n, s in spec.continuous_stats.items()
        },
        "categorical_specs": {n: list(s.categories) for n, s in spec.categorical_specs.items()},
        "checkpoint_categories": list(spec.checkpoint_spec.categories),
        "feature_names": list(spec.feature_names),
        "dropped_zero_variance_columns": list(spec.dropped_zero_variance_columns),
        "fit_row_count": spec.fit_row_count,
    }
    restored = deserialize_preprocessing(payload)
    row = _row(Decimal("15"), "BEAR_TREND", "09:30")
    assert transform_row(row, restored) == transform_row(row, spec)
    assert restored.feature_names == spec.feature_names


def test_transform_is_deterministic():
    rows = [_row(Decimal("10"), "BULL_TREND", "09:20"), _row(Decimal("20"), "BEAR_TREND", "09:30"),
            _row(None, None, "09:20")]
    spec = _fit(rows)
    row = _row(Decimal("15"), "BEAR_TREND", "09:30")
    assert transform_row(row, spec) == transform_row(row, spec)
