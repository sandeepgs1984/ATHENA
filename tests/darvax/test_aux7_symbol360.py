"""AUX-7: "Symbol 360" page.

"One search box, one page: ATHENA's Decision, DarvaX's screen result,
saved-symbol status, and journal history for that instrument, side by
side." DarvaX-owned (ADR-010 DX-4), same as every other file in
src/athena/darvax/api/static/ -- this page's own JS fetches ATHENA's API
directly, architecturally fine in this direction per AUX-6's own
established asymmetry. No new backend route: every value shown comes from
an endpoint AUX-5, AUX-6, or ATHENA core already exposed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from athena.api.app import create_app
from athena.api.config import APISettings
from athena.api.darvax_mount import DARVAX_MOUNT_PATH, mount_darvax_if_enabled
from tests.darvax.test_dx4b_tab import HARNESS, NODE, TAB_JS as TAB_JS_PATH, _strip_js_comments, needs_node

REPO_ROOT = Path(__file__).resolve().parents[2]
ATHENA_STATIC = REPO_ROOT / "src" / "athena" / "api" / "static"
DARVAX_STATIC = REPO_ROOT / "src" / "athena" / "darvax" / "api" / "static"

SYMBOL360_HTML = (DARVAX_STATIC / "symbol360.html").read_text(encoding="utf-8")
SYMBOL360_JS = _strip_js_comments((DARVAX_STATIC / "symbol360.js").read_text(encoding="utf-8"))
DARVAX_JS = _strip_js_comments((DARVAX_STATIC / "darvax.js").read_text(encoding="utf-8"))
TAB_JS = _strip_js_comments((DARVAX_STATIC / "tab.js").read_text(encoding="utf-8"))


def _fn(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    try:
        end = source.index("\n  function ", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


# --------------------------------------------------------------------------- #
# 1. The page is served, and only by DarvaX -- never an ATHENA asset
# --------------------------------------------------------------------------- #


def test_symbol360_is_served_at_a_clean_darvax_route(tmp_path: Path):
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
            res = client.get(f"{DARVAX_MOUNT_PATH}/symbol360")
            assert res.status_code == 200
            assert "Symbol 360" in res.text
            assert res.headers.get("cache-control") == "no-cache, must-revalidate"
    finally:
        repo.close()


def test_no_athena_asset_references_darvax_for_symbol360():
    """Same ADR-010 Amendment 1 guard AUX-6 had to learn the hard way --
    pinned here too so a reader of this file alone sees it was checked for
    this feature specifically, not just inherited from the suite-wide test."""
    for path in (ATHENA_STATIC / "js").rglob("*.js"):
        assert "darvax" not in path.read_text(encoding="utf-8").lower(), (
            f"{path.name} references DarvaX -- Symbol 360 entry points must be "
            "injected from tab.js, never added to any ATHENA asset"
        )


# --------------------------------------------------------------------------- #
# 2. symbol360.js -- reuses existing endpoints, no new backend surface
# --------------------------------------------------------------------------- #


def test_loads_athena_decision_via_the_existing_filtered_list_endpoint():
    """No new "one decision per instrument" route: instrument_id is already
    a supported filter on GET /api/v1/decisions, sorted newest-first by
    default -- page_size=1 is a complete, correct single-instrument lookup
    without inventing a new endpoint."""
    body = _fn(SYMBOL360_JS, "loadAthenaDecision")
    assert "/api/v1/decisions?instrument_id=" in body
    assert "page_size=1" in body


def test_loads_darvax_read_via_existing_bulk_endpoint_filtered_client_side():
    """No new single-instrument screen-result route either: this mirrors
    the exact client-side-filter convention darvax.js's own screenRowFor()
    already established, and falls back to the raw per-instrument signal
    endpoint (already built for AUX-6) when no current sweep row exists."""
    body = _fn(SYMBOL360_JS, "loadDarvaxRead")
    assert "/darvax/api/screen/latest?limit=5000" in body
    assert "/darvax/api/signals/" in body


def test_saved_symbol_toggle_uses_the_existing_saved_symbols_api():
    body = _fn(SYMBOL360_JS, "loadSavedStatus")
    assert "/api/v1/saved-symbols" in body


def test_journal_history_joins_decisions_with_their_journal_and_outcome():
    """Per-instrument journal history needs journal + outcome joined onto
    each of that instrument's recent decisions -- reuses the exact
    per-decision journal/outcome endpoints already built, capped to a
    small bounded window rather than an unbounded per-decision fan-out."""
    body = _fn(SYMBOL360_JS, "loadJournalHistory")
    assert "/api/v1/decisions?instrument_id=" in body
    assert "/journal" in body
    assert "/outcome" in body
    assert "HISTORY_LIMIT" in body


def test_lookup_reads_the_symbol_query_param_on_load():
    """A link into this page (from tab.js or a DarvaX card) passes
    ?symbol=X -- the page must read it back out on load, not require the
    owner to re-type the symbol they just clicked through on."""
    assert "new URLSearchParams(window.location.search).get(\"symbol\")" in SYMBOL360_JS


# --------------------------------------------------------------------------- #
# 3. Entry points -- one from ATHENA's Decision Brief, one from DarvaX cards
# --------------------------------------------------------------------------- #


def test_tab_js_injects_an_unconditional_symbol360_link():
    """Unlike checkCrossLink's DarvaX-signal-gated link, this one must show
    up regardless of whether DarvaX has anything for the instrument --
    ATHENA's own decision, saved-symbol status, and journal history are
    all useful on Symbol 360 even when DarvaX has nothing. Links to tab.js's
    own ROUTE (?view=symbol360), never straight at /darvax/symbol360 -- a
    direct link would drop ATHENA's sidebar/chrome entirely, the same bug
    class AUX-6's DarvaX -> ATHENA link had to be fixed for (bug 4)."""
    body = _fn(TAB_JS, "showSymbol360Link")
    assert "ROUTE + \"?symbol=\"" in body
    assert "&view=symbol360" in body
    assert "/darvax/symbol360" not in body, "must not link straight at the standalone page"
    assert "target" not in body, "same-tab navigation: tab.js never runs nested"


