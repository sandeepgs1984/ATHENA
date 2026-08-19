"""DX-1 isolation contract — the twelve acceptance tests mandated by ADR-010.

These prove isolation rather than describe it. Each test below maps 1:1 to a
numbered acceptance test in ADR-010's implementation gate, and the test names
carry the number so a failure points straight at the clause it breaks.

DX-1 contains no DarvaX trading logic, so nothing here exercises methodology —
these are architecture tests.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import (
    DARVAX_MOUNT_PATH,
    _build_session_calendar,
    darvax_activation_requested,
    mount_darvax_if_enabled,
)
from athena.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "athena"

#: Every test here builds an ATHENA app, so pin a config directory where
#: DarvaX is disabled rather than inheriting the working copy's real flag.
#: Tests that want DarvaX enabled mount their own instance explicitly.
pytestmark = pytest.mark.usefixtures("athena_config_darvax_disabled")

#: The one file in ATHENA core allowed to reference athena.darvax (ADR-010 §4).
APPROVED_SEAM = SRC_ROOT / "api" / "darvax_mount.py"


def test_mount_calendar_adapter_uses_real_config_contract() -> None:
    calendar, timezone_name, setup_error = _build_session_calendar(
        REPO_ROOT / "config"
    )

    assert calendar is not None
    assert timezone_name == "Asia/Kolkata"
    assert setup_error is None
    assert calendar.context_for(date(2026, 8, 19)).is_trading_session


def _write_darvax_config(config_dir: Path, **overrides: object) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"enabled": False}
    payload.update(overrides)
    path = config_dir / "darvax.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture()
def darvax_disabled_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the seam's default repo-root resolution at a throwaway tree where
    DarvaX is explicitly disabled.

    Without this, every test below that calls a bare ``create_app()`` would
    silently inherit whatever the working copy's real ``config/darvax.json``
    happens to say — so the suite would go red the moment the owner legitimately
    enables DarvaX. These tests assert the *disabled contract*, so they must
    pin the disabled state themselves rather than depend on ambient config.
    """
    _write_darvax_config(tmp_path / "config", enabled=False)
    monkeypatch.setattr("athena.api.darvax_mount._default_repo_root", lambda: tmp_path)
    return tmp_path


# --------------------------------------------------------------------------- #
# 1. Disabled -> no athena.darvax module imported
# --------------------------------------------------------------------------- #


