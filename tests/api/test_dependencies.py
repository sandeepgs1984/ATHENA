"""Unit tests for athena.api.dependencies config-dir resolution."""

from __future__ import annotations

from pathlib import Path

from athena.api import dependencies


def test_resolve_config_dir_honors_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ATHENA_CONFIG_DIR", str(tmp_path))

    assert dependencies._resolve_config_dir() == tmp_path


def test_resolve_config_dir_falls_back_to_repo_root(monkeypatch):
    monkeypatch.delenv("ATHENA_CONFIG_DIR", raising=False)

    assert dependencies._resolve_config_dir() == dependencies._find_repo_root() / "config"
