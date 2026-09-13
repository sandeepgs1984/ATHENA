
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

    function siMoney(value) {
        if (value === null || value === undefined || value === "") return "—";
        const amount = Number(value);
        if (!Number.isFinite(amount)) return siEscape(value);
        return `₹${amount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    function siPct(value) {
        if (value === null || value === undefined || value === "") return "";
        const amount = Number(value);
        if (!Number.isFinite(amount)) return "";
        const sign = amount > 0 ? "+" : "";
        return `${sign}${amount.toFixed(2)}%`;
    }

    function siNum(value, digits = 2) {
        if (value === null || value === undefined || value === "") return "—";
        const amount = Number(value);
        if (!Number.isFinite(amount)) return siEscape(value);
        return amount.toLocaleString("en-IN", {
            minimumFractionDigits: 0,
            maximumFractionDigits: digits,
        });
    }

    function siDate(value) {
        if (!value) return "—";
        const text = String(value);
        return siEscape(text.slice(0, 10));
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

    function siZoneShort(zone) {
        if (!zone) return "—";
        return `${siText(zone.lower)} – ${siText(zone.upper)}`;
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
        return `<div class="si-id-block">
                <div class="si-id-symbol">${siText(identity.symbol || identity.instrument_id, identity.query || "Unresolved")}</div>
                <div class="si-id-name">${siText(identity.name, "")}</div>
                <div class="si-id-meta">${siText(identity.exchange, "")}${identity.instrument_id ? ` · ${siText(identity.instrument_id)}` : ""}</div>
            </div>
            <div>
                <div class="si-id-price">${siMoney(price)}</div>
                <div class="si-id-change ${changeClass}">${siEscape(change)}</div>
                <div class="si-id-session">${siQuoteCaption(live)}</div>
            </div>
            <div>
                <div class="si-id-session">D1 through: ${siDate(d1.latest_session)}</div>
                <div class="si-id-session">Expected: ${siDate(d1.expected_session)}</div>
                <div class="si-id-session">Market data: ${siMarketDataStatus(bundle)}</div>
                <div class="si-id-session">SI coverage: ${siCoverageStatus(bundle)}</div>
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
            message = message || "Symbol Intelligence is unavailable for this symbol.";
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
                <p class="si-empty">Not held.</p></div>`;
        }
        const banned = [portfolio.interpretation_status, portfolio.next_action, portfolio.daily_review_status]
            .filter(value => SI_HOLDING_GUIDANCE.has(String(value || "")));
        const interpretation = banned.length
            ? `<p class="si-empty">Held. Portfolio-owned status ${siText(portfolio.interpretation_status)}.</p>`
            : `<p class="si-empty">${siText(portfolio.interpretation_status)} · ${siText(portfolio.next_action)}</p>`;
        return `<div class="si-card"><h3>Portfolio Context</h3>
            <dl class="si-metrics">
                ${siMetric("Quantity", portfolio.quantity)}
                ${siMetric("Average", siMoney(portfolio.avg_price))}
                ${siMetric("P&L", `${siMoney(portfolio.pnl)}`)}
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
        return `<div class="si-card"><h3>ATHENA Decision</h3>
            <dl class="si-metrics">
                ${siMetric("Type", decision.decision_type)}
                ${siMetric("Direction", decision.direction)}
                ${siMetric("Confidence", decision.confidence_level)}
            </dl>
            <p>${siText(decision.explanation)}</p>
            ${plan ? `<p>TradePlan ${siMoney(plan.entry_low)} / ${siMoney(plan.entry_high)}</p>` : ""}
            <p><a class="btn" href="${siEscape(openHref)}">Open Decision Brief</a></p></div>`;
    }

    function siTrendCard(d1) {
        if (!d1 || !d1.present) {
            return `<div class="si-card"><h3>Trend / Structure</h3><p class="si-empty">No completed D1 evidence.</p></div>`;
        }
        return `<div class="si-card"><h3>Trend / Structure</h3>
            <dl class="si-metrics">
                ${siMetric("Daily SMA structure", siSmaStructureLabel(d1.symbol_trend), d1.symbol_trend)}
                ${siMetric("SuperTrend (10,3)", siSuperTrendLabel(d1.supertrend_direction), d1.supertrend_direction)}
                ${siMetric("SMA20", siNum(d1.fast_sma, 2))}
                ${siMetric("SMA50", siNum(d1.slow_sma, 2))}
            </dl>
            <p class="si-pending">SMA structure and SuperTrend are independent evidence. They are not blended.</p></div>`;
    }

    function siMomentumCard(bundle) {
        const d1 = bundle.d1 || {};
        return `<div class="si-card"><h3>Momentum Evidence</h3>
            <p class="si-pending">Methodology pending</p>
            <dl class="si-metrics">
                ${siMetric("RSI14", siNum(d1.rsi14, 1))}
                ${siMetric("Volume vs MA20", siVolumeVsMa20(d1))}
            </dl></div>`;
    }

    function siLevelsCard(d1) {
        return `<div class="si-card"><h3>Key Levels</h3>
            <dl class="si-metrics">
                ${siOptionalZoneMetric("Support 1", d1 && d1.support_1)}
                ${siOptionalZoneMetric("Major support", d1 && d1.major_support)}
                ${siOptionalZoneMetric("Review trigger", d1 && d1.review_trigger)}
                ${siOptionalZoneMetric("Target 1", d1 && d1.target_1)}
                ${siOptionalZoneMetric("Target 2", d1 && d1.target_2)}
                ${siOptionalZoneMetric("Target 3", d1 && d1.target_3)}
                ${siMetric("Available-history high", siMoney(d1 && d1.available_history_high))}
            </dl></div>`;
    }

    function siAvailabilityChips(bundle) {
        const fundamentals = bundle.fundamentals || {};
        const news = bundle.news || {};
        return `<div class="si-card"><h3>Additional sources</h3>
            <div class="si-availability-chips">
                <span class="si-chip">Fundamentals — Not ingested</span>
                <span class="si-chip">News &amp; catalysts — Not ingested</span>
            </div>
            <p class="si-pending">Not available yet. ${siText(fundamentals.status, "NOT_INGESTED")} / ${siText(news.status, "NOT_INGESTED")} are not errors.</p></div>`;
    }

    function siDarvaxOverview(darvax) {
        const label = siText(darvax && darvax.experimental_label, "EXPERIMENTAL_UNVALIDATED");
        if (!darvax || darvax.status !== "ENABLED_IFRAME") {
            return `<div class="si-card"><h3>DarvaX</h3>
                <p class="si-empty">DARVAX UNAVAILABLE</p>
                <p class="si-pending">${label}</p></div>`;
        }
        return `<div class="si-card"><h3>DarvaX</h3>
            <p class="si-empty">Symbol 360 is available on the DarvaX surface. It is not mixed into Stock 360 evidence.</p>
            <p class="si-pending">${label}</p></div>`;
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

    function siChartBlock() {
        return `<div class="si-card"><h3>Completed D1 chart</h3>
            <p class="si-pending">LAST COMPLETED D1 · unfinished session candles are excluded</p>
            <div class="si-chart-host" id="si-d1-chart-host"><p class="text-muted">Loading D1 chart…</p></div>
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
        const trend = d1.symbol_trend ? `Primary D1 trend is ${d1.symbol_trend}.` : "D1 trend is unavailable.";
        const st = d1.supertrend_direction ? `SuperTrend remains ${String(d1.supertrend_direction).toLowerCase()}.` : "";
        const rsi = d1.rsi14 != null ? `RSI is ${siNum(d1.rsi14, 1)}.` : "RSI is unavailable.";
        return `<div class="si-card si-review">
            <h3>Written summary</h3>
            <h4>Market Snapshot</h4>
            <p>${siSentence([
                live.present
                    ? `${live.quote_kind === "LIVE" ? "Live" : "Latest quote"} ${siMoney(live.last_price)} (${siText(live.label)}).`
                    : "No current/latest quote was captured; last completed D1 is shown.",
                d1.present ? `Last completed D1 close ${siMoney(d1.close)} on ${siDate(d1.latest_session)}.` : "No completed D1 bar is present.",
            ])}</p>
            <h4>Trend</h4><p>${siSentence([trend, st])}</p>
            <h4>Momentum Evidence</h4><p>${rsi} Momentum Quality is not yet methodologically defined.</p>
            <h4>Structure</h4><p>${d1.present ? `Available-history high ${siMoney(d1.available_history_high)}.` : "Structure unavailable."}</p>
            <h4>Key Levels</h4><p>Support 1 ${siZoneShort(d1.support_1)}. Review trigger ${siZoneShort(d1.review_trigger)}.</p>
            <h4>Entry Evidence</h4><p>Entry Quality is not yet methodologically defined. Named support/review levels are shown without a buy/wait verdict.</p>
            <h4>ATHENA Decision</h4>
            <p>${decision.present ? siText(decision.explanation) : "ATHENA has not produced a Decision for this symbol."}</p>
            <h4>DarvaX</h4>
            <p>${darvax.status === "ENABLED_IFRAME" ? "DarvaX Symbol 360 is available as an experimental satellite." : "DarvaX is unavailable."}</p>
            <h4>Portfolio Context</h4>
            <p>${portfolio.status === "HELD" ? "This symbol is held in My Portfolio." : "This symbol is not held."}</p>
            <h4>Data Availability</h4>
            <p>Fundamentals and news are not ingested. Market data: ${siMarketDataStatus(bundle)}. SI coverage: ${siCoverageStatus(bundle)}. ${siCoverageReason(bundle)}</p>
        </div>`;
    }

    function siAuditTable(bundle) {
        const rows = (bundle.sources || []).map(src => (
            `<tr><td>${siText(src.source)}</td><td>${siText(src.status)}</td><td>${siDate(src.as_of)}</td>
            <td>${siText(src.lineage)}</td><td>${siText(src.explanation)}</td></tr>`
        )).join("");
        const missing = (bundle.unavailable || []).map(item => (
            `<tr><td>${siText(item.code)}</td><td>UNAVAILABLE</td><td>—</td>
            <td>${siText(item.lineage)}</td><td>${siText(item.detail)}</td></tr>`
        )).join("");
        const hydration = bundle.hydration || {};
        return `<div class="si-card"><h3>Evidence / Audit</h3>
            <table class="si-audit-table">
                <thead><tr><th>Source</th><th>Status</th><th>As Of</th><th>Reference</th><th>Reason</th></tr></thead>
                <tbody>${rows}${missing}
                <tr><td>HYDRATION</td><td>${siText(hydration.status, "SKIPPED")}</td><td>—</td>
                    <td>D1_CANDLES</td><td>${siText(hydration.detail)}</td></tr>
                </tbody>
            </table></div>`;
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
        const height = 280;
        const margin = { top: 12, right: 56, bottom: 36, left: 12 };
        const plotWidth = width - margin.left - margin.right;
        const priceHeight = 190;
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
        bundleEl.innerHTML = `
            <section class="si-section" data-si-panel="stock-360">
                ${siCoverageBanner(bundle)}
                <div class="si-360-core">
                    ${siTrendCard(d1)}
                    ${siMomentumCard(bundle)}
                    ${siDecisionCard(bundle.decision)}
                    ${siLevelsCard(d1)}
                </div>
                ${siChartBlock()}
                <details class="si-written-summary">
                    <summary>Written summary</summary>
                    ${siCompleteReview(bundle)}
                </details>
                <div class="si-360-secondary">
                    ${siPortfolioCard(bundle.portfolio)}
                    ${siAvailabilityChips(bundle)}
                    ${siDarvaxOverview(bundle.darvax)}
                </div>
            </section>
            <section class="si-section" data-si-panel="decision" hidden>${siDecisionCard(bundle.decision)}</section>
            <section class="si-section" data-si-panel="experimental" hidden>${siDarvaxCard(bundle.darvax)}</section>
            <section class="si-section" data-si-panel="audit" hidden>${siAuditTable(bundle)}</section>`;
        showSiSection(document.querySelector(".si-section-nav-item.active")?.getAttribute("data-si-section") || "stock-360");
        bindDarvaxFrame();
        if (bundle.identity && bundle.identity.instrument_id) {
            loadSiD1Chart(bundle.identity.instrument_id, d1, siLoadGeneration);
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
