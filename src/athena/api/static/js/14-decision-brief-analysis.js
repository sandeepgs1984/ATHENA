

    // Expected Return % (owner audit #10) — pure arithmetic over the plan's
    // own persisted entry_low/entry_high/targets[0], nothing invented. Uses
    // the nearest target (targets[0]) since that's the one most likely to
    // be hit; when there's more than one target the label says "to T1" so
    // it's never ambiguous which target the % refers to.
    function computeExpectedReturnPct(plan, direction) {
        if (!plan || !Array.isArray(plan.targets) || !plan.targets.length) return null;
        const entryMid = (Number(plan.entry_low) + Number(plan.entry_high)) / 2;
        const target = Number(plan.targets[0]);
        if (!Number.isFinite(entryMid) || entryMid === 0 || !Number.isFinite(target)) return null;
        const isShort = String(direction || "").toUpperCase() === "SHORT";
        return isShort ? ((entryMid - target) / entryMid) * 100 : ((target - entryMid) / entryMid) * 100;
    }

    function computeTradePlanLevelPct(plan, price, direction) {
        const entryMid = (Number(plan && plan.entry_low) + Number(plan && plan.entry_high)) / 2;
        const level = Number(price);
        if (!Number.isFinite(entryMid) || entryMid === 0 || !Number.isFinite(level)) return null;
        const isShort = String(direction || "").toUpperCase() === "SHORT";
        return isShort ? ((entryMid - level) / entryMid) * 100 : ((level - entryMid) / entryMid) * 100;
    }

    function formatTradePlanLevelPct(pct) {
        if (pct === null || pct === undefined || !Number.isFinite(Number(pct))) return "";
        const n = Number(pct);
        return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
    }

    function renderTradePlanLevel(price, pct, tone) {
        const pctLabel = formatTradePlanLevelPct(pct);
        return `
            <span class="trade-plan-level">
                <span>${formatDecisionPrice(price)}</span>
                ${pctLabel ? `<span class="trade-plan-level-delta ${tone}">${escapeDecisionHtml(pctLabel)}</span>` : ""}
            </span>
        `;
    }

    function formatTradePlanValidityPeriod(validFrom, validUntil) {
        const start = new Date(validFrom);
        const end = new Date(validUntil);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "";
        const totalMinutes = Math.round((end.getTime() - start.getTime()) / 60000);
        if (totalMinutes <= 0) return "";
        const days = Math.floor(totalMinutes / 1440);
        const hours = Math.floor((totalMinutes % 1440) / 60);
        const minutes = totalMinutes % 60;
        const parts = [];
        if (days) parts.push(`${days}d`);
        if (hours) parts.push(`${hours}h`);
        if (minutes || parts.length === 0) parts.push(`${minutes}m`);
        return `Valid for ${parts.join(" ")}`;
    }

    function renderTradePlan(plan, decisionType, direction, freshness = null) {
        if (!plan) {
            const label = decisionType ? friendlyAnalysisName(decisionType) : "non-Trade";
            return `
                <div class="decision-brief-section">
                    <h4>ATHENA TradePlan</h4>
                    <div class="no-trade-plan">
                        No actionable entry or exit plan is authorized for a
                        <strong>${escapeDecisionHtml(label)}</strong> decision.
                        Re-validate when new market data arrives; do not infer levels from this screen.
                    </div>
                </div>
            `;
        }

        const validFrom = new Date(plan.valid_from);
        const validUntil = new Date(plan.valid_until);
        const now = new Date();
        let statusLabel = "Active";
        let statusClass = "active";
        if (!Number.isNaN(validUntil.getTime()) && now > validUntil) {
            statusLabel = "Expired";
            statusClass = "expired";
        } else if (!Number.isNaN(validFrom.getTime()) && now < validFrom) {
            statusLabel = "Pending";
            statusClass = "pending";
        }
        const freshnessStatus = String(freshness && freshness.status || statusLabel).toUpperCase();
        const historicalPlan = ["EXPIRED", "STALE", "UNKNOWN"].includes(freshnessStatus);
        const title = historicalPlan ? "Historical TradePlan" : "ATHENA TradePlan";
        const advisoryLabel = historicalPlan
            ? `${friendlyAnalysisName(freshnessStatus)} · re-validate before use`
            : "Advisory · not an order";
        const targetList = Array.isArray(plan.targets) ? plan.targets : [];
        const stopDeltaPct = computeTradePlanLevelPct(plan, plan.stop_loss, direction);
        const targets = targetList.length
            ? targetList.map(target => renderTradePlanLevel(
                target,
                computeTradePlanLevelPct(plan, target, direction),
                "target"
            )).join("")
            : "—";
        const returnPct = computeExpectedReturnPct(plan, direction);
        const returnLabel = returnPct !== null
            ? `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(1)}%`
            : "—";
        const returnCaption = targetList.length > 1 ? "to T1" : "to target";
        // A single point entry (low == high) reading as "X - X" looks like
        // a rendering glitch, not a real zone (owner-reported).
        const entryZoneLabel = Number(plan.entry_low) === Number(plan.entry_high)
            ? formatDecisionPrice(plan.entry_low)
            : `${formatDecisionPrice(plan.entry_low)} – ${formatDecisionPrice(plan.entry_high)}`;
        const validityPeriodLabel = formatTradePlanValidityPeriod(plan.valid_from, plan.valid_until);

        return `
            <div class="decision-brief-section">
                <div class="decision-brief-section-header">
                    <h4>${escapeDecisionHtml(title)}</h4>
                    <span class="trade-plan-label">${escapeDecisionHtml(advisoryLabel)}</span>
                </div>
                ${historicalPlan ? `
                    <div class="no-trade-plan">
                        This persisted plan is not current. Re-validate before considering these entry,
                        stop, or target levels.
                    </div>
                ` : ""}
                <div class="trade-plan-hero-grid">
                    <div class="trade-plan-hero-metric">
                        <span class="trade-plan-hero-label">Entry zone</span>
                        <strong class="trade-plan-hero-value">${entryZoneLabel}</strong>
                    </div>
                    <div class="trade-plan-hero-metric invalidation">
                        <span class="trade-plan-hero-label">Stop</span>
                        <strong class="trade-plan-hero-value">${renderTradePlanLevel(plan.stop_loss, stopDeltaPct, "stop")}</strong>
                    </div>
                    <div class="trade-plan-hero-metric target">
                        <span class="trade-plan-hero-label">${targetList.length > 1 ? "Targets" : "Target"}</span>
                        <strong class="trade-plan-hero-value">${targets}</strong>
                    </div>
                    <div class="trade-plan-hero-metric">
                        <span class="trade-plan-hero-label">Expected return</span>
                        <strong class="trade-plan-hero-value">${returnLabel}</strong>
                        <span class="trade-plan-hero-caption">${escapeDecisionHtml(returnCaption)}</span>
                    </div>
                    <div class="trade-plan-hero-metric">
                        <span class="trade-plan-hero-label">Risk : reward</span>
                        <strong class="trade-plan-hero-value">${formatDecisionRatio(plan.risk_reward)}</strong>
                    </div>
                </div>
                <div class="trade-plan-secondary-row">
                    <span>Model units · risk</span>
                    <strong>${escapeDecisionHtml(plan.position_size || 0)} · ${formatDecisionPrice(plan.risk_amount)}</strong>
                </div>
                <div class="trade-plan-validity">
                    <span class="trade-plan-validity-window">
                        ${validityPeriodLabel ? `<strong>${escapeDecisionHtml(validityPeriodLabel)}</strong>` : ""}
                        <span>${formatDecisionTime(plan.valid_from)} → ${formatDecisionTime(plan.valid_until)}</span>
                    </span>
                    <span class="plan-status-group">
                        <span class="plan-status ${statusClass}">${statusLabel}</span>
                        <span id="trade-plan-freshness-badge" class="plan-freshness-badge"></span>
                    </span>
                </div>
            </div>
        `;
    }

    function renderPlanFreshnessBadge(data) {
        const badge = document.getElementById("trade-plan-freshness-badge");
        if (!badge) return;
        if (!data || !data.has_trade_plan) {
            badge.textContent = "";
            badge.title = "";
            badge.className = "plan-freshness-badge";
            return;
        }
        badge.className = `plan-freshness-badge tone-${String(data.status).toLowerCase()}`;
        badge.textContent = formatTradePlanFreshnessBadge(data);
        badge.title = formatTradePlanFreshnessTitle(data);
    }

    async function loadDecisionPlanFreshness(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/plan-freshness`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activePlanFreshness = response && response.data;
            renderPlanFreshnessBadge(activePlanFreshness);
            renderDecisionActionability(activePlanFreshness);
            if (typeof renderEntryReadiness === "function") renderEntryReadiness(activePlanFreshness);
            renderSidebarQuickSummary();
            refreshTradePlaybook(activePlanFreshness);
            refreshActiveDecisionChart();
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load plan freshness for ${decisionId}`, err);
        }
    }

    // Number(null) is 0 in JavaScript, not NaN — a genuinely-absent value
    // (status !== "OK", JSON null) would otherwise silently become a fake
    // "0.0", which is exactly the owner-reported confusion (a real error
    // state rendering as a plausible-looking zero score instead of an
    // honest "—"). Same class of bug already fixed once for the chart's
    // numericOrNull — this was the one other place it was still lurking.
    function analysisPercent(value) {
        if (value === null || value === undefined) return "—";
        const number = Number(value);
        return Number.isFinite(number) ? `${number.toFixed(1)}` : "—";
    }

    function analysisMeterWidth(value) {
        if (value === null || value === undefined) return 0;
        const number = Number(value);
        if (!Number.isFinite(number)) return 0;
        return Math.max(0, Math.min(100, number));
    }

    function analysisPresentation(label, block, tone) {
        const data = block || {};
        const status = String(data.status || "UNKNOWN").toUpperCase();
        const level = data.level ? String(data.level).toUpperCase() : "";
        // Same Number(null) === 0 trap as analysisPercent/analysisMeterWidth
        // above — a genuinely-absent completeness value must read as
        // "Completeness unknown", never a fabricated "0% complete".
        const completeness = (data.completeness === null || data.completeness === undefined)
            ? NaN
            : Number(data.completeness);
        const completenessLabel = Number.isFinite(completeness)
            ? `${Math.round(completeness * 100)}% complete`
            : "Completeness unknown";
        const config = {
            score: {
                icon: "fa-chart-line",
                eyebrow: "Opportunity quality",
                guidance: "Higher means stronger alignment with the active strategy.",
            },
            confidence: {
                icon: "fa-shield-halved",
                eyebrow: "Evidence reliability",
                guidance: "Higher means the assessment is better supported.",
            },
            risk: {
                icon: "fa-triangle-exclamation",
                eyebrow: "Exposure level",
                guidance: "Higher means more uncertainty or market exposure.",
            },
        }[tone];
        // Score has no backend-computed level (scoring.json carries no
        // levels block) — band it client-side from the same value everyone
        // else already sees, same convention as the Hero cockpit gauges.
        // Confidence/Risk keep their real backend level; never invented.
        const isOk = status === "OK";
        const displayBand = tone === "score"
            ? (isOk ? qualityBand(data.value) : null)
            : (isOk && level ? friendlyAnalysisName(level) : null);
        return {
            data,
            status,
            level,
            displayBand,
            completenessLabel,
            icon: config.icon,
            eyebrow: config.eyebrow,
            guidance: config.guidance,
            label,
            tone,
            valueLabel: analysisPercent(data.value),
            meterWidth: analysisMeterWidth(data.value),
        };
    }

    // Same "Eligible"/"Excluded" wording as the Universe table (UX-8 copy
    // pass) — this previously showed the raw INCLUDED/EXCLUDED/UNKNOWN
    // status instead of matching that established, friendlier vocabulary.
    function friendlyEligibilityLabel(status) {
        if (status === "INCLUDED") return "Eligible";
        if (status === "EXCLUDED") return "Excluded";
        return "Unknown";
    }

    function renderEligibilityDepth(eligibility) {
        const host = document.getElementById("decision-eligibility-depth");
        if (!host) return;
        const data = eligibility || {};
        const status = String(data.status || "UNKNOWN").toUpperCase();
        const statusClass =
            status === "INCLUDED" ? "included" : (status === "EXCLUDED" ? "excluded" : "unknown");
        const exclusions = Array.isArray(data.exclusion_reasons) ? data.exclusion_reasons : [];
        const rules = Array.isArray(data.rules) ? data.rules : [];
        const historicalPlan = decisionHasHistoricalTradePlan(activeDecisionData, activePlanFreshness);
        host.innerHTML = `
            <div class="eligibility-summary">
                <span class="depth-status ${statusClass}">${escapeDecisionHtml(friendlyEligibilityLabel(status))}</span>
                <span>${escapeDecisionHtml(data.summary || "No eligibility assessment recorded for this decision.")}</span>
            </div>
            ${historicalPlan ? `
                <div class="eligibility-exclusions">
                    <span>Persisted assessment from the historical decision run; use latest revalidation before acting.</span>
                </div>
            ` : ""}
            ${exclusions.length ? `
                <div class="eligibility-exclusions">
                    ${exclusions.map(reason => `<span>${escapeDecisionHtml(reason)}</span>`).join("")}
                </div>
            ` : ""}
            ${rules.length ? `
                <details class="decision-depth-details">
                    <summary>${rules.length} eligibility rule${rules.length === 1 ? "" : "s"}</summary>
                    <div class="eligibility-rule-list">
                        ${rules.map(rule => `
                            <div class="eligibility-rule">
                                <i class="fa-solid ${rule.passed ? "fa-circle-check pass" : "fa-circle-xmark fail"}"></i>
                                <div>
                                    <strong>${escapeDecisionHtml(friendlyAnalysisName(rule.rule))}</strong>
                                    <p>${escapeDecisionHtml(rule.explanation || "No rationale recorded.")}</p>
                                </div>
                            </div>
                        `).join("")}
                    </div>
                </details>
            ` : ""}
        `;
    }

    const QUALITY_LADDER_BANDS = ["Weak", "Fair", "Good", "Strong", "Excellent"];

    function qualityLadder(band) {
        return `
            <div class="quality-ladder" aria-hidden="true">
                ${QUALITY_LADDER_BANDS.map(b => `<span class="quality-ladder-seg${b === band ? " active" : ""}"></span>`).join("")}
            </div>
        `;
    }

    function renderAnalysisSummaryCard(label, block, tone) {
        const view = analysisPresentation(label, block, tone);
        const band = view.displayBand || "Unknown";
        return `
            <article class="analysis-summary-card ${escapeDecisionHtml(tone)}">
                <div class="analysis-summary-top">
                    <span class="analysis-summary-icon">
                        <i class="fa-solid ${escapeDecisionHtml(view.icon)}"></i>
                    </span>
                    <div>
                        <span class="analysis-summary-eyebrow">${escapeDecisionHtml(view.eyebrow)}</span>
                        <h5>${escapeDecisionHtml(label)}</h5>
                    </div>
                    <span class="depth-status ${view.status === "OK" ? "included" : "unknown"}">
                        ${escapeDecisionHtml(view.status === "OK" ? "OK" : "Unknown")}
                    </span>
                </div>
                <div class="analysis-summary-band">${escapeDecisionHtml(band)}</div>
                <div class="analysis-summary-score">
                    <strong>${escapeDecisionHtml(view.valueLabel)}</strong>
                    ${view.valueLabel === "—" ? "" : "<span>/ 100</span>"}
                </div>
                <div class="analysis-meter" aria-hidden="true">
                    <span style="width: ${view.meterWidth}%"></span>
                </div>
                ${tone === "score" ? qualityLadder(view.displayBand) : ""}
                <div class="analysis-summary-foot">
                    <span>${escapeDecisionHtml(view.completenessLabel)}</span>
                </div>
            </article>
        `;
    }

    // Real, already-persisted weight/weighted fields (AnalysisDimensionDTO) —
    // never a client-side re-derivation of config weights, per "Why?"
    // contribution breakdown (owner audit #36).
    function dimensionContributionPct(dimensions) {
        const total = dimensions.reduce((sum, d) => {
            const w = Number(d.weighted);
            return sum + (Number.isFinite(w) ? w : 0);
        }, 0);
        return dimensions.map(d => {
            const w = Number(d.weighted);
            const pct = total > 0 && Number.isFinite(w) ? (w / total) * 100 : null;
            return Object.assign({}, d, { contributionPct: pct });
        });
    }

    function dimensionExplanationBody(dimension) {
        const contributions = Array.isArray(dimension.contributions) ? dimension.contributions : [];
        const explanation = sanitizeNumericText(dimension.explanation || "No component rationale recorded.");
        return `
            <div class="analysis-component-body">
                <p>${escapeDecisionHtml(explanation)}</p>
                ${contributions.length ? `
                    <div class="analysis-inputs">
                        <span>Recorded inputs</span>
                        <ul>
                    ${contributions.map(item => `
                        <li>${escapeDecisionHtml(sanitizeNumericText(item.description || item.source || "Recorded contribution"))}</li>
                    `).join("")}
                        </ul>
                    </div>
                ` : ""}
            </div>
        `;
    }

    function starRating(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return 0;
        return Math.max(1, Math.min(5, Math.round(n / 20)));
    }

    function starGlyphs(count) {
        return "★".repeat(count) + "☆".repeat(5 - count);
    }

    // Score contributors as storytelling (owner audit #7): ranked by actual
    // value, star rating plus the real contribution % from weight/weighted —
    // never a re-derived config-weight table client-side.
    function renderScoreContributors(dimensions) {
        const withPct = dimensionContributionPct(dimensions);
        // Sort by actual contribution (weight x value), not star rating —
        // a 4-star dimension worth 12% of the score must never rank above a
        // 3-star one worth 21% (owner-reported mismatch between order and %).
        const sorted = [...withPct].sort((a, b) => {
            const pa = a.contributionPct;
            const pb = b.contributionPct;
            if (pa === null && pb === null) return (Number(b.value) || -1) - (Number(a.value) || -1);
            if (pa === null) return 1;
            if (pb === null) return -1;
            return pb - pa;
        });
        return `<div class="analysis-component-list">${sorted.map(d => {
            const known = d.status === "OK";
            const stars = known ? starRating(d.value) : 0;
            const pctLabel = d.contributionPct !== null
                ? `${d.contributionPct.toFixed(0)}% of score`
                : "not counted";
            return `
                <details class="score-contributor-row">
                    <summary>
                        <span class="contributor-name">${escapeDecisionHtml(friendlyAnalysisName(d.name))}</span>
                        <span class="contributor-stars" aria-hidden="true">${known ? escapeDecisionHtml(starGlyphs(stars)) : "—"}</span>
                        <span class="contributor-pct">${escapeDecisionHtml(pctLabel)}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </summary>
                    ${dimensionExplanationBody(d)}
                </details>
            `;
        }).join("")}</div>`;
    }

    // "Why ATHENA trusts this" (owner audit #8) — a checklist, not a bar
    // chart. Trust/flag comes entirely from the backend's own persisted
    // level (LOW/MODERATE/HIGH), never a new client-side threshold.
    const CONFIDENCE_TRUST_LABELS = {
        evidence_completeness: "Evidence is complete",
        data_freshness: "Data is fresh",
        indicator_availability: "Indicators fully available",
        cross_engine_agreement: "Engines agree with each other",
        unknown_ratio: "No unknown or missing signals",
        consistency: "No conflicting signals",
    };

    function renderConfidenceChecklist(dimensions) {
        return `<div class="analysis-component-list">${dimensions.map(d => {
            const known = d.status === "OK";
            const level = String(d.level || "").toUpperCase();
            const trusted = known && level && !level.includes("LOW");
            const icon = !known ? "fa-circle-question unknown" : (trusted ? "fa-circle-check pass" : "fa-circle-xmark fail");
            const label = CONFIDENCE_TRUST_LABELS[d.name] || friendlyAnalysisName(d.name);
            return `
                <details class="trust-checklist-row">
                    <summary>
                        <i class="fa-solid ${icon}"></i>
                        <span class="contributor-name">${escapeDecisionHtml(label)}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </summary>
                    ${dimensionExplanationBody(d)}
                </details>
            `;
        }).join("")}</div>`;
    }

    // Major Risks (owner audit #9) — categorized by hazard, highest first.
    // Same 3-band Low/Medium/High scale as the Hero cockpit gauge, applied
    // per-dimension instead of only to the overall risk value.
    function renderRiskSummary(dimensions) {
        const sorted = [...dimensions].sort((a, b) => (Number(b.value) || -1) - (Number(a.value) || -1));
        return `<div class="analysis-component-list">${sorted.map(d => {
            const known = d.status === "OK";
            const band = known ? riskBand(d.value) : null;
            const tone = band === "High" ? "fail" : (band === "Medium" ? "warn" : "pass");
            return `
                <details class="risk-summary-row">
                    <summary>
                        <span class="contributor-name">${escapeDecisionHtml(friendlyAnalysisName(d.name))}</span>
                        <span class="risk-band-chip ${known ? tone : "unknown"}">${escapeDecisionHtml(band || "Unknown")}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </summary>
                    ${dimensionExplanationBody(d)}
                </details>
            `;
        }).join("")}</div>`;
    }

    function renderAnalysisBlock(label, block, tone) {
        const view = analysisPresentation(label, block, tone);
        const data = view.data;
        const dimensions = Array.isArray(data.dimensions) ? data.dimensions : [];
        const explanation = sanitizeNumericText(
            data.explanation || `No persisted ${label.toLowerCase()} explanation.`
        );
        const componentsHtml = !dimensions.length
            ? '<div class="analysis-no-components">No component detail was persisted.</div>'
            : (tone === "score" ? renderScoreContributors(dimensions)
                : tone === "confidence" ? renderConfidenceChecklist(dimensions)
                : renderRiskSummary(dimensions));
        return `
            <details class="analysis-detail-panel ${escapeDecisionHtml(tone)}">
                <summary>
                    <span class="analysis-detail-icon">
                        <i class="fa-solid ${escapeDecisionHtml(view.icon)}"></i>
                    </span>
                    <span class="analysis-detail-title">
                        <strong>${escapeDecisionHtml(label)} breakdown</strong>
                        <small>${dimensions.length} component${dimensions.length === 1 ? "" : "s"} · ${escapeDecisionHtml(view.guidance)}</small>
                    </span>
                    <span class="analysis-detail-value">${escapeDecisionHtml(view.valueLabel)}</span>
                    <i class="fa-solid fa-chevron-down analysis-detail-chevron"></i>
                </summary>
                <div class="analysis-detail-content">
                    <p class="analysis-detail-explanation">${escapeDecisionHtml(explanation)}</p>
                    ${componentsHtml}
                </div>
            </details>
        `;
    }

    // The action bar is static (wired once, not rebuilt per decision) so a
    // "Removed" state from a previous symbol must not leak onto the next one.
    function resetActionButtons() {
        const removeBtn = document.getElementById("decision-brief-remove-candidate");
        if (removeBtn) {
            removeBtn.disabled = false;
            const icon = removeBtn.querySelector("i");
            const label = removeBtn.querySelector("span");
            if (icon) icon.className = "fa-solid fa-list-check";
            if (label) label.textContent = "Remove candidate";
        }
    }

    // Sticky cockpit gauges reuse the exact same status/level/value already
    // computed for the Analysis tab's summary cards — never a second
    // client-derived score, just a different rendering of the same numbers.
    function resetCockpitGauges() {
        ["score", "confidence", "risk"].forEach(tone => {
            const valueEl = document.getElementById(`gauge-${tone}-value`);
            const bandEl = document.getElementById(`gauge-${tone}-band`);
            const barEl = document.getElementById(`gauge-${tone}-bar`);
            if (valueEl) valueEl.textContent = "—";
            if (bandEl) bandEl.textContent = "—";
            if (barEl) {
                barEl.style.width = "0%";
                barEl.style.background = "var(--text-muted)";
            }
        });
        const rrEl = document.getElementById("hero-rr-value");
        if (rrEl) rrEl.textContent = "—";
        const recommendationBandEl = document.getElementById("gauge-recommendation-band");
        if (recommendationBandEl) recommendationBandEl.textContent = "—";
    }

    function scoreBandColor(band) {
        if (band === "Excellent" || band === "Strong") return "var(--success)";
        if (band === "Good") return "var(--accent)";
        if (band === "Fair") return "var(--warning)";
        if (band === "Weak") return "var(--danger)";
        return "var(--text-muted)";
    }

    function gaugeToneColor(view, band = null) {
        if (view.status !== "OK") return "var(--text-muted)";
        if (view.tone === "score") return scoreBandColor(band || qualityBand(view.data.value));
        const level = String(view.level || "").toUpperCase();
        if (!level) return "var(--text-muted)";
        const highIsGood = view.tone !== "risk";
        if (level.includes("HIGH") || level.includes("STRONG")) {
            return highIsGood ? "var(--success)" : "var(--danger)";
        }
        if (level.includes("LOW") || level.includes("WEAK")) {
            return highIsGood ? "var(--danger)" : "var(--success)";
        }
        return "var(--warning)";
    }

    function renderCockpitGauges(depth) {
        [
            ["score", depth && depth.score],
            ["confidence", depth && depth.confidence],
            ["risk", depth && depth.risk],
        ].forEach(([tone, block]) => {
            const view = analysisPresentation(friendlyAnalysisName(tone), block, tone);
            const valueEl = document.getElementById(`gauge-${tone}-value`);
            const bandEl = document.getElementById(`gauge-${tone}-band`);
            const barEl = document.getElementById(`gauge-${tone}-bar`);
            // A block that isn't OK (UNKNOWN status) must never be banded as
            // a real "Weak" score — that's fabricating a value that was
            // never actually computed (owner-reported mismatch: banner said
            // 66.92, gauge said 0.0/Weak).
            const known = view.status === "OK";
            const band = known
                ? (tone === "risk" ? riskBand(view.data.value) : qualityBand(view.data.value))
                : null;
            const color = known ? gaugeToneColor(view, band) : "var(--text-muted)";
            if (valueEl) valueEl.textContent = known ? view.valueLabel : "—";
            if (bandEl) {
                bandEl.textContent = band || "Unknown";
                bandEl.style.color = color;
            }
            if (barEl) {
                barEl.style.width = known ? `${view.meterWidth}%` : "0%";
                barEl.style.background = color;
            }
            // Recommendation tile's qualifier ("Strong Setup") reuses the
            // Score tile's own already-computed band — never a second,
            // independently-derived word.
            if (tone === "score") {
                const recommendationBandEl = document.getElementById("gauge-recommendation-band");
                if (recommendationBandEl) {
                    recommendationBandEl.textContent = decisionHasHistoricalTradePlan(activeDecisionData, activePlanFreshness)
                        ? "Plan not current"
                        : (band ? `${band} Setup` : "—");
                }
            }
        });
        renderExecutiveSummary();
    }

    function renderDecisionDepth(depth) {
        renderEligibilityDepth(depth && depth.eligibility);
        renderCockpitGauges(depth);
        const host = document.getElementById("decision-analysis-depth");
        if (!host) return;
        const blocks = [
            ["Score", depth && depth.score, "score"],
            ["Confidence", depth && depth.confidence, "confidence"],
            ["Risk", depth && depth.risk, "risk"],
        ];
        // Progressive disclosure (owner UX audit #6): overview first, the
        // full component breakdown is a second click away — never all
        // three categories' worth of components dumped in one first look.
        host.innerHTML = `
            <div class="analysis-overview-grid">
                ${blocks.map(args => renderAnalysisSummaryCard(...args)).join("")}
            </div>
            <details class="analysis-detail-toggle">
                <summary>
                    <i class="fa-solid fa-list-ul"></i>
                    <span>View detailed breakdown</span>
                    <i class="fa-solid fa-chevron-down analysis-detail-toggle-chevron"></i>
                </summary>
                <div class="analysis-detail-stack">
                    ${blocks.map(args => renderAnalysisBlock(...args)).join("")}
                </div>
            </details>
        `;
    }

    // Five plain-English lines, composed entirely from strings the engines
    // already wrote (score/confidence/risk .explanation, gate results) —
    // never generated, per ADR-005. "Building summary..." until score depth
    // arrives; gates + suitability show immediately since they're synchronous.
    function buildExecutiveSummaryLines(decision, depth) {
        const lines = [];
        const gates = decision.analysis && Array.isArray(decision.analysis.gate_results)
            ? decision.analysis.gate_results
            : [];
        if (gates.length) {
            const failed = gates.filter(g => g && g.passed === false);
            lines.push(failed.length
                ? `Blocked on ${failed.length} of ${gates.length} safety gates: ${failed.map(g => friendlyGateName(g.gate)).join(", ")}.`
                : `Passed all ${gates.length} safety gates.`);
        }
        [["score", "Score"], ["confidence", "Confidence"], ["risk", "Risk"]].forEach(([key, label]) => {
            const block = depth && depth[key];
            if (block && block.status === "OK" && block.explanation) {
                lines.push(sanitizeNumericText(block.explanation));
            }
        });
        const suitability = {
            TRADE: decisionHasHistoricalTradePlan(decision)
                ? "Historical trade thesis only — current TradePlan is not actionable."
                : "All safety checks cleared — ready for entry.",
            WATCH: "Above the watch threshold, not yet ready to trade.",
            NO_TRADE: "Below the bar for a trade right now.",
            INSUFFICIENT_DATA: "Not enough data to assess yet.",
        }[String(decision.metadata.decision_type || "").toUpperCase()];
        if (suitability) lines.push(suitability);
        return lines;
    }

    function renderExecutiveSummary() {
        const host = document.getElementById("decision-executive-summary");
        if (!host || !activeDecisionData) return;
        const lines = buildExecutiveSummaryLines(activeDecisionData, activeDepth);
        if (!lines.length) {
            host.innerHTML = '<div class="decision-depth-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> Building summary…</div>';
            return;
        }
        host.innerHTML = `<ul class="executive-summary-list">${
            lines.map(l => `<li>${escapeDecisionHtml(l)}</li>`).join("")
        }</ul>`;
    }

    async function loadDecisionDepth(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/depth`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeDepth = response && response.data;
            renderDecisionDepth(activeDepth);
            refreshDagNodeMeanings();
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load decision depth for ${decisionId}`, err);
            renderDecisionDepth(null);
        }
    }
