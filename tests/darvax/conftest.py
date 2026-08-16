"""Shared fixtures for the DarvaX suite.

**Why this exists.** `create_app` resolves its config directory from
`ATHENA_CONFIG_DIR` (defaulting to `config`) and hands it to the DarvaX mount
seam, so a bare `create_app()` inside a test reads the *working copy's real*
`config/darvax.json`. That makes any such test depend on ambient state: the
moment the owner legitimately sets `enabled: true`, tests asserting the disabled
contract go red, and tests that mount their own temp DarvaX get **two** apps at
`/darvax` — with the real one winning the route match and serving the real
`darvax.db`.

Enabling a feature must never break the suite. Tests that build an app therefore
pin a throwaway config directory where DarvaX is explicitly disabled, and mount
their own instance on top when they want it enabled.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def darvax_never_activates_in_tests() -> None:
    """Opt back in to the real mount seam for the DarvaX suite.

    Overrides the suite-wide guard in ``tests/conftest.py``, which neutralises
    `create_app`'s DarvaX seam so unrelated tests cannot touch the owner's live
    `db/darvax.db`. These tests are *about* that seam, so they need it intact —
    and they stay off the production database via ``darvax_config_is_hermetic``
    below, which is autouse for exactly that reason.
    """
    return None


@pytest.fixture(autouse=True)
def darvax_config_is_hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point `create_app` at a throwaway config with DarvaX **disabled**.

    This module's docstring described the hazard from the start: a test that
    calls ``create_app()`` and then mounts its own DarvaX gets *two* apps at
    ``/darvax``, and the real one wins the route match — so requests land on the
    owner's live ``db/darvax.db``. Every fixture was expected to remember the
    guard individually.

    On 2026-08-16 that expectation failed and the hazard became real: the owner
    enabled DarvaX and opted it into a 2,191-instrument universe, and API tests
    that POST ``/screen`` ran **full sweeps against the production database**,
    writing sweeps, screen results and thousands of signals into it.

    It is autouse now because "remember to pin the config" is not a safeguard —
    it is a convention, and this is what conventions cost. A test that genuinely
    wants DarvaX still mounts its own instance explicitly, which is unaffected;
    what changes is that forgetting no longer reaches production.
    """
    root = tmp_path / "_autohermetic"
    root.mkdir(parents=True, exist_ok=True)
    config_dir = athena_config_copy(root / "config", darvax_enabled=False)
    monkeypatch.setenv("ATHENA_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr("athena.api.darvax_mount._default_repo_root", lambda: root)
    return config_dir


def athena_config_copy(dest: Path, *, darvax_enabled: bool) -> Path:
    """Copy ATHENA's real config directory to ``dest``, overriding only DarvaX.

    The rest of the config is copied rather than synthesised because `create_app`
    legitimately needs it (validation config, Kite session paths, and so on) —
    only the DarvaX flag is under test here.
    """
    shutil.copytree(REPO_ROOT / "config", dest)
    (dest / "darvax.json").write_text(
        json.dumps({"enabled": darvax_enabled}), encoding="utf-8"
    )
    return dest


@pytest.fixture()
def athena_config_darvax_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """Make `create_app` see DarvaX as disabled, whatever the working copy says.

    Deliberately rooted at ``_hermetic/`` rather than ``tmp_path/config`` so it
    never collides with the ``tmp_path/config`` directories individual tests
    build for their own *enabled* DarvaX instances.

    Both resolution paths are pinned: `ATHENA_CONFIG_DIR` for the production path
    through `create_app`, and `_default_repo_root` for any direct seam call that
    omits ``config_dir``.
    """
    root = tmp_path / "_hermetic"
    root.mkdir()
    config_dir = athena_config_copy(root / "config", darvax_enabled=False)
    monkeypatch.setenv("ATHENA_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(
        "athena.api.darvax_mount._default_repo_root", lambda: root
    )
    return config_dir