def test_tab_js_still_never_calls_athena_internals_for_symbol360():
    body = _fn(TAB_JS, "showSymbol360Link")
    for forbidden in ("switchTab(", "state.", "apiRequest(", "loadTabData("):
        assert forbidden not in body, f"showSymbol360Link calls ATHENA internal {forbidden}"


def test_darvax_cards_link_to_symbol360_with_target_top():
    """This page can be viewed either standalone or embedded inside
    ATHENA's own DarvaX nav tab (an iframe) -- same reasoning athenaChip
    already established: target="_top" always lands on the full page
    rather than nesting it inside a small pane. Links to ATHENA's own
    /dashboard/darvax route (view=symbol360), never straight at
    /darvax/symbol360 -- same AUX-6-bug-4 class as showSymbol360Link above:
    a direct link drops ATHENA's sidebar entirely instead of retargeting
    the embedded iframe."""
    body = _fn(DARVAX_JS, "symbol360Chip")
    assert "/dashboard/darvax?symbol=" in body
    assert "&view=symbol360" in body
    assert "/darvax/symbol360" not in body, "must not link straight at the standalone page"
    assert 'target="_top"' in body


def test_ticket_and_ladder_cards_include_the_symbol360_chip():
    assert DARVAX_JS.count("symbol360Chip(") >= 3, (
        "expected the chip wired into buyTicket, holdingTicket, and ladderCard"
    )


# --------------------------------------------------------------------------- #
# 4. build() actually routes the embedded iframe -- executed, not grepped
# --------------------------------------------------------------------------- #


