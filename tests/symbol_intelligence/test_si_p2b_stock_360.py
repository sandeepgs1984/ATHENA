"""SI-P2B Stock 360 research-workspace presentation contracts."""

from __future__ import annotations

from pathlib import Path

from athena.api.app import DASHBOARD_JS_PARTS, assemble_dashboard_js

STATIC = Path("src/athena/api/static")
JS = STATIC / "js/08c-symbol-intelligence.js"
HTML = STATIC / "index.html"
CSS = STATIC / "css/15-symbol-intelligence.css"


def _si_pane(html: str) -> str:
    start = html.index('id="tab-symbol-intelligence"')
    end = html.index('id="tab-market"')
    return html[start:end]


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def test_si_p2b_keeps_four_p2a_surfaces_and_stock_360_default() -> None:
    pane = _si_pane(HTML.read_text(encoding="utf-8"))
    assert pane.count("data-si-section=") == 4
    assert 'data-si-section="stock-360"' in pane and "Stock 360</button>" in pane
    assert 'class="si-section-nav-item active" data-si-section="stock-360"' in pane
    assert "Complete Review" not in pane
    js = _js()
    assert 'getAttribute("data-si-section") || "stock-360"' in js


def test_si_p2b_duplicate_company_name_suppressed() -> None:
    js = _js()
    assert "function siCompanyName(identity)" in js
    assert "function siNormalizeLabel(value)" in js
    assert "siCompanyName(identity)" in js
    assert "normalizedName === siNormalizeLabel(symbol)" in js


def test_si_p2b_independent_structure_no_blend() -> None:
    js = _js()
    assert "Daily SMA structure" in js
    assert "function siSuperTrendLabel(value)" in js
    assert "`SuperTrend ${st}`" in js
    assert "function siSummaryStructure(d1, reportedMissing)" in js
    assert "the two measurements disagree" in js
    assert "Overall Trend" not in js
    assert "Moderately Bullish" not in js
    assert "Trend Health" not in js
    assert "Bullishness" not in js


def test_si_p2b_rsi_volume_levels_and_omit_empty_targets() -> None:
    js = _js()
    assert 'siSignalChip("rsi", "Momentum · RSI (14)", siRsi(d1.rsi14), "")' in js
    assert "const volumeLabel = siVolumeVsMa20(d1);" in js
    assert 'Number(d1.volume) >= Number(d1.volume_ma20) ? "Above MA20" : "Below MA20"' in js
    assert 'addZone("support", "Support 1"' in js
    assert 'addZone("major-support", "Major Support"' in js
    assert 'addZone("trigger", "Review Trigger"' in js
    assert 'addZone("target", "Target 1"' in js
    assert 'addZone("target", "Target 2"' in js
    assert 'addZone("target", "Target 3"' in js
    assert "function siZoneLooksEmpty(zone)" in js
    assert "if (siZoneLooksEmpty(zone)) return;" in js
    assert "Available High" in js
    assert "52-week high" not in js
    assert "function siPriceMapRelation" in js
    assert "function siCloseVsBoundary" in js
    assert "function siLevelVsClose" in js
    assert "siPriceMapRelation(closeN - boundaryN, boundaryN)" in js
    assert "siPriceMapRelation(levelN - closeN, closeN)" in js
    assert 'bound === "upper" ? zone.upper : zone.lower' in js
    assert "Live/latest quote is not mixed in" in js


def test_si_p2b_decision_portfolio_partial_and_capabilities() -> None:
    js = _js()
    assert "function siAthenaView(decision)" in js
    assert "ATHENA Decision not available for this symbol" in js
    assert "Stock 360 research remains available" in js
    assert "ATHENA has not produced a Decision for this symbol." in js
    assert "Stock 360 research remains available" in js
    assert 'tone = "partial"' in js
    assert "Not held in My Portfolio" in js
    assert "Symbol Intelligence does not issue BUY/HOLD/SELL" in js
    assert "Fundamentals <b>Not ingested</b>" in js
    assert "News &amp; catalysts <b>Not ingested</b>" in js
    assert "DarvaX experimental view available" in js
    assert "It is not mixed into Stock 360 evidence" in js
    assert "View evidence" in js
    assert "Open ATHENA Decision" in js


