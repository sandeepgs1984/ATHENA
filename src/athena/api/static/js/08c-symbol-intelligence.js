
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

    function siStructureDiffers(d1) {
        const sma = String((d1 && d1.symbol_trend) || "");
        const st = String((d1 && d1.supertrend_direction) || "");
        if (!sma || !st) return false;
        if (sma === "UPTREND" && st === "BEARISH") return true;
        if (sma === "DOWNTREND" && st === "BULLISH") return true;
        if (sma === "SIDEWAYS" && (st === "BULLISH" || st === "BEARISH")) return true;
        if (sma === "MIXED" && (st === "BULLISH" || st === "BEARISH")) return true;
        return false;
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

    function siJumpButton(section, label) {
        return `<button type="button" class="si-jump" data-si-jump="${siEscape(section)}">${siEscape(label)}</button>`;
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

    function siMetric(label, value, title) {
        const tip = title ? ` title="${siEscape(title)}"` : "";
        return `<div class="si-metric"${tip}><dt>${siEscape(label)}</dt><dd>${siText(value)}</dd></div>`;
    }

    function siZoneLooksEmpty(zone) {
        if (!zone) return true;
        const lower = zone.lower;
        const upper = zone.upper;
        return (lower == null || lower === "") && (upper == null || upper === "");
    }

    function siOptionalZoneMetric(label, zone) {
        if (siZoneLooksEmpty(zone)) return "";
        return siMetric(label, siZoneShort(zone));
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

    function siQuotePriceLabel(live) {
        if (!live || !live.present) return "Last completed D1";
        if (live.quote_kind === "LIVE") return "Live";
        return "Latest quote";
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
            btn.textContent = analyzeInFlight ? "Analyzing…" : "Analyze";
            btn.setAttribute("aria-busy", analyzeInFlight ? "true" : "false");
        }
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

    function siHeader(bundle) {
        const identity = bundle.identity || {};
        const d1 = bundle.d1 || {};
        const live = bundle.live || {};
        const price = live.present ? live.last_price : d1.close;
        const change = live.present ? siPct(live.change_pct) : "";
        const changeClass = Number(live.change_pct) > 0 ? "up" : Number(live.change_pct) < 0 ? "down" : "";
        const company = siCompanyName(identity);
        return `<div class="si-id-block">
                <div class="si-id-symbol">${siText(identity.symbol || identity.instrument_id, identity.query || "Unresolved")}</div>
                ${company ? `<div class="si-id-name">${siText(company, "")}</div>` : ""}
                <div class="si-id-meta">${siText(identity.exchange, "")}${identity.instrument_id ? ` · ${siText(identity.instrument_id)}` : ""}</div>
            </div>
            <div>
                <div class="si-id-price">${siMoney(price)}</div>
                <div class="si-id-change ${changeClass}">${siEscape(change)}</div>
                <div class="si-id-session">${siQuoteCaption(live)}</div>
                <div class="si-id-session">${siQuotePriceLabel(live)}</div>
            </div>
            <div>
                <div class="si-id-session">Completed D1 as-of: ${siDate(d1.latest_session)}</div>
                <div class="si-id-session">Last completed D1 close: ${siMoney(d1.close)}</div>
                ${identity.resolved ? "" : `<p class="si-unavailable">${siText(identity.unresolved_reason)}</p>`}
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
                <div>Market data: ${siEscape(market)}</div>
                <div>SI coverage: ${siEscape(coverage)}</div>
                ${decisionLine}
            </div>
            ${message ? `<p class="si-coverage-note">${siEscape(message)}</p>` : ""}
        </div>`;
    }

    function siPortfolioCard(portfolio) {
        if (!portfolio || portfolio.status === "NOT_HELD") {
            return `<div class="si-card"><h3>Portfolio Context</h3>
                <p class="si-empty">Not held in My Portfolio</p></div>`;
        }
        const banned = [portfolio.interpretation_status, portfolio.next_action, portfolio.daily_review_status]
            .filter(value => SI_HOLDING_GUIDANCE.has(String(value || "")));
        const interpretation = banned.length
            ? `<p class="si-empty">Held. Portfolio-owned status ${siText(portfolio.interpretation_status)}.</p>`
            : `<p class="si-empty">${siText(portfolio.interpretation_status)} · ${siText(portfolio.next_action)}</p>`;
        return `<div class="si-card"><h3>Portfolio Context</h3>
            <p class="si-pending">These facts are Portfolio-owned. Symbol Intelligence does not issue BUY/HOLD/SELL.</p>
            <dl class="si-metrics">
                ${siMetric("Quantity", siInteger(portfolio.quantity))}
                ${siMetric("Average", siMoney(portfolio.avg_price))}
                ${siMetric("Last", siMoney(portfolio.last_price))}
                ${siMetric("Current value", siMoney(portfolio.current_value))}
                ${siMetric("Investment", siMoney(portfolio.investment))}
                ${siMetric("P&L", `${siMoney(portfolio.pnl)}${siPct(portfolio.pnl_pct) ? ` (${siEscape(siPct(portfolio.pnl_pct))})` : ""}`)}
            </dl>
            ${interpretation}</div>`;
    }

    function siDecisionCard(decision) {
        if (!decision || !decision.present) {
            return `<div class="si-card"><h3>ATHENA Decision</h3>
                <p class="si-empty">ATHENA has not produced a Decision for this symbol.</p>
                <p class="si-pending">This does not limit Symbol Intelligence analysis. SI research remains available.</p></div>`;
        }
        const plan = decision.trade_plan;
        const openHref = `/dashboard/decisions?decision=${encodeURIComponent(decision.decision_id)}`;
        const score = siPersistedScore(decision);
        const gates = siGatePassSummary(decision);
        const freshness = decision.plan_freshness && decision.plan_freshness.status
            ? siMetric("Plan freshness", siEnumLabel(decision.plan_freshness.status))
            : "";
        return `<div class="si-card"><h3>ATHENA Decision</h3>
            <dl class="si-metrics">
                ${siMetric("Type", siEnumLabel(decision.decision_type))}
                ${siMetric("Direction", siEnumLabel(decision.direction))}
                ${siMetric("Confidence", decision.confidence_level)}
                ${score != null ? siMetric("Score", siScore(score)) : ""}
                ${gates ? siMetric("Gates", gates) : ""}
                ${siMetric("Decision as-of", siDate(decision.ts))}
                ${freshness}
            </dl>
            <p>${siText(siDisplayExplanation(decision.explanation))}</p>
            ${plan ? `<p>TradePlan ${siMoney(plan.entry_low)} / ${siMoney(plan.entry_high)}</p>` : ""}
            <p><a class="btn" href="${siEscape(openHref)}">Open Decision Brief</a></p></div>`;
    }

    function siAthenaView(decision) {
        if (!decision || !decision.present) {
            return `<div class="si-card si-athena-view"><h3>ATHENA View</h3>
                <p class="si-empty">ATHENA Decision</p>
                <p class="si-empty">Not available for this symbol</p>
                <p class="si-pending">Stock 360 research remains available. This is not an Analyze failure.</p>
                ${siJumpButton("decision", "Open ATHENA Decision")}
                ${siJumpButton("audit", "View evidence")}</div>`;
        }
        const openHref = `/dashboard/decisions?decision=${encodeURIComponent(decision.decision_id)}`;
        const score = siPersistedScore(decision);
        const gates = siGatePassSummary(decision);
        return `<div class="si-card si-athena-view"><h3>ATHENA View</h3>
            <dl class="si-metrics">
                ${siMetric("Decision", siEnumLabel(decision.decision_type))}
                ${siMetric("Confidence", decision.confidence_level)}
                ${score != null ? siMetric("Score", siScore(score)) : ""}
                ${gates ? siMetric("Gates", gates) : ""}
                ${siMetric("As-of", siDate(decision.ts))}
                ${decision.plan_freshness && decision.plan_freshness.status ? siMetric("Plan freshness", siEnumLabel(decision.plan_freshness.status)) : ""}
            </dl>
            <p>${siText(siDisplayExplanation(decision.explanation))}</p>
            <p class="si-actions">
                ${siJumpButton("decision", "Open ATHENA Decision")}
                <a class="btn" href="${siEscape(openHref)}">Open Decision Brief</a>
                ${siJumpButton("audit", "View evidence")}
            </p></div>`;
    }

    function siTrendCard(d1) {
        if (!d1 || !d1.present) {
            return `<div class="si-card"><h3>Technical Structure</h3><p class="si-empty">No completed D1 evidence.</p></div>`;
        }
        const differ = siStructureDiffers(d1);
        const note = differ
            ? `<p class="si-note" data-si-structure-note="disagree">Daily SMA structure and SuperTrend currently differ. They are independent measurements, not a blended verdict. Neither is treated as authoritative here.</p>`
            : `<p class="si-pending">SMA structure and SuperTrend are independent evidence. They are not blended.</p>`;
        return `<div class="si-card"><h3>Technical Structure</h3>
            <dl class="si-metrics">
                ${siMetric("Daily SMA structure", siSmaStructureLabel(d1.symbol_trend), d1.symbol_trend)}
                ${siMetric("SuperTrend (10,3)", siSuperTrendLabel(d1.supertrend_direction), d1.supertrend_direction)}
                ${siMetric("SuperTrend value", siMoney(d1.supertrend_value))}
                ${siMetric("SMA20", siMoney(d1.fast_sma))}
                ${siMetric("SMA50", siMoney(d1.slow_sma))}
            </dl>
            ${note}</div>`;
    }

    function siMomentumCard(bundle) {
        const d1 = bundle.d1 || {};
        return `<div class="si-card"><h3>Momentum / Participation</h3>
            <dl class="si-metrics">
                ${siMetric("RSI (14)", siRsi(d1.rsi14))}
                ${siMetric("Volume vs MA20", siVolumeVsMa20(d1))}
            </dl>
            <p class="si-pending">Volume vs 20D average uses completed-D1 volume against MA20. Momentum Quality is not yet methodologically defined.</p></div>`;
    }

    function siLevelRow(label, zone, close, { perspective, bound } = {}) {
        if (siZoneLooksEmpty(zone)) return "";
        const level = bound === "upper" ? zone.upper : zone.lower;
        const distLine = perspective === "close-vs-boundary"
            ? siCloseVsBoundarySentence(label, close, level)
            : siLevelVsCloseSentence(label, level, close);
        return `<div class="si-level-row">
            <div><dt>${siEscape(label)}</dt><dd>${siZoneShort(zone)}</dd></div>
            ${distLine ? `<p class="si-level-dist">${siEscape(distLine)}</p>` : ""}
        </div>`;
    }

    function siLevelsCard(d1) {
        const close = d1 && d1.close;
        const highLine = siLevelVsCloseSentence(
            "Available-history high",
            d1 && d1.available_history_high,
            close
        );
        return `<div class="si-card si-price-map"><h3>Price Map</h3>
            <p class="si-pending">Distances use completed-D1 close against completed-D1 levels. Live/latest quote is not mixed in.</p>
            <div class="si-level-list">
                ${siLevelRow("Support 1", d1 && d1.support_1, close, { perspective: "close-vs-boundary", bound: "upper" })}
                ${siLevelRow("Major support", d1 && d1.major_support, close, { perspective: "close-vs-boundary", bound: "upper" })}
                ${siLevelRow("Review trigger", d1 && d1.review_trigger, close, { perspective: "level-vs-close", bound: "lower" })}
                ${siLevelRow("Target 1", d1 && d1.target_1, close, { perspective: "level-vs-close", bound: "lower" })}
                ${siOptionalZoneMetric("Target 2", d1 && d1.target_2)}
                ${siOptionalZoneMetric("Target 3", d1 && d1.target_3)}
                ${d1 && d1.available_history_high != null ? `<div class="si-level-row">
                    <div><dt>Available-history high</dt><dd>${siMoney(d1.available_history_high)}</dd></div>
                    ${highLine ? `<p class="si-level-dist">${siEscape(highLine)}</p>` : ""}
                </div>` : ""}
            </div></div>`;
    }

    function siScanStrip(bundle) {
        const d1 = bundle.d1 || {};
        const decision = bundle.decision || {};
        const decisionLabel = decision.present ? siEnumLabel(decision.decision_type) : "Not available";
        return `<div class="si-scan-strip" aria-label="Compact technical snapshot">
            <div class="si-scan-item"><span>Daily SMA structure</span><strong title="${siEscape(d1.symbol_trend || "")}">${siSmaStructureLabel(d1.symbol_trend)}</strong></div>
            <div class="si-scan-item"><span>SuperTrend (10,3)</span><strong title="${siEscape(d1.supertrend_direction || "")}">${siSuperTrendLabel(d1.supertrend_direction)}</strong></div>
            <div class="si-scan-item"><span>RSI (14)</span><strong>${siRsi(d1.rsi14)}</strong></div>
            <div class="si-scan-item"><span>Volume vs MA20</span><strong>${siVolumeVsMa20(d1)}</strong></div>
            <div class="si-scan-item"><span>ATHENA Decision</span><strong>${siEscape(decisionLabel)}</strong></div>
        </div>`;
    }

    function siMarketSnapshot(bundle) {
        const d1 = bundle.d1 || {};
        const live = bundle.live || {};
        return `<div class="si-card"><h3>Market Snapshot</h3>
            <dl class="si-metrics">
                ${live.present ? siMetric(siQuotePriceLabel(live), siMoney(live.last_price)) : ""}
                ${live.present && siPct(live.change_pct) ? siMetric("Change", siPct(live.change_pct)) : ""}
                ${siMetric("Quote", siQuoteCaption(live))}
                ${siMetric("Completed D1 close", siMoney(d1.close))}
                ${siMetric("Completed D1 date", siDate(d1.latest_session))}
                ${d1.present ? siMetric("D1 open / high / low", `${siMoney(d1.open)} / ${siMoney(d1.high)} / ${siMoney(d1.low)}`) : ""}
                ${siMetric("Available-history high", siMoney(d1.available_history_high))}
            </dl>
            <p class="si-pending">Available-history high is prior persisted D1 history, not an official 52-week or all-time high.</p></div>`;
    }

    function siAvailabilityChips(bundle) {
        const fundamentals = bundle.fundamentals || {};
        const news = bundle.news || {};
        return `<div class="si-card si-capability"><h3>Capability availability</h3>
            <div class="si-availability-chips">
                <span class="si-chip">Fundamentals — Not ingested</span>
                <span class="si-chip">News &amp; catalysts — Not ingested</span>
            </div>
            <p class="si-pending">Not available yet. ${siText(fundamentals.status, "NOT_INGESTED")} / ${siText(news.status, "NOT_INGESTED")} are not errors.</p>
            ${siJumpButton("audit", "View evidence")}</div>`;
    }

    function siDarvaxOverview(darvax) {
        const label = siText(darvax && darvax.experimental_label, "EXPERIMENTAL_UNVALIDATED");
        if (!darvax || darvax.status !== "ENABLED_IFRAME") {
            return `<div class="si-card"><h3>DarvaX</h3>
                <p class="si-empty">DARVAX UNAVAILABLE</p>
                <p class="si-pending">${label}</p></div>`;
        }
        return `<div class="si-card"><h3>DarvaX</h3>
            <p class="si-empty">DarvaX experimental view available</p>
            <p class="si-empty">Symbol 360 is available on the DarvaX surface. It is not mixed into Stock 360 evidence.</p>
            <p class="si-pending">${label}</p>
            ${siJumpButton("experimental", "Open DarvaX")}</div>`;
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
                    ${siMarketSnapshot(bundle)}
                    ${siTrendCard(d1)}
                    ${siMomentumCard(bundle)}
                    ${siLevelsCard(d1)}
                    ${siAthenaView(bundle.decision)}
                </div>` : ""}
                ${siChartBlock(identity, d1)}
                ${identity.resolved ? `<details class="si-written-summary">
                    <summary>Written summary</summary>
                    ${siCompleteReview(bundle)}
                </details>
                <div class="si-360-secondary">
                    ${siPortfolioCard(bundle.portfolio)}
                    ${siAvailabilityChips(bundle)}
                    ${siDarvaxOverview(bundle.darvax)}
                </div>` : ""}
            </section>
            <section class="si-section" data-si-panel="decision" hidden>${siDecisionCard(bundle.decision)}</section>
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
                `<button type="button" class="si-search-hit" data-si-id="${siEscape(hit.instrument_id)}">${siText(hit.instrument_id)}${hit.name ? ` · ${siText(hit.name)}` : ""}</button>`
            )).join("");
        } catch (err) {
            hitsEl.hidden = false;
            hitsEl.innerHTML = `<span class="si-unavailable">${siEscape(err && err.message || "Search failed")}</span>`;
        }
    }

    async function loadSymbolIntelligenceWorkspace() {
        const params = new URLSearchParams(window.location.search);
        const fromUrl = params.get("symbol");
        const input = document.getElementById("si-symbol-input");
        const next = fromUrl || siQuery || (input && input.value.trim()) || "";
        if (next) {
            await loadSymbolIntelligence(next);
        } else if (siBundle) {
            renderSymbolIntelligence(siBundle);
        }
    }

    document.getElementById("si-load-btn")?.addEventListener("click", requestSymbolIntelligenceLoad);
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
