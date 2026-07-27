
    const dagNodesContainer = document.getElementById("dag-nodes-container");
    const dagSvgLines = document.getElementById("dag-svg-lines");
    const dagDetailsPanel = document.getElementById("dag-details-panel");
    const dagDetailsTitle = document.getElementById("dag-details-title");
    const dagDetailsStatus = document.getElementById("dag-details-status");
    const dagDetailsSummary = document.getElementById("dag-details-summary");
    const dagDetailsGrid = document.getElementById("dag-details-grid");

    async function loadDecisionTrace(decisionId) {
        try {
            const res = await apiRequest(`/api/v1/decisions/${decisionId}/trace`);
            if (activeDecisionId !== decisionId) return;
            if (res && res.status === "success") {
                activeTrace = res.data;
                renderTraceDAG(activeTrace);
            }
        } catch (err) {
            console.error(`Failed to load trace for ${decisionId}`, err);
        }
    }

    // Shared by the node list and the detail card header.
    const STAGE_ICONS = {
        "universe_ingest": "fa-globe",
        "technical_indicators": "fa-chart-area",
        "scoring_engine": "fa-calculator",
        "confidence_engine": "fa-shield-halved",
        "risk_assessment": "fa-triangle-exclamation",
        "quality_gates": "fa-circle-check",
        "final_decision": "fa-brain",
        "regime": "fa-chart-line",
        "market_health": "fa-heartbeat",
        "sector_health": "fa-industry",
        "evidence": "fa-layer-group",
        "score": "fa-calculator",
        "confidence": "fa-shield-halved",
        "risk": "fa-triangle-exclamation",
        "decision": "fa-brain",
        "trade_plan": "fa-list-check",
    };

    // Every stage maps to exactly one brief tab — the DAG points, the tab
    // explains. Covers both stage-id vocabularies seen in persisted traces.
    const STAGE_TAB_MAP = {
        universe_ingest: "setup",
        technical_indicators: "setup",
        trade_plan: "setup",
        scoring_engine: "analysis",
        confidence_engine: "analysis",
        risk_assessment: "analysis",
        quality_gates: "analysis",
        final_decision: "analysis",
        score: "analysis",
        confidence: "analysis",
        risk: "analysis",
        decision: "analysis",
        evidence: "analysis",
        regime: "context",
        market_health: "context",
        sector_health: "context",
    };

    // Each stage's own computed state instead of the generic lifecycle
    // "Completed" (owner audit #19/#14) — reuses whatever's already loaded
    // client-side; a stage with no specific mapping (or whose data hasn't
    // loaded yet) keeps showing the persisted lifecycle status, refreshed
    // once the real data arrives via refreshDagNodeMeanings().
    function stageMeaning(stageId) {
        const depth = activeDepth;
        const ctx = activeContextData;
        const decision = activeDecisionData;

        if (stageId === "regime") {
            const regime = ctx && ctx.regime;
            if (!regime || regime.status !== "ASSESSED") return null;
            const labels = Array.isArray(regime.labels) ? regime.labels : [];
            const trendLabel = labels.find(l => regimeLabelCategory(l) === "Trend") || labels[0];
            if (!trendLabel) return null;
            return { label: friendlyLabel(trendLabel), tone: contextChipTone(trendLabel) };
        }
        if (stageId === "market_health") {
            const mh = ctx && ctx.market_health;
            if (!mh || mh.status !== "ASSESSED") return null;
            const dims = mh.dimensions || {};
            const preferred = dims.momentum || Object.values(dims)[0];
            if (!preferred) return null;
            return { label: friendlyLabel(preferred), tone: contextChipTone(preferred) };
        }
        if (stageId === "score" || stageId === "confidence" || stageId === "risk") {
            const block = depth && depth[stageId];
            if (!block || block.status !== "OK") return null;
            const view = analysisPresentation(friendlyAnalysisName(stageId), block, stageId);
            const band = view.displayBand;
            if (!band) return null;
            const b = band.toUpperCase();
            let tone = "warn";
            if (stageId === "risk") {
                if (b === "LOW") tone = "good"; else if (b === "HIGH") tone = "bad";
            } else {
                if (b === "EXCELLENT" || b === "STRONG" || b === "GOOD" || b === "HIGH") tone = "good";
                else if (b === "WEAK" || b === "LOW") tone = "bad";
            }
            return { label: band, tone };
        }
        if (stageId === "decision") {
            if (!decision || !decision.metadata) return null;
            const stance = decisionStance(decision.metadata.decision_type, decision.metadata.direction);
            const toneMap = {
                "stance-buy": "good", "stance-sell": "bad",
                "stance-hold": "warn", "stance-pass": "neutral", "stance-wait": "neutral",
            };
            return { label: stance.label, tone: toneMap[stance.cls] || "neutral" };
        }
        if (stageId === "trade_plan") {
            if (!decision) return null;
            return decision.trade_plan
                ? { label: "Authorized", tone: "good" }
                : { label: "Not authorized", tone: "neutral" };
        }
        if (stageId === "evidence") {
            const gates = decision && decision.analysis && Array.isArray(decision.analysis.gate_results)
                ? decision.analysis.gate_results
                : [];
            const gate = gates.find(g => g && g.gate === "EVIDENCE");
            if (!gate) return null;
            return gate.passed ? { label: "Sufficient", tone: "good" } : { label: "Insufficient", tone: "bad" };
        }
        return null;
    }

    function dagStatusBadgeHtml(stage) {
        const meaning = stageMeaning(stage.stage_id);
        if (meaning) {
            return `<span class="dag-node-status meaning-${meaning.tone}">${escapeDecisionHtml(meaning.label)}</span>`;
        }
        return `<span class="dag-node-status ${stage.status.toLowerCase()}">${stage.status}</span>`;
    }

    // Called once activeDepth/activeContextData arrive (async, after the DAG
    // already rendered) so nodes upgrade from the generic lifecycle status
    // to their real computed state without re-selecting or jumping tabs.
    function refreshDagNodeMeanings() {
        renderSidebarQuickSummary();
        if (!dagNodesContainer || !activeTrace || !Array.isArray(activeTrace.stages)) return;
        activeTrace.stages.forEach(stage => {
            const node = dagNodesContainer.querySelector(`[data-stage="${stage.stage_id}"]`);
            const badge = node && node.querySelector(".dag-node-status");
            if (!badge) return;
            const meaning = stageMeaning(stage.stage_id);
            if (!meaning) return;
            badge.className = `dag-node-status meaning-${meaning.tone}`;
            badge.textContent = meaning.label;
        });
    }

    function renderTraceDAG(trace) {
        if (!dagNodesContainer) return;
        dagNodesContainer.innerHTML = "";
        if (dagSvgLines) dagSvgLines.innerHTML = "";
        selectedStageId = null;

        if (!trace.stages || trace.stages.length === 0) {
            dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">No reasoning trace recorded for this decision yet.</div>';
            if (dagDetailsSummary) dagDetailsSummary.textContent = "This decision has no recorded reasoning stages to show.";
            return;
        }

        trace.stages.forEach((stage, idx) => {
            const node = document.createElement("div");
            node.className = "dag-node";
            node.setAttribute("data-stage", stage.stage_id);

            const icon = STAGE_ICONS[stage.stage_id] || "fa-circle-notch";

            node.innerHTML = `
                <i class="fa-solid ${icon} dag-node-icon"></i>
                <span class="dag-node-name" title="${escapeDecisionHtml(stage.name)}">${escapeDecisionHtml(stage.name)}</span>
                ${dagStatusBadgeHtml(stage)}
            `;

            node.addEventListener("click", () => {
                selectNode(stage.stage_id, { userInitiated: true });
            });

            dagNodesContainer.appendChild(node);
        });

        // Add resize observer to draw SVG lines dynamically when nodes position shifts
        const resizeObserver = new ResizeObserver(() => {
            drawDAGLines();
        });
        resizeObserver.observe(dagNodesContainer);

        // Draw initial connector lines
        setTimeout(drawDAGLines, 100);

        // Highlight the first node by default, but never jump tabs for it —
        // only an actual click should navigate away from whichever tab the
        // trader is currently comparing across decisions (owner-reported:
        // picking a new decision was silently yanking them back to Context).
        if (trace.stages.length > 0) {
            selectNode(trace.stages[0].stage_id, { userInitiated: false });
        }
    }

    function selectNode(stageId, { userInitiated = false } = {}) {
        const nodes = dagNodesContainer.querySelectorAll(".dag-node");
        nodes.forEach(n => {
            if (n.getAttribute("data-stage") === stageId) {
                n.classList.add("active");
            } else {
                n.classList.remove("active");
            }
        });

        const stage = activeTrace.stages.find(s => s.stage_id === stageId);
        if (stage) {
            showStageDetails(stage);
            const tab = STAGE_TAB_MAP[stage.stage_id];
            if (userInitiated && tab) switchBriefTab(tab);
        }
    }

    function renderStageProvenance(stage) {
        if (!dagDetailsGrid) return;
        const refIds = Array.isArray(stage.details && stage.details.ref_ids)
            ? stage.details.ref_ids
            : [];
        if (!refIds.length) {
            dagDetailsGrid.innerHTML = '<div class="text-muted" style="grid-column: 1/-1; font-size: 0.72rem;">No source references recorded for this stage.</div>';
            return;
        }
        const label = refIds.length === 1 ? "reference" : "references";
        const shown = refIds.length > 2
            ? `${refIds.slice(0, 2).join(", ")} +${refIds.length - 2} more`
            : refIds.join(", ");
        dagDetailsGrid.innerHTML = `
            <div class="strategy-criteria-item" style="grid-column: 1/-1;">
                <span class="criteria-label">${escapeDecisionHtml(label)}</span>
                <span class="criteria-value" title="${escapeDecisionHtml(refIds.join(", "))}">${escapeDecisionHtml(shown)}</span>
            </div>
        `;
    }

    // Full detail for every stage already lives in one of the four brief tabs
    // (Setup/Analysis/Context) — this panel shows only what isn't duplicated
    // there: the stage's own status and its provenance references.
    function showStageDetails(stage) {
        if (!dagDetailsPanel) return;
        selectedStageId = stage.stage_id;

        const icon = STAGE_ICONS[stage.stage_id] || "fa-circle-notch";
        dagDetailsTitle.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeDecisionHtml(stage.name)}</span>`;
        dagDetailsStatus.className = `badge ${stage.status.toLowerCase()}`;
        dagDetailsStatus.textContent = stage.status;

        const tab = STAGE_TAB_MAP[stage.stage_id];
        dagDetailsSummary.innerHTML = tab
            ? `<p class="context-caption">Full detail lives in the <strong>${escapeDecisionHtml(BRIEF_TAB_LABELS[tab] || friendlyLabel(tab))}</strong> tab — opened automatically.</p>`
            : `<p class="context-caption">${escapeDecisionHtml(stage.summary || "")}</p>`;

        renderStageProvenance(stage);
        dagDetailsPanel.style.display = "block";
    }

    const BRIEF_TAB_NAMES = new Set(["setup", "analysis", "context", "response", "history"]);

    // Trader-facing tab labels (UX-4 renamed the visible tab strip text
    // while deliberately keeping these internal data-brief-tab keys
    // unchanged) — anywhere a tab name is reconstructed for display must
    // use this, not a raw capitalization of the internal key, or it goes
    // stale the moment the visible name diverges from the key (as
    // showStageDetails's "Setup tab" text just did).
    const BRIEF_TAB_LABELS = {
        setup: "Trade Plan",
        analysis: "Analysis",
        context: "Market Context",
        response: "Response",
        history: "History",
    };

    // Sticky-cockpit tab strip. Deliberately not reset when the selected
    // decision changes (selectBriefing) — flipping through several decisions
    // to compare the same aspect should keep you on that aspect.
    function switchBriefTab(name) {
        if (!BRIEF_TAB_NAMES.has(name)) return;
        activeBriefTab = name;
        if (decisionBriefTabstrip) {
            decisionBriefTabstrip.querySelectorAll(".brief-tab").forEach(btn => {
                btn.classList.toggle("active", btn.getAttribute("data-brief-tab") === name);
            });
        }
        if (decisionBriefBody) {
            decisionBriefBody.querySelectorAll(".tabpane").forEach(pane => {
                pane.classList.toggle("active", pane.getAttribute("data-brief-pane") === name);
            });
        }
    }

    function drawDAGLines() {
        if (!dagSvgLines || !dagNodesContainer) return;
        dagSvgLines.innerHTML = "";

        const nodes = Array.from(dagNodesContainer.querySelectorAll(".dag-node"));
        if (nodes.length < 2) return;

        // Get container bounding rect
        const containerRect = dagNodesContainer.getBoundingClientRect();
        
        // Match SVG viewport to container dimensions
        dagSvgLines.setAttribute("width", containerRect.width);
        dagSvgLines.setAttribute("height", containerRect.height);

        for (let i = 0; i < nodes.length - 1; i++) {
            const current = nodes[i].getBoundingClientRect();
            const next = nodes[i+1].getBoundingClientRect();

            // Calculate center coordinates relative to container
            const startX = (current.left + current.width / 2) - containerRect.left;
            const startY = (current.top + current.height / 2) - containerRect.top;
            
            const endX = (next.left + next.width / 2) - containerRect.left;
            const endY = (next.top + next.height / 2) - containerRect.top;

            // Draw line — a gentle continuous dash-flow animation (CSS
            // class, respects prefers-reduced-motion) gives the "animated
            // flow" feel the owner asked for without anything flashy.
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", startX);
            line.setAttribute("y1", startY);
            line.setAttribute("x2", endX);
            line.setAttribute("y2", endY);
            line.setAttribute("class", "dag-flow-line");
            line.setAttribute("stroke", "rgba(56, 189, 248, 0.2)");
            line.setAttribute("stroke-width", "2");
            line.setAttribute("stroke-dasharray", "4 4");

            // Brighter + faster flow along the line adjacent to the selected node
            if (nodes[i].classList.contains("active") || nodes[i+1].classList.contains("active")) {
                line.setAttribute("stroke", "rgba(56, 189, 248, 0.6)");
                line.setAttribute("stroke-width", "3");
                line.classList.add("dag-flow-line-active");
            }

            dagSvgLines.appendChild(line);
        }
    }