"""EM-7B / EM-7B.1: EMR operational configuration.

Missing file is safely inert (disabled), a present-but-invalid file
fails loudly, unknown keys are rejected, and the shipped default really
is disabled.

EM-7B.1 (Owner/Chief Architect correction, 2026-09-04): proves the
runtime-tolerance authority boundary. `max_checkpoint_price_delay_seconds`
is no longer a configurable field at all -- it must be rejected as an
unknown key, exactly like any other typo, since the frozen bound it used
to carry now comes from a Python constant no config edit can reach.
`base_universe`/`model_version` remain configurable selectors, but
`load_emr_operational_config` (the real config-*file* boundary) must
refuse one that does not resolve to an already-frozen, already-approved
source -- proven against a fixture frozen-model manifest, never the real
repo's own `config/emr/frozen_models/`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from athena.errors import ConfigError
from athena.explosive_move.live.operational_config import (
    ADR_014_APPROVED_BASE_UNIVERSE,
    EmrOperationalConfig,
    emr_operational_config_path,
    load_emr_operational_config,
)


def _seed_frozen_model_manifest(config_dir: Path, *, version: str = "v1", manifest_version: str | None = None) -> None:
    manifest_dir = config_dir / "emr" / "frozen_models" / version
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "FROZEN_MODEL_MANIFEST.json").write_text(
        json.dumps({"version": manifest_version if manifest_version is not None else version}), encoding="utf-8",
    )


def test_default_config_is_disabled():
    config = EmrOperationalConfig()
    assert config.enabled is False


def test_missing_file_loads_as_disabled_default(tmp_path):
    """No frozen-model manifest needs to exist for this path -- the
    inert-default case is deliberately not subject to the frozen-source
    check (see load_emr_operational_config's own docstring)."""
    config = load_emr_operational_config(tmp_path)
    assert config.enabled is False
    assert config.base_universe == "athena_core"


def test_explicit_enabled_true_loads(tmp_path):
    _seed_frozen_model_manifest(tmp_path)
    (tmp_path / "emr").mkdir(exist_ok=True)
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
    _seed_frozen_model_manifest(tmp_path)
    (tmp_path / "emr").mkdir(exist_ok=True)
    emr_operational_config_path(tmp_path).write_text(
        json.dumps({"_note": "documentation only", "enabled": True}), encoding="utf-8",
    )
    config = load_emr_operational_config(tmp_path)
    assert config.enabled is True


def test_real_repo_config_ships_disabled():
    """The actual config/emr/operational.json checked into the repo must
    ship disabled -- this is the file production would read if EMR were
    ever mounted, so its shipped default is a real safety property, not
    just this test suite's own fixture default. Loading the real repo
    config also exercises the frozen-source validation against the real
    config/emr/frozen_models/v1/ manifest -- a passing load here is
    itself proof the shipped file resolves correctly."""
    repo_root = Path(__file__).resolve().parents[2]
    config = load_emr_operational_config(repo_root / "config")
    assert config.enabled is False
    assert config.base_universe == ADR_014_APPROVED_BASE_UNIVERSE
    assert config.model_version == "v1"


class TestRuntimeToleranceAuthority:
    """EM-7B.1: max_checkpoint_price_delay_seconds is no longer a field at
    all -- the frozen bound it used to carry is now sourced directly from
    checkpoint_reference_price.MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS
    in worker.py, unreachable from any config edit."""

    def test_max_checkpoint_price_delay_seconds_is_not_a_valid_field(self):
        with pytest.raises(Exception, match="max_checkpoint_price_delay_seconds"):
            EmrOperationalConfig(max_checkpoint_price_delay_seconds=999.0)

    def test_operator_supplying_the_removed_field_fails_as_unknown_key(self, tmp_path):
        _seed_frozen_model_manifest(tmp_path)
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "max_checkpoint_price_delay_seconds": 999.0}), encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="invalid EMR operational config"):
            load_emr_operational_config(tmp_path)

    def test_max_staleness_minutes_remains_a_genuinely_operational_field(self, tmp_path):
        """Unlike the removed field, this one is legitimately
        configurable -- eligibility.py's own docstring calls it 'an
        operational tuning knob, not evidence.'"""
        _seed_frozen_model_manifest(tmp_path)
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "max_staleness_minutes": 45.0}), encoding="utf-8",
        )
        config = load_emr_operational_config(tmp_path)
        assert config.max_staleness_minutes == 45.0

    def test_max_staleness_minutes_default_matches_the_accepted_canary_default(self):
        """Proven against the real function's own signature, not a
        hardcoded duplicate -- if the canary's own accepted default ever
        changes, this test (not a silent divergence) is what notices."""
        import inspect

        from athena.explosive_move.live.canary_gate import run_em5_production_canary

        canary_default = inspect.signature(run_em5_production_canary).parameters["max_staleness_minutes"].default
        assert EmrOperationalConfig().max_staleness_minutes == canary_default


