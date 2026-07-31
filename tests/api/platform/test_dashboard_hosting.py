"""Integration tests for Phase 9.1 Dashboard Static Asset Hosting & SPA Routing.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from athena.api.app import DASHBOARD_JS_PARTS, assemble_dashboard_js

_IMPORT_RE = re.compile(r'@import\s+url\("([^"]+)"\)')


def _fetch_full_css(client: TestClient) -> str:
    """dashboard.css (UX-7 refactor) is a slim entry point that @imports the
    real rules from css/*.css, split by concern for maintainability. Tests
    that assert on CSS content need the fully assembled stylesheet, so this
    resolves and concatenates every @import in the same cascade order the
    browser would load them in — never re-derive this by re-reading
    dashboard.css directly, it no longer carries the rules itself."""
    manifest = client.get("/dashboard/dashboard.css")
    assert manifest.status_code == 200
    imports = _IMPORT_RE.findall(manifest.text)
    assert imports, "dashboard.css should @import at least one css/*.css module"
    parts = []
    for href in imports:
        resp = client.get(f"/dashboard/{href}")
        assert resp.status_code == 200, f"failed to load imported stylesheet {href}"
        parts.append(resp.text)
    return "\n".join(parts)


def test_dashboard_static_hosting_and_fallback(client: TestClient) -> None:
    """Verify static assets are correctly served and client routes fallback to index.html."""
    # 1. Test index.html retrieval
    resp_index = client.get("/dashboard/")
    assert resp_index.status_code == 200
    assert "ATHENA" in resp_index.text
    assert "<aside" in resp_index.text

    # 2. Test CSS loading — dashboard.css (UX-7) is a slim @import manifest;
    # the real rules live in css/*.css, each independently servable
    resp_css = client.get("/dashboard/dashboard.css")
    assert resp_css.status_code == 200
    assert "@import" in resp_css.text
    assert "background-color" in _fetch_full_css(client)

    # 3. Test JS loading
    resp_js = client.get("/dashboard/dashboard.js")
    assert resp_js.status_code == 200
    assert "state" in resp_js.text

    # 4. Test client-side routing fallback (non-existent path starts with /dashboard)
    resp_fallback = client.get("/dashboard/portfolio")
    assert resp_fallback.status_code == 200
    assert "ATHENA" in resp_fallback.text
    assert "<aside" in resp_fallback.text


def test_dashboard_modals_are_inert_outside_tab_flow(client: TestClient) -> None:
    """Inactive modals must not participate in tab document flow (P9 console hotfix)."""
    html = client.get("/dashboard/").text
    css = _fetch_full_css(client)
    js = client.get("/dashboard/dashboard.js").text

    # Modals are present once each and marked inert at rest
    assert html.count('id="trace-modal"') == 1
    assert html.count('id="backtest-modal"') == 1
    # trace-modal also carries .modal-stacked (drill-down layer, MI-3 polish);
    # what matters here is that it is still hidden/inert at rest.
    assert 'id="trace-modal" class="modal-overlay modal-stacked" hidden' in html
    assert 'id="backtest-modal" class="modal-overlay" hidden' in html
    assert 'aria-hidden="true"' in html

    # Modals must live outside tab panes (after #app close)
    assert "Modals live outside #app" in html
    assert html.find('id="trace-modal"') > html.find("Modals live outside #app")
    assert html.find('id="backtest-modal"') > html.find("Modals live outside #app")
    assert 'id="tab-operations"' in html
    assert html.find('id="trace-modal"') > html.find('id="tab-operations"')

    # CSS fortress: inactive overlays are forced out of layout
    assert "display: none !important" in css
    assert ".modal-overlay.active" in css

    # JS exposes open/close helpers and clears loaders on failure
    assert "function openModal" in js
    assert "function closeModal" in js
    assert "Failed to load strategy profiles" in js
    assert "Failed to load decisions" in js
    # Decisions workspace must walk every page before latest-per-instrument dedupe
    assert "function fetchAllDecisionPages" in js
    assert "function latestDecisionPerInstrument" in js
    assert "page_size" in js
    assert "has_next" in js
    assert 'sort_by: "ts"' in js

    # M-D1 instrument brief is selection-driven and never deletes decision history
    assert 'id="decision-brief-body"' in html
    assert 'id="decision-brief-title"' in html
    assert "function loadDecisionDetail" in js
    assert "function renderDecisionBrief" in js
    assert "function renderTradePlan" in js
    assert "dismissDecisionForToday" in js
    assert "athena.dismissed-decisions" in js
    assert "Decision history and replay evidence are never deleted" in js
    # M-D2 renders persisted candles with plan overlays and explicit freshness
    assert "function loadDecisionChart" in js
    assert "class DecisionChartController" in js
    assert "function renderProfessionalDecisionChart" in js
    assert "function renderCandlestickSvg" in js
    assert "function renderChartFreshness" in js
    assert "CHART_TIMEFRAMES = [\"5m\", \"15m\"]" in js
    assert "CHART_LIMITS = [60, 120, 300, 500]" in js
    assert "athena.decision-chart-preferences" in js
    assert "function chartPreferences" in js
    assert "function saveChartPreferences" in js
    assert "function renderChartControlState" in js
    assert "function chartReturnedRangeLabel" in js
    assert "function chartInspectionValue" in js
    assert "function chartPlanInspection" in js
    assert "inspectAtIndex" in js
    assert "inspectFromPointer" in js
    assert "hideCrosshair" in js
    assert "focusShell" in js
    assert "activeInspectionHostId" in js
    assert "hitArea.getBoundingClientRect()" in js
    assert "event.currentTarget.getBoundingClientRect()" not in js
    assert 'role="slider"' not in js
    assert 'tabindex="0" role="slider"' not in js
    assert 'tabindex="0" role="group"' in js
    assert "pointerdown" in js
    assert "pointer-events: all" in css
    assert "function reloadActiveDecisionChart" in js
    assert "data-chart-timeframe=\"1m\"" not in js
    assert "data-chart-timeframe=\"1m\"" not in html
    assert "data-chart-timeframe=\"5m\"" in js
    assert "data-chart-timeframe=\"15m\"" in js
    assert "data-chart-limit=\"500\"" in js
    assert 'id="decision-chart-open-fullscreen"' in js
    assert 'class="decision-chart-controls chart-modal-controls"' in html
    assert "No persisted ${escapeDecisionHtml(timeframe)} candles" in js
    assert "of ${requested} requested" in js
    assert "data-chart-inspector-copy" in js
    assert "decision-chart-hit-area" in js
    assert "decision-chart-crosshair" in js
    assert "data-chart-reset" in js
    assert "Keyboard" not in html
    assert "Unavailable" in js
    assert "ArrowLeft" in js
    assert "ArrowRight" in js
    assert "timeframe=${encodeURIComponent(prefs.timeframe)}&limit=${encodeURIComponent(prefs.limit)}" in js
    assert "decision-chart-session-separator" in js
    assert "function chartPersistedEvents" in js
    assert "function nearestCandleIndexForTs" in js
    assert "decision-chart-event-marker" in js
    assert "activeJournalEntry.action_ts" in js
    assert "activeTradeOutcome.closed_ts" in js
    assert "return null" in js
    assert ".decision-chart-event-marker" in css
    assert ".decision-chart-event-marker.journal" in css
    assert ".decision-chart-event-marker.outcome" in css
    assert "latest candle" in js
    assert "skipToast: true" in js
    assert "session-close analysis" in js
    # M-D3 renders persisted eligibility/analysis/history and safe candidate removal
    assert "function loadDecisionDepth" in js
    assert "/depth" in js
    assert "function renderEligibilityDepth" in js
    assert "function renderAnalysisSummaryCard" in js
    assert "function renderAnalysisBlock" in js
    assert "Opportunity quality" in js
    assert "Evidence reliability" in js
    assert "Exposure level" in js
    assert "function renderDecisionTimeline" in js
    assert "allTraceDecisionsList" in js
    assert "function sanitizeNumericText" in js
    assert "preferInstrumentId" in js
    assert 'id="decision-brief-remove-candidate"' in html
    assert "Existing decisions, traces, and replay evidence will be preserved" in js
    assert "decision history preserved" in js
    assert ".analysis-depth-grid" in css
    assert ".analysis-overview-grid" in css
    assert ".analysis-detail-panel" in css
    assert ".analysis-component-meter" in css
    assert ".decision-history-timeline" in css
    assert "Re-validate before using the TradePlan" in js
    assert "Restart ATHENA (Dock/athena-serve)" in js
    assert "decision-chart-entry-zone" in css
    assert "decision-chart-plan-line" in css
    assert "decision-chart-price-panel" in css
    assert "decision-chart-volume-panel" in css
    assert "decision-chart-price-marker-line" in css
    assert "decision-chart-price-marker-box" in css
    assert "decision-chart-shell" in css
    assert "width: 80vw" in css
    assert "height: 80vh" in css
    assert ".chart-modal-container .modal-body" in css
    assert "overflow: hidden" in css
    assert ".chart-modal-canvas .decision-chart-shell" in css
    assert "dashboard.css?v=9.125.0" in html
    assert "dashboard.js?v=9.125.0" in html
    assert 'id="advisor-pulse"' in html
    assert 'id="header-diagnostics-popover"' in html
    assert 'id="decision-actionability-banner"' in html
    assert "function setAdvisorPulse" in js
    assert "function renderDecisionActionability" in js
    assert "Plan expired · re-validate" in js
    assert "Re-validate before using entry/stop/target levels" in js
    assert ".advisor-pulse" in css
    assert ".diagnostics-popover" in css
    assert ".decision-actionability-banner.tone-danger" in css
    assert "function inferTradePlanFreshness" in js
    assert "TRADE_PLAN_FRESHNESS_WARN_FRACTION = 0.5" in js
    assert "TRADE_PLAN_FRESHNESS_STALE_FRACTION = 0.8" in js
    assert ".symbol-row-plan-status.tone-expired" in css
    assert ".quick-summary-plan-status.tone-expired" in css
    assert 'id="decisions-revalidate-visible-btn"' in html
    assert 'id="decisions-revalidate-status"' in html
    assert "QUICK_VISIBLE_REVALIDATE_LIMIT = 5" in js
    assert "QUICK_VISIBLE_REVALIDATE_COOLDOWN_MS = 60000" in js
    assert "function currentVisibleBoardSymbols" in js
    assert "decisionsCarouselContainer.getBoundingClientRect()" in js
    assert "row.getBoundingClientRect()" in js
    assert "rowRect.bottom > containerRect.top" in js
    assert "rowRect.top < containerRect.bottom" in js
    assert "row.offsetParent === null" in js
    assert "const symbols = onScreenSymbols.slice(0, QUICK_VISIBLE_REVALIDATE_LIMIT)" in js
    assert "first ${symbols.length} of ${onScreenSymbols.length} on-screen" in js
    assert "validateSymbolsNow(symbols" in js
    assert "refreshDecisions: true" in js
    assert "Validated${capCopy}" in js
    assert "cooling down 60s" in js
    assert "No on-screen current-board rows to re-validate" in js
    assert "function clearBoardRevalidateStatusAfterCooldown" in js
    assert "/cooling down|Retry visible refresh/i" in js
    assert 'setBoardRevalidateStatus("", "neutral")' in js
    assert "function readableBoardRevalidateError" in js
    assert "function isKiteRateLimitError" in js
    assert "function syncBoardRevalidateCooldownButton" in js
    assert "function startBoardRevalidateCooldown" in js
    assert "boardRevalidateCooldownTimer" in js
    assert "setInterval(syncBoardRevalidateCooldownButton, 1000)" in js
    assert "clearInterval(boardRevalidateCooldownTimer)" in js
    assert "nextBoardRevalidateAllowedAt" in js
    assert "fa-hourglass-half" in js
    assert "Cooling down · retry in" in js
    assert "Kite is cooling down. Retry visible refresh in" in js
    assert "error.userMessage" in js
    assert "err.userMessage = message" in js
    assert "Kite rate limit hit. Wait about a minute" in js
    assert "Validation failed. Treat existing rows as stale until you retry" in js
    assert ".symbols-revalidate-status.tone-success" in css
    assert ".symbols-revalidate-status.tone-danger" in css
    assert "TOP_CURRENT_SETUPS_LIMIT = 10" in js
    assert "function isTopCurrentSetup" in js
    assert 'decisionListSectionType(d) === "TRADE"' in js
    assert "decisionHasCurrentActionableTradePlan(d, freshness)" in js
    assert 'status === "FRESH" || status === "AGING"' in js
    assert "function sortTopCurrentSetups" in js
    assert "decisionScoreValue(b) - decisionScoreValue(a)" in js
    assert "function decisionConfidenceValue" in js
    assert "function decisionRiskValue" in js
    assert "function decisionExpectedReturnPctValue" in js
    assert "function decisionRiskRewardValue" in js
    assert ".slice(0, TOP_CURRENT_SETUPS_LIMIT)" in js
    assert "Top Current Setups" in js
    assert "ranked review queue" in js
    assert "Current valid/aging TradePlans only" in js
    assert 'type === "TOP_CURRENT_SETUPS"' in js
    assert "rowToScroll?.scrollIntoView" in js
    assert "symbols-summary-help" in js
    assert "summaryEl.setAttribute(\"title\", details.join(\" \"))" in js
    assert ".top-current-setups-section" in css
    assert ".top-current-setups-head" in css
    assert ".top-current-setups-note" in css
    assert ".symbols-summary-help" in css
    assert 'id="intraday-sop-trigger"' in html
    assert 'id="intraday-sop-modal"' in html
    assert 'id="intraday-sop-close"' in html
    assert "Intraday operating guide" in html
    assert "ATHENA is advisory only." in html
    assert "It does not place orders, does not guarantee profit" in html
    assert "Before market opens" in html
    assert "Build the work queue" in html
    assert "Before entry" in html
    assert "If price does not enter" in html
    assert "After entry" in html
    assert "End of day" in html
    assert "Manual boundary:" in html
    assert "Do not chase price outside the entry zone" in html
    assert "Do not treat an intraday setup as an overnight hold" in html
    assert "const intradaySopModalEl" in js
    assert "intraday-sop-trigger" in js
    assert "intraday-sop-close" in js
    assert "openModal(intradaySopModalEl)" in js
    assert "closeModal(intradaySopModalEl)" in js
    assert 'closeModal(document.getElementById("intraday-sop-modal"))' in js
    assert ".intraday-sop-modal-container" in css
    assert ".intraday-sop-grid" in css
    assert ".intraday-sop-alert" in css
    assert ".intraday-sop-footer" in css
    assert 'id="decision-entry-readiness"' in html
    assert 'id="decision-entry-readiness-label"' in html
    assert "function entryReadinessView" in js
    assert "function renderEntryReadiness" in js
    assert "formatEntryZone(plan)" in js
    assert "decisionHasCurrentActionableTradePlan(decision, planFreshness)" in js
    assert "Entry ready" in js
    assert "Entry acceptable" in js
    assert "Wait for entry" in js
    assert "Chasing risk" in js
    assert "Avoid entry" in js
    assert "No current entry" in js
    assert "Waiting for quote" in js
    assert "const ENTRY_ACCEPTABLE_MIN_RR = 1.8" in js
    assert "const ENTRY_ACCEPTABLE_MAX_CHASE_PCT = 0.25" in js
    assert "function liveRewardRisk" in js
    assert "function priceHasInvalidatedEntry" in js
    assert "liveRr >= ENTRY_ACCEPTABLE_MIN_RR" in js
    assert "chasePct <= ENTRY_ACCEPTABLE_MAX_CHASE_PCT" in js
    assert "Confirm broker quote before manual action" in js
    assert "Avoid chasing unless ATHENA re-validates" in js
    assert "renderEntryReadiness();" in js
    assert 'if (typeof renderEntryReadiness === "function") renderEntryReadiness(activePlanFreshness);' in js
    assert ".decision-entry-readiness" in css
    assert ".decision-entry-readiness.tone-good" in css
    assert ".decision-entry-readiness.tone-warning" in css
    assert ".decision-entry-readiness.tone-danger" in css
    assert 'id="validation-report-modal"' in html
    assert 'id="validation-report-title"' in html
    assert 'id="validation-report-body"' in html
    assert 'id="validation-report-close"' in html
    assert "function renderValidationReport" in js
    assert "function validationReportOutcome" in js
    assert "function latestDecisionForSymbol" in js
    assert "function validationReportMetricValue" in js
    assert "showReport = false" in js
    assert "if (showReport && list.length === 1)" in js
    assert "saved-symbol-validate-btn" in js
    assert "saved-symbol-action-btn" in js
    assert "aria-label=\"Validate ${s.symbol}\"" in js
    assert "showReport: true" in js
    assert "Decision-detail revalidation" not in js
    assert "validateSymbolsNow([bareSymbol], { button: event.currentTarget, refreshDecisions: true });" in js
    assert "Open decision" in js
    assert "function openDecisionForSymbol" in js
    assert "strictPreferInstrumentId: true" in js
    assert 'switchTab("decisions", { skipLoad: true })' in js
    assert "return applyDecisionsView(options);" in js
    strict_symbol_start = js.find("if (preferInstrumentId && options.strictPreferInstrumentId)")
    active_decision_start = js.find("if (!next && preferDecisionId)")
    assert strict_symbol_start != -1
    assert active_decision_start != -1
    assert strict_symbol_start < active_decision_start
    assert "reportDecisionOpenable" in js
    assert 'currentDecision && outcome.label !== "Excluded"' in js
    assert ".inspect-btn:disabled" in css
    assert "Inspect trace" in js
    assert "Save symbol" in js
    assert "Remove saved" in js
    assert ".validation-report-modal-container" in css
    assert ".validation-report-hero.tone-good" in css
    assert ".validation-report-metrics" in css
    assert ".validation-report-plan-metric" in css
    assert ".saved-symbol-action-btn" in css
    assert 'closeModal(document.getElementById("validation-report-modal"))' in js
    assert "/api/v1/dashboard/session-status" in js
    assert "state.marketSession" in js
    assert "function marketSessionPulse" in js
    market_pulse_start = js.find("function marketSessionPulse")
    market_pulse_end = js.find("\n    function ", market_pulse_start + 1)
    market_pulse_body = js[market_pulse_start:market_pulse_end]
    assert "session && session.is_market_open === true" in market_pulse_body
    assert "session && session.is_market_open === false" in market_pulse_body
    assert "Checking market hours" in market_pulse_body
    assert "Kite connected" in market_pulse_body
    update_market_pulse_start = js.find("function updateMarketPulse")
    update_market_pulse_end = js.find("\n    async function ", update_market_pulse_start + 1)
    update_market_pulse_body = js[update_market_pulse_start:update_market_pulse_end]
    assert "marketSessionPulse(state.marketSession)" in update_market_pulse_body
    assert 'state.kiteConnected ? "Market live · Kite connected"' not in update_market_pulse_body
    assert "Review mode · market closed" in js
    assert "Review the thesis only; confirm live quote and re-validate before entry" in js
    assert "function chartPlanLevelPct" in js
    assert "function chartPlanValidityLabel" in js
    assert "function refreshActiveDecisionChart" in js
    assert "refreshActiveDecisionChart();" in js
    assert "decision-chart-plan-strip" in js
    assert "decision-chart-plan-chip stop" in js
    assert "decision-chart-plan-chip target" in js
    assert "Plan expires in" in js
    assert "activeBriefQuote" in js
    assert "function activeQuoteForSeries" in js
    assert "${escapeDecisionHtml(markerLabel)} ${chartPriceLabel(markerPrice)} · Candle close" in js
    assert "Candle close ${chartPriceLabel(latestClose)}" in js
    assert "Marker color: quote above/below candle close" in html
    assert "Marker color: quote above/below candle close" in js
    assert ".decision-chart-plan-strip" in css
    assert ".decision-chart-plan-chip.stop" in css
    assert ".decision-chart-plan-chip.target" in css
    assert ".decision-chart-plan-chip.validity.expired" in css
    assert ".legend-price-marker" in css
    assert ".decision-chart-controls" in css
    assert ".decision-chart-control.active" in css
    assert ".decision-chart-session-separator" in css

    # M-D4 renders session/calendar, regime/market-health context, curated links, and export
    assert 'id="decision-context-lane"' in js
    assert 'id="decision-brief-export"' in html
    assert "function renderDecisionContext" in js
    assert "function loadDecisionContext" in js
    assert "function exportDecisionBrief" in js
    assert "/context" in js
    assert "DECISION_BRIEF" in js
    assert "No live news feed" in js
    assert "no AI-written commentary" in js
    assert "Not available yet — re-validate this decision to capture a regime assessment" in js
    assert ".decision-context-lane" in css
    assert ".context-chip" in css
    assert ".context-links-list" in css

    # Market Context redesign (owner screenshot review, DT-4 follow-up):
    # Session as a slim full-width bar instead of a card matching Regime/
    # Market Health's height (was leaving a large dead-space gap under a
    # near-empty Session card); Regime's 3 dimensions forced into one even
    # row instead of auto-fit wrapping 2+1; the redundant composite
    # explanation sentence (raw SNAKE_CASE repeat of the metric cards
    # above it) replaced by each metric's own real per-dimension evidence
    # text, shown as a title tooltip.
    assert "context-session-bar" in js
    assert ".context-session-bar" in css
    assert ".context-analytics-row" in css
    assert "context-metric-grid--cols-3" in js
    assert ".context-metric-grid--cols-3" in css
    assert "function evidenceExplanationByDimension" in js
    context_metric_card_start = js.find("function contextMetricCard")
    context_metric_card_end = js.find("\n    function ", context_metric_card_start + 1)
    assert "explanation" in js[context_metric_card_start:context_metric_card_end]
    render_context_start = js.find("function renderDecisionContext")
    render_context_end = js.find("\n    function ", render_context_start + 1)
    render_context_body = js[render_context_start:render_context_end]
    assert "regimeEvidence" in render_context_body
    assert "healthEvidence" in render_context_body
    assert "regime.explanation" not in render_context_body
    assert "mh.explanation" not in render_context_body

    # Decisions & Trace UI overhaul (owner-reported: overcrowded single scroll,
    # duplicate gate chips, DAG panel re-explaining what the brief already
    # shows). Reasoning Trace nodes now navigate to the matching brief tab
    # instead of duplicating its content in a side panel.
    assert "function showStageDetails" in js
    assert "function renderStageProvenance" in js
    assert "STAGE_ICONS" in js
    assert "STAGE_TAB_MAP" in js
    assert "function switchBriefTab" in js
    assert "activeBriefTab" in js
    # Bug fix: each brief tab now lands at the top instead of keeping
    # whatever scroll offset the previous tab happened to be at.
    switch_brief_tab_start = js.find("function switchBriefTab")
    switch_brief_tab_end = js.find("\n    function ", switch_brief_tab_start + 1)
    assert "decisionBriefScrollRegion || decisionBriefBody" in js[switch_brief_tab_start:switch_brief_tab_end]
    assert "scrollTarget.scrollTop = 0" in js[switch_brief_tab_start:switch_brief_tab_end]
    assert "opened automatically" in js
    assert "activeDepth" in js
    assert "activeContextData" in js
    assert "formatDecisionRatio" in js
    assert "function renderStageDetailBody" not in js
    assert "function renderContextStageBody" not in js
    assert "function renderTradePlanStageBody" not in js
    assert "function refreshSelectedStageDetail" not in js

    # Today's Decisions is grouped into outcome groups (Trade -> Watch ->
    # No trade -> everything else), always in that priority order regardless
    # of timestamp — never one flat chronological list. DT-1 (2026-07-27)
    # replaced the horizontal carousel presentation with a permanent left
    # symbols panel (see the symbols-panel assertions further below) — same
    # grouping/priority/render functions, just a vertical row instead of a
    # fixed-width horizontal card.
    assert 'id="decisions-carousel-groups"' in html
    assert "function renderDecisionCarousels" in js
    assert "function renderSymbolRow" in js
    assert "DECISION_CAROUSEL_SECTIONS" in js
    assert "function decisionTypePriority" in js
    assert "function decisionListSectionType" in js
    assert "function decisionListPriority" in js
    assert "function isCurrentDecisionListRow" in js
    assert "function decisionHasCurrentActionableTradePlan" in js
    assert "function decisionHasHistoricalTradePlan" in js
    assert "return !decisionHasHistoricalTradePlan(d);" in js
    assert "traceDecisionsList.filter(isCurrentDecisionListRow)" in js
    assert "isCurrentDecisionListRow(d) && dismissedDecisionSymbols.has" in js
    assert "expired historical TradePlans are hidden from this list" in js
    assert "currentPlanBlocked" in js
    assert "plan not current" in js
    assert "Do not use this historical TradePlan without re-validation" in js
    assert "regardless of timestamp" in js
    assert "linear-gradient(${section.wash}, ${section.wash}), rgba(15, 23, 42, 0.92)" in js
    assert ".decision-carousel-section" in css
    assert ".decision-carousel-head" in css
    assert "position: sticky" in css
    assert ".symbol-row" in css

    # Sticky cockpit header: live score/confidence/risk gauges + a five-tab
    # brief (Setup/Analysis/Context/Response/History) replacing one long
    # stacked scroll
    assert 'id="decision-brief-gauges"' in html
    assert 'id="gauge-score-value"' in html
    assert 'id="gauge-confidence-value"' in html
    assert 'id="gauge-risk-value"' in html
    assert 'data-brief-tab="setup"' in html
    assert 'data-brief-tab="analysis"' in html
    assert 'data-brief-tab="context"' in html
    assert 'data-brief-tab="response"' in html
    assert 'data-brief-tab="history"' in html
    assert "function renderCockpitGauges" in js
    assert "function resetCockpitGauges" in js
    assert ".decision-brief-gauges" in css
    assert ".brief-tab" in css
    assert ".tabpane" in css

    # UX-1: Hero Decision Card + Executive Summary + Decision Banner (owner
    # UX audit, 2026-07-26) — meaning over decimals (band words, not just
    # raw 0-100 numbers), a five-line plain-English summary composed
    # entirely from already-persisted engine explanations (never generated,
    # per ADR-005), and a recommendation banner reusing the existing
    # stance-buy/sell/hold/pass/wait palette
    assert 'id="gauge-score-band"' in html
    assert 'id="gauge-confidence-band"' in html
    assert 'id="gauge-risk-band"' in html
    assert 'id="hero-rr-value"' in html
    # DT-3 refinement: this container moved from a per-decision JS template
    # into static HTML inside the new executive-summary-modal (see below) —
    # renderExecutiveSummary() still targets the same id via getElementById,
    # it just no longer builds the wrapping <div> itself each render.
    assert 'id="decision-executive-summary"' in html
    assert "function qualityBand" in js
    assert "function riskBand" in js
    risk_band_start = js.find("function riskBand")
    risk_band_end = js.find("\n    function ", risk_band_start + 1)
    risk_band_body = js[risk_band_start:risk_band_end]
    assert "if (n < 40) return \"Low\";" in risk_band_body
    assert "if (n < 70) return \"Medium\";" in risk_band_body
    assert "function buildExecutiveSummaryLines" in js
    assert "function renderExecutiveSummary" in js
    assert "never generated" in js
    assert ".decision-banner" in css
    assert ".executive-summary-list" in css
    assert ".hero-metric-band" in css

    # UX-1 fix pass: gauges must never band a fabricated 0.0 as "Weak" when
    # the underlying block isn't OK; DAG auto-highlight must never force a
    # tab jump — only an explicit click may
    assert "function selectNode" in js
    assert "userInitiated" in js

    # UX-2: score/confidence/risk storytelling (owner UX audit) — star-rated
    # score contributors, a "why ATHENA trusts this" checklist, risk as a
    # categorized Low/Medium/High summary, a reassuring safety checklist
    # headline, and a Decision Quality Meter ladder — every band/percentage
    # derived from already-persisted dimension value/level/weight/weighted
    # fields, never a client-side re-derivation of config thresholds
    assert "function renderScoreContributors" in js
    assert "function renderConfidenceChecklist" in js
    assert "function renderRiskSummary" in js
    assert "function dimensionContributionPct" in js
    assert "function starRating" in js
    assert "CONFIDENCE_TRUST_LABELS" in js
    assert "QUALITY_LADDER_BANDS" in js
    assert "function qualityLadder" in js
    assert "safety-checklist-summary" in js
    assert ".score-contributor-row" in css
    assert ".trust-checklist-row" in css
    assert ".risk-summary-row" in css
    assert ".quality-ladder" in css
    assert ".safety-checklist-summary" in css
    # Owner-requested: Score has no backend `level`, so the header Score
    # gauge must color from the existing client-side score quality band
    # instead of falling through to muted grey forever.
    assert "function scoreBandColor" in js
    assert "view.tone === \"score\"" in js
    assert "band || qualityBand(view.data.value)" in js

    # UX-3: Trade Plan visual redesign (owner UX audit) — bigger numbers,
    # plus a genuinely new Expected Return % computed from the plan's own
    # persisted entry/target values, never fabricated
    assert "function computeExpectedReturnPct" in js
    assert "function computeTradePlanLevelPct" in js
    assert "function renderTradePlanLevel" in js
    assert "function formatTradePlanValidityPeriod" in js
    assert "function renderTradePlaybook" in js
    assert "function refreshTradePlaybook" in js
    assert "Trading steps" in js
    assert "Manual advisory workflow" in js
    assert "Enter only if the live price is inside the entry zone" in js
    assert "If price never reaches the entry zone before the plan expires" in js
    assert "do not treat this as an overnight hold" in js
    assert 'id="decision-brief-scroll-region"' in html
    header_start = html.find('class="card-header decision-brief-header"')
    header_end = html.find('id="decision-brief-scroll-region"')
    scroll_region_end = html.find('id="decision-brief-body"')
    assert header_start != -1
    assert header_end != -1
    assert header_start < header_end < scroll_region_end
    assert "const decisionBriefScrollRegion = document.getElementById(\"decision-brief-scroll-region\")" in js
    assert "function resetDecisionBriefScroll" in js
    assert "function updateDecisionBriefHeaderDensity" not in js
    assert "decisionBriefBody?.addEventListener(\"scroll\", updateDecisionBriefHeaderDensity" not in js
    assert "refreshTradePlaybook(activePlanFreshness)" in js
    render_brief_start = js.find("function renderDecisionBrief(decision)")
    render_brief_end = js.find("\n    // ", render_brief_start + 1)
    render_brief_body = js[render_brief_start:render_brief_end]
    trade_plan_idx = render_brief_body.find("renderTradePlan")
    chart_idx = render_brief_body.find("decision-chart-section")
    playbook_idx = render_brief_body.find("renderTradePlaybook")
    portfolio_idx = render_brief_body.find("decision-portfolio-impact-section")
    eligibility_idx = render_brief_body.find("decision-eligibility-depth")
    assert -1 not in {playbook_idx, trade_plan_idx, chart_idx, portfolio_idx, eligibility_idx}
    assert trade_plan_idx < chart_idx < playbook_idx < portfolio_idx < eligibility_idx
    assert "Valid for" in js
    assert "trade-plan-validity-window" in js
    assert "trade-plan-level-delta ${tone}" in js
    assert "renderTradePlanLevel(plan.stop_loss, stopDeltaPct, \"stop\")" in js
    assert "computeTradePlanLevelPct(plan, target, direction)" in js
    assert "\"target\"" in js
    assert ".trade-plan-hero-grid" in css
    assert ".trade-plan-hero-value" in css
    assert ".trade-plan-validity-window" in css
    assert ".trade-plan-level-delta.stop" in css
    assert ".decision-brief-scroll-region" in css
    assert "order: 1" in css[css.find(".decision-brief-tabstrip {"):css.find("\n}", css.find(".decision-brief-tabstrip {"))]
    assert "order: 2" in css[css.find(".decision-actionability-banner {"):css.find("\n}", css.find(".decision-actionability-banner {"))]
    assert "order: 3" in css[css.find(".decision-brief-body {"):css.find("\n}", css.find(".decision-brief-body {"))]
    assert "order: 5" in css[css.find(".decision-brief-gauges {"):css.find("\n}", css.find(".decision-brief-gauges {"))]
    tabstrip_start = css.find(".decision-brief-tabstrip {")
    tabstrip_end = css.find("\n}", tabstrip_start)
    tabstrip_css = css[tabstrip_start:tabstrip_end]
    assert "position: sticky" not in tabstrip_css
    assert "flex: 0 0 auto" in tabstrip_css
    assert "min-height: 38px" in tabstrip_css
    assert "resetDecisionBriefScroll();" in render_brief_body
    assert ".decision-brief-header.is-compact" not in css
    assert ".trade-plan-level-delta.target" in css

    # UX-3b: chart ATR/moving-average/volume overlay — plotted from the
    # candle-level atr/moving_average fields the API now serves, honestly
    # None during warmup, never interpolated or invented
    assert "Moving average" in js
    assert "ATR band" in js
    assert "decision-chart-ma-line" in js
    assert "decision-chart-atr-band" in js
    assert "decision-chart-volume-bar" in js
    assert "decisionChartControllers" in js
    assert "chartControllerFor" in js
    assert ".decision-chart-ma-line" in css
    assert ".decision-chart-atr-band" in css
    assert ".decision-chart-volume-bar" in css

    # UX-4: tab renaming, progressive disclosure, Market Context cards
    # (owner UX audit) — engineering tab names replaced with trader-facing
    # ones (internal data-brief-tab keys unchanged so nothing else breaks),
    # the Analysis component breakdown is a second click away from the
    # overview, and regime/market-health render as labeled metric cards
    # instead of a flat row of chips
    assert ">Trade Plan</span>" in html
    assert ">Market Context</span>" in html
    # DT-3 split the old "Decision History" tab into Response (Journal/
    # Outcome only) + History (Timeline + Similar past setups).
    assert ">Response</span>" in html
    assert ">History</span>" in html
    assert 'data-brief-tab="setup"' in html
    assert 'data-brief-tab="context"' in html
    assert 'data-brief-tab="response"' in html
    assert 'data-brief-tab="history"' in html
    assert "function contextMetricCard" in js
    assert "function regimeLabelCategory" in js
    assert "View detailed breakdown" in js
    assert ".analysis-detail-toggle" in css
    assert ".context-metric-grid" in css
    assert ".context-metric-value" in css

    # Bug fix: RegimeLabel/MarketHealthLabel values are DESCRIPTOR_DIMENSION
    # (e.g. BULL_TREND, HEALTHY_MOMENTUM) — an end-anchored regex assuming
    # the descriptor was a suffix silently matched none of the real enum
    # values, always falling through to neutral instead of good/bad.
    context_chip_tone_start = js.find("function contextChipTone")
    context_chip_tone_end = js.find("\n    function ", context_chip_tone_start + 1)
    context_chip_tone_body = js[context_chip_tone_start:context_chip_tone_end]
    assert "(BULL|STRONG|HEALTHY|CALM)$" not in context_chip_tone_body
    assert "BULL|STRONG|HEALTHY|CALM" in context_chip_tone_body

    # UX-5: Reasoning Trace redesign (owner UX audit #14/#19) — DAG nodes
    # show each stage's own real computed state (e.g. "Bullish", "BUY",
    # "Authorized") instead of the generic lifecycle badge once that
    # stage's data has loaded, falling back to the lifecycle status when
    # no mapping applies.
    assert "function stageMeaning" in js
    assert "function dagStatusBadgeHtml" in js
    assert "function refreshDagNodeMeanings" in js
    assert ".dag-node-status.meaning-good" in css
    assert ".dag-node-status.meaning-bad" in css
    assert ".dag-node-status.meaning-warn" in css
    assert ".dag-node-status.meaning-neutral" in css
    assert "prefers-reduced-motion" in css

    # UX-7: design tokens + accessibility polish pass. Spacing/typography/
    # elevation/color tokens were added by naming every distinct value
    # already in use (verified separately via a resolved-value diff against
    # the pre-refactor stylesheet — zero visual drift) so this only checks
    # the tokens and their consuming rules exist, not exhaustive coverage.
    assert "--space-8" in css
    assert "--space-24" in css
    assert "--text-0-85" in css
    assert "--text-0-5625" in css  # former bare 9px, folded into the rem scale
    assert "--shadow-md" in css
    assert "--ring-accent" in css
    assert "--glow-accent-md" in css
    assert "--tone-good-text" in css
    assert "--tone-bad-solid" in css
    assert "--tone-cyan-dot" in css
    assert "var(--space-8)" in css
    assert "var(--text-0-85)" in css
    assert "var(--shadow-md)" in css or "var(--shadow-lg)" in css
    assert "var(--tone-good-text)" in css

    # Accessibility: global keyboard focus ring + reduced-motion coverage
    # dashboard-wide; aria-labels on icon-only header buttons that only had
    # a `title` (not reliably exposed as an accessible name); keyboard-
    # operable "Today's Decisions" cards (previously click-only,
    # unreachable by tab).
    assert ":focus-visible" in css
    assert "prefers-reduced-motion: reduce" in css
    assert 'id="logout-btn"' in html
    assert 'aria-label="Log out"' in html
    assert 'aria-label="Force refresh"' in html
    assert 'aria-label="Refresh backup list"' in html
    assert 'row.setAttribute("tabindex", "0")' in js
    assert 'row.setAttribute("role", "button")' in js

    # UX-8: copy pass — raw ALL_CAPS enums (TRADE/WATCH/NO_TRADE/
    # INSUFFICIENT_DATA, INCLUDED/EXCLUDED/UNKNOWN) no longer leak into
    # sentences/chips next to the already-friendly stance vocabulary; dense
    # engineering paragraphs ("persisted"/"config thresholds"/"ingestion"/
    # "generated rationale"/the internal "AI Playbook Diagnostics" module
    # name/"deterministic nearest-neighbor... fingerprint") were rewritten
    # in plain English; the market-health block gained the same real,
    # already-persisted `explanation` sentence the regime block already
    # showed (parity fix, not new data); the hero "Composite score" label
    # now reads "Score", matching the app's own established convention.
    assert "function friendlyEligibilityLabel" in js
    # decisionTypeBadge() (the type-chip UX-8 fix this originally locked in)
    # was removed entirely in the later identity-row redesign below — the
    # BUY/TRADE chips it built are gone, replaced by the Recommendation tile.
    assert "No live news feed" in js
    assert "no AI-written commentary" in js
    assert "Exact math comparing this decision" in js
    assert "ATHENA's future tuning can ever" in js
    assert "The closest-matching past decisions" in js
    # mh.explanation (the market-health composite sentence UX-6 parity fix
    # originally locked in here) was later replaced entirely by per-dimension
    # evidence tooltips (see the Market Context redesign assertions above) —
    # the composite sentence just repeated the metric cards in raw SNAKE_CASE.
    assert ">Score</span>" in html
    assert "Composite score" not in html

    # UX-9a: quick actions (Open Chart, Compare, News) + Portfolio Impact.
    # Compare and Portfolio Impact are pure frontend derivations over
    # already-existing endpoints (GET /decisions?instrument_id=, GET
    # /decisions/{id}/depth, GET /portfolio, GET /market/instruments/{id}/
    # candles) — no new backend routes. Open Chart reuses the exact same
    # renderCandlestickSvg used by the Trade Plan tab, just into a bigger
    # modal container. "Place Order" remains excluded, per the constitution.
    assert 'id="decision-brief-open-chart"' in html
    assert 'id="decision-brief-compare"' in html
    assert 'id="decision-brief-news"' in html
    assert 'id="chart-modal"' in html
    assert 'class="decision-chart-controls chart-modal-controls"' in html
    assert 'id="compare-modal"' in html
    assert "function openChartModal" in js
    assert "function openCompareModal" in js
    assert "function runSymbolCompare" in js
    assert "function fetchLatestDecisionForSymbol" in js
    assert "instrument_id: candidateId" in js
    # Fix pass: instrument_id is stored with an exchange prefix (e.g.
    # "NSE:HFCL") and the backend filter is an exact match, so a bare
    # symbol typed into Compare always found nothing — this locks in the
    # NSE:-prefix candidate probe (same pattern loadDecisionChart uses).
    assert "`NSE:${upper}`" in js
    # Fix pass: the compare input's uppercase look is CSS text-transform
    # only — the underlying .value keeps whatever case was typed, so a
    # lowercase/mixed-case symbol previously matched nothing against the
    # case-sensitive instrument_id filter. Locks in the .toUpperCase() fix.
    assert "const upper = String(symbol).toUpperCase();" in js
    assert "function loadPortfolioImpact" in js
    assert "function renderPortfolioImpact" in js
    assert "/api/v1/portfolio" in js
    assert "currently own any shares" in js
    assert 'hostId = "decision-chart-canvas"' in js
    assert ".chart-modal-container" in css
    assert ".compare-grid" in css
    assert ".portfolio-impact-grid" in css

    # Fix pass: analysisPercent/analysisMeterWidth/the completeness
    # calculation all did Number(value) without first checking for null —
    # and Number(null) is 0 in JavaScript, not NaN. A genuinely-absent
    # score/confidence/risk (status != "OK") silently rendered as a
    # plausible-looking "0.0/100" and "0% complete" instead of the honest
    # "—"/"Completeness unknown" — exactly the owner-reported confusion
    # ("zero values" that looked like real data, not an error state).
    assert "if (value === null || value === undefined) return \"—\";" in js
    assert "if (value === null || value === undefined) return 0;" in js
    assert "data.completeness === null || data.completeness === undefined" in js
    assert "Place Order" not in html
    assert "Place Order" not in js

    # Owner-requested "Clear all" for Decisions & Trace — CONFIRM-gated,
    # mirroring the existing Portfolio "Reset fills" pattern exactly (typed
    # token unlock, backup created server-side before deletion).
    assert 'id="decisions-clear-all-btn"' in html
    assert 'id="decisions-clear-all-modal"' in html
    assert 'id="decisions-clear-all-confirm"' in html
    assert "function syncDecisionsClearAllGate" in js
    assert "/api/v1/decisions/reset" in js
    assert 'confirmation: "CONFIRM"' in js

    # Fix pass: the DAG stage-detail panel's "Full detail lives in the X
    # tab" text was reconstructing the tab name via a raw capitalization
    # of the internal data-brief-tab key (still "setup"/"response" post
    # UX-4), so it read "Setup"/"Response" instead of the actual renamed
    # visible tab labels "Trade Plan"/"Decision History" — owner screenshot
    # caught it live. BRIEF_TAB_LABELS is the one place that mapping lives.
    assert "BRIEF_TAB_LABELS" in js
    assert '"Trade Plan"' in js
    # DT-3: BRIEF_TAB_LABELS relabeled response -> "Response" and added a
    # new "history" -> "History" entry (split out of the old single
    # "Decision History" tab) — no stage currently maps to either via
    # STAGE_TAB_MAP, so this is a pure label/structure change.
    assert '"Response"' in js
    assert '"History"' in js

    # UX-6: Sidebar summary + Historical Validation + Decision Timeline
    # narrative + Decision History polish (owner UX audit) — a sticky
    # quick-glance strip pinned to the Reasoning Trace panel; win-rate/
    # avg-return/avg-holding aggregate across analog matches (from the new
    # DecisionAnalogsDTO fields, real arithmetic, never fabricated); the
    # Decision Timeline reads as a narrative of stance/score deltas instead
    # of a flat list; Decision History shows a friendly accuracy label
    # wrapping the same real pnl sign.
    assert 'id="dag-quick-summary"' in html
    assert "function renderSidebarQuickSummary" in js
    assert ".dag-quick-summary" in css
    # DT-2 expanded this into a richer "Quick Summary" card (see the DT-2
    # assertions further below) — .dag-quick-metric (the old inline-chip
    # layout) no longer exists, replaced by .quick-summary-row.
    assert ".dag-quick-metric" not in css
    assert "function renderHistoricalValidation" in js
    assert "win_rate_pct" in js
    assert "avg_return_pct" in js
    assert "avg_holding_days" in js
    assert ".historical-validation" in css
    assert "function timelineNarrative" in js
    assert ".decision-timeline-narrative" in css
    assert "function decisionAccuracyLabel" in js
    assert ".outcome-accuracy-badge" in css

    # TP-1: symbol revalidation belongs in Advisor Status, next to the reason
    # it is needed, not in the generic header action row.
    actionability_start = html.find('id="decision-actionability-banner"')
    actionability_end = html.find('id="decision-brief-tabstrip"', actionability_start)
    actionability_html = html[actionability_start:actionability_end]
    assert 'id="decision-brief-revalidate-header"' in actionability_html
    assert "Re-validate plan" in actionability_html
    assert 'id="decision-brief-revalidate"' not in js
    assert "function setHeaderRevalidateEnabled" in js
    assert ".decision-actionability-cta" in css
    assert ".btn-sm" in css
    assert 'status: "No current trade plan"' in js
    assert 'cta: "Re-check symbol"' in js
    assert ".decision-actionability-banner.tone-neutral" in css

    # Owner-reported: with no decision selected, Open Chart/Compare/the
    # "more" overflow toggle stayed clickable even though there was nothing
    # for them to act on. Disabled by default in static HTML (matches
    # Re-validate's own existing pattern) and toggled together via a new
    # setHeaderActionsEnabled(), called from both the empty-state render
    # (false) and a loaded decision (true).
    assert 'id="decision-brief-open-chart"' in html
    assert re.search(r'id="decision-brief-open-chart"[^>]*disabled', html)
    assert re.search(r'id="decision-brief-compare"[^>]*disabled', html)
    assert re.search(r'id="decision-brief-overflow-toggle"[^>]*disabled', html)
    assert "function setHeaderActionsEnabled" in js
    set_actions_start = js.find("function setHeaderActionsEnabled")
    set_actions_end = js.find("\n    function ", set_actions_start + 1)
    set_actions_body = js[set_actions_start:set_actions_end]
    assert "decisionBriefOpenChart.disabled" in set_actions_body
    assert "decisionBriefCompare.disabled" in set_actions_body
    assert "decisionBriefOverflowToggle.disabled" in set_actions_body
    render_empty_start = js.find("function renderDecisionBriefEmpty")
    render_empty_end = js.find("\n    function ", render_empty_start + 1)
    assert "setHeaderActionsEnabled(false)" in js[render_empty_start:render_empty_end]

    # Owner-requested (2026-07-29): "kill everything and restart fresh" — a
    # header button, confirmed first (window.confirm), POSTs
    # /api/v1/ops/restart, then polls /health until the relaunched process
    # answers before reloading.
    assert 'id="restart-server-trigger"' in html
    assert "restartServerTrigger" in js
    assert "/api/v1/ops/restart" in js
    assert "window.confirm(" in js
    assert "function awaitServerRestartThenReload" in js
    restart_handler_start = js.find('restartServerTrigger?.addEventListener("click"')
    restart_handler_end = js.find("\n    async function ", restart_handler_start + 1)
    restart_handler_body = js[restart_handler_start:restart_handler_end]
    assert "window.confirm(" in restart_handler_body
    assert "/api/v1/ops/restart" in restart_handler_body
    assert "awaitServerRestartThenReload()" in restart_handler_body

    # M-X0: owner response + realized outcome capture — closes the gap where
    # DecisionJournalEntry/TradeOutcome existed but were never wired to any action
    assert 'id="decision-journal-panel"' in js
    assert "function renderJournalPanel" in js
    assert "function loadJournalPanel" in js
    assert "function recordJournalEntry" in js
    assert "function recordTradeOutcomeNow" in js
    assert "function renderOutcomeForm" in js
    assert "function renderOutcomeResult" in js
    assert "/journal" in js
    assert "/outcome" in js
    assert "computed here" in js  # never client-entered pnl/adherence, per ADR-005
    assert ".decision-journal-panel" in css
    assert ".outcome-form" in css
    assert ".outcome-result" in css

    # M-X1: deterministic nearest-neighbor historical analog matcher
    assert 'id="decision-analogs-panel"' in js
    assert "function renderAnalogsPanel" in js
    assert "function loadDecisionAnalogs" in js
    assert "/analogs" in js
    assert "ANALOG_MAX_DISTANCE" in js
    assert "nothing generated" in js
    assert ".analog-row" in css
    assert ".analog-list" in css

    # DT-4: last-5-trades sparkline — built purely from each analog's own
    # already-fetched outcome_return_pct/outcome_closed_ts, no new fetch
    assert "function renderAnalogSparkline" in js
    assert "function analogSparklinePoints" in js
    assert "outcome_return_pct" in js
    assert "outcome_closed_ts" in js
    assert ".analog-sparkline" in css
    assert ".analog-sparkline-bar" in css
    sparkline_fn_start = js.find("function renderAnalogSparkline")
    sparkline_fn_end = js.find("\n    function ", sparkline_fn_start + 1)
    sparkline_fn_body = js[sparkline_fn_start:sparkline_fn_end]
    assert "analogSparklinePoints" in sparkline_fn_body
    assert "<svg" in sparkline_fn_body
    validation_fn_start = js.find("function renderHistoricalValidation")
    validation_fn_end = js.find("\n    function ", validation_fn_start + 1)
    assert "renderAnalogSparkline(data)" in js[validation_fn_start:validation_fn_end]

    # M-X2: exact quantified distance to the TRADE gate — arithmetic over
    # already-persisted score/confidence/risk values, never a recomputed decision
    assert 'id="decision-counterfactual-panel"' in js
    assert "function renderCounterfactualPanel" in js
    assert "function loadDecisionCounterfactual" in js
    assert "/counterfactual" in js
    assert ".decision-counterfactual-panel" in css
    assert ".counterfactual-row" in css

    # M-X3: deterministic decay clock for TradePlan validity-window staleness
    assert 'id="trade-plan-freshness-badge"' in js
    assert "function renderPlanFreshnessBadge" in js
    assert "function formatTradePlanFreshnessBadge" in js
    assert "function formatTradePlanRelativeDuration" in js
    assert "expires in" in js
    assert "expired ${ago} ago" in js
    actionability_fn_start = js.find("function actionabilityStatusFromPlan")
    actionability_fn_end = js.find("\n    function ", actionability_fn_start + 1)
    actionability_fn_body = js[actionability_fn_start:actionability_fn_end]
    expired_branch_start = actionability_fn_body.find('if (status === "EXPIRED"')
    stale_branch_start = actionability_fn_body.find('if (status === "STALE"', expired_branch_start)
    expired_branch = actionability_fn_body[expired_branch_start:stale_branch_start]
    assert "expiredLabel" in expired_branch
    assert "freshness.valid_until" in actionability_fn_body
    assert "freshness.as_of" in actionability_fn_body
    assert "remainingLabel" not in expired_branch
    assert "decayed" not in js
    assert "function loadDecisionPlanFreshness" in js
    assert "/plan-freshness" in js
    assert ".plan-freshness-badge" in css
    assert "text-transform: none" in css

    # Operations console (P9.7) is live — warnings feed + backup panel, not a fake loader
    assert 'id="ops-warnings-feed"' in html
    assert 'id="ops-telemetry-chart"' in html
    assert 'id="ops-backups-body"' in html
    assert "Loading platform telemetry, logs, and triggers..." not in html
    assert "loadOperationsWorkspace" in js
    assert "startOpsStream" in js

    # Owner-requested full-viewport progress overlay during validate. Close
    # hides progress only; it does not cancel the backend validation once
    # started. Centralized inside validateSymbolsNow so all callers get the
    # same readable symbol summary, elapsed timer, and close behavior.
    assert 'id="validate-overlay"' in html
    assert 'id="validate-overlay-close"' in html
    assert 'id="validate-overlay-symbols"' in html
    assert 'id="validate-overlay-timer"' in html
    assert 'id="validate-overlay-detail"' in html
    assert 'role="alertdialog"' in html
    assert "const validateOverlayTimer" in js
    assert "const validateOverlayClose" in js
    assert "function formatValidationSymbolSummary" in js
    assert "+${list.length - limit} more" in js
    assert "function updateValidateOverlayTimer" in js
    assert "Elapsed ${elapsedSeconds}s" in js
    assert "setInterval(updateValidateOverlayTimer, 1000)" in js
    assert "clearInterval(validateOverlayTimerId)" in js
    assert "function showValidateOverlay" in js
    assert "function hideValidateOverlay" in js
    assert "validateOverlayClose?.addEventListener" in js
    assert "Validation continues in the background" in js
    assert "showValidateOverlay(list);" in js
    assert "hideValidateOverlay();" in js
    assert "Validating ${formatValidationSymbolSummary(list)}" in js
    assert "function latestValidationExclusion" in js
    assert "latest revalidation excluded it; no current TradePlan" in js
    assert "no current plan" in js
    assert ".validate-overlay" in css
    assert ".validate-overlay-panel" in css
    assert "max-height: calc(100vh - 64px)" in css
    assert ".validate-overlay-close" in css
    assert ".validate-overlay-timer" in css
    assert ".validate-overlay-symbols" in css
    assert "overflow-wrap: anywhere" in css
    assert "validate-spin" in css

    # UX-9b: owner-curated "Saved Symbols" personal watch list — deliberately
    # independent of the Stock List / owner-candidates validation list (no
    # pipeline seeding effect) and of the automated M4.3 watchlist package
    # (config-driven, no owner input). New backend domain (saved_symbols
    # table + SavedSymbolsService + /api/v1/saved-symbols endpoints), new
    # Market Intelligence card for add/list/remove.
    assert 'id="saved-symbol-input"' in html
    assert 'id="saved-symbol-add-btn"' in html
    assert 'id="saved-symbols-list"' in html
    assert 'id="saved-symbols-count"' in html
    assert 'id="saved-symbols-empty"' in html
    assert "function loadSavedSymbols" in js
    assert "function removeSavedSymbolNow" in js
    assert "/api/v1/saved-symbols" in js
    assert "saved-symbol-remove-btn" in js

    # Fix pass (owner screenshot, 2026-07-27): two bugs reported after the
    # dashboard.js concern split landed.
    #
    # (1) initializeRoute used to read window.location.pathname to decide
    # which tab to land on after login/bootstrap, so a stale URL left over
    # from a previous session (e.g. a session that expired while on
    # /dashboard/decisions) could reopen that same tab instead of Portfolio
    # Overview. First fix made every bootstrap always reset to Overview —
    # correct for a fresh login, but the owner then reported it also made a
    # *plain reload* of an already-active session jump back to Overview
    # every time ("very annoying"). Corrected: initializeRoute (used by
    # bootstrapSession's silent-restore paths — auth not required, or an
    # already-valid stored token) is back to being URL-preserving; only the
    # actual login form submit calls the new, separate resetToOverviewTab.
    assert "function initializeRoute" in js
    assert "function resetToOverviewTab" in js
    assert 'window.history.replaceState({ tabId: "overview" }, "", "/dashboard/overview");' in js
    reset_tab_fn_start = js.find("function resetToOverviewTab")
    reset_tab_fn_end = js.find("function ", reset_tab_fn_start + 1)
    assert 'switchTab("overview");' in js[reset_tab_fn_start:reset_tab_fn_end]
    # The critical distinction: initializeRoute's OWN body must not contain
    # the force-reset call — it must still parse window.location.pathname,
    # or a plain reload would regress right back to jumping to Overview.
    init_route_fn_start = js.find("function initializeRoute")
    init_route_fn_end = js.find("function ", init_route_fn_start + 1)
    init_route_body = js[init_route_fn_start:init_route_fn_end]
    assert "window.location.pathname.split" in init_route_body
    assert "replaceState" not in init_route_body
    # (2) After "Clear all" (and, more generally, whenever there's no active
    # decision), the main brief correctly went empty but the Reasoning Trace
    # sidebar kept showing the previously selected symbol's quick-summary
    # chips and DAG stage-detail card — neither is owned by the main brief
    # body, so both were silently left stale. renderDecisionBriefEmpty now
    # clears both authoritatively for every caller.
    assert "function renderDecisionBriefEmpty" in js
    assert "activeDecisionData = null;" in js
    assert "renderSidebarQuickSummary();" in js
    assert 'dagDetailsPanel.style.display = "none";' in js

    # DT-1 (owner UX workstation refactor, 2026-07-27): Decisions & Trace's
    # horizontal outcome carousels + toolbar-above-the-fold layout replaced
    # with a permanent 3-pane workstation — left symbols panel (search always
    # visible, collapsible outcome groups, no scrolling back to find the
    # list), center detail (immediately visible, no scroll-past-carousels),
    # right Reasoning Trace (unchanged in this milestone — its own redesign
    # is DT-4). Same underlying data/selection/filter logic throughout —
    # every id the JS already wired by id (briefing-search,
    # decisions-filter-stance/-type, decisions-sort, decisions-clear-all-btn,
    # decisions-summary-strip, decisions-carousel-groups) is unchanged, only
    # repositioned in the DOM.
    assert 'class="decisions-workstation"' in html
    assert 'class="symbols-panel"' in html
    assert 'id="symbols-filter-toggle"' in html
    assert 'id="symbols-filter-popover"' in html
    assert 'id="briefing-search"' in html
    assert 'id="briefing-search-clear"' in html
    assert 'id="decisions-clear-all-btn"' in html
    assert ".decisions-workstation" in css
    assert ".symbols-panel" in css
    assert ".symbols-filter-popover" in css
    assert ".symbols-search-clear" in css
    assert ".symbols-search-clear[hidden]" in css
    assert ".symbol-row.active" in css
    assert "function renderSymbolRow" in js
    assert "const briefingSearchClear = document.getElementById(\"briefing-search-clear\")" in js
    assert "function updateBriefingSearchClear" in js
    assert "function clearBriefingSearch" in js
    assert "briefingSearchClear?.addEventListener(\"click\", clearBriefingSearch)" in js

    # Fix pass (owner screenshot, 2026-07-27): section headers (Trade/Watch/
    # No trade/...) had no background — flush with the rows below them, no
    # differentiation between sections.
    #
    # Second fix pass (owner screenshot, same day): the first attempt reused
    # each section's raw alert-style dot color (--success/--warning) as a
    # color-mix() full-block background — but those hues are calibrated for
    # a tiny 8px dot, not a background: pure yellow (Watch) visually
    # overpowered green (Trade) at the identical opacity.
    #
    # Third fix pass (owner screenshot, same day): even hue-balanced, 3-4
    # stacked full-width solid blocks read as "too much color". Switched to
    # a thin left-border accent + a barely-there wash — same restrained
    # pattern the Recommendation tile/ATHENA Summary card use.
    assert "accent: \"rgba(34, 197, 94," in js  # Trade
    assert "accent: \"rgba(245, 158, 11," in js  # Watch
    assert "accent: \"rgba(148, 163, 184," in js  # No trade / Insufficient data
    assert "linear-gradient(${section.wash}, ${section.wash}), rgba(15, 23, 42, 0.92)" in js
    assert "border-left-color: ${section.accent}" in js
    assert "filter: brightness(1.25)" in css

    # Fourth fix pass (owner follow-up, same day): even the header's thin
    # accent, repeated per-row via decisionCardStanceColor()/--stance-color,
    # was "not feeling good" once the header already carried that same
    # color — redundant on top of it. decisionCardStanceColor() and the
    # --stance-color wiring were removed entirely (dead code, not just
    # hidden), so .symbol-row now carries no per-row color at all — the
    # section header is the only place that color lives. A subtle
    # border-bottom divider (reusing --border-color, not a new value)
    # replaces color as the way rows separate from each other.
    assert "decisionCardStanceColor" not in js
    assert "--stance-color" not in js
    assert ".symbol-row:not(:last-child)" in css
    assert "border-bottom-color: var(--border-color);" in css
    assert "symbolsFilterToggle" in js
    # Fix pass (live browser check, same milestone): the popover must be a
    # DOM child of .symbols-panel-header (its position:relative anchor), not
    # a sibling — a sibling popover anchors to some unrelated ancestor
    # further up the tree and renders far from the toggle button that opens
    # it. A plain "both strings appear" check can't tell nesting from
    # sibling placement, so walk the div depth between the two: if the
    # header's own <div> hasn't been closed by the time the popover's id
    # appears, the popover is still inside it.
    header_start = html.find('class="symbols-panel-header"')
    popover_start = html.find('id="symbols-filter-popover"')
    assert 0 <= header_start < popover_start, "symbols-panel-header must appear before the popover"
    between = html[header_start:popover_start]
    depth = between.count("<div") - between.count("</div>")
    assert depth >= 1, (
        "symbols-filter-popover must be nested inside .symbols-panel-header "
        f"(div depth between them was {depth}, expected >= 1)"
    )

    # Fix pass (owner screenshots, 2026-07-27): filter popover refinements.
    # (1) "Clear all" moved to its own separate, danger-styled icon button —
    # a destructive data wipe sitting inside a view-only filter popover read
    # as "clear the filters", not "wipe my decisions".
    # (2) each filter <label> used to inherit `flex: 1 1 100px` from the
    # shared .decisions-filter-label rule (written for the old horizontal
    # toolbar row) — inside this vertical popover that stretched every label
    # to fill the popover's height, producing large gaps. Pinned to `flex:
    # none` so each takes only its natural content height.
    # (3) an explicit Reset (view only, not data) and a close (X) button —
    # the filter icon toggle was previously the only way to close it.
    # (4) a backdrop dims and blocks clicks to the symbol list while the
    # popover is open — previously the list stayed fully visible/clickable
    # underneath it, with no visual differentiation.
    # (5) Reset also dismisses the popover (owner feedback) rather than
    # leaving it open after a completed reset action.
    assert 'id="decisions-clear-all-btn"' in html
    assert "symbols-icon-btn-danger" in html
    assert "flex: none;" in css
    assert 'id="symbols-filter-reset"' in html
    assert 'id="symbols-filter-close"' in html
    assert ".symbols-filter-reset-btn" in css
    assert "symbolsFilterReset" in js
    assert "symbolsFilterClose" in js
    assert 'id="symbols-filter-backdrop"' in html
    assert ".symbols-filter-backdrop" in css
    assert "symbolsFilterBackdrop" in js
    reset_fn_start = js.find("symbolsFilterReset?.addEventListener")
    reset_fn_end = js.find("});", reset_fn_start)
    assert "closeSymbolsFilterPopover();" in js[reset_fn_start:reset_fn_end]

    # Left-panel scroll position preserved across a rebuild; center panel
    # resets to top on every new selection; right panel untouched by either.
    assert "const previousScrollTop = decisionsCarouselContainer.scrollTop;" in js
    assert "decisionsCarouselContainer.scrollTop = previousScrollTop;" in js
    assert 'id="decisions-scroll-top"' in html
    assert ".symbols-scroll-top" in css
    assert ".symbols-scroll-top[hidden]" in css
    assert "function updateDecisionListScrollTopButton" in js
    assert "decisionsCarouselContainer.scrollTop < 180" in js
    assert "decisionsCarouselContainer.scrollTo({ top: 0, behavior: \"smooth\" });" in js
    assert "decisionsCarouselContainer?.addEventListener(\"scroll\", updateDecisionListScrollTopButton" in js
    assert "decisionsScrollTopBtn?.addEventListener(\"click\", scrollDecisionListToTop)" in js
    assert "resetDecisionBriefScroll();" in js

    # Owner-requested (2026-07-27): collapsible global sidebar — icon-only
    # when collapsed, .console-main (flex-grow: 1) reflows automatically via
    # the CSS width transition, no JS recalculation needed. Preference
    # persisted in localStorage across reloads.
    assert 'id="sidebar-collapse-toggle"' in html
    assert 'title="Portfolio Overview"' in html
    assert ".sidebar.collapsed" in css
    assert "transition: width var(--transition-speed) ease;" in css
    assert "function applySidebarCollapsed" in js
    assert "athena.sidebar-collapsed" in js

    # DT-2 (owner UX workstation refactor) — header market ticker: NIFTY 50 /
    # BANK NIFTY / INDIA VIX only, real level + real day-change % from a new
    # GET /api/v1/market/ticker (derives everything from already-persisted
    # Kite snapshot + daily candle data — no new provider, no new
    # calculations beyond simple arithmetic). Market breadth and an overall
    # health score are deliberately omitted — neither exists as real data
    # anywhere in ATHENA today (tracked as future scope, not fabricated).
    # MI-1 (Market Intelligence redesign) generalized this from a
    # Decisions-&-Trace-only component to a shared strip covering both tabs
    # (TICKER_TABS) — one component/endpoint, not two.
    assert 'id="header-market-ticker"' in html
    assert 'id="ticker-nifty-level"' in html
    assert 'id="ticker-banknifty-level"' in html
    assert 'id="ticker-vix-level"' in html
    assert ".header-market-ticker" in css
    assert "function loadMarketTicker" in js
    assert "/api/v1/market/ticker" in js
    assert 'TICKER_TABS = new Set(["decisions", "market"])' in js
    assert 'headerMarketTicker.hidden = tabId !== "decisions";' not in js
    assert "headerMarketTicker.hidden = !TICKER_TABS.has(tabId);" in js

    # Fix pass (owner, 2026-07-27): ticker previously only refreshed on
    # tab-switch/manual refresh, same as every other tab (no polling existed
    # anywhere in this dashboard) — owner asked for a timer. Scoped tightly
    # to the ticker only (not the decisions list/briefing, which would reset
    # scroll position/selection on every tick) and only while one of
    # TICKER_TABS is the active tab, mirroring the existing start/stop
    # pattern already used for the Operations tab's live stream (stopOpsStream).
    # IX-2 also refreshes persisted index context while Market Intelligence
    # is active, without reloading the validation workspace.
    assert "function startTickerRefresh" in js
    assert "function stopTickerRefresh" in js
    assert "TICKER_REFRESH_INTERVAL_MS = 60000" in js
    assert "tickerRefreshIntervalId = setInterval(() => {" in js
    assert "loadMarketTicker();" in js
    assert 'state.activeTab === "market"' in js
    assert "loadIndexLeadership();" in js
    switch_tab_start = js.find("function switchTab(tabId, options = {})")
    switch_tab_end = js.find("\n    function ", switch_tab_start + 1)
    switch_tab_body = js[switch_tab_start:switch_tab_end]
    assert "startTickerRefresh();" in switch_tab_body
    assert "stopTickerRefresh();" in switch_tab_body
    assert "TICKER_TABS.has(tabId)" in switch_tab_body
    assert "if (options.skipLoad)" in switch_tab_body
    assert "return loadTabData(tabId);" in switch_tab_body

    # MI-1: Market Intelligence's own tab also loads the shared ticker.
    load_tab_data_start = js.find("async function loadTabData(tabId)")
    load_tab_data_end = js.find("\n    async function ", load_tab_data_start + 1)
    load_tab_data_body = js[load_tab_data_start:load_tab_data_end]
    market_branch_start = load_tab_data_body.find('tabId === "market"')
    market_branch_end = load_tab_data_body.find("} else if", market_branch_start)
    market_branch_body = load_tab_data_body[market_branch_start:market_branch_end]
    assert "loadMarketIntelligence();" in market_branch_body
    assert "loadMarketTicker();" in market_branch_body

    # MI-1 (Market Intelligence redesign): Trading Calendar relocated out of
    # the primary 3-column grid (now 2 columns) into a collapsed-by-default
    # <details> panel — it previously occupied the largest area on the page
    # for one of the lowest-value sections during live trading. Same ids
    # (calendar-month-year/calendar-grid-container/upcoming-events-container)
    # so renderCalendar()/renderUpcomingEvents() are untouched.
    # MI-1 relocated the calendar; MI-5 reshaped the workstation into
    # summary + main + right rail (mock-aligned), so the grid is no longer
    # a flat 1fr 1fr pair of equal columns.
    assert '<details class="card market-calendar-details">' in html
    assert 'id="calendar-month-year"' in html
    assert 'id="calendar-grid-container"' in html
    assert 'id="upcoming-events-container"' in html
    assert ".market-calendar-details" in css
    assert ".market-calendar-summary" in css
    assert "grid-template-areas:" in css
    assert '"summary rail"' in css
    assert '"main rail"' in css
    assert "minmax(0, 1fr) 280px" in css

    # MH-3 refined Market Summary: mock-aligned 8-cell hero. Every visual uses
    # summary API values or categorical labels; no display-only market score.
    assert "<h3>Market Summary</h3>" in html
    assert "Volatility Regime & Health" not in html
    assert 'id="market-summary-asof"' in html
    assert 'class="card-body market-summary-body" aria-live="polite"' in html
    assert 'id="regime-trend-badge" class="market-hero-value"' in html
    assert "function formatVolatilityLabel" not in js
    assert '"regime-badge' not in js
    assert ".regime-badge" not in css
    assert ".health-bar-fill" not in css
    assert ".health-gauge-container" not in css
    assert ".market-hero-metric" in css
    assert "function conciseMarketLabel" in js
    assert "function renderCategoricalIndicator" in js
    assert 'replace(/_?VOLATILITY/g, "")' in js
    assert 'gap: value === "NO_GAP" ? "NONE" : value.replace(/^GAP_?/, "")' in js
    assert 'replace(/_?MOMENTUM/g, "")' in js
    assert 'replace(/_?TREND_QUALITY/g, "")' in js
    load_mi_start = js.find("async function loadMarketIntelligence")
    load_mi_end = js.find("\n    async function ", load_mi_start + 1)
    load_mi_body = js[load_mi_start:load_mi_end]
    assert "/api/v1/market/summary" in load_mi_body
    assert "renderMarketSummaryHero(" in load_mi_body
    assert "repeat(8, minmax(118px, 1fr))" in css
    assert "grid-column: 1 / -1" in css

    # IX-2: compact persisted index leadership stays inside the Market Summary
    # card; complete grouped observations open outside workspace flow.
    assert 'id="index-leadership-title"' in html
    assert 'id="index-leadership-broad"' in html
    assert 'id="index-leadership-sector"' in html
    assert 'id="index-leadership-open"' in html
    assert 'id="index-leadership-modal"' in html
    assert 'id="index-leadership-retry"' in html
    assert 'id="index-broad-market-grid"' in html
    assert 'id="index-sector-grid"' in html
    assert "Market context only. Index movement is not an ATHENA trade signal." in html
    assert "function renderIndexLeadership" in js
    assert "function loadIndexLeadership" in js
    assert "Promise.allSettled" in js
    assert 'renderIndexLeadership(null, state.marketSession, { loadFailed: true });' in js
    assert '{ loadFailed: !payload || !Array.isArray(payload.indices) }' in js
    assert 'title.textContent = loadFailed' in js
    assert "levels available" in js
    assert "indexLeadershipRetry.innerHTML = loadFailed" in js
    assert "Index data unavailable" in js
    assert "Index service unavailable" in js
    assert "/api/v1/market/index-intelligence" in js
    assert "/api/v1/dashboard/session-status" in js
    assert 'if (value == null || value === "") return null;' in js
    assert "Change unavailable" in js
    assert "Leading sector" in js
    assert "Lagging sector" in js
    assert 'state.activeTab === "market"' in js
    assert ".index-leadership-ribbon" in css
    assert "container-type: inline-size" in css
    assert "@container (max-width: 900px)" in css
    assert ".index-leadership-modal-container" in css
    assert "overflow-x: auto" not in css[
        css.find(".index-leadership-ribbon"):css.find(".index-leadership-modal-container")
    ]

    # Real indicators: score/breadth rings, NIFTY/VIX sparklines, categorical
    # bars/dots, gap direction, and read-only attribution footer.
    assert 'id="market-health-score-ring"' in html
    assert 'id="market-health-score-value"' in html
    assert 'id="market-breadth-ring"' in html
    assert 'id="market-breadth-pct"' in html
    assert 'id="market-breadth-counts"' in html
    assert 'id="market-sparkline-nifty"' in html
    assert 'id="market-sparkline-vix"' in html
    assert 'id="market-gap-indicator"' in html
    assert 'id="market-momentum-indicator"' in html
    assert 'id="market-trend-quality-indicator"' in html
    assert 'id="market-volatility-quality-indicator"' in html
    assert '<div class="regime-explanation">' in html
    assert "fa-chevron-down" not in html[html.find('<div class="regime-explanation">'):html.find('<div class="regime-explanation">') + 300]
    assert "countsEl.hidden = true" in js
    assert "function renderMarketHealthScore" in js
    assert "function renderUniverseBreadth" in js
    assert "function renderMarketSparklines" in js
    assert "function renderMarketSummaryHero" in js
    assert ".market-ring" in css
    assert ".market-mini-sparkline" in css
    assert ".market-dot-indicator" in css
    assert ".market-bar-indicator" in css
    assert ".market-health-score-value" in css
    assert "Universe breadth" in js
    # Never invent a display number client-side.
    assert "84/100" not in js
    assert 'regime.trend || "TREND_UNKNOWN"' in js
    assert 'regime.volatility || "VOLATILITY_UNKNOWN"' in js
    assert 'regime.gap || "GAP_UNKNOWN"' in js
    # MI-3 (Market Intelligence redesign): Today's Validation text strip
    # replaced with a typed Validation Pipeline funnel (Universe→Eligible→
    # Filtered→Watch→Trade) backed by GET /api/v1/pipelines/validation-funnel.
    # Filtered is server-side Eligible−Watch−Trade arithmetic; AW-3 turns View
    # Details into a daily-use workbench over the same existing data.
    assert "Validation Pipeline <span" in html
    assert "(Today)</span>" in html
    assert "Today's Validation" not in html
    assert 'id="validation-funnel"' in html
    assert 'id="validation-funnel-asof"' in html
    assert 'id="validation-funnel-details-btn"' in html
    assert 'id="validation-funnel-modal"' in html
    assert 'id="validation-workbench-summary"' in html
    assert "validation-workbench-summary-action" in html
    assert 'id="validation-workbench-overview"' in html
    assert 'id="validation-workbench-next-action"' in html
    assert 'id="validation-blockers-list"' in html
    assert 'id="validation-runs-list"' in html
    assert 'data-validation-workbench-tab="blockers"' in html
    assert 'data-validation-workbench-pane="symbols"' in html
    assert 'id="validation-results-outcome-filter"' in html
    assert 'id="validation-results-plan-filter"' in html
    assert 'id="validation-results-sort"' in html
    assert 'id="validation-results-count"' in html
    assert 'id="validation-results-busy"' in html
    assert 'id="validation-results-reset"' in html
    assert 'id="validation-summary-strip"' not in html
    assert "function renderValidationFunnel" in js
    assert "function renderValidationWorkbench" in js
    assert "function validationTopBlockers" in js
    assert "function validationNextAction" in js
    assert "function validationShortBlockerLabel" in js
    assert "/api/v1/pipelines/validation-funnel" in js
    assert "validation-funnel-stage" in js
    assert "validation-funnel-stage-icon" in js
    assert "Last Updated:" in js
    assert ".validation-funnel" in css
    assert ".validation-funnel-stage.is-trade" in css
    assert ".validation-workbench-summary" in css
    assert ".validation-workbench-summary-action" in css
    assert "grid-column: 1 / -1" in css
    assert "white-space: normal" in css
    assert ".validation-workbench-tabs" in css
    assert ".validation-results-toolbar" in css
    assert ".validation-results-select" in css
    assert ".validation-results-count" in css
    assert ".validation-results-busy" in css
    assert ".validation-results-list.is-filtering" in css
    assert ".validation-results-reset" in css
    assert ".validation-blocker-row" in css
    assert ".validation-run-row.is-failed" in css
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in css
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in css
    assert "View Details" in html
    assert "openModal(funnelDetailsModal)" in js
    assert 'setValidationWorkbenchTab("overview")' in js
    assert "body.scrollTop = 0" in js
    assert "renderValidationWorkbench({" in js
    assert "validationMemberBlocker" in js
    assert "exclusion_reasons" in js
    assert "data-validation-workbench-pane" in js
    assert "renderValidationResults(universe, qualified, universeNote)" in js
    assert "function validationResultRows" in js
    assert "function validationResultOutcome" in js
    assert "function validationScoreFromExplanation" in js
    assert "function validationResultPlan" in js
    assert "function validationWorkbenchFilters" in js
    assert "function validationResultRowView" in js
    assert "function filteredValidationResultViews" in js
    assert "function renderCurrentValidationResults" in js
    assert "function setValidationResultsBusy" in js
    assert "function scheduleValidationResultsRender" in js
    assert "score-desc" in js
    assert "No validation results match these filters" in js
    assert "setValidationResultsBusy(true)" in js
    assert "setValidationResultsBusy(false)" in js
    assert "window.setTimeout" in js
    assert "validationResultsOutcomeFilter" in js
    assert "validationResultsPlanFilter" in js
    assert "validationResultsSort" in js
    assert "validationResultsReset" in js
    assert "function refreshDecisionCacheForValidationResults" in js
    assert "await refreshDecisionCacheForValidationResults();" in js
    assert "allTraceDecisionsList = raw;" in js
    assert "traceDecisionsList = latestDecisionPerInstrument(raw);" in js
    assert "validation-results-head" not in html
    assert "validation-results-list" in html
    assert "data-validation-result-symbol" in js
    assert "validation-result-summary" in js
    assert "validation-result-metric" in js
    assert "qualified-open-decision-btn" in js
    assert "qualified-save-btn" in js
    assert "qualified-trace-btn" in js
    assert "canOpen: Boolean(decision)" in js
    assert "Not on the current Decisions board" in js
    assert "openDecisionForSymbol(symbol)" in js
    assert "renderValidationResults(validationWorkbenchState.universe, validationWorkbenchState.qualified, validationWorkbenchState.universeNote)" in js
    assert ".validation-result-row" in css
    assert ".validation-result-main" in css
    assert ".validation-result-summary" in css
    assert ".validation-result-meta" in css
    assert ".validation-result-metric" in css
    assert ".validation-result-actions" in css
    assert ".validation-legacy-table" in css
    assert "width: min(1120px, 94vw)" in css
    assert "overflow-x: hidden" in css
    assert "overflow-wrap: anywhere" in css
    assert "Qualified Today" not in html
    assert "strictPreferInstrumentId" in js
    assert "No current decision" in js
    assert 'id="validation-funnel-details"' not in html
    load_mi_start = js.find("async function loadMarketIntelligence")
    load_mi_end = js.find("\n    async function ", load_mi_start + 1)
    load_mi_body = js[load_mi_start:load_mi_end]
    assert "renderValidationFunnel(" in load_mi_body
    assert "/api/v1/pipelines/validation-funnel" in load_mi_body
    # A scoped validate's run holds only its own symbol, so the details modal
    # merges the day's runs (newest verdict per symbol) instead of rendering the
    # newest run alone — same rule as the funnel counts.
    assert "if (sym in universe) continue;" in load_mi_body
    assert "dayKey(r.as_of) !== dayKey(leading.as_of)" in load_mi_body
    # Eligible/Excluded + Qualified live in the details modal (same ids).
    assert 'id="universe-list-body"' in html
    assert 'id="qualified-today-body"' in html
    modal_idx = html.find('id="validation-funnel-modal"')
    universe_idx = html.find('id="universe-list-body"')
    assert modal_idx != -1 and universe_idx != -1
    assert modal_idx < universe_idx
    assert 'class="card candidate-card market-stock-list-card market-universe-card"' in html
    assert "market-saved-symbols-card" in html
    assert "market-side-rail" in html
    assert "market-workstation-mi5" in html
    assert 'closeModal(document.getElementById("validation-funnel-modal"))' in js
    # Inspect Trace is reached only from inside the funnel details modal, and
    # all overlays otherwise share one z-index (later-in-DOM wins), so the
    # trace modal needs its own higher layer or it renders behind its parent.
    assert 'id="trace-modal" class="modal-overlay modal-stacked"' in html
    assert ".modal-overlay.modal-stacked" in css
    assert ".modal-overlay.modal-stacked.active" in js

    # MI-4: Stock List redesigned into Universe table — Sector from seed CSV
    # Industry (instruments.sector), Status/Eligibility from latest validation
    # members, Last Validated from decisions.ts.
    assert "<h3>Universe</h3>" in html
    assert "<h3>Stock List</h3>" not in html
    assert 'id="candidate-list-body"' in html
    assert 'id="universe-status-filter"' in html
    assert 'id="universe-sector-filter"' in html
    # Mock-faithful Universe chrome: title actions share one header row and
    # search/status/sector/add-and-validate share one toolbar row. The search
    # field doubles as the explicit add target, avoiding a redundant input row.
    assert 'id="candidate-symbol-input"' not in html
    toolbar = html[html.find('<div class="universe-table-toolbar">'):]
    toolbar = toolbar[:toolbar.find("</div>", toolbar.find("</select>")) + 500]
    assert toolbar.find('id="candidate-search-input"') < toolbar.find('id="universe-status-filter"')
    assert toolbar.find('id="universe-status-filter"') < toolbar.find('id="universe-sector-filter"')
    assert toolbar.find('id="universe-sector-filter"') < toolbar.find('id="candidate-add-btn"')
    assert "minmax(170px, 1.3fr)" in css
    assert ".market-universe-card > .candidate-card-header" in css
    assert "const candidateInput = candidateSearchInput;" in js
    assert "table-layout: fixed" in css
    assert "overflow-x: hidden" in css
    assert "function compactEligibilitySummary" in js
    assert "function compactUniverseTime" in js
    assert "eligibility_evidence" in js
    assert "function showEligibilityDetail" in js
    assert 'id="eligibility-detail-modal"' in html
    assert 'class="eligibility-metric-btn"' in js
    assert ".eligibility-rule-row" in css
    assert "candidate-save-toggle-btn" in js
    assert "function toggleSavedSymbolNow" in js
    assert 'class="${isSaved ? "fa-solid" : "fa-regular"} fa-star"' in js
    assert "universe-symbol-heading" in html
    assert "width: 28%" in css
    # The Inspect Trace modal must read persisted per-rule outcomes. It used to
    # infer them by searching each explanation for "(PASS)" — a marker only the
    # in-memory demo fixture writes — so every real rule rendered FAIL, even for
    # symbols that passed all of them.
    assert 'logLine.includes("(PASS)")' not in js
    assert "Eligibility validation check executed for" not in js
    assert "const evidence = Array.isArray(member.evidence) ? member.evidence : [];" in js
    # Symbols the exchange does not list get their own status, so they can be
    # spotted and removed instead of looking like never-validated symbols.
    assert '<option value="UNRESOLVED">Unresolved</option>' in html
    assert "symbol-status-badge.unresolved" in css
    assert "<th>Sector</th>" in html
    assert "<th>Eligibility</th>" in html
    assert "<th>Last Validated</th>" in html
    assert "function applyUniverseFilters" in js
    assert "populateUniverseSectorFilter" in js
    assert ".market-universe-table" in css
    assert "last_validated_ts" in js
    assert "eligibility_summary" in js

    # MI-5: Quick Actions + Recent Activity + Validate All + Saved Symbols
    # relocated out of the primary workstation column.
    assert 'id="mi-run-full-validation-btn"' in html
    assert "Run Full Validation" in html
    assert 'id="universe-validate-all-btn"' in html
    assert "Validate All" in html
    assert 'id="mi-refresh-market-btn"' in html
    assert "Refresh Market View" in html
    assert 'id="market-recent-activity"' in html
    assert "function startFullUniverseValidation" in js
    assert "function renderRecentActivity" in js
    assert "/api/v1/market/validate-all" in js
    assert ".mi-action-row" in css
    assert ".mi-action-icon-play" in css
    assert ".mi-primary-btn" in css
    assert ".market-recent-activity-list" in css
    assert "market-side-rail" in html
    assert "market-main-column" in html
    assert "market-main-split" in html
    assert "validation-funnel-vertical" in html
    assert "market-summary-band" in html
    assert "minmax(360px, 0.58fr) minmax(0, 1fr)" in css
    assert ".market-main-split .market-universe-scroll" in css
    assert "grid-template-columns: repeat(5, minmax(64px, 1fr))" in css
    # Utility rail order is Activity → Saved → Actions; Saved is not collapsed
    # under the calendar, and occasional actions receive the lowest priority.
    assert "market-saved-symbols-card" in html
    cal_idx = html.find('class="card market-calendar-details"')
    activity_idx = html.find("market-recent-activity-card")
    saved_idx = html.find("market-saved-symbols-card")
    actions_idx = html.find("market-quick-actions-card")
    assert saved_idx != -1 and cal_idx != -1 and saved_idx < cal_idx
    assert activity_idx < saved_idx < actions_idx

    # DT-2 — Quick Summary: the UX-6 sidebar strip (score/confidence/risk
    # only) expanded into a richer card (R:R Potential, Expected Return,
    # Win Rate/Avg Holding — all historical-analogs-labeled honestly) rather
    # than a second, separate "Quick Summary" section duplicating the same
    # score/confidence/risk (owner: "don't duplicate information
    # unnecessarily"). No new fetch — reuses activeDecisionData/activeDepth/
    # activeAnalogs already loaded for the brief.
    #
    # DT-2 refinement (owner reference mock): Quick Summary is its own
    # standalone card, not inline at the top of the Reasoning Trace card —
    # header markup (title + stance chip) lives in static HTML; JS only
    # toggles the card's visibility and the stance chip's text/class.
    assert 'id="quick-summary-card"' in html
    assert 'id="quick-summary-stance"' in html
    assert "quickSummaryCard" in js
    assert "quickSummaryStanceEl" in js
    assert ".quick-summary-card-header" in css
    assert "R:R Potential" in js
    assert "Expected Return" in js
    assert "Plan Status" in js
    assert "Win Rate (Historical)" in js
    assert "Holding Period (Historical)" in js
    assert ".quick-summary-row" in css
    # Locks in that Win Rate/Avg Holding actually refresh once analogs load
    # (nothing else re-rendered the sidebar for this data before).
    analogs_fn_start = js.find("async function loadDecisionAnalogs")
    analogs_fn_end = js.find("async function ", analogs_fn_start + 1)
    assert "renderSidebarQuickSummary();" in js[analogs_fn_start:analogs_fn_end]

    # Fix pass (owner reference-mock screenshot, 2026-07-27): Quick Summary
    # value formatting/coloring corrections — Score/Confidence as raw
    # numbers (not repeating the gauge chips' band words), Risk as
    # "band (value)" colored by band, R:R at one decimal matching the hero
    # gauge's own formatting, Expected Return colored by sign. All reuse the
    # exact same status/level/value already computed for the hero cockpit
    # gauges (analysisPresentation/riskBand) — never a second, client-
    # derived number.
    assert "escapeDecisionHtml(scoreView.valueLabel)}/100" in js
    assert "escapeDecisionHtml(confidenceView.valueLabel)}%" in js
    quick_summary_fn_start = js.find("function renderSidebarQuickSummary")
    quick_summary_fn_end = js.find("\n    function ", quick_summary_fn_start + 1)
    quick_summary_fn_body = js[quick_summary_fn_start:quick_summary_fn_end]
    assert "riskBand(riskView.data.value)" in quick_summary_fn_body
    assert "tone-good-text" in quick_summary_fn_body
    assert "tone-warn-text" in quick_summary_fn_body
    assert "tone-bad-text" in quick_summary_fn_body
    assert "rr.toFixed(1)" in quick_summary_fn_body
    assert "inferTradePlanFreshness(plan)" in quick_summary_fn_body
    assert "activePlanFreshness" in quick_summary_fn_body
    assert "quick-summary-plan-status" in quick_summary_fn_body
    freshness_fn_start = js.find("async function loadDecisionPlanFreshness")
    freshness_fn_end = js.find("\n    // ", freshness_fn_start + 1)
    assert "renderSidebarQuickSummary();" in js[freshness_fn_start:freshness_fn_end]

    # Owner follow-up (2026-07-27): "does ATHENA have a real Holding Period
    # (days)?" — checked, and each analog's own outcome_holding_days is
    # already computed for the avg; min/max across that same real list is
    # honest historical data, not a guess, and matches the reference mock's
    # field more closely than a single average did. Replaces the earlier
    # "Avg Holding (Historical)" row.
    assert "min_holding_days" in js
    assert "max_holding_days" in js
    assert "minHold === maxHold" in quick_summary_fn_body

    # DT-2 — hero header spacing/hierarchy polish (owner assignment: "large:
    # stock name... more whitespace instead of extra separators"). Same
    # elements, same data — only sizing/spacing/grouping changed.
    assert "var(--text-1-4)" in css
    assert "border-top: 1px solid var(--border-color);" in css
    # Fix pass (owner screenshot): 5 gauge tiles in a 4-column grid wrapped
    # Expected R:R alone onto row 2 with only 1/4 the row's width — "reward
    # per ₹1 risked" truncated with empty space right next to it. It's
    # always the last tile, so give it the whole row instead.
    assert ".decision-brief-gauges .brief-gauge:last-child" in css

    # DT-3 — tab restructuring: the old single "Decision History" tab (which
    # mixed logging a response with browsing history) split into Response
    # (Journal only) and History (Decision Timeline, moved out of the
    # always-visible hero, + Similar past setups, moved out of Response).
    # No content deleted or invented — same three sections, regrouped.
    assert '["setup", "analysis", "context", "response", "history"]' in js
    response_pane_start = js.find('data-brief-pane="response"')
    history_pane_start = js.find('data-brief-pane="history"')
    history_pane_end = js.find("decision-brief-footnote", history_pane_start)
    assert 0 <= response_pane_start < history_pane_start < history_pane_end
    response_pane_body = js[response_pane_start:history_pane_start]
    history_pane_body = js[history_pane_start:history_pane_end]
    assert "decision-journal-panel" in response_pane_body
    assert "decision-analogs-panel" not in response_pane_body
    assert "decision-history-timeline" in history_pane_body
    assert "decision-analogs-panel" in history_pane_body
    # Decision Timeline no longer renders on every tab via the hero — it's
    # gated behind selecting the History tab now (confirmed above: it only
    # appears inside history_pane_body).

    # Follow-up refinement (owner reference-mock screenshot): the always-
    # visible ".decision-brief-hero" wrapper (ATHENA Recommendation banner +
    # full bullet-point Executive Summary, both repeating on every tab) is
    # gone entirely — the per-decision body template now starts directly
    # with the first tabpane.
    render_fn_start = js.find("function renderDecisionBrief(decision)")
    render_fn_end = js.find("\n    function ", render_fn_start + 1)
    render_fn_body = js[render_fn_start:render_fn_end]
    assert 'class="decision-brief-hero"' not in render_fn_body
    assert 'class="decision-banner' not in render_fn_body

    # Recommendation merged into the gauges row as its own tile — stance
    # badge set synchronously (same stance already computed for the header
    # chip); qualifier band ("Strong Setup") reuses the Score tile's own
    # already-computed band via renderCockpitGauges, never a second word.
    assert 'id="gauge-recommendation-tile"' in html
    assert 'id="gauge-recommendation-stance"' in html
    assert 'id="gauge-recommendation-band"' in html
    assert "gaugeRecommendationStance.textContent = displayStance.label" in js
    assert "Not actionable" in js
    assert "Historical universe eligibility" in js
    assert "Historical BUY setup" in js
    cockpit_fn_start = js.find("function renderCockpitGauges(depth)")
    cockpit_fn_end = js.find("\n    function ", cockpit_fn_start + 1)
    cockpit_fn_body = js[cockpit_fn_start:cockpit_fn_end]
    assert "gauge-recommendation-band" in cockpit_fn_body
    assert "${band} Setup" in cockpit_fn_body
    assert "Plan not current" in cockpit_fn_body
    # Fix pass (owner screenshot): a small pill badge read as just another
    # gauge tile — the whole tile is now stance-tinted (same tone treatment
    # .decision-banner.stance-* already uses), not a plain dark tile with a
    # chip inside.
    assert 'gaugeRecommendationTile.className = `brief-gauge brief-gauge-recommendation ${displayStance.cls}`' in js
    assert ".brief-gauge-recommendation.stance-buy" in css
    assert ".brief-gauge-recommendation.stance-buy #gauge-recommendation-stance" in css

    # ATHENA Summary: the same real headline previously shown inline as the
    # "ATHENA Recommendation" banner (now redundant with the stance badge
    # above), collapsed behind "View Details" instead of always showing the
    # full bullet breakdown on every tab.
    assert 'id="decision-summary-card"' in html
    assert 'id="decision-summary-headline"' in html
    assert 'id="decision-summary-view-details"' in html
    assert "decisionSummaryHeadline.textContent = summary.headline" in js

    # View Details opens the SAME executive-summary-modal via the existing
    # openModal/closeModal pattern already used for Compare/Chart/Backtest —
    # no new modal architecture, and it's wired into closeAllModals()/Escape.
    assert 'id="executive-summary-modal"' in html
    assert 'openModal(executiveSummaryModalEl)' in js
    assert 'closeModal(document.getElementById("executive-summary-modal"))' in js

    # Future-implementation nav placeholders (no backing route yet) —
    # deliberately excluded from .nav-item so app-shell.js's click-wiring
    # never has to special-case them.
    assert 'class="nav-item-disabled"' in html
    assert "Reports &amp; Analytics" in html or "Reports & Analytics" in html
    assert ">Settings<" in html
    assert ".nav-item-disabled" in css

    # Owner reference-mock screenshot (2026-07-27): identity row redesign.
    # BUY/TRADE badges dropped (now redundant with the Recommendation tile);
    # star favorite toggle wired to the existing Saved Symbols endpoints
    # (Priority-2 — no new backend); real company name + "EXCHANGE: SYMBOL"
    # meta row; secondary action-bar buttons consolidated into a "more" menu.
    assert 'id="decision-brief-stance-chip"' not in html
    assert 'id="decision-brief-type-chip"' not in html
    assert 'id="decision-brief-favorite-toggle"' in html
    assert 'id="decision-brief-company-name"' in html
    assert 'id="decision-brief-meta-row"' in html
    assert 'id="decision-brief-exchange-symbol"' in html
    header_start = html.find('class="card-header decision-brief-header"')
    row1_start = html.find('class="decision-brief-header-row1"', header_start)
    identity_start = html.find('class="decision-brief-identity"', row1_start)
    identity_end = html.find('class="decision-brief-header-actions"', identity_start)
    row1_end = html.find('id="decision-brief-meta-row"', identity_end)
    identity_body = html[identity_start:identity_end]
    assert 'id="decision-brief-title"' in identity_body
    assert 'id="decision-brief-meta-row"' not in identity_body
    scroll_region_start = html.find('id="decision-brief-scroll-region"')
    meta_row_start = html.find('id="decision-brief-meta-row"')
    assert header_start < row1_start < identity_start < identity_end < row1_end
    assert identity_end < meta_row_start < scroll_region_start
    assert "function loadSavedSymbolsCache" in js
    assert "/api/v1/saved-symbols" in js
    render_fn_start2 = js.find("function renderDecisionBrief(decision)")
    render_fn_end2 = js.find("\n    function ", render_fn_start2 + 1)
    render_fn_body2 = js[render_fn_start2:render_fn_end2]
    assert "meta.instrument_name" in render_fn_body2
    assert "decisionBriefExchangeSymbol.textContent" in render_fn_body2
    assert "exchangePrefix || \"\"" in render_fn_body2
    assert "`${exchangePrefix}: ${symbol}`" not in render_fn_body2
    assert ".favorite-toggle-btn" in css
    assert ".is-saved" in css
    assert ".decision-brief-identity-copy" not in css
    identity_css_start = css.find(".decision-brief-identity {")
    identity_css_end = css.find("\n}", identity_css_start)
    identity_css = css[identity_css_start:identity_css_end]
    assert "flex: 0 1 auto" in identity_css
    symbol_css_start = css.find(".decision-brief-symbol-lg {")
    symbol_css_end = css.find("\n}", symbol_css_start)
    symbol_css = css[symbol_css_start:symbol_css_end]
    assert "max-width: clamp(160px, 22vw, 340px)" in symbol_css
    assert "max-width: 220px" not in symbol_css
    meta_css_start = css.find(".decision-brief-meta-row {")
    meta_css_end = css.find("\n}", meta_css_start)
    meta_css = css[meta_css_start:meta_css_end]
    assert "flex-wrap: wrap" in meta_css
    assert "width: 100%" in meta_css
    assert "padding-left: calc(28px + var(--space-10))" in meta_css
    assert ".decision-brief-meta-row[hidden]" in css
    company_css_start = css.find(".decision-brief-company-name {")
    company_css_end = css.find("\n}", company_css_start)
    company_css = css[company_css_start:company_css_end]
    assert "white-space: normal" in company_css
    assert "text-overflow: clip" in company_css

    # Overflow menu — same moved buttons (ids/classes/click handlers
    # unchanged), only their container changed; toggle/backdrop-click/
    # Escape follow the same pattern as the symbols filter popover.
    assert 'id="decision-brief-overflow-toggle"' in html
    assert 'id="decision-brief-overflow-menu"' in html
    assert 'id="decision-brief-dismiss"' in html
    assert 'id="decision-brief-remove-candidate"' in html
    assert 'id="decision-brief-export"' in html
    assert 'id="decision-brief-news"' in html
    assert "function closeOverflowMenu" in js
    assert ".decision-brief-overflow-menu" in css
    assert ".overflow-menu-item" in css

    # Owner screenshot follow-up (2026-07-27): Market Intelligence dropped
    # entirely (redundant with the sidebar nav item of the same name — no
    # button anywhere replaces it); Open Chart/Compare relocated as icon-
    # only buttons in the header. TP-1 later moved symbol Re-validate into
    # Advisor Status, so the header remains display/system actions only.
    assert 'id="decision-brief-actionbar"' not in html
    assert 'id="decision-brief-market"' not in html
    assert "function switchTab" in js  # still used pervasively elsewhere
    header_actions_start = html.find('class="decision-brief-header-actions"')
    header_actions_end = html.find('id="decision-brief-scroll-region"', header_actions_start)
    header_actions_body = html[header_actions_start:header_actions_end]
    assert 'id="decision-brief-open-chart"' in header_actions_body
    assert 'id="decision-brief-compare"' in header_actions_body
    assert 'id="decision-brief-revalidate-header"' not in header_actions_body
    assert ">Open Chart<" not in header_actions_body  # icon-only, no label
    assert ">Compare<" not in header_actions_body
    assert ".header-icon-btn" in css
    # Header LTP — single-symbol 10s poll, paused off Decisions / when hidden.
    assert 'id="decision-brief-live-price"' in header_actions_body
    assert 'id="decision-brief-live-price-value"' in html
    assert "function startBriefPriceRefresh" in js
    assert "function stopBriefPriceRefresh" in js
    assert "BRIEF_PRICE_REFRESH_MS = 10000" in js
    assert "/api/v1/market/instruments/" in js and "/quote" in js
    assert "stopBriefPriceRefresh()" in js
    assert ".decision-brief-live-price" in css

    # DT-4 (owner reference-mock screenshot): Reasoning Trace redesigned
    # from an auto-fit grid + dynamically-computed SVG connector lines into
    # a vertical pipeline list — same stageMeaning()/dagStatusBadgeHtml()/
    # refreshDagNodeMeanings() data wiring (checked above, unchanged), same
    # click -> selectNode() -> showStageDetails()+switchBriefTab() behavior,
    # same stage order (trace.stages, unchanged) — presentation-only.
    # ResizeObserver/ getBoundingClientRect coordinate math and the SVG
    # overlay are gone entirely, replaced by a pure-CSS rail.
    assert 'id="dag-svg-lines"' not in html
    assert "class=\"dag-svg-overlay\"" not in html
    assert "new ResizeObserver" not in js
    assert "function drawDAGLines" not in js
    assert "dagSvgLines" not in js
    assert ".dag-node-rail" in css
    assert ".dag-node-icon-wrap" in css
    assert ".dag-node-body" in css
    render_trace_dag_start = js.find("function renderTraceDAG(trace)")
    render_trace_dag_end = js.find("\n    function ", render_trace_dag_start + 1)
    render_trace_dag_body = js[render_trace_dag_start:render_trace_dag_end]
    assert "dag-node-rail" in render_trace_dag_body
    assert "dag-node-icon-wrap" in render_trace_dag_body
    assert "dag-node-body" in render_trace_dag_body
    assert "selectNode(stage.stage_id, { userInitiated: true })" in render_trace_dag_body


def test_advisor_status_release_gate(client: TestClient) -> None:
    """AS-4: advisor status must stay privacy-safe and de-action expired plans."""
    html = client.get("/dashboard/").text
    css = _fetch_full_css(client)
    js = client.get("/dashboard/dashboard.js").text

    # Diagnostics privacy: correlation IDs and latency remain available, but
    # only inside an explicitly opened popover rather than the permanent header.
    header_start = html.find('<header class="console-header">')
    header_end = html.find("</header>", header_start)
    header_html = html[header_start:header_end]
    assert 'id="advisor-pulse"' in header_html
    assert 'id="header-diagnostics-toggle"' in header_html
    assert 'id="header-diagnostics-popover" class="diagnostics-popover" hidden' in header_html
    assert header_html.count("REQ-ID") == 1
    assert header_html.count("CORR-ID") == 1
    assert header_html.count("LATENCY") == 1
    assert header_html.find('id="advisor-pulse"') < header_html.find('id="header-diagnostics-popover"')
    assert "diagnosticsPopover.hidden = !opening" in js
    assert 'diagnosticsToggle.setAttribute("aria-expanded", opening ? "true" : "false")' in js

    # Reduced-motion users must never get a moving advisor marquee.
    reduced_motion_start = css.find(
        "@media (prefers-reduced-motion: reduce)",
        css.find(".advisor-pulse-message"),
    )
    assert reduced_motion_start != -1
    reduced_motion_css = css[reduced_motion_start: css.find("}", css.find(".advisor-pulse-message", reduced_motion_start)) + 1]
    assert ".advisor-pulse-message" in reduced_motion_css
    assert "animation: none" in reduced_motion_css
    assert "text-overflow: ellipsis" in reduced_motion_css

    # Actionability dominance: expired/stale warnings must win before
    # market-closed review mode or green "plan valid" messaging.
    actionability_start = js.find("function actionabilityStatusFromPlan")
    actionability_end = js.find("\n    function ", actionability_start + 1)
    actionability_body = js[actionability_start:actionability_end]
    no_plan_idx = actionability_body.find('status: "No current trade plan"')
    expired_idx = actionability_body.find('status === "EXPIRED"')
    stale_idx = actionability_body.find('status === "STALE"')
    market_closed_idx = actionability_body.find("if (marketClosed)")
    aging_idx = actionability_body.find('status === "AGING"')
    valid_idx = actionability_body.find('status: "Plan valid"')
    assert -1 not in (no_plan_idx, expired_idx, stale_idx, market_closed_idx, aging_idx, valid_idx)
    assert no_plan_idx < expired_idx < stale_idx < market_closed_idx < aging_idx < valid_idx
    expired_branch = actionability_body[expired_idx:stale_idx]
    assert "tone: \"danger\"" in expired_branch
    assert "tone: \"neutral\"" in actionability_body[:expired_idx]
    assert "Re-check the symbol when you want ATHENA to refresh the thesis" in actionability_body
    assert "Re-validate before using entry/stop/target levels" in actionability_body
    assert "ATHENA is advisory only; confirm live quote before manual action" in actionability_body

    # Expired historical TRADE records are audit/history records, not current
    # action-board rows. They must not become restorable dismissals.
    assert "function isCurrentDecisionListRow" in js
    assert "return !decisionHasHistoricalTradePlan(d);" in js
    assert "traceDecisionsList.filter(isCurrentDecisionListRow)" in js
    assert "isCurrentDecisionListRow(d) && dismissedDecisionSymbols.has" in js
    assert "expired historical TradePlans are hidden from this list" in js

    # Detail-pane dominance: preserve the thesis, but label every top-level
    # cue as historical/not-actionable for blocked TradePlans.
    assert "Historical BUY setup — current TradePlan is not actionable" in js
    assert "Historical universe eligibility" in js
    assert "Historical TradePlan" in js
    assert "Plan not current" in js
    assert "Not actionable" in js
    assert "re-validate before use" in js


def test_dashboard_js_assembled_losslessly_from_concern_split(client: TestClient) -> None:
    """dashboard.js (owner-flagged: 6,100+ lines in one file) was split into
    22 concern-based files under static/js/ (mirrors the earlier dashboard.css
    @import split from UX-7) — verified during the refactor with a standalone
    content-equality script confirming every one of the original 372
    top-level statements survives byte-for-byte, just relocated, never
    altered. Classic <script> tags have no @import equivalent, so this route
    concatenates the split files server-side; this test locks in that the
    served response is exactly what DASHBOARD_JS_PARTS says it should be —
    never a stale cached single file, never a partial/reordered assembly."""
    import athena.api.app as app_module

    real_static_dir = str(Path(app_module.__file__).parent / "static")
    expected = assemble_dashboard_js(real_static_dir)
    resp = client.get("/dashboard/dashboard.js")
    assert resp.status_code == 200
    assert resp.text == expected

    # Every concern file actually contributed real content (catches an empty
    # or accidentally-dropped file in DASHBOARD_JS_PARTS).
    js_dir = Path(real_static_dir) / "js"
    for name in DASHBOARD_JS_PARTS:
        text = (js_dir / name).read_text(encoding="utf-8")
        assert text.strip(), f"{name} is empty — dropped from the split?"

    # Spot-check functions from across the concern spread survive in the
    # assembled output, in their original, unaltered form.
    assert "function apiRequest(url, options = {})" in expected
    assert "function bootstrapSession()" in expected
    assert "function loadPortfolioData()" in expected
    assert "function loadMarketIntelligence()" in expected
    assert "function renderDecisionBrief(" in expected
    assert "function refreshDagNodeMeanings(" in expected
    assert "function loadOperationsWorkspace()" in expected
    assert "function loadSavedSymbols()" in expected
    # The wrapper closure must be preserved exactly — everything still runs
    # inside one document.addEventListener("DOMContentLoaded", ...) callback.
    expected_prefix = (
        '/* ATHENA Workstation Coordinator Script (P9.1) */\n\n'
        'document.addEventListener("DOMContentLoaded", () => {'
    )
    assert expected.startswith(expected_prefix)
    assert expected.rstrip().endswith("});")
    # bootstrapSession() must still be the very last statement to execute —
    # everything else must already be declared by the time it runs.
    tail = expected.rstrip()
    assert tail.endswith("bootstrapSession();\n});") or tail.endswith("bootstrapSession();\n    });")