def test_01_disabled_never_imports_darvax_module():
    """Asserted in a clean subprocess: building the app with DarvaX disabled
    must leave ``athena.darvax`` entirely absent from sys.modules. An in-process
    check would be defeated by other tests having already imported it, so this
    deliberately runs isolated — and pins its own disabled config so the result
    does not depend on the working copy's real one."""
    code = (
        "import sys, os, json, pathlib, tempfile, shutil;"
        "d = pathlib.Path(tempfile.mkdtemp());"
        f"shutil.copytree(pathlib.Path({str(REPO_ROOT)!r}) / 'config', d / 'config');"
        "(d / 'config' / 'darvax.json').write_text(json.dumps({'enabled': False}));"
        # create_app resolves its config dir from this variable and hands it to
        # the seam, so pinning it is what actually pins the flag.
        "os.environ['ATHENA_CONFIG_DIR'] = str(d / 'config');"
        "import athena.api.darvax_mount as dm;"
        "dm._default_repo_root = (lambda: d);"
        "from athena.api.app import create_app;"
        "from athena.api.config import APISettings;"
        "create_app(APISettings());"
        "leaked=[m for m in sys.modules if m.startswith('athena.darvax')];"
        "print('LEAKED' if leaked else 'CLEAN')"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "CLEAN" in result.stdout, f"athena.darvax was imported: {result.stdout}"


# --------------------------------------------------------------------------- #
# 2. Disabled -> no /darvax route
# --------------------------------------------------------------------------- #


def test_02_disabled_registers_no_darvax_route(darvax_disabled_env: Path):
    app = create_app(APISettings())
    mounted = [getattr(r, "path", "") for r in app.routes]
    assert not any(str(p).startswith(DARVAX_MOUNT_PATH) for p in mounted)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(f"{DARVAX_MOUNT_PATH}/status").status_code == 404


# --------------------------------------------------------------------------- #
# 3. Disabled -> darvax.db never created
# --------------------------------------------------------------------------- #


def test_03_disabled_never_creates_darvax_database(tmp_path: Path):
    config_dir = tmp_path / "config"
    _write_darvax_config(config_dir, enabled=False, database={"path": "db/darvax.db"})
    app = create_app(APISettings())

    mounted = mount_darvax_if_enabled(
        app, repo=object(), config_dir=config_dir, repo_root=tmp_path
    )

    assert mounted is False
    assert not (tmp_path / "db" / "darvax.db").exists()
    assert list(tmp_path.glob("**/darvax.db")) == []


# --------------------------------------------------------------------------- #
# 4. Import-graph isolation
# --------------------------------------------------------------------------- #


def test_04_no_athena_core_module_imports_darvax_except_the_seam():
    """Static import-graph scan — catches a coupling introduced anywhere in
    ATHENA core, including inside a function body, which a runtime check on one
    code path would miss."""
    offenders: list[str] = []
    for py in SRC_ROOT.rglob("*.py"):
        if SRC_ROOT / "darvax" in py.parents or py == APPROVED_SEAM:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(n == "athena.darvax" or n.startswith("athena.darvax.") for n in names):
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{node.lineno}")
    assert offenders == [], (
        "ATHENA core must not import athena.darvax outside the approved seam; "
        f"found: {offenders}"
    )


def test_04b_the_seam_imports_darvax_lazily_not_at_module_scope():
    """The seam's import must live inside the function, otherwise merely
    importing athena.api.app would pull DarvaX in and break test 1."""
    tree = ast.parse(APPROVED_SEAM.read_text(encoding="utf-8"))
    for node in tree.body:  # module-level statements only
        assert not isinstance(node, (ast.Import, ast.ImportFrom)) or not any(
            (getattr(node, "module", "") or "").startswith("athena.darvax")
            or a.name.startswith("athena.darvax")
            for a in getattr(node, "names", [])
        ), "seam imports athena.darvax at module scope"


# --------------------------------------------------------------------------- #
# 5. ATHENA schema / DDL / record-count invariance
# --------------------------------------------------------------------------- #


def test_05_athena_schema_surface_is_unchanged_by_darvax(tmp_path: Path):
    from athena.data.store.repository import SqliteRepository
    from athena.data.store.schema import SCHEMA_VERSION, ddl_statements

    # Asserted as "DarvaX left no trace", not as a version literal: ATHENA
    # legitimately bumps its own schema for its own reasons (SU-1 added
    # symbol_master at v13), and pinning the number made this test fail for
    # changes that have nothing to do with DarvaX.
    ddl = " ".join(ddl_statements()).lower()
    assert "darvax" not in ddl, "ATHENA DDL must not mention DarvaX"
    assert SCHEMA_VERSION >= 12, "ATHENA schema version must never go backwards"

    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    try:
        assert not any("darvax" in t.lower() for t in repo.record_counts())
    finally:
        repo.close()


# --------------------------------------------------------------------------- #
# 6. Enablement changes nothing about ATHENA except adding the mount
# --------------------------------------------------------------------------- #


def test_06_enabling_darvax_does_not_alter_athena_routes(
    darvax_disabled_env: Path, tmp_path: Path
):
    """The baseline is captured through ``darvax_disabled_env`` so it reflects a
    genuinely DarvaX-free app regardless of the working copy's real config."""
    from athena.data.store.repository import SqliteRepository

    baseline = {getattr(r, "path", "") for r in create_app(APISettings()).routes}
    assert not any(str(p).startswith(DARVAX_MOUNT_PATH) for p in baseline)

    config_dir = tmp_path / "darvax-on"
    _write_darvax_config(config_dir, enabled=True, database={"path": "db/darvax.db"})
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    try:
        assert (
            mount_darvax_if_enabled(
                app, repo=repo, config_dir=config_dir, repo_root=tmp_path
            )
            is True
        )
        after = {getattr(r, "path", "") for r in app.routes}
        assert after - baseline == {DARVAX_MOUNT_PATH}, (
            "enabling DarvaX changed ATHENA's own routes"
        )
        assert baseline - after == set()
    finally:
        repo.close()


# --------------------------------------------------------------------------- #
# 7. Market-data port structurally exposes no write capability
# --------------------------------------------------------------------------- #


def test_07_market_data_port_is_structurally_read_only():
    from athena.darvax.adapters import SqliteMarketDataAdapter
    from athena.darvax.ports import (
        DARVAX_MARKET_DATA_READ_METHODS,
        DarvaxMarketDataPort,
    )

    members = {
        name
        for name in vars(DarvaxMarketDataPort)
        if not name.startswith("_") and callable(getattr(DarvaxMarketDataPort, name))
    }
    assert members == set(DARVAX_MARKET_DATA_READ_METHODS), f"port surface changed: {members}"

    forbidden = (
        "add", "save", "write", "insert", "update", "delete", "upsert",
        "reset", "close", "initialize", "commit",
    )
    for surface in (DarvaxMarketDataPort, SqliteMarketDataAdapter):
        for name in dir(surface):
            if name.startswith("_"):
                continue
            assert not name.lower().startswith(forbidden), (
                f"{surface.__name__}.{name} looks like a write method"
            )


# --------------------------------------------------------------------------- #
# 8. Removing DarvaX leaves ATHENA green
# --------------------------------------------------------------------------- #


def test_08_athena_builds_with_darvax_package_absent(monkeypatch, tmp_path: Path):
    """Simulates DarvaX being deleted from disk: with the config also gone (the
    documented complete-removal pairing), the seam is a clean no-op.

    The DX-1 milestone additionally verified this for real by physically moving
    the package, config, and tests off disk and running the full ATHENA suite —
    see the DX-1 review summary."""
    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name.startswith("athena.darvax"):
            raise ImportError("simulated: DarvaX package deleted")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    assert (
        mount_darvax_if_enabled(
            FastAPI(), repo=None, config_dir=tmp_path / "no-config", repo_root=tmp_path
        )
        is False
    )


# --------------------------------------------------------------------------- #
# 9. Disabled + module absent -> normal startup
# --------------------------------------------------------------------------- #


def test_09_disabled_plus_module_absent_starts_normally(
    monkeypatch, darvax_disabled_env: Path
):
    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name.startswith("athena.darvax"):
            raise ImportError("simulated: DarvaX package deleted")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)

    app = create_app(APISettings())
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/health").status_code == 200
    assert not any(
        str(getattr(r, "path", "")).startswith(DARVAX_MOUNT_PATH) for r in app.routes
    )


