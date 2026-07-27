

    // "Compare" quick action (UX-9, symbol vs. symbol) — fetches the entered
    // symbol's own latest decision + depth via the existing decisions list
    // (instrument_id filter, already supported) and depth endpoints, exactly
    // like the current decision's own data was loaded. No new backend, and
    // the same real analysisPresentation/decisionStance helpers render both
    // sides identically — never a second, different code path for "the other
    // symbol."
    async function fetchLatestDecisionForSymbol(symbol) {
        // instrument_id is stored with an exchange prefix (e.g. "NSE:HFCL")
        // and the backend filter is an exact, case-sensitive match — a bare
        // or lower/mixed-case symbol typed by the trader (the input's
        // uppercase display is CSS text-transform only; the underlying
        // .value keeps whatever case was actually typed) would silently
        // match nothing. Same candidate-id probe already used by
        // loadDecisionChart, so typing "hfcl" or "HFCL" both find NSE:HFCL
        // instead of always reporting "no decision found."
        const upper = String(symbol).toUpperCase();
        const candidates = upper.includes(":")
            ? [upper]
            : [`NSE:${upper}`, upper];
        let rows = [];
        for (const candidateId of candidates) {
            const qs = new URLSearchParams({
                instrument_id: candidateId,
                sort_by: "ts",
                sort_dir: "desc",
                page: "1",
                page_size: "1",
            });
            const listRes = await apiRequest(`/api/v1/decisions?${qs.toString()}`, { skipToast: true });
            rows = (listRes && Array.isArray(listRes.data)) ? listRes.data : [];
            if (rows.length) break;
        }
        if (!rows.length) return null;
        const decision = rows[0];
        const decisionId = decision.metadata && decision.metadata.decision_id;
        let depth = null;
        if (decisionId) {
            const depthRes = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/depth`,
                { skipToast: true }
            );
            depth = depthRes && depthRes.data;
        }
        return { decision, depth };
    }

    function compareMetricRow(labelText, tone, depth) {
        const block = depth && depth[tone];
        if (!block || block.status !== "OK") {
            return `<div class="compare-metric"><span>${escapeDecisionHtml(labelText)}</span><strong>—</strong></div>`;
        }
        const view = analysisPresentation(labelText, block, tone);
        const value = view.displayBand || view.valueLabel;
        return `<div class="compare-metric"><span>${escapeDecisionHtml(labelText)}</span><strong>${escapeDecisionHtml(value)}</strong></div>`;
    }

    function compareColumn(symbol, decision, depth) {
        if (!decision) {
            return `<div class="compare-column">
                <h5>${escapeDecisionHtml(symbol)}</h5>
                <p class="context-caption">No decision found for this symbol.</p>
            </div>`;
        }
        const meta = decision.metadata || {};
        const stance = decisionStance(meta.decision_type, meta.direction);
        const rr = decision.trade_plan ? Number(decision.trade_plan.risk_reward) : NaN;
        return `<div class="compare-column">
            <h5>${escapeDecisionHtml(symbol)}</h5>
            <span class="stance-chip ${stance.cls}">${escapeDecisionHtml(stance.label)}</span>
            <span class="text-muted">${escapeDecisionHtml(formatDecisionTime(meta.ts))}</span>
            ${compareMetricRow("Score", "score", depth)}
            ${compareMetricRow("Confidence", "confidence", depth)}
            ${compareMetricRow("Risk", "risk", depth)}
            <div class="compare-metric"><span>Risk : Reward</span><strong>${Number.isFinite(rr) ? `${rr.toFixed(1)} : 1` : "—"}</strong></div>
        </div>`;
    }

    async function runSymbolCompare(symbol) {
        const resultHost = document.getElementById("compare-result");
        if (!resultHost) return;
        resultHost.innerHTML = '<div class="decision-depth-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> Comparing…</div>';
        const currentMeta = activeDecisionData && activeDecisionData.metadata;
        const currentSymbol = currentMeta ? String(currentMeta.instrument_id || "").split(":").pop() : "Current";
        try {
            const other = await fetchLatestDecisionForSymbol(symbol);
            resultHost.innerHTML = `<div class="compare-grid">
                ${compareColumn(currentSymbol, activeDecisionData, activeDepth)}
                ${compareColumn(symbol.toUpperCase(), other && other.decision, other && other.depth)}
            </div>`;
        } catch (err) {
            console.error(`Failed to compare against ${symbol}`, err);
            resultHost.innerHTML = '<div class="context-caption">Unable to fetch that symbol\'s decision right now.</div>';
        }
    }

    function openCompareModal() {
        const modal = document.getElementById("compare-modal");
        const input = document.getElementById("compare-symbol-input");
        const resultHost = document.getElementById("compare-result");
        if (!modal) return;
        if (input) input.value = "";
        if (resultHost) resultHost.innerHTML = '<p class="context-caption">Enter a symbol above to compare it against the current decision.</p>';
        openModal(modal);
        if (input) input.focus();
    }

    const compareModalEl = document.getElementById("compare-modal");
    document.getElementById("compare-modal-close")?.addEventListener("click", () => closeModal(compareModalEl));
    window.addEventListener("click", event => {
        if (event.target === compareModalEl) closeModal(compareModalEl);
    });
    const compareSubmitBtn = document.getElementById("compare-symbol-submit");
    const compareInputEl = document.getElementById("compare-symbol-input");
    const submitCompare = () => {
        const raw = (compareInputEl && compareInputEl.value || "").trim();
        if (raw) runSymbolCompare(raw);
    };
    compareSubmitBtn?.addEventListener("click", submitCompare);
    compareInputEl?.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            submitCompare();
        }
    });