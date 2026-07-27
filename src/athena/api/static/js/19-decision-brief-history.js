

    function journalActionTone(userAction) {
        if (userAction === "ACCEPTED") return "good";
        if (userAction === "REJECTED") return "bad";
        return "neutral";
    }

    function renderJournalPanel(decisionId) {
        const host = document.getElementById("decision-journal-panel");
        if (!host) return;

        const entry = activeJournalEntry;
        const actionRow = `
            <div class="journal-action-row">
                <button type="button" class="btn btn-outline journal-action-btn" data-action="ACCEPTED">
                    <i class="fa-solid fa-check"></i> Accept
                </button>
                <button type="button" class="btn btn-outline journal-action-btn" data-action="REJECTED">
                    <i class="fa-solid fa-xmark"></i> Reject
                </button>
                <button type="button" class="btn btn-outline journal-action-btn" data-action="IGNORED">
                    <i class="fa-solid fa-eye-slash"></i> Ignore
                </button>
            </div>
            <textarea id="journal-notes-input" class="journal-notes-input" rows="2"
                placeholder="Optional notes (why, sizing, conviction…)"></textarea>
        `;

        const statusBadge = entry
            ? `<div class="journal-status-row">
                   <span class="context-chip tone-${journalActionTone(entry.user_action)}">${escapeDecisionHtml(entry.user_action)}</span>
                   <span class="text-muted">recorded ${escapeDecisionHtml(formatDecisionTime(entry.action_ts))}</span>
                   ${entry.notes ? `<p class="context-caption">${escapeDecisionHtml(entry.notes)}</p>` : ""}
               </div>`
            : "";

        let outcomeBlock = "";
        if (entry && entry.user_action === "ACCEPTED") {
            outcomeBlock = activeTradeOutcome
                ? renderOutcomeResult(activeTradeOutcome)
                : renderOutcomeForm();
        }

        host.innerHTML = `
            ${statusBadge}
            <details class="decision-depth-details" ${entry ? "" : "open"}>
                <summary>${entry ? "Change response" : "Record your response"}</summary>
                ${actionRow}
            </details>
            ${outcomeBlock}
        `;

        host.querySelectorAll(".journal-action-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const notesEl = document.getElementById("journal-notes-input");
                recordJournalEntry(decisionId, btn.getAttribute("data-action"), notesEl ? notesEl.value : "", btn);
            });
        });

        const outcomeSubmit = document.getElementById("outcome-submit-btn");
        if (outcomeSubmit) {
            outcomeSubmit.addEventListener("click", () => recordTradeOutcomeNow(decisionId, outcomeSubmit));
        }
    }

    function renderOutcomeForm() {
        const plan = activeDecisionData && activeDecisionData.trade_plan;
        const defaultQty = plan ? plan.position_size : 1;
        return `
            <div class="outcome-form">
                <h5>Log realized outcome</h5>
                <p class="context-caption">
                    PnL, holding time, and TradePlan adherence are computed here — never entered
                    manually.
                </p>
                <div class="outcome-form-grid">
                    <label>Entry price
                        <input id="outcome-entry-price" type="number" step="0.01"
                            value="${plan ? plan.entry_low : ""}">
                    </label>
                    <label>Exit price
                        <input id="outcome-exit-price" type="number" step="0.01">
                    </label>
                    <label>Quantity
                        <input id="outcome-quantity" type="number" step="1" min="1" value="${defaultQty}">
                    </label>
                </div>
                <button id="outcome-submit-btn" class="btn btn-outline" type="button">
                    <i class="fa-solid fa-flag-checkered"></i> Log outcome
                </button>
            </div>
        `;
    }

    // "Did the call turn out right?" (owner UX audit — Decision History
    // should show outcome + accuracy, not just raw pnl) — a friendlier label
    // wrapping the same real pnl sign already shown below, same convention
    // as qualityBand/riskBand: cosmetic phrasing over an already-real value,
    // never a second judgment of the decision.
    function decisionAccuracyLabel(outcome) {
        const meta = activeDecisionData && activeDecisionData.metadata;
        const stance = meta ? decisionStance(meta.decision_type, meta.direction) : null;
        const pnlValue = Number(outcome.pnl);
        if (!Number.isFinite(pnlValue) || pnlValue === 0) {
            return { label: stance ? `${stance.label} call — broke even` : "Broke even", tone: "neutral", icon: "fa-circle-minus" };
        }
        const paidOff = pnlValue > 0;
        const label = stance
            ? `${stance.label} call ${paidOff ? "paid off" : "didn't pay off"}`
            : (paidOff ? "Call paid off" : "Call didn't pay off");
        return { label, tone: paidOff ? "good" : "bad", icon: paidOff ? "fa-circle-check" : "fa-circle-xmark" };
    }

    function renderOutcomeResult(outcome) {
        const pnlValue = Number(outcome.pnl);
        const pnlTone = pnlValue > 0 ? "good" : (pnlValue < 0 ? "bad" : "neutral");
        const accuracy = decisionAccuracyLabel(outcome);
        const adherence = outcome.adherence || {};
        const adherenceChips = Object.entries(adherence).map(([key, value]) => {
            const label = key.replace(/_/g, " ");
            return `<span class="context-chip tone-${value ? "good" : "bad"}">${escapeDecisionHtml(label)}: ${value ? "yes" : "no"}</span>`;
        }).join("");
        return `
            <div class="outcome-result">
                <h5>Realized outcome</h5>
                <div class="outcome-accuracy-badge tone-${accuracy.tone}">
                    <i class="fa-solid ${accuracy.icon}"></i> ${escapeDecisionHtml(accuracy.label)}
                </div>
                <div class="outcome-result-grid">
                    <div><span>Entry</span><strong>${formatDecisionPrice(outcome.entry_price)}</strong></div>
                    <div><span>Exit</span><strong>${formatDecisionPrice(outcome.exit_price)}</strong></div>
                    <div><span>PnL</span><strong class="tone-${pnlTone}-text">${formatDecisionPrice(outcome.pnl)}</strong></div>
                    <div><span>Holding</span><strong>${Math.round(outcome.holding_seconds / 60)} min</strong></div>
                </div>
                <div class="context-chip-row">${adherenceChips}</div>
                <p class="context-caption">Closed ${escapeDecisionHtml(formatDecisionTime(outcome.closed_ts))}</p>
            </div>
        `;
    }

    async function loadJournalPanel(decisionId) {
        try {
            const [journalRes, outcomeRes] = await Promise.all([
                apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/journal`, { skipToast: true }),
                apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/outcome`, { skipToast: true }),
            ]);
            if (activeDecisionId !== decisionId) return;
            activeJournalEntry = journalRes && journalRes.data;
            activeTradeOutcome = outcomeRes && outcomeRes.data;
            renderJournalPanel(decisionId);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load journal/outcome for ${decisionId}`, err);
            const host = document.getElementById("decision-journal-panel");
            if (host) host.innerHTML = '<div class="context-caption">Unable to load your response.</div>';
        }
    }

    async function recordJournalEntry(decisionId, userAction, notes, button) {
        if (button) button.disabled = true;
        try {
            const res = await apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/journal`, {
                method: "POST",
                body: JSON.stringify({ user_action: userAction, notes: notes || "" }),
            });
            activeJournalEntry = res && res.data;
            showToast(`Response recorded: ${userAction}`, "success");
            renderJournalPanel(decisionId);
        } catch (err) {
            console.error(`Failed to record journal entry for ${decisionId}`, err);
        } finally {
            if (button) button.disabled = false;
        }
    }

    async function recordTradeOutcomeNow(decisionId, button) {
        const entryEl = document.getElementById("outcome-entry-price");
        const exitEl = document.getElementById("outcome-exit-price");
        const qtyEl = document.getElementById("outcome-quantity");
        const entryPrice = entryEl ? entryEl.value : "";
        const exitPrice = exitEl ? exitEl.value : "";
        const quantity = qtyEl ? qtyEl.value : "";
        if (!entryPrice || !exitPrice || !quantity) {
            showToast("Entry price, exit price, and quantity are required", "danger");
            return;
        }
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Logging…';
        }
        try {
            const res = await apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/outcome`, {
                method: "POST",
                body: JSON.stringify({
                    entry_price: entryPrice,
                    exit_price: exitPrice,
                    quantity: Number(quantity),
                }),
            });
            activeTradeOutcome = res && res.data;
            showToast("Outcome logged.", "success");
            renderJournalPanel(decisionId);
        } catch (err) {
            console.error(`Failed to record trade outcome for ${decisionId}`, err);
            showToast("Failed to log outcome.", "danger");
            if (button) {
                button.disabled = false;
                button.innerHTML = '<i class="fa-solid fa-flag-checkered"></i> Log outcome';
            }
        }
    }

    // Max possible distance across 3 dimensions each 0-100 (sqrt(100^2*3)) —
    // used only to render an intuitive similarity %, never persisted or compared.
    const ANALOG_MAX_DISTANCE = 173.2;

    // Historical Validation (owner UX audit) — win-rate/avg-return/avg-holding
    // across whichever shown analogs have a realized outcome. Exact values
    // from DecisionAnalogsDTO's aggregate fields (UX-6 backend addition);
    // None/zero-sample is shown honestly, never backfilled with a guess.
    function renderHistoricalValidation(data, shownCount) {
        const sampleSize = Number(data.outcomes_sample_size) || 0;
        if (!sampleSize) {
            return `<div class="historical-validation tone-neutral">
                <span class="historical-validation-title">Historical validation</span>
                <p class="context-caption">No realized outcomes logged yet among these similar setups — this will fill in once at least one is closed out.</p>
            </div>`;
        }
        const winRate = Number(data.win_rate_pct);
        const avgReturn = Number(data.avg_return_pct);
        const avgHolding = Number(data.avg_holding_days);
        const winRateLabel = Number.isFinite(winRate) ? `${winRate.toFixed(0)}%` : "—";
        const avgReturnLabel = Number.isFinite(avgReturn) ? `${avgReturn >= 0 ? "+" : ""}${avgReturn.toFixed(1)}%` : "—";
        const avgHoldingLabel = Number.isFinite(avgHolding) ? `${avgHolding.toFixed(1)}d` : "—";
        const tone = Number.isFinite(winRate) ? (winRate >= 60 ? "good" : (winRate <= 40 ? "bad" : "warn")) : "neutral";
        return `
            <div class="historical-validation tone-${tone}">
                <span class="historical-validation-title">Historical validation</span>
                <div class="historical-validation-stats">
                    <div><strong>${winRateLabel}</strong><span>win rate</span></div>
                    <div><strong>${avgReturnLabel}</strong><span>avg return</span></div>
                    <div><strong>${avgHoldingLabel}</strong><span>avg holding</span></div>
                </div>
                <p class="context-caption">Across ${sampleSize} of the ${shownCount} similar setups shown with a realized outcome.</p>
            </div>
        `;
    }

    function renderAnalogsPanel(analogs) {
        const host = document.getElementById("decision-analogs-panel");
        if (!host) return;
        const data = analogs || { analogs: [], compared_count: 0 };
        const rows = Array.isArray(data.analogs) ? data.analogs : [];

        if (!rows.length) {
            host.innerHTML = `<div class="context-caption">
                ${data.compared_count === 0
                    ? "No comparable historical decisions yet — this needs a scored, confidence-rated, risk-rated decision to compare against."
                    : "No similar setups found."}
            </div>`;
            return;
        }

        host.innerHTML = `
            ${renderHistoricalValidation(data, rows.length)}
            <div class="analog-list">
                ${rows.map(row => {
                    const symbol = (row.instrument_id || "").split(":").pop() || "—";
                    const similarity = Math.max(
                        0, Math.round(100 - (Number(row.distance) / ANALOG_MAX_DISTANCE) * 100)
                    );
                    const stance = decisionStance(row.decision_type, row.direction);
                    const responseChip = row.user_action
                        ? contextChip(row.user_action, journalActionTone(row.user_action))
                        : `<span class="context-chip tone-unknown">no response</span>`;
                    const pnlValue = row.outcome_pnl !== null && row.outcome_pnl !== undefined
                        ? Number(row.outcome_pnl) : null;
                    const outcomeChip = pnlValue !== null
                        ? `<span class="context-chip tone-${pnlValue > 0 ? "good" : (pnlValue < 0 ? "bad" : "neutral")}">${escapeDecisionHtml(formatDecisionPrice(row.outcome_pnl))}</span>`
                        : `<span class="context-chip tone-unknown">no outcome logged</span>`;
                    return `
                        <button type="button" class="analog-row" data-decision-id="${escapeDecisionHtml(row.decision_id)}">
                            <span class="analog-row-main">
                                <strong>${escapeDecisionHtml(symbol)}</strong>
                                <span class="stance-chip ${stance.cls}">${stance.label}</span>
                                <small>${escapeDecisionHtml(formatDecisionTime(row.ts))}</small>
                            </span>
                            <span class="analog-row-chips">
                                <span class="context-chip tone-neutral">${similarity}% similar</span>
                                ${responseChip}
                                ${outcomeChip}
                            </span>
                        </button>
                    `;
                }).join("")}
            </div>
            <p class="context-caption">Compared against ${data.compared_count} historical decision(s) with a comparable fingerprint.</p>
        `;

        host.querySelectorAll(".analog-row").forEach(row => {
            row.addEventListener("click", () => {
                const id = row.getAttribute("data-decision-id");
                if (id && id !== activeDecisionId) selectBriefing(id);
            });
        });
    }

    async function loadDecisionAnalogs(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/analogs`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeAnalogs = response && response.data;
            renderAnalogsPanel(activeAnalogs);
            // DT-2: Quick Summary's Win Rate/Avg Holding rows depend on this
            // same activeAnalogs — refresh once it's loaded (nothing else
            // re-rendered the sidebar for this specific data before).
            renderSidebarQuickSummary();
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load analogs for ${decisionId}`, err);
            const host = document.getElementById("decision-analogs-panel");
            if (host) host.innerHTML = '<div class="context-caption">Unable to load similar setups.</div>';
        }
    }

    function formatCounterfactualNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num.toFixed(2) : "—";
    }

    function renderCounterfactualPanel(data) {
        const host = document.getElementById("decision-counterfactual-panel");
        if (!host) return;
        if (!data) {
            host.innerHTML = '<div class="context-caption">Unable to compute the gap to TRADE.</div>';
            return;
        }

        if (data.is_trade) {
            host.innerHTML = `
                <div class="counterfactual-cleared">
                    <span class="context-chip tone-good"><i class="fa-solid fa-check"></i> All gates cleared</span>
                    <p class="context-caption">${escapeDecisionHtml(data.summary)}</p>
                </div>
            `;
            return;
        }

        const scoreRow = data.score_current !== null && data.score_current !== undefined
            ? `
                <div class="counterfactual-row">
                    <span class="counterfactual-row-label">Composite score</span>
                    <span class="counterfactual-row-values">
                        <strong>${formatCounterfactualNumber(data.score_current)}</strong>
                        <small>/ ${formatCounterfactualNumber(data.score_required)} required</small>
                    </span>
                    ${data.score_gap !== null && data.score_gap !== undefined && Number(data.score_gap) > 0
                        ? `<span class="context-chip tone-bad">+${formatCounterfactualNumber(data.score_gap)} short</span>`
                        : `<span class="context-chip tone-good">met</span>`}
                </div>
            `
            : "";

        const gateRows = (Array.isArray(data.gates) ? data.gates : []).map(gate => {
            const hasNumbers = gate.current !== null && gate.current !== undefined
                && gate.required !== null && gate.required !== undefined;
            const gapPositive = gate.gap !== null && gate.gap !== undefined && Number(gate.gap) > 0;
            return `
                <div class="counterfactual-row">
                    <span class="counterfactual-row-label">${escapeDecisionHtml(friendlyLabel(gate.gate))}</span>
                    ${hasNumbers
                        ? `<span class="counterfactual-row-values">
                            <strong>${formatCounterfactualNumber(gate.current)}</strong>
                            <small>vs ${formatCounterfactualNumber(gate.required)} required</small>
                        </span>`
                        : `<span class="counterfactual-row-values"><small>${escapeDecisionHtml(gate.detail)}</small></span>`}
                    ${hasNumbers
                        ? (gapPositive
                            ? `<span class="context-chip tone-bad">gap ${formatCounterfactualNumber(gate.gap)}</span>`
                            : `<span class="context-chip tone-good">met</span>`)
                        : `<span class="context-chip tone-unknown">blocked</span>`}
                </div>
            `;
        }).join("");

        host.innerHTML = `
            <div class="counterfactual-body">
                ${scoreRow}
                ${gateRows}
                <p class="counterfactual-summary">${escapeDecisionHtml(data.summary)}</p>
            </div>
        `;
    }

    async function loadDecisionCounterfactual(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/counterfactual`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeCounterfactual = response && response.data;
            renderCounterfactualPanel(activeCounterfactual);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load counterfactual for ${decisionId}`, err);
            const host = document.getElementById("decision-counterfactual-panel");
            if (host) host.innerHTML = '<div class="context-caption">Unable to compute the gap to TRADE.</div>';
        }
    }

    // A narrative delta between two consecutive timeline entries (owner UX
    // audit — "timeline should read as an evolving story, not a flat list of
    // timestamps"). Reuses decisionScoreValue's existing explanation-text
    // extraction (the same technique already trusted for timeline sorting) —
    // no new data, no invented commentary, just a factual stance/score delta.
    function timelineNarrative(current, previous) {
        if (!previous) return "Earliest tracked assessment shown for this setup.";
        const curMeta = current.metadata || {};
        const prevMeta = previous.metadata || {};
        const curStance = decisionStance(curMeta.decision_type, curMeta.direction);
        const prevStance = decisionStance(prevMeta.decision_type, prevMeta.direction);
        const curScore = decisionScoreValue(current);
        const prevScore = decisionScoreValue(previous);
        const parts = [];
        parts.push(curStance.label === prevStance.label
            ? `Stance held ${curStance.label}`
            : `Stance moved from ${prevStance.label} to ${curStance.label}`);
        if (curScore >= 0 && prevScore >= 0 && curScore !== prevScore) {
            const direction = curScore > prevScore ? "rose" : "fell";
            parts.push(`score ${direction} from ${prevScore.toFixed(1)} to ${curScore.toFixed(1)}`);
        }
        return `${parts.join(", ")}.`;
    }

    function renderDecisionTimeline(decision) {
        const host = document.getElementById("decision-history-timeline");
        if (!host || !decision || !decision.metadata) return;
        const instrument = String(decision.metadata.instrument_id || "").toUpperCase();
        const bare = instrument.split(":").pop();
        const rows = allTraceDecisionsList
            .filter(item => {
                const candidate = String(item?.metadata?.instrument_id || "").toUpperCase();
                return candidate === instrument || candidate.split(":").pop() === bare;
            })
            .sort((a, b) => new Date(b.metadata.ts || 0) - new Date(a.metadata.ts || 0))
            .slice(0, 8);
        if (!rows.length) {
            host.innerHTML = '<div class="text-muted">No persisted decision history.</div>';
            return;
        }
        host.innerHTML = rows.map((item, idx) => {
            const meta = item.metadata || {};
            const current = meta.decision_id === decision.metadata.decision_id;
            const stance = decisionStance(meta.decision_type, meta.direction);
            const narrative = timelineNarrative(item, rows[idx + 1]);
            return `
                <button type="button" class="decision-timeline-row ${current ? "current" : ""}"
                        data-decision-id="${escapeDecisionHtml(meta.decision_id || "")}">
                    <span class="decision-timeline-dot"></span>
                    <span>
                        <strong>${escapeDecisionHtml(formatDecisionTime(meta.ts))}</strong>
                        <small>${escapeDecisionHtml(stance.label)} · ${escapeDecisionHtml(meta.decision_type ? friendlyAnalysisName(meta.decision_type) : "Unknown")}</small>
                        <span class="decision-timeline-narrative">${escapeDecisionHtml(narrative)}</span>
                    </span>
                    ${current ? '<em>Current</em>' : ""}
                </button>
            `;
        }).join("");
        host.querySelectorAll(".decision-timeline-row").forEach(row => {
            row.addEventListener("click", () => {
                const id = row.getAttribute("data-decision-id");
                if (id && id !== activeDecisionId) selectBriefing(id);
            });
        });
    }