

    const decisionChartControllers = new Map();

    function chartLevelValues(plan) {
        if (!plan) return [];
        return [
            Number(plan.entry_low),
            Number(plan.entry_high),
            Number(plan.stop_loss),
            ...(Array.isArray(plan.targets) ? plan.targets.map(Number) : []),
        ].filter(Number.isFinite);
    }

    // Number(null) is 0 in JavaScript, not NaN — a warmup candle's
    // genuinely-absent atr/moving_average (JSON null) would otherwise
    // silently become a fake reading of exactly 0.
    const chartNumericOrNull = value => {
        if (value === null || value === undefined) return null;
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    };

    const chartPriceLabel = value => Number(value).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });

    const chartTimeLabel = value => new Date(value).toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
    });

    function scaledPath(indexes, xAt, yAt, values) {
        return indexes.map(index => `${xAt(index)},${yAt(values[index])}`).join(" ");
    }

    class DecisionChartController {
        constructor(hostId) {
            this.hostId = hostId;
            this.host = document.getElementById(hostId);
        }

        render(series, plan) {
            if (!this.host) return;
            const candles = Array.isArray(series.candles) ? series.candles : [];
            if (!candles.length) {
                this.host.innerHTML = `
                    <div class="decision-chart-empty">
                        No persisted 5-minute candles for ${escapeDecisionHtml(series.instrument_id)}.
                        Re-validate after Kite ingestion.
                    </div>
                `;
                return;
            }

            const width = 1040;
            const height = 440;
            const margin = { top: 24, right: 86, bottom: 32, left: 16 };
            const volumeHeight = 72;
            const panelGap = 18;
            const plotWidth = width - margin.left - margin.right;
            const priceHeight = height - margin.top - margin.bottom - volumeHeight - panelGap;
            const volumeTop = margin.top + priceHeight + panelGap;
            const priceBottom = margin.top + priceHeight;
            const plotRight = margin.left + plotWidth;

            const maValues = candles.map(c => chartNumericOrNull(c.moving_average));
            const atrValues = candles.map(c => chartNumericOrNull(c.atr));
            const bandPrices = candles.flatMap((c, i) => {
                if (maValues[i] === null || atrValues[i] === null) return [];
                return [maValues[i] + atrValues[i], maValues[i] - atrValues[i]];
            });

            const prices = candles.flatMap(candle => [Number(candle.high), Number(candle.low)]);
            prices.push(...chartLevelValues(plan), ...bandPrices);
            let minPrice = Math.min(...prices);
            let maxPrice = Math.max(...prices);
            const span = Math.max(maxPrice - minPrice, Math.abs(maxPrice || 1) * 0.005);
            minPrice -= span * 0.08;
            maxPrice += span * 0.08;

            const y = price => margin.top
                + ((maxPrice - Number(price)) / (maxPrice - minPrice)) * priceHeight;
            const slot = plotWidth / candles.length;
            const bodyWidth = Math.max(2.5, Math.min(9, slot * 0.62));
            const xAt = index => margin.left + slot * index + slot / 2;

            const grid = Array.from({ length: 6 }, (_, index) => {
                const ratio = index / 5;
                const price = maxPrice - (maxPrice - minPrice) * ratio;
                const yy = margin.top + priceHeight * ratio;
                return `
                    <line x1="${margin.left}" y1="${yy}" x2="${plotRight}" y2="${yy}"
                        class="decision-chart-gridline" />
                    <text x="${plotRight + 10}" y="${yy + 4}"
                        class="decision-chart-axis-label">${chartPriceLabel(price)}</text>
                `;
            }).join("");

            let entryZone = "";
            let planLines = "";
            if (plan) {
                const entryLowY = y(plan.entry_low);
                const entryHighY = y(plan.entry_high);
                const zoneY = Math.min(entryLowY, entryHighY);
                const zoneHeight = Math.max(2, Math.abs(entryLowY - entryHighY));
                entryZone = `
                    <rect x="${margin.left}" y="${zoneY}" width="${plotWidth}" height="${zoneHeight}"
                        class="decision-chart-entry-zone" />
                    <text x="${margin.left + 8}" y="${Math.max(margin.top + 13, zoneY - 6)}"
                        class="decision-chart-plan-label entry">ENTRY ZONE</text>
                `;
                const levels = [
                    { value: plan.stop_loss, label: "STOP", cls: "stop" },
                    ...(Array.isArray(plan.targets)
                        ? plan.targets.map((target, index) => ({
                            value: target,
                            label: `T${index + 1}`,
                            cls: "target",
                        }))
                        : []),
                ];
                planLines = levels.map(level => {
                    const yy = y(level.value);
                    return `
                        <line x1="${margin.left}" y1="${yy}" x2="${plotRight}" y2="${yy}"
                            class="decision-chart-plan-line ${level.cls}" />
                        <text x="${margin.left + 8}" y="${yy - 6}"
                            class="decision-chart-plan-label ${level.cls}">
                            ${level.label} ${chartPriceLabel(level.value)}
                        </text>
                    `;
                }).join("");
            }

            // ATR envelope (moving average +/- ATR) is a volatility band, not
            // a price level. It only spans bars where both inputs exist.
            let atrBand = "";
            let maLine = "";
            const bandIndexes = candles
                .map((_, i) => i)
                .filter(i => maValues[i] !== null && atrValues[i] !== null);
            if (bandIndexes.length > 1) {
                const upper = bandIndexes.map(i => `${xAt(i)},${y(maValues[i] + atrValues[i])}`);
                const lower = [...bandIndexes].reverse()
                    .map(i => `${xAt(i)},${y(maValues[i] - atrValues[i])}`);
                atrBand = `<polygon class="decision-chart-atr-band" points="${upper.concat(lower).join(" ")}" />`;
            }
            const maIndexes = candles.map((_, i) => i).filter(i => maValues[i] !== null);
            if (maIndexes.length > 1) {
                maLine = `<polyline class="decision-chart-ma-line"
                    points="${scaledPath(maIndexes, xAt, y, maValues)}" />`;
            }

            const bars = candles.map((candle, index) => {
                const open = Number(candle.open);
                const close = Number(candle.close);
                const high = Number(candle.high);
                const low = Number(candle.low);
                const rising = close >= open;
                const x = xAt(index);
                const bodyY = Math.min(y(open), y(close));
                const bodyHeight = Math.max(1.8, Math.abs(y(open) - y(close)));
                const cls = rising ? "up" : "down";
                return `
                    <g class="decision-candle ${cls}">
                        <line x1="${x}" y1="${y(high)}" x2="${x}" y2="${y(low)}" />
                        <rect x="${x - bodyWidth / 2}" y="${bodyY}"
                            width="${bodyWidth}" height="${bodyHeight}" rx="1.2" />
                        <title>${escapeDecisionHtml(formatDecisionTime(candle.ts_open))}
O ${chartPriceLabel(open)} · H ${chartPriceLabel(high)} · L ${chartPriceLabel(low)} · C ${chartPriceLabel(close)}
Volume ${Number(candle.volume).toLocaleString("en-IN")}</title>
                    </g>
                `;
            }).join("");

            const volumes = candles.map(c => Number(c.volume) || 0);
            const maxVolume = Math.max(1, ...volumes);
            const volY = v => volumeTop + volumeHeight - (v / maxVolume) * volumeHeight;
            const volumeBars = candles.map((candle, index) => {
                const rising = Number(candle.close) >= Number(candle.open);
                const x = xAt(index);
                const vy = volY(volumes[index]);
                return `
                    <rect x="${x - bodyWidth / 2}" y="${vy}"
                        width="${bodyWidth}" height="${Math.max(1.5, volumeTop + volumeHeight - vy)}"
                        rx="1.2" class="decision-chart-volume-bar ${rising ? "up" : "down"}" />
                `;
            }).join("");

            const labelIndexes = [...new Set([
                0,
                Math.floor((candles.length - 1) * 0.25),
                Math.floor((candles.length - 1) * 0.5),
                Math.floor((candles.length - 1) * 0.75),
                candles.length - 1,
            ])];
            const timeLabels = labelIndexes.map(index => {
                const candle = candles[index];
                const x = xAt(index);
                return `<text x="${x}" y="${height - 9}" text-anchor="middle"
                    class="decision-chart-axis-label">${escapeDecisionHtml(chartTimeLabel(candle.ts_open))}</text>`;
            }).join("");

            const latestCandle = candles[candles.length - 1];
            const latestClose = Number(latestCandle.close);
            const latestY = y(latestClose);
            const latestTone = latestClose >= Number(latestCandle.open) ? "up" : "down";
            const high = Math.max(...candles.map(c => Number(c.high)));
            const low = Math.min(...candles.map(c => Number(c.low)));

            this.host.innerHTML = `
                <div class="decision-chart-shell" data-chart-host="${escapeDecisionHtml(this.hostId)}">
                    <div class="decision-chart-topline">
                        <span>${escapeDecisionHtml(series.timeframe || "5m")} · ${candles.length} bars</span>
                        <span>High ${chartPriceLabel(high)} · Low ${chartPriceLabel(low)}</span>
                    </div>
                    <svg class="decision-candlestick-chart decision-chart-svg" viewBox="0 0 ${width} ${height}"
                        preserveAspectRatio="none"
                        role="img" aria-label="${escapeDecisionHtml(series.instrument_id)} ${escapeDecisionHtml(series.timeframe || "5m")} candlestick chart">
                        <defs>
                            <linearGradient id="chartPanelGradient-${escapeDecisionHtml(this.hostId)}" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stop-color="rgba(15, 23, 42, 0.88)" />
                                <stop offset="100%" stop-color="rgba(2, 6, 23, 0.7)" />
                            </linearGradient>
                        </defs>
                        <rect x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${priceHeight}"
                            class="decision-chart-price-panel" />
                        <rect x="${margin.left}" y="${volumeTop}" width="${plotWidth}" height="${volumeHeight}"
                            class="decision-chart-volume-panel" />
                        ${grid}
                        <line x1="${margin.left}" y1="${priceBottom}" x2="${plotRight}" y2="${priceBottom}"
                            class="decision-chart-panel-separator" />
                        ${entryZone}
                        ${atrBand}
                        ${bars}
                        ${maLine}
                        ${planLines}
                        ${volumeBars}
                        <text x="${margin.left}" y="${volumeTop - 6}"
                            class="decision-chart-axis-label">VOLUME</text>
                        <line x1="${margin.left}" y1="${latestY}" x2="${plotRight}" y2="${latestY}"
                            class="decision-chart-price-marker-line ${latestTone}" />
                        <rect x="${plotRight + 6}" y="${latestY - 10}" width="74" height="20" rx="3"
                            class="decision-chart-price-marker-box ${latestTone}" />
                        <text x="${plotRight + 43}" y="${latestY + 4}" text-anchor="middle"
                            class="decision-chart-price-marker-text">${chartPriceLabel(latestClose)}</text>
                        ${timeLabels}
                    </svg>
                </div>
            `;
        }
    }

    function chartControllerFor(hostId) {
        const currentHost = document.getElementById(hostId);
        const existing = decisionChartControllers.get(hostId);
        if (existing && existing.host === currentHost) return existing;
        const controller = new DecisionChartController(hostId);
        decisionChartControllers.set(hostId, controller);
        return controller;
    }

    function renderProfessionalDecisionChart(series, plan, hostId = "decision-chart-canvas") {
        chartControllerFor(hostId).render(series, plan);
    }

    function renderCandlestickSvg(series, plan, hostId = "decision-chart-canvas") {
        renderProfessionalDecisionChart(series, plan, hostId);
    }

    function renderChartFreshness(series) {
        const status = document.getElementById("decision-chart-status");
        const meta = document.getElementById("decision-chart-meta");
        const warning = document.getElementById("decision-chart-warning");
        if (!status || !meta || !warning) return;
        const state = String(series.freshness_status || "NO_DATA");
        status.className = `chart-freshness-badge ${state.toLowerCase()}`;
        status.textContent = state === "NO_DATA" ? "NO DATA" : state;
        const latestCandle = Array.isArray(series.candles) && series.candles.length
            ? series.candles[series.candles.length - 1]
            : null;
        const source = latestCandle && latestCandle.source
            ? ` · ${latestCandle.source}`
            : "";
        meta.textContent = series.latest_ts
            ? `${series.count} × ${series.timeframe} bars · latest ${formatDecisionTime(series.latest_ts)}${source}`
            : `No ${series.timeframe} candles persisted`;
        if (state === "STALE") {
            warning.hidden = false;
            warning.textContent =
                `Chart is ${series.age_minutes} minutes old (limit ${series.freshness_threshold_minutes}). ` +
                "Re-validate before using the TradePlan.";
        } else {
            warning.hidden = true;
            warning.textContent = "";
        }
    }

    async function loadDecisionChart(instrumentId, plan, decisionId) {
        const host = document.getElementById("decision-chart-canvas");
        if (!host) return;
        host.innerHTML =
            '<div class="decision-chart-empty"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading persisted candles…</div>';
        try {
            const candidates = String(instrumentId).includes(":")
                ? [String(instrumentId)]
                : [String(instrumentId), `NSE:${instrumentId}`];
            let series = null;
            let lastError = null;
            for (const candidateId of candidates) {
                const path = `/api/v1/market/instruments/${encodeURIComponent(candidateId)}/candles?timeframe=5m&limit=120`;
                try {
                    // Chart panel owns empty/404/stale UI — do not toast on select.
                    const response = await apiRequest(path, { skipToast: true });
                    if (activeDecisionId !== decisionId) return;
                    series = response && response.data;
                    if (series && series.count > 0) break;
                } catch (err) {
                    lastError = err;
                }
            }
            if (!series) {
                if (lastError) throw lastError;
                throw new Error("candles response missing data");
            }
            renderChartFreshness(series);
            renderCandlestickSvg(series, plan);
            activeChartSeries = series;
            activeChartPlan = plan;
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load candles for ${instrumentId}`, err);
            const statusCode = err && err.status;
            let detail =
                "Chart unavailable. Decision evidence and TradePlan remain unchanged.";
            let badge = "UNAVAILABLE";
            if (statusCode === 404) {
                detail =
                    "Candles API is missing on this running host. Restart ATHENA (Dock/athena-serve), then hard-refresh.";
                badge = "RESTART HOST";
            } else if (statusCode === 401) {
                detail = "Unlock again, then reopen Decisions to load the chart.";
                badge = "AUTH";
            }
            host.innerHTML =
                `<div class="decision-chart-empty">${escapeDecisionHtml(detail)}</div>`;
            const status = document.getElementById("decision-chart-status");
            if (status) {
                status.className = "chart-freshness-badge no_data";
                status.textContent = badge;
            }
            const meta = document.getElementById("decision-chart-meta");
            if (meta) {
                meta.textContent = statusCode
                    ? `Candles request failed (${statusCode})`
                    : "Candles request failed";
            }
        }
    }

    // Latest real close for an instrument (UX-9 Portfolio Impact) — same
    // NSE-prefix fallback probing as loadDecisionChart, kept independent
    // rather than sharing state with it so the two loads can't race.
    async function fetchLatestClose(instrumentId) {
        const candidates = String(instrumentId).includes(":")
            ? [String(instrumentId)]
            : [String(instrumentId), `NSE:${instrumentId}`];
        for (const candidateId of candidates) {
            try {
                const path = `/api/v1/market/instruments/${encodeURIComponent(candidateId)}/candles?timeframe=5m&limit=1`;
                const response = await apiRequest(path, { skipToast: true });
                const series = response && response.data;
                if (series && Array.isArray(series.candles) && series.candles.length) {
                    const close = Number(series.candles[series.candles.length - 1].close);
                    if (Number.isFinite(close)) return close;
                }
            } catch (err) {
                // try the next candidate id
            }
        }
        return null;
    }

    function portfolioInstrumentMatches(positionInstrumentId, targetInstrumentId) {
        const norm = v => String(v || "").toUpperCase().replace(/^NSE:|^BSE:/, "");
        return norm(positionInstrumentId) === norm(targetInstrumentId);
    }

    // "You own N shares, avg price, gain %" (owner UX audit) — derived
    // entirely from the existing full positions list (GET /api/v1/portfolio,
    // already used by the Portfolio Overview workstation) and a real latest
    // close price. No new backend, no fabricated numbers: gain % is exact
    // arithmetic over the aggregated open positions' weighted average price
    // vs. the latest real close. "—" (never 0%) when there's no position or
    // no current price to compare against.
    function renderPortfolioImpact(host, instrumentId, positions, lastClose) {
        const open = positions.filter(p =>
            !p.closed_ts && portfolioInstrumentMatches(p.instrument_id, instrumentId)
        );
        if (!open.length) {
            host.innerHTML = '<p class="context-caption">You don\'t currently own any shares of this symbol.</p>';
            return;
        }
        const totalQty = open.reduce((sum, p) => sum + (Number(p.quantity) || 0), 0);
        const totalCost = open.reduce((sum, p) => sum + (Number(p.quantity) || 0) * (Number(p.avg_price) || 0), 0);
        const avgPrice = totalQty > 0 ? totalCost / totalQty : null;
        const gainPct = (avgPrice && Number.isFinite(lastClose))
            ? ((lastClose - avgPrice) / avgPrice) * 100
            : null;
        const gainTone = gainPct === null ? "neutral" : (gainPct > 0 ? "good" : (gainPct < 0 ? "bad" : "neutral"));

        host.innerHTML = `
            <div class="portfolio-impact-grid">
                <div><span>Shares owned</span><strong>${totalQty}</strong></div>
                <div><span>Avg price</span><strong>${avgPrice !== null ? escapeDecisionHtml(formatDecisionPrice(avgPrice)) : "—"}</strong></div>
                <div><span>Current price</span><strong>${Number.isFinite(lastClose) ? escapeDecisionHtml(formatDecisionPrice(lastClose)) : "—"}</strong></div>
                <div><span>Gain / loss</span><strong class="tone-${gainTone}-text">${gainPct !== null ? `${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(1)}%` : "—"}</strong></div>
            </div>
            <p class="context-caption">Across ${open.length} open position${open.length === 1 ? "" : "s"} in this symbol.</p>
        `;
    }

    async function loadPortfolioImpact(instrumentId, decisionId) {
        const host = document.getElementById("decision-portfolio-impact");
        if (!host) return;
        try {
            const [portfolioRes, lastClose] = await Promise.all([
                apiRequest("/api/v1/portfolio", { skipToast: true }),
                fetchLatestClose(instrumentId),
            ]);
            if (activeDecisionId !== decisionId) return;
            const positions = (portfolioRes && portfolioRes.data && portfolioRes.data.positions) || [];
            renderPortfolioImpact(host, instrumentId, positions, lastClose);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load portfolio impact for ${instrumentId}`, err);
            host.innerHTML = '<div class="context-caption">Unable to check your holdings for this symbol.</div>';
        }
    }

    // "Open Chart" quick action (UX-9) — reuses the exact same chart data and
    // render function already loaded for the Trade Plan tab, just at a larger
    // size (the SVG's viewBox scales to fill whatever container CSS gives
    // it) — no second fetch, no separate chart implementation to maintain.
    function openChartModal() {
        const modal = document.getElementById("chart-modal");
        const canvas = document.getElementById("chart-modal-canvas");
        const title = document.getElementById("chart-modal-title");
        if (!modal || !canvas) return;
        const meta = activeDecisionData && activeDecisionData.metadata;
        const symbol = meta ? String(meta.instrument_id || "").split(":").pop() : "";
        if (title) title.textContent = symbol ? `${symbol} — Price Chart` : "Price Chart";
        if (!activeChartSeries) {
            canvas.innerHTML = '<div class="decision-chart-empty">Chart hasn\'t loaded yet for this decision.</div>';
        } else {
            renderCandlestickSvg(activeChartSeries, activeChartPlan, "chart-modal-canvas");
        }
        openModal(modal);
    }

    const chartModalEl = document.getElementById("chart-modal");
    document.getElementById("chart-modal-close")?.addEventListener("click", () => closeModal(chartModalEl));
    window.addEventListener("click", event => {
        if (event.target === chartModalEl) closeModal(chartModalEl);
    });