def test_si_p2b_invalid_symbol_omits_chart_loading_host() -> None:
    js = _js()
    chart_fn = js[js.index("function siChartBlock") : js.index("function siSentence")]
    assert "if (!identity || !identity.resolved)" in chart_fn
    assert 'return "";' in chart_fn
    render = js[js.index("function renderSymbolIntelligence") : js.index("function siErrorText")]
    assert "siChartBlock(identity, d1, bundle)" in render
    assert "identity.resolved && identity.instrument_id && d1.present" in render
    assert "Loading D1 chart…" in chart_fn
    css = CSS.read_text(encoding="utf-8")
    assert ".si-chart-host.si-chart-pending" in css
    assert ".si-chart-glance" in css
    assert "flex-shrink: 0" in css
    assert "@media (max-width: 720px)" in css


def test_si_p2b1_empty_search_and_invalid_states_are_distinct() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = _js()
    css = CSS.read_text(encoding="utf-8")
    render = js[js.index("function renderSymbolIntelligence") : js.index("function siErrorText")]

    assert 'class="si-workspace-state is-empty"' in html
    assert "Research any NSE/BSE symbol" in html
    assert 'data-si-example="NSE:INFY"' in html
    assert "function siWorkspaceState(kind, title, detail)" in js
    assert '"Enter a symbol to continue"' in js
    assert '"Symbol not found"' in render
    assert "if (!identity.resolved)" in render
    assert render.index("if (!identity.resolved)") < render.index("identityEl.innerHTML = siHeader(bundle)")
    assert "No matching instruments" in js
    assert "Check the ticker, or try the canonical format NSE:INFY." in js
    assert ".si-workspace-state.is-invalid" in css
    assert ".si-search-no-results" in css


def test_si_p2b1_header_date_nav_and_price_map_polish() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = _js()
    css = CSS.read_text(encoding="utf-8")

    assert "Load reads persisted evidence. Analyze refreshes stale D1" in html
    assert "function siQuoteCaption(live, d1)" in js
    assert '["LAST CLOSE", session === "—" ? "" : session, siEscape(market)]' in js
    assert 'const months = ["Jan", "Feb", "Mar"' in js
    assert 'tabindex="0" aria-label=' in js
    assert ".si-section-nav.is-stuck" in css
    assert ".si-price-map .si-ladder-point:hover .si-ladder-card" in css
    assert ".si-price-map .si-ladder-value" in css


