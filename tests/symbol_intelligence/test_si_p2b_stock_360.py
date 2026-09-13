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
    assert 'data-si-section="stock-360">Stock 360</button>' in pane
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
    assert "SuperTrend (10,3)" in js
    assert "function siStructureDiffers(d1)" in js
    assert 'sma === "UPTREND" && st === "BEARISH"' in js
    assert "They are independent measurements, not a blended verdict" in js
    assert "SMA structure and SuperTrend are independent evidence" in js
    assert "Overall Trend" not in js
    assert "Moderately Bullish" not in js
    assert "Trend Health" not in js
    assert "Bullishness" not in js


def test_si_p2b_rsi_volume_levels_and_omit_empty_targets() -> None:
    js = _js()
    assert '${siMetric("RSI (14)", siRsi(d1.rsi14))}' in js
    assert '${siMetric("Volume vs MA20", siVolumeVsMa20(d1))}' in js
    assert 'Number(d1.volume) >= Number(d1.volume_ma20) ? "Above MA20" : "Below MA20"' in js
    assert 'siLevelRow("Support 1"' in js
    assert 'siLevelRow("Major support"' in js
    assert 'siLevelRow("Review trigger"' in js
    assert 'siLevelRow("Target 1"' in js
    assert 'siOptionalZoneMetric("Target 2"' in js
    assert 'siOptionalZoneMetric("Target 3"' in js
    assert "function siZoneLooksEmpty(zone)" in js
    assert "Available-history high" in js
    assert "52-week high" not in js
    assert "function siPriceMapRelation" in js
    assert "function siCloseVsBoundary" in js
    assert "function siLevelVsClose" in js
    assert "siPriceMapRelation(closeN - boundaryN, boundaryN)" in js
    assert "siPriceMapRelation(levelN - closeN, closeN)" in js
    assert 'bound: "upper"' in js
    assert 'bound: "lower"' in js
    assert 'perspective: "close-vs-boundary"' in js
    assert 'perspective: "level-vs-close"' in js
    assert "Live/latest quote is not mixed in" in js


def test_si_p2b_decision_portfolio_partial_and_capabilities() -> None:
    js = _js()
    assert "function siAthenaView(decision)" in js
    assert "Not available for this symbol" in js
    assert "Stock 360 research remains available" in js
    assert "ATHENA has not produced a Decision for this symbol." in js
    assert "SI research remains available" in js
    assert 'tone = "partial"' in js
    assert "Not held in My Portfolio" in js
    assert "Symbol Intelligence does not issue BUY/HOLD/SELL" in js
    assert "Fundamentals — Not ingested" in js
    assert "News &amp; catalysts — Not ingested" in js
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
    assert "siChartBlock(identity, d1)" in render
    assert "identity.resolved && identity.instrument_id && d1.present" in render
    assert "Loading D1 chart…" in chart_fn
    css = CSS.read_text(encoding="utf-8")
    assert ".si-chart-host.si-chart-pending" in css
    assert ".si-scan-strip" in css
    assert "flex-shrink: 0" in css
    assert "@media (max-width: 720px)" in css


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
    assert "dashboard.css?v=9.244.0" in html
    assert "dashboard.js?v=9.244.0" in html
    assert "css/15-symbol-intelligence.css?v=9.244.0" in css


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
    price_map = js[js.index("function siLevelRow") : js.index("function siScanStrip")]
    assert "d1 && d1.close" in price_map or "const close = d1 && d1.close" in price_map
    assert "live.last_price" not in price_map
    assert "live.change_pct" not in price_map
    assert 'bound === "upper" ? zone.upper : zone.lower' in price_map
    assert 'siLevelRow("Support 1"' in price_map
    assert 'bound: "upper"' in price_map
    assert 'siLevelRow("Major support"' in price_map
    assert 'siLevelRow("Review trigger"' in price_map
    assert 'bound: "lower"' in price_map
    assert 'siLevelRow("Target 1"' in price_map
    assert 'siOptionalZoneMetric("Target 2"' in price_map
    assert 'siOptionalZoneMetric("Target 3"' in price_map
    import re

    for banned in (
        "good buffer",
        "low risk",
        "strong support",
    ):
        assert banned not in price_map.lower()
    assert re.search(r"\b(safe|healthy|broken|exit|sell|buy|hold)\b", price_map, re.I) is None


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
    assert "live.present ? siMetric(siQuotePriceLabel(live), siMoney(live.last_price))" in js
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
    assert "overflow-wrap: anywhere" not in css[css.index(".si-scan-item strong") : css.index(".si-note")]


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

