
    const dagQuickSummary = document.getElementById("dag-quick-summary");
    const quickSummaryCard = document.getElementById("quick-summary-card");
    const quickSummaryStanceEl = document.getElementById("quick-summary-stance");
    const decisionBriefTitle = document.getElementById("decision-brief-title");
    const decisionBriefCompanyName = document.getElementById("decision-brief-company-name");
    const decisionBriefMetaRow = document.getElementById("decision-brief-meta-row");
    const decisionBriefExchangeSymbol = document.getElementById("decision-brief-exchange-symbol");
    const decisionBriefFavoriteToggle = document.getElementById("decision-brief-favorite-toggle");
    const decisionBriefAsOf = document.getElementById("decision-brief-asof");
    const decisionBriefLivePrice = document.getElementById("decision-brief-live-price");
    const decisionBriefLivePriceValue = document.getElementById("decision-brief-live-price-value");
    const decisionBriefLivePriceChange = document.getElementById("decision-brief-live-price-change");
    const decisionBriefBody = document.getElementById("decision-brief-body");
    const decisionBriefHeader = document.querySelector(".decision-brief-header");
    const decisionBriefGauges = document.getElementById("decision-brief-gauges");
    const decisionBriefTabstrip = document.getElementById("decision-brief-tabstrip");
    const decisionBriefRevalidateHeader = document.getElementById("decision-brief-revalidate-header");
    const gaugeRecommendationTile = document.getElementById("gauge-recommendation-tile");
    const gaugeRecommendationStance = document.getElementById("gauge-recommendation-stance");
    const decisionSummaryCard = document.getElementById("decision-summary-card");
    const decisionSummaryHeadline = document.getElementById("decision-summary-headline");
    const decisionActionabilityBanner = document.getElementById("decision-actionability-banner");
    const decisionActionabilityLabel = document.getElementById("decision-actionability-label");
    const decisionActionabilityStatus = document.getElementById("decision-actionability-status");
    const decisionActionabilityDetail = document.getElementById("decision-actionability-detail");

    // ATHENA Summary "View Details" opens the same executive-summary bullet
    // list previously shown inline on every tab — now a modal, following the
    // existing openModal/closeModal pattern already used for Compare/Chart/
    // Backtest (no new modal architecture).
    const executiveSummaryModalEl = document.getElementById("executive-summary-modal");
    document.getElementById("decision-summary-view-details")?.addEventListener("click", () => openModal(executiveSummaryModalEl));
    document.getElementById("executive-summary-modal-close")?.addEventListener("click", () => closeModal(executiveSummaryModalEl));
    window.addEventListener("click", event => {
        if (event.target === executiveSummaryModalEl) closeModal(executiveSummaryModalEl);
    });

    // Header LTP poll — one symbol, 10s, only while Decisions is active and the
    // document is visible. Server coalesces duplicate hits for 5s; client never
    // stacks in-flight requests. Stops on empty brief / tab leave / hide.
    const BRIEF_PRICE_REFRESH_MS = 10000;
    let briefPriceInstrumentId = null;
    let briefPriceIntervalId = null;
    let briefPriceInFlight = false;

    function formatBriefPrice(value) {
        const num = Number(value);
        if (!Number.isFinite(num)) return "—";
        return `₹${num.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    function renderBriefLivePrice(quote) {
        if (!decisionBriefLivePrice || !decisionBriefLivePriceValue) return;
        activeBriefQuote = quote || null;
        const price = quote && quote.last_price != null ? Number(quote.last_price) : NaN;
        if (!Number.isFinite(price)) {
            decisionBriefLivePrice.hidden = false;
            decisionBriefLivePriceValue.textContent = "—";
            if (decisionBriefLivePriceChange) {
                decisionBriefLivePriceChange.textContent = "";
                decisionBriefLivePriceChange.className = "decision-brief-live-price-change";
            }
            decisionBriefLivePrice.title = "Current market price unavailable";
            if (typeof refreshActiveDecisionChart === "function") refreshActiveDecisionChart();
            return;
        }
        decisionBriefLivePrice.hidden = false;
        decisionBriefLivePriceValue.textContent = formatBriefPrice(price);
        const change = quote && quote.change_pct != null ? Number(quote.change_pct) : NaN;
        if (decisionBriefLivePriceChange) {
            if (!Number.isFinite(change)) {
                decisionBriefLivePriceChange.textContent = "";
                decisionBriefLivePriceChange.className = "decision-brief-live-price-change";
            } else {
                const sign = change > 0 ? "+" : "";
                decisionBriefLivePriceChange.textContent = `${sign}${change.toFixed(2)}%`;
                decisionBriefLivePriceChange.className = `decision-brief-live-price-change ${
                    change > 0 ? "is-up" : change < 0 ? "is-down" : "is-flat"
                }`;
            }
        }
        const source = quote && quote.source === "kite_live"
            ? "Live Kite"
            : quote && quote.source === "persisted"
                ? "Last persisted quote"
                : "Unavailable";
        const asOf = quote && quote.as_of
            ? ` · ${formatDecisionTime(quote.as_of)}`
            : "";
        decisionBriefLivePrice.title = `${source}${asOf}`;
        if (typeof refreshActiveDecisionChart === "function") refreshActiveDecisionChart();
    }

    function clearBriefLivePrice() {
        activeBriefQuote = null;
        if (decisionBriefLivePrice) decisionBriefLivePrice.hidden = true;
        if (decisionBriefLivePriceValue) decisionBriefLivePriceValue.textContent = "—";
        if (decisionBriefLivePriceChange) {
            decisionBriefLivePriceChange.textContent = "";
            decisionBriefLivePriceChange.className = "decision-brief-live-price-change";
        }
    }

    async function loadBriefLivePrice() {
        if (!briefPriceInstrumentId || briefPriceInFlight) return;
        if (document.hidden || (typeof state !== "undefined" && state.activeTab !== "decisions")) {
            return;
        }
        briefPriceInFlight = true;
        try {
            const res = await apiRequest(
                `/api/v1/market/instruments/${encodeURIComponent(briefPriceInstrumentId)}/quote`,
                { skipToast: true }
            );
            if (!briefPriceInstrumentId) return;
            if (res && res.status === "success" && res.data) {
                renderBriefLivePrice(res.data);
            }
        } catch (err) {
            console.error("Failed to load brief live price", err);
        } finally {
            briefPriceInFlight = false;
        }
    }

    function stopBriefPriceRefresh() {
        briefPriceInstrumentId = null;
        if (briefPriceIntervalId != null) {
            clearInterval(briefPriceIntervalId);
            briefPriceIntervalId = null;
        }
        clearBriefLivePrice();
    }

    function startBriefPriceRefresh(instrumentId) {
        const iid = String(instrumentId || "").trim().toUpperCase();
        if (!iid || iid === "INDEX") {
            stopBriefPriceRefresh();
            return;
        }
        const normalized = iid.includes(":") ? iid : `NSE:${iid}`;
        if (briefPriceInstrumentId === normalized && briefPriceIntervalId != null) {
            loadBriefLivePrice();
            return;
        }
        if (briefPriceIntervalId != null) {
            clearInterval(briefPriceIntervalId);
            briefPriceIntervalId = null;
        }
        briefPriceInstrumentId = normalized;
        if (decisionBriefLivePrice) decisionBriefLivePrice.hidden = false;
        if (decisionBriefLivePriceValue) decisionBriefLivePriceValue.textContent = "—";
        if (decisionBriefLivePriceChange) {
            decisionBriefLivePriceChange.textContent = "";
            decisionBriefLivePriceChange.className = "decision-brief-live-price-change";
        }
        loadBriefLivePrice();
        briefPriceIntervalId = setInterval(loadBriefLivePrice, BRIEF_PRICE_REFRESH_MS);
    }

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden && briefPriceInstrumentId && state.activeTab === "decisions") {
            loadBriefLivePrice();
        }
    });

    function updateDecisionBriefHeaderDensity() {
        const isCompact = Boolean(decisionBriefBody && decisionBriefBody.scrollTop > 16);
        decisionBriefHeader?.classList.toggle("is-compact", isCompact);
    }

    function resetDecisionBriefHeaderDensity() {
        if (decisionBriefBody) decisionBriefBody.scrollTop = 0;
        decisionBriefHeader?.classList.remove("is-compact");
    }

    decisionBriefBody?.addEventListener("scroll", updateDecisionBriefHeaderDensity, { passive: true });

    // Owner reference-mock: secondary actions (Dismiss today/Remove
    // candidate/Export/News) consolidated behind a "more" popover instead of
    // cluttering the action bar — same toggle/backdrop-click/Escape pattern
    // already established for the symbols filter popover (12-decisions-
    // list.js) and the reasoning-trace stage-detail panel.
    const decisionBriefOverflowToggle = document.getElementById("decision-brief-overflow-toggle");
    const decisionBriefOverflowMenu = document.getElementById("decision-brief-overflow-menu");
    const decisionBriefOpenChart = document.getElementById("decision-brief-open-chart");
    const decisionBriefCompare = document.getElementById("decision-brief-compare");

    function closeOverflowMenu() {
        if (!decisionBriefOverflowMenu || !decisionBriefOverflowToggle) return;
        decisionBriefOverflowMenu.hidden = true;
        decisionBriefOverflowToggle.setAttribute("aria-expanded", "false");
    }

    decisionBriefOverflowToggle?.addEventListener("click", event => {
        event.stopPropagation();
        if (!decisionBriefOverflowMenu) return;
        const opening = decisionBriefOverflowMenu.hidden;
        decisionBriefOverflowMenu.hidden = !opening;
        decisionBriefOverflowToggle.setAttribute("aria-expanded", opening ? "true" : "false");
    });
    document.addEventListener("click", event => {
        if (decisionBriefOverflowMenu && !decisionBriefOverflowMenu.hidden
            && !decisionBriefOverflowMenu.contains(event.target)
            && event.target !== decisionBriefOverflowToggle) {
            closeOverflowMenu();
        }
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeOverflowMenu();
    });
    // Any menu item click also closes the menu (owner UX precedent: the
    // symbols filter popover closes itself after an action, not left open).
    decisionBriefOverflowMenu?.querySelectorAll(".overflow-menu-item").forEach(btn => {
        btn.addEventListener("click", closeOverflowMenu);
    });

    // Favorite (Saved Symbols) toggle — reuses the existing GET/POST/DELETE
    // /api/v1/saved-symbols endpoints (Market Intelligence's own watch-list
    // feature, UX-9b), just a new star-icon surface for it. A lightweight
    // local Set cache avoids re-fetching the whole list on every keystroke/
    // selection; refreshed whenever it might be stale.
    let savedSymbolsCache = null;

    async function loadSavedSymbolsCache() {
        try {
            const res = await apiRequest("/api/v1/saved-symbols", { skipToast: true });
            const rows = (res && res.data && res.data.symbols) ? res.data.symbols : [];
            savedSymbolsCache = new Set(rows.map(s => String(s.symbol || "").toUpperCase()));
        } catch (err) {
            console.error("Failed to load saved symbols", err);
            savedSymbolsCache = null;
        }
    }

    function applyFavoriteToggleState(bareSymbol) {
        if (!decisionBriefFavoriteToggle) return;
        const saved = savedSymbolsCache instanceof Set && savedSymbolsCache.has(bareSymbol);
        decisionBriefFavoriteToggle.classList.toggle("is-saved", saved);
        decisionBriefFavoriteToggle.setAttribute("aria-pressed", saved ? "true" : "false");
        decisionBriefFavoriteToggle.title = saved ? "Remove from watch list" : "Save to watch list";
    }

    decisionBriefFavoriteToggle?.addEventListener("click", async () => {
        const bareSymbol = decisionBriefFavoriteToggle.dataset.symbol;
        if (!bareSymbol) return;
        decisionBriefFavoriteToggle.disabled = true;
        try {
            const alreadySaved = savedSymbolsCache instanceof Set && savedSymbolsCache.has(bareSymbol);
            if (alreadySaved) {
                await apiRequest(`/api/v1/saved-symbols/${encodeURIComponent(bareSymbol)}`, {
                    method: "DELETE", skipToast: true,
                });
                savedSymbolsCache?.delete(bareSymbol);
                showToast(`${bareSymbol} removed from Saved Symbols`, "success");
            } else {
                await apiRequest("/api/v1/saved-symbols", {
                    method: "POST",
                    body: JSON.stringify({ symbol: bareSymbol }),
                    skipToast: true,
                });
                if (!(savedSymbolsCache instanceof Set)) savedSymbolsCache = new Set();
                savedSymbolsCache.add(bareSymbol);
                showToast(`${bareSymbol} saved to your watch list`, "success");
            }
            applyFavoriteToggleState(bareSymbol);
        } catch (err) {
            console.error(`Failed to toggle saved symbol ${bareSymbol}`, err);
            showToast("Could not update Saved Symbols — try again", "danger");
        } finally {
            decisionBriefFavoriteToggle.disabled = false;
        }
    });

    function renderDecisionBriefEmpty(title, detail) {
        resetDecisionBriefHeaderDensity();
        if (decisionBriefTitle) {
            decisionBriefTitle.textContent = "Select a symbol";
            decisionBriefTitle.title = "";
        }
        if (decisionBriefAsOf) decisionBriefAsOf.textContent = "Select a symbol";
        stopBriefPriceRefresh();
        if (decisionBriefCompanyName) decisionBriefCompanyName.textContent = "";
        if (decisionBriefMetaRow) decisionBriefMetaRow.hidden = true;
        if (decisionBriefExchangeSymbol) decisionBriefExchangeSymbol.textContent = "";
        if (decisionBriefFavoriteToggle) {
            decisionBriefFavoriteToggle.disabled = true;
            decisionBriefFavoriteToggle.classList.remove("is-saved");
            decisionBriefFavoriteToggle.removeAttribute("data-symbol");
        }
        closeOverflowMenu();
        if (decisionBriefGauges) decisionBriefGauges.hidden = true;
        if (decisionBriefTabstrip) decisionBriefTabstrip.hidden = true;
        if (decisionSummaryCard) decisionSummaryCard.hidden = true;
        if (decisionSummaryHeadline) decisionSummaryHeadline.textContent = "";
        if (decisionActionabilityBanner) decisionActionabilityBanner.hidden = true;
        if (decisionActionabilityStatus) decisionActionabilityStatus.textContent = "Review required";
        if (decisionActionabilityDetail) decisionActionabilityDetail.textContent = "";
        if (gaugeRecommendationTile) gaugeRecommendationTile.className = "brief-gauge brief-gauge-recommendation";
        if (gaugeRecommendationStance) gaugeRecommendationStance.textContent = "—";
        if (typeof clearAdvisorPulsePriority === "function") clearAdvisorPulsePriority(1);
        if (typeof setAdvisorPulse === "function") {
            setAdvisorPulse(
                "ATHENA advisor ready · Select a symbol to review actionability",
                "neutral",
                0
            );
        }
        resetCockpitGauges();
        setHeaderRevalidateEnabled(false);
        setHeaderActionsEnabled(false);
        // Owner-reported: after "Clear all", the main brief correctly went
        // empty but the Reasoning Trace sidebar kept showing the previously
        // selected symbol's quick-summary chips and DAG stage-detail card —
        // neither is owned by the main brief body this function otherwise
        // resets, so both were silently left stale. This is the one function
        // whose job is "there is no decision to show," so it now clears them
        // authoritatively for every caller (Clear all, zero-filter-results,
        // and a failed decision-detail fetch) rather than relying on each
        // call site to remember to do it individually.
        activeDecisionData = null;
        selectedStageId = null;
        renderSidebarQuickSummary();
        if (dagDetailsPanel) dagDetailsPanel.style.display = "none";
        if (!decisionBriefBody) return;
        decisionBriefBody.innerHTML = `
            <div class="decision-brief-empty">
                <i class="fa-solid fa-chart-line"></i>
                <strong>${escapeDecisionHtml(title || "Select a decision")}</strong>
                <span>${escapeDecisionHtml(detail || "ATHENA will show the current thesis, safety gates, and advisory TradePlan.")}</span>
            </div>
        `;
    }

    async function exportDecisionBrief(decisionId, button) {
        if (button) {
            button.disabled = true;
            button.dataset.originalHtml = button.innerHTML;
            button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Exporting…';
        }
        try {
            const jobRes = await apiRequest("/api/v1/exports", {
                method: "POST",
                body: JSON.stringify({
                    source: { artifact_id: decisionId, artifact_type: "DECISION_BRIEF" },
                    format: "JSON",
                    options: {},
                }),
            });
            const artifactId = jobRes && jobRes.data && jobRes.data.result_artifact_id;
            if (!artifactId) throw new Error("Export produced no artifact");
            const artRes = await apiRequest(
                `/api/v1/exports/artifacts/${encodeURIComponent(artifactId)}`
            );
            const artifact = artRes && artRes.data;
            if (!artifact) throw new Error("Export artifact unavailable");
            const blob = new Blob(
                [artifact.payload],
                { type: (artifact.metadata && artifact.metadata.content_type) || "application/json" }
            );
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = (artifact.metadata && artifact.metadata.filename) || `decision_brief_${decisionId}.json`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
            showToast("Decision brief exported.", "success");
        } catch (err) {
            console.error(`Failed to export decision brief for ${decisionId}`, err);
            showToast("Failed to export decision brief.", "danger");
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = button.dataset.originalHtml
                    || '<i class="fa-solid fa-file-export"></i> Export Brief';
            }
        }
    }

    // Sticky "Quick Summary" card pinned to the top of the Reasoning Trace
    // panel (DT-2, owner UX workstation refactor — expanded from UX-6's
    // score/confidence/risk-only sidebar strip). Every field is a value
    // that already exists and already renders elsewhere on this same brief
    // (gauges, Trade Plan, Historical Analogs) — this consolidates them into
    // one glanceable card rather than duplicating a second, separate
    // "Quick Summary" section, per the owner's "don't duplicate information
    // unnecessarily" instruction. No new fetch, no new calculation beyond
    // formatting — reuses activeDecisionData/activeDepth/activeAnalogs
    // already loaded for the brief, and shows "—" for anything not loaded
    // (or not applicable) yet, never a fabricated value.
    function renderSidebarQuickSummary() {
        if (!dagQuickSummary) return;
        const decision = activeDecisionData;
        if (!decision || !decision.metadata) {
            if (quickSummaryCard) quickSummaryCard.style.display = "none";
            dagQuickSummary.innerHTML = "";
            return;
        }
        const meta = decision.metadata;
        const stance = decisionStance(meta.decision_type, meta.direction);
        const historicalPlan = decisionHasHistoricalTradePlan(decision, activePlanFreshness);
        const displayStance = historicalPlan
            ? { label: "Not actionable", cls: "stance-pass" }
            : stance;
        const depth = activeDepth;

        // Score/Confidence/Risk reuse the exact same status/level/value
        // already computed for the hero cockpit gauges (renderCockpitGauges)
        // — never a second, client-derived number — but formatted per the
        // owner's reference mock (raw numbers, not band words, so this card
        // reads as data at a glance rather than repeating the gauge chips).
        const scoreView = analysisPresentation(friendlyAnalysisName("score"), depth && depth.score, "score");
        const scoreRow = scoreView.status === "OK"
            ? `<div class="quick-summary-row"><span>Score</span><strong>${escapeDecisionHtml(scoreView.valueLabel)}/100</strong></div>`
            : `<div class="quick-summary-row"><span>Score</span><strong>—</strong></div>`;

        const confidenceView = analysisPresentation(friendlyAnalysisName("confidence"), depth && depth.confidence, "confidence");
        const confidenceRow = confidenceView.status === "OK"
            ? `<div class="quick-summary-row"><span>Confidence</span><strong>${escapeDecisionHtml(confidenceView.valueLabel)}%</strong></div>`
            : `<div class="quick-summary-row"><span>Confidence</span><strong>—</strong></div>`;

        // Risk band (Low/Medium/High) from the same riskBand() thresholds
        // the hero gauge already bands by, colored via the shared
        // .tone-good/warn/bad-text utility classes (same tokens the header
        // ticker's positive/negative colors use).
        const riskView = analysisPresentation(friendlyAnalysisName("risk"), depth && depth.risk, "risk");
        const riskRow = (() => {
            if (riskView.status !== "OK") {
                return `<div class="quick-summary-row"><span>Risk</span><strong>—</strong></div>`;
            }
            const band = riskBand(riskView.data.value) || "—";
            const toneCls = band === "Low" ? "tone-good-text" : band === "High" ? "tone-bad-text" : "tone-warn-text";
            return `<div class="quick-summary-row"><span>Risk</span><strong class="${toneCls}">${escapeDecisionHtml(band)} (${escapeDecisionHtml(riskView.valueLabel)})</strong></div>`;
        })();

        const plan = decision.trade_plan;
        // One-decimal ratio, matching the hero gauge's own "EXPECTED R:R"
        // formatting (heroRR.toFixed(1)) rather than the two-decimal
        // formatDecisionRatio() used on the Trade Plan tab.
        const rr = plan ? Number(plan.risk_reward) : NaN;
        const rrRow = Number.isFinite(rr)
            ? `<div class="quick-summary-row"><span>R:R Potential</span><strong>${rr.toFixed(1)} : 1</strong></div>`
            : "";
        // Same computeExpectedReturnPct already used by the Trade Plan tab —
        // never a second, independently-derived calculation.
        const expectedReturnPct = plan ? computeExpectedReturnPct(plan, meta.direction) : null;
        const expectedReturnRow = expectedReturnPct != null && Number.isFinite(expectedReturnPct)
            ? `<div class="quick-summary-row"><span>Expected Return</span><strong class="${expectedReturnPct >= 0 ? "tone-good-text" : "tone-bad-text"}">${expectedReturnPct >= 0 ? "+" : ""}${expectedReturnPct.toFixed(2)}%</strong></div>`
            : "";
        const planFreshness = activePlanFreshness && activePlanFreshness.has_trade_plan
            ? activePlanFreshness
            : inferTradePlanFreshness(plan);
        const planTone = String(planFreshness.status || "unknown").toLowerCase();
        const planLabel = formatTradePlanFreshnessBadge(planFreshness);
        const planTitle = formatTradePlanFreshnessTitle(planFreshness)
            || "TradePlan freshness uses the persisted validity window.";
        const planStatusRow = plan
            ? `<div class="quick-summary-row quick-summary-plan-row"><span>Plan Status</span><strong class="quick-summary-plan-status tone-${escapeDecisionHtml(planTone)}" title="${escapeDecisionHtml(planTitle)}">${escapeDecisionHtml(planLabel)}</strong></div>`
            : `<div class="quick-summary-row quick-summary-plan-row"><span>Plan Status</span><strong class="quick-summary-plan-status tone-no_plan">No plan</strong></div>`;

        // Historical Analogs aggregate (UX-6) — explicitly labeled
        // "(Historical)" since there is no forward-looking, per-decision
        // holding-period field anywhere in ATHENA; this is a real average
        // across similar PAST trades, not a guarantee for this one.
        const analogs = activeAnalogs;
        const winRateRow = analogs && analogs.win_rate_pct != null
            ? `<div class="quick-summary-row"><span>Win Rate (Historical)</span><strong>${Number(analogs.win_rate_pct).toFixed(0)}%</strong></div>`
            : "";
        // Holding Period: a real min-max range across the same per-analog
        // outcome_holding_days values already averaged above (never a
        // fabricated estimate) — matches the reference mock's field more
        // closely than a single average did. Whole days, matching the
        // mock's own "2 - 5 Days" convention; collapses to one number when
        // every analog happened to hold for the same length of time.
        const minHold = analogs && analogs.min_holding_days != null ? Math.round(Number(analogs.min_holding_days)) : null;
        const maxHold = analogs && analogs.max_holding_days != null ? Math.round(Number(analogs.max_holding_days)) : null;
        const holdingPeriodRow = minHold != null && maxHold != null
            ? `<div class="quick-summary-row"><span>Holding Period (Historical)</span><strong>${minHold === maxHold ? `${minHold}` : `${minHold} - ${maxHold}`} Days</strong></div>`
            : "";

        if (quickSummaryStanceEl) {
            quickSummaryStanceEl.textContent = displayStance.label;
            quickSummaryStanceEl.className = `stance-chip ${displayStance.cls}`;
        }
        if (quickSummaryCard) quickSummaryCard.style.display = "flex";
        dagQuickSummary.innerHTML = `
            ${scoreRow}
            ${confidenceRow}
            ${riskRow}
            ${holdingPeriodRow}
            ${winRateRow}
            ${expectedReturnRow}
            ${rrRow}
            ${planStatusRow}
        `;
    }

    function actionabilityStatusFromPlan(decision, freshness = null) {
        const plan = decision && decision.trade_plan;
        if (!decision || !decision.metadata || !plan) return null;
        const stance = decisionStance(
            decision.metadata.decision_type,
            decision.metadata.direction
        );
        const rawSymbol = String(decision.metadata.instrument_id || "");
        const symbol = rawSymbol.includes(":") ? rawSymbol.split(":").pop() : rawSymbol;
        const status = String(freshness && freshness.status || "").toUpperCase();
        const validUntil = new Date(plan.valid_until);
        const now = new Date();
        const inferredExpired = !Number.isNaN(validUntil.getTime()) && now > validUntil;
        const remaining = freshness && freshness.remaining_seconds != null
            ? Number(freshness.remaining_seconds)
            : Number.isNaN(validUntil.getTime())
                ? null
                : Math.round((validUntil.getTime() - now.getTime()) / 1000);
        const remainingLabel = remaining != null && Number.isFinite(remaining)
            ? formatTradePlanRelativeDuration(Math.abs(remaining))
            : "";
        const expiredLabel = (() => {
            const asOf = freshness && freshness.as_of ? new Date(freshness.as_of) : now;
            const expiry = freshness && freshness.valid_until
                ? new Date(freshness.valid_until)
                : validUntil;
            if (Number.isNaN(asOf.getTime()) || Number.isNaN(expiry.getTime())) {
                return remainingLabel;
            }
            return formatTradePlanRelativeDuration((asOf.getTime() - expiry.getTime()) / 1000);
        })();
        const session = state && state.marketSession ? state.marketSession : null;
        const marketClosed = session && session.is_market_open === false;
        const sessionMessage = session && session.message ? String(session.message) : "Market closed";

        if (status === "EXPIRED" || inferredExpired) {
            return {
                tone: "danger",
                status: "Plan expired · re-validate",
                detail: `Expired${
                    expiredLabel ? ` ${expiredLabel} ago` : ""
                }. Re-validate before using entry/stop/target levels.`,
                pulse: `${symbol ? `${symbol} · ` : ""}expired${
                    expiredLabel ? ` ${expiredLabel} ago` : ""
                } · re-validate`,
                cta: "Re-validate plan",
                priority: 2,
            };
        }
        if (status === "STALE") {
            return {
                tone: "warning",
                status: "Plan stale · confirm first",
                detail: marketClosed
                    ? `${sessionMessage}. Re-validate after market opens before entry.`
                    : `Validity window is nearly exhausted. Re-validate before entry.`,
                pulse: marketClosed
                    ? `${symbol ? `${symbol} · ` : ""}review mode · plan stale`
                    : `${symbol ? `${symbol} · ` : ""}plan stale · confirm first`,
                cta: "Re-validate plan",
                priority: 2,
            };
        }
        if (marketClosed) {
            return {
                tone: "warning",
                status: "Review mode · market closed",
                detail: `${sessionMessage}. Review the thesis only; confirm live quote and re-validate before entry.`,
                pulse: `${symbol ? `${symbol} · ` : ""}review mode · market closed`,
                cta: "Re-check at open",
                priority: 1,
            };
        }
        if (status === "AGING") {
            return {
                tone: "warning",
                status: "Plan aging",
                detail: `TradePlan expires${remainingLabel ? ` in ${remainingLabel}` : " this session"}. Confirm live quote before entry.`,
                pulse: `${symbol ? `${symbol} · ` : ""}expires in ${remainingLabel || "this session"}`,
                cta: "Refresh thesis",
                priority: 1,
            };
        }
        return {
            tone: "good",
            status: "Plan valid",
            detail: `TradePlan is valid${remainingLabel ? ` for ${remainingLabel}` : ""}. ATHENA is advisory only; confirm live quote before manual action.`,
            pulse: `${symbol ? `${symbol} · ` : ""}plan valid${remainingLabel ? ` ${remainingLabel}` : ""}`,
            cta: "Refresh thesis",
            priority: 1,
        };
    }

    function renderDecisionActionability(freshness = null) {
        const view = actionabilityStatusFromPlan(activeDecisionData, freshness);
        if (!decisionActionabilityBanner || !view) {
            if (decisionActionabilityBanner) decisionActionabilityBanner.hidden = true;
            if (typeof clearAdvisorPulsePriority === "function") clearAdvisorPulsePriority(1);
            if (typeof setAdvisorPulse === "function") {
                setAdvisorPulse(
                    "ATHENA advisor ready · Select a symbol to review actionability",
                    "neutral",
                    0
                );
            }
            return;
        }
        decisionActionabilityBanner.hidden = false;
        decisionActionabilityBanner.className = `decision-actionability-banner tone-${view.tone}`;
        if (decisionActionabilityLabel) decisionActionabilityLabel.textContent = "Advisor status";
        if (decisionActionabilityStatus) decisionActionabilityStatus.textContent = view.status;
        if (decisionActionabilityDetail) decisionActionabilityDetail.textContent = view.detail;
        if (decisionBriefRevalidateHeader) {
            const label = decisionBriefRevalidateHeader.querySelector("span");
            if (label) label.textContent = view.cta || "Re-validate plan";
            decisionBriefRevalidateHeader.title = view.cta || "Re-validate this symbol";
        }
        if (typeof clearAdvisorPulsePriority === "function" && view.priority <= 1) {
            clearAdvisorPulsePriority(2);
        }
        if (typeof setAdvisorPulse === "function") {
            setAdvisorPulse(view.pulse, view.tone, view.priority);
        }
    }

    function renderTradePlaybook(decision, freshness = null) {
        const plan = decision && decision.trade_plan;
        const meta = decision && decision.metadata ? decision.metadata : {};
        const status = String(freshness && freshness.status || "").toUpperCase();
        const session = state && state.marketSession ? state.marketSession : null;
        const marketClosed = session && session.is_market_open === false;
        const historical = decisionHasHistoricalTradePlan(decision, freshness);
        const validLike = decisionHasCurrentActionableTradePlan(decision, freshness);
        const statusClass = historical ? "blocked" : (marketClosed || status === "STALE" ? "review" : "");
        const statusText = historical
            ? "This plan is old. Do not use these entry, stop, or target prices until ATHENA checks the symbol again."
            : marketClosed
                ? "Market is closed. Review only; check again after the market opens."
                : validLike
                    ? "Use these steps before taking any manual trade."
                    : "There is no current trade plan for this symbol.";
        const entryText = plan
            ? "Enter only if the live price is inside the entry zone and the plan is still valid."
            : "Do not enter; ATHENA has not given an entry zone.";
        const stopText = plan
            ? "If price reaches the stop, the setup has failed. Exit manually."
            : "There is no stop price without a trade plan.";
        const targetText = plan
            ? "Use the first target as the planned profit area. Do not make up extra targets."
            : "There is no target price without a trade plan.";
        const noFillText = plan
            ? "If price never reaches the entry zone before the plan expires, skip the trade."
            : "If there is no plan, wait until ATHENA checks the symbol again.";
        const closeText = "For intraday trading, do not treat this as an overnight hold. Review or exit before market close unless you have a separate swing plan.";
        const recheckText = marketClosed
            ? "Check again after the market opens before any entry."
            : "Check again after expiry, stale price data, a large price move, or a broad market change.";
        return `
            <section class="decision-brief-section trade-playbook-section" id="trade-playbook-section">
                <div class="decision-brief-section-header">
                    <h4>Trading steps</h4>
                    <span class="trade-plan-label">Manual advisory workflow</span>
                </div>
                <p class="trade-playbook-status ${statusClass}">${escapeDecisionHtml(statusText)}</p>
                <div class="trade-playbook-grid">
                    <div class="trade-playbook-rule">
                        <strong>1. Entry</strong>
                        <span>${escapeDecisionHtml(entryText)}</span>
                    </div>
                    <div class="trade-playbook-rule">
                        <strong>2. Stop</strong>
                        <span>${escapeDecisionHtml(stopText)}</span>
                    </div>
                    <div class="trade-playbook-rule">
                        <strong>3. Target</strong>
                        <span>${escapeDecisionHtml(targetText)}</span>
                    </div>
                    <div class="trade-playbook-rule">
                        <strong>4. No fill</strong>
                        <span>${escapeDecisionHtml(noFillText)}</span>
                    </div>
                    <div class="trade-playbook-rule">
                        <strong>5. End of day</strong>
                        <span>${escapeDecisionHtml(closeText)}</span>
                    </div>
                    <div class="trade-playbook-rule">
                        <strong>6. Re-check</strong>
                        <span>${escapeDecisionHtml(recheckText)}</span>
                    </div>
                </div>
            </section>
        `;
    }

    function refreshTradePlaybook(freshness = null) {
        const host = document.getElementById("trade-playbook-section");
        if (!host || !activeDecisionData) return;
        host.outerHTML = renderTradePlaybook(
            activeDecisionData,
            freshness || decisionTradePlanFreshness(activeDecisionData)
        );
    }

    function renderDecisionBrief(decision) {
        if (!decisionBriefBody || !decision || !decision.metadata) return;
        activeDecisionData = decision;
        renderSidebarQuickSummary();
        const meta = decision.metadata;
        const rawSymbol = meta.instrument_id || "INDEX";
        const symbol = rawSymbol.includes(":") ? rawSymbol.split(":").pop() : rawSymbol;
        const stance = decisionStance(meta.decision_type, meta.direction);
        const historicalPlan = decisionHasHistoricalTradePlan(decision);
        const displayStance = historicalPlan
            ? { label: "Not actionable", cls: "stance-pass" }
            : stance;
        const gates = decision.analysis && Array.isArray(decision.analysis.gate_results)
            ? decision.analysis.gate_results
            : [];
        const summary = historicalPlan
            ? {
                headline: "Historical BUY setup — current TradePlan is not actionable.",
                bullets: [
                    "Re-validate before using entry, stop, or target levels.",
                    "The original persisted decision remains available for audit and replay.",
                ],
            }
            : formatDecisionSummary(decision.explanation, meta.decision_type, gates);

        if (decisionBriefTitle) {
            decisionBriefTitle.textContent = symbol;
            decisionBriefTitle.title = rawSymbol;
        }
        if (decisionBriefAsOf) decisionBriefAsOf.textContent = `As of ${formatDecisionTime(meta.ts)}`;
        startBriefPriceRefresh(rawSymbol);
        // Owner reference-mock: company name (real instruments.name — absent
        // for instruments the catalog hasn't re-synced since it was added,
        // never fabricated) instead of the BUY/TRADE badges, which are now
        // redundant with the Recommendation tile in the gauges row below.
        if (decisionBriefCompanyName) {
            decisionBriefCompanyName.textContent = meta.instrument_name || "";
        }
        // "NSE: DIXON" — trivial split of instrument_id, already available.
        const exchangePrefix = rawSymbol.includes(":") ? rawSymbol.split(":")[0] : null;
        if (decisionBriefExchangeSymbol) {
            decisionBriefExchangeSymbol.textContent = exchangePrefix ? `${exchangePrefix}: ${symbol}` : symbol;
        }
        if (decisionBriefMetaRow) decisionBriefMetaRow.hidden = false;
        // Favorite (Saved Symbols) toggle — bare symbol, matching the same
        // NSE:/BSE: stripping convention already used by
        // removeSavedSymbolNow (09-market-intelligence.js).
        if (decisionBriefFavoriteToggle) {
            const bareSymbol = symbol.toUpperCase();
            decisionBriefFavoriteToggle.disabled = false;
            decisionBriefFavoriteToggle.dataset.symbol = bareSymbol;
            if (savedSymbolsCache === null) {
                loadSavedSymbolsCache().then(() => applyFavoriteToggleState(bareSymbol));
            } else {
                applyFavoriteToggleState(bareSymbol);
            }
        }
        if (decisionBriefGauges) decisionBriefGauges.hidden = false;
        if (decisionBriefTabstrip) decisionBriefTabstrip.hidden = false;
        resetCockpitGauges();
        resetActionButtons();

        const heroRR = document.getElementById("hero-rr-value");
        if (heroRR) {
            const rr = decision.trade_plan ? Number(decision.trade_plan.risk_reward) : NaN;
            heroRR.textContent = Number.isFinite(rr) ? `${rr.toFixed(1)} : 1` : "—";
        }

        // DT-3 refinement (owner reference-mock screenshot): Recommendation
        // merged into the gauges row as its own tile, styled as a filled
        // stance-tinted card (not a small pill) to match the mock — the
        // whole tile's background/border and the stance text's color both
        // key off the same .stance-buy/-sell/-hold/-pass/-wait class,
        // mirroring the exact tone treatment .decision-banner already uses.
        // Stance is known synchronously (from decision.metadata, same as
        // the header chip); the qualifier band ("Strong Setup") depends on
        // the async score depth and is filled in by renderCockpitGauges
        // alongside the Score tile's own band, reusing that exact same
        // computed value.
        if (gaugeRecommendationTile) {
            gaugeRecommendationTile.className = `brief-gauge brief-gauge-recommendation ${displayStance.cls}`;
        }
        if (gaugeRecommendationStance) {
            gaugeRecommendationStance.textContent = displayStance.label;
        }

        // ATHENA Summary card: the same real headline previously shown
        // inline as the "ATHENA Recommendation" banner (now redundant with
        // the gauges-row stance badge above) — repositioned into the sticky
        // header, collapsed behind a "View Details" button rather than
        // permanently repeating the full bullet breakdown on every tab.
        if (decisionSummaryCard) {
            decisionSummaryCard.className = `decision-banner ${displayStance.cls}`;
            decisionSummaryCard.hidden = false;
        }
        if (decisionSummaryHeadline) {
            decisionSummaryHeadline.textContent = summary.headline;
            decisionSummaryHeadline.title = summary.headline;
        }
        renderDecisionActionability();

        const gateRows = gates.length
            ? gates.map(gate => `
                <div class="decision-gate-row">
                    <i class="fa-solid ${gate.passed ? "fa-circle-check pass" : "fa-circle-xmark fail"}"></i>
                    <span class="decision-gate-name">${escapeDecisionHtml(friendlyGateName(gate.gate))}</span>
                    <span class="decision-gate-detail">${escapeDecisionHtml(sanitizeNumericText(gate.detail || "No rationale recorded"))}</span>
                </div>
            `).join("")
            : '<div class="text-muted">No gate results were persisted for this decision.</div>';

        // Safety checklist summary (owner audit #20) — a reassuring headline
        // over the same gate results, not a separate computation.
        const gatesFailed = gates.filter(g => g && g.passed === false).length;
        const gatesSummary = !gates.length
            ? ""
            : gatesFailed === 0
                ? '<div class="safety-checklist-summary pass"><i class="fa-solid fa-shield-halved"></i> All safety checks passed</div>'
                : `<div class="safety-checklist-summary fail"><i class="fa-solid fa-shield-halved"></i> Blocked on ${gatesFailed} of ${gates.length} safety checks</div>`;

        const references = ["score_ref", "confidence_ref", "risk_ref"]
            .map(key => decision.analysis ? decision.analysis[key] : null)
            .filter(Boolean)
            .map(ref => `
                <span class="provenance-chip" title="${escapeDecisionHtml(ref.id)}">
                    ${escapeDecisionHtml(ref.resource_type)} · ${escapeDecisionHtml(ref.id)}
                </span>
            `).join("");

        const paneActive = name => (activeBriefTab === name ? " active" : "");

        decisionBriefBody.innerHTML = `
            <div class="tabpane${paneActive("setup")}" id="brief-pane-setup" data-brief-pane="setup">
                <section class="decision-brief-section">
                    <h4>${historicalPlan ? "Historical universe eligibility" : "Universe eligibility"}</h4>
                    <div id="decision-eligibility-depth" class="decision-depth-loading">
                        <i class="fa-solid fa-circle-notch fa-spin"></i> Loading persisted assessment…
                    </div>
                </section>

                ${renderTradePlaybook(decision, decisionTradePlanFreshness(decision))}

                ${renderTradePlan(decision.trade_plan, meta.decision_type, meta.direction, decisionTradePlanFreshness(decision))}

                <section class="decision-brief-section" id="decision-portfolio-impact-section">
                    <h4>Portfolio impact</h4>
                    <div id="decision-portfolio-impact" class="decision-portfolio-impact">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Checking your holdings…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section decision-chart-section">
                    <div class="decision-brief-section-header">
                        <h4 id="decision-chart-title">Intraday price context · 5 minute</h4>
                        <span id="decision-chart-status" class="chart-freshness-badge no_data">LOADING</span>
                    </div>
                    <div class="decision-chart-controls" aria-label="Chart controls">
                        <div class="decision-chart-control-group" aria-label="Timeframe">
                            <button type="button" class="decision-chart-control" data-chart-timeframe="5m">5m</button>
                            <button type="button" class="decision-chart-control" data-chart-timeframe="15m">15m</button>
                        </div>
                        <div class="decision-chart-control-group" aria-label="Bar range">
                            <button type="button" class="decision-chart-control" data-chart-limit="60">60</button>
                            <button type="button" class="decision-chart-control" data-chart-limit="120">120</button>
                            <button type="button" class="decision-chart-control" data-chart-limit="300">300</button>
                            <button type="button" class="decision-chart-control" data-chart-limit="500">500</button>
                        </div>
                    </div>
                    <p id="decision-chart-meta" class="decision-chart-meta">Loading persisted OHLCV…</p>
                    <div id="decision-chart-warning" class="decision-chart-warning" hidden></div>
                    <div class="decision-chart-frame">
                        <div id="decision-chart-canvas" class="decision-chart-canvas"></div>
                        <button id="decision-chart-open-fullscreen" class="decision-chart-open-fullscreen" type="button"
                            aria-label="Open dedicated price chart" title="Open dedicated price chart">
                            <i class="fa-solid fa-expand"></i>
                        </button>
                    </div>
                    <div class="decision-chart-legend">
                        <span><i class="legend-box entry"></i> Entry zone</span>
                        <span><i class="legend-line stop"></i> Invalidation</span>
                        <span><i class="legend-line target"></i> Targets</span>
                        <span><i class="legend-line ma"></i> Moving average</span>
                        <span><i class="legend-box atr"></i> ATR band</span>
                        <span><i class="legend-box volume"></i> Volume</span>
                        <span class="legend-note"><i class="legend-price-marker"></i> Marker color: quote above/below candle close</span>
                    </div>
                </section>
            </div>

            <div class="tabpane${paneActive("analysis")}" id="brief-pane-analysis" data-brief-pane="analysis">
                <section class="decision-brief-section">
                    <h4>Score · confidence · risk</h4>
                    <p class="analysis-section-intro">
                        Read the three headline assessments first. Expand a category, then a component,
                        only when you need the recorded rationale and inputs.
                    </p>
                    <div id="decision-analysis-depth" class="analysis-depth-grid">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Loading analytical artifacts…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section" id="decision-counterfactual-section">
                    <h4>Why not a trade?</h4>
                    <p class="analysis-section-intro">
                        Exact math comparing this decision's saved values against today's
                        thresholds — never a re-run of the score, confidence, or risk itself.
                    </p>
                    <div id="decision-counterfactual-panel" class="decision-counterfactual-panel">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Computing gap to TRADE…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section">
                    <h4>Safety &amp; quality gates</h4>
                    ${gatesSummary}
                    <div class="decision-gates-list">${gateRows}</div>
                </section>
            </div>

            <div class="tabpane${paneActive("context")}" id="brief-pane-context" data-brief-pane="context">
                <section class="decision-brief-section">
                    <h4>Session &amp; market context</h4>
                    <p class="analysis-section-intro">
                        Trading-day session state, the regime/market-health reading saved with
                        this decision, and your own curated research links. No live news feed,
                        no AI-written commentary.
                    </p>
                    <div id="decision-context-lane" class="decision-context-lane">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Loading session &amp; market context…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section">
                    <h4>Data sources</h4>
                    <p class="analysis-section-intro">
                        Exactly which stored records this decision's numbers were pulled from —
                        useful if you ever need to trace a value back to where it came from.
                    </p>
                    <div class="decision-provenance">
                        ${references || '<span class="text-muted">No source references recorded for this decision.</span>'}
                    </div>
                </section>
            </div>

            <div class="tabpane${paneActive("response")}" id="brief-pane-response" data-brief-pane="response">
                <section class="decision-brief-section">
                    <h4>Your response</h4>
                    <p class="analysis-section-intro">
                        Every recommendation gets your recorded response — accepted, rejected,
                        or ignored. It's the only real feedback ATHENA's future tuning can ever
                        learn from.
                    </p>
                    <div id="decision-journal-panel" class="decision-journal-panel">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Loading your response…
                        </div>
                    </div>
                </section>
            </div>

            <!-- DT-3 (owner workstation refactor): split out of the old
                 "Decision History" tab — Decision Timeline moved here from
                 the always-visible hero (it was crowding the hero on every
                 tab, not just when reviewing history), Similar past setups
                 moved here from the Response tab (owner: response/outcome
                 recording is a distinct action from browsing history). -->
            <div class="tabpane${paneActive("history")}" id="brief-pane-history" data-brief-pane="history">
                <section class="decision-brief-section decision-timeline-section">
                    <div class="decision-brief-section-header">
                        <h4>Decision timeline</h4>
                        <span class="decision-timeline-hint">Click an entry to view ATHENA's assessment at that point in time</span>
                    </div>
                    <div id="decision-history-timeline" class="decision-history-timeline"></div>
                </section>

                <section class="decision-brief-section">
                    <h4>Similar past setups</h4>
                    <p class="analysis-section-intro">
                        The closest-matching past decisions by score/confidence/risk profile,
                        pulled from your own decision history — nothing generated or predicted.
                    </p>
                    <div id="decision-analogs-panel" class="decision-analogs-panel">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Finding similar setups…
                        </div>
                    </div>
                </section>
            </div>

            <p class="decision-brief-footnote">
                Dismiss only hides this symbol in this browser until the next IST day.
                Removing a candidate stops future validation only. Decision history and replay evidence are never deleted.
            </p>
        `;

        renderDecisionTimeline(decision);
        renderExecutiveSummary();
        loadDecisionDepth(meta.decision_id);
        loadDecisionContext(meta.decision_id);
        loadDecisionChart(rawSymbol, decision.trade_plan, meta.decision_id);
        loadPortfolioImpact(rawSymbol, meta.decision_id);
        loadJournalPanel(meta.decision_id);
        loadDecisionAnalogs(meta.decision_id);
        loadDecisionCounterfactual(meta.decision_id);
        loadDecisionPlanFreshness(meta.decision_id);
        setHeaderRevalidateEnabled(true);
        setHeaderActionsEnabled(true);
    }

    async function loadDecisionDetail(decisionId) {
        if (!decisionBriefBody) return;
        decisionBriefBody.innerHTML =
            '<div class="decision-brief-empty"><i class="fa-solid fa-circle-notch fa-spin"></i><strong>Loading decision brief…</strong></div>';
        try {
            const res = await apiRequest(`/api/v1/decisions/${decisionId}`);
            if (activeDecisionId !== decisionId) return;
            if (res && res.status === "success") {
                renderDecisionBrief(res.data);
            }
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load decision detail for ${decisionId}`, err);
            renderDecisionBriefEmpty(
                "Decision brief unavailable",
                "The decision list remains available. Refresh or select another symbol."
            );
        }
    }

    function selectBriefing(decisionId) {
        activeDecisionId = decisionId;
        // Clear cross-decision caches so a stale card never renders under a new symbol
        activeDepth = null;
        activeContextData = null;
        activeJournalEntry = null;
        activeTradeOutcome = null;
        activeAnalogs = null;
        activeCounterfactual = null;
        activePlanFreshness = null;
        activeChartSeries = null;
        activeChartPlan = null;
        activeBriefQuote = null;
        if (decisionActionabilityBanner) decisionActionabilityBanner.hidden = true;
        if (typeof clearAdvisorPulsePriority === "function") clearAdvisorPulsePriority(1);
        // Toggle the active row across every symbol group in the left panel,
        // and bring the selected row into view only if it isn't already
        // (graceful selection — never yanks the panel's scroll position
        // around for a row that's already visible).
        if (decisionsCarouselContainer) {
            const activeRows = [];
            decisionsCarouselContainer.querySelectorAll(".symbol-row").forEach(c => {
                const isActive = c.getAttribute("data-id") === decisionId;
                c.classList.toggle("active", isActive);
                if (isActive) activeRows.push(c);
            });
            const containerRect = decisionsCarouselContainer.getBoundingClientRect();
            const visibleActiveRow = activeRows.find(c => {
                const rowRect = c.getBoundingClientRect();
                return rowRect.bottom > containerRect.top && rowRect.top < containerRect.bottom;
            });
            const rowToScroll = visibleActiveRow || activeRows[0];
            rowToScroll?.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" });
        }

        // Selecting a symbol resets only the center detail panel to the top —
        // the left symbol list and right Reasoning Trace panel keep whatever
        // scroll position they were already at (owner requirement).
        resetDecisionBriefHeaderDensity();

        // Load selected instrument brief and its independent reasoning trace.
        loadDecisionDetail(decisionId);
        loadDecisionTrace(decisionId);
    }

    // Symbol Re-validate now lives inside Advisor Status, where the stale /
    // expired / review-mode reason is shown next to the corrective action.
    function setHeaderRevalidateEnabled(enabled) {
        if (!decisionBriefRevalidateHeader) return;
        decisionBriefRevalidateHeader.disabled = !enabled;
    }

    // Owner-reported: with no decision selected (empty state, zero-filter-
    // results, or a failed load), Open Chart/Compare/the "more" overflow
    // toggle stayed clickable — there's nothing for them to act on, so they
    // must disable together with Re-validate rather than being a separate,
    // easily-missed case.
    function setHeaderActionsEnabled(enabled) {
        if (decisionBriefOpenChart) decisionBriefOpenChart.disabled = !enabled;
        if (decisionBriefCompare) decisionBriefCompare.disabled = !enabled;
        if (decisionBriefOverflowToggle) decisionBriefOverflowToggle.disabled = !enabled;
    }

    decisionBriefRevalidateHeader?.addEventListener("click", event => {
        const instrumentId = activeDecisionData && activeDecisionData.metadata
            ? activeDecisionData.metadata.instrument_id
            : null;
        if (!instrumentId) return;
        const bareSymbol = String(instrumentId).replace(/^NSE:|^BSE:/, "");
        validateSymbolsNow([bareSymbol], { button: event.currentTarget, refreshDecisions: true });
    });

    // Tab strip and action bar live in the static sticky header (not rebuilt
    // per decision), so they're wired exactly once here and read
    // activeDecisionData/activeDecisionId at click time.
    decisionBriefTabstrip?.querySelectorAll(".brief-tab").forEach(btn => {
        btn.addEventListener("click", () => switchBriefTab(btn.getAttribute("data-brief-tab")));
    });

    document.getElementById("decision-brief-dismiss")?.addEventListener("click", () => {
        if (activeDecisionData) dismissDecisionForToday(activeDecisionData);
    });
    document.getElementById("decision-brief-remove-candidate")?.addEventListener("click", async event => {
        const instrumentId = activeDecisionData && activeDecisionData.metadata
            ? activeDecisionData.metadata.instrument_id
            : null;
        if (!instrumentId) return;
        const bareSymbol = String(instrumentId).replace(/^NSE:|^BSE:/, "");
        const removed = await removeCandidateNow(bareSymbol, { button: event.currentTarget });
        if (removed) {
            event.currentTarget.disabled = true;
            event.currentTarget.querySelector("i").className = "fa-solid fa-check";
            event.currentTarget.querySelector("span").textContent = "Removed";
        }
    });
    document.getElementById("decision-brief-export")?.addEventListener("click", event => {
        const decisionId = activeDecisionData && activeDecisionData.metadata
            ? activeDecisionData.metadata.decision_id
            : null;
        if (!decisionId) return;
        exportDecisionBrief(decisionId, event.currentTarget);
    });
    decisionBriefOpenChart?.addEventListener("click", () => {
        openChartModal();
    });
    document.getElementById("decision-brief-news")?.addEventListener("click", () => {
        switchBriefTab("context");
    });
    decisionBriefCompare?.addEventListener("click", () => {
        openCompareModal();
    });
