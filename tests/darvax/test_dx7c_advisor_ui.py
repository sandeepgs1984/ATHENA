"""DX-7c: the advisor dashboard.

Structural, like DX-6c's: these pin the contract between the API and the page
and fail if someone removes the unvalidated badge, introduces a quality score,
re-derives advice in the browser, or renames a field the page reads.

The behavioural check — driving the real page against a real sweep — is recorded
in the DX-7c review summary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = (STATIC / "darvax.js").read_text(encoding="utf-8")
CSS = (STATIC / "darvax.css").read_text(encoding="utf-8")
CODE = _strip_js_comments(JS)

#: Page text with runs of whitespace collapsed. HTML wraps for readability, so
#: asserting on a phrase that happens to straddle a line break fails for
#: formatting rather than for meaning.
FLAT_HTML = " ".join(HTML.split())


def body(name: str) -> str:
    """Source of one top-level function in ``darvax.js``.

    Delimited by the next **top-level** declaration (newline + two spaces +
    ``function``) rather than the next ``function`` anywhere: every one of these
    functions contains inline callbacks, so the naive split truncated the body
    at the first ``function (r) {`` and made assertions pass or fail on
    whichever lines happened to survive.
    """
    after = CODE.split("function " + name, 1)[1]
    end = after.find("\n  function ")
    return after if end == -1 else after[:end]


# --------------------------------------------------------------------------- #
# 1. The shortlist is a measurement, not a quality claim
# --------------------------------------------------------------------------- #


def test_the_shortlist_is_not_called_best():
    """The owner asked for "top 10 best". DarvaX has no quality score and DX-6a
    deferred the quantities needed to build one, so the panel is titled by what
    it actually measures. Calling it "best" would be the false precision DX-5
    warns about."""
    assert "Buy candidates" in HTML
    lowered = HTML.lower()
    for claim in ("top 10 best", "best trades", "best picks", "highest conviction"):
        assert claim not in lowered, f"page claims {claim!r}, which DarvaX cannot support"


def test_the_shortlist_states_that_it_is_not_a_ranking_of_quality():
    assert "not a ranking of quality" in FLAT_HTML
    assert "no score, no target" in FLAT_HTML


def test_the_shortlist_uses_the_engines_rank_not_a_client_side_reranking():
    """The engine already orders ACTIONABLE by distance-to-breakout and assigns
    `rank`. Re-sorting on a raw measurement here would be a second ranking,
    free to disagree with the screen below it (ADR-005)."""
    assert "renderBuy" in CODE
    top10 = body("renderBuy")
    assert "a.rank" in top10 and "b.rank" in top10, (
        "the shortlist must order by the engine's persisted rank"
    )
    comparator = top10.split(".sort(", 1)[1].split("})", 1)[0]
    assert "distance_to_breakout_pct" not in comparator, (
        "ordering must not be recomputed from a raw measurement"
    )


def test_the_shortlist_is_capped():
    """Was pinned to `.slice(0, 10)`. DX-10b made the cap depend on whether a
    filter is active — an unfiltered screen must not open with 117 cards, but a
    filtered list is narrowed by intent and earns a larger one. The durable
    property is that a cap exists and is applied, not its literal value."""
    fn = body("renderBuy")
    assert ".slice(0, limit)" in fn
    assert "BUY_SHORTLIST" in fn


def test_the_shortlist_only_contains_entry_candidates():
    """A held instrument reads HOLD, and a shortlist of things to enter must not
    include something already owned."""
    assert "risk_bearing" in body("renderBuy")


# --------------------------------------------------------------------------- #
# 2. The unvalidated badge (design decision 3b)
# --------------------------------------------------------------------------- #


def test_the_badge_is_driven_by_the_server_not_a_hardcoded_list():
    """`risk_bearing` is computed from RISK_BEARING_ACTIONS server-side, so the
    set cannot drift when an action is added."""
    chip = body("actionChip")
    assert "risk_bearing" in chip
    assert '"ENTER"' not in chip and "'ENTER'" not in chip, (
        "which actions carry risk must not be re-decided in JS"
    )


def test_the_badge_names_the_dx5_attribution_finding():
    """The label must carry *why* it is unvalidated, not just that it is —
    DX-5 attributes most of the measured edge to the exit rule and drift."""
    chip = body("actionChip")
    assert "unvalidated" in chip.lower()
    assert "box detection" in chip, "the badge must state what DX-5 actually found"


def test_the_badge_has_a_visible_style():
    assert ".unval" in CSS


def test_the_page_level_banner_survives_the_redesign():
    """Decision 3b moved the *per-action* warning onto chips; it did not remove
    the page banner. A redesign is the easiest place to lose this."""
    assert "EXPERIMENTAL" in HTML and "UNVALIDATED" in HTML
    assert 'class="banner"' in HTML
    assert "banner" not in CODE, "the banner must never be conditionally hidden"


# --------------------------------------------------------------------------- #
# 3. Advice is rendered, never derived
# --------------------------------------------------------------------------- #


def test_the_page_renders_the_stored_action_reason_verbatim():
    assert "action_reason" in CODE


def test_the_action_label_map_is_labels_only():
    """Mapping ENTER -> "Enter" is presentation. Mapping a *signal state* to an
    action would be a second source of truth for advice (ADR-005)."""
    labels = CODE.split("var ACTION_LABEL")[1].split("};")[0]
    for state in ("BREAKOUT", "INSIDE_TOPMOST_BOX", "BELOW_BOX_BOTTOM", "NO_BOX"):
        assert state not in labels, f"label map derives from {state}"


def test_no_advice_word_is_computed_from_a_signal_state():
    """Line-scoped, as in DX-7a: displaying a state and displaying an action are
    both fine; the two on one line is what a lookup or ternary looks like."""
    states = ("BREAKOUT_RETEST", "INSIDE_TOPMOST_BOX", "BELOW_BOX_BOTTOM", "NO_BOX")
    actions = ("ENTER", "ENTER_ON_RETEST", "WAIT", "EXIT_IF_HELD", "NO_ENTRY", "HOLD")
    offenders = []
    for lineno, line in enumerate(CODE.splitlines(), start=1):
        hit = next((s for s in states if s in line), None)
        if hit is None:
            continue
        rest = line.replace(hit, "")
        act = next((a for a in actions if a in rest), None)
        if act:
            offenders.append(f"darvax.js:{lineno} {hit} -> {act}")
    assert offenders == [], offenders


def test_the_page_computes_no_percentage_the_engine_could_have_persisted():
    """Unrealised return is the one number computed client-side, and only
    because it changes with every tick and has no rule behind it to record."""
    assert "action_reason" in CODE
    assert "distance_to_breakout_pct" in CODE  # read, not recomputed


# --------------------------------------------------------------------------- #
# 4. Positions zone
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "element_id",
    [
        "positions-zone", "pos-empty", "pos-form", "pos-note",
        "sell-group", "sell-tickets", "hold-group", "hold-tickets",
        "buy-zone", "buy-tickets", "buy-sub",
        "advisor-view", "detailed-view",
    ],
)
def test_required_containers_exist(element_id: str):
    assert f'id="{element_id}"' in HTML


def test_the_positions_zone_explains_why_it_exists_when_empty():
    """An empty state that just says "nothing here" wastes the one moment the
    owner is asking what this is for."""
    assert "No positions recorded" in HTML
    assert "cannot see what you own" in HTML


def test_the_form_says_the_stop_is_derived_and_frozen():
    assert "fixed at the time you add it" in FLAT_HTML


def test_delete_is_confirmed_and_close_is_not():
    """Close preserves a round trip and is the normal path; delete erases a
    record. Only the destructive one interrupts."""
    flat = " ".join(CODE.split())
    # The delete branch confirms; the close branch does not. Asserted on the
    # ordering of the two branches rather than on a substring anywhere in the
    # file, so a confirm added to the close path would fail this.
    close_branch = flat.split("if (closeBtn) {", 1)[1].split("if (delBtn) {", 1)[0]
    del_branch = flat.split("if (delBtn) {", 1)[1]
    assert "confirm" not in close_branch, (
        "closing a real trade is the normal path and must not interrupt"
    )
    assert "window.confirm" in del_branch, (
        "deleting erases a record and must be confirmed"
    )


def test_the_page_does_not_reconcile_with_athenas_positions():
    """Decision 1a: DarvaX keeps its own list. Reading ATHENA's would need an
    ADR-010 amendment that was explicitly not taken."""
    assert "owner_positions" not in CODE
    assert "/api/v1/portfolio" not in CODE


def test_recording_a_position_never_places_an_order():
    for word in ("place_order", "submit_order", "/orders", "buy(", "sell("):
        assert word not in CODE, f"page references {word!r}"


# --------------------------------------------------------------------------- #
# 5. Discipline carried over from DX-6c
# --------------------------------------------------------------------------- #


def test_no_framework_or_build_step_is_introduced():
    """ADR-004. The advisor is a bigger UI, which is exactly when a framework
    starts looking reasonable."""
    for marker in ("react", "vue", "angular", "import ", "require(", "webpack"):
        assert marker not in CODE.lower(), f"{marker!r} appeared in darvax.js"


def test_dates_use_local_time_not_utc():
    """`toISOString` is a day behind IST every morning — the DX-6c freshness
    bug. The position form defaults a date, so it is exposed to the same trap."""
    assert "toISOString" not in CODE


def test_the_asset_version_moved_past_the_previous_milestone():
    """A browser holding the DX-6c bundle renders the new HTML against old JS:
    the zones appear and nothing ever populates them, which looks like a data
    problem rather than a caching one.

    Pinned to "not the previous value" rather than to this milestone's literal —
    the equal-versions invariant lives in the DX-6c suite, and pinning the
    current string here would break the next milestone for doing the right
    thing."""
    assert "dx6c" not in HTML, "assets still carry the previous milestone's version"


def test_the_screener_table_is_kept_as_the_third_zone():
    """DX-6c's table already handles sorting, filtering, expansion, progress,
    cancel, staleness and digest mismatch. Rebuilding it would discard tested
    behaviour for no gain."""
    assert 'id="tiers"' in HTML
    assert "renderTiers" in CODE
    assert 'id="skipped"' in HTML


def test_the_advisor_zones_render_from_the_same_rows_as_the_table():
    """Otherwise the shortlist could show a different sweep than the screen
    beneath it."""
    render = body("renderScreen")
    assert "renderBuy" in render and "renderPositions" in render


def test_the_screen_request_does_not_silently_truncate_the_universe():
    """Found in the browser at DX-7c: the page requested `limit=2000` against a
    2,191-instrument sweep, dropped 191 rows, and then reported "2000
    instrument(s) screened" as though that were the coverage.

    Two separate defects — a cap below the universe, and a count derived from
    rows received rather than from what the sweep evaluated. The second is the
    worse one: a truncated view that says so is a limitation, one that reports
    the smaller number as fact is wrong."""
    assert "limit=2000" not in CODE, "the row cap must not sit below the universe"
    assert "SCREEN_ROW_LIMIT" in CODE
    loader = body("loadScreen") if "function loadScreen" in CODE else CODE
    assert "sweep.evaluated" in loader, (
        "the count shown must come from the sweep, not from rows received"
    )
    assert "truncated" in loader, "truncation must be stated, not hidden"


def test_hidden_is_forced_off_regardless_of_display_rules():
    """Also found in the browser: `.posform { display: flex }` overrode the
    `hidden` attribute, so the "record a holding" form rendered permanently
    open. Every state on this page is toggled with `hidden`, so the guard is
    declared once globally rather than remembered per component."""
    flat = " ".join(CSS.split())
    assert "[hidden] { display: none !important; }" in flat


def test_the_page_document_is_revalidated_on_every_load(tmp_path):
    """After DX-7c the owner restarted onto new code and still saw the old
    bundle: the dashboard tab embeds this page in a lazy iframe, the browser
    had the *document* cached, and a cached document requests the old
    `darvax.js?v=…` — so the version bump could never be observed.

    Cache-busting sub-resources only works if the HTML that references them is
    fetched. `no-cache` means revalidate, so an unchanged file still answers
    304."""
    import json

    from fastapi.testclient import TestClient

    from athena.api.app import create_app
    from athena.api.config import APISettings
    from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
    from athena.data.store.repository import SqliteRepository

    config_dir = tmp_path / "cfg"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "database": {"path": "db/darvax.db"}}),
        encoding="utf-8",
    )
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    app.state.sqlite_repo = repo
    assert mount_darvax_if_enabled(
        app, repo=repo, config_dir=config_dir, repo_root=tmp_path
    )
    with TestClient(app) as client:
        response = client.get(f"{DARVAX_MOUNT_PATH}/")
    repo.close()

    assert response.status_code == 200
    assert "no-cache" in response.headers.get("cache-control", "").lower(), (
        "a cached document pins the browser to the previous JS bundle"
    )


TAB_JS = (STATIC / "tab.js").read_text(encoding="utf-8")


def test_the_embedded_iframe_url_is_versioned():
    """The dashboard tab kept showing the DX-6c UI while `/darvax/` in its own
    tab showed DX-7c — same server, same minute.

    `/darvax/` and `/darvax/?embedded=1` are separate cache keys, and `tab.js`
    sets the iframe `src` *dynamically*, which does not inherit the parent's
    reload cache-bypass. So a hard reload fixed the standalone page and left the
    frame untouched. Versioning the frame URL means a UI bump produces a URL the
    browser has never seen, which it cannot serve from cache."""
    assert "UI_VERSION" in TAB_JS
    assert "embedded=1&v=" in TAB_JS


def test_the_iframe_version_matches_the_asset_version():
    """Two independent version strings that must agree; if they drift, the
    frame is busted on a schedule unrelated to the assets it loads."""
    import re

    ui = re.search(r'UI_VERSION\s*=\s*"([^"]+)"', TAB_JS)
    asset = re.search(r"darvax\.js\?v=([\w.\-]+)", HTML)
    assert ui and asset
    assert ui.group(1) == asset.group(1), (
        f"tab.js UI_VERSION={ui.group(1)} but assets are {asset.group(1)}"
    )


def test_darvax_static_assets_are_revalidated(tmp_path):
    """`tab.js` is referenced from ATHENA's index.html with **no** version
    query, so it is cacheable forever by default — a stale `tab.js` keeps
    building the old iframe no matter what the assets it points at say."""
    import json

    from fastapi.testclient import TestClient

    from athena.api.app import create_app
    from athena.api.config import APISettings
    from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
    from athena.data.store.repository import SqliteRepository

    config_dir = tmp_path / "cfg"
    config_dir.mkdir(parents=True)
    (config_dir / "darvax.json").write_text(
        json.dumps({"enabled": True, "database": {"path": "db/darvax.db"}}),
        encoding="utf-8",
    )
    repo = SqliteRepository(tmp_path / "athena.db")
    repo.initialize()
    app = create_app(APISettings())
    app.state.sqlite_repo = repo
    assert mount_darvax_if_enabled(
        app, repo=repo, config_dir=config_dir, repo_root=tmp_path
    )
    with TestClient(app) as client:
        for asset in ("tab.js", "darvax.js", "darvax.css"):
            response = client.get(f"{DARVAX_MOUNT_PATH}/static/{asset}")
            assert response.status_code == 200, asset
            assert "no-cache" in response.headers.get("cache-control", "").lower(), (
                f"{asset} may be cached indefinitely"
            )
    repo.close()
