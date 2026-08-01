    const savedSymbolSet = new Set();
    const eligibilityDetailBySymbol = new Map();
    // IX-4a/IX-4b: shared index-filter catalog/cache — one fetch per index
    // key, reused by both the Universe filter and the Workbench Results
    // filter, never a second membership mapping.
    let universeIndexCatalog = [];
    const universeIndexMembersCache = new Map();
    let universeIndexMembersRequestToken = 0;

    async function fetchIndexMembers(key) {
        if (universeIndexMembersCache.has(key)) return universeIndexMembersCache.get(key);
        const res = await apiRequest(
            `/api/v1/market/index-intelligence/${encodeURIComponent(key)}/members`,
            { skipToast: true },
        );
        const data = res && res.data ? res.data : null;
        const members = data && Array.isArray(data.members) ? data.members : [];
        const symbols = new Set(
            members.filter(m => m.resolved).map(m => String(m.symbol).toUpperCase())
        );
        const unresolvedCount = members.filter(m => !m.resolved).length;
        const cacheEntry = { symbols, unresolvedCount };
        universeIndexMembersCache.set(key, cacheEntry);
        return cacheEntry;
    }
    let validateOverlayStartedAt = 0;
    let validateOverlayTimerId = null;
    let validationWorkbenchState = {
        funnel: null,
        runs: [],
        universe: {},
        qualified: [],
        universeNote: null,
    };
    let validationResultsRenderTimerId = null;
    const indexLeadershipModal = document.getElementById("index-leadership-modal");
    const indexLeadershipOpen = document.getElementById("index-leadership-open");
    const indexLeadershipClose = document.getElementById("index-leadership-modal-close");
    const indexLeadershipRetry = document.getElementById("index-leadership-retry");

    indexLeadershipOpen?.addEventListener("click", () => openModal(indexLeadershipModal));
    indexLeadershipClose?.addEventListener("click", () => closeModal(indexLeadershipModal));
    indexLeadershipRetry?.addEventListener("click", async () => {
        indexLeadershipRetry.disabled = true;
        indexLeadershipRetry.classList.add("is-loading");
        try {
            await loadIndexLeadership();
        } finally {
            indexLeadershipRetry.disabled = false;
            indexLeadershipRetry.classList.remove("is-loading");
        }
    });
    window.addEventListener("click", event => {
        if (event.target === indexLeadershipModal) closeModal(indexLeadershipModal);
    });

    const validationReportModal = document.getElementById("validation-report-modal");
    const validationReportTitle = document.getElementById("validation-report-title");
    const validationReportBody = document.getElementById("validation-report-body");
    document.getElementById("validation-report-close")?.addEventListener("click", () => closeModal(validationReportModal));
    window.addEventListener("click", event => {
        if (event.target === validationReportModal) closeModal(validationReportModal);
    });

    // Blocking overlay while a validate (ingest + score) is in flight (owner
    // UX request) — otherwise only the clicked button showed a spinner while
    // the rest of the page stayed fully interactive, risking the trader
    // acting on stale/half-updated state mid-run. Centralized here so every
    // caller of validateSymbolsNow gets it for free.
    function formatValidationSymbolSummary(symbols, limit = 8) {
        const list = [...new Set(
            (symbols || [])
                .map(s => String(s || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, ""))
                .filter(Boolean)
        )];
        if (!list.length) return "No symbols";
        if (list.length <= limit) return list.join(", ");
        return `${list.length} symbols · ${list.slice(0, limit).join(", ")} +${list.length - limit} more`;
    }

    function updateValidateOverlayTimer() {
        if (!validateOverlayTimer || !validateOverlayStartedAt) return;
        const elapsedSeconds = Math.max(0, Math.floor((Date.now() - validateOverlayStartedAt) / 1000));
        validateOverlayTimer.textContent = `Elapsed ${elapsedSeconds}s`;
    }

    function showValidateOverlay(symbols) {
        if (!validateOverlay) return;
        validateOverlayStartedAt = Date.now();
        if (validateOverlaySymbols) {
            validateOverlaySymbols.textContent = formatValidationSymbolSummary(symbols);
            validateOverlaySymbols.title = (symbols || []).join(", ");
        }
        updateValidateOverlayTimer();
        if (validateOverlayTimerId != null) clearInterval(validateOverlayTimerId);
        validateOverlayTimerId = setInterval(updateValidateOverlayTimer, 1000);
        if (validateOverlayDetail) {
            validateOverlayDetail.textContent = "Ingesting quotes and recomputing the decision…";
        }
        validateOverlay.hidden = false;
        validateOverlay.setAttribute("aria-hidden", "false");
    }

    function hideValidateOverlay() {
        if (!validateOverlay) return;
        validateOverlay.hidden = true;
        validateOverlay.setAttribute("aria-hidden", "true");
        if (validateOverlayTimerId != null) {
            clearInterval(validateOverlayTimerId);
            validateOverlayTimerId = null;
        }
    }

    validateOverlayClose?.addEventListener("click", () => {
        hideValidateOverlay();
        showToast("Validation continues in the background. Watch the list status for the result.", "info");
    });

    function latestValidationExclusion(data, symbol) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        const pipeline = data && data.detail && data.detail.pipeline ? data.detail.pipeline : {};
        const members = pipeline && pipeline.universe_members ? pipeline.universe_members : {};
        const member = members[bare] || Object.values(members).find(item => {
            if (!item || typeof item !== "object") return false;
            const memberSymbol = String(item.symbol || "").toUpperCase();
            const memberInstrument = String(item.instrument_id || "").toUpperCase();
            return memberSymbol === bare || memberInstrument === `NSE:${bare}` || memberInstrument.endsWith(`:${bare}`);
        });
        if (!member || member.included !== false) return null;
        const reasons = Array.isArray(member.exclusion_reasons) ? member.exclusion_reasons : [];
        return {
            symbol: bare,
            summary: String(member.eligibility_summary || "excluded by latest validation"),
            reason: reasons.length ? String(reasons[0]) : "",
        };
    }

    function latestDecisionForSymbol(symbol) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return null;
        return traceDecisionsBySymbol.get(bare) || null;
    }

    function currentOpenableDecisionForSymbol(symbol) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return null;
        const d = traceDecisionsBySymbol.get(bare);
        if (!d || !d.metadata) return null;
        if (typeof isCurrentDecisionListRow === "function" && !isCurrentDecisionListRow(d)) return null;
        if (typeof decisionInstrumentKey === "function" && dismissedDecisionSymbols.has(decisionInstrumentKey(d))) return null;
        return d;
    }

    async function refreshDecisionCacheForValidationResults() {
        if (typeof fetchAllDecisionPages !== "function" || typeof latestDecisionPerInstrument !== "function") {
            return;
        }
        try {
            const raw = await fetchAllDecisionPages();
            allTraceDecisionsList = raw;
            traceDecisionsList = latestDecisionPerInstrument(raw);
            rebuildTraceDecisionsBySymbolIndex();
        } catch (err) {
            console.warn("Validation workbench could not refresh Decisions cache", err);
        }
    }

    function validationReportOutcome(data, symbol) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        const decision = latestDecisionForSymbol(bare);
        const exclusion = latestValidationExclusion(data, bare);
        if (exclusion) {
            return {
                label: "Excluded",
                tone: "danger",
                detail: exclusion.reason || exclusion.summary || "Latest validation excluded this symbol.",
                decision,
            };
        }
        if (decision && decision.metadata) {
            const type = decisionListSectionType(decision);
            const stance = decisionStance(decision.metadata.decision_type, decision.metadata.direction);
            if (type === "TRADE") {
                return { label: stance.label || "Trade", tone: "good", detail: "Current TradePlan available. Review Advisor Status before action.", decision };
            }
            if (type === "WATCH") {
                return { label: "Watch", tone: "warning", detail: "Interesting setup, but ATHENA did not authorize entry yet.", decision };
            }
            if (type === "NO_TRADE") {
                return { label: "No trade", tone: "neutral", detail: "ATHENA found no current manual action for this symbol.", decision };
            }
            return { label: friendlyLabel(type), tone: "neutral", detail: "Validation completed. Review the decision for details.", decision };
        }
        const status = String(data && data.status || "").toUpperCase();
        if (status && status !== "COMPLETED") {
            return { label: status, tone: "warning", detail: "Validation did not complete cleanly. Treat existing rows as stale.", decision: null };
        }
        return { label: "Validated", tone: "neutral", detail: "Validation completed, but no current decision row was available yet.", decision: null };
    }

    function validationReportMetricValue(decision, key) {
        const source = decision && decision[key] ? decision[key] : {};
        const candidates = key === "confidence"
            ? [source.score, source.confidence, source.confidence_score, source.overall, decision?.metadata?.confidence]
            : [source.score, source.risk_score, source.total_risk_score, source.overall, decision?.metadata?.risk];
        for (const candidate of candidates) {
            const value = Number(candidate);
            if (Number.isFinite(value)) return value;
        }
        return NaN;
    }

    function renderValidationReport(symbol, response) {
        if (!validationReportModal || !validationReportBody) return;
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        const data = response && response.data ? response.data : {};
        const outcome = validationReportOutcome(data, bare);
        const decision = outcome.decision;
        const currentDecision = currentOpenableDecisionForSymbol(bare);
        const score = decision ? decisionScoreValue(decision) : NaN;
        const confidence = validationReportMetricValue(decision, "confidence");
        const risk = validationReportMetricValue(decision, "risk");
        const freshness = decision ? inferTradePlanFreshness(decision.trade_plan) : null;
        const planLabel = freshness && freshness.has_trade_plan ? formatTradePlanFreshnessBadge(freshness) : "No plan";
        const mode = String(data.as_of_mode || "").toLowerCase();
        const modeLabel = mode === "live" ? "Live" : mode === "session_close" ? "Session close" : "Validation";
        const asOf = data.as_of ? formatDecisionTime(data.as_of) : "Unknown time";
        const isSaved = savedSymbolSet.has(bare);
        const canInspectTrace = Boolean(universeCache[bare]);
        const reportDecisionOpenable = Boolean(currentDecision && outcome.label !== "Excluded");

        if (validationReportTitle) validationReportTitle.textContent = `${bare} — Validation Report`;
        validationReportBody.innerHTML = `
            <div class="validation-report-hero tone-${outcome.tone}">
                <div>
                    <span class="validation-report-kicker">${escapeDecisionHtml(modeLabel)} · ${escapeDecisionHtml(asOf)}</span>
                    <strong>${escapeDecisionHtml(outcome.label)}</strong>
                    <p>${escapeDecisionHtml(outcome.detail)}</p>
                </div>
            </div>
            <div class="validation-report-metrics">
                <div class="validation-report-metric"><span>Score</span><strong>${Number.isFinite(score) ? score.toFixed(1) : "—"}</strong></div>
                <div class="validation-report-metric"><span>Confidence</span><strong>${Number.isFinite(confidence) ? `${confidence.toFixed(1)}%` : "—"}</strong></div>
                <div class="validation-report-metric"><span>Risk</span><strong>${Number.isFinite(risk) ? `${risk.toFixed(1)}` : "—"}</strong></div>
                <div class="validation-report-metric validation-report-plan-metric"><span>Plan status</span><strong>${escapeDecisionHtml(planLabel)}</strong></div>
            </div>
            <div class="validation-report-actions">
                <button type="button" id="validation-report-open-decision" class="inspect-btn" ${reportDecisionOpenable ? "" : "disabled"} title="${reportDecisionOpenable ? "Open current decision" : "No current decision row to open"}">
                    <i class="fa-solid fa-brain"></i> Open decision
                </button>
                <button type="button" id="validation-report-trace" class="inspect-btn" ${canInspectTrace ? "" : "disabled"}>
                    <i class="fa-solid fa-search"></i> Inspect trace
                </button>
                <button type="button" id="validation-report-save" class="inspect-btn">
                    <i class="fa-solid fa-bookmark"></i> ${isSaved ? "Remove saved" : "Save symbol"}
                </button>
                <button type="button" id="validation-report-revalidate" class="inspect-btn">
                    <i class="fa-solid fa-arrows-rotate"></i> Re-validate
                </button>
            </div>
        `;
        document.getElementById("validation-report-open-decision")?.addEventListener("click", async () => {
            closeModal(validationReportModal);
            await openDecisionForSymbol(bare);
        });
        document.getElementById("validation-report-trace")?.addEventListener("click", () => {
            if (typeof window.openTraceModal === "function") window.openTraceModal(bare);
        });
        document.getElementById("validation-report-save")?.addEventListener("click", async event => {
            await toggleSavedSymbolNow(bare, { button: event.currentTarget });
            renderValidationReport(bare, response);
        });
        document.getElementById("validation-report-revalidate")?.addEventListener("click", async event => {
            await validateSymbolsNow([bare], {
                button: event.currentTarget,
                refreshDecisions: true,
                showReport: true,
            });
        });
        openModal(validationReportModal);
    }

    function showDecisionOpenOverlay(symbol) {
        const overlay = document.getElementById("decision-open-overlay");
        if (!overlay) return;
        const symbolEl = document.getElementById("decision-open-overlay-symbol");
        if (symbolEl) symbolEl.textContent = symbol || "";
        overlay.hidden = false;
        overlay.setAttribute("aria-hidden", "false");
    }

    function hideDecisionOpenOverlay() {
        const overlay = document.getElementById("decision-open-overlay");
        if (!overlay) return;
        overlay.hidden = true;
        overlay.setAttribute("aria-hidden", "true");
    }

    async function openDecisionForSymbol(symbol) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return;
        showDecisionOpenOverlay(bare);
        try {
            const searchEl = document.getElementById("briefing-search");
            const stanceEl = document.getElementById("decisions-filter-stance");
            const typeEl = document.getElementById("decisions-filter-type");
            const sortEl = document.getElementById("decisions-sort");
            if (searchEl) searchEl.value = "";
            if (stanceEl) stanceEl.value = "all";
            if (typeEl) typeEl.value = "all";
            if (sortEl) sortEl.value = "newest";
            if (typeof switchTab === "function") {
                window.history.pushState({ tabId: "decisions" }, "", "/dashboard/decisions");
                const tabLoad = switchTab("decisions", { skipLoad: true });
                if (tabLoad && typeof tabLoad.then === "function") {
                    await tabLoad;
                }
            }
            if (typeof loadDecisionsWorkspace === "function") {
                const selected = await loadDecisionsWorkspace({
                    preferInstrumentId: bare,
                    strictPreferInstrumentId: true,
                });
                if (!selected) {
                    showToast(`${bare} is not in the current Decisions list`, "warning");
                }
            }
        } finally {
            hideDecisionOpenOverlay();
        }
    }

    /** Ensure candidates exist, then run scoped validate (ingest + score). */
    async function validateSymbolsNow(symbols, { button = null, refreshDecisions = false, showReport = false } = {}) {
        const list = [...new Set(
            (symbols || [])
                .map(s => String(s || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, ""))
                .filter(Boolean)
        )];
        if (!list.length) {
            showToast("Enter a symbol", "danger");
            return null;
        }
        const prev = button ? button.innerHTML : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validating…';
        }
        showValidateOverlay(list);
        try {
            for (const symbol of list) {
                try {
                    await apiRequest("/api/v1/market/candidates", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ symbol }),
                        skipToast: true,
                    });
                } catch (err) {
                    const detail = err?.data?.detail;
                    showToast(
                        typeof detail === "string" && detail.trim()
                            ? detail
                            : `Could not add ${symbol}`,
                        "danger"
                    );
                    return null;
                }
            }
            showToast(
                `Validating ${formatValidationSymbolSummary(list)} — live during session; after hours uses last session close…`,
                "success"
            );
            let valRes;
            try {
                valRes = await apiRequest("/api/v1/market/validate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ symbols: list }),
                    skipToast: true,
                });
            } catch (err) {
                const detail = err?.data?.detail;
                const title = err?.data?.title;
                let message =
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : (typeof title === "string" && title.trim() ? title : "Validate failed");
                if (/FRESHNESS|quotes are .* behind/i.test(message)) {
                    message =
                        "Quotes are too old relative to the validation clock. " +
                        "After hours, ATHENA uses last session close — if this still fails, " +
                        "Kite has no usable session quotes yet. Retry during market hours.";
                } else if (/kite HTTP 429|too many requests|NetworkException/i.test(message)) {
                    message =
                        "Kite rate limit hit. Wait about a minute, then re-validate fewer symbols. " +
                        "Existing rows may be stale until refresh succeeds.";
                }
                err.userMessage = message;
                showToast(message, "danger");
                throw err;
            }
            const d = (valRes && valRes.data) ? valRes.data : {};
            const ok = String(d.status || "").toUpperCase() === "COMPLETED";
            const mode = String(d.as_of_mode || "").toLowerCase();
            let asOfLabel = "";
            if (d.as_of) {
                const asOfDate = new Date(d.as_of);
                if (!Number.isNaN(asOfDate.getTime())) {
                    asOfLabel = asOfDate.toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        hour: "numeric",
                        minute: "2-digit",
                        hour12: true,
                        timeZone: "Asia/Kolkata",
                    });
                }
            }
            let modeLabel = "";
            if (mode === "session_close" && asOfLabel) {
                modeLabel = ` · session-close analysis as of ${asOfLabel} IST`;
            } else if (mode === "live" && asOfLabel) {
                modeLabel = ` · live as of ${asOfLabel} IST`;
            } else if (mode === "session_close") {
                modeLabel = " · session-close analysis (not live)";
            }
            showToast(
                `${list.join(", ")}: ${d.status || "done"}${modeLabel} · Eligible ${d.eligible ?? "—"} · ` +
                `Excluded ${d.excluded ?? "—"} · decisions ${d.decisions ?? "—"}`,
                ok ? (mode === "session_close" ? "warning" : "success") : "warning"
            );
            if (typeof loadMarketIntelligence === "function") {
                await loadMarketIntelligence();
            }
            // Owner-reported (2026-08-01): this used to also call
            // loadDecisionsWorkspace(), which re-fetches every decision page
            // a second time — loadMarketIntelligence() above already
            // refreshed the exact same shared cache via
            // refreshDecisionCacheForValidationResults(). Re-apply the view
            // over that already-fresh cache instead of fetching it twice.
            if (refreshDecisions && typeof applyDecisionsView === "function") {
                applyDecisionsView({
                    preferInstrumentId: list.length === 1 ? list[0] : null,
                });
            }
            if (list.length === 1) {
                const exclusion = latestValidationExclusion(d, list[0]);
                if (exclusion) {
                    showToast(
                        `${exclusion.symbol}: latest revalidation excluded it; no current TradePlan.`,
                        "warning"
                    );
                    if (typeof setAdvisorPulse === "function") {
                        setAdvisorPulse(
                            `${exclusion.symbol} · no current plan · ${exclusion.reason || exclusion.summary}`,
                            "warning",
                            3
                        );
                    }
                }
            }
            if (showReport && list.length === 1) {
                renderValidationReport(list[0], valRes);
            }
            return valRes;
        } finally {
            if (button) {
                button.disabled = false;
                if (prev != null) button.innerHTML = prev;
            }
            hideValidateOverlay();
        }
    }

    async function removeCandidateNow(symbol, { button = null } = {}) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return false;
        const confirmed = window.confirm(
            `Remove ${bare} from future validation?\n\n` +
            "Existing decisions, traces, and replay evidence will be preserved."
        );
        if (!confirmed) return false;

        const previous = button ? button.innerHTML : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing…';
        }
        try {
            await apiRequest(
                `/api/v1/market/candidates/${encodeURIComponent(bare)}`,
                { method: "DELETE", skipToast: true }
            );
            showToast(
                `${bare} removed from future validation · decision history preserved`,
                "success"
            );
            if (typeof loadCandidateList === "function") {
                await loadCandidateList();
            }
            return true;
        } catch (err) {
            if (err?.status === 404) {
                showToast(`${bare} is not in the active validation list`, "warning");
            } else {
                const detail = err?.data?.detail;
                showToast(
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : `Failed to remove ${bare} from validation`,
                    "danger"
                );
            }
            return false;
        } finally {
            if (button && !button.disabled && previous != null) {
                button.innerHTML = previous;
            } else if (button && previous != null) {
                button.disabled = false;
                button.innerHTML = previous;
            }
        }
    }

    // Cache for universe trace results to speed up detail views
    let universeCache = {};

    // Remove only the dimension words already present in the header. Stored
    // enum values remain unchanged and continue to drive tone/evidence.
    function conciseMarketLabel(dimension, rawLabel) {
        const value = String(rawLabel || "").toUpperCase();
        if (!value) return "Unknown";
        const concise = {
            volatility: value.replace(/_?VOLATILITY/g, ""),
            gap: value === "NO_GAP" ? "NONE" : value.replace(/^GAP_?/, ""),
            momentum: value.replace(/_?MOMENTUM/g, ""),
            trend_quality: value.replace(/_?TREND_QUALITY/g, ""),
            volatility_quality: value.replace(/^VOLATILITY_?/, ""),
            breadth: value.replace(/_?BREADTH/g, ""),
        }[dimension] || value;
        return friendlyLabel(concise || "UNKNOWN");
    }

    function setMarketHeroValue(elementId, dimension, rawLabel) {
        const el = document.getElementById(elementId);
        if (!el) return;
        const raw = rawLabel || `${dimension.toUpperCase()}_UNKNOWN`;
        el.textContent = conciseMarketLabel(dimension, raw);
        el.className = `market-hero-value tone-${contextChipTone(raw)}-text`;
    }

    // Dots/bars visualize the persisted categorical result; they do not
    // create or imply a new numeric score.
    function categoricalIndicatorLevel(rawLabel) {
        const value = String(rawLabel || "").toUpperCase();
        if (!value || value.includes("UNKNOWN")) return 0;
        if (/STRONG|HEALTHY|CALM/.test(value)) return 4;
        if (/MIXED|NORMAL|FLAT/.test(value)) return 2;
        if (/WEAK|ELEVATED/.test(value)) return 1;
        return 0;
    }

    function renderCategoricalIndicator(elementId, rawLabel) {
        const host = document.getElementById(elementId);
        if (!host) return;
        const baseClass = host.classList.contains("market-bar-indicator")
            ? "market-bar-indicator"
            : "market-dot-indicator";
        host.className = `${baseClass} tone-${contextChipTone(rawLabel)}-text`;
        const level = categoricalIndicatorLevel(rawLabel);
        [...host.children].forEach((node, index) => {
            node.classList.toggle("is-active", index < level);
        });
        host.title = rawLabel
            ? `Categorical assessment: ${friendlyLabel(rawLabel)}`
            : "Categorical assessment unavailable";
    }

    // MH-3: Health Score ring from persisted MarketHealthScore.total only.
    function renderMarketHealthScore(health) {
        const valueEl = document.getElementById("market-health-score-value");
        const ringEl = document.getElementById("market-health-score-ring");
        const captionEl = document.getElementById("market-health-score-caption");
        const denomEl = ringEl && ringEl.querySelector(".market-health-score-denom");
        if (!valueEl || !ringEl || !captionEl) return;

        const score = health && health.score != null ? Number(health.score) : null;
        if (score == null || Number.isNaN(score)) {
            valueEl.textContent = "—";
            valueEl.classList.add("is-unavailable");
            if (denomEl) denomEl.hidden = true;
            ringEl.style.setProperty("--metric-progress", "0");
            ringEl.className = "market-ring market-health-score-ring is-unavailable";
            captionEl.textContent = "Unavailable";
            ringEl.title = (health && health.unavailable_reason)
                || "Score needs all six F-5 components";
            ringEl.setAttribute("aria-label", ringEl.title);
            return;
        }
        valueEl.textContent = String(Math.round(score));
        valueEl.classList.remove("is-unavailable");
        if (denomEl) denomEl.hidden = false;
        ringEl.style.setProperty("--metric-progress", String(Math.max(0, Math.min(100, score))));
        const scoreTone = score >= 70 ? "good" : score >= 45 ? "warn" : "bad";
        ringEl.className = `market-ring market-health-score-ring tone-${scoreTone}-text`;
        captionEl.textContent = "F-5 total";
        ringEl.title = health.explanation || `Persisted F-5 score ${score}/100`;
        ringEl.setAttribute("aria-label", ringEl.title);
    }

    // MH-3: Universe ADV/DEC/neutral — never imply exchange-wide NSE breadth.
    function renderUniverseBreadth(breadth, breadthLabel) {
        const pctEl = document.getElementById("market-breadth-pct");
        const countsEl = document.getElementById("market-breadth-counts");
        const captionEl = document.getElementById("market-breadth-caption");
        const ringEl = document.getElementById("market-breadth-ring");
        if (!pctEl || !countsEl || !captionEl || !ringEl) return;

        if (!breadth) {
            pctEl.textContent = "—";
            pctEl.className = "market-hero-value tone-unknown-text";
            countsEl.textContent = "";
            countsEl.hidden = true;
            captionEl.textContent = "Run validation";
            ringEl.style.setProperty("--metric-progress", "0");
            ringEl.className = "market-ring market-breadth-ring is-unavailable";
            ringEl.title = "Run validation to compute universe breadth";
            ringEl.setAttribute("aria-label", ringEl.title);
            return;
        }
        const pct = breadth.advance_pct == null ? null : Number(breadth.advance_pct);
        pctEl.textContent = pct == null || Number.isNaN(pct)
            ? "—"
            : `${pct.toFixed(0)}%`;
        pctEl.className = `market-hero-value tone-${contextChipTone(breadthLabel)}-text`;
        countsEl.hidden = false;
        countsEl.textContent =
            `ADV ${breadth.advances} · DEC ${breadth.declines} · NEU ${breadth.neutral}`;
        captionEl.textContent = conciseMarketLabel("breadth", breadthLabel || "BREADTH_UNKNOWN");
        const progress = pct == null || Number.isNaN(pct)
            ? 0
            : Math.max(0, Math.min(100, pct));
        ringEl.style.setProperty("--metric-progress", String(progress));
        ringEl.className = `market-ring market-breadth-ring tone-${contextChipTone(breadthLabel)}-text`;
        const coverage = breadth.coverage == null
            ? "unknown"
            : `${(Number(breadth.coverage) * 100).toFixed(0)}%`;
        ringEl.title = `Universe breadth ${pctEl.textContent}; coverage ${coverage}`;
        ringEl.setAttribute("aria-label", ringEl.title);
    }

    function renderCloseSparkline(svgEl, closes) {
        if (!svgEl) return;
        const values = (closes || []).map(Number).filter((n) => !Number.isNaN(n));
        if (values.length < 2) {
            svgEl.innerHTML = "";
            svgEl.classList.add("is-empty");
            return;
        }
        svgEl.classList.remove("is-empty");
        const w = 120;
        const h = 28;
        const pad = 2;
        const min = Math.min(...values);
        const max = Math.max(...values);
        const span = max - min || 1;
        const points = values.map((v, i) => {
            const x = pad + (i / (values.length - 1)) * (w - pad * 2);
            const y = h - pad - ((v - min) / span) * (h - pad * 2);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
        svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
        svgEl.innerHTML = `<polyline points="${points}"></polyline>`;
    }

    function renderMarketSparklines(summary) {
        const niftySvg = document.getElementById("market-sparkline-nifty");
        const vixSvg = document.getElementById("market-sparkline-vix");
        const vixEl = document.getElementById("market-vix-level");
        const sparks = (summary && summary.sparklines) || {};
        renderCloseSparkline(niftySvg, sparks.nifty_closes);
        renderCloseSparkline(vixSvg, sparks.vix_closes);
        if (!vixEl) return;
        const vix = summary && summary.vix;
        if (!vix || vix.level == null) {
            vixEl.textContent = "VIX —";
            return;
        }
        const level = Number(vix.level);
        const change = vix.change_pct == null ? null : Number(vix.change_pct);
        const changeLabel = change == null || Number.isNaN(change)
            ? ""
            : ` (${change >= 0 ? "+" : ""}${change.toFixed(2)}%)`;
        vixEl.textContent = `VIX ${level.toFixed(2)}${changeLabel}`;
    }

    function renderMarketSummaryHero(summary) {
        const trendBadge = document.getElementById("regime-trend-badge");
        const volBadge = document.getElementById("regime-vol-badge");
        const gapBadge = document.getElementById("regime-gap-badge");
        const evidenceText = document.getElementById("regime-evidence-text");
        const asOfEl = document.getElementById("market-summary-asof");
        if (!trendBadge || !volBadge || !gapBadge || !evidenceText) return;

        const regime = summary && summary.regime;
        const health = (summary && summary.market_health) || {};

        if (asOfEl) {
            asOfEl.textContent = summary && summary.as_of
                ? `As of ${formatDecisionTime(summary.as_of)}`
                : "";
        }

        if (regime) {
            const trendRaw = regime.trend || "TREND_UNKNOWN";
            trendBadge.textContent = friendlyLabel(trendRaw);
            trendBadge.className = `market-hero-value tone-${contextChipTone(trendRaw)}-text`;

            const volRaw = regime.volatility || "VOLATILITY_UNKNOWN";
            setMarketHeroValue("regime-vol-badge", "volatility", volRaw);

            const gapRaw = regime.gap || "GAP_UNKNOWN";
            setMarketHeroValue("regime-gap-badge", "gap", gapRaw);
            const gapIndicator = document.getElementById("market-gap-indicator");
            if (gapIndicator) {
                const icon = gapRaw === "GAP_UP"
                    ? "fa-arrow-up"
                    : gapRaw === "GAP_DOWN"
                        ? "fa-arrow-down"
                        : "fa-minus";
                gapIndicator.className =
                    `fas ${icon} market-gap-indicator tone-${contextChipTone(gapRaw)}-text`;
            }

            let evidence = regime.explanation || health.explanation
                || "No attribution summary available.";
            evidence = evidence
                .replace(/NORMAL_VOLATILITY/g, "Normal volatility")
                .replace(/HIGH_VOLATILITY/g, "High volatility")
                .replace(/LOW_VOLATILITY/g, "Low volatility")
                .replace(/VOLATILITY_UNKNOWN/g, "Volatility unknown (VIX missing)")
                .replace(/BULL_TREND/g, "Bullish")
                .replace(/BEAR_TREND/g, "Bearish")
                .replace(/GAP_DOWN/g, "Gap down")
                .replace(/GAP_UP/g, "Gap up")
                .replace(/NO_GAP/g, "No gap")
                .replace(/SIDEWAYS/g, "Sideways");
            if (health.unavailable_reason && health.score == null) {
                evidence = `${evidence} Health score: ${health.unavailable_reason}`;
            }
            evidenceText.textContent = evidence;
        } else {
            trendBadge.textContent = "Unknown";
            trendBadge.className = "market-hero-value tone-unknown-text";
            volBadge.textContent = "Unknown";
            volBadge.className = "market-hero-value tone-unknown-text";
            gapBadge.textContent = "Unknown";
            gapBadge.className = "market-hero-value tone-unknown-text";
            evidenceText.textContent =
                "No regime assessment from the latest validation run yet. " +
                "Re-run ./athena-daily or Validate All — regime and F-5 inputs are written from validation.";
        }

        const dimensions = health.dimensions || {};
        const momentum = dimensions.momentum || "MOMENTUM_UNKNOWN";
        const trendQuality = dimensions.trend_quality || "TREND_QUALITY_UNKNOWN";
        const volatilityQuality = dimensions.volatility || "VOLATILITY_UNKNOWN";
        const breadthLabel = dimensions.breadth || "BREADTH_UNKNOWN";
        setMarketHeroValue("market-momentum-value", "momentum", momentum);
        setMarketHeroValue("market-trend-quality-value", "trend_quality", trendQuality);
        setMarketHeroValue(
            "market-volatility-quality-value",
            "volatility_quality",
            volatilityQuality
        );
        renderCategoricalIndicator("market-momentum-indicator", momentum);
        renderCategoricalIndicator("market-trend-quality-indicator", trendQuality);
        renderCategoricalIndicator("market-volatility-quality-indicator", volatilityQuality);
        renderMarketHealthScore(health);
        renderUniverseBreadth(summary && summary.breadth, breadthLabel);
        renderMarketSparklines(summary);
    }

    function indexNumericValue(value) {
        if (value == null || value === "") return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function indexLevelLabel(value) {
        const number = indexNumericValue(value);
        if (number === null) return "Level unavailable";
        return new Intl.NumberFormat("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(number);
    }

    function indexChangeLabel(value) {
        const number = indexNumericValue(value);
        if (number === null) return "Change unavailable";
        return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
    }

    function indexChangeTone(value) {
        const number = indexNumericValue(value);
        if (number === null || number === 0) return "neutral";
        return number > 0 ? "positive" : "negative";
    }

    function indexSessionLabel(session, asOf) {
        const observed = asOf ? `Observed ${formatDecisionTime(asOf)}` : "Observation unavailable";
        if (session && session.is_market_open === true) {
            return `Market live · ${observed}`;
        }
        if (session && session.is_market_open === false) {
            return `${session.message || "Market closed"} · ${observed}`;
        }
        return `Market hours unavailable · ${observed}`;
    }

    function indexConstituentContextMarkup(context) {
        if (!context) {
            return '<div class="index-membership is-incomplete">Membership snapshot unavailable</div>';
        }
        const total = Number(context.total_members) || 0;
        const resolved = Number(context.resolved_members) || 0;
        const covered = Number(context.decision_covered_members) || 0;
        const age = Math.max(0, Number(context.membership_age_days) || 0);
        const effective = escapeDecisionHtml(context.effective_date || "Unknown date");
        const source = typeof context.source_url === "string" && context.source_url.startsWith("https://")
            ? context.source_url
            : null;
        const provenance = source
            ? `<a href="${escapeDecisionHtml(source)}" target="_blank" rel="noopener noreferrer">Official membership</a>`
            : "Official membership source unavailable";
        const snapshotLabel = age === 0 ? "updated today" : `${age}d old`;

        if (context.breadth_status === "AVAILABLE") {
            return `
                <div class="index-membership">
                    <div class="index-membership-meta">
                        <span>${total} members · ${resolved} resolved</span>
                        <span>${effective} · ${snapshotLabel}</span>
                    </div>
                    <div class="index-board-breadth" aria-label="Current ATHENA board composition">
                        <strong>${escapeDecisionHtml(context.trade_breadth_pct)}% Trade breadth</strong>
                        <span>Trade ${Number(context.trade_count) || 0} · Watch ${Number(context.watch_count) || 0} · No trade ${Number(context.no_trade_count) || 0}</span>
                    </div>
                    <small>${provenance}</small>
                </div>
            `;
        }

        const unresolved = Array.isArray(context.unresolved_symbols) ? context.unresolved_symbols : [];
        const missing = Array.isArray(context.missing_decision_symbols) ? context.missing_decision_symbols : [];
        const issueLabel = unresolved.length
            ? `${unresolved.length} unresolved instrument${unresolved.length === 1 ? "" : "s"}`
            : `${missing.length} current decision${missing.length === 1 ? "" : "s"} missing`;
        const issueSymbols = unresolved.length ? unresolved : missing;
        return `
            <div class="index-membership is-incomplete">
                <div class="index-membership-meta">
                    <span>${total} members · ${resolved} resolved · ${covered} covered</span>
                    <span>${effective} · ${snapshotLabel}</span>
                </div>
                <strong>Breadth unavailable · ${escapeDecisionHtml(issueLabel)}</strong>
                ${issueSymbols.length ? `
                    <details>
                        <summary>Review affected symbols</summary>
                        <span>${issueSymbols.map(symbol => escapeDecisionHtml(symbol)).join(", ")}</span>
                    </details>
                ` : ""}
                <small>${provenance}</small>
            </div>
        `;
    }

    // IX-8: the leader/laggard summary already renders each item's own
    // change_pct; this surfaces ATHENA's already-computed decision breadth
    // for that same sector alongside it (item.constituents is already part
    // of the same /market/index-intelligence payload — no new fetch, no new
    // endpoint). Omitted (not a fabricated "unavailable" chip) unless the
    // breadth is actually AVAILABLE, matching indexConstituentContextMarkup's
    // own AVAILABLE-only guard.
    function indexLeadershipBreadthChip(constituents) {
        if (!constituents || constituents.breadth_status !== "AVAILABLE") return "";
        const trade = Number(constituents.trade_count) || 0;
        const watch = Number(constituents.watch_count) || 0;
        return `<small class="index-sector-breadth">${trade} Trade · ${watch} Watch</small>`;
    }

    function indexObservationMarkup(item, compact = false) {
        const change = indexChangeLabel(item && item.change_pct);
        const tone = indexChangeTone(item && item.change_pct);
        const level = indexLevelLabel(item && item.level);
        const status = item && item.data_status === "AVAILABLE" ? "" : " is-unavailable";
        return `
            <div class="index-observation ${tone}${status}" aria-label="${escapeDecisionHtml(item.label)}: ${escapeDecisionHtml(level)}, ${escapeDecisionHtml(change)}">
                <span class="index-observation-label">${escapeDecisionHtml(item.label)}</span>
                <strong>${escapeDecisionHtml(change)}</strong>
                ${compact ? "" : `<small>${escapeDecisionHtml(level)}</small>`}
                ${compact ? "" : indexConstituentContextMarkup(item.constituents)}
            </div>
        `;
    }

    function renderIndexLeadership(payload, session, options = {}) {
        const loadFailed = options.loadFailed === true;
        const indices = Array.isArray(payload && payload.indices) ? payload.indices : [];
        const broad = indices.filter(item => item.family === "broad_market");
        const sectors = indices.filter(item => item.family === "sectoral");
        const comparableSectors = sectors
            .filter(item => indexNumericValue(item.change_pct) !== null)
            .sort(
                (a, b) =>
                    indexNumericValue(b.change_pct) - indexNumericValue(a.change_pct),
            );
        const leader = comparableSectors.length ? comparableSectors[0] : null;
        const laggard = comparableSectors.length > 1
            ? comparableSectors[comparableSectors.length - 1]
            : null;
        const sessionLabel = indexSessionLabel(session, payload && payload.as_of);
        const availableCount = Number(payload && payload.available_count) || 0;

        const title = document.getElementById("index-leadership-title");
        const sessionEl = document.getElementById("index-leadership-session");
        const broadEl = document.getElementById("index-leadership-broad");
        const sectorEl = document.getElementById("index-leadership-sector");
        if (indexLeadershipRetry) {
            indexLeadershipRetry.innerHTML = loadFailed
                ? '<i class="fa-solid fa-arrows-rotate"></i> Retry'
                : '<i class="fa-solid fa-arrows-rotate"></i> Refresh';
        }
        if (title) {
            title.textContent = loadFailed
                ? "Index data unavailable"
                : `${availableCount} of ${indices.length} levels available`;
        }
        if (sessionEl) sessionEl.textContent = sessionLabel;
        if (broadEl) {
            broadEl.innerHTML = broad.length
                ? broad.map(item => indexObservationMarkup(item, true)).join("")
                : `<span class="index-leadership-empty">${loadFailed ? "Index service unavailable" : "Broad-market data unavailable"}</span>`;
        }
        if (sectorEl) {
            if (leader && laggard) {
                sectorEl.innerHTML = `
                    <div class="index-sector-extreme">
                        <span>Leading sector</span>
                        <strong>${escapeDecisionHtml(leader.label)}</strong>
                        <em class="${indexChangeTone(leader.change_pct)}">${escapeDecisionHtml(indexChangeLabel(leader.change_pct))}</em>
                        ${indexLeadershipBreadthChip(leader.constituents)}
                    </div>
                    <div class="index-sector-extreme">
                        <span>Lagging sector</span>
                        <strong>${escapeDecisionHtml(laggard.label)}</strong>
                        <em class="${indexChangeTone(laggard.change_pct)}">${escapeDecisionHtml(indexChangeLabel(laggard.change_pct))}</em>
                        ${indexLeadershipBreadthChip(laggard.constituents)}
                    </div>
                `;
            } else if (leader) {
                sectorEl.innerHTML = `
                    <div class="index-sector-extreme">
                        <span>Sector observed</span>
                        <strong>${escapeDecisionHtml(leader.label)}</strong>
                        <em class="${indexChangeTone(leader.change_pct)}">${escapeDecisionHtml(indexChangeLabel(leader.change_pct))}</em>
                        ${indexLeadershipBreadthChip(leader.constituents)}
                    </div>
                `;
            } else {
                sectorEl.innerHTML = `<span class="index-leadership-empty">${loadFailed ? "Retry index data" : "Sector change unavailable"}</span>`;
            }
        }

        const modalSession = document.getElementById("index-leadership-modal-session");
        const broadGrid = document.getElementById("index-broad-market-grid");
        const sectorGrid = document.getElementById("index-sector-grid");
        const broadCount = document.getElementById("index-broad-market-count");
        const sectorCount = document.getElementById("index-sector-count");
        if (modalSession) modalSession.textContent = sessionLabel;
        if (broadCount) broadCount.textContent = loadFailed ? "Unavailable" : `${broad.length} tracked`;
        if (sectorCount) sectorCount.textContent = loadFailed ? "Unavailable" : `${sectors.length} tracked`;
        if (broadGrid) {
            broadGrid.innerHTML = broad.length
                ? broad.map(item => indexObservationMarkup(item)).join("")
                : `<div class="index-leadership-empty">${loadFailed ? "Index data could not be loaded. Retry after the ATHENA service is updated or restarted." : "No broad-market indices configured."}</div>`;
        }
        if (sectorGrid) {
            sectorGrid.innerHTML = sectors.length
                ? sectors.map(item => indexObservationMarkup(item)).join("")
                : `<div class="index-leadership-empty">${loadFailed ? "Sector data is unavailable because the index request failed." : "No sector indices configured."}</div>`;
        }
    }

    let indexFilterCatalogLoadPromise = null;

    // Owner-reported: the Decisions & Trace Index filter stayed empty with
    // no explanation until Market Intelligence happened to be visited first
    // (only loadIndexLeadership() populated the catalog, and it only runs
    // when the Market Intelligence tab loads). This is a standalone,
    // idempotent fetch of the same catalog so the filter self-populates
    // regardless of which tab the owner opens first.
    async function ensureIndexFilterCatalogLoaded() {
        if (universeIndexCatalog.length > 0) return;
        if (indexFilterCatalogLoadPromise) return indexFilterCatalogLoadPromise;
        indexFilterCatalogLoadPromise = (async () => {
            try {
                const indexResponse = await apiRequest("/api/v1/market/index-intelligence", { skipToast: true });
                const payload = indexResponse && indexResponse.data ? indexResponse.data : null;
                if (payload && Array.isArray(payload.indices)) {
                    universeIndexCatalog = payload.indices.map(item => ({ key: item.key, label: item.label }));
                    populateUniverseIndexFilter();
                    populateValidationResultsIndexFilter();
                    populateDecisionsIndexFilter();
                }
            } catch (err) {
                console.error("Failed to load index filter catalog", err);
            } finally {
                indexFilterCatalogLoadPromise = null;
            }
        })();
        return indexFilterCatalogLoadPromise;
    }

    async function loadIndexLeadership() {
        const [indexResult, sessionResult] = await Promise.allSettled([
            apiRequest("/api/v1/market/index-intelligence", { skipToast: true }),
            apiRequest("/api/v1/dashboard/session-status", { skipToast: true }),
        ]);
        if (sessionResult.status === "fulfilled") {
            const sessionResponse = sessionResult.value;
            state.marketSession = sessionResponse && sessionResponse.data
                ? sessionResponse.data
                : state.marketSession;
        } else {
            console.error("Failed to load index session status", sessionResult.reason);
        }
        if (indexResult.status === "fulfilled") {
            const indexResponse = indexResult.value;
            const payload = indexResponse && indexResponse.data ? indexResponse.data : null;
            if (payload && Array.isArray(payload.indices)) {
                universeIndexCatalog = payload.indices.map(item => ({ key: item.key, label: item.label }));
                populateUniverseIndexFilter();
                populateValidationResultsIndexFilter();
                populateDecisionsIndexFilter();
            }
            renderIndexLeadership(
                payload,
                state.marketSession,
                { loadFailed: !payload || !Array.isArray(payload.indices) },
            );
        } else {
            console.error("Failed to load index leadership", indexResult.reason);
            renderIndexLeadership(null, state.marketSession, { loadFailed: true });
        }
    }

    // MI-3: Validation Pipeline funnel — typed stages from
    // GET /api/v1/pipelines/validation-funnel (Universe→Eligible→Filtered→
    // Watch→Trade). Filtered is server-side arithmetic; UI never recomputes.
    function renderValidationFunnel(funnel) {
        const host = document.getElementById("validation-funnel");
        const asOfEl = document.getElementById("validation-funnel-asof");
        const emptyEl = document.getElementById("validation-funnel-empty");
        if (!host) return;

        const stages = (funnel && funnel.stages) || [];
        const available = !!(funnel && funnel.available);

        if (asOfEl) {
            asOfEl.textContent = available && funnel.as_of
                ? `Last Updated: ${formatDecisionTime(funnel.as_of)}`
                : "";
        }
        if (emptyEl) {
            emptyEl.hidden = available;
        }

        if (!stages.length) {
            host.innerHTML = '<div class="text-muted">No funnel data.</div>';
            return;
        }

        host.innerHTML = stages.map((stage) => {
            const iconByStage = {
                universe: "fa-circle-nodes",
                eligible: "fa-tags",
                filtered: "fa-filter-circle-xmark",
                watch: "fa-tag",
                trade: "fa-stamp",
            };
            const pct = stage.pct_of_universe == null
                ? "—"
                : `${Number(stage.pct_of_universe).toFixed(1)}%`;
            const tradeClass = stage.id === "trade" ? " is-trade" : "";
            const countLabel = stage.id === "universe"
                ? `${stage.count} Symbols`
                : String(stage.count);
            // Labels/ids come from the typed ValidationFunnel DTO only —
            // never free-form user input. Still coerce via String().
            const id = String(stage.id || "");
            const label = String(stage.label || "");
            return (
                `<div class="validation-funnel-stage${tradeClass}" data-stage="${id}">` +
                `<span class="validation-funnel-stage-icon" aria-hidden="true">` +
                `<i class="fa-solid ${iconByStage[id] || "fa-circle"}"></i></span>` +
                `<span class="validation-funnel-stage-label">${label}</span>` +
                `<strong class="validation-funnel-stage-count">${countLabel}</strong>` +
                `<span class="validation-funnel-stage-pct">${pct}</span>` +
                `</div>`
            );
        }).join("");
    }

    function validationStageMap(funnel) {
        const out = {};
        ((funnel && funnel.stages) || []).forEach(stage => {
            out[String(stage.id || "")] = stage;
        });
        return out;
    }

    function validationStageCount(funnel, id) {
        const stage = validationStageMap(funnel)[id];
        return stage ? Number(stage.count || 0) : 0;
    }

    function validationRunLabel(run) {
        if (!run) return "No run yet";
        const status = String(run.overall_status || "unknown").toUpperCase();
        if (status === "SUCCESS") return "Completed";
        if (status === "FAILED") return "Failed";
        if (status === "RUNNING") return "Running";
        return friendlyLabel(status);
    }

    function validationMemberBlocker(member) {
        if (!member || member.included) return "";
        const reasons = Array.isArray(member.exclusion_reasons)
            ? member.exclusion_reasons.map(String).filter(Boolean)
            : [];
        if (reasons.length) return reasons[0];
        const summary = String(member.eligibility_summary || "").trim();
        if (summary) return summary.replace(/^excluded\s*:\s*/i, "");
        return "Excluded by eligibility rules";
    }

    function validationTopBlockers(universe) {
        const counts = new Map();
        Object.values(universe || {}).forEach(member => {
            const blocker = validationMemberBlocker(member);
            if (!blocker) return;
            counts.set(blocker, (counts.get(blocker) || 0) + 1);
        });
        return [...counts.entries()]
            .map(([reason, count]) => ({ reason, count }))
            .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
    }

    function validationShortBlockerLabel(blocker) {
        if (!blocker) return "No blocker";
        const reason = String(blocker.reason || "").toLowerCase();
        let label = "eligibility blocker";
        if (reason.includes("liquid") || reason.includes("volume")) {
            label = "liquidity blocker";
        } else if (reason.includes("history") || reason.includes("daily bar")) {
            label = "history blocker";
        } else if (reason.includes("price")) {
            label = "price blocker";
        } else if (reason.includes("sector")) {
            label = "sector blocker";
        }
        return `${blocker.count} ${label}${blocker.count === 1 ? "" : "s"}`;
    }

    function validationNextAction(funnel, runs, blockers) {
        const available = Boolean(funnel && funnel.available);
        const latest = Array.isArray(runs) && runs.length ? runs[0] : null;
        const status = String(latest && latest.overall_status || "").toUpperCase();
        const trade = validationStageCount(funnel, "trade");
        const watch = validationStageCount(funnel, "watch");
        const eligible = validationStageCount(funnel, "eligible");
        if (!available) return "Run Validate All to build today's validation picture.";
        if (status === "FAILED") return "Open Runs, review the failure, then retry after fixing the cause.";
        if (trade > 0) return `Review ${trade} current Trade setup${trade === 1 ? "" : "s"} in Decisions & Trace.`;
        if (watch > 0) return `Monitor ${watch} Watch setup${watch === 1 ? "" : "s"}; no entry until ATHENA authorizes.`;
        if (eligible > 0) return "Eligible symbols exist, but none cleared Watch or Trade thresholds.";
        if (blockers.length) return "Open Blockers to see why symbols failed validation.";
        return "Refresh Market View or run Validate All if this looks stale.";
    }

    function renderValidationWorkbench({ funnel, runs, universe, qualified, universeNote }) {
        validationWorkbenchState = {
            funnel: funnel || null,
            runs: Array.isArray(runs) ? runs : [],
            universe: universe || {},
            qualified: Array.isArray(qualified) ? qualified : [],
            universeNote: universeNote || null,
        };
        const stages = validationStageMap(funnel);
        const latest = validationWorkbenchState.runs[0] || null;
        const blockers = validationTopBlockers(validationWorkbenchState.universe);
        const topBlocker = blockers[0] || null;
        const universeCount = validationStageCount(funnel, "universe");
        const eligibleCount = validationStageCount(funnel, "eligible");
        const tradeCount = validationStageCount(funnel, "trade");
        const eligiblePct = stages.eligible && stages.eligible.pct_of_universe != null
            ? `${Number(stages.eligible.pct_of_universe).toFixed(1)}% eligible`
            : "Eligibility pending";
        const tradePct = stages.trade && stages.trade.pct_of_universe != null
            ? `${Number(stages.trade.pct_of_universe).toFixed(1)}% trade`
            : "Trade rate pending";
        const nextAction = validationNextAction(funnel, validationWorkbenchState.runs, blockers);

        const summary = document.getElementById("validation-workbench-summary");
        if (summary) {
            summary.innerHTML = `
                <div class="validation-workbench-summary-item">
                    <span>Latest</span>
                    <strong>${escapeDecisionHtml(validationRunLabel(latest))}</strong>
                </div>
                <div class="validation-workbench-summary-item" title="${topBlocker ? escapeDecisionHtml(topBlocker.reason) : ""}">
                    <span>Blocker</span>
                    <strong>${escapeDecisionHtml(validationShortBlockerLabel(topBlocker))}</strong>
                </div>
                <div class="validation-workbench-summary-action">
                    ${escapeDecisionHtml(nextAction)}
                </div>
            `;
        }

        const latestEl = document.getElementById("validation-workbench-latest");
        const latestMetaEl = document.getElementById("validation-workbench-latest-meta");
        const conversionEl = document.getElementById("validation-workbench-conversion");
        const conversionMetaEl = document.getElementById("validation-workbench-conversion-meta");
        const blockerEl = document.getElementById("validation-workbench-top-blocker");
        const blockerMetaEl = document.getElementById("validation-workbench-top-blocker-meta");
        const nextEl = document.getElementById("validation-workbench-next-action");
        if (latestEl) latestEl.textContent = validationRunLabel(latest);
        if (latestMetaEl) {
            latestMetaEl.textContent = latest
                ? `${latest.run_id || "run"} · ${latest.as_of ? formatDecisionTime(latest.as_of) : "time unknown"}`
                : "No completed validation run loaded.";
        }
        if (conversionEl) conversionEl.textContent = `${eligibleCount}/${universeCount || 0} eligible · ${tradeCount} trade`;
        if (conversionMetaEl) conversionMetaEl.textContent = `${eligiblePct} · ${tradePct}`;
        if (blockerEl) blockerEl.textContent = topBlocker ? validationShortBlockerLabel(topBlocker) : "No blocker in loaded rows";
        if (blockerMetaEl) {
            blockerMetaEl.textContent = topBlocker
                ? topBlocker.reason
                : (universeNote || "No exclusion reason available from the current payload.");
        }
        if (nextEl) nextEl.textContent = nextAction;

        const overviewDetail = document.getElementById("validation-workbench-overview-detail");
        if (overviewDetail) {
            overviewDetail.innerHTML = `
                <p><strong>Today:</strong> ${universeCount || 0} symbols validated, ${eligibleCount} eligible, ${validationStageCount(funnel, "watch")} watch, ${tradeCount} trade.</p>
                <p><strong>Use this:</strong> start with Trade setups when they exist; otherwise use Blockers to understand why the list is thin before running more validations.</p>
                ${universeNote ? `<p><strong>Note:</strong> ${escapeDecisionHtml(universeNote)}</p>` : ""}
            `;
        }

        const blockersEl = document.getElementById("validation-blockers-list");
        if (blockersEl) {
            blockersEl.innerHTML = blockers.length
                ? blockers.slice(0, 8).map(item => `
                    <div class="validation-blocker-row">
                        <div>
                            <strong>${escapeDecisionHtml(item.reason)}</strong>
                            <span>Real exclusion reason from latest loaded validation rows.</span>
                        </div>
                        <span class="meta-chip score-chip">${item.count}</span>
                    </div>
                `).join("")
                : '<div class="text-muted">No exclusion blockers are available from the loaded rows.</div>';
        }

        const runsEl = document.getElementById("validation-runs-list");
        if (runsEl) {
            const rows = validationWorkbenchState.runs.slice(0, 10);
            runsEl.innerHTML = rows.length
                ? rows.map(run => {
                    const status = String(run.overall_status || "unknown").toUpperCase();
                    const failed = status === "FAILED";
                    return `
                        <div class="validation-run-row ${failed ? "is-failed" : ""}">
                            <div>
                                <strong>${escapeDecisionHtml(validationRunLabel(run))}</strong>
                                <span>${escapeDecisionHtml(run.run_id || "run")}</span>
                            </div>
                            <span>${run.as_of ? escapeDecisionHtml(formatDecisionTime(run.as_of)) : "—"}</span>
                        </div>
                    `;
                }).join("")
                : '<div class="text-muted">No validation run history loaded.</div>';
        }
    }

    async function loadMarketIntelligence() {
        try {
            await loadCandidateList();
            await loadSavedSymbols();
            const indexLeadershipPromise = loadIndexLeadership();

            // 1. Fetch Market Summary (MH-3), Validation Pipeline funnel, and
            //    pipeline runs (Universe / Recent Activity) in parallel.
            const [summaryRes, runsRes, funnelRes] = await Promise.all([
                apiRequest("/api/v1/market/summary").catch(() => null),
                apiRequest("/api/v1/pipelines/runs?page_size=100&sort_by=as_of&sort_dir=desc").catch(() => null),
                apiRequest("/api/v1/pipelines/validation-funnel").catch(() => null),
            ]);
            renderValidationFunnel(funnelRes && funnelRes.data ? funnelRes.data : null);
            renderMarketSummaryHero(summaryRes && summaryRes.data ? summaryRes.data : null);
            await indexLeadershipPromise;

            let universe = {};
            let qualified = [];
            let universeNote = null;
            let sortedRuns = [];

            if (runsRes && runsRes.data && runsRes.data.length > 0) {
                const extractData = (r) => {
                    const ctx =
                        r.final_context ||
                        (r.pipeline_runs && r.pipeline_runs[0]
                            ? r.pipeline_runs[0].final_context
                            : null);
                    return ctx && ctx.data ? ctx.data : {};
                };
                // Newest first — prefer known volatility over older UNKNOWN payloads
                const runs = [...runsRes.data].sort(
                    (a, b) => new Date(b.as_of || 0) - new Date(a.as_of || 0)
                );
                sortedRuns = runs;

                // A scoped validate writes a run holding only the symbols it was
                // asked about, so reading the newest run alone showed just that
                // symbol and hid everything validated earlier the same day. Each
                // symbol keeps the verdict of the newest run that covered it —
                // the same merge the Universe table and the funnel counts use.
                const dayKey = (iso) => new Date(iso || 0).toDateString();
                let leading = null;
                for (const r of runs) {
                    const status = (r.overall_status || "").toString().toUpperCase();
                    if (status === "FAILED" || status === "RUNNING") continue;
                    const data = extractData(r);
                    const members = data.universe_members || {};
                    const hasMembers = Object.keys(members).length > 0;

                    if (!hasMembers) continue;
                    if (!leading) {
                        leading = r;
                        universeNote = data.universe_note || null;
                        const summary = data.universe_summary || {};
                        if (!universeNote && summary.excluded != null && summary.included === 0 && summary.evaluated > 0) {
                            universeNote =
                                `All ${summary.evaluated} evaluated symbols were Excluded (e.g. need ≥30 daily bars). ` +
                                "Inspect Trace for rule evidence. Increase ingestion lookback_days if history is short.";
                        }
                    } else if (dayKey(r.as_of) !== dayKey(leading.as_of)) {
                        continue;
                    }
                    // A symbol's decision comes from the same run that judged
                    // it, so a name re-validated without qualifying does not
                    // keep the WATCH/TRADE it earned in an earlier run.
                    const runQualified = data.qualified_today || [];
                    for (const [sym, member] of Object.entries(members)) {
                        if (sym in universe) continue;
                        universe[sym] = member;
                        for (const row of runQualified) {
                            if (String(row.symbol || "").toUpperCase() === sym.toUpperCase()) {
                                qualified.push(row);
                            }
                        }
                    }
                }
                qualified.sort((a, b) =>
                    String(a.symbol || "").localeCompare(String(b.symbol || ""))
                );
                universeCache = universe;
            }

            // 2. Refresh read-only Decisions cache for result-row actions.
            await refreshDecisionCacheForValidationResults();

            // 3. Fetch and Render Calendar Grid & Events
            const calRes = await apiRequest("/api/v1/dashboard/calendar").catch(() => null);
            if (calRes && calRes.data) {
                renderCalendar(calRes.data);
                renderUpcomingEvents(calRes.data);
            }

            // 4. Render Universe list table + qualified layer
            renderUniverseTable(universe, universeNote);
            renderValidationResults(universe, qualified, universeNote);
            renderValidationWorkbench({
                funnel: funnelRes && funnelRes.data ? funnelRes.data : null,
                runs: sortedRuns,
                universe,
                qualified,
                universeNote,
            });

            // 5. MI-5: Recent Activity from the same runs we already fetched.
            if (runsRes && runsRes.data) {
                renderRecentActivity(runsRes.data);
            } else {
                renderRecentActivity([]);
            }
            // Resume an in-flight full-validation poll if the host still has one.
            pollFullValidationStatus({ silent: true });

        } catch (err) {
            console.error("Failed to load market intelligence data", err);
            const trendBadge = document.getElementById("regime-trend-badge");
            const volBadge = document.getElementById("regime-vol-badge");
            const gapBadge = document.getElementById("regime-gap-badge");
            const evidenceText = document.getElementById("regime-evidence-text");
            const universeBody = document.getElementById("universe-list-body");
            if (trendBadge) trendBadge.textContent = "ERROR";
            if (volBadge) volBadge.textContent = "ERROR";
            if (gapBadge) gapBadge.textContent = "ERROR";
            if (evidenceText) evidenceText.textContent = "Market intelligence failed to load. Use refresh to retry.";
            if (universeBody) {
                universeBody.innerHTML = `<tr><td colspan="3" class="text-muted text-center" style="padding: 24px;">Failed to load universe members.</td></tr>`;
            }
            showToast("Failed to load market intelligence data", "danger");
        }
    }

    function renderRecentActivity(runs) {
        const host = document.getElementById("market-recent-activity");
        if (!host) return;
        const sorted = [...(runs || [])].sort(
            (a, b) => new Date(b.as_of || 0) - new Date(a.as_of || 0)
        ).slice(0, 12);
        if (!sorted.length) {
            host.innerHTML = '<li class="text-muted">No validation runs yet.</li>';
            return;
        }
        host.innerHTML = sorted.map((r) => {
            const status = String(r.overall_status || "unknown");
            const failed = status.toUpperCase() === "FAILED";
            const when = r.as_of ? formatDecisionTime(r.as_of) : "—";
            const runId = String(r.run_id || "").slice(0, 18);
            const label = failed ? "Validation failed" : "Market validation completed";
            return (
                `<li>` +
                `<span class="market-activity-dot${failed ? " is-failed" : ""}" aria-hidden="true"></span>` +
                `<span class="market-activity-main">${label}` +
                (runId ? `<br><span class="text-muted">${runId}</span>` : "") +
                `</span>` +
                `<span class="market-activity-meta">${when}</span>` +
                `</li>`
            );
        }).join("");
    }

    let _fullValidationPollTimer = null;

    function renderFullValidationProgress(progress) {
        const el = document.getElementById("full-validation-progress");
        const runBtn = document.getElementById("mi-run-full-validation-btn");
        const allBtn = document.getElementById("universe-validate-all-btn");
        if (!el) return;
        if (!progress) {
            el.hidden = true;
            el.textContent = "";
            el.className = "full-validation-progress text-muted";
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
            return;
        }
        const state = String(progress.state || "idle");
        const stage = String(progress.stage || "idle");
        const total = progress.symbols_total ?? 0;
        const done = progress.symbols_completed ?? 0;
        el.hidden = state === "idle";
        el.className = `full-validation-progress text-muted is-${state}`;
        if (state === "running") {
            el.textContent =
                `Running full validation… ${stage}` +
                (total ? ` · ${done}/${total} symbols` : "") +
                " (this can take several minutes)";
            if (runBtn) runBtn.disabled = true;
            if (allBtn) allBtn.disabled = true;
        } else if (state === "completed") {
            el.textContent =
                `Full validation completed` +
                (progress.run_id ? ` · ${progress.run_id}` : "") +
                (total ? ` · ${total} symbols` : "");
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
        } else if (state === "failed") {
            el.textContent =
                `Full validation failed` +
                (progress.detail ? `: ${progress.detail}` : "");
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
        } else {
            el.hidden = true;
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
        }
    }

    async function pollFullValidationStatus({ silent = false } = {}) {
        try {
            const res = await apiRequest("/api/v1/market/validate-all", { skipToast: true });
            const progress = res && res.data ? res.data : null;
            renderFullValidationProgress(progress);
            if (progress && progress.state === "running") {
                if (_fullValidationPollTimer) clearTimeout(_fullValidationPollTimer);
                _fullValidationPollTimer = setTimeout(() => pollFullValidationStatus(), 3000);
            } else if (progress && progress.state === "completed" && !silent) {
                showToast("Full validation completed", "success");
                if (typeof loadMarketIntelligence === "function") {
                    await loadMarketIntelligence();
                }
            } else if (progress && progress.state === "failed" && !silent) {
                showToast(progress.detail || "Full validation failed", "danger");
            }
        } catch (err) {
            if (!silent) {
                console.error("full validation status poll failed", err);
            }
        }
    }

    async function startFullUniverseValidation() {
        try {
            const res = await apiRequest("/api/v1/market/validate-all", {
                method: "POST",
                skipToast: true,
            });
            renderFullValidationProgress(res && res.data ? res.data : null);
            showToast("Full validation started in the background", "success");
            pollFullValidationStatus();
        } catch (err) {
            const status = err?.status;
            const detail = err?.data?.detail || err?.data?.title;
            if (status === 404) {
                showToast(
                    "Full validation API not loaded — restart ./athena-serve and hard-refresh",
                    "danger"
                );
                return;
            }
            showToast(
                typeof detail === "string" && detail.trim()
                    ? detail
                    : "Could not start full validation",
                "danger"
            );
        }
    }

    function renderCalendar(calData) {
        const gridContainer = document.getElementById("calendar-grid-container");
        const monthYearLabel = document.getElementById("calendar-month-year");
        if (!gridContainer) return;

        gridContainer.innerHTML = "";

        // Build weekday headers (Mon - Sun)
        const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        days.forEach(day => {
            const header = document.createElement("div");
            header.className = "calendar-day-header";
            header.textContent = day;
            gridContainer.appendChild(header);
        });

        // Use the current month for display
        const displayDate = new Date();
        const displayYear = displayDate.getFullYear();
        const displayMonth = displayDate.getMonth(); // 0-indexed

        // Set Month/Year label
        const monthNames = [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ];
        monthYearLabel.textContent = `${monthNames[displayMonth]} ${displayYear}`;

        // Get first day of month (0 = Sunday, 1 = Monday...)
        const firstDay = new Date(displayYear, displayMonth, 1).getDay();
        // Convert to Mon-first offset (0 = Monday, 6 = Sunday)
        const startOffset = firstDay === 0 ? 6 : firstDay - 1;

        // Get total days in month
        const totalDays = new Date(displayYear, displayMonth + 1, 0).getDate();

        // Create mapping sets for fast lookups
        const holidaysMap = new Map((calData.holidays || []).map(h => [h.date, h.name]));
        const specialMap = new Map((calData.special_sessions || []).map(s => [s.date, s]));
        const weeklyExpiries = new Set(calData.weekly_expiries || []);
        const monthlyExpiries = new Set(calData.monthly_expiries || []);

        // Inject empty offset cells
        for (let i = 0; i < startOffset; i++) {
            const emptyCell = document.createElement("div");
            emptyCell.className = "calendar-cell empty";
            gridContainer.appendChild(emptyCell);
        }

        // Inject day cells
        for (let dayNum = 1; dayNum <= totalDays; dayNum++) {
            const cell = document.createElement("div");
            cell.className = "calendar-cell";

            // Format date string YYYY-MM-DD (zero-padded)
            const dateStr = `${displayYear}-${String(displayMonth + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;

            // Add day number
            const label = document.createElement("span");
            label.textContent = dayNum;
            cell.appendChild(label);

            // Check attributes
            const isWeekend = new Date(displayYear, displayMonth, dayNum).getDay() === 0 || 
                              new Date(displayYear, displayMonth, dayNum).getDay() === 6;
            const holidayName = holidaysMap.get(dateStr);
            const specialSession = specialMap.get(dateStr);
            const isWeeklyExp = weeklyExpiries.has(dateStr);
            const isMonthlyExp = monthlyExpiries.has(dateStr);
            const isToday = displayDate.getDate() === dayNum && displayDate.getMonth() === displayMonth;

            // Apply classes
            if (isWeekend) cell.classList.add("weekend");
            if (holidayName) cell.classList.add("holiday");
            if (specialSession) cell.classList.add("special");
            if (isWeeklyExp || isMonthlyExp) cell.classList.add("expiry");
            if (isToday) cell.classList.add("today-cell");

            // Add hover tooltip detail (HTML title attribute for ease)
            let tooltip = `Date: ${dateStr}`;
            if (holidayName) tooltip += `\nHoliday: ${holidayName}`;
            if (specialSession) tooltip += `\nSpecial: ${specialSession.name} (${specialSession.timings_note || 'Muhurat session'})`;
            if (isWeeklyExp) tooltip += `\nWeekly Expiry`;
            if (isMonthlyExp) tooltip += `\nMonthly Expiry`;
            cell.title = tooltip;

            // Add cell dots indicators
            const dotsContainer = document.createElement("div");
            dotsContainer.className = "calendar-cell-indicators";

            if (holidayName) {
                const dot = document.createElement("span");
                dot.className = "cell-dot holiday";
                dotsContainer.appendChild(dot);
            }
            if (specialSession) {
                const dot = document.createElement("span");
                dot.className = "cell-dot special";
                dotsContainer.appendChild(dot);
            }
            if (isWeeklyExp || isMonthlyExp) {
                const dot = document.createElement("span");
                dot.className = "cell-dot expiry";
                dotsContainer.appendChild(dot);
            }

            cell.appendChild(dotsContainer);
            gridContainer.appendChild(cell);
        }
    }

    function renderUpcomingEvents(calData) {
        const container = document.getElementById("upcoming-events-container");
        if (!container) return;

        container.innerHTML = "";

        const allEvents = [];

        // Aggregate weekly expiries
        (calData.weekly_expiries || []).forEach(date => {
            allEvents.push({ date, kind: "weekly_expiry", name: "Weekly F&O Expiry", tagClass: "expiry-tag", tagText: "weekly exp" });
        });
        // Aggregate monthly expiries
        (calData.monthly_expiries || []).forEach(date => {
            allEvents.push({ date, kind: "monthly_expiry", name: "Monthly F&O Expiry", tagClass: "expiry-tag", tagText: "monthly exp" });
        });
        // Aggregate holidays
        (calData.holidays || []).forEach(h => {
            allEvents.push({ date: h.date, kind: "holiday", name: h.name, tagClass: "holiday-tag", tagText: "holiday" });
        });
        // Aggregate events
        (calData.events || []).forEach(e => {
            allEvents.push({ date: e.date, kind: e.kind, name: e.name, tagClass: "macro", tagText: e.kind });
        });

        // Filter events for displays after today or within display range
        const displayDate = new Date();
        const displayYear = displayDate.getFullYear();
        const displayMonth = displayDate.getMonth();
        const displayMonthStr = String(displayMonth + 1).padStart(2, '0');

        const currentMonthEvents = allEvents.filter(ev => {
            return ev.date.startsWith(`${displayYear}-${displayMonthStr}`);
        });

        // Sort by date ascending
        currentMonthEvents.sort((a, b) => a.date.localeCompare(b.date));

        if (currentMonthEvents.length === 0) {
            container.innerHTML = `<div class="text-muted text-center" style="padding: 12px 0; font-size: 0.85rem;">No scheduled events this month.</div>`;
            return;
        }

        currentMonthEvents.forEach(ev => {
            const item = document.createElement("div");
            item.className = "event-item";

            // Format date for display
            const dateObj = new Date(ev.date);
            const dateText = dateObj.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

            item.innerHTML = `
                <div class="event-info">
                    <span class="event-title">${ev.name}</span>
                    <span class="event-meta">${dateText} (${ev.date})</span>
                </div>
                <span class="event-tag ${ev.tagClass}">${ev.tagText}</span>
            `;
            container.appendChild(item);
        });
    }

    function renderUniverseTable(universeMembers, universeNote) {
        const tbody = document.getElementById("universe-list-body");
        if (!tbody) return;

        tbody.innerHTML = "";

        const symbols = Object.keys(universeMembers);

        if (symbols.length === 0) {
            const note = universeNote
                ? universeNote
                : "No eligibility results yet. Add symbols above, then run <code>athena cycle</code> / <code>./athena-run-due</code>.";
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="text-muted text-center" style="padding: 24px;">
                        ${note}
                    </td>
                </tr>
            `;
            return;
        }

        symbols.forEach(sym => {
            const member = universeMembers[sym];
            const tr = document.createElement("tr");
            tr.setAttribute("data-symbol", sym.toUpperCase());

            const statusBadge = member.included 
                ? '<span class="symbol-status-badge included"><i class="fas fa-check"></i> Eligible</span>'
                : '<span class="symbol-status-badge excluded"><i class="fas fa-ban"></i> Excluded</span>';

            tr.innerHTML = `
                <td class="symbol-name-col">${sym}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="inspect-btn" onclick="openTraceModal('${sym}')">
                        <i class="fas fa-search-plus"></i> Inspect Trace
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function compactEligibilitySummary(value) {
        const text = String(value || "").trim();
        if (!text) return "—";
        const passed = text.match(/passed all\s+(\d+)/i);
        if (passed) return `${passed[1]}/${passed[1]} passed`;
        const failed = text.match(/failed\s+(\d+)\s*\/\s*(\d+)/i);
        if (failed) return `${failed[1]}/${failed[2]} failed`;
        const withoutOutcome = text.replace(/^(included|excluded)\s*:\s*/i, "");
        return withoutOutcome.length > 20
            ? `${withoutOutcome.slice(0, 18)}…`
            : withoutOutcome;
    }

    function compactUniverseTime(value) {
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return "—";
        const date = parsed.toLocaleDateString("en-IN", {
            day: "2-digit",
            month: "short",
        });
        const time = parsed.toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        });
        return `${date} · ${time}`;
    }

    function friendlyEligibilityRule(value) {
        return String(value || "Rule")
            .replace(/[_-]+/g, " ")
            .replace(/\b\w/g, ch => ch.toUpperCase());
    }

    function showEligibilityDetail(symbol) {
        const bare = String(symbol || "").toUpperCase();
        const detail = eligibilityDetailBySymbol.get(bare);
        const modal = document.getElementById("eligibility-detail-modal");
        const title = document.getElementById("eligibility-detail-title");
        const summary = document.getElementById("eligibility-detail-summary");
        const body = document.getElementById("eligibility-detail-body");
        if (!modal || !title || !summary || !body || !detail) return;

        title.textContent = `${bare} eligibility`;
        summary.textContent = detail.summary || "Eligibility evidence unavailable.";
        body.innerHTML = "";
        const evidence = Array.isArray(detail.evidence) ? detail.evidence : [];
        if (evidence.length === 0) {
            const empty = document.createElement("p");
            empty.className = "eligibility-detail-empty";
            empty.textContent = "Rule-level evidence is unavailable for this historical validation.";
            body.appendChild(empty);
        } else {
            evidence.forEach(item => {
                const passed = Boolean(item.passed);
                const row = document.createElement("div");
                row.className = `eligibility-rule-row ${passed ? "is-passed" : "is-failed"}`;

                const icon = document.createElement("span");
                icon.className = "eligibility-rule-icon";
                icon.setAttribute("aria-hidden", "true");
                icon.innerHTML = `<i class="fa-solid ${passed ? "fa-check" : "fa-xmark"}"></i>`;

                const copy = document.createElement("div");
                copy.className = "eligibility-rule-copy";
                const name = document.createElement("strong");
                name.textContent = friendlyEligibilityRule(item.rule);
                const explanation = document.createElement("span");
                explanation.textContent = String(item.explanation || "No explanation recorded.");
                copy.append(name, explanation);

                const outcome = document.createElement("span");
                outcome.className = "eligibility-rule-outcome";
                outcome.textContent = passed ? "Passed" : "Failed";

                row.append(icon, copy, outcome);
                body.appendChild(row);
            });
        }
        openModal(modal);
    }

    function syncUniverseSavedStars() {
        document.querySelectorAll(".candidate-save-toggle-btn").forEach(btn => {
            const symbol = String(btn.getAttribute("data-symbol") || "").toUpperCase();
            const isSaved = savedSymbolSet.has(symbol);
            btn.classList.toggle("is-saved", isSaved);
            btn.title = isSaved ? `Remove ${symbol} from Saved Symbols` : `Save ${symbol}`;
            btn.setAttribute("aria-label", btn.title);
            btn.setAttribute("aria-pressed", isSaved ? "true" : "false");
            btn.innerHTML = `<i class="${isSaved ? "fa-solid" : "fa-regular"} fa-star"></i>`;
        });
    }

    async function toggleSavedSymbolNow(symbol, { button = null } = {}) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return;
        const wasSaved = savedSymbolSet.has(bare);
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
        try {
            if (wasSaved) {
                await apiRequest(`/api/v1/saved-symbols/${encodeURIComponent(bare)}`, {
                    method: "DELETE",
                    skipToast: true,
                });
                savedSymbolSet.delete(bare);
                showToast(`${bare} removed from Saved Symbols`, "success");
            } else {
                await apiRequest("/api/v1/saved-symbols", {
                    method: "POST",
                    body: JSON.stringify({ symbol: bare }),
                    skipToast: true,
                });
                savedSymbolSet.add(bare);
                showToast(`${bare} saved to your watch list`, "success");
            }
            await loadSavedSymbols();
        } catch (err) {
            const detail = err?.data?.detail;
            showToast(
                typeof detail === "string" && detail.trim()
                    ? detail
                    : `Failed to ${wasSaved ? "remove" : "save"} ${bare}`,
                "danger"
            );
        } finally {
            if (button) button.disabled = false;
            syncUniverseSavedStars();
        }
    }

    function validationResultRows(universeMembers, qualified) {
        const bySymbol = new Map();
        Object.entries(universeMembers || {}).forEach(([symbol, member]) => {
            const bare = String(symbol || member?.symbol || member?.instrument_id || "")
                .toUpperCase()
                .replace(/^NSE:|^BSE:/, "");
            if (!bare) return;
            bySymbol.set(bare, { symbol: bare, member, qualified: null });
        });
        (Array.isArray(qualified) ? qualified : []).forEach(row => {
            const bare = String(row.symbol || row.instrument_id || "")
                .toUpperCase()
                .replace(/^NSE:|^BSE:/, "");
            if (!bare) return;
            const existing = bySymbol.get(bare) || { symbol: bare, member: null, qualified: null };
            existing.qualified = row;
            bySymbol.set(bare, existing);
        });
        const priority = (row) => {
            const decision = currentOpenableDecisionForSymbol(row.symbol) || latestDecisionForSymbol(row.symbol);
            const type = String(row.qualified?.decision_type || decision?.metadata?.decision_type || "").toUpperCase();
            if (type === "TRADE") return 0;
            if (type === "WATCH") return 1;
            if (row.member && row.member.included === true) return 2;
            if (row.member && row.member.included === false) return 3;
            return 4;
        };
        return Array.from(bySymbol.values()).sort((a, b) => {
            const rank = priority(a) - priority(b);
            return rank || a.symbol.localeCompare(b.symbol);
        });
    }

    function validationResultStatus(member) {
        if (!member) {
            return {
                html: '<span class="symbol-status-badge neutral">Validated</span>',
                text: "Validated",
            };
        }
        if (member.included === true) {
            return {
                html: '<span class="symbol-status-badge included"><i class="fas fa-check"></i> Eligible</span>',
                text: "Eligible",
            };
        }
        const reason = validationMemberBlocker(member);
        return {
            html: `<span class="symbol-status-badge excluded" title="${escapeDecisionHtml(reason)}"><i class="fas fa-ban"></i> Excluded</span>`,
            text: reason || "Excluded",
        };
    }

    function validationResultOutcome(row, decision) {
        const type = String(row.qualified?.decision_type || decision?.metadata?.decision_type || "").toUpperCase();
        if (type === "TRADE" || type === "WATCH" || type === "NO_TRADE") {
            return {
                html: `<span class="type-chip type-${type.toLowerCase()}">${escapeDecisionHtml(friendlyAnalysisName(type))}</span>`,
                rank: type === "TRADE" ? 0 : type === "WATCH" ? 1 : 3,
            };
        }
        if (row.member && row.member.included === true) {
            return {
                html: '<span class="type-chip type-hold">Eligible only</span>',
                rank: 2,
            };
        }
        if (row.member && row.member.included === false) {
            return {
                html: '<span class="type-chip type-pass">Blocked</span>',
                rank: 4,
            };
        }
        return { html: '<span class="type-chip type-pass">No current row</span>', rank: 5 };
    }

    function validationScoreCandidateValue(value) {
        const score = Number(value);
        return Number.isFinite(score) && score >= 0 ? score : null;
    }

    function validationScoreFromExplanation(text) {
        const match = String(text || "").match(/score\s+(\d+(?:\.\d+)?)/i);
        if (!match) return null;
        return validationScoreCandidateValue(match[1]);
    }

    function validationResultScore(row, decision) {
        const decisionScore = decision ? decisionScoreValue(decision) : null;
        const candidates = [
            validationScoreCandidateValue(decisionScore),
            validationScoreCandidateValue(row.qualified?.score),
            validationScoreCandidateValue(row.qualified?.score_value),
            validationScoreCandidateValue(row.qualified?.score_total),
            validationScoreCandidateValue(row.qualified?.scoring?.score),
            validationScoreCandidateValue(row.qualified?.score_summary?.score),
            validationScoreFromExplanation(row.qualified?.explanation),
        ];
        const score = candidates.find(value => Number.isFinite(value));
        return Number.isFinite(score) ? score.toFixed(1) : "Not scored";
    }

    function validationResultPlan(decision, row) {
        if (!decision) return row.qualified ? "No current plan" : "No plan";
        const freshness = inferTradePlanFreshness(decision.trade_plan);
        return freshness && freshness.has_trade_plan ? formatTradePlanFreshnessBadge(freshness) : "No plan";
    }

    function validationResultPlanType(decision, row) {
        if (!decision) return row.qualified ? "no-current-plan" : "no-plan";
        const freshness = inferTradePlanFreshness(decision.trade_plan);
        if (!freshness || !freshness.has_trade_plan) return "no-plan";
        const status = String(freshness.status || "").toLowerCase();
        if (status === "fresh" || status === "aging" || status === "expired") return status;
        if (status === "stale") return "expired";
        return "fresh";
    }

    function validationResultOutcomeType(row, decision) {
        const type = String(row.qualified?.decision_type || decision?.metadata?.decision_type || "").toUpperCase();
        if (type === "TRADE") return "trade";
        if (type === "WATCH") return "watch";
        if (type === "NO_TRADE") return "no-trade";
        if (row.member && row.member.included === true) return "eligible";
        if (row.member && row.member.included === false) return "blocked";
        return "none";
    }

    function validationWorkbenchFilters() {
        return {
            query: String(document.getElementById("universe-search")?.value || "").trim().toUpperCase(),
            outcome: document.getElementById("validation-results-outcome-filter")?.value || "all",
            plan: document.getElementById("validation-results-plan-filter")?.value || "all",
            index: document.getElementById("validation-results-index-filter")?.value || "all",
            sort: document.getElementById("validation-results-sort")?.value || "score-desc",
        };
    }

    function validationResultScoreNumber(score) {
        const value = Number(score);
        return Number.isFinite(value) ? value : null;
    }

    function validationResultRowView(row) {
        const symbol = row.symbol;
        const decision = currentOpenableDecisionForSymbol(symbol);
        const latestDecision = decision || latestDecisionForSymbol(symbol);
        const status = validationResultStatus(row.member);
        const outcome = validationResultOutcome(row, latestDecision);
        const score = validationResultScore(row, latestDecision);
        const plan = validationResultPlan(decision, row);
        const blocker = row.member && row.member.included === false
            ? validationMemberBlocker(row.member)
            : "";
        const summary = row.qualified
            ? formatDecisionSummary(row.qualified.explanation || "", row.qualified.decision_type || "", [])
            : null;
        const summaryText = summary
            ? summary.headline
            : (blocker || compactEligibilitySummary(row.member?.eligibility_summary || status.text));
        return {
            row,
            symbol,
            status,
            outcome,
            outcomeType: validationResultOutcomeType(row, latestDecision),
            score,
            scoreValue: validationResultScoreNumber(score),
            plan,
            planType: validationResultPlanType(decision, row),
            blocker,
            summaryText,
            isSaved: savedSymbolSet.has(symbol),
            canOpen: Boolean(decision),
        };
    }

    function validationResultMatchesFilters(view, filters) {
        if (filters.query) {
            const haystack = [
                view.symbol,
                view.summaryText,
                view.status?.text,
                view.blocker,
                view.plan,
                view.outcomeType,
            ].join(" ").toUpperCase();
            if (!haystack.includes(filters.query)) return false;
        }
        if (filters.outcome !== "all" && view.outcomeType !== filters.outcome) return false;
        if (filters.plan !== "all" && view.planType !== filters.plan) return false;
        if (filters.index !== "all") {
            if (!validationResultsIndexMemberSymbols || !validationResultsIndexMemberSymbols.has(view.symbol)) {
                return false;
            }
        }
        return true;
    }

    function validationPlanSortRank(planType) {
        if (planType === "fresh") return 0;
        if (planType === "aging") return 1;
        if (planType === "expired") return 2;
        if (planType === "no-current-plan") return 3;
        return 4;
    }

    function compareValidationResultViews(a, b, sort) {
        const scoreA = Number.isFinite(a.scoreValue) ? a.scoreValue : -Infinity;
        const scoreB = Number.isFinite(b.scoreValue) ? b.scoreValue : -Infinity;
        if (sort === "score-asc") {
            return (scoreA - scoreB) || a.symbol.localeCompare(b.symbol);
        }
        if (sort === "symbol-asc") return a.symbol.localeCompare(b.symbol);
        if (sort === "symbol-desc") return b.symbol.localeCompare(a.symbol);
        if (sort === "outcome-priority") {
            return (a.outcome.rank - b.outcome.rank) || (scoreB - scoreA) || a.symbol.localeCompare(b.symbol);
        }
        if (sort === "plan-status") {
            return (validationPlanSortRank(a.planType) - validationPlanSortRank(b.planType))
                || (scoreB - scoreA)
                || a.symbol.localeCompare(b.symbol);
        }
        return (scoreB - scoreA) || a.symbol.localeCompare(b.symbol);
    }

    function filteredValidationResultViews(rows, filters) {
        return rows
            .map(validationResultRowView)
            .filter(view => validationResultMatchesFilters(view, filters))
            .sort((a, b) => compareValidationResultViews(a, b, filters.sort));
    }

    function setValidationResultsBusy(isBusy) {
        const body = document.getElementById("qualified-today-body");
        const busy = document.getElementById("validation-results-busy");
        const controls = [
            document.getElementById("validation-results-outcome-filter"),
            document.getElementById("validation-results-plan-filter"),
            document.getElementById("validation-results-index-filter"),
            document.getElementById("validation-results-sort"),
            document.getElementById("validation-results-reset"),
        ];
        if (body) {
            body.classList.toggle("is-filtering", isBusy);
            body.setAttribute("aria-busy", isBusy ? "true" : "false");
        }
        if (busy) {
            busy.hidden = !isBusy;
            busy.setAttribute("aria-hidden", isBusy ? "false" : "true");
        }
        controls.forEach(control => {
            if (control) control.disabled = isBusy;
        });
    }

    function renderValidationResults(universeMembers, qualified, universeNote) {
        const body = document.getElementById("qualified-today-body");
        if (!body) return;
        const rows = validationResultRows(universeMembers || {}, qualified || []);
        const countEl = document.getElementById("validation-results-count");
        const filters = validationWorkbenchFilters();
        updateValidationResultsFilterToggleActiveState(filters);
        if (rows.length === 0) {
            body.className = "validation-results-list";
            body.innerHTML = `<div class="text-muted text-center" style="padding: 24px;">${escapeDecisionHtml(universeNote || "No validation results are available yet.")}</div>`;
            if (countEl) countEl.textContent = "Showing 0";
            return;
        }
        const views = filteredValidationResultViews(rows, filters);
        if (countEl) {
            countEl.textContent = `Showing ${views.length} of ${rows.length}`;
        }
        body.className = "validation-results-list";
        if (views.length === 0) {
            body.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">No validation results match these filters.</div>';
            return;
        }
        body.innerHTML = views.map(view => {
            const symbol = view.symbol;
            return `
                <div class="validation-result-row" data-validation-result-symbol="${escapeDecisionHtml(symbol)}" title="${escapeDecisionHtml(view.blocker || view.status.text || "")}">
                    <div class="validation-result-main">
                        <div class="validation-result-title">
                            <strong>${escapeDecisionHtml(symbol)}</strong>
                            ${view.status.html}
                            ${view.outcome.html}
                        </div>
                        <p class="validation-result-summary">${escapeDecisionHtml(view.summaryText)}</p>
                    </div>
                    <div class="validation-result-meta" aria-label="${escapeDecisionHtml(symbol)} validation details">
                        <span class="validation-result-metric">
                            <span>Score</span>
                            <strong>${escapeDecisionHtml(view.score)}</strong>
                        </span>
                        <span class="validation-result-metric">
                            <span>Plan</span>
                            <strong>${escapeDecisionHtml(view.plan)}</strong>
                        </span>
                    </div>
                    <div class="validation-result-actions">
                        <button type="button" class="inspect-btn qualified-open-decision-btn" data-symbol="${escapeDecisionHtml(symbol)}" ${view.canOpen ? "" : "disabled"} title="${view.canOpen ? `Open ${escapeDecisionHtml(symbol)} in Decisions & Trace` : "Not on the current Decisions board"}" aria-label="Open ${escapeDecisionHtml(symbol)} decision">
                            <i class="fa-solid fa-brain" aria-hidden="true"></i>
                        </button>
                        <button type="button" class="inspect-btn qualified-save-btn" data-symbol="${escapeDecisionHtml(symbol)}" title="${view.isSaved ? "Remove from Saved Symbols" : "Save symbol"}" aria-label="${view.isSaved ? "Remove saved" : "Save"} ${escapeDecisionHtml(symbol)}">
                            <i class="${view.isSaved ? "fa-solid" : "fa-regular"} fa-bookmark" aria-hidden="true"></i>
                        </button>
                        <button type="button" class="inspect-btn qualified-trace-btn" data-symbol="${escapeDecisionHtml(symbol)}" title="Inspect ${escapeDecisionHtml(symbol)} trace" aria-label="Inspect ${escapeDecisionHtml(symbol)} trace">
                            <i class="fa-solid fa-search-plus" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
            `;
        }).join("");
        body.querySelectorAll(".qualified-open-decision-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                if (btn.disabled) return;
                const symbol = btn.getAttribute("data-symbol");
                closeValidationResultsFilterPopover();
                closeModal(document.getElementById("validation-funnel-modal"));
                await openDecisionForSymbol(symbol);
            });
        });
        body.querySelectorAll(".qualified-save-btn").forEach(btn => {
            btn.addEventListener("click", async () => {
                const symbol = btn.getAttribute("data-symbol");
                await toggleSavedSymbolNow(symbol, { button: btn });
                renderValidationResults(validationWorkbenchState.universe, validationWorkbenchState.qualified, validationWorkbenchState.universeNote);
            });
        });
        body.querySelectorAll(".qualified-trace-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const symbol = btn.getAttribute("data-symbol");
                if (typeof window.openTraceModal === "function") window.openTraceModal(symbol);
            });
        });
    }

    async function loadCandidateList() {
        const bodyEl = document.getElementById("candidate-list-body");
        const emptyEl = document.getElementById("candidate-list-empty");
        const countEl = document.getElementById("candidate-count");
        const candidateSearch = document.getElementById("candidate-search-input");
        if (!bodyEl) return;
        try {
            const res = await apiRequest("/api/v1/market/candidates");
            const rows = (res && res.data && res.data.candidates) ? res.data.candidates : [];
            bodyEl.innerHTML = "";
            populateUniverseSectorFilter(rows);
            if (countEl) {
                countEl.textContent = `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
            }
            if (rows.length === 0) {
                if (emptyEl) {
                    emptyEl.textContent = "No symbols in the universe yet.";
                    emptyEl.style.display = "block";
                }
                return;
            }
            if (emptyEl) emptyEl.style.display = "none";
            eligibilityDetailBySymbol.clear();
            rows.forEach(c => {
                const tr = document.createElement("tr");
                const status = String(c.status || "PENDING").toUpperCase();
                const sector = c.sector || "";
                tr.dataset.symbol = String(c.symbol || "").toUpperCase();
                tr.dataset.status = status;
                tr.dataset.sector = sector.toUpperCase();
                const statusClass = status === "ELIGIBLE"
                    ? "included"
                    : status === "EXCLUDED"
                        ? "excluded"
                        : status === "UNRESOLVED"
                            ? "unresolved"
                            : "pending";
                const statusLabel = status === "ELIGIBLE"
                    ? "Eligible"
                    : status === "EXCLUDED"
                        ? "Excluded"
                        : status === "UNRESOLVED"
                            ? "Unresolved"
                            : "Pending";
                const statusIcon = status === "ELIGIBLE"
                    ? "fa-check"
                    : status === "EXCLUDED"
                        ? "fa-ban"
                        : status === "UNRESOLVED"
                            ? "fa-triangle-exclamation"
                            : "fa-clock";
                const eligibility = c.eligibility_summary
                    ? String(c.eligibility_summary)
                    : "—";
                const eligibilityShort = compactEligibilitySummary(eligibility);
                const lastValidated = c.last_validated_ts
                    ? formatDecisionTime(c.last_validated_ts)
                    : "—";
                const lastValidatedShort = c.last_validated_ts
                    ? compactUniverseTime(c.last_validated_ts)
                    : "—";
                const canTrace = status === "ELIGIBLE" || status === "EXCLUDED";
                const symbol = String(c.symbol || "").toUpperCase();
                eligibilityDetailBySymbol.set(symbol, {
                    summary: eligibility,
                    evidence: Array.isArray(c.eligibility_evidence)
                        ? c.eligibility_evidence
                        : [],
                });
                tr.innerHTML = `
                    <td>
                        <div class="universe-symbol-cell">
                            <button type="button" class="candidate-save-toggle-btn" data-symbol="${c.symbol}"></button>
                            <strong class="symbol-name-col">${c.symbol}</strong>
                        </div>
                    </td>
                    <td class="text-muted universe-sector-cell" title="${String(sector || "—").replace(/"/g, "&quot;")}">${sector || "—"}</td>
                    <td>
                        <span class="symbol-status-badge ${statusClass}">
                            <i class="fas ${statusIcon}"></i>
                            ${statusLabel}
                        </span>
                    </td>
                    <td class="universe-eligibility-cell">
                        ${eligibility === "—"
                            ? "—"
                            : `<button type="button" class="eligibility-metric-btn" data-symbol="${c.symbol}" title="View passed and failed eligibility rules">${eligibilityShort}</button>`}
                    </td>
                    <td class="text-muted universe-validated-cell" title="${lastValidated.replace(/"/g, "&quot;")}">${lastValidatedShort}</td>
                    <td>
                        <div class="candidate-row-actions">
                            <button type="button" class="inspect-btn candidate-validate-btn" data-symbol="${c.symbol}" title="Re-run ingest + score">
                                <i class="fas fa-bolt"></i>
                            </button>
                            ${canTrace ? `<button type="button" class="inspect-btn candidate-trace-btn" data-symbol="${c.symbol}" title="Inspect Trace"><i class="fas fa-search"></i></button>` : ""}
                            <button type="button" class="inspect-btn candidate-remove-btn" data-symbol="${c.symbol}" title="Remove candidate">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </td>
                `;
                bodyEl.appendChild(tr);
            });
            syncUniverseSavedStars();
            applyUniverseFilters();
            bodyEl.querySelectorAll(".candidate-save-toggle-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await toggleSavedSymbolNow(sym, { button: btn });
                });
            });
            bodyEl.querySelectorAll(".eligibility-metric-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    showEligibilityDetail(btn.getAttribute("data-symbol"));
                });
            });
            bodyEl.querySelectorAll(".candidate-validate-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await validateSymbolsNow([sym], { button: btn, refreshDecisions: true, showReport: true });
                });
            });
            bodyEl.querySelectorAll(".candidate-remove-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await removeCandidateNow(sym, { button: btn });
                });
            });
            bodyEl.querySelectorAll(".candidate-trace-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const sym = btn.getAttribute("data-symbol");
                    if (sym && typeof window.openTraceModal === "function") {
                        window.openTraceModal(sym);
                    }
                });
            });
        } catch (err) {
            console.error("Failed to load candidates", err);
            if (emptyEl) {
                emptyEl.style.display = "block";
                emptyEl.textContent = "Failed to load universe list.";
            }
            if (countEl) countEl.textContent = "Unavailable";
        }
    }

    let universeIndexFilterKey = "all";
    let universeIndexFilterMemberSymbols = null;

    function populateUniverseIndexFilter() {
        const select = document.getElementById("universe-index-filter");
        if (!select) return;
        const current = select.value || "all";
        select.innerHTML = '<option value="all">All indices</option>' +
            universeIndexCatalog.map(item => `<option value="${item.key}">${item.label}</option>`).join("");
        select.value = universeIndexCatalog.some(item => item.key === current) ? current : "all";
    }

    function renderUniverseIndexFilterNote(cacheEntry) {
        const noteEl = document.getElementById("universe-index-filter-note");
        if (!noteEl) return;
        if (cacheEntry && cacheEntry.unresolvedCount > 0) {
            noteEl.textContent = `${cacheEntry.unresolvedCount} unresolved symbol${cacheEntry.unresolvedCount === 1 ? "" : "s"} not shown`;
            noteEl.style.display = "inline";
        } else {
            noteEl.textContent = "";
            noteEl.style.display = "none";
        }
    }

    async function applyUniverseIndexFilterSelection(key) {
        const select = document.getElementById("universe-index-filter");
        const noteEl = document.getElementById("universe-index-filter-note");
        universeIndexFilterKey = key;
        if (key === "all") {
            universeIndexFilterMemberSymbols = null;
            renderUniverseIndexFilterNote(null);
            applyUniverseFilters();
            return;
        }
        const cached = universeIndexMembersCache.get(key);
        if (cached) {
            universeIndexFilterMemberSymbols = cached.symbols;
            renderUniverseIndexFilterNote(cached);
            applyUniverseFilters();
            return;
        }
        const requestToken = ++universeIndexMembersRequestToken;
        if (select) select.disabled = true;
        if (noteEl) {
            noteEl.textContent = "Loading membership…";
            noteEl.style.display = "inline";
        }
        try {
            const entry = await fetchIndexMembers(key);
            if (requestToken !== universeIndexMembersRequestToken) return;
            universeIndexFilterMemberSymbols = entry.symbols;
            renderUniverseIndexFilterNote(entry);
        } catch (err) {
            console.error("Failed to load index members", err);
            if (requestToken !== universeIndexMembersRequestToken) return;
            universeIndexFilterMemberSymbols = new Set();
            if (noteEl) {
                noteEl.textContent = "Index membership unavailable.";
                noteEl.style.display = "inline";
            }
        } finally {
            if (requestToken === universeIndexMembersRequestToken) {
                if (select) select.disabled = false;
                applyUniverseFilters();
            }
        }
    }

    // IX-4b: Validation Workbench Results index filter — same catalog/cache
    // as the Universe filter above, independent selection state per surface.
    let validationResultsIndexFilterKey = "all";
    let validationResultsIndexMemberSymbols = null;

    function populateValidationResultsIndexFilter() {
        const select = document.getElementById("validation-results-index-filter");
        if (!select) return;
        const current = select.value || "all";
        select.innerHTML = '<option value="all">All indices</option>' +
            universeIndexCatalog.map(item => `<option value="${item.key}">${item.label}</option>`).join("");
        select.value = universeIndexCatalog.some(item => item.key === current) ? current : "all";
    }

    function renderValidationResultsIndexFilterNote(cacheEntry) {
        const noteEl = document.getElementById("validation-results-index-filter-note");
        if (!noteEl) return;
        if (cacheEntry && cacheEntry.unresolvedCount > 0) {
            noteEl.textContent = `${cacheEntry.unresolvedCount} unresolved symbol${cacheEntry.unresolvedCount === 1 ? "" : "s"} not shown`;
            noteEl.style.display = "inline";
        } else {
            noteEl.textContent = "";
            noteEl.style.display = "none";
        }
    }

    async function applyValidationResultsIndexFilterSelection(key) {
        validationResultsIndexFilterKey = key;
        if (key === "all") {
            validationResultsIndexMemberSymbols = null;
            renderValidationResultsIndexFilterNote(null);
            scheduleValidationResultsRender();
            return;
        }
        const cached = universeIndexMembersCache.get(key);
        if (cached) {
            validationResultsIndexMemberSymbols = cached.symbols;
            renderValidationResultsIndexFilterNote(cached);
            scheduleValidationResultsRender();
            return;
        }
        const requestToken = ++universeIndexMembersRequestToken;
        setValidationResultsBusy(true);
        try {
            const entry = await fetchIndexMembers(key);
            if (requestToken !== universeIndexMembersRequestToken) return;
            validationResultsIndexMemberSymbols = entry.symbols;
            renderValidationResultsIndexFilterNote(entry);
        } catch (err) {
            console.error("Failed to load index members", err);
            if (requestToken !== universeIndexMembersRequestToken) return;
            validationResultsIndexMemberSymbols = new Set();
            const noteEl = document.getElementById("validation-results-index-filter-note");
            if (noteEl) {
                noteEl.textContent = "Index membership unavailable.";
                noteEl.style.display = "inline";
            }
        } finally {
            if (requestToken === universeIndexMembersRequestToken) {
                // scheduleValidationResultsRender's own busy toggle re-enables
                // this control once the debounced render completes.
                scheduleValidationResultsRender();
            }
        }
    }

    function populateUniverseSectorFilter(rows) {
        const select = document.getElementById("universe-sector-filter");
        if (!select) return;
        const current = select.value || "all";
        const sectors = [...new Set(
            rows.map(r => String(r.sector || "").trim()).filter(Boolean)
        )].sort((a, b) => a.localeCompare(b));
        select.innerHTML = '<option value="all">All sectors</option>' +
            sectors.map(s => `<option value="${s}">${s}</option>`).join("");
        select.value = sectors.includes(current) ? current : "all";
    }

    function applyUniverseFilters() {
        const bodyEl = document.getElementById("candidate-list-body");
        const emptyEl = document.getElementById("candidate-list-empty");
        const countEl = document.getElementById("candidate-count");
        const searchEl = document.getElementById("candidate-search-input");
        const statusEl = document.getElementById("universe-status-filter");
        const sectorEl = document.getElementById("universe-sector-filter");
        if (!bodyEl) return;
        const query = String((searchEl && searchEl.value) || "").trim().toUpperCase();
        const statusFilter = String((statusEl && statusEl.value) || "all").toUpperCase();
        const sectorFilter = String((sectorEl && sectorEl.value) || "all").toUpperCase();
        const indexFilterActive = universeIndexFilterKey !== "all";
        updateUniverseFilterToggleActiveState(statusFilter !== "ALL" || sectorFilter !== "ALL" || indexFilterActive);
        const rows = Array.from(bodyEl.querySelectorAll("tr"));
        let visible = 0;
        rows.forEach(row => {
            const matchesQuery = !query || (row.dataset.symbol || "").includes(query);
            const matchesStatus = statusFilter === "ALL" || (row.dataset.status || "") === statusFilter;
            const matchesSector = sectorFilter === "ALL" || (row.dataset.sector || "") === sectorFilter;
            const matchesIndex = !indexFilterActive
                || (universeIndexFilterMemberSymbols
                    ? universeIndexFilterMemberSymbols.has(row.dataset.symbol || "")
                    : false);
            const show = matchesQuery && matchesStatus && matchesSector && matchesIndex;
            row.hidden = !show;
            if (show) visible += 1;
        });
        if (countEl) {
            const filtering = query || statusFilter !== "ALL" || sectorFilter !== "ALL" || indexFilterActive;
            countEl.textContent = filtering
                ? `${visible} of ${rows.length}`
                : `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
        }
        if (emptyEl) {
            emptyEl.textContent = visible === 0
                ? (rows.length === 0 ? "No symbols in the universe yet." : "No symbols match the current filters.")
                : "No symbols in the universe yet.";
            emptyEl.style.display = visible === 0 ? "block" : "none";
        }
    }

    function filterCandidateList(rawQuery) {
        applyUniverseFilters();
    }

    const candidateAddBtn = document.getElementById("candidate-add-btn");
    const candidateSearchInput = document.getElementById("candidate-search-input");
    const candidateSearchClear = document.getElementById("candidate-search-clear");
    const candidateInput = candidateSearchInput;

    function updateCandidateSearchClear() {
        if (!candidateSearchInput || !candidateSearchClear) return;
        candidateSearchClear.hidden = !candidateSearchInput.value.trim();
    }

    if (candidateSearchInput) {
        candidateSearchInput.addEventListener("input", () => {
            updateCandidateSearchClear();
            applyUniverseFilters();
        });
        updateCandidateSearchClear();
    }
    candidateSearchClear?.addEventListener("click", () => {
        if (!candidateSearchInput) return;
        candidateSearchInput.value = "";
        updateCandidateSearchClear();
        applyUniverseFilters();
        candidateSearchInput.focus();
    });
    const universeStatusFilter = document.getElementById("universe-status-filter");
    if (universeStatusFilter) {
        universeStatusFilter.addEventListener("change", () => applyUniverseFilters());
    }
    const universeSectorFilter = document.getElementById("universe-sector-filter");
    if (universeSectorFilter) {
        universeSectorFilter.addEventListener("change", () => applyUniverseFilters());
    }
    const universeIndexFilter = document.getElementById("universe-index-filter");
    if (universeIndexFilter) {
        universeIndexFilter.addEventListener("change", () => {
            applyUniverseIndexFilterSelection(universeIndexFilter.value || "all");
        });
    }

    // Owner-reported: search + 3 filter selects + action button wrapped to
    // two lines. Moves Status/Sector/Index behind a "Filters" popover,
    // mirroring the exact same toggle/popover/close/Escape pattern already
    // used by Decisions & Trace (#symbols-filter-toggle/-popover). No
    // backdrop here — unlike the Decisions left rail, this toolbar has no
    // large content area to dim, and the existing click-outside listener
    // below already closes the popover without one.
    const universeFilterToggle = document.getElementById("universe-filter-toggle");
    const universeFilterPopover = document.getElementById("universe-filter-popover");
    const universeFilterClose = document.getElementById("universe-filter-close");
    const universeFilterReset = document.getElementById("universe-filter-reset");

    function updateUniverseFilterToggleActiveState(active) {
        universeFilterToggle?.classList.toggle("has-active-filters", active);
    }

    function closeUniverseFilterPopover() {
        if (!universeFilterPopover || universeFilterPopover.hidden) return;
        universeFilterPopover.hidden = true;
        universeFilterToggle?.setAttribute("aria-expanded", "false");
    }

    universeFilterToggle?.addEventListener("click", event => {
        event.stopPropagation();
        const willOpen = universeFilterPopover.hidden;
        universeFilterPopover.hidden = !willOpen;
        universeFilterToggle.setAttribute("aria-expanded", String(willOpen));
    });
    universeFilterClose?.addEventListener("click", event => {
        event.stopPropagation();
        closeUniverseFilterPopover();
    });
    universeFilterReset?.addEventListener("click", () => {
        if (universeStatusFilter) universeStatusFilter.value = "all";
        if (universeSectorFilter) universeSectorFilter.value = "all";
        if (universeIndexFilter) universeIndexFilter.value = "all";
        applyUniverseIndexFilterSelection("all");
    });
    document.addEventListener("click", event => {
        if (!universeFilterPopover || universeFilterPopover.hidden) return;
        if (universeFilterPopover.contains(event.target) || event.target === universeFilterToggle) return;
        closeUniverseFilterPopover();
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeUniverseFilterPopover();
    });

    if (candidateAddBtn && candidateInput) {
        const addAndValidateCandidate = async () => {
            const symbol = (candidateInput.value || "").trim().toUpperCase();
            if (!symbol) {
                showToast("Enter a symbol", "danger");
                return;
            }
            candidateInput.value = "";
            applyUniverseFilters();
            await validateSymbolsNow([symbol], { button: candidateAddBtn, refreshDecisions: true, showReport: true });
        };
        candidateAddBtn.addEventListener("click", addAndValidateCandidate);
    }

    // UX-9b: "Saved Symbols" — a passive personal watch list, deliberately
    // independent of the Stock List / owner-candidates validation list above
    // (saving a symbol here never seeds ingest/scoring) and of the automated
    // M4.3 watchlist package (that one is fully config-driven, no owner input).
    async function removeSavedSymbolNow(symbol, { button = null } = {}) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return false;
        const previous = button ? button.innerHTML : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing…';
        }
        try {
            await apiRequest(
                `/api/v1/saved-symbols/${encodeURIComponent(bare)}`,
                { method: "DELETE", skipToast: true }
            );
            showToast(`${bare} removed from Saved Symbols`, "success");
            await loadSavedSymbols();
            return true;
        } catch (err) {
            if (err?.status === 404) {
                showToast(`${bare} is not in Saved Symbols`, "warning");
            } else {
                const detail = err?.data?.detail;
                showToast(
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : `Failed to remove ${bare} from Saved Symbols`,
                    "danger"
                );
            }
            return false;
        } finally {
            if (button) {
                button.disabled = false;
                if (previous != null) button.innerHTML = previous;
            }
        }
    }

    async function loadSavedSymbols() {
        const listEl = document.getElementById("saved-symbols-list");
        const emptyEl = document.getElementById("saved-symbols-empty");
        const countEl = document.getElementById("saved-symbols-count");
        if (!listEl) return;
        try {
            const res = await apiRequest("/api/v1/saved-symbols");
            const rows = (res && res.data && res.data.symbols) ? res.data.symbols : [];
            savedSymbolSet.clear();
            rows.forEach(s => {
                const symbol = String(s.symbol || "").trim().toUpperCase();
                if (symbol) savedSymbolSet.add(symbol);
            });
            syncUniverseSavedStars();
            listEl.innerHTML = "";
            if (countEl) {
                countEl.textContent = `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
            }
            if (rows.length === 0) {
                if (emptyEl) emptyEl.style.display = "block";
                return;
            }
            if (emptyEl) emptyEl.style.display = "none";
            rows.forEach(s => {
                const li = document.createElement("li");
                li.className = "candidate-row";
                li.dataset.symbol = String(s.symbol || "").toUpperCase();
                li.innerHTML = `
                    <span class="symbol-name-col">${s.symbol}</span>
                    <div class="candidate-row-actions">
                        <button type="button" class="inspect-btn saved-symbol-action-btn saved-symbol-validate-btn" data-symbol="${s.symbol}" title="Validate saved symbol" aria-label="Validate ${s.symbol}">
                            <i class="fas fa-bolt" aria-hidden="true"></i>
                        </button>
                        <button type="button" class="inspect-btn saved-symbol-action-btn saved-symbol-remove-btn" data-symbol="${s.symbol}" title="Remove saved symbol" aria-label="Remove ${s.symbol}">
                            <i class="fas fa-times" aria-hidden="true"></i>
                        </button>
                    </div>
                `;
                listEl.appendChild(li);
            });
            listEl.querySelectorAll(".saved-symbol-validate-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await validateSymbolsNow([sym], { button: btn, refreshDecisions: true, showReport: true });
                });
            });
            listEl.querySelectorAll(".saved-symbol-remove-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await removeSavedSymbolNow(sym, { button: btn });
                });
            });
        } catch (err) {
            console.error("Failed to load saved symbols", err);
            if (emptyEl) {
                emptyEl.style.display = "block";
                emptyEl.textContent = "Failed to load Saved Symbols.";
            }
            if (countEl) countEl.textContent = "Unavailable";
        }
    }

    const savedSymbolAddBtn = document.getElementById("saved-symbol-add-btn");
    const savedSymbolInput = document.getElementById("saved-symbol-input");
    if (savedSymbolAddBtn && savedSymbolInput) {
        const addSavedSymbol = async () => {
            const symbol = (savedSymbolInput.value || "").trim().toUpperCase();
            if (!symbol) {
                showToast("Enter a symbol", "danger");
                return;
            }
            const previous = savedSymbolAddBtn.innerHTML;
            savedSymbolAddBtn.disabled = true;
            savedSymbolAddBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';
            try {
                await apiRequest("/api/v1/saved-symbols", {
                    method: "POST",
                    body: JSON.stringify({ symbol }),
                    skipToast: true,
                });
                savedSymbolInput.value = "";
                showToast(`${symbol} saved to your watch list`, "success");
                await loadSavedSymbols();
            } catch (err) {
                const detail = err?.data?.detail;
                showToast(
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : `Failed to save ${symbol}`,
                    "danger"
                );
            } finally {
                savedSymbolAddBtn.disabled = false;
                savedSymbolAddBtn.innerHTML = previous;
            }
        };
        savedSymbolAddBtn.addEventListener("click", addSavedSymbol);
        savedSymbolInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                addSavedSymbol();
            }
        });
    }

    function renderCurrentValidationResults() {
        renderValidationResults(
            validationWorkbenchState.universe,
            validationWorkbenchState.qualified,
            validationWorkbenchState.universeNote
        );
    }

    function scheduleValidationResultsRender() {
        if (validationResultsRenderTimerId) window.clearTimeout(validationResultsRenderTimerId);
        setValidationResultsBusy(true);
        validationResultsRenderTimerId = window.setTimeout(() => {
            window.requestAnimationFrame(() => {
                try {
                    renderCurrentValidationResults();
                } finally {
                    setValidationResultsBusy(false);
                    validationResultsRenderTimerId = null;
                }
            });
        }, 90);
    }

    const validationResultsSearch = document.getElementById("universe-search");
    const validationResultsSearchClear = document.getElementById("universe-search-clear");

    function updateValidationResultsSearchClear() {
        if (!validationResultsSearch || !validationResultsSearchClear) return;
        validationResultsSearchClear.hidden = !validationResultsSearch.value.trim();
    }
    const validationResultsOutcomeFilter = document.getElementById("validation-results-outcome-filter");
    const validationResultsPlanFilter = document.getElementById("validation-results-plan-filter");
    const validationResultsIndexFilter = document.getElementById("validation-results-index-filter");
    const validationResultsSort = document.getElementById("validation-results-sort");
    const validationResultsReset = document.getElementById("validation-results-filter-reset");
    if (validationResultsSearch) {
        validationResultsSearch.addEventListener("input", () => {
            updateValidationResultsSearchClear();
            scheduleValidationResultsRender();
        });
        updateValidationResultsSearchClear();
    }
    validationResultsSearchClear?.addEventListener("click", () => {
        if (!validationResultsSearch) return;
        validationResultsSearch.value = "";
        updateValidationResultsSearchClear();
        scheduleValidationResultsRender();
        validationResultsSearch.focus();
    });
    // Owner-reported (2026-08-01, third round): picking a value left the
    // popover open — a completed choice, not a mid-adjustment the owner
    // needs the panel open for, so each select closes it after applying.
    [validationResultsOutcomeFilter, validationResultsPlanFilter, validationResultsSort].forEach(control => {
        if (control) control.addEventListener("change", () => {
            scheduleValidationResultsRender();
            closeValidationResultsFilterPopover();
        });
    });
    if (validationResultsIndexFilter) {
        validationResultsIndexFilter.addEventListener("change", () => {
            applyValidationResultsIndexFilterSelection(validationResultsIndexFilter.value || "all");
            closeValidationResultsFilterPopover();
        });
    }
    if (validationResultsReset) {
        validationResultsReset.addEventListener("click", () => {
            if (validationResultsOutcomeFilter) validationResultsOutcomeFilter.value = "all";
            if (validationResultsPlanFilter) validationResultsPlanFilter.value = "all";
            if (validationResultsIndexFilter) validationResultsIndexFilter.value = "all";
            validationResultsIndexFilterKey = "all";
            validationResultsIndexMemberSymbols = null;
            renderValidationResultsIndexFilterNote(null);
            if (validationResultsSort) validationResultsSort.value = "score-desc";
            scheduleValidationResultsRender();
        });
    }

    // Owner-reported: Outcome/Plan/Index/Sort wrapped to two lines. Moves
    // them behind a "Filters" popover, mirroring the same toggle/backdrop/
    // close/Escape pattern used by Decisions & Trace and the Universe card.
    const validationResultsFilterToggle = document.getElementById("validation-results-filter-toggle");
    const validationResultsFilterPopover = document.getElementById("validation-results-filter-popover");
    const validationResultsFilterClose = document.getElementById("validation-results-filter-close");
    const validationResultsFilterPopoverHome = { parent: null, nextSibling: null };

    function updateValidationResultsFilterToggleActiveState(filters) {
        const active = filters.outcome !== "all" || filters.plan !== "all"
            || filters.index !== "all" || filters.sort !== "score-desc";
        validationResultsFilterToggle?.classList.toggle("has-active-filters", active);
    }

    // Unlike Universe/Decisions, this toggle sits inside a scrollable modal
    // body (.validation-funnel-modal-body, overflow-y: auto). overflow clips
    // ANY descendant that visually extends past it — including an absolutely
    // or fixed positioned popover — regardless of how correct its top/left
    // math is, because clipping follows DOM containment, not the positioned
    // element's containing block. No amount of coordinate math escapes that;
    // the popover has to actually leave that DOM subtree while open.
    function moveValidationResultsFilterPopoverToBody() {
        if (!validationResultsFilterPopover || validationResultsFilterPopover.parentElement === document.body) return;
        validationResultsFilterPopoverHome.parent = validationResultsFilterPopover.parentElement;
        validationResultsFilterPopoverHome.nextSibling = validationResultsFilterPopover.nextSibling;
        document.body.appendChild(validationResultsFilterPopover);
    }

    function restoreValidationResultsFilterPopoverHome() {
        if (!validationResultsFilterPopover || !validationResultsFilterPopoverHome.parent) return;
        validationResultsFilterPopoverHome.parent.insertBefore(validationResultsFilterPopover, validationResultsFilterPopoverHome.nextSibling);
        validationResultsFilterPopoverHome.parent = null;
        validationResultsFilterPopoverHome.nextSibling = null;
    }

    function closeValidationResultsFilterPopover() {
        if (!validationResultsFilterPopover || validationResultsFilterPopover.hidden) return;
        validationResultsFilterPopover.hidden = true;
        validationResultsFilterToggle?.setAttribute("aria-expanded", "false");
        restoreValidationResultsFilterPopoverHome();
    }

    function openValidationResultsFilterPopover() {
        if (!validationResultsFilterPopover) return;
        moveValidationResultsFilterPopoverToBody();
        // Now a direct child of body (no transformed/overflow-clipping
        // ancestor in between), so position:fixed is plain viewport math —
        // no container-relative re-basing needed.
        validationResultsFilterPopover.style.position = "fixed";
        // As a body child it's a sibling of .modal-overlay (z-index 2000),
        // not a descendant of the modal's own stacking context anymore, so
        // its base z-index: 20 would paint BEHIND the modal it belongs to.
        // 2200 clears both modal layers (2000/2100 stacked) while staying
        // below every blocking gate (validate-overlay 9000, Kite/unlock
        // 10000/11000), which must still cover it if one opens mid-filter.
        validationResultsFilterPopover.style.zIndex = "2200";
        const rect = validationResultsFilterToggle.getBoundingClientRect();
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 720;
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1280;
        const margin = 8;
        const minUsableHeight = 160;
        // Owner-reported: clamping to the full viewport let the popover
        // visually spill past the dialog card's own right/bottom edge onto
        // the backdrop — it belongs to this modal, so it must stay inside
        // the modal's own box, not just somewhere on screen.
        const modalEl = validationResultsFilterToggle.closest(".modal-container");
        const modalRect = modalEl ? modalEl.getBoundingClientRect() : null;
        const boundsTop = Math.max(margin, modalRect ? modalRect.top : margin);
        const boundsBottom = Math.min(viewportHeight - margin, modalRect ? modalRect.bottom : viewportHeight - margin);
        const boundsLeft = Math.max(margin, modalRect ? modalRect.left : margin);
        const boundsRight = Math.min(viewportWidth - margin, modalRect ? modalRect.right : viewportWidth - margin);
        // Purely geometric (toggle rect vs modal bounds) — never measures the
        // popover's own box, which would read as zero height while still
        // `hidden`. Opens below by default; flips above only when there's
        // truly more room there, so it can never render overlapping or
        // past the toggle itself.
        const spaceBelow = boundsBottom - rect.bottom - 4;
        const spaceAbove = rect.top - boundsTop - 4;
        // Anchor by the toggle's own left edge (it sits near the LEFT of
        // this toolbar, unlike Universe/Decisions where it sits near the
        // right) — right-aligning here would push a 260px-wide popover
        // off the left edge of the modal entirely. Clamp so it also never
        // overflows the modal's right edge.
        const popoverWidth = validationResultsFilterPopover.offsetWidth || 260;
        const left = Math.min(rect.left, Math.max(boundsLeft, boundsRight - popoverWidth));
        validationResultsFilterPopover.style.left = `${left}px`;
        validationResultsFilterPopover.style.right = "auto";
        if (spaceBelow >= minUsableHeight || spaceBelow >= spaceAbove) {
            validationResultsFilterPopover.style.bottom = "auto";
            validationResultsFilterPopover.style.top = `${rect.bottom + 4}px`;
            validationResultsFilterPopover.style.maxHeight = `${Math.max(minUsableHeight, spaceBelow)}px`;
        } else {
            validationResultsFilterPopover.style.top = "auto";
            validationResultsFilterPopover.style.bottom = `${viewportHeight - rect.top + 4}px`;
            validationResultsFilterPopover.style.maxHeight = `${Math.max(minUsableHeight, spaceAbove)}px`;
        }
        validationResultsFilterPopover.hidden = false;
        validationResultsFilterToggle.setAttribute("aria-expanded", "true");
    }

    validationResultsFilterToggle?.addEventListener("click", event => {
        event.stopPropagation();
        if (validationResultsFilterPopover.hidden) {
            openValidationResultsFilterPopover();
        } else {
            closeValidationResultsFilterPopover();
        }
    });
    validationResultsFilterClose?.addEventListener("click", event => {
        event.stopPropagation();
        closeValidationResultsFilterPopover();
    });
    document.addEventListener("click", event => {
        if (!validationResultsFilterPopover || validationResultsFilterPopover.hidden) return;
        if (validationResultsFilterPopover.contains(event.target) || event.target === validationResultsFilterToggle) return;
        closeValidationResultsFilterPopover();
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeValidationResultsFilterPopover();
    });

    // MI-3 polish: View Details opens a modal (Eligible/Excluded + Qualified)
    // instead of expanding inline — keeps the funnel compact and the Stock List
    // as the only primary scroll region in the right column.
    const funnelDetailsBtn = document.getElementById("validation-funnel-details-btn");
    const funnelDetailsModal = document.getElementById("validation-funnel-modal");
    const funnelDetailsClose = document.getElementById("validation-funnel-modal-close");

    const runFullValidationBtn = document.getElementById("mi-run-full-validation-btn");
    const universeValidateAllBtn = document.getElementById("universe-validate-all-btn");
    const focusAddSymbolBtn = document.getElementById("mi-focus-add-symbol-btn");
    const refreshMarketBtn = document.getElementById("mi-refresh-market-btn");
    if (runFullValidationBtn) {
        runFullValidationBtn.addEventListener("click", () => startFullUniverseValidation());
    }
    if (universeValidateAllBtn) {
        universeValidateAllBtn.addEventListener("click", () => startFullUniverseValidation());
    }
    if (focusAddSymbolBtn) {
        focusAddSymbolBtn.addEventListener("click", () => {
            const input = document.getElementById("candidate-search-input");
            if (input) {
                input.focus();
                input.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
    }
    if (refreshMarketBtn) {
        refreshMarketBtn.addEventListener("click", async () => {
            showToast("Refreshing market view…", "info");
            if (typeof loadMarketIntelligence === "function") {
                await loadMarketIntelligence();
            }
        });
    }
    if (funnelDetailsBtn && funnelDetailsModal) {
        funnelDetailsBtn.addEventListener("click", () => {
            setValidationWorkbenchTab("overview");
            const body = funnelDetailsModal.querySelector(".validation-funnel-modal-body");
            if (body) body.scrollTop = 0;
            openModal(funnelDetailsModal);
        });
    }
    function setValidationWorkbenchTab(target) {
        if (target !== "symbols") closeValidationResultsFilterPopover();
        document.querySelectorAll("[data-validation-workbench-tab]").forEach(btn => {
            const active = btn.getAttribute("data-validation-workbench-tab") === target;
            btn.classList.toggle("is-active", active);
        });
        document.querySelectorAll("[data-validation-workbench-pane]").forEach(pane => {
            const active = pane.getAttribute("data-validation-workbench-pane") === target;
            pane.classList.toggle("is-active", active);
            pane.hidden = !active;
        });
    }
    document.querySelectorAll("[data-validation-workbench-tab]").forEach(tab => {
        tab.addEventListener("click", () => {
            setValidationWorkbenchTab(tab.getAttribute("data-validation-workbench-tab"));
        });
    });
    if (funnelDetailsClose) {
        funnelDetailsClose.addEventListener("click", () => {
            closeValidationResultsFilterPopover();
            closeModal(funnelDetailsModal);
        });
    }
    if (funnelDetailsModal) {
        funnelDetailsModal.addEventListener("click", (event) => {
            if (event.target === funnelDetailsModal) {
                closeValidationResultsFilterPopover();
                closeModal(funnelDetailsModal);
            }
        });
    }

    // Modal drawer helpers — keep inactive overlays fully out of layout
    const traceModal = document.getElementById("trace-modal");
    const traceModalClose = document.getElementById("trace-modal-close");
    const traceModalTitle = document.getElementById("trace-modal-title");
    const traceModalBody = document.getElementById("trace-modal-body");
    const eligibilityDetailModal = document.getElementById("eligibility-detail-modal");
    const eligibilityDetailClose = document.getElementById("eligibility-detail-close");

    // Rule outcomes come from the persisted `evidence` array only. A previous
    // version inferred them by searching each explanation for "(PASS)", a
    // marker the UniverseEngine never writes, so every real rule rendered FAIL
    // — including for symbols that passed all of them.
    window.openTraceModal = function(symbol) {
        const member = universeCache[symbol];
        if (!member) return;

        traceModalTitle.textContent = `${symbol} Universe Inclusion Trace`;
        traceModalBody.innerHTML = "";

        const traceList = document.createElement("div");
        traceList.className = "trace-logs-list";

        const evidence = Array.isArray(member.evidence) ? member.evidence : [];
        const traceLines = Array.isArray(member.trace) ? member.trace : [];

        if (evidence.length > 0) {
            evidence.forEach(item => {
                const isPass = Boolean(item.passed);
                const step = document.createElement("div");
                step.className = `trace-step-item ${isPass ? "pass" : "fail"}`;

                const header = document.createElement("div");
                header.className = "trace-step-header";
                const rule = document.createElement("span");
                rule.className = "trace-step-rule";
                rule.textContent = friendlyEligibilityRule(item.rule);
                const status = document.createElement("span");
                status.className = `trace-step-status ${isPass ? "pass" : "fail"}`;
                status.textContent = isPass ? "PASS" : "FAIL";
                header.append(rule, status);

                const detail = document.createElement("span");
                detail.className = "trace-step-detail";
                detail.textContent = String(item.explanation || "No explanation recorded.");

                step.append(header, detail);
                traceList.appendChild(step);
            });
        } else if (traceLines.length > 0) {
            // Older runs persisted explanations without per-rule outcomes. Show
            // them verbatim rather than guessing a pass/fail state.
            traceLines.forEach(logLine => {
                const step = document.createElement("div");
                step.className = "trace-step-item";
                const detail = document.createElement("span");
                detail.className = "trace-step-detail";
                detail.textContent = String(logLine);
                step.appendChild(detail);
                traceList.appendChild(step);
            });
        } else {
            traceList.innerHTML = `<div class="text-muted text-center">No step-by-step trace logged for this symbol.</div>`;
        }

        traceModalBody.appendChild(traceList);
        openModal(traceModal);
    };

    if (traceModalClose) {
        traceModalClose.addEventListener("click", () => {
            closeModal(traceModal);
        });
    }
    if (eligibilityDetailClose && eligibilityDetailModal) {
        eligibilityDetailClose.addEventListener("click", () => {
            closeModal(eligibilityDetailModal);
        });
    }
    window.addEventListener("click", (e) => {
        if (e.target === traceModal) {
            closeModal(traceModal);
        }
        if (e.target === eligibilityDetailModal) {
            closeModal(eligibilityDetailModal);
        }
    });
