"""SI-P2A experience IA + GET-first / in-flight request hardening contracts."""

from __future__ import annotations

from pathlib import Path

from athena.api.app import DASHBOARD_JS_PARTS, assemble_dashboard_js

STATIC = Path("src/athena/api/static")
JS = STATIC / "js/08c-symbol-intelligence.js"
SHELL = STATIC / "js/03-app-shell.js"
HTML = STATIC / "index.html"
CSS = STATIC / "css/15-symbol-intelligence.css"


def _si_pane(html: str) -> str:
    start = html.index('id="tab-symbol-intelligence"')
    end = html.index('id="tab-market"')
    return html[start:end]


def test_si_p2a_four_primary_surfaces_replace_eight_tabs() -> None:
    html = HTML.read_text(encoding="utf-8")
    pane = _si_pane(html)
    assert 'data-si-section="stock-360">Stock 360</button>' in pane
    assert 'data-si-section="decision">ATHENA Decision</button>' in pane
    assert 'data-si-section="experimental">DarvaX</button>' in pane
    assert 'data-si-section="audit">Evidence</button>' in pane
    assert pane.count("data-si-section=") == 4
    assert 'data-si-section="complete"' not in pane
    assert 'data-si-section="technical"' not in pane
    assert 'data-si-section="fundamentals"' not in pane
    assert 'data-si-section="news"' not in pane
    assert "Complete Review" not in pane
    assert "Technical / Structure" not in pane
    assert ">Fundamentals<" not in pane
    assert "News &amp; Catalysts" not in pane


def test_si_p2a_get_first_no_automatic_duplicate_post() -> None:
    js = JS.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    assert "const analyze = options.analyze === true;" in js
    assert 'method: "POST"' in js
    assert "Loading persisted Symbol Intelligence" in js
    assert "Refreshing D1 history… Analyzing…" in js
    workspace = js[js.index("async function loadSymbolIntelligenceWorkspace") :]
    assert "await loadSymbolIntelligence(next);" in workspace
    assert "{ analyze: true }" not in workspace
    request_fn = js[
        js.index("function requestSymbolIntelligenceLoad") : js.index("async function searchSymbolIntelligence")
    ]
    assert 'loadSymbolIntelligence(input ? input.value : "", { analyze: true })' in request_fn
    init = shell[shell.index("function initializeRoute()") : shell.index("function resetToOverviewTab()")]
    assert "loadSymbolIntelligence" not in init
    assert "function loadSymbolIntelligenceWorkspace()" in js
    assert "await loadSymbolIntelligenceWorkspace();" in shell


def test_si_p2a_stale_response_and_repeated_analyze_protection() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "let siLoadGeneration = 0;" in js
    assert "generation !== siLoadGeneration" in js
    assert 'let siInFlightMode = "";' in js
    assert "function siShouldSuppressAnalyze(query)" in js
    assert 'siInFlightMode === "ANALYZE" && siSameQuery(query, siInFlightQuery)' in js
    assert "if (analyze && siShouldSuppressAnalyze(needle)) return;" in js
    assert 'siSetInFlight(analyze ? "ANALYZE" : "GET", needle)' in js
    assert 'siSetInFlight("")' in js
    assert "siSyncAnalyzeControl" in js
    assert "btn.disabled = duplicateAnalyze;" in js
    assert "siInFlightController.abort()" in js
    assert "siIsAbortError" in js
    assert "siBundle = null;" in js[js.index("function siShowWorkspaceError") :]
    assert "siAnalyzeBusy" not in js
    request_fn = js[
        js.index("function requestSymbolIntelligenceLoad") : js.index("async function searchSymbolIntelligence")
    ]
    assert "if (siAnalyzeBusy) return;" not in request_fn
    assert "siShouldSuppressAnalyze" not in request_fn


def _same_query(left: str, right: str) -> bool:
    return str(left or "").strip() == str(right or "").strip()


def _should_suppress_analyze(
    *, in_flight_mode: str, in_flight_query: str, requested_analyze: bool, requested_query: str
) -> bool:
    return requested_analyze and in_flight_mode == "ANALYZE" and _same_query(requested_query, in_flight_query)


