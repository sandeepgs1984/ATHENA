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


@pytest.fixture(autouse=True)
def darvax_never_activates_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """The suite must never touch the owner's live DarvaX database.

    ``create_app()`` reads the working copy's real ``config/darvax.json``. Once
    the owner legitimately sets ``enabled: true``, every test that builds an app
    — and most API tests do — mounts the real satellite, which resolves its
    relative ``db/darvax.db`` against the real repo root and calls
    ``initialize()`` on the owner's production ledger.

    That is not hypothetical: enabling DarvaX made ~1300 unrelated tests open
    and migrate ``db/darvax.db``. It stayed invisible because schema
    initialisation is idempotent, and only surfaced when a schema version
    changed. The next step down that path is a test that triggers a scan and
    writes real signals into the owner's data.

    Patches the name as imported into ``athena.api.app``, not the seam module,
    so a direct ``mount_darvax_if_enabled(...)`` call — how the DarvaX tests
    mount their own instance — keeps working normally. Tests under
    ``tests/darvax/`` override this fixture to restore the real seam, and stay
    off production by pinning their own config directory and database.
    """
    monkeypatch.setattr(
        "athena.api.app.mount_darvax_if_enabled",
        lambda app, **kwargs: False,
        raising=True,
    )
