

    // ---------------------------------------------------------------------------
    // Decisions & Trace DAG Handlers
    // ---------------------------------------------------------------------------
    const decisionsCarouselContainer = document.getElementById("decisions-carousel-groups");
    const briefingSearch = document.getElementById("briefing-search");

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
            applyDecisionsView(options);
        } catch (err) {
            console.error("Failed to load decisions", err);
            if (decisionsCarouselContainer) {
                decisionsCarouselContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">Failed to load decisions. Use refresh to retry.</div>';
            }
            if (dagNodesContainer) {
                dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">Decision trace unavailable until briefings load.</div>';
            }
            showToast("Failed to load decisions workspace", "danger");
        }
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

        let rows = [...traceDecisionsList];
        rows = rows.filter(d => {
            if (dismissedDecisionSymbols.has(decisionInstrumentKey(d))) return false;
            const type = (d.metadata && d.metadata.decision_type) || "";
            const dir = (d.metadata && d.metadata.direction) || "NONE";
            const stance = decisionStance(type, dir).label;
            if (stanceFilter !== "all" && stance !== stanceFilter) return false;
            if (typeFilter !== "all" && String(type).toUpperCase() !== typeFilter) return false;
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
            switch (sortMode) {
                case "oldest": return ta - tb;
                case "symbol-asc": return sa.localeCompare(sb);
                case "symbol-desc": return sb.localeCompare(sa);
                case "score-desc": return scoreB - scoreA || tb - ta;
                case "score-asc": return scoreA - scoreB || tb - ta;
                case "stance":
                    return (stanceRank[stanceA] ?? 9) - (stanceRank[stanceB] ?? 9) || tb - ta;
                case "newest":
                default:
                    return tb - ta;
            }
        });

        renderDecisionCarousels(rows);
        if (rows.length > 0) {
            let next = preferDecisionId
                ? rows.find(d => d.metadata && d.metadata.decision_id === preferDecisionId)
                : null;
            if (!next && preferInstrumentId) {
                next = rows.find(d => {
                    const instrument = String(d.metadata && d.metadata.instrument_id || "")
                        .toUpperCase()
                        .replace(/^NSE:|^BSE:/, "");
                    return instrument === preferInstrumentId;
                });
            }
            // Default selection follows outcome priority (Trade -> Watch ->
            // No trade -> everything else), never plain recency, matching the
            // carousel display order (owner: 2026-07-25, regardless of timestamp).
            const fallback = next || rows.reduce(
                (best, d) => (decisionTypePriority(d) < decisionTypePriority(best) ? d : best),
                rows[0]
            );
            selectBriefing(fallback.metadata.decision_id);
        } else if (dagNodesContainer) {
            dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">No decisions match the current filters.</div>';
            renderDecisionBriefEmpty("No visible decision", "Restore dismissed symbols or change the filters.");
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
        const noteText = gates.length === 0
            ? "no gates recorded"
            : (failed.length ? `${failed.length} of ${gates.length} gates open` : "all gates cleared");
        const noteTitle = failed.length
            ? `Needs ${failed.map(g => friendlyGateName(g.gate)).join(", ")}`
            : noteText;
        // Quick-glance severity without a hover — many cards otherwise show
        // the same generic "N of M gates open" in identical muted gray.
        const noteTone = gates.length === 0
            ? ""
            : (failed.length === 0 ? "tone-good-text" : (failed.length <= 2 ? "tone-warn-text" : "tone-bad-text"));
        const planFreshness = inferTradePlanFreshness(d.trade_plan);
        const planStatus = formatTradePlanFreshnessShort(planFreshness);
        const planStatusClass = String(planFreshness.status || "unknown").toLowerCase();
        const planStatusTitle = planFreshness.has_trade_plan
            ? formatTradePlanFreshnessBadge(planFreshness)
            : "No authorized TradePlan for this decision";

        const row = document.createElement("div");
        row.className = "symbol-row";
        row.setAttribute("data-id", d.metadata.decision_id);
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
                d => dismissedDecisionSymbols.has(decisionInstrumentKey(d))
            ).length;
            const counts = {};
            decisions.forEach(d => {
                const t = (d.metadata && d.metadata.decision_type) || "OTHER";
                counts[t] = (counts[t] || 0) + 1;
            });
            if (decisions.length === 0) {
                summaryEl.textContent = traceDecisionsList.length
                    ? "No visible decisions — restore dismissed symbols or change filters."
                    : "No decisions yet — run ./athena-daily smoke after Kite auth.";
            } else {
                summaryEl.innerHTML =
                    `<strong>${decisions.length}</strong> symbols (latest each) · ` +
                    `BUY/SELL ${counts.TRADE || 0} · HOLD ${counts.WATCH || 0} · ` +
                    `PASS ${counts.NO_TRADE || 0} · other ${
                        decisions.length - (counts.TRADE || 0) - (counts.WATCH || 0) - (counts.NO_TRADE || 0)
                    }. ` +
                    `<span class="text-muted">HOLD = interesting but blocked; PASS = below watch score. Grouped by outcome below — Trade first, always.</span>`;
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

        const byType = new Map();
        decisions.forEach(d => {
            const t = String((d.metadata && d.metadata.decision_type) || "OTHER").toUpperCase();
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
    }

    // Search / filter / sort for Today's Decisions
    const wireDecisionsControls = () => {
        ["decisions-filter-stance", "decisions-filter-type", "decisions-sort"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener("change", applyDecisionsView);
        });
        if (briefingSearch) {
            briefingSearch.addEventListener("input", applyDecisionsView);
        }
    };
    wireDecisionsControls();

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
