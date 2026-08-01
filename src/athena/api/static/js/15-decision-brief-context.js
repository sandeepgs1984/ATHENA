

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

    // IX-5: plain sign comparison of two already-real numbers — no magnitude
    // threshold, no new numeric constant, never fabricated when either side
    // is unavailable.
    function indexBackdropAlignment(stockChangePct, indexChangePct) {
        if (!Number.isFinite(stockChangePct) || !Number.isFinite(indexChangePct)) return null;
        if (stockChangePct === 0 || indexChangePct === 0) {
            return { label: "Flat move", tone: "neutral" };
        }
        const sameDirection = (stockChangePct > 0) === (indexChangePct > 0);
        return sameDirection
            ? { label: "With index", tone: "good" }
            : { label: "Against index", tone: "warn" };
    }

    function renderIndexBackdrop(data, options = {}) {
        const host = document.getElementById("decision-index-backdrop-lane");
        if (!host) return;
        if (options.failed) {
            host.innerHTML = '<p class="context-caption unknown">Index backdrop unavailable — check your connection and retry.</p>';
            return;
        }
        const memberships = data && Array.isArray(data.memberships) ? data.memberships : [];
        if (memberships.length === 0) {
            host.innerHTML = '<p class="context-caption">No official index membership found for this symbol.</p>';
            return;
        }
        const stockChangePct = activeBriefQuote && activeBriefQuote.change_pct != null
            ? Number(activeBriefQuote.change_pct)
            : NaN;
        const rows = memberships.map(item => {
            const indexChangePct = item && item.change_pct != null ? Number(item.change_pct) : NaN;
            const alignment = indexBackdropAlignment(stockChangePct, indexChangePct);
            const alignmentMarkup = alignment
                ? contextChip(alignment.label, alignment.tone)
                : '<span class="context-caption">Alignment unavailable — live quote or index change missing.</span>';
            return `
                <div class="index-backdrop-row">
                    ${indexObservationMarkup(item)}
                    ${alignmentMarkup}
                </div>
            `;
        }).join("");
        host.innerHTML = `<div class="index-backdrop-list">${rows}</div>`;
    }

    async function loadIndexBackdrop(rawSymbol, decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/market/instruments/${encodeURIComponent(rawSymbol)}/index-backdrop`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            renderIndexBackdrop(response && response.data);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load index backdrop for ${rawSymbol}`, err);
            renderIndexBackdrop(null, { failed: true });
        }
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