"""Shared fixtures: an isolated, fully-valid config tree for tests.

Tests NEVER depend on production config values — they build their own,
so a production tuning change can never break a test by accident.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROD_CONFIG = REPO_ROOT / "config"


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """A temp copy of production config with deterministic calendar fixtures."""

    target = tmp_path / "config"
    shutil.copytree(PROD_CONFIG, target)

    # Deterministic expiry fixtures (production file is empty by design).
    (target / "calendar" / "expiries.json").write_text(json.dumps({
        "weekly": ["2026-07-23"],
        "monthly": ["2026-07-30"],
    }), encoding="utf-8")

    return target


def rewrite_json(path: Path, mutate) -> None:
    """Load → mutate → save a JSON file (helper for invalid-config tests)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")
