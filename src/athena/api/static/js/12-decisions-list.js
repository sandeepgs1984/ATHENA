

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
    const DECISION_CAROUSEL_SECTIONS = [
        { type: "TRADE", label: "Trade", dot: "var(--success)", hint: "acted on now" },
        { type: "WATCH", label: "Watch", dot: "var(--warning)", hint: "borderline, monitor" },
        { type: "NO_TRADE", label: "No trade", dot: "var(--text-muted)", hint: "nothing to act on" },
        { type: "INSUFFICIENT_DATA", label: "Insufficient data", dot: "var(--text-muted)", hint: "not enough data yet" },
    ];

    function decisionCardStanceColor(type) {
        const t = String(type || "").toUpperCase();
        if (t === "TRADE") return "var(--success)";
        if (t === "WATCH") return "var(--warning)";
        return "var(--text-muted)";
    }

    function renderDeckCard(d) {
        const rawSym = d.metadata.instrument_id || "INDEX";
        const symbol = rawSym.includes(":") ? rawSym.split(":").pop() : rawSym;
        const type = d.metadata.decision_type;
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

        const card = document.createElement("div");
        card.className = "deck-card";
        card.style.setProperty("--stance-color", decisionCardStanceColor(type));
        card.setAttribute("data-id", d.metadata.decision_id);
        // Keyboard-operable (UX-7 accessibility) — this was a plain click-only
        // div with no way for a keyboard user to reach or activate it.
        card.setAttribute("tabindex", "0");
        card.setAttribute("role", "button");
        card.setAttribute("aria-label", `View ${symbol} decision`);
        card.innerHTML = `
            <div class="deck-top">
                <span class="deck-sym" title="${escapeDecisionHtml(rawSym)}">${escapeDecisionHtml(symbol)}</span>
                <button class="deck-dismiss-btn" type="button"
                    title="Hide ${escapeDecisionHtml(symbol)} from Today's Decisions until tomorrow"
                    aria-label="Dismiss ${escapeDecisionHtml(symbol)} for today">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="deck-mid">
                <span class="deck-score">${escapeDecisionHtml(scoreLabel)}</span>
                <span class="deck-time">${escapeDecisionHtml(dateStr)}</span>
            </div>
            <div class="deck-note ${noteTone}" title="${escapeDecisionHtml(noteTitle)}">${escapeDecisionHtml(noteText)}</div>
        `;

        card.addEventListener("click", () => {
            selectBriefing(d.metadata.decision_id);
        });
        card.addEventListener("keydown", event => {
            if (event.target !== card) return; // let the dismiss button handle its own keys
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectBriefing(d.metadata.decision_id);
            }
        });
        card.querySelector(".deck-dismiss-btn")?.addEventListener("click", event => {
            event.stopPropagation();
            dismissDecisionForToday(d);
        });
        return card;
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
            ...extraTypes.map(t => ({ type: t, label: friendlyLabel(t), dot: "var(--text-muted)", hint: "" })),
        ];

        sections.forEach(section => {
            const rows = byType.get(section.type) || [];
            if (!rows.length) return;

            const sectionEl = document.createElement("div");
            sectionEl.className = "decision-carousel-section";
            sectionEl.setAttribute("data-section", section.type);
            sectionEl.innerHTML = `
                <div class="decision-carousel-head" data-toggle>
                    <span class="decision-carousel-dot" style="background: ${section.dot}"></span>
                    <span class="decision-carousel-name">${escapeDecisionHtml(section.label)}</span>
                    <span class="decision-carousel-count">${rows.length}</span>
                    ${section.hint ? `<span class="decision-carousel-hint">${escapeDecisionHtml(section.hint)}</span>` : ""}
                    <i class="fa-solid fa-chevron-down decision-carousel-chevron"></i>
                </div>
                <div class="decision-carousel-body">
                    <button class="decision-carousel-nav prev" type="button" aria-label="Scroll ${escapeDecisionHtml(section.label)} left">
                        <i class="fa-solid fa-chevron-left"></i>
                    </button>
                    <div class="decision-carousel-track"></div>
                    <button class="decision-carousel-nav next" type="button" aria-label="Scroll ${escapeDecisionHtml(section.label)} right">
                        <i class="fa-solid fa-chevron-right"></i>
                    </button>
                </div>
            `;

            const track = sectionEl.querySelector(".decision-carousel-track");
            const body = sectionEl.querySelector(".decision-carousel-body");
            rows.forEach(d => track.appendChild(renderDeckCard(d)));

            sectionEl.querySelector("[data-toggle]").addEventListener("click", () => {
                sectionEl.classList.toggle("collapsed");
            });
            sectionEl.querySelectorAll(".decision-carousel-nav").forEach(btn => {
                const dir = btn.classList.contains("prev") ? -1 : 1;
                btn.addEventListener("click", event => {
                    event.stopPropagation();
                    track.scrollBy({ left: dir * 340, behavior: "smooth" });
                });
            });

            decisionsCarouselContainer.appendChild(sectionEl);
            wireCarouselOverflow(body, track);
        });
    }

    // Nav arrows and edge fades only show when a row actually overflows, and
    // each arrow disables at its own end — no dead-end clicks, no "scroll
    // hint" shown when there's nothing to scroll (owner-reported).
    function wireCarouselOverflow(body, track) {
        const updateEdges = () => {
            const overflowing = track.scrollWidth > track.clientWidth + 1;
            body.classList.toggle("scrollable", overflowing);
            if (!overflowing) return;
            body.classList.toggle("at-start", track.scrollLeft <= 1);
            body.classList.toggle(
                "at-end", track.scrollLeft >= track.scrollWidth - track.clientWidth - 1
            );
        };
        track.addEventListener("scroll", updateEdges, { passive: true });
        new ResizeObserver(updateEdges).observe(track);
        updateEdges();
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