def test_si_p2b1_reference_closure_composition_and_copy() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = _js()
    css = CSS.read_text(encoding="utf-8")
    render = js[js.index("function renderSymbolIntelligence") : js.index("function siErrorText")]

    toolbar = html.index('class="si-toolbar"')
    toolbar_home = html.index('id="si-toolbar-home"')
    identity = html.index('id="si-identity"')
    nav = html.index('class="si-section-nav"')
    bundle = html.index('id="si-bundle"')
    assert toolbar < toolbar_home < identity < nav < bundle

    chart = render.index("siChartBlock(identity, d1, bundle)")
    primary = render.index('class="si-360-row si-360-row-primary"')
    secondary = render.index('class="si-360-row si-360-row-secondary"')
    footer = render.index("siStock360Footer()")
    assert chart < primary < secondary < footer
    assert render.index("siCompleteReview(bundle)", primary) < render.index(
        "siPortfolioCard(bundle.portfolio)", primary
    ) < render.index("siAvailabilityChips(bundle)", primary)
    assert render.index("siLevelsCard(d1)", secondary) < render.index(
        "siAthenaView(bundle.decision)", secondary
    ) < render.index("siDarvaxOverview(bundle.darvax)", secondary)

    assert "function siChartGlancePanel(bundle)" in js
    assert '"Trend"' in js
    assert '"SuperTrend (10,3)"' in js
    assert "d1.supertrend_value" in js
    assert "superTrendDisplay" in js
    assert '"Momentum · RSI (14)"' in js
    assert '"Volume vs MA20"' in js
    assert "function siScanStrip" not in js
    assert "Momentum Healthy" not in js
    assert '<div class="si-review">' in js
    assert '<div class="si-card si-review">' not in js

    shell = (STATIC / "js/03-app-shell.js").read_text(encoding="utf-8")
    assert 'window.matchMedia("(min-width: 1181px)")' in shell
    assert "function syncSymbolIntelligenceToolbar" in shell
    assert "consoleHeader.insertBefore(toolbar, headerRight)" in shell
    assert "toolbarHome.after(toolbar)" in shell

    assert 'id="page-subtitle"' in html
    assert "Deep Insights. Smarter Decisions." in (STATIC / "js/03-app-shell.js").read_text(
        encoding="utf-8"
    )
    assert "Better information. Better decisions. A better you." in js
    assert "Symbol Intelligence · Asset 9.275.0" in js
    assert '.si-id-meta-tag + .si-id-meta-tag::before' in css
    assert 'content: "|"' in css
    assert "border-radius: 999px" not in css[css.index(".si-id-meta-tag {") : css.index(".si-id-decorative {")]
    assert ".si-portfolio-card > .si-pending" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    assert ".si-identity:not(:empty) + #si-nav-sentinel + .si-section-nav" in css
    assert """.si-identity:not(:empty) {
    border: 0;
    border-radius: 0;
}""" in css
    assert """.si-section-nav::before {
    display: none;
}""" in css
    assert """.si-section-nav.is-stuck {
    border: 0;
    border-radius: 0;""" in css
    assert """.si-chart-glance {
    gap: 2px;
    border: 0;
    border-left: 1px solid rgba(115, 146, 184, 0.16);
    border-radius: 0;""" in css
    assert "border-color: rgba(112, 143, 180, 0.2);" in css
    assert ".si-coverage-facts > div::before" in css
    assert ".si-jump > i" in css
    assert "new ResizeObserver(requestSync).observe(identity)" in js
    assert 'id="si-sticky-context"' in html
    assert "function siSyncStickyContext(bundle)" in js
    assert ".si-section-nav.is-stuck .si-sticky-context" in css
    assert "color: #a8b7cc;" in css
    assert "background: rgba(11, 23, 39, 0.97);" in css
    assert ".si-section-nav.is-stuck::after" in css
    assert "height: 12px;" in css
    assert "background: linear-gradient(180deg, rgba(1, 6, 14, 0.48), transparent);" in css
    assert "background: linear-gradient(180deg, #0d1421 0%, #0b111c 100%);" in css
    assert """.si-chart-composition {
    grid-template-columns: minmax(0, 1fr) minmax(13rem, 0.24fr);
    gap: 0;
    overflow: hidden;
    border-radius: 0;
    background: transparent;
}""" in css
    assert """.si-chart-stage {
    background: transparent;
}""" in css
    assert "padding: 2px 2px 0;" in css


def test_si_p2b_p2a_request_lifecycle_untouched() -> None:
    js = _js()
    assert "const analyze = options.analyze === true;" in js
    assert 'siSetInFlight(analyze ? "ANALYZE" : "GET", needle)' in js
    assert "function siShouldSuppressAnalyze(query)" in js
    assert "Loading persisted Symbol Intelligence" in js
    assert "Refreshing D1 history… Analyzing…" in js
    assert "siLoadGeneration" in js
    assembled = assemble_dashboard_js(str(STATIC))
    assert "function siAthenaView(decision)" in assembled
    assert "08c-symbol-intelligence.js" in DASHBOARD_JS_PARTS


def test_si_p2b_asset_cache_pin() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = (STATIC / "dashboard.css").read_text(encoding="utf-8")
    assert "dashboard.css?v=9.275.0" in html
    assert "dashboard.js?v=9.275.0" in html
    assert "css/15-symbol-intelligence.css?v=9.275.0" in css


def _finite(value: object) -> float | None:
    try:
        amount = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if amount != amount:
        return None
    return amount


