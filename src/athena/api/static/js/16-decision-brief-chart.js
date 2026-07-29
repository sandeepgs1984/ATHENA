

    const decisionChartControllers = new Map();
    const CHART_PREF_KEY = "athena.decision-chart-preferences";
    const CHART_TIMEFRAMES = ["5m", "15m"];
    const CHART_LIMITS = [60, 120, 300, 500];
    const DEFAULT_CHART_PREFS = Object.freeze({ timeframe: "5m", limit: 120 });
    let activeChartInstrumentId = null;
    let activeChartDecisionId = null;
    let activeInspectionHostId = null;

    function chartPreferences() {
        try {
            const raw = JSON.parse(localStorage.getItem(CHART_PREF_KEY) || "{}");
            const timeframe = CHART_TIMEFRAMES.includes(raw.timeframe)
                ? raw.timeframe
                : DEFAULT_CHART_PREFS.timeframe;
            const limit = CHART_LIMITS.includes(Number(raw.limit))
                ? Number(raw.limit)
                : DEFAULT_CHART_PREFS.limit;
            return { timeframe, limit };
        } catch (_err) {
            return { ...DEFAULT_CHART_PREFS };
        }
    }

    function saveChartPreferences(nextPrefs) {
        const prefs = {
            timeframe: CHART_TIMEFRAMES.includes(nextPrefs.timeframe)
                ? nextPrefs.timeframe
                : DEFAULT_CHART_PREFS.timeframe,
            limit: CHART_LIMITS.includes(Number(nextPrefs.limit))
                ? Number(nextPrefs.limit)
                : DEFAULT_CHART_PREFS.limit,
        };
        try {
            localStorage.setItem(CHART_PREF_KEY, JSON.stringify(prefs));
        } catch (_err) {
            // Preference persistence is nice-to-have; chart rendering must continue.
        }
        return prefs;
    }

    function chartTimeframeLabel(timeframe) {
        return timeframe === "1m" ? "1 minute" : timeframe === "15m" ? "15 minute" : "5 minute";
    }

    function renderChartControlState(prefs = chartPreferences()) {
        document.querySelectorAll("[data-chart-timeframe]").forEach(button => {
            const active = button.getAttribute("data-chart-timeframe") === prefs.timeframe;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });
        document.querySelectorAll("[data-chart-limit]").forEach(button => {
            const active = Number(button.getAttribute("data-chart-limit")) === Number(prefs.limit);
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
        });
        const title = document.getElementById("decision-chart-title");
        if (title) title.textContent = `Intraday price context · ${chartTimeframeLabel(prefs.timeframe)}`;
    }

    function chartReturnedRangeLabel(series, candleCount) {
        const prefs = chartPreferences();
        const requested = Number(series && series.requested_limit) || prefs.limit;
        const count = Number(series && series.count) || candleCount;
        if (requested > 0 && count > 0 && count < requested) {
            return `${count} of ${requested} requested`;
        }
        return `${candleCount} bars`;
    }

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

    const chartDateKey = value => {
        const parts = new Intl.DateTimeFormat("en-CA", {
            timeZone: "Asia/Kolkata",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }).formatToParts(new Date(value));
        const data = Object.fromEntries(parts.map(part => [part.type, part.value]));
        return `${data.year}-${data.month}-${data.day}`;
    };

    const chartDateLabel = value => new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
    }).format(new Date(value));

    function chartFormatDuration(seconds) {
        const totalSeconds = Math.max(0, Math.round(Number(seconds)));
        if (!Number.isFinite(totalSeconds)) return "";
        if (totalSeconds < 60) return "under 1m";
        const days = Math.floor(totalSeconds / 86400);
        const hours = Math.floor((totalSeconds % 86400) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const parts = [];
        if (days) parts.push(`${days}d`);
        if (hours) parts.push(`${hours}h`);
        if (minutes && parts.length < 2) parts.push(`${minutes}m`);
        return parts.slice(0, 2).join(" ");
    }

    function chartPlanDirection() {
        const meta = activeDecisionData && activeDecisionData.metadata;
        return String(meta && meta.direction || "").toUpperCase();
    }

    function chartPlanLevelPct(plan, price) {
        const entryMid = (Number(plan && plan.entry_low) + Number(plan && plan.entry_high)) / 2;
        const level = Number(price);
        if (!Number.isFinite(entryMid) || entryMid === 0 || !Number.isFinite(level)) return null;
        return chartPlanDirection() === "SHORT"
            ? ((entryMid - level) / entryMid) * 100
            : ((level - entryMid) / entryMid) * 100;
    }

    function chartPlanLevelPctLabel(plan, price) {
        const pct = chartPlanLevelPct(plan, price);
        if (pct === null || pct === undefined || !Number.isFinite(Number(pct))) return "";
        return `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
    }

    function chartPlanValidityLabel(plan, freshness) {
        const status = String(freshness && freshness.status || "").toUpperCase();
        if (status === "EXPIRED") {
            const asOf = new Date(freshness.as_of);
            const validUntil = new Date(freshness.valid_until);
            const expiredSeconds = (asOf.getTime() - validUntil.getTime()) / 1000;
            const ago = chartFormatDuration(expiredSeconds);
            return ago ? `Expired · ${ago} ago` : "Expired";
        }
        const remaining = Number(freshness && freshness.remaining_seconds);
        if (Number.isFinite(remaining)) {
            const expiresIn = chartFormatDuration(remaining);
            return expiresIn ? `Plan expires in ${expiresIn}` : friendlyLabel(status || "ACTIVE");
        }

        const validUntil = new Date(plan && plan.valid_until);
        if (Number.isNaN(validUntil.getTime())) return "";
        const seconds = (validUntil.getTime() - Date.now()) / 1000;
        if (seconds < 0) {
            const ago = chartFormatDuration(Math.abs(seconds));
            return ago ? `Expired · ${ago} ago` : "Expired";
        }
        const expiresIn = chartFormatDuration(seconds);
        return expiresIn ? `Plan expires in ${expiresIn}` : "Plan active";
    }

    function chartPlanValidityClass(plan, freshness) {
        const status = String(freshness && freshness.status || "").toLowerCase();
        if (status) return status;
        const validUntil = new Date(plan && plan.valid_until);
        if (!Number.isNaN(validUntil.getTime()) && Date.now() > validUntil.getTime()) return "expired";
        return "fresh";
    }

    function chartPlanEntryLabel(plan) {
        if (!plan) return "";
        if (Number(plan.entry_low) === Number(plan.entry_high)) return chartPriceLabel(plan.entry_low);
        return `${chartPriceLabel(plan.entry_low)}-${chartPriceLabel(plan.entry_high)}`;
    }

    function chartInspectionValue(value, formatter = chartPriceLabel) {
        const n = chartNumericOrNull(value);
        return n === null ? "Unavailable" : formatter(n);
    }

    function chartPlanInspection(plan) {
        if (!plan) return "Plan unavailable";
        const targets = Array.isArray(plan.targets) ? plan.targets : [];
        const firstTarget = targets.length ? chartPriceLabel(targets[0]) : "Unavailable";
        return `Entry ${chartPlanEntryLabel(plan)} · Stop ${chartPriceLabel(plan.stop_loss)} · T1 ${firstTarget}`;
    }

    function chartTimeframeMs(timeframe) {
        if (timeframe === "15m") return 15 * 60 * 1000;
        if (timeframe === "1m") return 60 * 1000;
        return 5 * 60 * 1000;
    }

    function chartPersistedEvents() {
        const events = [];
        const meta = activeDecisionData && activeDecisionData.metadata;
        if (meta && meta.ts) {
            events.push({
                kind: "decision",
                label: "Decision",
                ts: meta.ts,
                title: `Decision ${meta.decision_id} · ${formatDecisionTime(meta.ts)}`,
            });
        }
        if (activeJournalEntry && activeJournalEntry.action_ts) {
            events.push({
                kind: "journal",
                label: activeJournalEntry.user_action || "Response",
                ts: activeJournalEntry.action_ts,
                title: `Journal ${activeJournalEntry.user_action || "response"} · ${formatDecisionTime(activeJournalEntry.action_ts)}`,
            });
        }
        if (activeTradeOutcome && activeTradeOutcome.closed_ts) {
            events.push({
                kind: "outcome",
                label: "Outcome",
                ts: activeTradeOutcome.closed_ts,
                title: `Outcome closed · ${formatDecisionTime(activeTradeOutcome.closed_ts)}`,
            });
        }
        return events;
    }

    function nearestCandleIndexForTs(candles, ts, timeframe) {
        const eventTime = new Date(ts).getTime();
        if (!Number.isFinite(eventTime) || !candles.length) return null;
        const first = new Date(candles[0].ts_open).getTime();
        const last = new Date(candles[candles.length - 1].ts_open).getTime();
        const tolerance = chartTimeframeMs(timeframe) / 2;
        if (eventTime < first - tolerance || eventTime > last + chartTimeframeMs(timeframe)) return null;
        let bestIndex = 0;
        let bestDistance = Math.abs(eventTime - first);
        candles.forEach((candle, index) => {
            const distance = Math.abs(eventTime - new Date(candle.ts_open).getTime());
            if (distance < bestDistance) {
                bestDistance = distance;
                bestIndex = index;
            }
        });
        return bestIndex;
    }

    function chartNormalizeInstrumentId(value) {
        return String(value || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
    }

    function activeQuoteForSeries(series) {
        if (!series || !activeBriefQuote) return null;
        if (chartNormalizeInstrumentId(series.instrument_id) !== chartNormalizeInstrumentId(activeBriefQuote.instrument_id)) {
            return null;
        }
        const price = Number(activeBriefQuote.last_price);
        return Number.isFinite(price) ? activeBriefQuote : null;
    }

    function scaledPath(indexes, xAt, yAt, values) {
        return indexes.map(index => `${xAt(index)},${yAt(values[index])}`).join(" ");
    }

    class DecisionChartController {
        constructor(hostId) {
            this.hostId = hostId;
            this.host = document.getElementById(hostId);
            this.series = null;
            this.plan = null;
            this.layout = null;
            this.lastInspectionIndex = null;
        }

        render(series, plan) {
            if (!this.host) return;
            const candles = Array.isArray(series.candles) ? series.candles : [];
            if (!candles.length) {
                const timeframe = chartTimeframeLabel(series.timeframe || chartPreferences().timeframe).toLowerCase();
                this.host.innerHTML = `
                    <div class="decision-chart-empty">
                        No persisted ${escapeDecisionHtml(timeframe)} candles for ${escapeDecisionHtml(series.instrument_id)}.
                        Switch timeframe or re-validate after Kite ingestion.
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
            const activeQuote = activeQuoteForSeries(series);
            const quotePrice = activeQuote ? Number(activeQuote.last_price) : null;
            if (Number.isFinite(quotePrice)) prices.push(quotePrice);
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
            this.series = series;
            this.plan = plan;
            this.layout = {
                margin,
                plotWidth,
                plotRight,
                priceHeight,
                volumeTop,
                volumeHeight,
                minPrice,
                maxPrice,
                slot,
                xAt,
                y,
            };

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
                    const pctLabel = chartPlanLevelPctLabel(plan, level.value);
                    const label = pctLabel
                        ? `${level.label} ${chartPriceLabel(level.value)} ${pctLabel}`
                        : `${level.label} ${chartPriceLabel(level.value)}`;
                    return `
                        <line x1="${margin.left}" y1="${yy}" x2="${plotRight}" y2="${yy}"
                            class="decision-chart-plan-line ${level.cls}" />
                        <text x="${margin.left + 8}" y="${yy - 6}"
                            class="decision-chart-plan-label ${level.cls}">
                            ${escapeDecisionHtml(label)}
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
            const sessionSeparators = candles.map((candle, index) => {
                if (index === 0) return "";
                const prev = candles[index - 1];
                if (chartDateKey(prev.ts_open) === chartDateKey(candle.ts_open)) return "";
                const x = xAt(index) - slot / 2;
                return `
                    <line x1="${x}" y1="${margin.top}" x2="${x}" y2="${volumeTop + volumeHeight}"
                        class="decision-chart-session-separator" />
                    <text x="${x + 5}" y="${margin.top + 12}"
                        class="decision-chart-session-label">${escapeDecisionHtml(chartDateLabel(candle.ts_open))}</text>
                `;
            }).join("");

            const latestCandle = candles[candles.length - 1];
            const latestClose = Number(latestCandle.close);
            const markerPrice = Number.isFinite(quotePrice) ? quotePrice : latestClose;
            const markerY = y(markerPrice);
            const latestTone = markerPrice >= latestClose ? "up" : "down";
            const markerLabel = activeQuote ? "Quote" : "Candle close";
            const markerTitle = activeQuote
                ? `${activeQuote.source === "kite_live" ? "Live Kite quote" : "Last persisted quote"}${activeQuote.as_of ? ` · ${formatDecisionTime(activeQuote.as_of)}` : ""}`
                : `Latest persisted ${series.timeframe || "5m"} candle close · ${formatDecisionTime(latestCandle.ts_open)}`;
            const high = Math.max(...candles.map(c => Number(c.high)));
            const low = Math.min(...candles.map(c => Number(c.low)));
            const planStrip = this.renderPlanStrip(plan);
            const rangeLabel = chartReturnedRangeLabel(series, candles.length);
            const eventMarkers = chartPersistedEvents().map(event => {
                const index = nearestCandleIndexForTs(candles, event.ts, series.timeframe);
                if (index === null) return "";
                const x = xAt(index);
                const yTop = margin.top + 10;
                return `
                    <g class="decision-chart-event-marker ${escapeDecisionHtml(event.kind)}">
                        <line x1="${x}" y1="${margin.top}" x2="${x}" y2="${volumeTop + volumeHeight}" />
                        <path d="M ${x - 6} ${yTop} L ${x + 6} ${yTop} L ${x} ${yTop + 9} Z" />
                        <text x="${x + 8}" y="${yTop + 4}">${escapeDecisionHtml(event.label)}</text>
                        <title>${escapeDecisionHtml(event.title)}</title>
                    </g>
                `;
            }).join("");

            this.host.innerHTML = `
                <div class="decision-chart-shell" data-chart-host="${escapeDecisionHtml(this.hostId)}"
                    tabindex="0" role="group" aria-label="Inspect candles with pointer or arrow keys">
                    <div class="decision-chart-topline">
                        <span>${escapeDecisionHtml(series.timeframe || chartPreferences().timeframe)} · ${escapeDecisionHtml(rangeLabel)}</span>
                        <span>${escapeDecisionHtml(markerLabel)} ${chartPriceLabel(markerPrice)} · Candle close ${chartPriceLabel(latestClose)}</span>
                        <span>High ${chartPriceLabel(high)} · Low ${chartPriceLabel(low)}</span>
                    </div>
                    ${planStrip}
                    <div class="decision-chart-inspector" data-chart-inspector="${escapeDecisionHtml(this.hostId)}" aria-live="polite">
                        <span data-chart-inspector-copy>Latest candle selected.</span>
                        <button type="button" class="decision-chart-reset" data-chart-reset="${escapeDecisionHtml(this.hostId)}"
                            aria-label="Reset chart inspection to latest candle" title="Reset chart inspection">
                            <i class="fa-solid fa-rotate-left"></i>
                        </button>
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
                        ${sessionSeparators}
                        ${eventMarkers}
                        ${entryZone}
                        ${atrBand}
                        ${bars}
                        ${maLine}
                        ${planLines}
                        ${volumeBars}
                        <text x="${margin.left}" y="${volumeTop - 6}"
                            class="decision-chart-axis-label">VOLUME</text>
                        <line x1="${margin.left}" y1="${markerY}" x2="${plotRight}" y2="${markerY}"
                            class="decision-chart-price-marker-line ${latestTone}">
                            <title>${escapeDecisionHtml(markerTitle)}</title>
                        </line>
                        <rect x="${plotRight + 6}" y="${markerY - 10}" width="74" height="20" rx="3"
                            class="decision-chart-price-marker-box ${latestTone}">
                            <title>${escapeDecisionHtml(markerTitle)}</title>
                        </rect>
                        <text x="${plotRight + 43}" y="${markerY + 4}" text-anchor="middle"
                            class="decision-chart-price-marker-text">${chartPriceLabel(markerPrice)}</text>
                        ${timeLabels}
                        <g class="decision-chart-crosshair" data-chart-crosshair="${escapeDecisionHtml(this.hostId)}" hidden>
                            <line data-chart-crosshair-x x1="${xAt(candles.length - 1)}" y1="${margin.top}"
                                x2="${xAt(candles.length - 1)}" y2="${volumeTop + volumeHeight}" />
                            <line data-chart-crosshair-y x1="${margin.left}" y1="${y(latestClose)}"
                                x2="${plotRight}" y2="${y(latestClose)}" />
                            <circle data-chart-crosshair-dot cx="${xAt(candles.length - 1)}" cy="${y(latestClose)}" r="4" />
                        </g>
                        <rect x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${volumeTop + volumeHeight - margin.top}"
                            class="decision-chart-hit-area" data-chart-host-id="${escapeDecisionHtml(this.hostId)}" />
                    </svg>
                </div>
            `;
            this.inspectAtIndex(candles.length - 1, { revealCrosshair: false });
        }

        inspectAtIndex(index, options = {}) {
            const candles = this.series && Array.isArray(this.series.candles) ? this.series.candles : [];
            if (!this.host || !candles.length || !this.layout) return;
            const safeIndex = Math.max(0, Math.min(candles.length - 1, Number(index) || 0));
            this.lastInspectionIndex = safeIndex;
            const candle = candles[safeIndex];
            const ma = chartInspectionValue(candle.moving_average);
            const atr = chartInspectionValue(candle.atr);
            const volume = chartInspectionValue(candle.volume, v => v.toLocaleString("en-IN", { maximumFractionDigits: 0 }));
            const inspector = this.host.querySelector("[data-chart-inspector-copy]");
            if (inspector) {
                inspector.innerHTML = `
                    <strong>${escapeDecisionHtml(formatDecisionTime(candle.ts_open))}</strong>
                    <span>O ${chartPriceLabel(candle.open)}</span>
                    <span>H ${chartPriceLabel(candle.high)}</span>
                    <span>L ${chartPriceLabel(candle.low)}</span>
                    <span>C ${chartPriceLabel(candle.close)}</span>
                    <span>Vol ${escapeDecisionHtml(volume)}</span>
                    <span>SMA ${escapeDecisionHtml(ma)}</span>
                    <span>ATR ${escapeDecisionHtml(atr)}</span>
                    <span>${escapeDecisionHtml(chartPlanInspection(this.plan))}</span>
                `;
            }
            const crosshair = this.host.querySelector("[data-chart-crosshair]");
            const shell = this.host.querySelector("[data-chart-host]");
            const x = this.layout.xAt(safeIndex);
            const y = this.layout.y(candle.close);
            if (crosshair) {
                crosshair.hidden = options.revealCrosshair === false ? true : false;
                crosshair.querySelector("[data-chart-crosshair-x]")?.setAttribute("x1", x);
                crosshair.querySelector("[data-chart-crosshair-x]")?.setAttribute("x2", x);
                crosshair.querySelector("[data-chart-crosshair-y]")?.setAttribute("y1", y);
                crosshair.querySelector("[data-chart-crosshair-y]")?.setAttribute("y2", y);
                crosshair.querySelector("[data-chart-crosshair-dot]")?.setAttribute("cx", x);
                crosshair.querySelector("[data-chart-crosshair-dot]")?.setAttribute("cy", y);
            }
            if (shell) {
                shell.setAttribute(
                    "aria-label",
                    `Inspect candles with pointer or arrow keys. Selected ${safeIndex + 1} of ${candles.length}, ${formatDecisionTime(candle.ts_open)}, close ${chartPriceLabel(candle.close)}`
                );
            }
        }

        inspectFromPointer(event, hitArea) {
            const candles = this.series && Array.isArray(this.series.candles) ? this.series.candles : [];
            if (!candles.length || !this.layout || !hitArea) return;
            const rect = hitArea.getBoundingClientRect();
            if (!rect.width) return;
            const localX = this.layout.margin.left
                + ((event.clientX - rect.left) / rect.width) * this.layout.plotWidth;
            const raw = (localX - this.layout.margin.left) / this.layout.slot;
            this.inspectAtIndex(Math.floor(raw));
        }

        focusShell() {
            if (!this.host) return;
            activeInspectionHostId = this.hostId;
            this.host.querySelector("[data-chart-host]")?.focus({ preventScroll: true });
        }

        hideCrosshair() {
            if (!this.host) return;
            const crosshair = this.host.querySelector("[data-chart-crosshair]");
            if (crosshair) crosshair.hidden = true;
        }

        renderPlanStrip(plan) {
            if (!plan) return "";
            const freshness = activePlanFreshness;
            const targetList = Array.isArray(plan.targets) ? plan.targets : [];
            const firstTarget = targetList.length ? targetList[0] : null;
            const stopPct = chartPlanLevelPctLabel(plan, plan.stop_loss);
            const targetPct = firstTarget !== null ? chartPlanLevelPctLabel(plan, firstTarget) : "";
            const validity = chartPlanValidityLabel(plan, freshness);
            const validityClass = chartPlanValidityClass(plan, freshness);
            const validityTitle = freshness && typeof formatTradePlanFreshnessTitle === "function"
                ? formatTradePlanFreshnessTitle(freshness)
                : "";
            return `
                <div class="decision-chart-plan-strip">
                    <span class="decision-chart-plan-chip entry">
                        Entry ${escapeDecisionHtml(chartPlanEntryLabel(plan))}
                    </span>
                    <span class="decision-chart-plan-chip stop">
                        Stop ${escapeDecisionHtml(chartPriceLabel(plan.stop_loss))}
                        ${stopPct ? `<strong>${escapeDecisionHtml(stopPct)}</strong>` : ""}
                    </span>
                    ${firstTarget !== null ? `
                        <span class="decision-chart-plan-chip target">
                            T1 ${escapeDecisionHtml(chartPriceLabel(firstTarget))}
                            ${targetPct ? `<strong>${escapeDecisionHtml(targetPct)}</strong>` : ""}
                        </span>
                    ` : ""}
                    <span class="decision-chart-plan-chip rr">
                        R:R ${escapeDecisionHtml(formatDecisionRatio(plan.risk_reward))}
                    </span>
                    ${validity ? `
                        <span class="decision-chart-plan-chip validity ${escapeDecisionHtml(validityClass)}"
                            title="${escapeDecisionHtml(validityTitle)}">
                            ${escapeDecisionHtml(validity)}
                        </span>
                    ` : ""}
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

    function refreshActiveDecisionChart() {
        if (!activeChartSeries) return;
        renderProfessionalDecisionChart(activeChartSeries, activeChartPlan);
        const modal = document.getElementById("chart-modal");
        if (modal && !modal.hidden) {
            renderProfessionalDecisionChart(activeChartSeries, activeChartPlan, "chart-modal-canvas");
        }
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
        const rangeLabel = chartReturnedRangeLabel(series, Array.isArray(series.candles) ? series.candles.length : 0);
        meta.textContent = series.latest_ts
            ? `${rangeLabel} · ${series.timeframe} bars · latest candle ${formatDecisionTime(series.latest_ts)}${source}`
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
        activeChartInstrumentId = instrumentId;
        activeChartDecisionId = decisionId;
        const prefs = chartPreferences();
        renderChartControlState(prefs);
        host.innerHTML =
            '<div class="decision-chart-empty"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading persisted candles…</div>';
        try {
            const candidates = String(instrumentId).includes(":")
                ? [String(instrumentId)]
                : [String(instrumentId), `NSE:${instrumentId}`];
            let series = null;
            let lastError = null;
            for (const candidateId of candidates) {
                const path = `/api/v1/market/instruments/${encodeURIComponent(candidateId)}/candles?timeframe=${encodeURIComponent(prefs.timeframe)}&limit=${encodeURIComponent(prefs.limit)}`;
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
            activeChartSeries = series;
            activeChartPlan = plan;
            refreshActiveDecisionChart();
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

    function reloadActiveDecisionChart() {
        if (!activeChartInstrumentId || !activeChartDecisionId) return;
        loadDecisionChart(activeChartInstrumentId, activeChartPlan, activeChartDecisionId);
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
        renderChartControlState();
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

    document.addEventListener("pointermove", event => {
        const hitArea = event.target.closest("[data-chart-host-id]");
        if (!hitArea) return;
        const controller = decisionChartControllers.get(hitArea.getAttribute("data-chart-host-id"));
        if (controller) controller.inspectFromPointer(event, hitArea);
    });

    document.addEventListener("pointerdown", event => {
        const hitArea = event.target.closest("[data-chart-host-id]");
        if (!hitArea) return;
        const controller = decisionChartControllers.get(hitArea.getAttribute("data-chart-host-id"));
        if (!controller) return;
        controller.inspectFromPointer(event, hitArea);
        controller.focusShell();
    });

    document.addEventListener("click", event => {
        const hitArea = event.target.closest("[data-chart-host-id]");
        if (!hitArea) return;
        const controller = decisionChartControllers.get(hitArea.getAttribute("data-chart-host-id"));
        if (!controller) return;
        controller.inspectFromPointer(event, hitArea);
        controller.focusShell();
    });

    document.addEventListener("pointerleave", event => {
        const hitArea = event.target.closest("[data-chart-host-id]");
        if (!hitArea) return;
        const controller = decisionChartControllers.get(hitArea.getAttribute("data-chart-host-id"));
        if (controller) controller.hideCrosshair();
    }, true);

    document.addEventListener("focusin", event => {
        const shell = event.target.closest("[data-chart-host]");
        if (!shell) return;
        activeInspectionHostId = shell.getAttribute("data-chart-host");
        const controller = decisionChartControllers.get(shell.getAttribute("data-chart-host"));
        if (!controller) return;
        const candles = controller.series && Array.isArray(controller.series.candles)
            ? controller.series.candles
            : [];
        controller.inspectAtIndex(controller.lastInspectionIndex ?? candles.length - 1);
    });

    document.addEventListener("keydown", event => {
        const shell = event.target.closest("[data-chart-host]");
        const passiveFocus = event.target === document.body || event.target === document.documentElement;
        const hostId = shell ? shell.getAttribute("data-chart-host") : activeInspectionHostId;
        if (!hostId || (!shell && !passiveFocus)) return;
        const controller = decisionChartControllers.get(hostId);
        if (!controller || !controller.series || !Array.isArray(controller.series.candles)) return;
        const last = controller.series.candles.length - 1;
        const current = controller.lastInspectionIndex ?? last;
        let next = null;
        if (event.key === "ArrowLeft") next = current - 1;
        if (event.key === "ArrowRight") next = current + 1;
        if (event.key === "Home") next = 0;
        if (event.key === "End" || event.key.toLowerCase() === "r") next = last;
        if (next === null) return;
        event.preventDefault();
        controller.inspectAtIndex(next);
    });

    document.addEventListener("click", event => {
        const resetButton = event.target.closest("[data-chart-reset]");
        if (resetButton) {
            const controller = decisionChartControllers.get(resetButton.getAttribute("data-chart-reset"));
            const candles = controller && controller.series && Array.isArray(controller.series.candles)
                ? controller.series.candles
                : [];
            if (controller && candles.length) {
                controller.inspectAtIndex(candles.length - 1);
                controller.focusShell();
            }
            return;
        }
        const fullscreenButton = event.target.closest("#decision-chart-open-fullscreen");
        if (fullscreenButton) {
            openChartModal();
            return;
        }
        const timeframeButton = event.target.closest("[data-chart-timeframe]");
        if (timeframeButton) {
            const current = chartPreferences();
            const timeframe = timeframeButton.getAttribute("data-chart-timeframe");
            saveChartPreferences({ ...current, timeframe });
            renderChartControlState();
            reloadActiveDecisionChart();
            return;
        }
        const limitButton = event.target.closest("[data-chart-limit]");
        if (limitButton) {
            const current = chartPreferences();
            const limit = Number(limitButton.getAttribute("data-chart-limit"));
            saveChartPreferences({ ...current, limit });
            renderChartControlState();
            reloadActiveDecisionChart();
        }
    });