# --------------------------------------------------------------------------- #
# 10. Enabled + module absent -> explicit startup failure
# --------------------------------------------------------------------------- #


def test_10_enabled_plus_module_absent_fails_loudly(monkeypatch, tmp_path: Path):
    """Must raise, must name the contradiction and both remedies, and must NOT
    silently degrade to a disabled state (ADR-010 §4)."""
    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name.startswith("athena.darvax"):
            raise ImportError("simulated: DarvaX package deleted")
        return real_import(name, *args, **kwargs)

    config_dir = tmp_path / "config"
    _write_darvax_config(config_dir, enabled=True)
    monkeypatch.setattr(builtins, "__import__", _blocked)

    app = FastAPI()
    with pytest.raises(ConfigError) as excinfo:
        mount_darvax_if_enabled(
            app, repo=object(), config_dir=config_dir, repo_root=tmp_path
        )

    message = str(excinfo.value)
    assert "enabled" in message.lower()
    assert "athena.darvax" in message
    assert "false" in message.lower(), "error must state the disable remedy"
    assert not any(
        str(getattr(r, "path", "")).startswith(DARVAX_MOUNT_PATH) for r in app.routes
    ), "failed mount must not leave a partial route behind"


# --------------------------------------------------------------------------- #
# 11. ATHENA's config layer stays DarvaX-methodology-blind
# --------------------------------------------------------------------------- #


def test_11_athena_config_layer_is_methodology_blind():
    """No DarvaX methodology concept may appear in athena.config, and ATHENA's
    reader must extract only the activation flag."""
    config_pkg = SRC_ROOT / "config"
    methodology_terms = (
        "darvax", "stop_policy", "ema_stop_ladder", "canonical_stop_pct",
        "tight_stop_pct", "darvas", "fibonacci",
    )
    for py in config_pkg.rglob("*.py"):
        text = py.read_text(encoding="utf-8").lower()
        for term in methodology_terms:
            assert term not in text, (
                f"{py.relative_to(REPO_ROOT)} references DarvaX methodology "
                f"term '{term}' — ATHENA config must stay methodology-blind"
            )

    # The ATHENA-side reader parses exactly one key out of DarvaX's file.
    seam_src = inspect.getsource(darvax_activation_requested)
    for term in ("stop_policy", "ema_stop_ladder", "methodology", "database"):
        assert term not in seam_src, f"seam reads more than the activation flag: {term}"


