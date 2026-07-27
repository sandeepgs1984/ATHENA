
    const dagQuickSummary = document.getElementById("dag-quick-summary");
    const decisionBriefTitle = document.getElementById("decision-brief-title");
    const decisionBriefStanceChip = document.getElementById("decision-brief-stance-chip");
    const decisionBriefTypeChip = document.getElementById("decision-brief-type-chip");
    const decisionBriefAsOf = document.getElementById("decision-brief-asof");
    const decisionBriefBody = document.getElementById("decision-brief-body");
    const decisionBriefGauges = document.getElementById("decision-brief-gauges");
    const decisionBriefTabstrip = document.getElementById("decision-brief-tabstrip");
    const decisionBriefActionbar = document.getElementById("decision-brief-actionbar");
    const decisionBriefRevalidateHeader = document.getElementById("decision-brief-revalidate-header");

    function renderDecisionBriefEmpty(title, detail) {
        if (decisionBriefTitle) {
            decisionBriefTitle.textContent = "Select a symbol";
            decisionBriefTitle.title = "";
        }
        if (decisionBriefAsOf) decisionBriefAsOf.textContent = "Select a symbol";
        if (decisionBriefStanceChip) decisionBriefStanceChip.innerHTML = "";
        if (decisionBriefTypeChip) decisionBriefTypeChip.innerHTML = "";
        if (decisionBriefGauges) decisionBriefGauges.hidden = true;
        if (decisionBriefTabstrip) decisionBriefTabstrip.hidden = true;
        if (decisionBriefActionbar) decisionBriefActionbar.hidden = true;
        resetCockpitGauges();
        setHeaderRevalidateEnabled(false);
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

    // Sticky quick-glance strip pinned to the top of the Reasoning Trace
    // panel (owner UX audit — "sidebar summary") so symbol/stance/score/
    // confidence/risk stay visible while scrolling through DAG detail,
    // without duplicating the full Hero cockpit. Reuses activeDecisionData/
    // activeDepth already loaded for the brief — no separate fetch, and
    // shows "—" for a metric until its real value has loaded.
    function renderSidebarQuickSummary() {
        if (!dagQuickSummary) return;
        const decision = activeDecisionData;
        if (!decision || !decision.metadata) {
            dagQuickSummary.style.display = "none";
            dagQuickSummary.innerHTML = "";
            return;
        }
        const meta = decision.metadata;
        const symbol = String(meta.instrument_id || "").split(":").pop() || "—";
        const stance = decisionStance(meta.decision_type, meta.direction);
        const depth = activeDepth;
        const metricChip = (tone) => {
            const block = depth && depth[tone];
            if (!block || block.status !== "OK") {
                return `<span class="dag-quick-metric"><span>${escapeDecisionHtml(tone)}</span><strong>—</strong></span>`;
            }
            const view = analysisPresentation(friendlyAnalysisName(tone), block, tone);
            return `<span class="dag-quick-metric"><span>${escapeDecisionHtml(tone)}</span><strong>${escapeDecisionHtml(view.displayBand || view.valueLabel)}</strong></span>`;
        };
        dagQuickSummary.style.display = "flex";
        dagQuickSummary.innerHTML = `
            <span class="dag-quick-symbol">${escapeDecisionHtml(symbol)}</span>
            <span class="stance-chip ${stance.cls}">${escapeDecisionHtml(stance.label)}</span>
            ${metricChip("score")}
            ${metricChip("confidence")}
            ${metricChip("risk")}
        `;
    }

    function renderDecisionBrief(decision) {
        if (!decisionBriefBody || !decision || !decision.metadata) return;
        activeDecisionData = decision;
        renderSidebarQuickSummary();
        const meta = decision.metadata;
        const rawSymbol = meta.instrument_id || "INDEX";
        const symbol = rawSymbol.includes(":") ? rawSymbol.split(":").pop() : rawSymbol;
        const stance = decisionStance(meta.decision_type, meta.direction);
        const gates = decision.analysis && Array.isArray(decision.analysis.gate_results)
            ? decision.analysis.gate_results
            : [];
        const summary = formatDecisionSummary(decision.explanation, meta.decision_type, gates);

        if (decisionBriefTitle) {
            decisionBriefTitle.textContent = symbol;
            decisionBriefTitle.title = rawSymbol;
        }
        if (decisionBriefAsOf) decisionBriefAsOf.textContent = `As of ${formatDecisionTime(meta.ts)}`;
        if (decisionBriefStanceChip) {
            decisionBriefStanceChip.innerHTML = `<span class="stance-chip ${stance.cls}">${stance.label}</span>`;
        }
        if (decisionBriefTypeChip) {
            decisionBriefTypeChip.innerHTML = decisionTypeBadge(meta.decision_type);
        }
        if (decisionBriefGauges) decisionBriefGauges.hidden = false;
        if (decisionBriefTabstrip) decisionBriefTabstrip.hidden = false;
        if (decisionBriefActionbar) decisionBriefActionbar.hidden = false;
        resetCockpitGauges();
        resetActionButtons();

        const heroRR = document.getElementById("hero-rr-value");
        if (heroRR) {
            const rr = decision.trade_plan ? Number(decision.trade_plan.risk_reward) : NaN;
            heroRR.textContent = Number.isFinite(rr) ? `${rr.toFixed(1)} : 1` : "—";
        }

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
            <section class="decision-brief-hero">
                <div class="decision-banner ${stance.cls}">
                    <div class="decision-banner-head">
                        <span class="decision-banner-label">ATHENA Recommendation</span>
                        <span class="decision-banner-stance">${stance.label}</span>
                    </div>
                    <p class="decision-banner-reason" title="${escapeDecisionHtml(summary.headline)}">${escapeDecisionHtml(summary.headline)}</p>
                </div>
                <div id="decision-executive-summary" class="executive-summary">
                    <div class="decision-depth-loading">
                        <i class="fa-solid fa-circle-notch fa-spin"></i> Building summary…
                    </div>
                </div>
                <div class="decision-brief-section decision-timeline-section">
                    <div class="decision-brief-section-header">
                        <h4>Decision timeline</h4>
                        <span class="decision-timeline-hint">Click an entry to view ATHENA's assessment at that point in time</span>
                    </div>
                    <div id="decision-history-timeline" class="decision-history-timeline"></div>
                </div>
            </section>

            <div class="tabpane${paneActive("setup")}" id="brief-pane-setup" data-brief-pane="setup">
                <section class="decision-brief-section">
                    <h4>Universe eligibility</h4>
                    <div id="decision-eligibility-depth" class="decision-depth-loading">
                        <i class="fa-solid fa-circle-notch fa-spin"></i> Loading persisted assessment…
                    </div>
                </section>

                ${renderTradePlan(decision.trade_plan, meta.decision_type, meta.direction)}

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
                        <h4>Intraday price context · 5 minute</h4>
                        <span id="decision-chart-status" class="chart-freshness-badge no_data">LOADING</span>
                    </div>
                    <p id="decision-chart-meta" class="decision-chart-meta">Loading persisted OHLCV…</p>
                    <div id="decision-chart-warning" class="decision-chart-warning" hidden></div>
                    <div id="decision-chart-canvas" class="decision-chart-canvas"></div>
                    <div class="decision-chart-legend">
                        <span><i class="legend-box entry"></i> Entry zone</span>
                        <span><i class="legend-line stop"></i> Invalidation</span>
                        <span><i class="legend-line target"></i> Targets</span>
                        <span><i class="legend-line ma"></i> Moving average</span>
                        <span><i class="legend-box atr"></i> ATR band</span>
                        <span><i class="legend-box volume"></i> Volume</span>
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
        // Toggle active card class across every outcome carousel, and bring the
        // selected card into view within its own track (graceful selection).
        if (decisionsCarouselContainer) {
            decisionsCarouselContainer.querySelectorAll(".deck-card").forEach(c => {
                const isActive = c.getAttribute("data-id") === decisionId;
                c.classList.toggle("active", isActive);
                if (isActive) {
                    c.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" });
                }
            });
        }

        // Load selected instrument brief and its independent reasoning trace.
        loadDecisionDetail(decisionId);
        loadDecisionTrace(decisionId);
    }

    // Header Re-validate — always visible next to the "as of" timestamp,
    // rather than buried at the bottom of the brief (owner feedback).
    function setHeaderRevalidateEnabled(enabled) {
        if (!decisionBriefRevalidateHeader) return;
        decisionBriefRevalidateHeader.disabled = !enabled;
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

    document.getElementById("decision-brief-market")?.addEventListener("click", () => {
        switchTab("market");
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
    document.getElementById("decision-brief-open-chart")?.addEventListener("click", () => {
        openChartModal();
    });
    document.getElementById("decision-brief-news")?.addEventListener("click", () => {
        switchBriefTab("context");
    });
    document.getElementById("decision-brief-compare")?.addEventListener("click", () => {
        openCompareModal();
    });