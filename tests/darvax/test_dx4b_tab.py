"""DX-4b: DarvaX injected as an ATHENA dashboard tab (ADR-010 Amendment 1).

The eight acceptance tests the amendment requires. The behavioural ones actually
**execute** ``tab.js`` in Node against a DOM stub (``_tab_harness.js``) rather
than grepping its source, because a grep would only prove the file mentions
injection, not that it injects correctly or degrades safely.

The whole point of Amendment 1's design is that ATHENA carries exactly one
DarvaX reference — a script tag for an asset only DarvaX serves — so disabling or
deleting DarvaX makes the tab vanish with no trace left behind.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from athena.api.app import DASHBOARD_JS_PARTS, assemble_dashboard_js, create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled

REPO_ROOT = Path(__file__).resolve().parents[2]
ATHENA_STATIC = REPO_ROOT / "src" / "athena" / "api" / "static"
ATHENA_INDEX = ATHENA_STATIC / "index.html"
DARVAX_STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"

TAB_JS = DARVAX_STATIC / "tab.js"
HARNESS = Path(__file__).parent / "_tab_harness.js"

#: Every test here builds an ATHENA app, so pin a config directory where
#: DarvaX is disabled rather than inheriting the working copy's real flag.
#: Tests that want DarvaX enabled mount their own instance explicitly.
pytestmark = pytest.mark.usefixtures("athena_config_darvax_disabled")

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(
    NODE is None, reason="node is required to execute tab.js behaviourally"
)


def _run_tab_js(mode: str) -> dict:
    """Execute tab.js against the DOM stub and return what it did."""
    result = subprocess.run(
        [NODE, str(HARNESS), str(TAB_JS), mode],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --------------------------------------------------------------------------- #
# 1. index.html carries exactly one DarvaX reference, and it is the script tag
# --------------------------------------------------------------------------- #


def test_01_index_html_contains_only_the_script_tag_reference():
    html = ATHENA_INDEX.read_text(encoding="utf-8")
    lines_with_darvax = [
        line for line in html.splitlines() if "darvax" in line.lower()
    ]
    # Comment lines explaining the tag are documentation, not markup; the only
    # non-comment reference must be the script tag itself.
    code_lines = [
        line
        for line in lines_with_darvax
        if "<script" in line or ("<" in line and "<!--" not in line and "--" not in line)
    ]
    assert len(code_lines) == 1, f"expected one DarvaX code line, got {code_lines}"
    only = code_lines[0]
    assert "<script" in only and 'src="/darvax/static/tab.js"' in only
    assert "defer" in only

    # No DarvaX markup, nav entry, panel, or style may live in ATHENA's HTML.
    for forbidden in (
        'data-tab="darvax"',
        'id="tab-darvax"',
        "darvax-flag",
        "darvax-embed",
    ):
        assert forbidden not in html, f"ATHENA's index.html contains {forbidden!r}"


# --------------------------------------------------------------------------- #
# 2. DASHBOARD_JS_PARTS untouched; assembly survives a missing DarvaX
# --------------------------------------------------------------------------- #


def test_02_dashboard_js_parts_has_no_darvax_entry_and_assembly_still_works():
    """The reason Amendment 1 rejected a native tab: assemble_dashboard_js()
    raises on a missing part, so a DarvaX entry here would mean deleting DarvaX
    breaks the whole dashboard."""
    assert not any("darvax" in part.lower() for part in DASHBOARD_JS_PARTS)

    # Assembly reads only ATHENA's own parts, so it cannot depend on DarvaX.
    assembled = assemble_dashboard_js(str(ATHENA_STATIC))
    assert assembled, "dashboard.js assembled empty"
    assert "darvax" not in assembled.lower(), (
        "assembled dashboard.js contains DarvaX code"
    )


# --------------------------------------------------------------------------- #
# 3. Disabled -> tab.js 404s and the dashboard keeps its original tabs
# --------------------------------------------------------------------------- #


def test_03_disabled_darvax_serves_no_tab_asset(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": False}), encoding="utf-8"
    )
    app = create_app(APISettings())
    assert mount_darvax_if_enabled(
        app, repo=object(), config_dir=config_dir, repo_root=tmp_path
    ) is False

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(f"{DARVAX_MOUNT_PATH}/static/tab.js").status_code == 404
        # The dashboard itself still serves, and its own tabs are all present.
        page = client.get("/dashboard/")
        assert page.status_code == 200
        for tab in ("overview", "market", "strategies", "decisions", "operations"):
            assert f'data-tab="{tab}"' in page.text


# --------------------------------------------------------------------------- #
# 4. DarvaX deleted -> dashboard still loads
# --------------------------------------------------------------------------- #


def test_04_dashboard_loads_with_darvax_module_absent(monkeypatch, tmp_path: Path):
    """The script tag 404s and the browser moves on; nothing server-side depends
    on DarvaX existing. (The DX-1 milestone additionally verified this by
    physically removing the package and running the full suite.)"""
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name.startswith("athena.darvax"):
            raise ImportError("simulated: DarvaX package deleted")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    app = create_app(APISettings())
    with TestClient(app, raise_server_exceptions=False) as client:
        page = client.get("/dashboard/")
        assert page.status_code == 200
        # The tag is still in the HTML but resolves to nothing.
        assert 'src="/darvax/static/tab.js"' in page.text
        assert client.get(f"{DARVAX_MOUNT_PATH}/static/tab.js").status_code == 404
        assert client.get("/dashboard/dashboard.js").status_code == 200


def test_04b_create_app_reads_the_darvax_flag_from_athena_config_dir(
    monkeypatch, tmp_path: Path
):
    """``create_app`` must hand the seam the *same* config directory every other
    consumer uses, i.e. the one ``ATHENA_CONFIG_DIR`` selects.

    Regression test for a real defect: the seam call originally passed neither
    ``config_dir`` nor ``repo_root``, so ``mount_darvax_if_enabled`` fell back to
    its repo-root default and read ``<repo>/config/darvax.json`` no matter what
    ``ATHENA_CONFIG_DIR`` pointed at. Every other test in this file calls the
    seam directly with an explicit ``config_dir``, which is exactly why none of
    them caught it — this one goes through ``create_app``.
    """
    config_dir = tmp_path / "config"
    shutil.copytree(REPO_ROOT / "config", config_dir)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True}), encoding="utf-8"
    )
    monkeypatch.setenv("ATHENA_CONFIG_DIR", str(config_dir))

    captured: dict = {}

    def _spy(app, **kwargs):
        captured.update(kwargs)
        return False  # do not actually mount; the wiring is what is under test

    monkeypatch.setattr("athena.api.app.mount_darvax_if_enabled", _spy)
    create_app(APISettings())

    assert captured.get("config_dir") == config_dir, (
        "create_app must pass the ATHENA_CONFIG_DIR-selected config dir to the "
        "DarvaX seam, not let it fall back to the repo root"
    )
    assert captured.get("repo_root") == config_dir.parent
    # Sanity: that directory really is the one holding the enabled flag.
    from athena.api.darvax_mount import darvax_activation_requested

    assert darvax_activation_requested(config_dir) is True


# --------------------------------------------------------------------------- #
# 5. Enabled -> tab.js is served and injects exactly one nav item and one panel
# --------------------------------------------------------------------------- #


def test_05_enabled_darvax_serves_the_tab_asset(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "database": {"path": "db/darvax.db"}}),
        encoding="utf-8",
    )
    from athena.data.store.repository import SqliteRepository

    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    try:
        assert mount_darvax_if_enabled(
            app, repo=repo, config_dir=config_dir, repo_root=tmp_path
        ) is True
        with TestClient(app, raise_server_exceptions=False) as client:
            served = client.get(f"{DARVAX_MOUNT_PATH}/static/tab.js")
            assert served.status_code == 200
            assert "sidebar-nav" in served.text
    finally:
        repo.close()


@needs_node
def test_05b_tab_js_injects_exactly_one_nav_item_and_one_panel():
    """Executed, not grepped: the real DOM effects are asserted."""
    result = _run_tab_js("full")

    assert result["threw"] is None
    assert result["warnings"] == []
    assert result["navAppended"] == 1, "must inject exactly one nav item"
    assert result["panesAppended"] == 1, "must inject exactly one panel"
    assert result["navDataTab"] == "darvax"
    assert result["navIsNavItem"] is True, "must reuse ATHENA's .nav-item styling"
    assert "DarvaX" in result["navLabel"]
    assert "Exp" in result["navLabel"], "the tab itself must flag the lane"
    assert result["panelId"] == "tab-darvax"
    assert result["panelIsTabPane"] is True
    assert result["styleAppended"] == 1, "DarvaX injects its own styles, not ATHENA's"


@needs_node
def test_05c_embedded_frame_is_lazy_and_points_at_the_darvax_page():
    """The iframe must not load until the tab is opened — DarvaX must add no
    page-load cost, and read no ATHENA data, for someone who never opens it."""
    idle = _run_tab_js("full")
    assert idle["frameTag"] == "IFRAME"
    # `startswith`, not equality: DX-7c appended a `&v=` cache-busting version
    # to the frame URL because a dynamically-set iframe src does not inherit the
    # parent's reload cache-bypass, which left the tab showing the previous UI
    # after a restart. Pinning the exact string made this test fail for the fix.
    assert idle["frameDataSrc"].startswith("/darvax/?embedded=1")
    assert idle["frameSrc"] is None, "frame must stay unloaded until activated"
    assert idle["panelActive"] is False

    opened = _run_tab_js("deeplink")
    assert opened["panelActive"] is True
    assert opened["frameSrc"].startswith("/darvax/?embedded=1")
    assert opened["pageTitle"] == "DarvaX"


# --------------------------------------------------------------------------- #
# 6. Missing ATHENA hooks -> warn once, inject nothing, never throw
# --------------------------------------------------------------------------- #


@needs_node
def test_06_tab_js_degrades_silently_when_athena_hooks_are_missing():
    """A future dashboard refactor must not turn into a broken dashboard. This
    is the mitigation Amendment 1 promises for the runtime-coupling risk."""
    result = _run_tab_js("degraded")

    assert result["threw"] is None, "tab.js must never throw into ATHENA's page"
    assert result["navAppended"] == 0
    assert result["panesAppended"] == 0
    assert result["styleAppended"] == 0
    assert len(result["warnings"]) == 1, "exactly one warning, not a console flood"
    warning = result["warnings"][0]
    assert "[darvax]" in warning
    assert "/darvax/" in warning, "must point the owner at the standalone surface"


# --------------------------------------------------------------------------- #
# 7. Release gate: the DOM hooks tab.js depends on still exist in ATHENA
# --------------------------------------------------------------------------- #


def test_07_release_gate_athena_still_provides_the_hooks_tab_js_relies_on():
    """Amendment 1's key mitigation for invisible runtime coupling: if a
    dashboard refactor removes one of these hooks, this test fails loudly
    instead of the DarvaX tab silently disappearing for the owner."""
    html = ATHENA_INDEX.read_text(encoding="utf-8")
    js = assemble_dashboard_js(str(ATHENA_STATIC))

    assert 'class="sidebar-nav"' in html, "tab.js queries nav.sidebar-nav"
    assert 'class="tab-pane' in html, "tab.js locates the panel host via .tab-pane"
    assert 'id="page-title"' in html, "tab.js sets the header title"
    assert 'class="nav-item' in html, "tab.js reuses .nav-item styling"
    assert 'data-tab=' in html, "tab.js identifies tabs by data-tab"
    # ATHENA still drives its own tabs the way tab.js assumes.
    assert "function switchTab" in js
    assert "tab-${tabId}" in js, "panel ids are still tab-<tabId>"


# --------------------------------------------------------------------------- #
# 8. ATHENA's dashboard.js / dashboard.css stay free of DarvaX
# --------------------------------------------------------------------------- #


def test_08_athena_dashboard_assets_contain_no_darvax_reference():
    assembled = assemble_dashboard_js(str(ATHENA_STATIC)).lower()
    assert "darvax" not in assembled

    for asset in (ATHENA_STATIC / "css").rglob("*.css"):
        assert "darvax" not in asset.read_text(encoding="utf-8").lower(), (
            f"{asset.name} references DarvaX"
        )
    for asset in (ATHENA_STATIC / "js").rglob("*.js"):
        assert "darvax" not in asset.read_text(encoding="utf-8").lower(), (
            f"{asset.name} references DarvaX"
        )


# --------------------------------------------------------------------------- #
# Embedded mode
# --------------------------------------------------------------------------- #


def test_embedded_mode_hides_the_back_link_but_never_the_banner():
    """Inside the tab the "← ATHENA" link is redundant chrome. The experimental
    banner is a correctness requirement and must never be conditionally hidden."""
    js = (DARVAX_STATIC / "darvax.js").read_text(encoding="utf-8")
    assert "embedded=1" in js
    assert "a.link[href='/dashboard/']" in js, "only the back-link is removed"
    for banner_hint in (".banner", "banner"):
        assert f"remove('{banner_hint}')" not in js
    assert 'querySelector(".banner")' not in js

    html = (DARVAX_STATIC / "index.html").read_text(encoding="utf-8")
    assert 'class="banner"' in html
    assert "EXPERIMENTAL" in html


@pytest.mark.skipif(NODE is None, reason="node required")
def test_tab_js_is_syntactically_valid():
    assert subprocess.run(
        [NODE, "--check", str(TAB_JS)], capture_output=True, check=False
    ).returncode == 0


def _strip_js_comments(source: str) -> str:
    """Drop block and line comments so the check below inspects *code* only.

    Needed because tab.js's own comments legitimately discuss the ATHENA
    internals it deliberately avoids calling — matching those would fail the
    test for exactly the documentation that explains the correct behaviour.
    """
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif source.startswith("//", i):
            end = source.find("\n", i)
            i = n if end == -1 else end
        else:
            out.append(source[i])
            i += 1
    return "".join(out)


def test_tab_js_never_reaches_into_athena_internals_beyond_the_documented_hooks():
    """tab.js may read ATHENA's DOM; it must not call ATHENA's JS functions or
    touch its state, which would be a far deeper coupling than Amendment 1
    accepted."""
    code = _strip_js_comments(TAB_JS.read_text(encoding="utf-8"))
    for forbidden in ("switchTab(", "state.", "apiRequest(", "loadTabData("):
        assert forbidden not in code, (
            f"tab.js calls ATHENA internals ({forbidden}); it must self-manage"
        )
    # Sanity-check the stripper itself: tab.js discusses switchTab in prose, so a
    # working stripper must remove that mention while keeping real code.
    raw = TAB_JS.read_text(encoding="utf-8")
    assert "switchTab()" in raw, "expected the explanatory comment to exist"
    assert "querySelector" in code, "stripper removed real code"
