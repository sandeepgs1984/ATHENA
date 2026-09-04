"""EM-7B: EMR operational configuration -- missing file is safely inert
(disabled), a present-but-invalid file fails loudly, unknown keys are
rejected, and the shipped default really is disabled."""

from __future__ import annotations

import json

import pytest

from athena.errors import ConfigError
from athena.explosive_move.live.operational_config import (
    EmrOperationalConfig,
    emr_operational_config_path,
    load_emr_operational_config,
)


def test_default_config_is_disabled():
    config = EmrOperationalConfig()
    assert config.enabled is False


def test_missing_file_loads_as_disabled_default(tmp_path):
    config = load_emr_operational_config(tmp_path)
    assert config.enabled is False
    assert config.base_universe == "athena_core"


def test_explicit_enabled_true_loads(tmp_path):
    (tmp_path / "emr").mkdir()
    (emr_operational_config_path(tmp_path)).write_text(json.dumps({"enabled": True}), encoding="utf-8")
    config = load_emr_operational_config(tmp_path)
    assert config.enabled is True


def test_invalid_json_fails_loudly(tmp_path):
    (tmp_path / "emr").mkdir()
    emr_operational_config_path(tmp_path).write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid JSON"):
        load_emr_operational_config(tmp_path)


def test_unknown_key_fails_loudly_rather_than_silently_ignored(tmp_path):
    (tmp_path / "emr").mkdir()
    emr_operational_config_path(tmp_path).write_text(
        json.dumps({"enabled": False, "not_a_real_field": 123}), encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="invalid EMR operational config"):
        load_emr_operational_config(tmp_path)


def test_malformed_enabled_type_fails_loudly_not_silently_enabled(tmp_path):
    (tmp_path / "emr").mkdir()
    emr_operational_config_path(tmp_path).write_text(
        json.dumps({"enabled": "yes-please"}), encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="invalid EMR operational config"):
        load_emr_operational_config(tmp_path)


def test_meta_keys_are_dropped_before_validation(tmp_path):
    (tmp_path / "emr").mkdir()
    emr_operational_config_path(tmp_path).write_text(
        json.dumps({"_note": "documentation only", "enabled": True}), encoding="utf-8",
    )
    config = load_emr_operational_config(tmp_path)
    assert config.enabled is True


def test_real_repo_config_ships_disabled():
    """The actual config/emr/operational.json checked into the repo must
    ship disabled -- this is the file production would read if EMR were
    ever mounted, so its shipped default is a real safety property, not
    just this test suite's own fixture default."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    config = load_emr_operational_config(repo_root / "config")
    assert config.enabled is False
