"""EM-5 frozen inference -- loads the REAL promoted TOUCH_10 artifact
from `config/emr/frozen_models/v1/` (not a synthetic fixture -- this is
exactly what production EM-5 reads) and proves integrity verification
actually rejects a byte-corrupted file rather than silently trusting it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from athena.explosive_move.live.frozen_inference import (
    FrozenModelIntegrityError,
    load_frozen_model,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _empty_observation() -> dict:
    return {"session_date": "2026-08-28", "checkpoint_ist": "12:00"}


def test_loads_the_real_promoted_touch_10_artifact():
    model = load_frozen_model(config_dir=CONFIG_DIR, version="v1", family="TOUCH", threshold_percent=10)
    assert model.family == "TOUCH"
    assert model.threshold_percent == 10
    assert len(model.coefficients) == len(model.feature_names)
    assert isinstance(model.intercept, float)
    assert "12:00" in model.platt_by_checkpoint


def test_scores_an_all_missing_observation_via_median_imputation():
    model = load_frozen_model(config_dir=CONFIG_DIR, version="v1", family="TOUCH", threshold_percent=10)
    scored = model.score(_empty_observation(), checkpoint="12:00")
    assert scored.family == "TOUCH"
    assert scored.threshold_percent == 10
    assert scored.checkpoint == "12:00"
    assert isinstance(scored.raw_logit, float)
    assert 0.0 <= scored.calibrated_probability <= 1.0
    assert scored.calibration_level in ("CHECKPOINT_SPECIFIC", "POOLED_FAMILY_THRESHOLD")


def test_missing_checkpoint_calibration_raises():
    model = load_frozen_model(config_dir=CONFIG_DIR, version="v1", family="TOUCH", threshold_percent=10)
    with pytest.raises(ValueError, match="no Platt calibration"):
        model.score(_empty_observation(), checkpoint="23:59")


def test_corrupted_em4b_artifact_bytes_are_rejected(tmp_path):
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em4b").mkdir(parents=True)
    (root / "em4d").mkdir(parents=True)

    real_root = CONFIG_DIR / "emr" / "frozen_models" / "v1"
    manifest = (real_root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8")
    (root / "FROZEN_MODEL_MANIFEST.json").write_text(manifest, encoding="utf-8")

    corrupted = (real_root / "em4b" / "TOUCH_10.json").read_text(encoding="utf-8") + " "
    (root / "em4b" / "TOUCH_10.json").write_text(corrupted, encoding="utf-8")
    (root / "em4d" / "TOUCH_10.json").write_text(
        (real_root / "em4d" / "TOUCH_10.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(FrozenModelIntegrityError, match="sha256 mismatch"):
        load_frozen_model(config_dir=tmp_path, version="v1", family="TOUCH", threshold_percent=10)


def test_filename_absent_from_manifest_is_rejected(tmp_path):
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em4b").mkdir(parents=True)
    (root / "em4d").mkdir(parents=True)
    (root / "FROZEN_MODEL_MANIFEST.json").write_text(
        '{"sources": {"em4b": {"sha256": {}}, "em4d": {"sha256": {}}}}', encoding="utf-8"
    )
    (root / "em4b" / "TOUCH_10.json").write_text("{}", encoding="utf-8")
    (root / "em4d" / "TOUCH_10.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FrozenModelIntegrityError, match="not recorded"):
        load_frozen_model(config_dir=tmp_path, version="v1", family="TOUCH", threshold_percent=10)


def test_genuinely_missing_artifact_file_fails_closed_with_the_typed_error(tmp_path):
    """A file the manifest lists but that never made it to disk (a partial
    promotion, a botched deploy) must fail exactly like a hash mismatch --
    a bare FileNotFoundError would still stop the load, but silently, with
    no consistent typed-failure story for callers to handle."""
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em4b").mkdir(parents=True)
    (root / "em4d").mkdir(parents=True)

    real_root = CONFIG_DIR / "emr" / "frozen_models" / "v1"
    manifest = (real_root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8")
    (root / "FROZEN_MODEL_MANIFEST.json").write_text(manifest, encoding="utf-8")
    # em4b/TOUCH_10.json is recorded in the manifest but deliberately never written.
    (root / "em4d" / "TOUCH_10.json").write_text(
        (real_root / "em4d" / "TOUCH_10.json").read_text(encoding="utf-8"), encoding="utf-8",
    )

    with pytest.raises(FrozenModelIntegrityError, match="could not be read"):
        load_frozen_model(config_dir=tmp_path, version="v1", family="TOUCH", threshold_percent=10)


def test_missing_manifest_file_fails_closed_with_the_typed_error(tmp_path):
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em4b").mkdir(parents=True)
    (root / "em4d").mkdir(parents=True)
    # No FROZEN_MODEL_MANIFEST.json written at all.

    with pytest.raises(FrozenModelIntegrityError, match="cannot read manifest"):
        load_frozen_model(config_dir=tmp_path, version="v1", family="TOUCH", threshold_percent=10)
