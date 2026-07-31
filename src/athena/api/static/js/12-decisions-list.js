

    // ---------------------------------------------------------------------------
    // Decisions & Trace DAG Handlers
    // ---------------------------------------------------------------------------
    const decisionsCarouselContainer = document.getElementById("decisions-carousel-groups");
    const decisionsScrollTopBtn = document.getElementById("decisions-scroll-top");
    const briefingSearch = document.getElementById("briefing-search");
    const briefingSearchClear = document.getElementById("briefing-search-clear");
    const decisionsRevalidateVisibleBtn = document.getElementById("decisions-revalidate-visible-btn");
    const decisionsRevalidateStatus = document.getElementById("decisions-revalidate-status");
    const QUICK_VISIBLE_REVALIDATE_LIMIT = 5;
    const QUICK_VISIBLE_REVALIDATE_COOLDOWN_MS = 60000;
    const TOP_CURRENT_SETUPS_LIMIT = 10;
    let nextBoardRevalidateAllowedAt = 0;
    let boardRevalidateCooldownTimer = null;
    const BOARD_REVALIDATE_READY_HTML = '<i class="fa-solid fa-arrows-rotate"></i>';
    let boardRevalidateStatusTone = "neutral";

    function updateDecisionListScrollTopButton() {
        if (!decisionsScrollTopBtn || !decisionsCarouselContainer) return;
        decisionsScrollTopBtn.hidden = decisionsCarouselContainer.scrollTop < 180;
    }

    function scrollDecisionListToTop() {
        if (!decisionsCarouselContainer) return;
        decisionsCarouselContainer.scrollTo({ top: 0, behavior: "smooth" });
        decisionsScrollTopBtn.hidden = true;
    }

    function updateBriefingSearchClear() {
        if (!briefingSearch || !briefingSearchClear) return;
        briefingSearchClear.hidden = !briefingSearch.value.trim();
    }

    function clearBriefingSearch() {
        if (!briefingSearch) return;
        briefingSearch.value = "";
        updateBriefingSearchClear();
        applyDecisionsView();
        briefingSearch.focus();
    }

    function dismissDecisionForToday(decision) {
        const key = decisionInstrumentKey(decision);
        if (!key) return;
        dismissedDecisionSymbols.add(key);
        persistDismissedDecisionSymbols();
        showToast(`${key.includes(":") ? key.split(":").pop() : key} dismissed for today`, "success");
        applyDecisionsView();
    }

    function restoreDismissedDecisions() {
        dismissedDecisionSymbols.clear();
        persistDismissedDecisionSymbols();
        showToast("Dismissed decisions restored", "success");
        applyDecisionsView();
    }

    /** Keep the newest decision per instrument (or decision_id when instrument is missing). */
    function latestDecisionPerInstrument(rows) {
        const byInstrument = new Map();
        for (const d of rows || []) {
            const meta = d && d.metadata ? d.metadata : {};
            const key = meta.instrument_id || meta.decision_id;
            if (!key) continue;
            const prev = byInstrument.get(key);
            const ts = new Date(meta.ts || 0).getTime();
            const prevTs = prev
                ? new Date((prev.metadata && prev.metadata.ts) || 0).getTime()
                : -1;
            if (!prev || ts >= prevTs) {
                byInstrument.set(key, d);
            }
        }
        return Array.from(byInstrument.values());
    }

    /**
     * Walk /api/v1/decisions pages before client dedupe.
     * Default API page_size is 20 (max 100); a single page silently drops symbols
     * after large validate/seed runs.
     */
    async function fetchAllDecisionPages() {
        const pageSize = 100;
        const maxPages = 50;
        const collected = [];
        let page = 1;
        let hasNext = true;

        while (hasNext && page <= maxPages) {
            const qs = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
                sort_by: "ts",
                sort_dir: "desc",
            });
            const res = await apiRequest(`/api/v1/decisions?${qs.toString()}`);
            if (!res || res.status !== "success") {
                throw new Error("decisions list returned a non-success envelope");
            }
            const batch = Array.isArray(res.data) ? res.data : [];
            collected.push(...batch);
            hasNext = Boolean(res.pagination && res.pagination.has_next);
            page += 1;
            if (!batch.length) {
                break;
            }
        }
        return collected;
    }

    async function loadDecisionsWorkspace(options = {}) {
        try {
            const raw = await fetchAllDecisionPages();
            allTraceDecisionsList = raw;
            // Latest decision per instrument for "Today's Decisions" (avoid duplicate cards)
            traceDecisionsList = latestDecisionPerInstrument(raw);
            return applyDecisionsView(options);
        } catch (err) {
            console.error("Failed to load decisions", err);
            if (decisionsCarouselContainer) {
                decisionsCarouselContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">Failed to load decisions. Use refresh to retry.</div>';
            }
            if (dagNodesContainer) {
                dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">Decision trace unavailable until briefings load.</div>';
            }
            showToast("Failed to load decisions workspace", "danger");
            return null;
        }
    }

    function decisionListSectionType(d) {
        const rawType = String((d && d.metadata && d.metadata.decision_type) || "OTHER").toUpperCase();
        if (rawType !== "TRADE") return rawType;
        // The list is an action board, not the audit log. A historical TRADE
        // whose plan is no longer usable must not remain under the actionable
        // Trade section; the detail pane still preserves the original thesis.
        return decisionHasCurrentActionableTradePlan(d) ? "TRADE" : "NO_TRADE";
    }

    function decisionListPriority(d) {
        const t = decisionListSectionType(d);
        return DECISION_TYPE_PRIORITY[t] ?? 9;
    }

    function isCurrentDecisionListRow(d) {
        // Decisions & Trace's left rail is a current action board. Expired
        // historical TRADE records stay available in audit/history, but they
        // must not keep reappearing in the board or in Restore.
        return !decisionHasHistoricalTradePlan(d);
    }

    function topSetupNumericValue(...values) {
        for (const value of values) {
            const n = Number(value);
            if (Number.isFinite(n)) return n;
        }
        return null;
    }

    function decisionConfidenceValue(d) {
        const confidence = d && d.confidence ? d.confidence : {};
        return topSetupNumericValue(
            confidence.score,
            confidence.confidence,
            confidence.confidence_score,
            confidence.overall,
            d && d.metadata && d.metadata.confidence
        );
    }

    function decisionRiskValue(d) {
        const risk = d && d.risk ? d.risk : {};
        return topSetupNumericValue(
            risk.score,
            risk.risk_score,
            risk.overall,
            d && d.metadata && d.metadata.risk
        );
    }

    function decisionExpectedReturnPctValue(d) {
        const plan = d && d.trade_plan ? d.trade_plan : null;
        if (!plan) return null;
        const persisted = topSetupNumericValue(plan.expected_return_pct, plan.expected_return);
        if (persisted !== null) return persisted;

        const entryMid = (Number(plan.entry_low) + Number(plan.entry_high)) / 2;
        const target = Array.isArray(plan.targets) && plan.targets.length
            ? Number(plan.targets[0])
            : topSetupNumericValue(plan.target, plan.target_price);
        if (!Number.isFinite(entryMid) || entryMid === 0 || !Number.isFinite(target)) return null;
        const direction = d && d.metadata ? d.metadata.direction : "";
        const isShort = String(direction || "").toUpperCase() === "SHORT";
        return isShort ? ((entryMid - target) / entryMid) * 100 : ((target - entryMid) / entryMid) * 100;
    }

    function decisionRiskRewardValue(d) {
        const plan = d && d.trade_plan ? d.trade_plan : {};
        const numeric = topSetupNumericValue(
            plan.risk_reward,
            plan.risk_reward_ratio,
            plan.risk_reward_multiple,
            plan.reward_risk
        );
        if (numeric !== null) return numeric;
        const text = String(plan.risk_reward || plan.risk_reward_ratio || "");
        const match = text.match(/(\d+(?:\.\d+)?)\s*:/);
        return match ? Number(match[1]) : null;
    }

    function isTopCurrentSetup(d) {
        const freshness = inferTradePlanFreshness(d && d.trade_plan);
        const status = String(freshness && freshness.status || "").toUpperCase();
        return isCurrentDecisionListRow(d)
            && decisionListSectionType(d) === "TRADE"
            && decisionHasCurrentActionableTradePlan(d, freshness)
            && (status === "FRESH" || status === "AGING");
    }

    function sortTopCurrentSetups(a, b) {
        const score = decisionScoreValue(b) - decisionScoreValue(a);
        if (score) return score;
        const confidence = (decisionConfidenceValue(b) ?? -1) - (decisionConfidenceValue(a) ?? -1);
        if (confidence) return confidence;
        const risk = (decisionRiskValue(a) ?? 999) - (decisionRiskValue(b) ?? 999);
        if (risk) return risk;
        const expectedReturn = (decisionExpectedReturnPctValue(b) ?? -999) - (decisionExpectedReturnPctValue(a) ?? -999);
        if (expectedReturn) return expectedReturn;
        const riskReward = (decisionRiskRewardValue(b) ?? -1) - (decisionRiskRewardValue(a) ?? -1);
        if (riskReward) return riskReward;
        const ta = new Date((a.metadata && a.metadata.ts) || 0).getTime();
        const tb = new Date((b.metadata && b.metadata.ts) || 0).getTime();
        if (tb !== ta) return tb - ta;
        const sa = (a.metadata && a.metadata.instrument_id) || "";
        const sb = (b.metadata && b.metadata.instrument_id) || "";
        return sa.localeCompare(sb);
    }

    function topCurrentSetups(decisions) {
        return (decisions || [])
            .filter(isTopCurrentSetup)
            .slice()
            .sort(sortTopCurrentSetups)
            .slice(0, TOP_CURRENT_SETUPS_LIMIT);
    }

    function applyDecisionsView(options = {}) {
        const query = (briefingSearch && briefingSearch.value || "").toLowerCase().trim();
        const stanceFilter = (document.getElementById("decisions-filter-stance") || {}).value || "all";
        const typeFilter = (document.getElementById("decisions-filter-type") || {}).value || "all";
        const sortMode = (document.getElementById("decisions-sort") || {}).value || "newest";
        const preferDecisionId = options.preferDecisionId || activeDecisionId || null;
        let preferInstrumentId = options.preferInstrumentId
            ? String(options.preferInstrumentId).toUpperCase().replace(/^NSE:|^BSE:/, "")
            : null;

        if (!preferInstrumentId && preferDecisionId) {
            const prior = [...allTraceDecisionsList, ...traceDecisionsList].find(
                d => d && d.metadata && d.metadata.decision_id === preferDecisionId
            );
            if (prior && prior.metadata.instrument_id) {
                preferInstrumentId = String(prior.metadata.instrument_id)
                    .toUpperCase()
                    .replace(/^NSE:|^BSE:/, "");
            }
        }

        let rows = traceDecisionsList.filter(isCurrentDecisionListRow);
        rows = rows.filter(d => {
            if (dismissedDecisionSymbols.has(decisionInstrumentKey(d))) return false;
            const type = (d.metadata && d.metadata.decision_type) || "";
            const sectionType = decisionListSectionType(d);
            const dir = (d.metadata && d.metadata.direction) || "NONE";
            const stance = decisionStance(type, dir).label;
            if (stanceFilter !== "all" && stance !== stanceFilter) return false;
            if (typeFilter !== "all" && sectionType !== typeFilter) return false;
            if (!query) return true;
            const symbol = (d.metadata.instrument_id || "INDEX").toLowerCase();
            const exp = (d.explanation || "").toLowerCase();
            return symbol.includes(query) || type.toLowerCase().includes(query) || exp.includes(query)
                || stance.toLowerCase().includes(query);
        });

        const stanceRank = { BUY: 0, SELL: 1, HOLD: 2, WAIT: 3, PASS: 4 };
        rows.sort((a, b) => {
            const sa = (a.metadata && a.metadata.instrument_id) || "";
            const sb = (b.metadata && b.metadata.instrument_id) || "";
            const ta = new Date((a.metadata && a.metadata.ts) || 0).getTime();
            const tb = new Date((b.metadata && b.metadata.ts) || 0).getTime();
            const scoreA = decisionScoreValue(a);
            const scoreB = decisionScoreValue(b);
            const stanceA = decisionStance(a.metadata.decision_type, a.metadata.direction).label;
            const stanceB = decisionStance(b.metadata.decision_type, b.metadata.direction).label;
            const sectionA = decisionListSectionType(a);
            const sectionB = decisionListSectionType(b);
            switch (sortMode) {
                case "oldest": return ta - tb;
                case "symbol-asc": return sa.localeCompare(sb);
                case "symbol-desc": return sb.localeCompare(sa);
                case "score-desc": return scoreB - scoreA || tb - ta;
                case "score-asc": return scoreA - scoreB || tb - ta;
                case "stance":
                    return (DECISION_TYPE_PRIORITY[sectionA] ?? 9) - (DECISION_TYPE_PRIORITY[sectionB] ?? 9)
                        || (stanceRank[stanceA] ?? 9) - (stanceRank[stanceB] ?? 9)
                        || tb - ta;
                case "newest":
                default:
                    return tb - ta;
            }
        });

        renderDecisionCarousels(rows);
        if (rows.length > 0) {
            let next = null;
            if (preferInstrumentId && options.strictPreferInstrumentId) {
                next = rows.find(d => {
                    const instrument = String(d.metadata && d.metadata.instrument_id || "")
                        .toUpperCase()
                        .replace(/^NSE:|^BSE:/, "");
                    return instrument === preferInstrumentId;
                });
            }
            if (!next && preferDecisionId) {
                next = rows.find(d => d.metadata && d.metadata.decision_id === preferDecisionId);
            }
            if (!next && preferInstrumentId) {
                next = rows.find(d => {
                    const instrument = String(d.metadata && d.metadata.instrument_id || "")
                        .toUpperCase()
                        .replace(/^NSE:|^BSE:/, "");
                    return instrument === preferInstrumentId;
                });
            }
            if (preferInstrumentId && options.strictPreferInstrumentId && !next) {
                renderDecisionBriefEmpty(
                    "No current decision",
                    `${preferInstrumentId} is not available in the current Decisions list.`
                );
                return null;
            }
            // Default selection follows outcome priority (Trade -> Watch ->
            // No trade -> everything else), never plain recency, matching the
            // carousel display order (owner: 2026-07-25, regardless of timestamp).
            const fallback = next || rows.reduce(
                (best, d) => (decisionListPriority(d) < decisionListPriority(best) ? d : best),
                rows[0]
            );
            selectBriefing(fallback.metadata.decision_id);
            return fallback;
        } else if (dagNodesContainer) {
            dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">No decisions match the current filters.</div>';
            renderDecisionBriefEmpty("No visible decision", "Restore dismissed symbols or change the filters.");
        }
        return null;
    }

    function boardSymbolFromInstrument(value) {
        return String(value || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
    }

    function currentVisibleBoardSymbols() {
        if (!decisionsCarouselContainer) return [];
        const containerRect = decisionsCarouselContainer.getBoundingClientRect();
        const symbols = [];
        decisionsCarouselContainer.querySelectorAll(".symbol-row[data-symbol]").forEach(row => {
            if (row.offsetParent === null) return;
            const rowRect = row.getBoundingClientRect();
            const isInViewport = rowRect.bottom > containerRect.top && rowRect.top < containerRect.bottom;
            if (!isInViewport) return;
            const symbol = boardSymbolFromInstrument(row.getAttribute("data-symbol"));
            if (symbol) symbols.push(symbol);
        });
        return [...new Set(symbols)];
    }

    function currentBoardOutcomeCounts() {
        const counts = { trade: 0, watch: 0, noTrade: 0, other: 0 };
        if (!decisionsCarouselContainer) return counts;
        decisionsCarouselContainer.querySelectorAll(".decision-carousel-section").forEach(section => {
            const rows = section.querySelectorAll(".symbol-row[data-symbol]").length;
            const type = String(section.getAttribute("data-section") || "").toUpperCase();
            if (type === "TOP_CURRENT_SETUPS") return;
            if (type === "TRADE") counts.trade += rows;
            else if (type === "WATCH") counts.watch += rows;
            else if (type === "NO_TRADE") counts.noTrade += rows;
            else counts.other += rows;
        });
        return counts;
    }

    function setBoardRevalidateStatus(message, tone = "neutral") {
        if (!decisionsRevalidateStatus) return;
        boardRevalidateStatusTone = tone;
        decisionsRevalidateStatus.hidden = !message;
        decisionsRevalidateStatus.className = `symbols-revalidate-status tone-${tone}`;
        decisionsRevalidateStatus.textContent = message || "";
    }

    function clearBoardRevalidateStatusAfterCooldown() {
        if (!decisionsRevalidateStatus || decisionsRevalidateStatus.hidden) return;
        const text = decisionsRevalidateStatus.textContent || "";
        const cooldownOnly = /cooling down|Retry visible refresh/i.test(text);
        const lowSeverity = boardRevalidateStatusTone === "success"
            || boardRevalidateStatusTone === "info"
            || boardRevalidateStatusTone === "warning";
        if (cooldownOnly && lowSeverity) {
            setBoardRevalidateStatus("", "neutral");
        }
    }

    function readableBoardRevalidateError(error) {
        const detail = error?.data?.detail;
        const title = error?.data?.title;
        if (typeof error?.userMessage === "string" && error.userMessage.trim()) {
            return error.userMessage;
        }
        if (typeof detail === "string" && detail.trim()) return detail;
        if (detail && typeof detail === "object" && typeof detail.title === "string") {
            return detail.title;
        }
        if (typeof title === "string" && title.trim()) return title;
        return "Validation failed. Treat existing rows as stale until you retry.";
    }

    function isKiteRateLimitError(error) {
        const text = [
            error?.userMessage,
            error?.data?.detail,
            error?.data?.title,
        ].map(v => typeof v === "string" ? v : "").join(" ");
        return /kite rate limit|kite HTTP 429|too many requests|NetworkException/i.test(text);
    }

    function formatBoardCooldown(seconds) {
        const safeSeconds = Math.max(1, Math.ceil(Number(seconds) || 0));
        return `${safeSeconds}s`;
    }

    function syncBoardRevalidateCooldownButton() {
        if (!decisionsRevalidateVisibleBtn) return;
        const remainingMs = nextBoardRevalidateAllowedAt - Date.now();
        if (remainingMs <= 0) {
            nextBoardRevalidateAllowedAt = 0;
            decisionsRevalidateVisibleBtn.disabled = false;
            decisionsRevalidateVisibleBtn.innerHTML = BOARD_REVALIDATE_READY_HTML;
            decisionsRevalidateVisibleBtn.title = "Re-validate only the rows currently visible in this list";
            decisionsRevalidateVisibleBtn.setAttribute("aria-label", "Re-validate visible current-board rows");
            if (boardRevalidateCooldownTimer != null) {
                clearInterval(boardRevalidateCooldownTimer);
                boardRevalidateCooldownTimer = null;
            }
            clearBoardRevalidateStatusAfterCooldown();
            return;
        }
        const wait = formatBoardCooldown(remainingMs / 1000);
        decisionsRevalidateVisibleBtn.disabled = true;
        decisionsRevalidateVisibleBtn.innerHTML = '<i class="fa-solid fa-hourglass-half"></i>';
        decisionsRevalidateVisibleBtn.title = `Cooling down · retry in ${wait}`;
        decisionsRevalidateVisibleBtn.setAttribute("aria-label", `Cooling down. Retry visible refresh in ${wait}`);
    }

    function startBoardRevalidateCooldown() {
        nextBoardRevalidateAllowedAt = Date.now() + QUICK_VISIBLE_REVALIDATE_COOLDOWN_MS;
        syncBoardRevalidateCooldownButton();
        if (boardRevalidateCooldownTimer != null) clearInterval(boardRevalidateCooldownTimer);
        boardRevalidateCooldownTimer = setInterval(syncBoardRevalidateCooldownButton, 1000);
    }

    async function revalidateVisibleDecisionBoard() {
        if (!decisionsRevalidateVisibleBtn) return;
        if (typeof validateSymbolsNow !== "function") {
            showToast("Validation controls are not ready yet — reload ATHENA.", "danger");
            setBoardRevalidateStatus("Validation controls are not ready. Reload ATHENA.", "danger");
            return;
        }
        const now = Date.now();
        if (now < nextBoardRevalidateAllowedAt) {
            const waitSeconds = (nextBoardRevalidateAllowedAt - now) / 1000;
            const message = `Kite is cooling down. Retry visible refresh in ${formatBoardCooldown(waitSeconds)}.`;
            showToast(message, "warning");
            setBoardRevalidateStatus(message, "warning");
            return;
        }
        const onScreenSymbols = currentVisibleBoardSymbols();
        if (!onScreenSymbols.length) {
            showToast("No on-screen current-board rows to re-validate", "warning");
            setBoardRevalidateStatus("No on-screen current-board rows to re-validate.", "warning");
            return;
        }
        const symbols = onScreenSymbols.slice(0, QUICK_VISIBLE_REVALIDATE_LIMIT);
        const capped = onScreenSymbols.length > symbols.length;
        const capCopy = capped
            ? ` first ${symbols.length} of ${onScreenSymbols.length} on-screen`
            : ` ${symbols.length} on-screen`;
        setBoardRevalidateStatus(`Re-validating${capCopy} symbol${symbols.length === 1 ? "" : "s"}…`, "info");
        decisionsRevalidateVisibleBtn.disabled = true;
        decisionsRevalidateVisibleBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        try {
            const res = await validateSymbolsNow(symbols, {
                refreshDecisions: true,
            });
            if (!res || !res.data) {
                startBoardRevalidateCooldown();
                setBoardRevalidateStatus("Re-validation did not complete. Current rows were left unchanged.", "warning");
                return;
            }
            const data = res.data || {};
            const counts = currentBoardOutcomeCounts();
            const excluded = Number.isFinite(Number(data.excluded)) ? Number(data.excluded) : 0;
            setBoardRevalidateStatus(
                `Validated${capCopy} · Trade ${counts.trade} · Watch ${counts.watch} · No trade ${counts.noTrade} · Excluded ${excluded} · cooling down 60s`,
                String(data.as_of_mode || "").toLowerCase() === "session_close" ? "warning" : "success"
            );
            startBoardRevalidateCooldown();
        } catch (err) {
            console.error("Visible board re-validation failed", err);
            startBoardRevalidateCooldown();
            setBoardRevalidateStatus(readableBoardRevalidateError(err), isKiteRateLimitError(err) ? "warning" : "danger");
        } finally {
            syncBoardRevalidateCooldownButton();
        }
    }

    // Priority order always — Trade first, then Watch, then No trade, then
    // Insufficient data — regardless of timestamp (owner: 2026-07-25). Any
    // decision_type not in this list still gets its own carousel, appended
    // after these four, so nothing is ever silently hidden.
    // `dot` stays a saturated alert color (fine for an 8px dot). `tint`/
    // `tintBorder` were a full-block background fill per section — the two
    // owner screenshots after that shipped both read as "too much color":
    // first an imbalance between hues, then (once balanced) simply too
    // much colored surface area for 3-4 stacked section dividers in a
    // narrow panel. Switched to a thin left-border accent (`accent`) +ba
    // much quieter wash (`wash`) — the same restrained pattern the
    // Recommendation tile/ATHENA Summary card already use elsewhere —
    // color reads as a scan cue at the edge, not a filled block.
    const DECISION_CAROUSEL_SECTIONS = [
        { type: "TRADE", label: "Trade", dot: "var(--success)", accent: "rgba(34, 197, 94, 0.65)", wash: "rgba(34, 197, 94, 0.05)", hint: "acted on now" },
        { type: "WATCH", label: "Watch", dot: "var(--warning)", accent: "rgba(245, 158, 11, 0.65)", wash: "rgba(245, 158, 11, 0.05)", hint: "borderline, monitor" },
        { type: "NO_TRADE", label: "No trade", dot: "var(--text-muted)", accent: "rgba(148, 163, 184, 0.45)", wash: "rgba(148, 163, 184, 0.04)", hint: "nothing to act on" },
        { type: "INSUFFICIENT_DATA", label: "Insufficient data", dot: "var(--text-muted)", accent: "rgba(148, 163, 184, 0.45)", wash: "rgba(148, 163, 184, 0.04)", hint: "not enough data yet" },
    ];

    // DT-1: was renderDeckCard, building a fixed-width horizontal carousel
    // card. Same data, same fields — just a full-width vertical row now that
    // the carousels are a permanent left-hand list instead of a scroller.
    function renderSymbolRow(d) {
        const rawSym = d.metadata.instrument_id || "INDEX";
        const symbol = rawSym.includes(":") ? rawSym.split(":").pop() : rawSym;
        const dateObj = new Date(d.metadata.ts);
        const dateStr = dateObj.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
        const gates = (d.analysis && d.analysis.gate_results) ? d.analysis.gate_results : [];
        const failed = gates.filter(g => g && g.passed === false);
        const score = decisionScoreValue(d);
        const scoreLabel = score >= 0 ? score.toFixed(1) : "—";
        const planFreshness = inferTradePlanFreshness(d.trade_plan);
        const planStatus = formatTradePlanFreshnessShort(planFreshness);
        const planStatusClass = String(planFreshness.status || "unknown").toLowerCase();
        const planStatusTitle = planFreshness.has_trade_plan
            ? formatTradePlanFreshnessBadge(planFreshness)
            : "No authorized TradePlan for this decision";
        const rawType = String((d.metadata && d.metadata.decision_type) || "").toUpperCase();
        const currentPlanBlocked = decisionHasHistoricalTradePlan(d);
        const noteText = currentPlanBlocked
            ? "plan not current"
            : gates.length === 0
            ? "no gates recorded"
            : (failed.length ? `${failed.length} of ${gates.length} gates open` : "all gates cleared");
        const noteTitle = currentPlanBlocked
            ? "Do not use this historical TradePlan without re-validation"
            : failed.length
            ? `Needs ${failed.map(g => friendlyGateName(g.gate)).join(", ")}`
            : noteText;
        // Quick-glance severity without a hover — many cards otherwise show
        // the same generic "N of M gates open" in identical muted gray.
        const noteTone = currentPlanBlocked
            ? "tone-bad-text"
            : gates.length === 0
            ? ""
            : (failed.length === 0 ? "tone-good-text" : (failed.length <= 2 ? "tone-warn-text" : "tone-bad-text"));

        const row = document.createElement("div");
        row.className = "symbol-row";
        row.setAttribute("data-id", d.metadata.decision_id);
        row.setAttribute("data-symbol", symbol);
        // Keyboard-operable (UX-7 accessibility) — this was a plain click-only
        // div with no way for a keyboard user to reach or activate it.
        row.setAttribute("tabindex", "0");
        row.setAttribute("role", "button");
        row.setAttribute("aria-label", `View ${symbol} decision`);
        row.innerHTML = `
            <div style="flex: 1 1 auto; min-width: 0;">
                <div class="symbol-row-top">
                    <span class="symbol-row-sym" title="${escapeDecisionHtml(rawSym)}">${escapeDecisionHtml(symbol)}</span>
                    <button class="symbol-row-dismiss" type="button"
                        title="Hide ${escapeDecisionHtml(symbol)} from Today's Decisions until tomorrow"
                        aria-label="Dismiss ${escapeDecisionHtml(symbol)} for today">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
                <div class="symbol-row-mid">
                    <span class="symbol-row-score">${escapeDecisionHtml(scoreLabel)}</span>
                    <span class="symbol-row-plan-status tone-${escapeDecisionHtml(planStatusClass)}" title="${escapeDecisionHtml(planStatusTitle)}">${escapeDecisionHtml(planStatus)}</span>
                    <span class="symbol-row-time">${escapeDecisionHtml(dateStr)}</span>
                </div>
                <div class="symbol-row-note ${noteTone}" title="${escapeDecisionHtml(noteTitle)}">${escapeDecisionHtml(noteText)}</div>
            </div>
        `;

        row.addEventListener("click", () => {
            selectBriefing(d.metadata.decision_id);
        });
        row.addEventListener("keydown", event => {
            if (event.target !== row) return; // let the dismiss button handle its own keys
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectBriefing(d.metadata.decision_id);
            }
        });
        row.querySelector(".symbol-row-dismiss")?.addEventListener("click", event => {
            event.stopPropagation();
            dismissDecisionForToday(d);
        });
        return row;
    }

    function renderDecisionCarousels(decisions) {
        if (!decisionsCarouselContainer) return;

        const summaryEl = document.getElementById("decisions-summary-strip");
        if (summaryEl) {
            const dismissedCount = traceDecisionsList.filter(
                d => isCurrentDecisionListRow(d) && dismissedDecisionSymbols.has(decisionInstrumentKey(d))
            ).length;
            const hiddenHistoricalCount = traceDecisionsList.filter(d => !isCurrentDecisionListRow(d)).length;
            const counts = {};
            decisions.forEach(d => {
                const t = decisionListSectionType(d);
                counts[t] = (counts[t] || 0) + 1;
            });
            if (decisions.length === 0) {
                summaryEl.textContent = traceDecisionsList.length
                    ? "No visible decisions — restore dismissed symbols or change filters."
                    : "No decisions yet — run ./athena-daily smoke after Kite auth.";
            } else {
                const tradeCount = counts.TRADE || 0;
                const watchCount = counts.WATCH || 0;
                const passCount = counts.NO_TRADE || 0;
                const otherCount = decisions.length - tradeCount - watchCount - passCount;
                const details = [
                    "Current board only.",
                    "expired historical TradePlans are hidden from this list.",
                    "HOLD = interesting but blocked.",
                    "PASS = below watch score.",
                ];
                if (hiddenHistoricalCount > 0) {
                    details.push(`${hiddenHistoricalCount} historical expired plan${
                        hiddenHistoricalCount === 1 ? "" : "s"
                    } hidden.`);
                }
                summaryEl.setAttribute("title", details.join(" "));
                summaryEl.innerHTML =
                    `<strong>${decisions.length}</strong> current · ` +
                    `Trade ${tradeCount} · Watch ${watchCount} · No trade ${passCount}` +
                    (otherCount > 0 ? ` · Other ${otherCount}` : "") +
                    ` <span class="symbols-summary-help" aria-hidden="true"><i class="fa-solid fa-circle-info"></i></span>`;
                if (hiddenHistoricalCount > 0) {
                    summaryEl.innerHTML +=
                        ` <span class="text-muted">· ${hiddenHistoricalCount} archived</span>`;
                }
            }
            if (dismissedCount > 0) {
                summaryEl.innerHTML +=
                    ` · <strong>${dismissedCount}</strong> hidden today ` +
                    `<button id="restore-dismissed-decisions" class="restore-dismissed-btn" type="button">Restore</button>`;
                document.getElementById("restore-dismissed-decisions")
                    ?.addEventListener("click", restoreDismissedDecisions);
            }
        }

        // DT-1: preserve the left panel's scroll position across a rebuild
        // (e.g. typing in search re-renders the list on every keystroke) —
        // only the newly *selected* row should ever move the viewport
        // (via scrollIntoView below), never a re-render on its own.
        const previousScrollTop = decisionsCarouselContainer.scrollTop;
        decisionsCarouselContainer.innerHTML = "";

        if (decisions.length === 0) {
            decisionsCarouselContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">No decisions match query.</div>';
            return;
        }

        const topRows = topCurrentSetups(decisions);
        if (topRows.length > 0) {
            const topSection = document.createElement("div");
            topSection.className = "decision-carousel-section top-current-setups-section";
            topSection.setAttribute("data-section", "TOP_CURRENT_SETUPS");
            topSection.innerHTML = `
                <div class="decision-carousel-head top-current-setups-head" data-toggle>
                    <i class="fa-solid fa-ranking-star top-current-setups-icon"></i>
                    <span class="decision-carousel-name">Top Current Setups</span>
                    <span class="decision-carousel-count">${topRows.length}</span>
                    <span class="decision-carousel-hint">ranked review queue</span>
                    <i class="fa-solid fa-chevron-down decision-carousel-chevron"></i>
                </div>
                <div class="top-current-setups-note">
                    Current valid/aging TradePlans only. Confirm live price and plan status before action.
                </div>
                <div class="decision-carousel-body"></div>
            `;
            const topBody = topSection.querySelector(".decision-carousel-body");
            topRows.forEach(d => topBody.appendChild(renderSymbolRow(d)));
            topSection.querySelector("[data-toggle]").addEventListener("click", () => {
                topSection.classList.toggle("collapsed");
            });
            decisionsCarouselContainer.appendChild(topSection);
        }

        const byType = new Map();
        decisions.forEach(d => {
            const t = decisionListSectionType(d);
            if (!byType.has(t)) byType.set(t, []);
            byType.get(t).push(d);
        });

        const knownTypes = new Set(DECISION_CAROUSEL_SECTIONS.map(s => s.type));
        const extraTypes = Array.from(byType.keys()).filter(t => !knownTypes.has(t));
        const sections = [
            ...DECISION_CAROUSEL_SECTIONS,
            ...extraTypes.map(t => ({
                type: t, label: friendlyLabel(t), dot: "var(--text-muted)",
                accent: "rgba(148, 163, 184, 0.45)", wash: "rgba(148, 163, 184, 0.04)", hint: "",
            })),
        ];

        sections.forEach(section => {
            const rows = byType.get(section.type) || [];
            if (!rows.length) return;

            const sectionEl = document.createElement("div");
            sectionEl.className = "decision-carousel-section";
            sectionEl.setAttribute("data-section", section.type);
            sectionEl.innerHTML = `
                <div class="decision-carousel-head" data-toggle style="background: linear-gradient(${section.wash}, ${section.wash}), rgba(15, 23, 42, 0.92); border-left-color: ${section.accent}">
                    <span class="decision-carousel-dot" style="background: ${section.dot}"></span>
                    <span class="decision-carousel-name">${escapeDecisionHtml(section.label)}</span>
                    <span class="decision-carousel-count">${rows.length}</span>
                    ${section.hint ? `<span class="decision-carousel-hint">${escapeDecisionHtml(section.hint)}</span>` : ""}
                    <i class="fa-solid fa-chevron-down decision-carousel-chevron"></i>
                </div>
                <div class="decision-carousel-body"></div>
            `;

            const body = sectionEl.querySelector(".decision-carousel-body");
            rows.forEach(d => body.appendChild(renderSymbolRow(d)));

            sectionEl.querySelector("[data-toggle]").addEventListener("click", () => {
                sectionEl.classList.toggle("collapsed");
            });

            decisionsCarouselContainer.appendChild(sectionEl);
        });

        decisionsCarouselContainer.scrollTop = previousScrollTop;
        updateDecisionListScrollTopButton();
    }

    // Search / filter / sort for Today's Decisions
    const wireDecisionsControls = () => {
        ["decisions-filter-stance", "decisions-filter-type", "decisions-sort"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener("change", applyDecisionsView);
        });
        if (briefingSearch) {
            briefingSearch.addEventListener("input", () => {
                updateBriefingSearchClear();
                applyDecisionsView();
            });
            updateBriefingSearchClear();
        }
        briefingSearchClear?.addEventListener("click", clearBriefingSearch);
    };
    wireDecisionsControls();

    decisionsRevalidateVisibleBtn?.addEventListener("click", revalidateVisibleDecisionBoard);
    decisionsCarouselContainer?.addEventListener("scroll", updateDecisionListScrollTopButton, { passive: true });
    decisionsScrollTopBtn?.addEventListener("click", scrollDecisionListToTop);

    // DT-1: stance/type/sort moved off the toolbar (removed, per the
    // workstation redesign) into a small popover behind an icon button, so
    // they never consume vertical space above the detail panel. Same
    // <select> elements, same change listeners above — only their
    // visibility is new. "Clear all" moved to its own separate icon button
    // (fix pass, owner screenshot) — it's a destructive data action, not a
    // view filter, so it no longer lives inside this popover at all.
    const symbolsFilterToggle = document.getElementById("symbols-filter-toggle");
    const symbolsFilterPopover = document.getElementById("symbols-filter-popover");
    const symbolsFilterReset = document.getElementById("symbols-filter-reset");
    const symbolsFilterClose = document.getElementById("symbols-filter-close");
    // Fix pass (owner screenshot): with no backdrop, the symbol list stayed
    // fully visible and clickable underneath the open popover — no visual
    // differentiation, and rows were still interactive. Shown/hidden in
    // lockstep with the popover itself.
    const symbolsFilterBackdrop = document.getElementById("symbols-filter-backdrop");

    function closeSymbolsFilterPopover() {
        if (!symbolsFilterPopover || symbolsFilterPopover.hidden) return;
        symbolsFilterPopover.hidden = true;
        if (symbolsFilterBackdrop) symbolsFilterBackdrop.hidden = true;
        symbolsFilterToggle?.setAttribute("aria-expanded", "false");
    }

    symbolsFilterToggle?.addEventListener("click", event => {
        event.stopPropagation();
        const willOpen = symbolsFilterPopover.hidden;
        symbolsFilterPopover.hidden = !willOpen;
        if (symbolsFilterBackdrop) symbolsFilterBackdrop.hidden = !willOpen;
        symbolsFilterToggle.setAttribute("aria-expanded", String(willOpen));
    });
    // Fix pass (owner screenshot): the filter icon toggling open/closed was
    // the *only* way to hide the popover again — "clueless for the user".
    // Click-outside and Escape already worked; this adds an explicit,
    // visible close button inside the popover itself.
    symbolsFilterClose?.addEventListener("click", event => {
        event.stopPropagation();
        closeSymbolsFilterPopover();
    });
    document.addEventListener("click", event => {
        if (!symbolsFilterPopover || symbolsFilterPopover.hidden) return;
        if (symbolsFilterPopover.contains(event.target) || event.target === symbolsFilterToggle) return;
        closeSymbolsFilterPopover();
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeSymbolsFilterPopover();
    });

    // Fix pass (owner screenshot): resets the view (stance/type/sort back to
    // defaults) — distinct from "Clear all", which deletes decision data.
    // Also dismisses the popover afterward (owner feedback) — resetting is a
    // completed action, not a mid-adjustment the user needs the panel open
    // for.
    symbolsFilterReset?.addEventListener("click", () => {
        const stanceEl = document.getElementById("decisions-filter-stance");
        const typeEl = document.getElementById("decisions-filter-type");
        const sortEl = document.getElementById("decisions-sort");
        if (stanceEl) stanceEl.value = "all";
        if (typeEl) typeEl.value = "all";
        if (sortEl) sortEl.value = "newest";
        applyDecisionsView();
        closeSymbolsFilterPopover();
    });

    // "Clear all" (owner-requested) — CONFIRM-gated wipe of the Decisions &
    // Trace domain via POST /decisions/reset, mirroring the existing
    // Portfolio "Reset fills" gate exactly (type CONFIRM to unlock, backup
    // created automatically server-side before anything is deleted).
    const decisionsClearAllConfirm = document.getElementById("decisions-clear-all-confirm");
    const decisionsClearAllGateStatus = document.getElementById("decisions-clear-all-gate-status");
    const decisionsClearAllSubmit = document.getElementById("decisions-clear-all-submit");
    function syncDecisionsClearAllGate() {
        const unlocked = decisionsClearAllConfirm && decisionsClearAllConfirm.value === "CONFIRM";
        if (decisionsClearAllGateStatus) {
            decisionsClearAllGateStatus.textContent = unlocked
                ? "Unlocked — Delete everything is now enabled."
                : "Locked until CONFIRM matches exactly.";
            decisionsClearAllGateStatus.className = `ops-restore-gate-status ${unlocked ? "unlocked" : "locked"}`;
        }
        if (decisionsClearAllSubmit) decisionsClearAllSubmit.disabled = !unlocked;
    }
    decisionsClearAllConfirm?.addEventListener("input", syncDecisionsClearAllGate);

    const decisionsClearAllModal = document.getElementById("decisions-clear-all-modal");
    document.getElementById("decisions-clear-all-btn")?.addEventListener("click", () => {
        if (decisionsClearAllConfirm) decisionsClearAllConfirm.value = "";
        syncDecisionsClearAllGate();
        openModal(decisionsClearAllModal);
    });
    document.getElementById("decisions-clear-all-close")?.addEventListener("click", () => {
        closeModal(decisionsClearAllModal);
    });
    window.addEventListener("click", event => {
        if (event.target === decisionsClearAllModal) closeModal(decisionsClearAllModal);
    });
    decisionsClearAllSubmit?.addEventListener("click", async () => {
        if (!decisionsClearAllConfirm || decisionsClearAllConfirm.value !== "CONFIRM") return;
        decisionsClearAllSubmit.disabled = true;
        decisionsClearAllSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Deleting…';
        try {
            const res = await apiRequest("/api/v1/decisions/reset", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ confirmation: "CONFIRM" }),
            });
            const n = res && res.data ? res.data.total_deleted : 0;
            showToast(`Cleared ${n} record(s) from Decisions & Trace`, "success");
            closeModal(decisionsClearAllModal);
            activeDecisionId = null;
            activeDecisionData = null;
            if (decisionBriefBody) renderDecisionBriefEmpty("Select a decision", "ATHENA will show the current thesis, safety gates, and advisory TradePlan.");
            if (dagNodesContainer) {
                dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">Select a decision briefing document to view its reasoning trace.</div>';
            }
            await loadDecisionsWorkspace();
        } catch (err) {
            console.error(err);
            showToast("Clear all failed", "danger");
        } finally {
            decisionsClearAllConfirm.value = "";
            syncDecisionsClearAllGate();
            decisionsClearAllSubmit.innerHTML = '<i class="fa-solid fa-trash-can"></i> Delete everything';
        }
    });
