"""AUX-6: "See the other view" cross-link between ATHENA and DarvaX.

Architecture note this milestone ran into: ATHENA's own dashboard assets
(src/athena/api/static/js/*.js, *.css) must never reference DarvaX by name
anywhere but the one permitted script tag (ADR-010 Amendment 1, enforced by
test_dx4_surface.py::test_darvax_ui_does_not_touch_athena_dashboard_assets
and test_dx4b_tab.py's equivalents). The ATHENA -> DarvaX half of this
cross-link therefore cannot live in any ATHENA asset. It is instead injected
entirely from DarvaX's own tab.js (already the one file responsible for
DOM-injecting things into ATHENA's page, per DX-4b), which watches
#decision-brief-title for a real instrument and adds a link only when
DarvaX has a signal for it. The DarvaX -> ATHENA half is architecturally
unremarkable (DarvaX may read ATHENA) and lives in darvax.js directly.
"""

from __future__ import annotations

from pathlib import Path

from tests.darvax.test_dx4b_tab import _strip_js_comments

REPO_ROOT = Path(__file__).resolve().parents[2]
ATHENA_STATIC = REPO_ROOT / "src" / "athena" / "api" / "static"
DARVAX_STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"

DARVAX_JS = _strip_js_comments((DARVAX_STATIC / "darvax.js").read_text(encoding="utf-8"))
TAB_JS_RAW = (DARVAX_STATIC / "tab.js").read_text(encoding="utf-8")
TAB_JS = _strip_js_comments(TAB_JS_RAW)