class TestBaseUniverseAuthority:
    def test_approved_base_universe_loads(self, tmp_path):
        _seed_frozen_model_manifest(tmp_path)
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "base_universe": ADR_014_APPROVED_BASE_UNIVERSE}), encoding="utf-8",
        )
        config = load_emr_operational_config(tmp_path)
        assert config.base_universe == ADR_014_APPROVED_BASE_UNIVERSE

    def test_unapproved_base_universe_is_rejected(self, tmp_path):
        _seed_frozen_model_manifest(tmp_path)
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "base_universe": "some-other-universe"}), encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="not the ADR-014 Section 11 frozen"):
            load_emr_operational_config(tmp_path)

    def test_direct_construction_is_unconstrained_for_test_fixture_isolation(self):
        """EmrOperationalConfig itself stays freely constructible -- the
        authority boundary lives at load_emr_operational_config (the real
        config-file boundary an operator can reach), not at the general-
        purpose dataclass's own constructor, which this repo's own test
        suite (test_em7b_worker.py) relies on for fixture isolation."""
        config = EmrOperationalConfig(base_universe="em5-test-universe")
        assert config.base_universe == "em5-test-universe"


class TestModelVersionAuthority:
    def test_promoted_model_version_loads(self, tmp_path):
        _seed_frozen_model_manifest(tmp_path, version="v1")
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "model_version": "v1"}), encoding="utf-8",
        )
        config = load_emr_operational_config(tmp_path)
        assert config.model_version == "v1"

    def test_never_promoted_model_version_is_rejected(self, tmp_path):
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "model_version": "v2-never-promoted"}), encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="no promoted frozen model manifest"):
            load_emr_operational_config(tmp_path)

    def test_manifest_version_mismatch_is_rejected(self, tmp_path):
        """A manifest directory named 'v1' whose own recorded version
        disagrees (a corrupted/tampered promotion) must not be trusted
        just because the directory name matches."""
        _seed_frozen_model_manifest(tmp_path, version="v1", manifest_version="v0-corrupted")
        (tmp_path / "emr").mkdir(exist_ok=True)
        emr_operational_config_path(tmp_path).write_text(
            json.dumps({"enabled": False, "model_version": "v1"}), encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="does not match its own promoted manifest"):
            load_emr_operational_config(tmp_path)

    def test_real_repo_v1_model_version_resolves_to_the_accepted_canary_artifact(self):
        """Confirms provenance: config_version 'v1' matches the same
        promoted frozen artifact set the accepted Section 14 canary uses
        (config/emr/frozen_models/v1/FROZEN_MODEL_MANIFEST.json's own
        recorded version)."""
        repo_root = Path(__file__).resolve().parents[2]
        manifest_path = repo_root / "config" / "emr" / "frozen_models" / "v1" / "FROZEN_MODEL_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["version"] == "v1"