def si_price_map_relation(signed_delta: object, denominator: object) -> dict[str, str] | None:
    """Mirrors 08c-symbol-intelligence.js siPriceMapRelation."""
    delta = _finite(signed_delta)
    den = _finite(denominator)
    if delta is None or den is None or den == 0:
        return None
    pct = (delta / den) * 100
    magnitude = f"{abs(pct):.1f}"
    if float(magnitude) == 0:
        return {"magnitude": magnitude, "direction": "at"}
    return {"magnitude": magnitude, "direction": "above" if pct > 0 else "below"}


def si_close_vs_boundary(close: object, boundary: object) -> dict[str, str] | None:
    close_n = _finite(close)
    boundary_n = _finite(boundary)
    if close_n is None or boundary_n is None or close_n == 0 or boundary_n == 0:
        return None
    return si_price_map_relation(close_n - boundary_n, boundary_n)


def si_level_vs_close(level: object, close: object) -> dict[str, str] | None:
    close_n = _finite(close)
    level_n = _finite(level)
    if close_n is None or level_n is None or close_n == 0 or level_n == 0:
        return None
    return si_price_map_relation(level_n - close_n, close_n)


def si_close_vs_boundary_sentence(label: str, close: object, boundary: object) -> str:
    rel = si_close_vs_boundary(close, boundary)
    if rel is None:
        return ""
    if rel["direction"] == "at":
        return f"Completed D1 is at {label} upper boundary."
    return f"Completed D1 is {rel['magnitude']}% {rel['direction']} {label} upper boundary."


def si_level_vs_close_sentence(label: str, level: object, close: object) -> str:
    rel = si_level_vs_close(level, close)
    if rel is None:
        return ""
    if rel["direction"] == "at":
        return f"{label} is at completed-D1 close."
    return f"{label} is {rel['magnitude']}% {rel['direction']} completed-D1 close."


def test_si_p2b_price_map_distance_arithmetic_and_wording() -> None:
    assert si_close_vs_boundary_sentence("Support 1", 110, 100) == (
        "Completed D1 is 10.0% above Support 1 upper boundary."
    )
    assert si_close_vs_boundary_sentence("Support 1", 90, 100) == (
        "Completed D1 is 10.0% below Support 1 upper boundary."
    )
    assert si_close_vs_boundary_sentence("Support 1", 100, 100) == (
        "Completed D1 is at Support 1 upper boundary."
    )
    assert si_level_vs_close_sentence("Review Trigger", 120, 100) == (
        "Review Trigger is 20.0% above completed-D1 close."
    )
    assert si_level_vs_close_sentence("Review Trigger", 80, 100) == (
        "Review Trigger is 20.0% below completed-D1 close."
    )
    assert si_level_vs_close_sentence("Target 1", 110, 100) == (
        "Target 1 is 10.0% above completed-D1 close."
    )
    assert si_close_vs_boundary_sentence("Support 1", None, 100) == ""
    assert si_close_vs_boundary_sentence("Support 1", 110, 0) == ""
    assert si_level_vs_close_sentence("Review Trigger", 120, 0) == ""
    assert si_level_vs_close_sentence("Review Trigger", None, 100) == ""
    assert "-10.0% above" not in si_close_vs_boundary_sentence("Support 1", 90, 100)
    assert "-20.0% above" not in si_level_vs_close_sentence("Review Trigger", 80, 100)


