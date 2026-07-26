"""Integration tests for Phase 9.1 Dashboard Static Asset Hosting & SPA Routing.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_static_hosting_and_fallback(client: TestClient) -> None:
    """Verify static assets are correctly served and client routes fallback to index.html."""
    # 1. Test index.html retrieval
    resp_index = client.get("/dashboard/")
    assert resp_index.status_code == 200
    assert "ATHENA" in resp_index.text
    assert "<aside" in resp_index.text

    # 2. Test CSS loading
    resp_css = client.get("/dashboard/dashboard.css")
    assert resp_css.status_code == 200
    assert "background-color" in resp_css.text

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
    css = client.get("/dashboard/dashboard.css").text
    js = client.get("/dashboard/dashboard.js").text

    # Modals are present once each and marked inert at rest
    assert html.count('id="trace-modal"') == 1
    assert html.count('id="backtest-modal"') == 1
    assert 'id="trace-modal" class="modal-overlay" hidden' in html
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
    assert "function renderCandlestickSvg" in js
    assert "function renderChartFreshness" in js
    assert "/candles?timeframe=5m&limit=120" in js
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

    # M-D4 renders session/calendar, regime/market-health context, curated links, and export
    assert 'id="decision-context-lane"' in js
    assert 'id="decision-brief-export"' in html
    assert "function renderDecisionContext" in js
    assert "function loadDecisionContext" in js
    assert "function exportDecisionBrief" in js
    assert "/context" in js
    assert "DECISION_BRIEF" in js
    assert "No news ingestion, no generated rationale" in js
    assert "UNKNOWN — re-validate to persist a regime assessment" in js
    assert ".decision-context-lane" in css
    assert ".context-chip" in css
    assert ".context-links-list" in css

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
    assert "opened automatically" in js
    assert "activeDepth" in js
    assert "activeContextData" in js
    assert "formatDecisionRatio" in js
    assert "function renderStageDetailBody" not in js
    assert "function renderContextStageBody" not in js
    assert "function renderTradePlanStageBody" not in js
    assert "function refreshSelectedStageDetail" not in js

    # Today's Decisions is grouped into outcome carousels (Trade -> Watch ->
    # No trade -> everything else), always in that priority order regardless
    # of timestamp — never one flat chronological list
    assert 'id="decisions-carousel-groups"' in html
    assert "function renderDecisionCarousels" in js
    assert "function renderDeckCard" in js
    assert "DECISION_CAROUSEL_SECTIONS" in js
    assert "function decisionTypePriority" in js
    assert "regardless of timestamp" in js
    assert ".decision-carousel-section" in css
    assert ".decision-carousel-track" in css
    assert ".deck-card" in css

    # Sticky cockpit header: live score/confidence/risk gauges + a four-tab
    # brief (Setup/Analysis/Context/Response) replacing one long stacked scroll
    assert 'id="decision-brief-gauges"' in html
    assert 'id="gauge-score-value"' in html
    assert 'id="gauge-confidence-value"' in html
    assert 'id="gauge-risk-value"' in html
    assert 'data-brief-tab="setup"' in html
    assert 'data-brief-tab="analysis"' in html
    assert 'data-brief-tab="context"' in html
    assert 'data-brief-tab="response"' in html
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
    assert 'id="decision-executive-summary"' in js
    assert "function qualityBand" in js
    assert "function riskBand" in js
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

    # UX-3: Trade Plan visual redesign (owner UX audit) — bigger numbers,
    # plus a genuinely new Expected Return % computed from the plan's own
    # persisted entry/target values, never fabricated
    assert "function computeExpectedReturnPct" in js
    assert ".trade-plan-hero-grid" in css
    assert ".trade-plan-hero-value" in css

    # UX-3b: chart ATR/moving-average/volume overlay — plotted from the
    # candle-level atr/moving_average fields the API now serves, honestly
    # None during warmup, never interpolated or invented
    assert "Moving average" in js
    assert "ATR band" in js
    assert "decision-chart-ma-line" in js
    assert "decision-chart-atr-band" in js
    assert "decision-chart-volume-bar" in js
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
    assert ">Decision History</span>" in html
    assert 'data-brief-tab="setup"' in html
    assert 'data-brief-tab="context"' in html
    assert 'data-brief-tab="response"' in html
    assert "function contextMetricCard" in js
    assert "function regimeLabelCategory" in js
    assert "View detailed breakdown" in js
    assert ".analysis-detail-toggle" in css
    assert ".context-metric-grid" in css
    assert ".context-metric-value" in css

    # Re-validate moved to the Decision Brief header — always visible, not buried
    # at the bottom of the brief (owner feedback: "no idea of where it exists")
    assert 'id="decision-brief-revalidate-header"' in html
    assert 'id="decision-brief-revalidate"' not in js
    assert "function setHeaderRevalidateEnabled" in js
    assert ".decision-brief-header-actions" in css
    assert ".btn-sm" in css

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
    assert "function loadDecisionPlanFreshness" in js
    assert "/plan-freshness" in js
    assert ".plan-freshness-badge" in css

    # Operations console (P9.7) is live — warnings feed + backup panel, not a fake loader
    assert 'id="ops-warnings-feed"' in html
    assert 'id="ops-telemetry-chart"' in html
    assert 'id="ops-backups-body"' in html
    assert "Loading platform telemetry, logs, and triggers..." not in html
    assert "loadOperationsWorkspace" in js
    assert "startOpsStream" in js