def test_11b_athena_reader_ignores_every_key_except_enabled(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    # Methodology section is deliberately invalid; ATHENA must not care.
    (config_dir / "darvax.json").write_text(
        json.dumps(
            {
                "enabled": False,
                "methodology": {
                    "stop_policy": "NOT_A_VALID_POLICY",
                    "canonical_stop_pct": -999,
                },
            }
        ),
        encoding="utf-8",
    )
    assert darvax_activation_requested(config_dir) is False


# --------------------------------------------------------------------------- #
# 12. DarvaX owns methodology validation; disabled -> never parsed
# --------------------------------------------------------------------------- #


def test_12_darvax_owns_methodology_validation(tmp_path: Path):
    from athena.darvax.config import load_darvax_config

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "methodology": {"stop_policy": "NOT_A_VALID_POLICY"}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_darvax_config(config_dir)
    assert "stop_policy" in str(excinfo.value)


def test_12b_disabled_darvax_never_parses_methodology_config(tmp_path: Path):
    """The same invalid file must be completely inert while disabled — proving
    ATHENA's startup can never be broken by DarvaX methodology config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps(
            {
                "enabled": False,
                "methodology": {
                    "stop_policy": "NOT_A_VALID_POLICY",
                    "unknown_future_key": 123,
                },
            }
        ),
        encoding="utf-8",
    )
    app = create_app(APISettings())
    assert (
        mount_darvax_if_enabled(
            app, repo=object(), config_dir=config_dir, repo_root=tmp_path
        )
        is False
    )


# --------------------------------------------------------------------------- #
# Shipped-default guard
# --------------------------------------------------------------------------- #


def test_darvax_is_opt_in_by_default():
    """DarvaX must be off unless something explicitly asks for it (ADR-010 §7).

    Deliberately asserted against the *contract* rather than the working copy's
    ``config/darvax.json``: that file is the owner's live switch, and a test that
    demands it stay ``false`` would fail the moment DarvaX is legitimately turned
    on — punishing the owner for using the feature instead of testing anything.
    The three guarantees below are what "opt-in" actually means, and none of them
    depends on ambient state.
    """
    from athena.darvax.config import DarvaxConfig

    # 1. The schema default is off.
    assert DarvaxConfig().enabled is False

    # 2. A config file that omits the flag is off, not on.
    assert DarvaxConfig.model_validate({}).enabled is False

    # 3. An absent config file means "not requested" — a normal supported state.
    assert darvax_activation_requested(REPO_ROOT / "does-not-exist") is False


def test_no_test_can_reach_the_owners_production_darvax_database(tmp_path):
    """Regression for 2026-08-16: DarvaX API tests wrote real sweeps into the
    owner's `db/darvax.db`.

    The mechanism was that `create_app()` reads `ATHENA_CONFIG_DIR` (defaulting
    to the working copy's real `config/`), so once the owner enabled DarvaX it
    mounted a *production* DarvaX alongside each test's own — and the real one
    won the route match. It stayed invisible while DarvaX was disabled and
    became destructive the day it was enabled.

    Asserted here rather than trusted to fixture discipline: the guard is now
    autouse in `tests/darvax/conftest.py`, and this fails if it is ever removed.
    """
    from athena.api.app import create_app
    from athena.api.config import APISettings
    from athena.api.darvax_mount import DARVAX_MOUNT_PATH

    app = create_app(APISettings())
    mounted = [
        r for r in app.routes if getattr(r, "path", "") == DARVAX_MOUNT_PATH
    ]
    for route in mounted:
        store = getattr(route.app.state, "darvax_store", None)
        if store is None:
            continue
        resolved = Path(store.path).resolve()
        assert resolved != REPO_ROOT / "db" / "darvax.db", (
            f"a test mounted DarvaX against the production database at {resolved}"
        )
