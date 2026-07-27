

    function chartLevelValues(plan) {
        if (!plan) return [];
        return [
            Number(plan.entry_low),
            Number(plan.entry_high),
            Number(plan.stop_loss),
            ...(Array.isArray(plan.targets) ? plan.targets.map(Number) : []),
        ].filter(Number.isFinite);
    }

    function renderCandlestickSvg(series, plan, hostId = "decision-chart-canvas") {
        const host = document.getElementById(hostId);
        if (!host) return;
        const candles = Array.isArray(series.candles) ? series.candles : [];
        if (!candles.length) {
            host.innerHTML = `
                <div class="decision-chart-empty">
                    No persisted 5-minute candles for ${escapeDecisionHtml(series.instrument_id)}.
                    Re-validate after Kite ingestion.
                </div>
            `;
            return;
        }

        const width = 900;
        const height = 390;
        const margin = { top: 20, right: 72, bottom: 34, left: 12 };
        // Volume subplot (UX-3b) takes a fixed band above the time axis;
        // the price plot fills whatever height remains.
        const volumeHeight = 56;
        const volumeGap = 10;
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom - volumeHeight - volumeGap;
        const volumeTop = margin.top + plotHeight + volumeGap;

        // Number(null) is 0 in JavaScript, not NaN — a warmup candle's
        // genuinely-absent atr/moving_average (JSON null) would otherwise
        // silently become a fake reading of exactly 0, corrupting both the
        // rendered line/band and the Y-axis autoscale (owner-reported: axis
        // spanning -907 to 16,026 for a ~13-15k stock).
        const numericOrNull = value => {
            if (value === null || value === undefined) return null;
            const n = Number(value);
            return Number.isFinite(n) ? n : null;
        };
        const maValues = candles.map(c => numericOrNull(c.moving_average));
        const atrValues = candles.map(c => numericOrNull(c.atr));
        const bandPrices = candles.flatMap((c, i) => {
            if (maValues[i] === null || atrValues[i] === null) return [];
            return [maValues[i] + atrValues[i], maValues[i] - atrValues[i]];
        });

        const prices = candles.flatMap(candle => [Number(candle.high), Number(candle.low)]);
        prices.push(...chartLevelValues(plan), ...bandPrices);
        let minPrice = Math.min(...prices);
        let maxPrice = Math.max(...prices);
        const span = Math.max(maxPrice - minPrice, Math.abs(maxPrice || 1) * 0.005);
        minPrice -= span * 0.06;
        maxPrice += span * 0.06;

        const y = price => margin.top
            + ((maxPrice - Number(price)) / (maxPrice - minPrice)) * plotHeight;
        const slot = plotWidth / candles.length;
        const bodyWidth = Math.max(2, Math.min(8, slot * 0.58));
        const xAt = index => margin.left + slot * index + slot / 2;
        const priceLabel = value => Number(value).toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });

        const grid = Array.from({ length: 5 }, (_, index) => {
            const ratio = index / 4;
            const price = maxPrice - (maxPrice - minPrice) * ratio;
            const yy = margin.top + plotHeight * ratio;
            return `
                <line x1="${margin.left}" y1="${yy}" x2="${margin.left + plotWidth}" y2="${yy}"
                    class="decision-chart-gridline" />
                <text x="${margin.left + plotWidth + 7}" y="${yy + 4}"
                    class="decision-chart-axis-label">${priceLabel(price)}</text>
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
                <text x="${margin.left + 6}" y="${Math.max(margin.top + 11, zoneY - 4)}"
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
                    <line x1="${margin.left}" y1="${yy}" x2="${margin.left + plotWidth}" y2="${yy}"
                        class="decision-chart-plan-line ${level.cls}" />
                    <text x="${margin.left + 6}" y="${yy - 4}"
                        class="decision-chart-plan-label ${level.cls}">
                        ${level.label} ${priceLabel(level.value)}
                    </text>
                `;
            }).join("");
        }

        // ATR envelope (moving average +/- ATR) — a volatility band, not a
        // price level. None during warmup, so the band only spans indices
        // where both values were actually computed (never interpolated
        // across a gap, never invented for a bar that had no history yet).
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
            const points = maIndexes.map(i => `${xAt(i)},${y(maValues[i])}`).join(" ");
            maLine = `<polyline class="decision-chart-ma-line" points="${points}" />`;
        }

        const bars = candles.map((candle, index) => {
            const open = Number(candle.open);
            const close = Number(candle.close);
            const high = Number(candle.high);
            const low = Number(candle.low);
            const rising = close >= open;
            const x = xAt(index);
            const bodyY = Math.min(y(open), y(close));
            const bodyHeight = Math.max(1.5, Math.abs(y(open) - y(close)));
            const cls = rising ? "up" : "down";
            return `
                <g class="decision-candle ${cls}">
                    <line x1="${x}" y1="${y(high)}" x2="${x}" y2="${y(low)}" />
                    <rect x="${x - bodyWidth / 2}" y="${bodyY}"
                        width="${bodyWidth}" height="${bodyHeight}" />
                    <title>${escapeDecisionHtml(formatDecisionTime(candle.ts_open))}
O ${priceLabel(open)} · H ${priceLabel(high)} · L ${priceLabel(low)} · C ${priceLabel(close)}
Volume ${Number(candle.volume).toLocaleString("en-IN")}</title>
                </g>
            `;
        }).join("");

        // Volume subplot — same up/down coloring as the candle bodies above it.
        const volumes = candles.map(c => Number(c.volume) || 0);
        const maxVolume = Math.max(1, ...volumes);
        const volY = v => volumeTop + volumeHeight - (v / maxVolume) * volumeHeight;
        const volumeBars = candles.map((candle, index) => {
            const rising = Number(candle.close) >= Number(candle.open);
            const x = xAt(index);
            const vy = volY(volumes[index]);
            return `
                <rect x="${x - bodyWidth / 2}" y="${vy}"
                    width="${bodyWidth}" height="${Math.max(1, volumeTop + volumeHeight - vy)}"
                    class="decision-chart-volume-bar ${rising ? "up" : "down"}" />
            `;
        }).join("");
        const volumeLabel = `<text x="${margin.left}" y="${volumeTop - 3}"
            class="decision-chart-axis-label">VOLUME</text>`;

        const labelIndexes = [...new Set([0, Math.floor((candles.length - 1) / 2), candles.length - 1])];
        const timeLabels = labelIndexes.map(index => {
            const candle = candles[index];
            const x = xAt(index);
            const date = new Date(candle.ts_open);
            const label = date.toLocaleTimeString("en-IN", {
                timeZone: "Asia/Kolkata",
                hour: "2-digit",
                minute: "2-digit",
            });
            return `<text x="${x}" y="${height - 9}" text-anchor="middle"
                class="decision-chart-axis-label">${escapeDecisionHtml(label)}</text>`;
        }).join("");

        host.innerHTML = `
            <svg class="decision-candlestick-chart" viewBox="0 0 ${width} ${height}"
                role="img" aria-label="${escapeDecisionHtml(series.instrument_id)} 5-minute candlestick chart">
                ${grid}
                ${entryZone}
                ${atrBand}
                ${bars}
                ${maLine}
                ${planLines}
                ${volumeLabel}
                ${volumeBars}
                ${timeLabels}
            </svg>
        `;
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