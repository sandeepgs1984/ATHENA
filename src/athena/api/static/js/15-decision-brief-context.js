

    function friendlySessionType(type) {
        const map = {
            NORMAL: "Normal trading session",
            WEEKEND: "Weekend — market closed",
            HOLIDAY: "Exchange holiday",
            MUHURAT: "Muhurat / special session",
            SPECIAL: "Special session",
        };
        return map[type] || type || "Unknown";
    }

    function sessionChipTone(type) {
        if (type === "NORMAL") return "good";
        if (type === "HOLIDAY" || type === "WEEKEND") return "neutral";
        return "unknown";
    }

    // Best-effort category from the label text itself (already-real data,
    // just grouped for display) — matches the known regime label families;
    // falls back to a generic caption for any future label type.
    function regimeLabelCategory(label) {
        const l = String(label || "").toUpperCase();
        if (l.includes("VOLATILITY")) return "Volatility";
        if (l.includes("GAP")) return "Gap";
        if (l.includes("BREADTH")) return "Breadth";
        if (l.includes("TREND")) return "Trend";
        return "Regime";
    }

    // Market Context as cards, not just labels (owner UX audit #13). The
    // optional `explanation` is real per-dimension evidence text already
    // fetched alongside the label (RegimeEvidence/HealthEvidence.explanation,
    // e.g. "fast SMA(20)=... vs slow SMA(50)=..."), shown as a native title
    // tooltip — replaces the old composite sentence that just repeated the
    // same enum values already visible in the cards, in raw SNAKE_CASE.
    function contextMetricCard(name, value, tone, explanation) {
        return `
            <div class="context-metric"${explanation ? ` title="${escapeDecisionHtml(explanation)}"` : ""}>
                <span class="context-metric-label">${escapeDecisionHtml(name)}</span>
                <strong class="context-metric-value tone-${tone}-text">${escapeDecisionHtml(friendlyLabel(value))}</strong>
            </div>
        `;
    }

    function evidenceExplanationByDimension(evidence) {
        const map = {};
        (Array.isArray(evidence) ? evidence : []).forEach(item => {
            if (item && item.dimension) map[String(item.dimension).toLowerCase()] = item.explanation || "";
        });
        return map;
    }

    function renderDecisionContext(context) {
        const host = document.getElementById("decision-context-lane");
        if (!host) return;
        if (!context) {
            host.innerHTML = '<div class="decision-depth-loading">Context unavailable.</div>';
            return;
        }
        const cal = context.calendar || {};
        const regime = context.regime || { status: "UNKNOWN" };
        const mh = context.market_health || { status: "UNKNOWN" };
        const links = Array.isArray(context.external_links) ? context.external_links : [];

        const sessionChips = [
            contextChip(friendlySessionType(cal.session_type), sessionChipTone(cal.session_type)),
            cal.is_weekly_expiry ? contextChip("Weekly expiry", "warn") : "",
            cal.is_monthly_expiry ? contextChip("Monthly expiry", "warn") : "",
            cal.holiday_name ? contextChip(cal.holiday_name, "warn") : "",
        ].filter(Boolean).join("");

        const eventRows = (cal.events || []).map(ev => `
            <li><i class="fa-solid fa-star-of-life"></i>
                <strong>${escapeDecisionHtml(friendlyLabel(ev.kind || "Event"))}</strong>
                <span>${escapeDecisionHtml(ev.name || "")}</span></li>
        `).join("");

        const regimeEvidence = evidenceExplanationByDimension(regime.evidence);
        const regimeBlock = regime.status === "ASSESSED"
            ? `<div class="context-metric-grid context-metric-grid--cols-3">${(regime.labels || [])
                  .map(l => contextMetricCard(
                      regimeLabelCategory(l), l, contextChipTone(l),
                      regimeEvidence[regimeLabelCategory(l).toLowerCase()]
                  )).join("")}</div>`
            : '<p class="context-caption unknown">Not available yet — re-validate this decision to capture a regime assessment.</p>';

        const dimensions = mh.dimensions || {};
        const healthEvidence = evidenceExplanationByDimension(mh.evidence);
        const healthBlock = mh.status === "ASSESSED"
            ? `<div class="context-metric-grid">${Object.entries(dimensions)
                  .map(([key, label]) => contextMetricCard(
                      friendlyLabel(key), label, contextChipTone(label), healthEvidence[key.toLowerCase()]
                  )).join("")}</div>`
            : '<p class="context-caption unknown">Not available yet — re-validate this decision to capture a market-health assessment.</p>';

        const linkRows = links.length
            ? `<ul class="context-links-list">
                   ${links.map(l => `
                       <li><i class="fa-solid fa-arrow-up-right-from-square"></i>
                           <a href="${escapeDecisionHtml(l.url)}" target="_blank" rel="noopener noreferrer">
                               ${escapeDecisionHtml(l.title)}
                           </a>
                           <small>${escapeDecisionHtml(l.source)}</small>
                       </li>
                   `).join("")}
               </ul>`
            : '<p class="context-caption">No curated external links for this instrument.</p>';

        host.innerHTML = `
            <div class="context-session-bar">
                <span class="context-lane-label"><i class="fa-solid fa-calendar-day"></i> Session</span>
                <div class="context-chip-row">${sessionChips}</div>
                ${eventRows ? `<ul class="context-events-list">${eventRows}</ul>` : ""}
            </div>
            <div class="context-analytics-row">
                <div class="context-lane-block">
                    <h5><i class="fa-solid fa-chart-line"></i> Regime</h5>
                    ${regimeBlock}
                </div>
                <div class="context-lane-block">
                    <h5><i class="fa-solid fa-heart-pulse"></i> Market health</h5>
                    ${healthBlock}
                </div>
            </div>
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-link"></i> External research</h5>
                ${linkRows}
            </div>
        `;
    }

    async function loadDecisionContext(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/context`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeContextData = response && response.data;
            renderDecisionContext(activeContextData);
            refreshDagNodeMeanings();
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load decision context for ${decisionId}`, err);
            renderDecisionContext(null);
        }
    }