"""EM-5 artifact promotion: byte-identical copy + hash verification,
never mutates source files, never overwrites an existing version."""

from __future__ import annotations

import json

import pytest

from athena.data.em5_artifact_promotion import promote


def _write_source(root, subdir, name, content: str):
    d = root / subdir
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(content, encoding="utf-8")


@pytest.fixture
def research_root(tmp_path):
    root = tmp_path / "research"
    _write_source(root, "em4b", "TOUCH_10.json", '{"coefficients": [1.0, 2.0]}')
    _write_source(root, "em4d", "TOUCH_10.json", '{"platt_a": 1.1}')
    _write_source(root, "em3", "manifest.json", '{"bin_edges": {}}')
    _write_source(root, "em3", "F_exploratory_candidate_register.json", "[]")
    return root


def test_promote_copies_files_byte_identically(tmp_path, research_root):
    config_dir = tmp_path / "config"
    manifest = promote(research_root=research_root, config_dir=config_dir, version="v1")

    promoted = config_dir / "emr" / "frozen_models" / "v1" / "em4b" / "TOUCH_10.json"
    source = research_root / "em4b" / "TOUCH_10.json"
    assert promoted.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert manifest["sources"]["em4b"]["file_count"] == 1
    assert manifest["sources"]["em4d"]["file_count"] == 1
    assert manifest["sources"]["em3"]["file_count"] == 2  # register + manifest only, not the diagnostic reports


def test_promote_excludes_em3_diagnostic_only_reports(tmp_path, research_root):
    # a purely descriptive EM-3 report never read by live inference --
    # must not be promoted, even though it sits in the same source directory.
    _write_source(research_root, "em3", "D_regime_stability_report.json", '{"huge": "report"}')
    config_dir = tmp_path / "config"
    manifest = promote(research_root=research_root, config_dir=config_dir, version="v1")
    assert "D_regime_stability_report.json" not in manifest["sources"]["em3"]["sha256"]
    promoted_dir = config_dir / "emr" / "frozen_models" / "v1" / "em3"
    assert not (promoted_dir / "D_regime_stability_report.json").exists()


def test_promote_never_modifies_source_files(tmp_path, research_root):
    config_dir = tmp_path / "config"
    original = (research_root / "em4b" / "TOUCH_10.json").read_bytes()
    promote(research_root=research_root, config_dir=config_dir, version="v1")
    assert (research_root / "em4b" / "TOUCH_10.json").read_bytes() == original


def test_promote_records_source_sha256(tmp_path, research_root):
    config_dir = tmp_path / "config"
    manifest = promote(research_root=research_root, config_dir=config_dir, version="v1")
    import hashlib

    expected = hashlib.sha256((research_root / "em4b" / "TOUCH_10.json").read_bytes()).hexdigest()
    assert manifest["sources"]["em4b"]["sha256"]["TOUCH_10.json"] == expected


def test_promote_refuses_to_overwrite_an_existing_version(tmp_path, research_root):
    config_dir = tmp_path / "config"
    promote(research_root=research_root, config_dir=config_dir, version="v1")
    with pytest.raises(RuntimeError, match="already exists"):
        promote(research_root=research_root, config_dir=config_dir, version="v1")


def test_promote_manifest_id_is_deterministic(tmp_path, research_root):
    config_dir_a = tmp_path / "config_a"
    config_dir_b = tmp_path / "config_b"
    manifest_a = promote(research_root=research_root, config_dir=config_dir_a, version="v1")
    manifest_b = promote(research_root=research_root, config_dir=config_dir_b, version="v1")
    assert manifest_a["manifest_id"] == manifest_b["manifest_id"]


def test_promote_writes_readable_manifest_file(tmp_path, research_root):
    config_dir = tmp_path / "config"
    promote(research_root=research_root, config_dir=config_dir, version="v1")
    manifest_path = config_dir / "emr" / "frozen_models" / "v1" / "FROZEN_MODEL_MANIFEST.json"
    assert manifest_path.is_file()
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded["version"] == "v1"
