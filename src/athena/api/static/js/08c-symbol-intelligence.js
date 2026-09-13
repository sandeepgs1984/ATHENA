
    const SI_HOLDING_GUIDANCE = new Set([
        "HOLD_STRONG", "HOLD", "REVIEW_HOLD_TIGHT",
    ]);
    let siBundle = null;
    let siQuery = "";
    let siSearchTimer = null;
    let siLoadGeneration = 0;
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
        if (!btn) return;
        const input = document.getElementById("si-symbol-input");
        const typed = input ? siNormalizedQuery(input.value) : "";
        const duplicateAnalyze = siInFlightMode === "ANALYZE" && siSameQuery(typed, siInFlightQuery);
        btn.disabled = duplicateAnalyze;
        btn.setAttribute("aria-busy", duplicateAnalyze ? "true" : "false");
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
            <p class="si-pending">Volume vs 20D average uses completed-D1 volume against MA20. Momentum Quality is not defined.</p></div>`;
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
        return `<div class="si-card si-chart-card"><h3>Completed D1 chart</h3>
            <p class="si-pending">LAST COMPLETED D1 · unfinished session candles are excluded</p>
            <div class="si-chart-host si-chart-pending" id="si-d1-chart-host"><p class="text-muted">Loading D1 chart…</p></div>
        </div>`;
    }

    function siSentence(parts) {
        return parts.filter(Boolean).join(" ");
    }

    function siCompleteReview(bundle) {
        const d1 = bundle.d1 || {};
        const live = bundle.live || {};
        const decision = bundle.decision || {};
        const portfolio = bundle.portfolio || {};
        const darvax = bundle.darvax || {};
        const trend = d1.symbol_trend ? `Daily SMA structure is ${d1.symbol_trend}.` : "D1 SMA structure is unavailable.";
        const st = d1.supertrend_direction ? `SuperTrend (10,3) is ${String(d1.supertrend_direction).toLowerCase()}.` : "";
        const differ = siStructureDiffers(d1)
            ? "Those two measurements currently differ; they are not blended."
            : "";
        const rsi = d1.rsi14 != null ? `RSI (14) is ${siRsi(d1.rsi14)}.` : "RSI is unavailable.";
        const volume = `Volume vs MA20 is ${siVolumeVsMa20(d1)}.`;
        return `<div class="si-card si-review">
            <h3>Written summary</h3>
            <h4>Market Snapshot</h4>
            <p>${siSentence([
                live.present
                    ? `${live.quote_kind === "LIVE" ? "Live" : "Latest quote"} ${siMoney(live.last_price)} (${siText(live.label)}).`
                    : "No current/latest quote was captured; last completed D1 is shown.",
                d1.present ? `Last completed D1 close ${siMoney(d1.close)} on ${siDate(d1.latest_session)}.` : "No completed D1 bar is present.",
            ])}</p>
            <h4>Trend</h4><p>${siSentence([trend, st, differ])}</p>
            <h4>Momentum Evidence</h4><p>${rsi} ${volume} Momentum Quality is not yet methodologically defined.</p>
            <h4>Structure</h4><p>${d1.present ? `Available-history high ${siMoney(d1.available_history_high)}.` : "Structure unavailable."}</p>
            <h4>Key Levels</h4><p>Support 1 ${siZoneShort(d1.support_1)}. Review trigger ${siZoneShort(d1.review_trigger)}.</p>
            <h4>Entry Evidence</h4><p>Entry Quality is not yet methodologically defined. Named support/review levels are shown without a buy/wait verdict.</p>
            <h4>ATHENA Decision</h4>
            <p>${decision.present ? siText(siDisplayExplanation(decision.explanation)) : "ATHENA has not produced a Decision for this symbol."}</p>
            <h4>DarvaX</h4>
            <p>${darvax.status === "ENABLED_IFRAME" ? "DarvaX Symbol 360 is available as an experimental satellite." : "DarvaX is unavailable."}</p>
            <h4>Portfolio Context</h4>
            <p>${portfolio.status === "HELD" ? "This symbol is held in My Portfolio." : "This symbol is not held."}</p>
            <h4>Data Availability</h4>
            <p>Fundamentals and news are not ingested. Market data: ${siMarketDataStatus(bundle)}. SI coverage: ${siCoverageStatus(bundle)}. ${siCoverageReason(bundle)}</p>
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

    function renderSiD1Chart(host, series, d1) {
        const candles = (series && series.candles) || [];
        if (!host) return;
        if (!candles.length) {
            host.innerHTML = "<p class=\"si-empty\">No D1 candles available for charting.</p>";
            return;
        }
        const width = 720;
        const height = 360;
        const margin = { top: 12, right: 56, bottom: 36, left: 12 };
        const plotWidth = width - margin.left - margin.right;
        const priceHeight = 250;
        const volumeTop = margin.top + priceHeight + 8;
        const volumeHeight = 34;
        const highs = candles.map(c => Number(c.high));
        const lows = candles.map(c => Number(c.low));
        let minPrice = Math.min(...lows);
        let maxPrice = Math.max(...highs);
        const span = Math.max(maxPrice - minPrice, Math.abs(maxPrice || 1) * 0.005);
        minPrice -= span * 0.08;
        maxPrice += span * 0.08;
        const y = price => margin.top + ((maxPrice - Number(price)) / (maxPrice - minPrice)) * priceHeight;
        const slot = plotWidth / candles.length;
        const bodyWidth = Math.max(2.2, Math.min(8, slot * 0.62));
        const xAt = index => margin.left + slot * index + slot / 2;
        const maxVol = Math.max(...candles.map(c => Number(c.volume) || 0), 1);
        const bodies = candles.map((c, index) => {
            const open = Number(c.open);
            const close = Number(c.close);
            const x = xAt(index);
            const up = close >= open;
            const top = y(Math.max(open, close));
            const bottom = y(Math.min(open, close));
            const volH = (Number(c.volume) || 0) / maxVol * volumeHeight;
            return `<line x1="${x}" y1="${y(c.high)}" x2="${x}" y2="${y(c.low)}" stroke="${up ? "#3dba7e" : "#e15b64"}" stroke-width="1"/>
                <rect x="${x - bodyWidth / 2}" y="${top}" width="${bodyWidth}" height="${Math.max(1, bottom - top)}" fill="${up ? "#3dba7e" : "#e15b64"}"/>
                <rect x="${x - bodyWidth / 2}" y="${volumeTop + volumeHeight - volH}" width="${bodyWidth}" height="${volH}" fill="${up ? "#3dba7e55" : "#e15b6455"}"/>`;
        }).join("");
        const last = candles[candles.length - 1];
        const lastY = y(last.close);
        const zones = [
            ["S1", d1 && d1.support_1 && d1.support_1.upper],
            ["MS", d1 && d1.major_support && d1.major_support.upper],
            ["RT", d1 && d1.review_trigger && d1.review_trigger.lower],
        ].filter(item => item[1] != null && Number.isFinite(Number(item[1])));
        const zoneLines = zones.map(([name, px]) => (
            `<line x1="${margin.left}" y1="${y(px)}" x2="${margin.left + plotWidth}" y2="${y(px)}" stroke="#5b8def88" stroke-dasharray="4 3"/>
             <text x="${margin.left + plotWidth + 4}" y="${y(px) + 3}" fill="#8aa0c4" font-size="10">${name}</text>`
        )).join("");
        host.innerHTML = `<svg class="si-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="D1 candlestick chart">
            ${bodies}
            <line x1="${margin.left}" y1="${lastY}" x2="${margin.left + plotWidth}" y2="${lastY}" stroke="#d7deea" stroke-dasharray="2 4"/>
            ${zoneLines}
            <text x="${margin.left}" y="${height - 8}" fill="#8aa0c4" font-size="10">LAST COMPLETED D1 · ${siEscape(String(last.ts_open || last.ts || "").slice(0, 10))}</text>
        </svg>`;
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