def test_si_p2b_price_map_js_helper_matches_python_contract() -> None:
    import json
    import shutil
    import subprocess

    js = _js()
    start = js.index("function siFiniteNumber")
    end = js.index("function siJumpButton")
    helpers = js[start:end]
    node = shutil.which("node")
    assert node is not None
    script = (
        helpers
        + """
const cases = [
  ["closeVsBoundary", siCloseVsBoundarySentence("Support 1", 110, 100)],
  ["closeBelow", siCloseVsBoundarySentence("Support 1", 90, 100)],
  ["closeAt", siCloseVsBoundarySentence("Support 1", 100, 100)],
  ["triggerAbove", siLevelVsCloseSentence("Review Trigger", 120, 100)],
  ["triggerBelow", siLevelVsCloseSentence("Review Trigger", 80, 100)],
  ["targetAbove", siLevelVsCloseSentence("Target 1", 110, 100)],
  ["missing", siCloseVsBoundarySentence("Support 1", null, 100)],
  ["zeroBoundary", siCloseVsBoundarySentence("Support 1", 110, 0)],
  ["zeroClose", siLevelVsCloseSentence("Review Trigger", 120, 0)]
];
process.stdout.write(JSON.stringify(Object.fromEntries(cases)));
"""
    )
    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    observed = json.loads(result.stdout)
    assert observed["closeVsBoundary"] == "Completed D1 is 10.0% above Support 1 upper boundary."
    assert observed["closeBelow"] == "Completed D1 is 10.0% below Support 1 upper boundary."
    assert observed["closeAt"] == "Completed D1 is at Support 1 upper boundary."
    assert observed["triggerAbove"] == "Review Trigger is 20.0% above completed-D1 close."
    assert observed["triggerBelow"] == "Review Trigger is 20.0% below completed-D1 close."
    assert observed["targetAbove"] == "Target 1 is 10.0% above completed-D1 close."
    assert observed["missing"] == ""
    assert observed["zeroBoundary"] == ""
    assert observed["zeroClose"] == ""
    assert observed["closeBelow"] == si_close_vs_boundary_sentence("Support 1", 90, 100)
    assert observed["triggerBelow"] == si_level_vs_close_sentence("Review Trigger", 80, 100)


def test_si_p2b_price_map_no_action_semantics_or_live_quote_distance() -> None:
    js = _js()
    price_map = js[js.index("function siPriceLadderPoints") : js.index("function siSignalTone")]
    assert "const close = siNullableFiniteNumber(d1 && d1.close);" in price_map
    # siFiniteNumber(null) coerces via Number(null) === 0 and is NOT null-safe
    # on its own -- a genuinely-absent available_history_high must never
    # render as a fabricated real "Available High" point at value 0.
    assert "const high = siNullableFiniteNumber(d1 && d1.available_history_high);" in price_map
    assert "live.last_price" not in price_map
    assert "live.change_pct" not in price_map
    assert 'bound === "upper" ? zone.upper : zone.lower' in price_map
    assert 'addZone("support", "Support 1"' in price_map
    assert 'addZone("major-support", "Major Support"' in price_map
    assert 'addZone("trigger", "Review Trigger"' in price_map
    assert 'addZone("target", "Target 1"' in price_map
    assert 'addZone("target", "Target 2"' in price_map
    assert 'addZone("target", "Target 3"' in price_map
    # Purely positional/stylistic red-green track -- never a safety/danger or
    # buy/sell signal (owner-mandated no-trading-advice framing).
    assert "--si-gradient-scale" in price_map or "si-price-ladder" in price_map
    import re

    for banned in (
        "good buffer",
        "low risk",
        "strong support",
    ):
        assert banned not in price_map.lower()
    assert re.search(r"\b(safe|healthy|broken|exit|sell|buy|hold)\b", price_map, re.I) is None


def test_si_p2b_ladder_null_available_high_omitted_not_zeroed() -> None:
    import json
    import shutil
    import subprocess

    js = _js()
    finite_helper = js[js.index("function siFiniteNumber") : js.index("function siMoney")]
    nullable_helper = js[js.index("function siNullableFiniteNumber") : js.index("function siPriceLadderPoints")]
    node = shutil.which("node")
    assert node is not None
    script = (
        finite_helper
        + nullable_helper
        + """
const cases = {
  nullHigh: siNullableFiniteNumber(null),
  undefinedHigh: siNullableFiniteNumber(undefined),
  realHigh: siNullableFiniteNumber(1980.4),
  zeroIsStillZero: siNullableFiniteNumber(0),
  legacyCoercesNullToZero: siFiniteNumber(null),
};
process.stdout.write(JSON.stringify(cases));
"""
    )
    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    observed = json.loads(result.stdout)
    assert observed["nullHigh"] is None
    assert observed["undefinedHigh"] is None
    assert observed["realHigh"] == 1980.4
    assert observed["zeroIsStillZero"] == 0
    # Documents the exact footgun siNullableFiniteNumber exists to guard
    # against -- siFiniteNumber alone is not safe for a plain optional field.
    assert observed["legacyCoercesNullToZero"] == 0


