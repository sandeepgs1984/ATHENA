
    const SI_HOLDING_GUIDANCE = new Set([
        "HOLD_STRONG", "HOLD", "REVIEW_HOLD_TIGHT",
    ]);
    let siBundle = null;
    let siQuery = "";
    let siSearchTimer = null;
    let siLoadGeneration = 0;
    let siChartOutsidePointerHandler = null;
    let siInFlightController = null;
    let siInFlightMode = "";
    let siInFlightQuery = "";

    function siNormalizedQuery(value) {
        return String(value || "").trim();
    }

    function siSameQuery(left, right) {
        return siNormalizedQuery(left) === siNormalizedQuery(right);
    }

    function siShouldSuppressAnalyze(query) {
        return siInFlightMode === "ANALYZE" && siSameQuery(query, siInFlightQuery);
    }

    function siEscape(value) {
        return String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
    }

    function siText(value, fallback = "—") {
        if (value === null || value === undefined || value === "") return fallback;
        return siEscape(value);
    }

    function siFiniteNumber(value) {
        const amount = Number(value);
        return Number.isFinite(amount) ? amount : null;
    }

    function siMoney(value) {
        if (value === null || value === undefined || value === "") return "—";
        const amount = siFiniteNumber(value);
        if (amount == null) return siEscape(value);
        const formatted = Math.abs(amount).toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return amount < 0 ? `-₹${formatted}` : `₹${formatted}`;
    }

    function siInteger(value) {
        if (value === null || value === undefined || value === "") return "—";
        const amount = siFiniteNumber(value);
        if (amount == null) return siEscape(value);
        return Math.round(amount).toLocaleString("en-IN");
    }

    function siRsi(value) {
        const amount = siFiniteNumber(value);
        if (amount == null) return "—";
        return amount.toFixed(1);
    }

    function siScore(value) {
        const amount = siFiniteNumber(value);
        if (amount == null) return "—";
        return amount.toFixed(1);
    }

    function siPct(value) {
        if (value === null || value === undefined || value === "") return "";
        const amount = siFiniteNumber(value);
        if (amount == null) return "";
        const sign = amount > 0 ? "+" : "";
        return `${sign}${amount.toFixed(2)}%`;
    }

    function siEnumLabel(value, fallback = "—") {
        if (value === null || value === undefined || value === "") return fallback;
        return String(value)
            .replace(/_/g, " ")
            .toLowerCase()
            .replace(/\b\w/g, char => char.toUpperCase());
    }

    function siDisplayExplanation(text) {
        if (!text) return "";
        return String(text)
            .replace(/\bscore\s+(\d+(?:\.\d+)?)\/100/gi, (_, number) => (
                `Score ${Number(number).toFixed(1)} / 100`
            ))
            .replace(/\bwatch level \((\d+(?:\.\d+)?)\)/gi, (_, number) => (
                `watch level (${Number(number).toFixed(1)})`
            ));
    }

    function siZoneShort(zone) {
        if (!zone) return "—";
        const lower = siFiniteNumber(zone.lower);
        const upper = siFiniteNumber(zone.upper);
        if (lower == null && upper == null) return "—";
        if (lower == null) return siMoney(upper);
        if (upper == null) return siMoney(lower);
        if (lower.toFixed(2) === upper.toFixed(2)) return siMoney(lower);
        return `${siMoney(lower)} – ${siMoney(upper)}`;
    }

    function siDate(value) {
        if (!value) return "—";
        const text = String(value);
        return siEscape(text.slice(0, 10));
    }

    function siDecisionDate(value) {
        if (!value) return "—";
        const key = String(value).slice(0, 10);
        const date = new Date(`${key}T12:00:00+05:30`);
        if (Number.isNaN(date.getTime())) return siEscape(key);
        return siEscape(new Intl.DateTimeFormat("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "numeric",
            month: "short",
            year: "numeric",
        }).format(date));
    }

    function siNormalizeLabel(value) {
        return String(value || "").trim().toUpperCase().replace(/[\s.\-_/:]/g, "");
    }

    function siCompanyName(identity) {
        const name = String((identity && identity.name) || "").trim();
        if (!name) return "";
        const symbol = String((identity && identity.symbol) || "").trim();
        const instrument = String((identity && identity.instrument_id) || "").trim();
        const normalizedName = siNormalizeLabel(name);
        if (symbol && normalizedName === siNormalizeLabel(symbol)) return "";
        if (instrument && normalizedName === siNormalizeLabel(instrument)) return "";
        const instrumentTail = instrument.includes(":") ? instrument.split(":").pop() : instrument;
        if (instrumentTail && normalizedName === siNormalizeLabel(instrumentTail)) return "";
        return name;
    }

    function siPriceMapRelation(signedDelta, denominator) {
        const delta = siFiniteNumber(signedDelta);
        const den = siFiniteNumber(denominator);
        if (delta == null || den == null || den === 0) return null;
        const pct = (delta / den) * 100;
        const magnitude = Math.abs(pct).toFixed(1);
        if (Number(magnitude) === 0) return { magnitude, direction: "at" };
        return { magnitude, direction: pct > 0 ? "above" : "below" };
    }

    function siCloseVsBoundary(close, boundary) {
        const closeN = siFiniteNumber(close);
        const boundaryN = siFiniteNumber(boundary);
        if (closeN == null || boundaryN == null || closeN === 0 || boundaryN === 0) return null;
        return siPriceMapRelation(closeN - boundaryN, boundaryN);
    }

    function siLevelVsClose(level, close) {
        const closeN = siFiniteNumber(close);
        const levelN = siFiniteNumber(level);
        if (closeN == null || levelN == null || closeN === 0 || levelN === 0) return null;
        return siPriceMapRelation(levelN - closeN, closeN);
    }

    function siCloseVsBoundarySentence(label, close, boundary) {
        const rel = siCloseVsBoundary(close, boundary);
        if (!rel) return "";
        if (rel.direction === "at") {
            return `Completed D1 is at ${label} upper boundary.`;
        }
        return `Completed D1 is ${rel.magnitude}% ${rel.direction} ${label} upper boundary.`;
    }

    function siLevelVsCloseSentence(label, level, close) {
        const rel = siLevelVsClose(level, close);
        if (!rel) return "";
        if (rel.direction === "at") {
            return `${label} is at completed-D1 close.`;
        }
        return `${label} is ${rel.magnitude}% ${rel.direction} completed-D1 close.`;
    }

    function siJumpButton(section, label, icon) {
        const iconHtml = icon ? `<i class="fas ${icon}" aria-hidden="true"></i> ` : "";
        return `<button type="button" class="si-jump" data-si-jump="${siEscape(section)}">${iconHtml}${siEscape(label)}</button>`;
    }

    function siPersistedScore(decision) {
        const value = decision && decision.depth && decision.depth.score && decision.depth.score.value;
        return siFiniteNumber(value);
    }

    function siGatePassSummary(decision) {
        const gates = (decision && decision.gates) || [];
        if (!gates.length) return "";
        const passed = gates.filter(gate => gate && gate.passed === true).length;
        return `${passed} of ${gates.length} gates passed`;
    }

    function showSiSection(sectionId) {
        document.querySelectorAll("#tab-symbol-intelligence [data-si-panel]").forEach(panel => {
            panel.hidden = panel.getAttribute("data-si-panel") !== sectionId;
        });
        document.querySelectorAll(".si-section-nav-item").forEach(item => {
            item.classList.toggle("active", item.getAttribute("data-si-section") === sectionId);
        });
    }

    function siZoneLooksEmpty(zone) {
        if (!zone) return true;
        const lower = zone.lower;
        const upper = zone.upper;
        return (lower == null || lower === "") && (upper == null || upper === "");
    }

    function siMarketDataStatus(bundle) {
        const d1 = (bundle.sources || []).find(src => src.source === "D1_CANDLES");
        return siText(d1 && d1.status, "UNAVAILABLE");
    }

    function siCoverageStatus(bundle) {
        return siText(bundle.overall_freshness && bundle.overall_freshness.status, "UNAVAILABLE");
    }

    function siCoverageReason(bundle) {
        return siText(bundle.overall_freshness && bundle.overall_freshness.explanation, "");
    }

    function siQuoteCaption(live) {
        if (live && live.present) {
            if (live.label) return siText(live.label);
            if (live.quote_kind === "LIVE" || live.market_state === "MARKET OPEN") {
                return "LIVE · MARKET OPEN";
            }
            return "LATEST QUOTE · MARKET CLOSED";
        }
        const market = (live && (live.market_state || live.label)) || "";
        return market ? `LAST COMPLETED D1 · ${siEscape(market)}` : "LAST COMPLETED D1";
    }

    function siSmaStructureLabel(value) {
        const raw = String(value || "");
        if (raw === "UPTREND") return "Up";
        if (raw === "DOWNTREND") return "Down";
        if (raw === "SIDEWAYS") return "Sideways";
        if (raw === "MIXED") return "Mixed";
        return raw || "—";
    }

    function siSuperTrendLabel(value) {
        const raw = String(value || "");
        if (raw === "BULLISH") return "Up";
        if (raw === "BEARISH") return "Down";
        return raw || "—";
    }

    function siVolumeVsMa20(d1) {
        if (!d1 || d1.volume_ma20 == null || d1.volume == null) return "—";
        return Number(d1.volume) >= Number(d1.volume_ma20) ? "Above MA20" : "Below MA20";
    }

    function siSyncAnalyzeControl() {
        const btn = document.getElementById("si-load-btn");
        const input = document.getElementById("si-symbol-input");
        const typed = input ? siNormalizedQuery(input.value) : "";
        const duplicateAnalyze = siInFlightMode === "ANALYZE" && siSameQuery(typed, siInFlightQuery);
        const analyzeInFlight = siInFlightMode === "ANALYZE";
        const loadInFlight = Boolean(siInFlightMode);
        if (btn) {
            btn.disabled = duplicateAnalyze;
            const label = btn.querySelector(".si-btn-label");
            if (label) label.textContent = analyzeInFlight ? "Analyzing…" : "Analyze";
            btn.setAttribute("aria-busy", analyzeInFlight ? "true" : "false");
        }
        const refreshBtn = document.getElementById("si-refresh-btn");
        const clearBtn = document.getElementById("si-clear-btn");
        const hasSymbol = Boolean(siBundle || siQuery);
        if (refreshBtn) refreshBtn.disabled = loadInFlight || !hasSymbol;
        if (clearBtn) clearBtn.disabled = loadInFlight || !hasSymbol;
        const overlay = document.getElementById("si-analyze-overlay");
        overlay?.classList.toggle("active", loadInFlight);
        overlay?.setAttribute("aria-hidden", loadInFlight ? "false" : "true");
        document.body.classList.toggle("si-analyze-blocked", loadInFlight);
        const overlayText = document.getElementById("si-analyze-overlay-text");
        if (overlayText && loadInFlight) {
            overlayText.textContent = analyzeInFlight
                ? "Analyzing Symbol Intelligence"
                : "Loading Symbol Intelligence";
        }
        const detail = document.getElementById("si-analyze-overlay-detail");
        if (detail && loadInFlight) {
            const action = analyzeInFlight
                ? "Refreshing completed-D1 evidence"
                : "Loading persisted evidence";
            detail.textContent = siInFlightQuery
                ? `${action} for ${siInFlightQuery}…`
                : `${action}…`;
        }
    }

    function siSetInFlight(mode, query) {
        siInFlightMode = mode || "";
        siInFlightQuery = siInFlightMode ? siNormalizedQuery(query) : "";
        siSyncAnalyzeControl();
    }

    function siDecisionChipClass(decisionType) {
        const type = String(decisionType || "").toLowerCase();
        if (type === "trade" || type === "watch" || type === "no_trade") return `type-chip type-${type}`;
        return "type-chip";
    }

    // Real-derived: chosen from the persisted identity.sector string. Never a
    // per-company logo -- no such field exists anywhere in the backend.
    function siSectorIcon(sector) {
        const s = String(sector || "").toLowerCase();
        if (/energy|power|solar|renewable/.test(s)) return "fa-bolt";
        if (/\bit\b|software|technology|tech/.test(s)) return "fa-microchip";
        if (/bank|financ|insur|nbfc/.test(s)) return "fa-landmark";
        if (/pharma|health|hospital/.test(s)) return "fa-pills";
        if (/fmcg|consumer|retail/.test(s)) return "fa-bag-shopping";
        if (/auto|vehicle/.test(s)) return "fa-car";
        if (/metal|material|mining|steel|cement/.test(s)) return "fa-industry";
        if (/infra|construction|real estate|realty/.test(s)) return "fa-building";
        return "fa-chart-simple";
    }

    function siSignedMoney(value) {
        const amount = siFiniteNumber(value);
        if (amount == null) return "";
        const abs = Math.abs(amount).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        if (amount > 0) return `+₹${abs}`;
        if (amount < 0) return `-₹${abs}`;
        return `₹${abs}`;
    }

    // Real-derived: last_price - previous_close, both persisted live-quote fields.
    function siAbsChange(live) {
        if (!live || !live.present) return null;
        const last = siFiniteNumber(live.last_price);
        const prev = siFiniteNumber(live.previous_close);
        if (last == null || prev == null) return null;
        return last - prev;
    }

    function siPriceChangeBadge(live) {
        if (!live || !live.present) return "";
        const pct = siPct(live.change_pct);
        const abs = siAbsChange(live);
        const text = [abs != null ? siSignedMoney(abs) : "", pct ? `(${pct})` : ""].filter(Boolean).join(" ");
        if (!text) return "";
        const signal = abs != null ? abs : Number(live.change_pct);
        const cls = signal > 0 ? "up" : signal < 0 ? "down" : "";
        return `<span class="si-id-change ${cls}">${siEscape(text)}</span>`;
    }

    function siHeader(bundle) {
        const identity = bundle.identity || {};
        const d1 = bundle.d1 || {};
        const live = bundle.live || {};
        const decision = bundle.decision || {};
        const price = live.present ? live.last_price : d1.close;
        const company = siCompanyName(identity);
        const decisionChip = decision.present
            ? `<span class="${siDecisionChipClass(decision.decision_type)}">${siEscape(siEnumLabel(decision.decision_type))}</span>`
            : "";
        const sector = siText(identity.sector, "");
        return `<div class="si-id-block">
                <div class="si-id-avatar" aria-hidden="true"><i class="fas ${siSectorIcon(identity.sector)}"></i></div>
                <div class="si-id-block-text">
                    <div class="si-id-symbol-row">
                        <span class="si-id-symbol">${siText(identity.symbol || identity.instrument_id, identity.query || "Unresolved")}</span>
                        ${decisionChip}
                    </div>
                    ${company ? `<div class="si-id-name">${siText(company, "")}</div>` : ""}
                    <div class="si-id-tags">
                        <span class="si-id-meta-tag">${siText(identity.exchange, "")}${identity.instrument_id ? ` · ${siText(identity.instrument_id)}` : ""}</span>
                        ${sector ? `<span class="si-id-meta-tag">${sector}</span>` : ""}
                        <span class="si-id-meta-tag si-id-tag-placeholder" data-si-placeholder="true" title="Market-cap classification is not yet available from ATHENA's persisted data -- shown as a placeholder for a future field, never a guessed value.">Cap tier — pending</span>
                    </div>
                </div>
            </div>
            <div>
                <div class="si-id-price-row">
                    <span class="si-id-price">${siMoney(price)}</span>
                    ${siPriceChangeBadge(live)}
                </div>
                <span class="si-id-quote-tag">${siQuoteCaption(live)}</span>
            </div>
            <div>
                <div class="si-id-session"><span>Completed D1 as-of</span><strong>${siDate(d1.latest_session)}</strong></div>
                <div class="si-id-session"><span>Last completed close</span><strong>${siMoney(d1.close)}</strong></div>
                ${identity.resolved ? "" : `<p class="si-unavailable">${siText(identity.unresolved_reason)}</p>`}
            </div>
            <div class="si-id-decorative" data-si-placeholder="true" aria-hidden="true">
                <div class="si-id-decorative-art"></div>
                <p class="si-id-decorative-line">Evidence-led.<br>Always explainable.</p>
            </div>`;
    }

    function siCoverageBanner(bundle) {
        const market = siMarketDataStatus(bundle);
        const coverage = siCoverageStatus(bundle);
        const decision = bundle.decision || {};
        let tone = "neutral";
        let message = siCoverageReason(bundle);
        if (coverage === "PARTIAL" && market === "CURRENT") {
            tone = "partial";
            message = "This stock can still be researched from current market evidence. ATHENA has not produced a Decision.";
        } else if (coverage === "READY") {
            tone = "ready";
            message = message || "Market data is current and an ATHENA Decision is available.";
        } else if (market === "STALE" || coverage === "STALE") {
            tone = "stale";
            message = message || "Completed D1 history is stale. Press Analyze to hydrate this symbol.";
        } else if (coverage === "UNAVAILABLE" || market === "UNAVAILABLE") {
            tone = "unavailable";
            if (bundle.identity && bundle.identity.resolved === false) {
                message = "";
            } else {
                message = message || "Symbol Intelligence is unavailable for this symbol.";
            }
        }
        const decisionLine = decision.present
            ? ""
            : "<div>ATHENA Decision unavailable</div>";
        return `<div class="si-coverage-banner tone-${tone}" data-si-coverage="${siEscape(coverage)}" data-si-market="${siEscape(market)}">
            <div class="si-coverage-facts">
                <div>Market data · ${siEscape(market)}</div>
                <div>SI coverage · ${siEscape(coverage)}</div>
                ${decisionLine}
            </div>
            ${message ? `<p class="si-coverage-note">${siEscape(message)}</p>` : ""}
        </div>`;
    }

    function siTile(label, value, tone) {
        return `<div class="si-tile${tone ? ` ${tone}` : ""}"><dt>${siEscape(label)}</dt><dd>${siText(value)}</dd></div>`;
    }

    function siPortfolioCard(portfolio) {
        if (!portfolio || portfolio.status === "NOT_HELD") {
            return `<div class="si-card"><h3>Portfolio Context</h3>
                <p class="si-empty">Not held in My Portfolio</p></div>`;
        }
        const banned = [portfolio.interpretation_status, portfolio.next_action, portfolio.daily_review_status]
            .filter(value => SI_HOLDING_GUIDANCE.has(String(value || "")));
        const interpretation = banned.length
            ? `Held. Portfolio-owned status ${siText(portfolio.interpretation_status)}.`
            : `${siText(portfolio.interpretation_status)} · ${siText(portfolio.next_action)}`;
        const statusRaw = String(portfolio.interpretation_status || "");
        const statusBanned = SI_HOLDING_GUIDANCE.has(statusRaw);
        const pillText = !statusBanned && statusRaw ? `Held &amp; ${siEscape(siEnumLabel(statusRaw))}` : "Held";
        const pnlAmount = siFiniteNumber(portfolio.pnl);
        const pnlTone = pnlAmount == null ? "" : pnlAmount >= 0 ? "is-good" : "is-bad";
        const pnlText = `${siMoney(portfolio.pnl)}${siPct(portfolio.pnl_pct) ? ` (${siEscape(siPct(portfolio.pnl_pct))})` : ""}`;
        return `<div class="si-card">
            <h3>Portfolio Context <span class="si-portfolio-status-pill">${pillText}</span></h3>
            <p class="si-pending">These facts are Portfolio-owned. Symbol Intelligence does not issue BUY/HOLD/SELL.</p>
            <div class="si-portfolio-tiles">
                ${siTile("Quantity", siInteger(portfolio.quantity))}
                ${siTile("Average price", siMoney(portfolio.avg_price))}
                ${siTile("Last price", siMoney(portfolio.last_price))}
                ${siTile("Investment", siMoney(portfolio.investment))}
                ${siTile("Current value", siMoney(portfolio.current_value))}
                ${siTile("P&L", pnlText, `si-pnl ${pnlTone}`)}
            </div>
            <div class="si-portfolio-callout">
                <i class="fas fa-circle-info" aria-hidden="true"></i>
                <p>${siEscape(interpretation)}</p>
            </div>
        </div>`;
    }

    function siDecisionSource(bundle) {
        return ((bundle && bundle.sources) || []).find(source => (
            source && source.source === "ATHENA_DECISION"
        )) || null;
    }

    function siDecisionTone(decisionType) {
        const type = String(decisionType || "").toUpperCase();
        if (type === "TRADE") return "trade";
        if (type === "WATCH") return "watch";
        if (type === "NO_TRADE") return "pass";
        return "neutral";
    }

    function siDecisionGateLabel(value) {
        const labels = {
            DATA: "Data quality",
            EVIDENCE: "Evidence quality",
            RISK: "Risk quality",
            EXPLAINABILITY: "Explainability",
            CONFIDENCE: "Confidence quality",
            MARKET: "Market quality",
        };
        return labels[String(value || "").toUpperCase()] || siEnumLabel(value, "Quality check");
    }

    function siDecisionGateRows(decision) {
        const gates = Array.isArray(decision && decision.gates) ? decision.gates : [];
        if (!gates.length) {
            return `<p class="si-decision-muted">No gate results were persisted for this Decision.</p>`;
        }
        return `<div class="si-decision-gates">${gates.map(gate => {
            const passed = gate && gate.passed === true;
            const detail = gate && gate.detail
                ? siText(gate.detail)
                : "No persisted detail is available.";
            return `<details class="si-decision-gate ${passed ? "is-pass" : "is-fail"}" ${passed ? "" : "open"}>
                <summary>
                    <span class="si-decision-gate-state" aria-hidden="true"></span>
                    <span class="si-decision-gate-name">${siEscape(siDecisionGateLabel(gate && gate.gate))}</span>
                    <strong>${passed ? "Passed" : "Failed"}</strong>
                    <span class="si-decision-disclosure" aria-hidden="true">⌄</span>
                </summary>
                <p>${detail}</p>
            </details>`;
        }).join("")}</div>`;
    }

    function siDecisionPlanMetric(label, value, formatter = siText) {
        if (value === null || value === undefined || value === "") return "";
        return `<div class="si-decision-plan-metric"><dt>${siEscape(label)}</dt><dd>${formatter(value)}</dd></div>`;
    }

    function siDecisionTradePlan(decision) {
        const plan = decision && decision.trade_plan;
        if (!plan) {
            return `<section class="si-decision-block si-decision-plan" aria-labelledby="si-decision-plan-title">
                <div class="si-decision-block-head">
                    <div><span class="si-decision-eyebrow">Decision-owned levels</span>
                    <h3 id="si-decision-plan-title">Persisted TradePlan</h3></div>
                </div>
                <p class="si-decision-empty-plan">No persisted trade plan for this Decision.</p>
            </section>`;
        }
        const targets = (Array.isArray(plan.targets) ? plan.targets : [])
            .filter(value => value !== null && value !== undefined && value !== "")
            .map((value, index) => siDecisionPlanMetric(`Target ${index + 1}`, value, siMoney))
            .join("");
        const freshness = decision.plan_freshness || {};
        const entryLow = plan.entry_low;
        const entryHigh = plan.entry_high;
        const entry = entryLow !== null && entryLow !== undefined
            && entryHigh !== null && entryHigh !== undefined
            ? (Number(entryLow) === Number(entryHigh)
                ? siMoney(entryLow)
                : `${siMoney(entryLow)} – ${siMoney(entryHigh)}`)
            : "";
        const rr = siFiniteNumber(plan.risk_reward);
        return `<section class="si-decision-block si-decision-plan" aria-labelledby="si-decision-plan-title">
            <div class="si-decision-block-head">
                <div><span class="si-decision-eyebrow">Decision-owned levels</span>
                <h3 id="si-decision-plan-title">Persisted TradePlan</h3></div>
                ${freshness.status ? `<span class="si-decision-status plan-${siEscape(String(freshness.status).toLowerCase())}">${siEscape(siEnumLabel(freshness.status))}</span>` : ""}
            </div>
            <dl class="si-decision-plan-grid">
                ${entry ? `<div class="si-decision-plan-metric is-primary"><dt>Entry band</dt><dd>${entry}</dd></div>` : ""}
                ${siDecisionPlanMetric("Stop loss", plan.stop_loss, siMoney)}
                ${targets}
                ${rr != null ? `<div class="si-decision-plan-metric"><dt>Risk / reward</dt><dd>${siEscape(rr.toFixed(2))} : 1</dd></div>` : ""}
                ${siDecisionPlanMetric("Position size", plan.position_size, siInteger)}
                ${siDecisionPlanMetric("Risk amount", plan.risk_amount, siMoney)}
                ${siDecisionPlanMetric("Valid from", plan.valid_from, siDecisionDate)}
                ${siDecisionPlanMetric("Valid until", plan.valid_until, siDecisionDate)}
            </dl>
            ${freshness.summary ? `<p class="si-decision-plan-note">${siText(freshness.summary)}</p>` : ""}
        </section>`;
    }

    function siDecisionCard(bundle) {
        const identity = (bundle && bundle.identity) || {};
        const decision = (bundle && bundle.decision) || {};
        if (!identity.resolved) {
            return `<div class="si-card si-decision-empty-state">
                <span class="si-decision-eyebrow">ATHENA Decision</span>
                <h2>Symbol unavailable</h2>
                <p>Resolve a valid instrument before inspecting persisted Decision evidence.</p>
            </div>`;
        }
        if (!decision.present) {
            return `<div class="si-card si-decision-empty-state">
                <span class="si-decision-eyebrow">ATHENA Decision</span>
                <h2>No persisted decision</h2>
                <p>ATHENA has not produced a Decision for this symbol. SI research remains available in Stock 360.</p>
                <div class="si-actions">
                    ${siJumpButton("stock-360", "Back to Stock 360")}
                    ${siJumpButton("audit", "View Evidence")}
                </div>
            </div>`;
        }

        const openHref = `/dashboard/decisions?decision=${encodeURIComponent(decision.decision_id)}`;
        const score = siPersistedScore(decision);
        const gates = Array.isArray(decision.gates) ? decision.gates : [];
        const passed = gates.filter(gate => gate && gate.passed === true).length;
        const failed = gates.filter(gate => gate && gate.passed === false).length;
        const gateSummary = gates.length
            ? `${passed} of ${gates.length} gates passed`
            : "Gate evidence unavailable";
        const decisionSource = siDecisionSource(bundle);
        const decisionFreshness = decisionSource && decisionSource.status
            ? String(decisionSource.status).toUpperCase()
            : "UNAVAILABLE";
        const marketStatus = siMarketDataStatus(bundle);
        const direction = String(decision.direction || "").toUpperCase();
        const tone = siDecisionTone(decision.decision_type);
        return `<div class="si-decision-experience tone-${tone}">
            <header class="si-decision-hero">
                <div class="si-decision-hero-main">
                    <span class="si-decision-eyebrow">Persisted ATHENA Decision</span>
                    <div class="si-decision-title-row">
                        <h2>${siEscape(siEnumLabel(decision.decision_type, "Decision"))}</h2>
                        ${direction && direction !== "NONE" ? `<span class="si-decision-direction">${siEscape(siEnumLabel(direction))}</span>` : ""}
                    </div>
                    <p class="si-decision-asof">Decision as of ${siDecisionDate(decision.ts)}</p>
                </div>
                <span class="si-decision-status decision-${siEscape(decisionFreshness.toLowerCase())}">${siEscape(siEnumLabel(decisionFreshness))}</span>
            </header>

            ${(decisionFreshness === "STALE" || marketStatus === "STALE") ? `<div class="si-decision-warning" role="status">
                ${decisionFreshness === "STALE" ? `<p><strong>Decision is stale.</strong> ${siText(decisionSource && decisionSource.explanation)}</p>` : ""}
                ${marketStatus === "STALE" ? `<p><strong>Completed-D1 evidence is stale.</strong> The persisted Decision remains visible as historical evidence.</p>` : ""}
            </div>` : ""}

            <div class="si-decision-strength" aria-label="Persisted Decision strength">
                ${decision.confidence_level ? `<div><span>Confidence</span><strong>${siEscape(siEnumLabel(decision.confidence_level))}</strong></div>` : ""}
                ${score != null ? `<div><span>Persisted score</span><strong>${siEscape(siScore(score))}<small> / 100</small></strong></div>` : ""}
                <div><span>Safety checks</span><strong>${siEscape(gateSummary)}</strong></div>
            </div>

            <div class="si-decision-layout">
                <section class="si-decision-block si-decision-why" aria-labelledby="si-decision-why-title">
                    <div class="si-decision-block-head">
                        <div><span class="si-decision-eyebrow">Persisted explanation</span>
                        <h3 id="si-decision-why-title">Why ATHENA decided this</h3></div>
                        ${gates.length ? `<span class="si-decision-gate-summary ${failed ? "has-failures" : "all-passed"}">${failed ? `${failed} failed` : "All passed"}</span>` : ""}
                    </div>
                    <p class="si-decision-explanation">${siText(siDisplayExplanation(decision.explanation), "No persisted explanation is available.")}</p>
                    ${siDecisionGateRows(decision)}
                </section>
                ${siDecisionTradePlan(decision)}
            </div>

            <footer class="si-decision-footer">
                <p>Deep analytical trace and provenance remain in the authoritative Decision Brief.</p>
                <div class="si-actions">
                    <a class="btn si-decision-primary-action" href="${siEscape(openHref)}">Open Decision Brief</a>
                    ${siJumpButton("audit", "View Evidence")}
                </div>
            </footer>
        </div>`;
    }

    function siViewTone(decisionType) {
        const type = String(decisionType || "").toLowerCase();
        return ["trade", "watch", "no_trade"].includes(type) ? type : "neutral";
    }

    function siAthenaView(decision) {
        if (!decision || !decision.present) {
            return `<div class="si-card si-athena-view"><h3>ATHENA View</h3>
                <p class="si-empty">ATHENA Decision not available for this symbol</p>
                <p class="si-pending">Stock 360 research remains available. This is not an Analyze failure.</p>
                <p class="si-actions">
                    ${siJumpButton("decision", "Open ATHENA Decision", "fa-brain")}
                    ${siJumpButton("audit", "View evidence", "fa-clipboard-check")}
                </p></div>`;
        }
        const openHref = `/dashboard/decisions?decision=${encodeURIComponent(decision.decision_id)}`;
        const score = siPersistedScore(decision);
        const gates = Array.isArray(decision.gates) ? decision.gates : [];
        const passed = gates.filter(gate => gate && gate.passed === true).length;
        const gateDots = gates.length
            ? `<div class="si-view-gates" aria-label="${passed} of ${gates.length} gates passed">
                ${gates.map(gate => `<span class="si-view-gate-dot${gate && gate.passed === true ? " is-passed" : ""}"></span>`).join("")}
            </div>`
            : "";
        const clampedScore = score != null ? Math.max(0, Math.min(100, score)) : null;
        return `<div class="si-card si-athena-view tone-${siViewTone(decision.decision_type)}"><h3>ATHENA View</h3>
            <div class="si-view-head">
                <span class="si-view-decision">${siEscape(siEnumLabel(decision.decision_type))}</span>
                <span class="si-view-asof">As of ${siDate(decision.ts)}</span>
            </div>
            <div class="si-view-strength">
                ${decision.confidence_level ? siViewStatTile("fa-shield-halved", "Confidence", siEnumLabel(decision.confidence_level)) : ""}
                ${decision.plan_freshness && decision.plan_freshness.status ? siViewStatTile("fa-calendar-check", "Plan freshness", siEnumLabel(decision.plan_freshness.status)) : ""}
                ${clampedScore != null ? `<div class="si-view-gauge">
                    <div class="si-view-gauge-row"><span>Score</span><strong>${siScore(score)} / 100</strong></div>
                    <div class="si-view-gauge-bar"><div class="si-view-gauge-mask" style="width:${100 - clampedScore}%"></div></div>
                    ${gateDots}
                </div>` : gateDots}
            </div>
            <p class="si-view-explanation">${siText(siDisplayExplanation(decision.explanation))}</p>
            <p class="si-actions">
                ${siJumpButton("decision", "Open ATHENA Decision", "fa-brain")}
                <a class="btn" href="${siEscape(openHref)}"><i class="fas fa-file-lines" aria-hidden="true"></i> Open Decision Brief</a>
                ${siJumpButton("audit", "View evidence", "fa-clipboard-check")}
            </p></div>`;
    }

    function siViewStatTile(icon, label, value) {
        return `<div class="si-view-stat">
            <span class="si-view-stat-icon"><i class="fas ${icon}" aria-hidden="true"></i></span>
            <span class="si-view-stat-text"><dt>${siEscape(label)}</dt><dd>${siText(value)}</dd></span>
        </div>`;
    }

    // Collects every real structural level into one flat list so the ladder
    // can position them on a shared scale. Each point's value is the exact
    // same boundary the old stacked rows used (upper for support zones,
    // lower for trigger/target zones) -- purely a layout change, not a new
    // methodology.
    // siFiniteNumber(null) coerces via Number(null) === 0, which IS finite --
    // it cannot tell "genuinely absent" from "zero". A plain scalar field
    // (unlike a zone object, already guarded by siZoneLooksEmpty) needs its
    // own null/undefined check first, or an absent value renders as a
    // fabricated real "₹0.00" point instead of being omitted.
    function siNullableFiniteNumber(value) {
        if (value === null || value === undefined) return null;
        return siFiniteNumber(value);
    }

    function siPriceLadderPoints(d1) {
        const close = siNullableFiniteNumber(d1 && d1.close);
        const points = [];
        function addZone(category, label, zone, bound) {
            if (siZoneLooksEmpty(zone)) return;
            const value = siFiniteNumber(bound === "upper" ? zone.upper : zone.lower);
            if (value == null) return;
            points.push({ category, label, value, display: siZoneShort(zone) });
        }
        addZone("support", "Support 1", d1 && d1.support_1, "upper");
        addZone("major-support", "Major Support", d1 && d1.major_support, "upper");
        addZone("trigger", "Review Trigger", d1 && d1.review_trigger, "lower");
        addZone("target", "Target 1", d1 && d1.target_1, "lower");
        addZone("target", "Target 2", d1 && d1.target_2, "lower");
        addZone("target", "Target 3", d1 && d1.target_3, "lower");
        const high = siNullableFiniteNumber(d1 && d1.available_history_high);
        if (high != null) points.push({ category: "high", label: "Available High", value: high, display: siMoney(high) });
        return { close, points };
    }

    function siLadderDistText(value, close) {
        const rel = siLevelVsClose(value, close);
        if (!rel) return "";
        if (rel.direction === "at") return "at close";
        return `${rel.direction === "above" ? "+" : "-"}${rel.magnitude}%`;
    }

    // Horizontal price ladder -- replaces the old stacked level rows. Every
    // position is a real value on a shared min-close-max scale; the
    // red-to-green track color is purely positional ("lower price on the
    // left, higher on the right"), never a trading instruction of any kind.
    function siPriceLadder(d1) {
        const { close, points } = siPriceLadderPoints(d1);
        if (!points.length || close == null) {
            return `<p class="si-empty">No structural levels are available for this symbol.</p>`;
        }
        const values = [...points.map(p => p.value), close];
        const min = Math.min(...values);
        const max = Math.min(Math.max(...values), Number.MAX_SAFE_INTEGER);
        const span = (max - min) || Math.max(1, Math.abs(close) * 0.02);
        const pad = span * 0.1;
        const lo = min - pad;
        const hi = max + pad;
        const denom = (hi - lo) || 1;
        const pct = value => Math.max(0, Math.min(100, ((value - lo) / denom) * 100));
        const sorted = [...points].sort((a, b) => a.value - b.value);
        // Adjacent points can land close enough together (in % terms) that
        // their label cards would overlap horizontally. A 2-tier zig-zag
        // only guarantees clearance between immediate neighbors -- with up
        // to 7 real points (the frozen d1 schema's max: support_1,
        // major_support, review_trigger, target_1/2/3, available_history_high)
        // in a narrower column, same-tier points 2 apart in sort order can
        // still collide. 3 tiers keeps any two same-tier points at least 3
        // sort-positions apart, without measuring actual rendered widths.
        const markers = sorted.map((p, index) => {
            const dist = siLadderDistText(p.value, close);
            const tier = index % 3;
            const tierClass = tier === 1 ? " si-ladder-point--tier1" : tier === 2 ? " si-ladder-point--tier2" : "";
            return `<div class="si-ladder-point${tierClass}" data-si-level="${siEscape(p.category)}" style="left:${pct(p.value)}%">
                <div class="si-ladder-card">
                    <span class="si-ladder-label">${siEscape(p.label)}</span>
                    <span class="si-ladder-value">${siEscape(p.display)}</span>
                    ${dist ? `<span class="si-ladder-dist">${siEscape(dist)}</span>` : ""}
                </div>
                <span class="si-ladder-dot"></span>
            </div>`;
        }).join("");
        return `<div class="si-price-ladder">
            <div class="si-ladder-track">
                ${markers}
                <div class="si-ladder-current" style="left:${pct(close)}%"><span class="si-ladder-current-dot"></span></div>
            </div>
            <div class="si-ladder-current-label" style="left:${pct(close)}%">
                <strong>${siMoney(close)}</strong><span>D1 close</span>
            </div>
        </div>`;
    }

    function siLevelsCard(d1) {
        return `<div class="si-card si-price-map"><h3>Price Map</h3>
            <p class="si-pending">Distances use completed-D1 close against completed-D1 levels. Live/latest quote is not mixed in.</p>
            ${siPriceLadder(d1 || {})}
        </div>`;
    }

    function siSignalTone(kind, value) {
        const raw = String(value || "").toUpperCase();
        if (kind === "structure") {
            if (raw === "UPTREND") return "good";
            if (raw === "DOWNTREND") return "bad";
            return "";
        }
        if (kind === "supertrend") {
            if (raw === "BULLISH") return "good";
            if (raw === "BEARISH") return "bad";
            return "";
        }
        if (kind === "volume") return raw === "Above MA20" ? "good" : "";
        if (kind === "decision") {
            if (raw === "TRADE") return "good";
            if (raw === "WATCH") return "warn";
            return "";
        }
        return "";
    }

    function siSignalIcon(kind) {
        switch (kind) {
            case "structure": return "fa-arrow-trend-up";
            case "supertrend": return "fa-wave-square";
            case "rsi": return "fa-gauge-high";
            case "volume": return "fa-chart-column";
            case "decision": return "fa-bullseye";
            default: return "fa-circle-dot";
        }
    }

    function siSignalChip(kind, label, value, tone, title) {
        const tip = title ? ` title="${siEscape(title)}"` : "";
        return `<div class="si-signal" data-tone="${tone || ""}">
            <span class="si-signal-icon"><i class="fas ${siSignalIcon(kind)}" aria-hidden="true"></i></span>
            <span class="si-signal-text">
                <span class="si-signal-label">${siEscape(label)}</span>
                <span class="si-signal-value"${tip}>${value}</span>
            </span>
        </div>`;
    }

    function siScanStrip(bundle) {
        const d1 = bundle.d1 || {};
        const decision = bundle.decision || {};
        const decisionLabel = decision.present ? siEnumLabel(decision.decision_type) : "Not available";
        const volumeLabel = siVolumeVsMa20(d1);
        return `<div class="si-scan-strip" aria-label="Compact technical snapshot">
            ${siSignalChip("structure", "Daily SMA structure", siSmaStructureLabel(d1.symbol_trend), siSignalTone("structure", d1.symbol_trend), d1.symbol_trend || "")}
            ${siSignalChip("supertrend", "SuperTrend (10,3)", siSuperTrendLabel(d1.supertrend_direction), siSignalTone("supertrend", d1.supertrend_direction), d1.supertrend_direction || "")}
            ${siSignalChip("rsi", "RSI (14)", siRsi(d1.rsi14), "")}
            ${siSignalChip("volume", "Volume vs MA20", volumeLabel, siSignalTone("volume", volumeLabel))}
            ${siSignalChip("decision", "ATHENA Decision", siEscape(decisionLabel), siSignalTone("decision", decision.decision_type))}
        </div>`;
    }

    function siAvailabilityChips(bundle) {
        const fundamentals = bundle.fundamentals || {};
        const news = bundle.news || {};
        return `<div class="si-card si-capability"><h3>Capability availability</h3>
            <div class="si-availability-chips">
                <span class="si-chip tone-warn">Fundamentals <b>Not ingested</b></span>
                <span class="si-chip tone-warn">News &amp; catalysts <b>Not ingested</b></span>
            </div>
            <p class="si-pending">Not available yet. ${siText(fundamentals.status, "NOT_INGESTED")} / ${siText(news.status, "NOT_INGESTED")} are not errors.</p>
            ${siJumpButton("audit", "View evidence", "fa-clipboard-check")}</div>`;
    }

    function siDarvaxOverview(darvax) {
        const label = siText(darvax && darvax.experimental_label, "EXPERIMENTAL_UNVALIDATED");
        const badge = `<span class="si-experimental-badge">Experimental</span>`;
        if (!darvax || darvax.status !== "ENABLED_IFRAME") {
            return `<div class="si-card"><h3>DarvaX</h3>
                <p class="si-empty">DARVAX UNAVAILABLE</p>
                <p class="si-pending">${label}</p></div>`;
        }
        return `<div class="si-card si-darvax-panel">
            <div class="si-darvax-art" data-si-placeholder="true" aria-hidden="true"></div>
            <h3>DarvaX ${badge}</h3>
            <p class="si-empty">DarvaX experimental view available</p>
            <p class="si-empty">Symbol 360 is available on the DarvaX surface. It is not mixed into Stock 360 evidence.</p>
            <p class="si-pending">${label}</p>
            ${siJumpButton("experimental", "Open DarvaX", "fa-arrow-up-right-from-square")}</div>`;
    }

    function siDarvaxCard(darvax) {
        const label = siText(darvax && darvax.experimental_label, "EXPERIMENTAL_UNVALIDATED");
        if (!darvax || darvax.status !== "ENABLED_IFRAME" || !darvax.iframe_url) {
            return `<div class="si-card"><h3>DarvaX</h3>
                <p class="si-empty">DARVAX UNAVAILABLE</p>
                <p class="si-pending">${siText(darvax && darvax.explanation)}</p>
                <p class="si-pending">${label}</p></div>`;
        }
        return `<div class="si-card"><h3>DarvaX · ${label}</h3>
            <div id="si-darvax-frame-wrap">
                <iframe id="si-darvax-frame" class="si-iframe" title="DarvaX Symbol 360" src="${siEscape(darvax.iframe_url)}"></iframe>
            </div></div>`;
    }

    function siChartBlock(identity, d1) {
        if (!identity || !identity.resolved) {
            return "";
        }
        if (!d1 || !d1.present) {
            return `<div class="si-card si-chart-card"><h3>Completed D1 chart</h3>
                <p class="si-empty">Completed D1 chart unavailable.</p></div>`;
        }
        return `<div class="si-card si-chart-card">
            <div class="si-chart-header">
                <div><h3>Completed D1 chart</h3>
                    <p class="si-pending si-chart-subtitle">LAST COMPLETED D1 · unfinished session candles are excluded</p></div>
                <div class="si-chart-controls-slot"></div>
            </div>
            <div class="si-chart-host si-chart-pending" id="si-d1-chart-host"><p class="text-muted">Loading D1 chart…</p></div>
        </div>`;
    }

    function siSentence(parts) {
        return parts.filter(Boolean).join(" ");
    }

    function siSummaryStatement(
        kind,
        text,
        sourceRefs,
        asOf = null,
        displayParts = [],
        displayMeta = ""
    ) {
        if (!text) return null;
        return Object.freeze({
            kind,
            text,
            source_refs: Object.freeze([...sourceRefs]),
            as_of: asOf || null,
            display_parts: Object.freeze([...displayParts]),
            display_meta: displayMeta,
        });
    }

    function siSummarySource(bundle, sourceName) {
        return ((bundle && bundle.sources) || []).find(source => source.source === sourceName) || null;
    }

    function siSummaryStructure(d1, reportedMissing) {
        if (!d1 || !d1.present) return null;
        const smaRaw = d1.symbol_trend_is_coherent === true
            && ["UPTREND", "DOWNTREND", "SIDEWAYS", "MIXED"].includes(String(d1.symbol_trend || ""))
            ? d1.symbol_trend
            : null;
        const stRaw = d1.supertrend_is_coherent === true
            && ["BULLISH", "BEARISH"].includes(String(d1.supertrend_direction || ""))
            ? d1.supertrend_direction
            : null;
        const sma = smaRaw ? siSmaStructureLabel(smaRaw) : "";
        const st = stRaw ? siSuperTrendLabel(stRaw) : "";
        let text = "";
        let displayParts = [];
        if (sma && st && sma === st && (sma === "Up" || sma === "Down")) {
            text = `Daily SMA structure and SuperTrend both indicate ${sma.toLowerCase()}ward technical structure.`;
            displayParts = [`SMA ${sma}`, `SuperTrend ${st}`];
        } else if (sma && st) {
            text = `Daily SMA structure is ${sma}, while SuperTrend is ${st}; the two measurements disagree.`;
            displayParts = [`SMA ${sma}`, `SuperTrend ${st}`, "Indicators disagree"];
        } else if (sma) {
            reportedMissing.add("SuperTrend");
            text = `Daily SMA structure is ${sma}; SuperTrend is unavailable.`;
            displayParts = [`SMA ${sma}`, "SuperTrend unavailable"];
        } else if (st) {
            reportedMissing.add("Daily SMA structure");
            text = `SuperTrend is ${st}; Daily SMA structure is unavailable.`;
            displayParts = ["SMA unavailable", `SuperTrend ${st}`];
        }
        return siSummaryStatement(
            "STRUCTURE",
            text,
            ["d1.symbol_trend", "d1.symbol_trend_is_coherent", "d1.supertrend_direction", "d1.supertrend_is_coherent"],
            d1.latest_session,
            displayParts
        );
    }

    function siSummaryMomentum(d1) {
        if (!d1 || !d1.present) return null;
        const rsi = d1.rsi_is_coherent === true ? siFiniteNumber(d1.rsi14) : null;
        const volume = d1.volume_is_coherent === true ? siFiniteNumber(d1.volume) : null;
        const volumeMa20 = d1.volume_is_coherent === true ? siFiniteNumber(d1.volume_ma20) : null;
        const participation = volume != null && volumeMa20 != null
            ? (volume >= volumeMa20 ? "above" : "below")
            : "";
        let text = "";
        const displayParts = [];
        if (rsi != null && participation) {
            text = `RSI (14) is ${siRsi(rsi)}, and completed-D1 volume is ${participation} its 20-session average.`;
        } else if (rsi != null) {
            text = `RSI (14) is ${siRsi(rsi)}.`;
        } else if (participation) {
            text = `Completed-D1 volume is ${participation} its 20-session average.`;
        }
        if (rsi != null) displayParts.push(`RSI ${siRsi(rsi)}`);
        if (participation) displayParts.push(`Volume ${participation} 20-session average`);
        return siSummaryStatement(
            "MOMENTUM",
            text,
            ["d1.rsi14", "d1.rsi_is_coherent", "d1.volume", "d1.volume_ma20", "d1.volume_is_coherent"],
            d1.latest_session,
            displayParts
        );
    }

    function siSummaryCloseVsBoundaryPart(label, close, boundary) {
        const relation = siCloseVsBoundary(close, boundary);
        if (!relation) return "";
        if (relation.direction === "at") return `D1 at ${label} upper boundary`;
        return `D1 ${relation.magnitude}% ${relation.direction} ${label}`;
    }

    function siSummaryLevelVsClosePart(label, level, close) {
        const relation = siLevelVsClose(level, close);
        if (!relation) return "";
        if (relation.direction === "at") return `${label} at D1 close`;
        return `${label} ${relation.magnitude}% ${relation.direction} D1 close`;
    }

    function siSummaryLevels(d1) {
        if (!d1 || !d1.present || d1.structural_is_coherent !== true) return null;
        const close = siFiniteNumber(d1.close);
        if (close == null || close === 0) return null;
        const observations = [];
        const displayParts = [];
        const sourceRefs = ["d1.close", "d1.structural_is_coherent"];
        const supportCandidates = [
            ["Support 1", d1.support_1, "d1.support_1"],
            ["Major Support", d1.major_support, "d1.major_support"],
        ];
        const upper = supportCandidates.find(([, zone]) => (
            zone && siFiniteNumber(zone.upper) != null && siFiniteNumber(zone.upper) !== 0
        ));
        if (upper) {
            observations.push(siCloseVsBoundarySentence(upper[0], close, upper[1].upper));
            displayParts.push(siSummaryCloseVsBoundaryPart(upper[0], close, upper[1].upper));
            sourceRefs.push(upper[2]);
        }
        const forwardCandidates = [
            ["Review Trigger", d1.review_trigger, "d1.review_trigger"],
            ["Target 1", d1.target_1, "d1.target_1"],
        ];
        const lower = forwardCandidates.find(([, zone]) => (
            zone && siFiniteNumber(zone.lower) != null && siFiniteNumber(zone.lower) !== 0
        ));
        if (lower) {
            observations.push(siLevelVsCloseSentence(lower[0], lower[1].lower, close));
            displayParts.push(siSummaryLevelVsClosePart(lower[0], lower[1].lower, close));
            sourceRefs.push(lower[2]);
        }
        return siSummaryStatement(
            "LEVEL_POSITION",
            observations.filter(Boolean).slice(0, 2).join(" "),
            sourceRefs,
            d1.latest_session,
            displayParts.filter(Boolean).slice(0, 2)
        );
    }

    function siSummaryDecision(decision) {
        if (!decision || !decision.present) {
            return siSummaryStatement(
                "ATHENA_DECISION",
                "ATHENA has no persisted Decision for this symbol; Stock 360 technical research remains available.",
                ["decision.present", "decision.null_reason"],
                null,
                ["No persisted Decision", "Stock 360 research remains available"]
            );
        }
        const type = siEnumLabel(decision.decision_type, "Decision");
        const date = decision.ts ? siChartLongDate(decision.ts) : "";
        const confidence = decision.confidence_level
            ? siEnumLabel(decision.confidence_level, "")
            : "";
        let text = `ATHENA has a persisted ${type} Decision`;
        if (date && date !== "—") text += ` as of ${date}`;
        if (confidence) text += ` with ${confidence} confidence`;
        text += ".";
        const score = siPersistedScore(decision);
        const gates = siGatePassSummary(decision);
        const displayParts = [type];
        if (confidence) displayParts.push(`${confidence} confidence`);
        if (score != null) displayParts.push(`Score ${siScore(score)}/100`);
        if (gates) {
            const compactGates = gates.replace(" of ", "/");
            displayParts.push(`${compactGates}`);
        }
        if (score != null && gates) {
            text += ` Persisted score is ${siScore(score)} / 100, and ${gates}.`;
        } else if (score != null) {
            text += ` Persisted score is ${siScore(score)} / 100.`;
        } else if (gates) {
            text += ` ${gates.charAt(0).toUpperCase()}${gates.slice(1)}.`;
        }
        return siSummaryStatement(
            "ATHENA_DECISION",
            text,
            ["decision.present", "decision.decision_type", "decision.ts", "decision.confidence_level", "decision.depth.score.value", "decision.gates"],
            decision.ts,
            displayParts,
            date && date !== "—" ? `Decision as of ${date}` : ""
        );
    }

    function siSummaryPortfolio(portfolio) {
        if (!portfolio) return null;
        if (portfolio.status !== "HELD") {
            return siSummaryStatement(
                "PORTFOLIO",
                "This symbol is not held in My Portfolio.",
                ["portfolio.status"],
                null,
                ["Not held"]
            );
        }
        const quantity = siFiniteNumber(portfolio.quantity);
        const average = siFiniteNumber(portfolio.avg_price);
        const pnlPct = siFiniteNumber(portfolio.pnl_pct);
        const displayParts = [];
        let text = "This symbol is held in My Portfolio";
        if (quantity != null && average != null) {
            text += `: ${siInteger(quantity)} shares at an average price of ${siMoney(average)}`;
        }
        text += ".";
        if (pnlPct != null) text += ` Current Portfolio P&L is ${siPct(pnlPct)}.`;
        if (quantity != null) displayParts.push(`${siInteger(quantity)} shares`);
        if (average != null) displayParts.push(`Avg ${siMoney(average)}`);
        if (pnlPct != null) displayParts.push(`P&L ${siPct(pnlPct)}`);
        if (!displayParts.length) displayParts.push("Held");
        return siSummaryStatement(
            "PORTFOLIO",
            text,
            ["portfolio.status", "portfolio.quantity", "portfolio.avg_price", "portfolio.pnl_pct"],
            null,
            displayParts
        );
    }

    function siSummaryAvailability(bundle, reportedMissing) {
        const d1 = bundle.d1 || {};
        const d1Source = siSummarySource(bundle, "D1_CANDLES");
        const parts = [];
        const displayParts = [];
        const refs = ["sources.D1_CANDLES.status", "d1.latest_session"];
        const date = d1.latest_session ? siChartLongDate(d1.latest_session) : "";
        if (!d1.present) {
            parts.push("Completed-D1 evidence is unavailable.");
            displayParts.push("Completed-D1 evidence unavailable");
        } else if (d1Source && d1Source.status === "STALE") {
            parts.push(date && date !== "—"
                ? `Completed-D1 evidence is stale through ${date}.`
                : "Completed-D1 evidence is stale.");
            displayParts.push(date && date !== "—"
                ? `Completed-D1 evidence stale through ${date}`
                : "Completed-D1 evidence stale");
        } else if (date && date !== "—") {
            parts.push(`Data through ${date}.`);
            displayParts.push(`Data through ${date}`);
        }
        if (d1.present) {
            const missing = [];
            if (!(d1.symbol_trend_is_coherent === true && d1.symbol_trend)) missing.push("Daily SMA structure");
            if (!(d1.supertrend_is_coherent === true && d1.supertrend_direction)) missing.push("SuperTrend");
            if (!(d1.rsi_is_coherent === true && siFiniteNumber(d1.rsi14) != null)) missing.push("RSI");
            if (!(d1.volume_is_coherent === true
                && siFiniteNumber(d1.volume) != null
                && siFiniteNumber(d1.volume_ma20) != null)) missing.push("volume comparison");
            const unreported = missing.filter(name => !reportedMissing.has(name));
            if (unreported.length > 0 && unreported.length <= 3) {
                const names = unreported.length === 1
                    ? unreported[0]
                    : `${unreported.slice(0, -1).join(", ")} and ${unreported.at(-1)}`;
                parts.push(`${names} ${unreported.length === 1 ? "is" : "are"} unavailable.`);
                displayParts.push(`${names} ${unreported.length === 1 ? "is" : "are"} unavailable`);
            } else if (unreported.length > 3) {
                parts.push("Some optional D1 measurements are unavailable.");
                displayParts.push("Some optional D1 measurements unavailable");
            }
        }
        if (bundle.fundamentals && bundle.fundamentals.status === "NOT_INGESTED"
            && bundle.news && bundle.news.status === "NOT_INGESTED") {
            parts.push("Fundamentals and news/catalysts are not yet ingested.");
            displayParts.push("Fundamentals and news/catalysts not yet ingested");
            refs.push("fundamentals.status", "news.status");
        } else if (bundle.fundamentals && bundle.fundamentals.status === "NOT_INGESTED") {
            parts.push("Fundamentals are not yet ingested.");
            displayParts.push("Fundamentals not yet ingested");
            refs.push("fundamentals.status");
        } else if (bundle.news && bundle.news.status === "NOT_INGESTED") {
            parts.push("News/catalysts are not yet ingested.");
            displayParts.push("News/catalysts not yet ingested");
            refs.push("news.status");
        }
        return siSummaryStatement(
            "DATA_AVAILABILITY",
            siSentence(parts),
            refs,
            d1.latest_session,
            displayParts
        );
    }

    function siComposeResearchSummary(bundle) {
        if (!bundle || !bundle.identity || bundle.identity.resolved !== true) {
            return Object.freeze({primary: Object.freeze([]), supporting: Object.freeze([]), availability: Object.freeze([]), statements: Object.freeze([])});
        }
        const d1 = bundle.d1 || {};
        const reportedMissing = new Set();
        const primary = [
            siSummaryStructure(d1, reportedMissing),
            siSummaryMomentum(d1),
            siSummaryLevels(d1),
            siSummaryDecision(bundle.decision),
        ].filter(Boolean).slice(0, 4);
        const supporting = [siSummaryPortfolio(bundle.portfolio)].filter(Boolean).slice(0, 1);
        const availability = [siSummaryAvailability(bundle, reportedMissing)].filter(Boolean).slice(0, 1);
        return Object.freeze({
            primary: Object.freeze(primary),
            supporting: Object.freeze(supporting),
            availability: Object.freeze(availability),
            statements: Object.freeze([...primary, ...supporting, ...availability]),
        });
    }

    function siSummaryFamilyLabel(kind) {
        return ({
            STRUCTURE: "Structure",
            MOMENTUM: "Momentum",
            LEVEL_POSITION: "Key Levels",
            ATHENA_DECISION: "ATHENA",
            PORTFOLIO: "Portfolio",
        })[kind] || "";
    }

    function siSummaryDisplayText(statement) {
        const parts = Array.isArray(statement && statement.display_parts)
            ? statement.display_parts.filter(Boolean)
            : [];
        return parts.length ? parts.join(" · ") : String(statement && statement.text || "");
    }

    function siSummaryDisplayGroups(statement) {
        const parts = Array.isArray(statement && statement.display_parts)
            ? statement.display_parts.filter(Boolean)
            : [];
        if (statement && statement.kind === "ATHENA_DECISION"
            && statement.source_refs.includes("decision.decision_type")) {
            const secondary = parts.filter(part => (
                /^Score\s/.test(part) || /\bgates passed$/.test(part)
            ));
            const primary = parts.filter(part => !secondary.includes(part));
            return {primary, secondary};
        }
        return {primary: parts, secondary: []};
    }

    function siSummaryAtomicHtml(parts) {
        return parts.map(part => siEscape(part).replaceAll(" ", "&nbsp;")).join(" · ");
    }

    function siSummaryRow(statement) {
        const label = siSummaryFamilyLabel(statement.kind);
        if (!label) return "";
        const sources = statement.source_refs.join(" ");
        const groups = siSummaryDisplayGroups(statement);
        const isPersistedDecision = statement.kind === "ATHENA_DECISION"
            && statement.source_refs.includes("decision.decision_type");
        const primaryText = groups.primary.length
            ? groups.primary.join(" · ")
            : siSummaryDisplayText(statement);
        const primaryHtml = isPersistedDecision
            ? siSummaryAtomicHtml(groups.primary)
            : siEscape(primaryText);
        const secondary = groups.secondary.length
            ? `<span class="si-brief-secondary">${siSummaryAtomicHtml(groups.secondary)}</span>`
            : "";
        const meta = statement.display_meta
            ? `<span class="si-brief-meta">${siEscape(statement.display_meta)}</span>`
            : "";
        return `<div class="si-brief-row" data-si-summary-kind="${siEscape(statement.kind)}" data-si-summary-sources="${siEscape(sources)}">
            <dt>${siEscape(label)}</dt>
            <dd><span class="si-brief-evidence">${primaryHtml}</span>${secondary}${meta}</dd>
        </div>`;
    }

    function siSummaryFooter(statement) {
        if (!statement) return "";
        const sources = statement.source_refs.join(" ");
        const parts = statement.display_parts.filter(Boolean);
        const firstIsFreshness = /^(Data through|Completed-D1 evidence)/.test(parts[0] || "");
        const freshness = firstIsFreshness ? parts[0] : "";
        const capability = parts.slice(firstIsFreshness ? 1 : 0).join(" · ");
        const stale = /\bstale\b/i.test(freshness);
        const freshnessHtml = freshness
            ? `<span class="si-review-freshness">${siEscape(freshness)}</span>`
            : "";
        const capabilityHtml = capability
            ? `<span class="si-review-capability">${siEscape(capability)}</span>`
            : "";
        return `<p class="si-review-meta${stale ? " is-stale" : ""}" data-si-summary-kind="DATA_AVAILABILITY" data-si-summary-sources="${siEscape(sources)}">${freshnessHtml}${capabilityHtml}</p>`;
    }

    function siCompleteReview(bundle) {
        const summary = siComposeResearchSummary(bundle);
        const visible = [...summary.primary, ...summary.supporting].filter(statement => (
            statement.kind !== "PORTFOLIO" || bundle.portfolio?.status === "HELD"
        ));
        const rows = visible.map(siSummaryRow).filter(Boolean).join("");
        return `<div class="si-card si-review">
            <h3>Research brief</h3>
            <dl class="si-research-brief">${rows}</dl>
            ${siSummaryFooter(summary.availability[0])}
        </div>`;
    }

    function siAuditTable(bundle) {
        const records = [
            ...((bundle.sources || []).map(src => ({
                source: src.source,
                status: src.status,
                asOf: siDate(src.as_of),
                reference: src.lineage,
                reason: src.explanation,
            }))),
            ...((bundle.unavailable || []).map(item => ({
                source: item.code,
                status: "UNAVAILABLE",
                asOf: "—",
                reference: item.lineage,
                reason: item.detail,
            }))),
        ];
        const hydration = bundle.hydration || {};
        records.push({
            source: "HYDRATION",
            status: hydration.status || "SKIPPED",
            asOf: "—",
            reference: "D1_CANDLES",
            reason: hydration.detail,
        });
        const rows = records.map(row => (
            `<tr><td>${siText(row.source)}</td><td>${siText(row.status)}</td><td>${siText(row.asOf)}</td>
            <td>${siText(row.reference)}</td><td>${siText(row.reason)}</td></tr>`
        )).join("");
        const cards = records.map(row => (
            `<article class="si-audit-card">
                <div><dt>Source</dt><dd>${siText(row.source)}</dd></div>
                <div><dt>Status</dt><dd>${siText(row.status)}</dd></div>
                <div><dt>As Of</dt><dd>${siText(row.asOf)}</dd></div>
                <div><dt>Reference</dt><dd>${siText(row.reference)}</dd></div>
                <div><dt>Reason</dt><dd>${siText(row.reason)}</dd></div>
            </article>`
        )).join("");
        return `<div class="si-card"><h3>Evidence / Audit</h3>
            <div class="si-audit-wrap">
            <table class="si-audit-table">
                <thead><tr><th>Source</th><th>Status</th><th>As Of</th><th>Reference</th><th>Reason</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
            </div>
            <div class="si-audit-cards">${cards}</div></div>`;
    }

    function bindDarvaxFrame() {
        const frame = document.getElementById("si-darvax-frame");
        const wrap = document.getElementById("si-darvax-frame-wrap");
        if (!frame || !wrap) return;
        frame.addEventListener("load", () => {
            let bodyText = "";
            try {
                bodyText = (frame.contentDocument && frame.contentDocument.body && frame.contentDocument.body.innerText || "").trim();
            } catch (_err) {
                return;
            }
            if (/not found/i.test(bodyText) && (bodyText.startsWith("{") || bodyText.includes('"detail"'))) {
                wrap.innerHTML = `<p class="si-empty">DARVAX UNAVAILABLE</p>
                    <p class="si-pending">Symbol 360 did not load. ${siEscape(bodyText.slice(0, 180))}</p>
                    <p class="si-pending">EXPERIMENTAL_UNVALIDATED</p>`;
            }
        });
    }

    function siChartDateKey(value) {
        const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
        return match ? match[1] : "";
    }

    function siChartCandle(value) {
        if (!value) return null;
        const date = siChartDateKey(value.ts_open || value.ts);
        const open = siFiniteNumber(value.open);
        const high = siFiniteNumber(value.high);
        const low = siFiniteNumber(value.low);
        const close = siFiniteNumber(value.close);
        const volume = siFiniteNumber(value.volume);
        if (!date || [open, high, low, close, volume].some(item => item == null)) return null;
        if (open <= 0 || high <= 0 || low <= 0 || close <= 0 || volume < 0) return null;
        if (high < low || high < Math.max(open, close) || low > Math.min(open, close)) return null;
        return {
            ts_open: String(value.ts_open || value.ts),
            date,
            open,
            high,
            low,
            close,
            volume,
        };
    }

    function siChartTrailingSma(values, period) {
        const result = values.map(() => null);
        if (!Number.isInteger(period) || period < 1 || values.length < period) return result;
        let windowSum = 0;
        for (let index = 0; index < values.length; index += 1) {
            windowSum += values[index];
            if (index >= period) windowSum -= values[index - period];
            if (index >= period - 1) result[index] = windowSum / period;
        }
        return result;
    }

    function siPrepareD1ChartSeries(series, completedSession) {
        const cutoff = siChartDateKey(completedSession);
        const rows = Array.isArray(series && series.candles) ? series.candles : [];
        let invalidCount = 0;
        let excludedAfterCutoff = 0;
        const candles = [];
        rows.forEach(row => {
            const candle = siChartCandle(row);
            if (!candle) {
                invalidCount += 1;
                return;
            }
            if (!cutoff || candle.date > cutoff) {
                excludedAfterCutoff += 1;
                return;
            }
            candles.push(candle);
        });
        candles.sort((left, right) => left.ts_open.localeCompare(right.ts_open));
        const closes = candles.map(candle => candle.close);
        return {
            cutoff,
            candles,
            sma20: siChartTrailingSma(closes, 20),
            sma50: siChartTrailingSma(closes, 50),
            invalidCount,
            excludedAfterCutoff,
        };
    }

    function siChartSameDisplayedPrice(left, right) {
        const a = siFiniteNumber(left);
        const b = siFiniteNumber(right);
        if (a == null || b == null) return a == null && b == null;
        return a.toFixed(2) === b.toFixed(2);
    }

    function siChartReconciliation(prepared, d1) {
        const candles = prepared.candles;
        const last = candles[candles.length - 1] || null;
        const final20 = prepared.sma20[prepared.sma20.length - 1] ?? null;
        const final50 = prepared.sma50[prepared.sma50.length - 1] ?? null;
        const expected20 = siFiniteNumber(d1 && d1.fast_sma);
        const expected50 = siFiniteNumber(d1 && d1.slow_sma);
        const closeMatches = Boolean(last && siChartSameDisplayedPrice(last.close, d1 && d1.close));
        const sma20Matches = expected20 == null ? null : siChartSameDisplayedPrice(final20, expected20);
        const sma50Matches = expected50 == null ? null : siChartSameDisplayedPrice(final50, expected50);
        return {
            final20,
            final50,
            closeMatches,
            sma20Matches,
            sma50Matches,
            coherent: closeMatches && sma20Matches !== false && sma50Matches !== false,
        };
    }

    function siChartLevels(d1) {
        if (!d1 || d1.structural_is_coherent !== true) return [];
        const definitions = [
            ["S1", "Support 1", d1.support_1, "upper"],
            ["MS", "Major Support", d1.major_support, "upper"],
            ["RT", "Review Trigger", d1.review_trigger, "lower"],
            ["T1", "Target 1", d1.target_1, "lower"],
            ["T2", "Target 2", d1.target_2, "lower"],
            ["T3", "Target 3", d1.target_3, "lower"],
        ];
        return definitions.flatMap(([short, label, zone, anchor]) => {
            if (!zone || zone.lineage !== "PORTFOLIO_STRUCTURAL_REVIEW") return [];
            const lower = siFiniteNumber(zone.lower);
            const upper = siFiniteNumber(zone.upper);
            if (lower == null || upper == null || lower <= 0 || upper <= 0 || lower > upper) return [];
            return [{ short, label, lower, upper, anchor, anchorPrice: anchor === "upper" ? upper : lower }];
        });
    }

    function siChartPlaceLevelTag(naturalY, d1Y, top, bottom, minimumGap = 6) {
        const levelHalfHeight = 12;
        const d1HalfHeight = 9;
        const clampedNatural = Math.max(top + levelHalfHeight, Math.min(bottom - levelHalfHeight, naturalY));
        const d1Top = d1Y - d1HalfHeight;
        const d1Bottom = d1Y + d1HalfHeight;
        const overlapsD1 = clampedNatural + levelHalfHeight + minimumGap > d1Top
            && clampedNatural - levelHalfHeight - minimumGap < d1Bottom;
        if (!overlapsD1) return { naturalY, labelY: clampedNatural, d1Y };
        const above = d1Top - minimumGap - levelHalfHeight;
        const below = d1Bottom + minimumGap + levelHalfHeight;
        const aboveFits = above - levelHalfHeight >= top;
        const belowFits = below + levelHalfHeight <= bottom;
        let labelY;
        if (naturalY <= d1Y && aboveFits) labelY = above;
        else if (naturalY > d1Y && belowFits) labelY = below;
        else if (aboveFits && belowFits) {
            labelY = Math.abs(above - clampedNatural) <= Math.abs(below - clampedNatural) ? above : below;
        } else if (aboveFits) labelY = above;
        else if (belowFits) labelY = below;
        else labelY = clampedNatural;
        return { naturalY, labelY, d1Y };
    }

    function siChartCreateLevelInteraction(levelIds, initialPersistent = null) {
        const allowed = new Set(levelIds);
        let persistentLevelId = allowed.has(initialPersistent) ? initialPersistent : null;
        let persistentSource = persistentLevelId ? "retained" : null;
        let transientLevelId = null;
        let transientSource = null;
        const valid = levelId => allowed.has(levelId) ? levelId : null;
        const snapshot = () => ({
            persistentLevelId,
            persistentSource,
            transientLevelId,
            transientSource,
            activeLevelId: transientLevelId || persistentLevelId,
        });
        return {
            snapshot,
            select(levelId, source) {
                persistentLevelId = valid(levelId);
                persistentSource = persistentLevelId ? source : null;
                transientLevelId = null;
                transientSource = null;
                return snapshot();
            },
            preview(levelId, source) {
                transientLevelId = valid(levelId);
                transientSource = transientLevelId ? source : null;
                return snapshot();
            },
            clearPreview(source = null) {
                if (source && transientSource !== source) return snapshot();
                transientLevelId = null;
                transientSource = null;
                return snapshot();
            },
            clearSelection() {
                persistentLevelId = null;
                persistentSource = null;
                return snapshot();
            },
            clearAll() {
                persistentLevelId = null;
                persistentSource = null;
                transientLevelId = null;
                transientSource = null;
                return snapshot();
            },
        };
    }

    function siChartPath(values, xAt, y) {
        let path = "";
        let drawing = false;
        values.forEach((value, index) => {
            if (value == null) {
                drawing = false;
                return;
            }
            path += `${drawing ? " L" : "M"}${xAt(index).toFixed(2)} ${y(value).toFixed(2)}`;
            drawing = true;
        });
        return path;
    }

    function siChartWindowCount(windowKey, total) {
        if (windowKey === "3M") return Math.min(total, 63);
        if (windowKey === "ALL") return total;
        return Math.min(total, 126);
    }

    function siChartDateTickIndices(total, compact, wide) {
        if (total <= 0) return [];
        const count = Math.min(total, compact ? 2 : wide ? 5 : 3);
        if (count === 1) return [0];
        return Array.from(
            new Set(Array.from({ length: count }, (_, index) => (
                Math.round(index * (total - 1) / (count - 1))
            )))
        );
    }

    function siChartPriceScale(values, targetIntervals) {
        const rawMin = Math.min(...values);
        const rawMax = Math.max(...values);
        const rawSpan = Math.max(rawMax - rawMin, Math.abs(rawMax || 1) * 0.005);
        const paddedMin = rawMin - rawSpan * 0.06;
        const paddedMax = rawMax + rawSpan * 0.06;
        const rawStep = (paddedMax - paddedMin) / Math.max(1, targetIntervals);
        const baseExponent = Math.floor(Math.log10(rawStep));
        const candidates = [];
        for (let exponent = baseExponent - 1; exponent <= baseExponent + 1; exponent += 1) {
            const magnitude = 10 ** exponent;
            for (const factor of [1, 2, 2.5, 5, 10]) candidates.push(factor * magnitude);
        }
        const desiredTicks = Math.max(2, targetIntervals + 1);
        const evaluated = [...new Set(candidates)].map(step => {
            const first = Math.ceil((paddedMin - step * 0.001) / step) * step;
            const last = Math.floor((paddedMax + step * 0.001) / step) * step;
            const tickCount = last < first ? 0 : Math.floor((last - first) / step + 0.5) + 1;
            const densityPenalty = tickCount < 2 || tickCount > 7 ? 100 : 0;
            return {
                step,
                score: densityPenalty + Math.abs(tickCount - desiredTicks) + Math.abs(step - rawStep) / rawStep * 0.01,
            };
        }).sort((left, right) => left.score - right.score || left.step - right.step);
        const step = evaluated[0].step;
        const min = paddedMin;
        const max = paddedMax;
        const precision = Math.max(0, -Math.floor(Math.log10(step)) + 1);
        const ticks = [];
        const tickMax = Math.floor((max + step * 0.001) / step) * step;
        for (let value = tickMax; value >= min - step * 0.001; value -= step) {
            ticks.push(Number(value.toFixed(precision)));
        }
        return { min, max, step, ticks };
    }

    function siChartAxisPrice(value, step) {
        const decimals = step >= 1 ? 0 : step >= 0.1 ? 1 : 2;
        return `₹${Number(value).toLocaleString("en-IN", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        })}`;
    }

    function siChartLongDate(value) {
        const key = siChartDateKey(value);
        if (!key) return "—";
        const date = new Date(`${key}T12:00:00+05:30`);
        if (Number.isNaN(date.getTime())) return key;
        return new Intl.DateTimeFormat("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "2-digit",
            month: "short",
            year: "numeric",
        }).format(date);
    }

    function siChartAxisZone(level) {
        if (siChartSameDisplayedPrice(level.lower, level.upper)) return siMoney(level.lower);
        return `${siMoney(level.lower)}–${siMoney(level.upper).replace("₹", "")}`;
    }

    function siChartResolveLevelAtY(levels, pointerY, yAt, tolerance = 8) {
        const candidates = levels.map((level, sourceOrder) => {
            const first = yAt(level.lower);
            const second = yAt(level.upper);
            const top = Math.min(first, second);
            const bottom = Math.max(first, second);
            const inside = pointerY >= top && pointerY <= bottom;
            const distance = inside
                ? Math.min(Math.abs(pointerY - top), Math.abs(pointerY - bottom))
                : Math.min(Math.abs(pointerY - top), Math.abs(pointerY - bottom));
            return { level, sourceOrder, inside, distance };
        }).filter(candidate => candidate.inside || candidate.distance <= tolerance);
        candidates.sort((left, right) => left.distance - right.distance || left.sourceOrder - right.sourceOrder);
        return candidates[0] ? candidates[0].level : null;
    }

    function siChartInspectionHtml(candle, sma20, sma50) {
        return `<b class="si-chart-inspection-date">${siChartLongDate(candle.date)}</b>
            <span class="si-chart-inspection-ohlc"><span>O <b>${siMoney(candle.open)}</b></span><span>H <b>${siMoney(candle.high)}</b></span><span>L <b>${siMoney(candle.low)}</b></span><span>C <b>${siMoney(candle.close)}</b></span></span>
            <span class="si-chart-inspection-volume">Vol <b>${siInteger(candle.volume)}</b></span>
            <span class="si-chart-inspection-secondary"><span>SMA20 <b>${sma20 == null ? "—" : siMoney(sma20)}</b></span><span>SMA50 <b>${sma50 == null ? "—" : siMoney(sma50)}</b></span></span>`;
    }

    function renderSiD1Chart(host, series, d1, windowKey = "6M") {
        if (!host) return;
        if (siChartOutsidePointerHandler) {
            document.removeEventListener("pointerdown", siChartOutsidePointerHandler);
            siChartOutsidePointerHandler = null;
        }
        const retainedPersistentLevel = host._siChartPersistentLevelId || null;
        const card = host.closest(".si-chart-card");
        const controlsSlot = card && card.querySelector(".si-chart-controls-slot");
        if (controlsSlot) controlsSlot.innerHTML = "";
        const prepared = siPrepareD1ChartSeries(series, d1 && d1.latest_session);
        const allCandles = prepared.candles;
        host.classList.remove("si-chart-pending");
        if (!prepared.cutoff) {
            host.innerHTML = "<p class=\"si-empty\">Completed-D1 chart cutoff is unavailable.</p>";
            return;
        }
        if (!allCandles.length) {
            host.innerHTML = "<p class=\"si-empty\">No valid completed D1 candles available for charting.</p>";
            return;
        }
        const reconciliation = siChartReconciliation(prepared, d1);
        if (!reconciliation.closeMatches) {
            host.innerHTML = `<p class="si-empty">D1 chart unavailable: candle close does not reconcile with Stock 360 at ${siText(prepared.cutoff)}.</p>`;
            return;
        }
        const visibleCount = siChartWindowCount(windowKey, allCandles.length);
        const visibleStart = allCandles.length - visibleCount;
        const candles = allCandles.slice(visibleStart);
        const visibleSma20 = prepared.sma20.slice(visibleStart);
        const visibleSma50 = prepared.sma50.slice(visibleStart);
        const measuredWidth = Math.round(host.clientWidth || 840);
        const compact = measuredWidth < 520;
        const width = Math.max(200, measuredWidth);
        const height = compact ? 350 : width < 900 ? 420 : 460;
        const margin = compact
            ? {
                top: 12,
                right: 12,
                bottom: 34,
                left: width < 280 ? 32 : 40,
            }
            : { top: 18, right: 112, bottom: 28, left: 58 };
        const plotWidth = width - margin.left - margin.right;
        const volumeHeight = compact ? 44 : 60;
        const volumeBottom = height - margin.bottom;
        const volumeTop = volumeBottom - volumeHeight;
        const priceHeight = volumeTop - margin.top - (compact ? 14 : 18);
        const levels = siChartLevels(d1);
        const plotted20 = reconciliation.sma20Matches === false ? visibleSma20.map(() => null) : visibleSma20;
        const plotted50 = reconciliation.sma50Matches === false ? visibleSma50.map(() => null) : visibleSma50;
        const priceValues = [
            ...candles.flatMap(candle => [candle.low, candle.high]),
            ...plotted20.filter(value => value != null),
            ...plotted50.filter(value => value != null),
            ...levels.flatMap(level => [level.lower, level.upper]),
        ];
        const priceScale = siChartPriceScale(priceValues, compact ? 2 : 4);
        const minPrice = priceScale.min;
        const maxPrice = priceScale.max;
        const y = price => margin.top + ((maxPrice - Number(price)) / (maxPrice - minPrice)) * priceHeight;
        const slot = plotWidth / candles.length;
        const bodyWidth = Math.max(1.8, Math.min(7, slot * 0.66));
        const xAt = index => margin.left + slot * index + slot / 2;
        const maxVol = Math.max(...candles.map(candle => candle.volume), 1);
        const grid = priceScale.ticks.map(price => {
            const gridY = y(price);
            return `<line class="si-chart-grid" x1="${margin.left}" y1="${gridY}" x2="${margin.left + plotWidth}" y2="${gridY}"/>
                <text class="si-chart-axis" x="${margin.left - (compact ? 4 : 8)}" y="${gridY + 3}" text-anchor="end">${siChartAxisPrice(price, priceScale.step)}</text>`;
        }).join("");
        const bodies = candles.map((candle, index) => {
            const x = xAt(index);
            const up = candle.close >= candle.open;
            const top = y(Math.max(candle.open, candle.close));
            const bottom = y(Math.min(candle.open, candle.close));
            const volH = candle.volume / maxVol * volumeHeight;
            const tone = up ? "up" : "down";
            return `<g class="si-chart-candle ${tone}" data-si-candle-index="${index}">
                <line x1="${x}" y1="${y(candle.high)}" x2="${x}" y2="${y(candle.low)}"/>
                <rect x="${x - bodyWidth / 2}" y="${top}" width="${bodyWidth}" height="${Math.max(1, bottom - top)}"/>
                <rect class="si-chart-volume" x="${x - bodyWidth / 2}" y="${volumeTop + volumeHeight - volH}" width="${bodyWidth}" height="${volH}"/>
            </g>`;
        }).join("");
        const levelBands = levels.map(level => {
            const upperY = y(level.upper);
            const lowerY = y(level.lower);
            const hitY = Math.min(upperY, lowerY) - 6;
            const hitHeight = Math.max(12, Math.abs(lowerY - upperY) + 12);
            const accessible = `${level.label}, ${siZoneShort(level)}. Source: Portfolio Structural Review. Completed D1.`;
            if (siChartSameDisplayedPrice(level.lower, level.upper)) {
                return `<g class="si-chart-level" data-si-level="${level.short}" tabindex="0" role="button" aria-label="${siEscape(accessible)}">
                    <line class="si-chart-level-emphasis" x1="${margin.left}" y1="${upperY}" x2="${margin.left + plotWidth}" y2="${upperY}"/>
                    <line class="si-chart-level-line" x1="${margin.left}" y1="${upperY}" x2="${margin.left + plotWidth}" y2="${upperY}"/>
                    <rect class="si-chart-level-hit" x="${margin.left}" y="${hitY}" width="${plotWidth}" height="${hitHeight}"/>
                </g>`;
            }
            const visualTop = Math.min(upperY, lowerY);
            const visualHeight = Math.max(6, Math.abs(lowerY - upperY));
            const visualY = (upperY + lowerY) / 2 - visualHeight / 2;
            return `<g class="si-chart-level" data-si-level="${level.short}" tabindex="0" role="button" aria-label="${siEscape(accessible)}">
                <rect class="si-chart-level-emphasis" x="${margin.left}" y="${visualY}" width="${plotWidth}" height="${visualHeight}"/>
                <rect class="si-chart-level-band" x="${margin.left}" y="${visualTop}" width="${plotWidth}" height="${Math.max(1, Math.abs(lowerY - upperY))}"/>
                <line class="si-chart-level-edge" x1="${margin.left}" y1="${upperY}" x2="${margin.left + plotWidth}" y2="${upperY}"/>
                <line class="si-chart-level-edge" x1="${margin.left}" y1="${lowerY}" x2="${margin.left + plotWidth}" y2="${lowerY}"/>
                <rect class="si-chart-level-hit" x="${margin.left}" y="${hitY}" width="${plotWidth}" height="${hitHeight}"/>
            </g>`;
        }).join("");
        const last = candles[candles.length - 1];
        const lastY = y(last.close);
        const levelLabels = levels.map(level => {
            const naturalY = (y(level.lower) + y(level.upper)) / 2;
            const placement = siChartPlaceLevelTag(
                naturalY,
                lastY,
                margin.top,
                margin.top + priceHeight
            );
            const markerY = placement.labelY;
            const markerX = margin.left + plotWidth + 7;
            return `<g class="si-chart-level-tag" data-si-level-tag="${level.short}" aria-hidden="true">
                <line class="si-chart-level-connector" x1="${margin.left + plotWidth}" y1="${naturalY}" x2="${markerX}" y2="${markerY}"/>
                <circle class="si-chart-level-anchor" cx="${margin.left + plotWidth}" cy="${naturalY}" r="3"/>
                <rect class="si-chart-level-label-bg" x="${markerX}" y="${markerY - 12}" width="52" height="24" rx="4"/>
                <text class="si-chart-level-label" x="${markerX + 26}" y="${markerY + 4}" text-anchor="middle">${level.short}</text>
            </g>`;
        }).join("");
        const sma20Path = siChartPath(plotted20, xAt, y);
        const sma50Path = siChartPath(plotted50, xAt, y);
        const dateTickIndices = siChartDateTickIndices(candles.length, compact, width >= 1180);
        const dateLabels = dateTickIndices.map((index, tickIndex) => {
            const anchor = tickIndex === 0 ? "start" : tickIndex === dateTickIndices.length - 1 ? "end" : "middle";
            return `<text class="si-chart-axis si-chart-date-axis" x="${xAt(index)}" y="${height - 8}" text-anchor="${anchor}">${candles[index].date}</text>`;
        }).join("");
        const notes = [];
        if (prepared.excludedAfterCutoff) notes.push(`${prepared.excludedAfterCutoff} later/current-session row(s) excluded`);
        if (prepared.invalidCount) notes.push(`${prepared.invalidCount} invalid row(s) excluded`);
        if (reconciliation.sma20Matches === false || reconciliation.sma50Matches === false) {
            notes.push("SMA overlay hidden: final value did not reconcile with Stock 360");
        } else if ((reconciliation.final20 != null && reconciliation.sma20Matches == null) || (reconciliation.final50 != null && reconciliation.sma50Matches == null)) {
            notes.push("SMA plotted from completed-D1 closes; Stock 360 comparison value unavailable");
        }
        const legend20 = reconciliation.sma20Matches === false ? "COHERENCE UNAVAILABLE" : reconciliation.final20 == null ? `Unavailable (${candles.length}/20 closes)` : siMoney(reconciliation.final20);
        const legend50 = reconciliation.sma50Matches === false ? "COHERENCE UNAVAILABLE" : reconciliation.final50 == null ? `Unavailable (${candles.length}/50 closes)` : siMoney(reconciliation.final50);
        const subtitle = card && card.querySelector(".si-chart-subtitle");
        if (subtitle) {
            subtitle.textContent = `Through ${siChartLongDate(last.date)} · ${candles.length} shown`;
        }
        if (controlsSlot) {
            controlsSlot.innerHTML = `<div class="si-chart-controls">
                <div class="si-chart-window" role="group" aria-label="Visible completed-D1 window">
                    ${["3M", "6M", "ALL"].map(key => `<button type="button" data-si-chart-window="${key}" aria-pressed="${key === windowKey ? "true" : "false"}" class="${key === windowKey ? "active" : ""}">${key === "ALL" ? "All" : key}</button>`).join("")}
                </div>
                ${levels.length ? `<div class="si-chart-level-control">
                    <button type="button" class="si-chart-level-toggle" aria-expanded="false" aria-haspopup="listbox" aria-controls="si-chart-level-menu" title="Browse approved structural levels"><span>Levels</span><b>${levels.length}</b><i aria-hidden="true">⌄</i></button>
                    <div class="si-chart-level-menu" id="si-chart-level-menu" role="listbox" aria-label="Approved structural levels" hidden>
                        ${levels.map(level => `<button type="button" role="option" aria-selected="false" data-si-level-choice="${level.short}" aria-label="${siEscape(`${level.label}, ${siZoneShort(level)}. Source: Portfolio Structural Review.`)}"><span>${siEscape(level.label)}</span><b>${siEscape(siChartAxisZone(level))}</b></button>`).join("")}
                    </div>
                </div>` : ""}
            </div>`;
        }
        host.innerHTML = `<div class="si-chart-toolbar" aria-label="Chart legend">
            <span class="si-chart-legend-item sma20"><i aria-hidden="true"></i><b>SMA20</b> ${legend20}</span>
            <span class="si-chart-legend-item sma50"><i aria-hidden="true"></i><b>SMA50</b> ${legend50}</span>
            <span class="si-chart-legend-item close"><i aria-hidden="true"></i><b>Completed D1</b> ${siMoney(last.close)}</span>
        </div>
        <div class="si-chart-stage">
            <div class="si-chart-inspection" id="si-chart-inspection" aria-live="polite">${siChartInspectionHtml(last, reconciliation.sma20Matches === false ? null : reconciliation.final20, reconciliation.sma50Matches === false ? null : reconciliation.final50)}</div>
            <div class="si-chart-level-inspection" id="si-chart-level-inspection" aria-live="polite" hidden></div>
            <svg class="si-chart" style="--si-chart-height:${height}px" viewBox="0 0 ${width} ${height}" tabindex="0" role="group" aria-label="Completed D1 candlestick chart from ${siEscape(candles[0].date)} through ${siEscape(last.date)}. ${levels.length} approved structural levels are available. Use Left and Right arrow keys to inspect sessions." aria-describedby="si-chart-inspection">
            ${grid}
            ${levelBands}
            ${bodies}
            ${sma20Path ? `<path class="si-chart-sma20" d="${sma20Path}"/>` : ""}
            ${sma50Path ? `<path class="si-chart-sma50" d="${sma50Path}"/>` : ""}
            <line class="si-chart-close-line" x1="${margin.left + plotWidth - (compact ? 34 : 52)}" y1="${lastY}" x2="${margin.left + plotWidth}" y2="${lastY}"/>
            <g class="si-chart-close-tag" aria-label="Completed D1 close ${siMoney(last.close)}">
                <line x1="${margin.left + plotWidth}" y1="${lastY}" x2="${margin.left + plotWidth + (compact ? 0 : 7)}" y2="${lastY}"/>
                <rect x="${compact ? margin.left + plotWidth - 48 : margin.left + plotWidth + 7}" y="${lastY - 9}" width="${compact ? 48 : 88}" height="18" rx="3"/>
                <text x="${compact ? margin.left + plotWidth - 24 : margin.left + plotWidth + 51}" y="${lastY + 3}" text-anchor="middle">D1 · ${compact ? Math.round(last.close).toLocaleString("en-IN") : siMoney(last.close)}</text>
            </g>
            <line class="si-chart-crosshair" x1="${xAt(candles.length - 1)}" y1="${margin.top}" x2="${xAt(candles.length - 1)}" y2="${volumeTop + volumeHeight}"/>
            ${levelLabels}
            <line class="si-chart-pane-separator" x1="${margin.left}" y1="${volumeTop - 9}" x2="${margin.left + plotWidth}" y2="${volumeTop - 9}"/>
            <line class="si-chart-volume-baseline" x1="${margin.left}" y1="${volumeTop + volumeHeight}" x2="${margin.left + plotWidth}" y2="${volumeTop + volumeHeight}"/>
            <text class="si-chart-volume-label" x="${margin.left}" y="${volumeTop - 3}">VOLUME</text>
            ${dateLabels}
            </svg>
        </div>
        ${notes.length ? `<p class="si-chart-note">${siEscape(notes.join(" · "))}</p>` : ""}`;
        const svg = host.querySelector("svg.si-chart");
        const crosshair = svg && svg.querySelector(".si-chart-crosshair");
        const inspection = host.querySelector(".si-chart-inspection");
        const levelInspection = host.querySelector(".si-chart-level-inspection");
        const levelToggle = controlsSlot && controlsSlot.querySelector(".si-chart-level-toggle");
        const levelMenu = controlsSlot && controlsSlot.querySelector(".si-chart-level-menu");
        let selectedIndex = candles.length - 1;
        const levelInteraction = siChartCreateLevelInteraction(
            levels.map(level => level.short),
            retainedPersistentLevel
        );
        const selectIndex = value => {
            selectedIndex = Math.max(0, Math.min(candles.length - 1, value));
            const selectedX = xAt(selectedIndex);
            if (crosshair) {
                crosshair.setAttribute("x1", selectedX);
                crosshair.setAttribute("x2", selectedX);
            }
            if (inspection) {
                inspection.innerHTML = siChartInspectionHtml(
                    candles[selectedIndex],
                    reconciliation.sma20Matches === false ? null : visibleSma20[selectedIndex],
                    reconciliation.sma50Matches === false ? null : visibleSma50[selectedIndex]
                );
            }
            svg?.querySelectorAll(".si-chart-candle").forEach((candle, index) => {
                candle.classList.toggle("is-selected", index === selectedIndex);
            });
            if (inspection && !compact) {
                inspection.style.left = `${selectedX + 12}px`;
                inspection.classList.toggle("place-left", selectedX > margin.left + plotWidth * 0.64);
            }
        };
        const syncActiveLevel = () => {
            const state = levelInteraction.snapshot();
            const level = levels.find(item => item.short === state.activeLevelId) || null;
            host.classList.toggle("is-level-active", Boolean(level));
            host.classList.toggle(
                "is-level-pinned",
                Boolean(level && state.persistentLevelId === state.activeLevelId && !state.transientLevelId)
            );
            svg?.querySelectorAll(".si-chart-level").forEach(element => {
                element.classList.toggle("is-inspected", element.getAttribute("data-si-level") === state.activeLevelId);
            });
            host.querySelectorAll(".si-chart-level-tag").forEach(element => {
                element.classList.toggle(
                    "is-inspected",
                    !compact && element.getAttribute("data-si-level-tag") === state.activeLevelId
                );
            });
            levelMenu?.querySelectorAll("[data-si-level-choice]").forEach(element => {
                const short = element.getAttribute("data-si-level-choice");
                const active = short === state.activeLevelId;
                const selected = short === state.persistentLevelId;
                element.classList.toggle("active", active);
                element.classList.toggle("is-selected", selected);
                element.setAttribute("aria-selected", selected ? "true" : "false");
            });
            host._siChartPersistentLevelId = state.persistentLevelId;
            if (!levelInspection) return;
            const compactMenuPreview = compact
                && Boolean(state.transientSource && state.transientSource.startsWith("menu"));
            levelInspection.hidden = !level || compactMenuPreview;
            levelInspection.classList.toggle(
                "place-low",
                Boolean(level && (y(level.lower) + y(level.upper)) / 2 < margin.top + priceHeight / 2)
            );
            levelInspection.innerHTML = level
                ? `<b>${siEscape(level.label)}</b><span>${siZoneShort(level)}</span><small>Portfolio Structural Review</small><small>Completed D1</small>`
                : "";
        };
        const previewLevel = (short, source) => {
            levelInteraction.preview(short, source);
            syncActiveLevel();
        };
        const clearLevelPreview = source => {
            levelInteraction.clearPreview(source);
            syncActiveLevel();
        };
        const selectLevel = (short, source) => {
            levelInteraction.select(short, source);
            syncActiveLevel();
        };
        const clearAllLevels = () => {
            levelInteraction.clearAll();
            syncActiveLevel();
        };
        const closeLevelMenu = () => {
            if (!levelToggle || !levelMenu) return;
            levelToggle.setAttribute("aria-expanded", "false");
            levelMenu.hidden = true;
            host.classList.remove("is-level-menu-open");
            const state = levelInteraction.snapshot();
            if (state.transientSource && state.transientSource.startsWith("menu")) {
                levelInteraction.clearPreview(state.transientSource);
                syncActiveLevel();
            }
        };
        if (svg) {
            let pinnedCandle = false;
            const setCandleInspectionActive = active => {
                host.classList.toggle("is-candle-active", active);
            };
            const inspectPointer = event => {
                const bounds = svg.getBoundingClientRect();
                if (!bounds.width) return;
                const viewX = (event.clientX - bounds.left) * width / bounds.width;
                selectIndex(Math.round((viewX - margin.left - slot / 2) / slot));
                setCandleInspectionActive(true);
            };
            const pointerLevel = event => {
                const bounds = svg.getBoundingClientRect();
                if (!bounds.height) return null;
                const viewY = (event.clientY - bounds.top) * height / bounds.height;
                return siChartResolveLevelAtY(levels, viewY, y, compact ? 9 : 7);
            };
            svg.addEventListener("pointerdown", event => {
                const level = pointerLevel(event);
                svg.classList.toggle("is-level-hover", Boolean(level));
                if (level) {
                    event.preventDefault();
                    pinnedCandle = false;
                    setCandleInspectionActive(false);
                    selectLevel(level.short, event.pointerType === "mouse" ? "chart-click" : "touch");
                    closeLevelMenu();
                    return;
                }
                clearAllLevels();
                closeLevelMenu();
                pinnedCandle = true;
                inspectPointer(event);
            });
            svg.addEventListener("pointermove", event => {
                if (event.pointerType !== "mouse") return;
                const level = pointerLevel(event);
                if (level) {
                    setCandleInspectionActive(false);
                    previewLevel(level.short, "chart-hover");
                } else {
                    clearLevelPreview("chart-hover");
                    inspectPointer(event);
                }
            });
            svg.addEventListener("pointerleave", () => {
                svg.classList.remove("is-level-hover");
                clearLevelPreview("chart-hover");
                if (!pinnedCandle && document.activeElement !== svg) setCandleInspectionActive(false);
            });
            svg.addEventListener("focus", () => {
                selectIndex(selectedIndex);
                setCandleInspectionActive(true);
            });
            svg.addEventListener("blur", () => {
                if (!pinnedCandle) setCandleInspectionActive(false);
            });
            svg.addEventListener("keydown", event => {
                if (event.key === "Escape") {
                    pinnedCandle = false;
                    setCandleInspectionActive(false);
                    clearAllLevels();
                    closeLevelMenu();
                    return;
                }
                if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                event.preventDefault();
                setCandleInspectionActive(true);
                if (event.key === "Home") selectIndex(0);
                else if (event.key === "End") selectIndex(candles.length - 1);
                else selectIndex(selectedIndex + (event.key === "ArrowLeft" ? -1 : 1));
            });
            svg.querySelectorAll(".si-chart-level").forEach(element => {
                const short = element.getAttribute("data-si-level");
                element.addEventListener("focus", () => previewLevel(short, "level-focus"));
                element.addEventListener("blur", () => clearLevelPreview("level-focus"));
                element.addEventListener("keydown", event => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        selectLevel(short, "keyboard");
                    } else if (event.key === "Escape") {
                        event.preventDefault();
                        clearAllLevels();
                    }
                });
            });
        }
        controlsSlot?.querySelectorAll("[data-si-chart-window]").forEach(button => {
            button.addEventListener("click", () => {
                const nextWindow = button.getAttribute("data-si-chart-window") || "6M";
                renderSiD1Chart(host, series, d1, nextWindow);
            });
        });
        if (levelToggle && levelMenu) {
            levelToggle.addEventListener("click", () => {
                const expanded = levelToggle.getAttribute("aria-expanded") !== "true";
                levelToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
                levelMenu.hidden = !expanded;
                host.classList.toggle("is-level-menu-open", expanded);
                if (!expanded) closeLevelMenu();
                if (expanded) {
                    const selected = levelInteraction.snapshot().persistentLevelId;
                    const target = selected
                        ? levelMenu.querySelector(`[data-si-level-choice="${selected}"]`)
                        : levelMenu.querySelector("[data-si-level-choice]");
                    target?.focus();
                }
            });
            levelMenu.querySelectorAll("[data-si-level-choice]").forEach(button => {
                const short = button.getAttribute("data-si-level-choice");
                button.addEventListener("pointerenter", () => previewLevel(short, "menu-hover"));
                button.addEventListener("pointerleave", () => clearLevelPreview("menu-hover"));
                button.addEventListener("focus", () => previewLevel(short, "menu-focus"));
                button.addEventListener("blur", () => clearLevelPreview("menu-focus"));
                button.addEventListener("click", () => {
                    selectLevel(short, "menu-selection");
                    if (compact) closeLevelMenu();
                });
            });
            levelMenu.addEventListener("keydown", event => {
                if (event.key !== "Escape") return;
                event.preventDefault();
                clearAllLevels();
                closeLevelMenu();
                levelToggle.focus();
            });
            levelMenu.addEventListener("focusout", event => {
                if (!levelMenu.contains(event.relatedTarget) && event.relatedTarget !== levelToggle) closeLevelMenu();
            });
        }
        syncActiveLevel();
        siChartOutsidePointerHandler = event => {
            if (card && card.contains(event.target)) return;
            closeLevelMenu();
        };
        document.addEventListener("pointerdown", siChartOutsidePointerHandler);
        host._siChartWindowKey = windowKey;
        host._siChartRenderWidth = measuredWidth;
        if (!host._siChartResizeObserver && typeof ResizeObserver !== "undefined") {
            host._siChartResizeObserver = new ResizeObserver(entries => {
                const nextWidth = Math.round(entries[0] && entries[0].contentRect.width || 0);
                if (!nextWidth || Math.abs(nextWidth - host._siChartRenderWidth) < 2) return;
                requestAnimationFrame(() => renderSiD1Chart(
                    host,
                    series,
                    d1,
                    host._siChartWindowKey || "6M"
                ));
            });
            host._siChartResizeObserver.observe(host);
        }
    }

    async function loadSiD1Chart(instrumentId, d1, generation) {
        const host = document.getElementById("si-d1-chart-host");
        if (!host || !instrumentId) return;
        try {
            const payload = await apiRequest(
                `/api/v1/market/instruments/${encodeURIComponent(instrumentId)}/candles?timeframe=1d&limit=180`,
                { skipToast: true }
            );
            if (generation !== siLoadGeneration) return;
            const liveHost = document.getElementById("si-d1-chart-host");
            if (!liveHost) return;
            renderSiD1Chart(liveHost, payload && payload.data, d1);
        } catch (_err) {
            if (generation !== siLoadGeneration) return;
            const liveHost = document.getElementById("si-d1-chart-host");
            if (liveHost) {
                liveHost.innerHTML = "<p class=\"si-empty\">D1 chart could not be loaded from persisted candles.</p>";
            }
        }
    }

    function renderSymbolIntelligence(bundle) {
        siBundle = bundle;
        const identityEl = document.getElementById("si-identity");
        const bundleEl = document.getElementById("si-bundle");
        if (!identityEl || !bundleEl) return;
        identityEl.innerHTML = siHeader(bundle);
        const d1 = bundle.d1 || {};
        const identity = bundle.identity || {};
        bundleEl.innerHTML = `
            <section class="si-section" data-si-panel="stock-360">
                ${siCoverageBanner(bundle)}
                ${identity.resolved ? siScanStrip(bundle) : ""}
                ${identity.resolved ? `<div class="si-360-stack">
                    ${siLevelsCard(d1)}
                    ${siAthenaView(bundle.decision)}
                </div>` : ""}
                ${siChartBlock(identity, d1)}
                ${identity.resolved ? `<details class="si-written-summary" open>
                    <summary>Research Brief</summary>
                    ${siCompleteReview(bundle)}
                </details>
                <div class="si-360-secondary">
                    ${siPortfolioCard(bundle.portfolio)}
                    ${siAvailabilityChips(bundle)}
                    ${siDarvaxOverview(bundle.darvax)}
                </div>` : ""}
            </section>
            <section class="si-section" data-si-panel="decision" hidden>${siDecisionCard(bundle)}</section>
            <section class="si-section" data-si-panel="experimental" hidden>${siDarvaxCard(bundle.darvax)}</section>
            <section class="si-section" data-si-panel="audit" hidden>${siAuditTable(bundle)}</section>`;
        showSiSection(document.querySelector(".si-section-nav-item.active")?.getAttribute("data-si-section") || "stock-360");
        bindDarvaxFrame();
        if (identity.resolved && identity.instrument_id && d1.present) {
            loadSiD1Chart(identity.instrument_id, d1, siLoadGeneration);
        }
    }

    function siErrorText(err) {
        if (err == null) return "COMPOSITION_UNAVAILABLE";
        const detail = err.data && err.data.detail;
        if (typeof detail === "string" && detail.trim()) return detail;
        if (detail && typeof detail === "object") {
            const titled = detail.title || detail.code || detail.detail;
            if (titled) return String(titled);
        }
        if (typeof err.userMessage === "string" && err.userMessage.trim()) return err.userMessage;
        if (typeof err.message === "string" && err.message.trim()) return err.message;
        if (err.status) return `API_ERROR (${err.status})`;
        return "COMPOSITION_UNAVAILABLE";
    }

    function siIsAbortError(err) {
        if (!err) return false;
        if (err.name === "AbortError") return true;
        const message = String(err.message || "");
        return message === "AbortError" || /aborted|AbortError/i.test(message);
    }

    function siShowWorkspaceError(code, detail) {
        siBundle = null;
        const identityEl = document.getElementById("si-identity");
        const bundleEl = document.getElementById("si-bundle");
        if (identityEl) identityEl.innerHTML = "";
        if (bundleEl) {
            bundleEl.innerHTML = `<div class="si-card"><h3>${siEscape(code)}</h3>
                <p class="si-unavailable">${siEscape(detail)}</p></div>`;
        }
    }

    async function loadSymbolIntelligence(query, options = {}) {
        const analyze = options.analyze === true;
        const needle = siNormalizedQuery(query);
        if (analyze && siShouldSuppressAnalyze(needle)) return;
        const input = document.getElementById("si-symbol-input");
        if (input && needle) input.value = needle;
        const hitsEl = document.querySelector("#si-search-hits");
        if (hitsEl) { hitsEl.hidden = true; hitsEl.innerHTML = ""; }
        const generation = ++siLoadGeneration;
        if (siInFlightController) {
            siInFlightController.abort();
        }
        siInFlightController = new AbortController();
        const signal = siInFlightController.signal;
        if (!needle) {
            siShowWorkspaceError("EMPTY_SYMBOL", "Enter EXCHANGE:SYMBOL or an unambiguous ticker, then Analyze.");
            siSetInFlight("");
            return;
        }
        siQuery = needle;
        siSetInFlight(analyze ? "ANALYZE" : "GET", needle);
        const bundleEl = document.getElementById("si-bundle");
        const identityEl = document.getElementById("si-identity");
        if (identityEl) identityEl.innerHTML = "";
        if (bundleEl) {
            bundleEl.innerHTML = analyze
                ? "<p class=\"text-muted\">Refreshing D1 history… Analyzing…</p>"
                : "<p class=\"text-muted\">Loading persisted Symbol Intelligence…</p>";
        }
        const path = `/api/v1/symbol-intelligence/${encodeURIComponent(needle)}`;
        let payload = null;
        let processNeedsRestart = false;
        try {
            try {
                if (analyze) {
                    payload = await apiRequest(path, { method: "POST", body: "{}", skipToast: true, signal });
                } else {
                    payload = await apiRequest(path, { skipToast: true, signal });
                }
            } catch (err) {
                if (analyze && err && Number(err.status) === 405) {
                    processNeedsRestart = true;
                    payload = await apiRequest(path, { skipToast: true, signal });
                } else {
                    throw err;
                }
            }
            if (generation !== siLoadGeneration) return;
            const bundle = payload && payload.data;
            if (!bundle) {
                siShowWorkspaceError("COMPOSITION_UNAVAILABLE", "Symbol Intelligence returned an empty payload.");
                return;
            }
            renderSymbolIntelligence(bundle);
            if (processNeedsRestart) {
                const header = document.getElementById("si-identity");
                if (header) {
                    header.insertAdjacentHTML("afterbegin",
                        `<p class="si-unavailable">This running ATHENA process does not yet accept Analyze (POST). Restart the server to hydrate stale D1. Showing persisted read-only composition.</p>`);
                }
            }
            const url = new URL(window.location.href);
            if (url.pathname.includes("symbol-intelligence")) {
                url.searchParams.set("symbol", needle);
                window.history.replaceState({ tabId: "symbol-intelligence" }, "", url);
            }
        } catch (err) {
            if (generation !== siLoadGeneration) return;
            if (siIsAbortError(err)) return;
            const status = Number(err && err.status);
            if (status === 405) {
                siShowWorkspaceError(
                    "RESTART_REQUIRED",
                    "Analyze uses POST. This ATHENA process is still the previous API (GET only). Restart the server so D1 hydration is loaded."
                );
                return;
            }
            siShowWorkspaceError("API_ERROR", siErrorText(err));
        } finally {
            if (generation === siLoadGeneration) {
                siSetInFlight("");
            }
        }
    }

    function requestSymbolIntelligenceLoad(event) {
        if (event) event.preventDefault();
        const input = document.getElementById("si-symbol-input");
        loadSymbolIntelligence(input ? input.value : "", { analyze: true });
    }

    function siCurrentSymbolQuery() {
        if (siQuery) return siQuery;
        const identity = siBundle && siBundle.identity;
        return (identity && (identity.instrument_id || identity.symbol)) || "";
    }

    function requestSymbolIntelligenceRefresh(event) {
        if (event) event.preventDefault();
        const current = siCurrentSymbolQuery();
        if (!current) return;
        loadSymbolIntelligence(current);
    }

    function siClearWorkspace(event) {
        if (event) event.preventDefault();
        siLoadGeneration++;
        if (siInFlightController) {
            siInFlightController.abort();
            siInFlightController = null;
        }
        siBundle = null;
        siQuery = "";
        const input = document.getElementById("si-symbol-input");
        if (input) input.value = "";
        const hitsEl = document.querySelector("#si-search-hits");
        if (hitsEl) { hitsEl.hidden = true; hitsEl.innerHTML = ""; }
        const identityEl = document.getElementById("si-identity");
        if (identityEl) identityEl.innerHTML = "";
        const bundleEl = document.getElementById("si-bundle");
        if (bundleEl) {
            bundleEl.innerHTML = `<p class="text-muted si-empty-state">Enter a canonical instrument to load persisted Symbol Intelligence. Analyze hydrates stale D1 when you need a refresh.</p>`;
        }
        const url = new URL(window.location.href);
        if (url.searchParams.has("symbol")) {
            url.searchParams.delete("symbol");
            window.history.replaceState({ tabId: "symbol-intelligence" }, "", url);
        }
        siSetInFlight("");
        if (input) input.focus();
    }

    async function searchSymbolIntelligence(query) {
        const hitsEl = document.getElementById("si-search-hits");
        if (!hitsEl) return;
        const needle = String(query || "").trim();
        if (needle.length < 1) {
            hitsEl.hidden = true;
            hitsEl.innerHTML = "";
            return;
        }
        try {
            const payload = await apiRequest(`/api/v1/symbol-intelligence/search?q=${encodeURIComponent(needle)}`);
            const hits = (payload.data && payload.data.hits) || [];
            if (!hits.length) {
                hitsEl.hidden = false;
                hitsEl.innerHTML = "<span class=\"text-muted\">No catalog matches.</span>";
                return;
            }
            hitsEl.hidden = false;
            hitsEl.innerHTML = hits.map(hit => (
                `<button type="button" class="si-search-hit" data-si-id="${siEscape(hit.instrument_id)}">
                    <span class="si-search-hit-symbol">${siText(hit.instrument_id)}</span>
                    ${hit.name ? `<span class="si-search-hit-name">${siText(hit.name)}</span>` : ""}
                </button>`
            )).join("");
        } catch (err) {
            hitsEl.hidden = false;
            hitsEl.innerHTML = `<span class="si-unavailable">${siEscape(err && err.message || "Search failed")}</span>`;
        }
    }

    async function loadSymbolIntelligenceWorkspace() {
        // Revisiting this tab must never re-fetch or re-render on its own —
        // the pane's DOM survives a tab switch untouched, and an owner
        // flagged the previous always-reload-on-revisit behavior as
        // disruptive. Auto-load only ever fires once per page load, and
        // only to honor a deep-linked ?symbol= URL; every later visit while
        // a bundle is already held is a no-op, and refreshing afterwards is
        // an explicit Refresh/Analyze action.
        if (siBundle) return;
        const params = new URLSearchParams(window.location.search);
        const fromUrl = params.get("symbol");
        const input = document.getElementById("si-symbol-input");
        const next = fromUrl || (input && input.value.trim()) || "";
        if (next) {
            await loadSymbolIntelligence(next);
        }
    }

    document.getElementById("si-load-btn")?.addEventListener("click", requestSymbolIntelligenceLoad);
    document.getElementById("si-refresh-btn")?.addEventListener("click", requestSymbolIntelligenceRefresh);
    document.getElementById("si-clear-btn")?.addEventListener("click", siClearWorkspace);
    document.getElementById("si-symbol-input")?.addEventListener("keydown", event => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        requestSymbolIntelligenceLoad(event);
    });
    document.getElementById("si-symbol-input")?.addEventListener("input", event => {
        siSyncAnalyzeControl();
        clearTimeout(siSearchTimer);
        siSearchTimer = setTimeout(() => searchSymbolIntelligence(event.target.value), 200);
    });
    document.getElementById("si-search-hits")?.addEventListener("click", event => {
        const button = event.target.closest("[data-si-id]");
        if (!button) return;
        loadSymbolIntelligence(button.getAttribute("data-si-id"));
    });
    document.querySelector(".si-section-nav")?.addEventListener("click", event => {
        const item = event.target.closest(".si-section-nav-item");
        if (!item) return;
        showSiSection(item.getAttribute("data-si-section"));
    });
    document.getElementById("si-bundle")?.addEventListener("click", event => {
        const jump = event.target.closest("[data-si-jump]");
        if (!jump) return;
        showSiSection(jump.getAttribute("data-si-jump"));
    });

    // The sticky section-nav needs to know when it is actually stuck (vs.
    // sitting in normal flow just below the toolbar) so its CSS can seal the
    // scroll container's own top padding only while stuck -- otherwise that
    // fill would paint over the toolbar note text above it before scrolling.
    // Driven directly off scroll position (not IntersectionObserver): a
    // zero-height sentinel sits immediately before the bar in normal flow,
    // so once its own top has scrolled above the bar's stuck offset, the
    // bar is stuck.
    (function initSiNavStuckTracking() {
        const sentinel = document.getElementById("si-nav-sentinel");
        const nav = document.querySelector(".si-section-nav");
        const viewport = document.querySelector(".workspace-viewport");
        if (!sentinel || !nav || !viewport) return;
        let scheduled = false;
        function syncStuck() {
            scheduled = false;
            // The point nav sticks to (its CSS "top: 0") is fixed relative to
            // the viewport's own padding edge, which never moves on screen --
            // only its scrolled content does. The sentinel sits in normal
            // flow immediately before nav; once the sentinel's own top has
            // scrolled above that fixed point, nav has nowhere left to go
            // but to stay pinned there, i.e. it is stuck.
            const viewportRect = viewport.getBoundingClientRect();
            const paddingTop = parseFloat(getComputedStyle(viewport).paddingTop) || 0;
            const stickyThreshold = viewportRect.top + paddingTop;
            const sentinelTop = sentinel.getBoundingClientRect().top;
            nav.classList.toggle("is-stuck", sentinelTop < stickyThreshold);
        }
        function requestSync() {
            if (scheduled) return;
            scheduled = true;
            requestAnimationFrame(syncStuck);
        }
        viewport.addEventListener("scroll", requestSync, { passive: true });
        requestSync();
    })();
