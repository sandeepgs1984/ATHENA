

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

    // Market Context as cards, not just labels (owner UX audit #13).
    function contextMetricCard(name, value, tone) {
        return `
            <div class="context-metric">
                <span class="context-metric-label">${escapeDecisionHtml(name)}</span>
                <strong class="context-metric-value tone-${tone}-text">${escapeDecisionHtml(friendlyLabel(value))}</strong>
            </div>
        `;
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

        const regimeBlock = regime.status === "ASSESSED"
            ? `<div class="context-metric-grid">${(regime.labels || [])
                  .map(l => contextMetricCard(regimeLabelCategory(l), l, contextChipTone(l))).join("")}</div>
               <p class="context-caption">${escapeDecisionHtml(regime.explanation || "")}</p>`
            : '<p class="context-caption unknown">Not available yet — re-validate this decision to capture a regime assessment.</p>';

        const dimensions = mh.dimensions || {};
        const healthBlock = mh.status === "ASSESSED"
            ? `<div class="context-metric-grid">${Object.entries(dimensions)
                  .map(([key, label]) => contextMetricCard(friendlyLabel(key), label, contextChipTone(label))).join("")}</div>
               ${mh.explanation ? `<p class="context-caption">${escapeDecisionHtml(mh.explanation)}</p>` : ""}`
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
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-calendar-day"></i> Session</h5>
                <div class="context-chip-row">${sessionChips}</div>
                ${eventRows ? `<ul class="context-events-list">${eventRows}</ul>` : ""}
            </div>
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-chart-line"></i> Regime</h5>
                ${regimeBlock}
            </div>
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-heart-pulse"></i> Market health</h5>
                ${healthBlock}
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