def test_si_p2b_presentation_formatters_and_toolbar() -> None:
    js = _js()
    css = CSS.read_text(encoding="utf-8")
    assert "function siMoney(value)" in js
    assert "function siZoneShort(zone)" in js
    assert "function siRsi(value)" in js
    assert "function siScore(value)" in js
    assert "function siEnumLabel(value" in js
    assert "amount < 0 ? `-₹${formatted}`" in js
    assert "lower.toFixed(2) === upper.toFixed(2)" in js
    assert ".toLowerCase()" in js
    assert "live.present ? live.last_price : d1.close" in js
    assert 'Symbol could not be resolved against the canonical instrument catalog.</p></div>`}' not in js
    assert "si-audit-wrap" in js
    assert "si-audit-cards" in js
    assert "UNAVAILABLE" in js
    assert "function siPriceMapRelation" in js
    assert "siPriceMapRelation(closeN - boundaryN, boundaryN)" in js
    assert ".si-symbol-input" in css and "max-height: 3rem" in css
    assert "#si-load-btn" in css
    assert "flex: 0 0 auto" in css
    media = css[css.index("@media (max-width: 720px)") :]
    assert "flex-direction: column" in media
    assert ".si-audit-cards" in media
    assert "overflow-wrap: anywhere" not in css[css.index(".si-signal-value") : css.index(".si-note")]


def test_si_p2b_presentation_js_helpers_match_owner_examples() -> None:
    import json
    import shutil
    import subprocess

    js = _js()
    helpers = js[js.index("function siEscape") : js.index("function siDate")]
    relation = js[js.index("function siPriceMapRelation") : js.index("function siJumpButton")]
    node = shutil.which("node")
    assert node is not None
    script = (
        helpers
        + relation
        + r"""
const cases = {
  p593: siMoney(593),
  p438: siMoney(438.3),
  p180: siMoney(180.5),
  p178: siMoney(178.14),
  z178: siZoneShort({lower: 178.14, upper: 180.5}),
  z438: siZoneShort({lower: 438.3, upper: 445.6}),
  z169: siZoneShort({lower: 169, upper: 169}),
  z450: siZoneShort({lower: 450.75, upper: 450.75}),
  z191: siZoneShort({lower: 191.34, upper: 191.34}),
  pnl: siMoney(-2737.9),
  chg: siPct(0.66),
  dist: siPriceMapRelation(13.742, 100).magnitude,
  rsi: siRsi(44.14),
  score: siScore(35.03),
  trade: siEnumLabel("NO_TRADE"),
  plan: siEnumLabel("NO_PLAN"),
  explain: siDisplayExplanation("Pass — score 35.03/100 is below the watch level (50.00).")
};
process.stdout.write(JSON.stringify(cases));
"""
    )
    result = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    observed = json.loads(result.stdout)
    assert observed["p593"] == "₹593.00"
    assert observed["p438"] == "₹438.30"
    assert observed["p180"] == "₹180.50"
    assert observed["p178"] == "₹178.14"
    assert observed["z178"] == "₹178.14 \u2013 ₹180.50"
    assert observed["z438"] == "₹438.30 \u2013 ₹445.60"
    assert observed["z169"] == "₹169.00"
    assert observed["z450"] == "₹450.75"
    assert observed["z191"] == "₹191.34"
    assert observed["pnl"] == "-₹2,737.90"
    assert observed["chg"] == "+0.66%"
    assert observed["dist"] == "13.7"
    assert observed["rsi"] == "44.1"
    assert observed["score"] == "35.0"
    assert observed["trade"] == "No Trade"
    assert observed["plan"] == "No Plan"
    assert observed["explain"] == "Pass — Score 35.0 / 100 is below the watch level (50.0)."