def test_si_p2a_get_does_not_masquerade_as_analyze_busy() -> None:
    """GET in flight must not suppress same-symbol Analyze; only duplicate Analyze does."""
    js = JS.read_text(encoding="utf-8")
    load_fn = js[js.index("async function loadSymbolIntelligence") : js.index("function requestSymbolIntelligenceLoad")]
    suppress_at = load_fn.index("if (analyze && siShouldSuppressAnalyze(needle)) return;")
    generation_at = load_fn.index("const generation = ++siLoadGeneration;")
    abort_at = load_fn.index("siInFlightController.abort()")
    mode_at = load_fn.index('siSetInFlight(analyze ? "ANALYZE" : "GET", needle)')
    assert suppress_at < generation_at < abort_at < mode_at
    assert 'siInFlightMode === "ANALYZE"' in js
    assert "siAnalyzeBusy" not in js

    # 1. GET AAA in flight + Analyze AAA → not suppressed (GET is not ANALYZE)
    assert (
        _should_suppress_analyze(
            in_flight_mode="GET",
            in_flight_query="NSE:AAA",
            requested_analyze=True,
            requested_query="NSE:AAA",
        )
        is False
    )
    # 2. Analyze AAA in flight + Analyze AAA → duplicate suppressed
    assert (
        _should_suppress_analyze(
            in_flight_mode="ANALYZE",
            in_flight_query="NSE:AAA",
            requested_analyze=True,
            requested_query="NSE:AAA",
        )
        is True
    )
    assert (
        _should_suppress_analyze(
            in_flight_mode="ANALYZE",
            in_flight_query="NSE:AAA",
            requested_analyze=True,
            requested_query="  NSE:AAA  ",
        )
        is True
    )
    # 3. Analyze AAA in flight + Analyze BBB → not suppressed (BBB starts)
    assert (
        _should_suppress_analyze(
            in_flight_mode="ANALYZE",
            in_flight_query="NSE:AAA",
            requested_analyze=True,
            requested_query="NSE:BBB",
        )
        is False
    )
    # 4. GET AAA in flight + GET BBB → GET never uses suppress (requested_analyze false)
    assert (
        _should_suppress_analyze(
            in_flight_mode="GET",
            in_flight_query="NSE:AAA",
            requested_analyze=False,
            requested_query="NSE:BBB",
        )
        is False
    )

    hits = js[js.index('document.getElementById("si-search-hits")') :]
    assert 'loadSymbolIntelligence(button.getAttribute("data-si-id"))' in hits
    assert "{ analyze: true }" not in hits
    assert "siShouldSuppressAnalyze" not in hits

    input_start = js.index('addEventListener("input", event =>')
    input_handler = js[input_start : js.index('document.getElementById("si-search-hits")?.addEventListener("click"')]
    assert "siSyncAnalyzeControl()" in input_handler
    assert "duplicateAnalyze" in js
    assert 'siInFlightMode === "ANALYZE" && siSameQuery(typed, siInFlightQuery)' in js


def test_si_p2a_partial_ready_and_no_decision_presentation() -> None:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "Market data: ${siEscape(market)}" in js
    assert "SI coverage: ${siEscape(coverage)}" in js
    assert "ATHENA Decision unavailable" in js
    assert "This stock can still be researched from current market evidence. ATHENA has not produced a Decision." in js
    assert 'tone = "partial"' in js
    assert 'tone = "ready"' in js
    assert "si-coverage-banner.tone-partial" in css
    assert "si-coverage-banner.tone-ready" in css
    assert "ATHENA has not produced a Decision for this symbol." in js
    assert "SI research remains available" in js
    assert "Trend Health" not in js
    assert "Bullishness" not in js
    assert "52-week high" not in js
    assert "Available-history high" in js


def test_si_p2a_volume_vs_ma20_uses_overview_comparison() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "function siVolumeVsMa20(d1)" in js
    assert 'Number(d1.volume) >= Number(d1.volume_ma20) ? "Above MA20" : "Below MA20"' in js
    assert '${siMetric("Volume vs MA20", siVolumeVsMa20(d1))}' in js
    assert 'siMetric("Volume vs MA20", siNum(d1.volume_ma20' not in js
    assert "Daily SMA structure" in js
    assert "SuperTrend (10,3)" in js
    assert "SMA structure and SuperTrend are independent evidence" in js


def test_si_p2a_evidence_and_darvax_isolation() -> None:
    js = JS.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")
    pane = _si_pane(html)
    assert "function siAuditTable(bundle)" in js
    assert "si-audit-table" in js
    assert "<th>Source</th><th>Status</th><th>As Of</th><th>Reference</th><th>Reason</th>" in js
    assert "HYDRATION" in js
    assert "EXPERIMENTAL_UNVALIDATED" in js
    assert "It is not mixed into Stock 360 evidence" in js
    assert 'data-si-panel="experimental"' in js
    assert 'id="si-darvax-frame"' in js
    assert 'data-si-section="experimental">DarvaX' in pane
    assert pane.count('id="si-darvax-frame"') == 0
    assert "Fundamentals — Not ingested" in js
    assert "News &amp; catalysts — Not ingested" in js
    assert "Not available yet" in js


def test_si_p2a_dashboard_assets_and_hosted_nav() -> None:
    html = HTML.read_text(encoding="utf-8")
    pane = _si_pane(html)
    assembled = assemble_dashboard_js(str(STATIC))
    css = (STATIC / "dashboard.css").read_text(encoding="utf-8")
    assert "dashboard.css?v=9.250.0" in html
    assert "dashboard.js?v=9.250.0" in html
    assert 'data-si-section="stock-360"' in pane
    assert "08c-symbol-intelligence.js" in DASHBOARD_JS_PARTS
    assert "function loadSymbolIntelligence(" in assembled
    assert "siLoadGeneration" in assembled
    assert "siInFlightMode" in assembled
    assert "css/15-symbol-intelligence.css?v=9.250.0" in css
