"""EM-5's deterministic-score companion -- loads the REAL promoted EM-3
register/manifest and proves integrity verification rejects corruption,
same discipline as the frozen logistic loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from athena.explosive_move.live.deterministic_scoring import (
    DeterministicRulesIntegrityError,
    load_deterministic_rules,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def test_loads_the_real_promoted_em3_register():
    rules = load_deterministic_rules(config_dir=CONFIG_DIR, version="v1")
    assert rules.rules_by_key
    assert rules.bin_edges


def test_scores_an_all_unknown_observation_as_unknown():
    rules = load_deterministic_rules(config_dir=CONFIG_DIR, version="v1")
    result = rules.score(family="TOUCH", threshold_percent=10, checkpoint="12:00", evidence={})
    assert result.score is None
    assert result.vote_count == 0


def test_unknown_family_threshold_checkpoint_combo_has_no_rules_but_does_not_error():
    rules = load_deterministic_rules(config_dir=CONFIG_DIR, version="v1")
    result = rules.score(
        family="TOUCH", threshold_percent=10, checkpoint="23:59", evidence={"adx14": "20"}
    )
    assert result.score is None


def test_corrupted_register_bytes_are_rejected(tmp_path):
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em3").mkdir(parents=True)
    real_root = CONFIG_DIR / "emr" / "frozen_models" / "v1"
    (root / "FROZEN_MODEL_MANIFEST.json").write_text(
        (real_root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    corrupted = (real_root / "em3" / "F_exploratory_candidate_register.json").read_text(encoding="utf-8") + " "
    (root / "em3" / "F_exploratory_candidate_register.json").write_text(corrupted, encoding="utf-8")
    (root / "em3" / "manifest.json").write_text(
        (real_root / "em3" / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(DeterministicRulesIntegrityError, match="sha256 mismatch"):
        load_deterministic_rules(config_dir=tmp_path, version="v1")


def test_genuinely_missing_register_file_fails_closed_with_the_typed_error(tmp_path):
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em3").mkdir(parents=True)
    real_root = CONFIG_DIR / "emr" / "frozen_models" / "v1"
    (root / "FROZEN_MODEL_MANIFEST.json").write_text(
        (real_root / "FROZEN_MODEL_MANIFEST.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    # F_exploratory_candidate_register.json is recorded in the manifest but
    # deliberately never written; manifest.json (em3's own) is present.
    (root / "em3" / "manifest.json").write_text(
        (real_root / "em3" / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(DeterministicRulesIntegrityError, match="could not be read"):
        load_deterministic_rules(config_dir=tmp_path, version="v1")


def test_missing_manifest_file_fails_closed_with_the_typed_error(tmp_path):
    root = tmp_path / "emr" / "frozen_models" / "v1"
    (root / "em3").mkdir(parents=True)
    # No FROZEN_MODEL_MANIFEST.json written at all.

    with pytest.raises(DeterministicRulesIntegrityError, match="cannot read manifest"):
        load_deterministic_rules(config_dir=tmp_path, version="v1")