def _fn(source: str, name: str) -> str:
    """Slice one function's body out of JS source by name (DX-12b's helper,
    made robust to being the last function declared in the file)."""
    start = source.index(f"function {name}(")
    try:
        end = source.index("\n  function ", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


# --------------------------------------------------------------------------- #
# 1. DarvaX -> ATHENA half (darvax.js) -- architecturally unremarkable
# --------------------------------------------------------------------------- #


def test_athena_chip_only_shows_when_the_bulk_map_has_the_instrument():
    body = _fn(DARVAX_JS, "athenaChip")
    assert "athenaDecisionByInstrument[instrumentId]" in body
    assert 'if (!decisionId) return ""' in body


def test_athena_chip_links_to_the_decision_by_id_not_a_resolve_step():
    """The bulk fetch already carries decision_id per instrument, so the
    link must use it directly -- a second resolve-by-instrument round trip
    on ATHENA's side would be unnecessary plumbing this design avoided."""
    body = _fn(DARVAX_JS, "athenaChip")
    assert "/dashboard/decisions?decision=" in body


def test_athena_chip_targets_top_not_blank_and_not_untargeted():
    """Three real bugs, in order, all caught by the owner live:
    (1) target="_blank" opened a new tab with no guaranteed access to this
    tab's sessionStorage (where the ATHENA auth token lives) -> login
    screen. (2) Removing target entirely broke when this page is viewed
    *embedded* in ATHENA's own DarvaX nav tab (an iframe) -- an untargeted
    link only navigates that iframe, opening a second, nested ATHENA
    dashboard inside the DarvaX pane. (3) target="_top" fixes both: it
    always navigates the outermost window of the SAME tab (no new browsing
    context, so sessionStorage is untouched) and is a harmless no-op when
    this page isn't embedded."""
    body = _fn(DARVAX_JS, "athenaChip")
    assert 'target="_top"' in body
    assert "noopener" not in body


def test_load_athena_cross_links_reuses_the_existing_latest_endpoint():
    """Must reuse GET /api/v1/decisions/latest (already built for AUX-1a) --
    not paginate the full decision list or invent a second endpoint."""
    body = _fn(DARVAX_JS, "loadAthenaCrossLinks")
    assert '"/api/v1/decisions/latest"' in body
    assert "renderScreen()" in body, "must re-render once the map arrives late"


def test_load_athena_cross_links_degrades_silently_on_failure():
    body = _fn(DARVAX_JS, "loadAthenaCrossLinks")
    assert ".catch(" in body


def test_crosslink_url_params_set_filter_and_mode_before_first_render():
    assert "function applyCrossLinkParams" in DARVAX_JS
    start = DARVAX_JS.index("function applyCrossLinkParams")
    body = DARVAX_JS[start:DARVAX_JS.index("})();", start) + len("})();")]
    assert 'params.get("symbol")' in body
    assert "screen.filter" in body
    assert 'setMode("table")' in body
    # The IIFE runs at its own definition point (top-level statements execute
    # in source order), so it must appear before loadScreen() is called, or
    # the opening render flashes unfiltered before jumping to the symbol.
    # rindex: "loadScreen();" also appears earlier as a retry call inside
    # loadScreen's own error handling — the boot-time call is the last one.
    load_at = DARVAX_JS.rindex("loadScreen();")
    assert start < load_at


# --------------------------------------------------------------------------- #
# 2. ATHENA -> DarvaX half (tab.js) -- injected, never in an ATHENA asset
# --------------------------------------------------------------------------- #


def test_no_athena_asset_references_darvax_for_this_feature():
    """Redundant with the existing suite-wide ADR-010 guard, but pinned here
    too so a reader of this specific test file sees the constraint that
    shaped this milestone's design, not just its result."""
    for path in (ATHENA_STATIC / "js").rglob("*.js"):
        assert "darvax" not in path.read_text(encoding="utf-8").lower(), (
            f"{path.name} references DarvaX -- the AUX-6 cross-link must be "
            "injected from tab.js, never added to any ATHENA asset"
        )


def test_tab_js_watches_the_real_athena_hook_not_a_polyfill():
    assert "watchDecisionBrief" in TAB_JS
    body = _fn(TAB_JS, "watchDecisionBrief")
    assert '"decision-brief-title"' in body
    assert "MutationObserver" in body
    assert 'attributeFilter: ["title"]' in body


def test_injected_link_targets_this_files_own_route_not_darvax_directly():
    """Real UX bug caught by the owner live: a link straight to /darvax/
    dropped them onto DarvaX's bare standalone page with ATHENA's sidebar
    and chrome gone entirely. It must instead target ROUTE
    (/dashboard/darvax, this file's own embedded-tab route) so build()'s
    param-forwarding (tested below) can carry ?symbol=/&mode= into the
    already-embedded iframe, keeping the rest of the dashboard visible."""
    body = _fn(TAB_JS, "checkCrossLink")
    assert 'link.href = ROUTE + "?symbol="' in body
    assert "/darvax/?symbol=" not in body


def test_build_forwards_crosslink_params_into_the_iframe_src():
    """The other half of the fix above: build() must read the SAME
    ?symbol=/&mode= params back out of the outer page's own URL (which is
    exactly what a link to ROUTE?symbol=...&mode=... produces) and forward
    them into the iframe's src, or the embedded view opens unfiltered
    instead of pre-scoped to the symbol that was clicked through on."""
    start = TAB_JS.index("function build(")
    end = TAB_JS.index("\n  var ATHENA_TOKEN_KEY", start)
    body = TAB_JS[start:end]
    assert 'outerParams.get("symbol")' in body
    assert 'outerParams.get("mode")' in body
    assert '"&symbol=" + encodeURIComponent(crosslinkSymbol)' in body
    assert '"&mode=" + encodeURIComponent(crosslinkMode)' in body


def test_deep_link_reasserts_activation_against_athenas_own_routing_race():
    """Real bug, owner-caught with a screenshot: a deep link to ROUTE
    correctly activated this pane synchronously, but ATHENA's own async
    bootstrap (an auth-status fetch that resolves after this deferred
    script has already run) then calls its own switchTab("overview") --
    unaware "darvax" isn't one of its own tab ids -- which deactivates this
    pane right back out, landing on Overview with no visible error at all.
    Confirmed by instrumenting a live page: the panel's "active" class was
    present at the moment this file's own build() finished, gone ~200ms
    later, with a stack trace pointing straight at ATHENA's switchTab. A
    fixed delay can't reliably win this race (the auth fetch's timing isn't
    knowable from here), so the fix watches for ATHENA's own class mutation
    and reasserts activation exactly once when it happens, rather than
    guessing when it's safe to activate."""
    start = TAB_JS.index("if (window.location.pathname === ROUTE) {\n      activate(false);")
    end = TAB_JS.index("\n  var ATHENA_TOKEN_KEY", start)
    body = TAB_JS[start:end]
    assert "new MutationObserver" in body
    assert "panel.classList.contains(\"active\")" in body
    assert "reassertOnce.disconnect()" in body, "must stop watching once it has intervened"
    assert "activate(false)" in body[body.index("MutationObserver"):]


def test_reassert_observer_does_not_fight_a_real_later_navigation():
    """The reassert observer must give up permanently after its first
    intervention (or after a bounded safety window) -- if it kept watching
    indefinitely, a deliberate later click to a different ATHENA tab within
    that window would be treated the same as the async-routing race and
    incorrectly reactivated, fighting the owner's own navigation."""
    start = TAB_JS.index("if (window.location.pathname === ROUTE) {\n      activate(false);")
    end = TAB_JS.index("\n  var ATHENA_TOKEN_KEY", start)
    body = TAB_JS[start:end]
    assert "setTimeout(function () { reassertOnce.disconnect(); }, 5000)" in body


def test_check_cross_link_calls_darvax_own_signal_endpoint():
    body = _fn(TAB_JS, "checkCrossLink")
    assert "/darvax/api/signals/" in body
    assert "res.ok" in body


def test_check_cross_link_navigates_in_the_same_tab():
    """Same real bug as the DarvaX-side chip, same fix: a new tab is not
    reliably guaranteed to inherit sessionStorage, so it opened to a login
    screen instead of the target page. Same-tab navigation has nothing to
    inherit -- the ATHENA token is already there."""
    body = _fn(TAB_JS, "checkCrossLink")
    assert "target" not in body
    assert "noopener" not in body


def test_injected_link_does_not_stretch_to_fill_the_column_flex_header():
    """Real UI bug: #decision-brief-header is display:flex with
    flex-direction:column, so an unstyled child defaults to align-self:
    stretch and fills the full header width -- this rendered as a wide
    banner instead of a small chip the first time. align-self must be
    pinned so it hugs its own content like every other .context-chip."""
    body = _fn(TAB_JS, "checkCrossLink")
    assert 'link.style.alignSelf = "flex-start"' in body


def test_check_cross_link_reuses_the_shared_athena_token_key():
    """Must read the exact same sessionStorage key darvax.js and ATHENA's own
    dashboard already use -- a second token store would be exactly the kind
    of parallel credential system DX-4's auth reuse was meant to avoid."""
    assert 'var ATHENA_TOKEN_KEY = "athena.access_token"' in TAB_JS
    body = _fn(TAB_JS, "crosslinkToken")
    assert "sessionStorage.getItem(ATHENA_TOKEN_KEY)" in body


def test_check_cross_link_removes_stale_link_before_checking_again():
    """Switching decisions must never leave a previous symbol's link showing
    while (or if) the new check fails."""
    body = _fn(TAB_JS, "checkCrossLink")
    assert body.index("removeCrossLink();") < body.index("fetch(")


def test_check_cross_link_guards_against_an_out_of_order_response():
    """A slow response for a since-abandoned symbol must not inject a link
    for whatever decision is open by the time it arrives."""
    body = _fn(TAB_JS, "checkCrossLink")
    assert "requestId !== crosslinkRequestId" in body


def test_tab_js_still_never_calls_athena_internals():
    """The existing DX-4b guard already covers this file wholesale; this
    pins the specific new functions this milestone added, so a future
    reader of just this test file sees the constraint was checked here too."""
    for fn_name in ("checkCrossLink", "watchDecisionBrief", "removeCrossLink"):
        body = _fn(TAB_JS, fn_name)
        for forbidden in ("switchTab(", "state.", "apiRequest(", "loadTabData("):
            assert forbidden not in body, f"{fn_name} calls ATHENA internal {forbidden}"
