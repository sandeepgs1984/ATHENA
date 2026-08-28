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


@pytest.fixture(autouse=True)
def reset_endpoints_never_back_up_the_real_database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The suite must never create a safety backup of the owner's real
    ``db/athena.db``.

    ``DecisionsService``/``PortfolioService`` reset endpoints back up the
    database at ``ops_service.default_db_path()``/``default_backup_dir()``
    before wiping it -- resolved from ``ATHENA_DB_PATH``/``ATHENA_BACKUP_DIR``
    if set, else the real repo-root ``db/athena.db``/``db/backups``. The
    reset *tests* correctly swap in an in-memory provider so no real record
    is ever deleted, but the pre-reset backup step is unconditional and
    reads real config regardless of that override -- so exercising these
    endpoints in the suite made a real ~4.3GB copy of the production
    database on every run (2026-08-28: ran the shared disk out of space).
    Same class of bug as ``darvax_never_activates_in_tests`` above, and the
    same fix: redirect the real path to a throwaway one for every test.
    """
    monkeypatch.setenv("ATHENA_DB_PATH", str(tmp_path / "unused-athena.db"))
    monkeypatch.setenv("ATHENA_BACKUP_DIR", str(tmp_path / "unused-backups"))


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """A temp copy of production config with deterministic calendar fixtures.

    Excludes ``config/emr/frozen_models`` (the promoted EM-5 model
    artifacts, ~35MB) -- no test using this fixture reads it; EM-5's own
    tests all reference the real ``REPO_ROOT / "config"`` directly instead
    (see ``tests/explosive_move/test_em5_*.py``). Copying it into every one
    of this fixture's ~90 call sites turned a previously trivial per-test
    copy into 35MB+ each -- tens of GB across one full suite run,
    accumulating in pytest's own retained temp dirs (2026-08-28: ran the
    shared disk out of space twice in one session).
    """

    target = tmp_path / "config"
    shutil.copytree(PROD_CONFIG, target, ignore=shutil.ignore_patterns("frozen_models"))

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