def _run_tab_js_deeplink(search: str) -> dict:
    """Same harness test_dx4b_tab.py uses, with a query string on the deep
    link -- grepping tab.js's source only proves it mentions "view=symbol360";
    this actually runs build() and inspects the iframe it constructs, which is
    the standard this whole test file (and AUX-6's postmortem) holds cross-lane
    routing to."""
    result = subprocess.run(
        [NODE, str(HARNESS), str(TAB_JS_PATH), "deeplink", search],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@needs_node
def test_symbol360_deep_link_points_the_embedded_iframe_at_symbol360():
    """A deep link to tab.js's own ROUTE with ?view=symbol360 (what
    showSymbol360Link and symbol360Chip both now emit) must retarget the
    embedded iframe at /darvax/symbol360, not the main screener -- this is
    the actual fix for the owner-reported bug where clicking either link
    dropped ATHENA's sidebar because the iframe still loaded the bare
    /darvax/symbol360 page pointed at directly instead."""
    outcome = _run_tab_js_deeplink("?symbol=ABDL&view=symbol360")
    assert outcome["threw"] is None
    assert outcome["frameDataSrc"] is not None
    assert outcome["frameDataSrc"].startswith("/darvax/symbol360?")
    assert "symbol=ABDL" in outcome["frameDataSrc"]
    assert outcome["panelActive"] is True


@needs_node
def test_plain_deep_link_without_view_param_still_opens_the_main_screener():
    """Regression guard for the branch itself: an ordinary /dashboard/darvax
    deep link (AUX-1b/AUX-6's existing case, no ?view=) must be unaffected by
    the new symbol360 branch and keep opening the main screener."""
    outcome = _run_tab_js_deeplink("")
    assert outcome["frameDataSrc"] is not None
    assert outcome["frameDataSrc"].startswith("/darvax/?")
    assert "/darvax/symbol360" not in outcome["frameDataSrc"]


# --------------------------------------------------------------------------- #
# 5. DarvaX Read's ACTION field: humanized label, not a raw DAR-CARD code
# --------------------------------------------------------------------------- #


def test_action_label_map_matches_darvax_js_exactly():
    """Owner-reported: the DarvaX Read card showed the raw code
    ("ENTER_ON_RETEST") instead of a readable label. Duplicated here per this
    file's own convention (no cross-file import), so pinned equal to
    darvax.js's own ACTION_LABEL to guard against the two silently drifting
    apart if either is edited alone."""
    own = _fn(SYMBOL360_JS, "actionLabel")
    for code, label in {
        "ENTER": "Buy",
        "ENTER_ON_RETEST": "Buy on retest",
        "WAIT": "Wait",
        "HOLD": "Hold",
        "EXIT": "Sell",
        "EXIT_IF_HELD": "Sell if held",
        "NO_ENTRY": "Skip",
    }.items():
        entry = code + ": \"" + label + "\""
        assert entry in SYMBOL360_JS, f"symbol360.js ACTION_LABEL missing {entry!r}"
        assert entry in DARVAX_JS, f"darvax.js ACTION_LABEL missing {entry!r}"
    assert "ACTION_LABEL[row.action]" in own


def test_action_label_has_no_bracketed_price():
    """An earlier version of this fix bracketed the same trigger/stop price
    already shown one line below ("Buy above" / "Stop loss") -- live review
    found that confusing duplication, not extra clarity, so the label must
    stay plain. Regression guard against re-adding it."""
    body = _fn(SYMBOL360_JS, "actionLabel")
    assert "trigger_price" not in body
    assert "stop_price" not in body
    assert "money(" not in body


def test_darvax_card_action_row_uses_the_humanized_helper():
    body = _fn(SYMBOL360_JS, "renderDarvaxCard")
    assert "actionLabel(row)" in body
    assert "esc(row.action)" not in body, "must not fall back to the raw DAR-CARD code"


def test_action_row_carries_a_tooltip_with_the_persisted_reason():
    """Owner-reported: "Buy on retest" alone doesn't say what the retest
    price actually is. The tooltip must reuse the same already-persisted
    action_reason_plain this card already prints as its own "why" paragraph
    (which carries the concrete box-top value) -- never a new sentence."""
    body = _fn(SYMBOL360_JS, "actionTitleAttr")
    assert "row.action_reason_plain" in body
    assert "actionTitleAttr(row)" in _fn(SYMBOL360_JS, "renderDarvaxCard")


def test_darvax_js_action_chip_also_carries_the_same_tooltip():
    """Same fix applied to the Advisor/Levels/holdingTicket/ladderCard pill
    chip, not just Symbol 360 -- the owner asked for it wherever the action
    shows, and actionChip is the one shared renderer for all of those."""
    body = _fn(DARVAX_JS, "actionChip")
    assert "row.action_reason_plain" in body
    assert "title=" in body


# --------------------------------------------------------------------------- #
# 6. ATHENA Decision card: a readable "As of" timestamp, ATHENA's own convention
# --------------------------------------------------------------------------- #


def test_as_of_uses_athenas_own_readable_time_format():
    """Owner-reported: "As of" showed the raw ISO timestamp
    (2026-08-21T15:45:45.282951+05:30) instead of a readable date. Mirrors
    ATHENA's own established convention (05-utils.js's formatDecisionTime:
    "21 Aug, 03:45 pm IST"), duplicated per this file's own no-cross-file-
    import rule rather than shared."""
    body = _fn(SYMBOL360_JS, "formatDecisionTime")
    assert "Asia/Kolkata" in body
    assert '" IST"' in body
    assert "toLocaleString" in body


def test_athena_card_as_of_line_uses_the_formatter_not_the_raw_timestamp():
    body = _fn(SYMBOL360_JS, "renderAthenaCard")
    assert "formatDecisionTime(meta.ts)" in body
    assert "esc(meta.ts)" not in body
