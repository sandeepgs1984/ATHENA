

    // Blocking overlay while a validate (ingest + score) is in flight (owner
    // UX request) — otherwise only the clicked button showed a spinner while
    // the rest of the page stayed fully interactive, risking the trader
    // acting on stale/half-updated state mid-run. Centralized here so every
    // caller of validateSymbolsNow gets it for free.
    function showValidateOverlay(symbols) {
        if (!validateOverlay) return;
        if (validateOverlaySymbols) validateOverlaySymbols.textContent = symbols.join(", ");
        if (validateOverlayDetail) {
            validateOverlayDetail.textContent = "Ingesting quotes and recomputing the decision…";
        }
        validateOverlay.hidden = false;
        validateOverlay.setAttribute("aria-hidden", "false");
    }

    function hideValidateOverlay() {
        if (!validateOverlay) return;
        validateOverlay.hidden = true;
        validateOverlay.setAttribute("aria-hidden", "true");
    }

    /** Ensure candidates exist, then run scoped validate (ingest + score). */
    async function validateSymbolsNow(symbols, { button = null, refreshDecisions = false } = {}) {
        const list = [...new Set(
            (symbols || [])
                .map(s => String(s || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, ""))
                .filter(Boolean)
        )];
        if (!list.length) {
            showToast("Enter a symbol", "danger");
            return null;
        }
        const prev = button ? button.innerHTML : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validating…';
        }
        showValidateOverlay(list);
        try {
            for (const symbol of list) {
                try {
                    await apiRequest("/api/v1/market/candidates", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ symbol }),
                        skipToast: true,
                    });
                } catch (err) {
                    const detail = err?.data?.detail;
                    showToast(
                        typeof detail === "string" && detail.trim()
                            ? detail
                            : `Could not add ${symbol}`,
                        "danger"
                    );
                    return null;
                }
            }
            showToast(
                `Validating ${list.join(", ")} — live during session; after hours uses last session close…`,
                "success"
            );
            let valRes;
            try {
                valRes = await apiRequest("/api/v1/market/validate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ symbols: list }),
                    skipToast: true,
                });
            } catch (err) {
                const detail = err?.data?.detail;
                const title = err?.data?.title;
                let message =
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : (typeof title === "string" && title.trim() ? title : "Validate failed");
                if (/FRESHNESS|quotes are .* behind/i.test(message)) {
                    message =
                        "Quotes are too old relative to the validation clock. " +
                        "After hours, ATHENA uses last session close — if this still fails, " +
                        "Kite has no usable session quotes yet. Retry during market hours.";
                }
                showToast(message, "danger");
                throw err;
            }
            const d = (valRes && valRes.data) ? valRes.data : {};
            const ok = String(d.status || "").toUpperCase() === "COMPLETED";
            const mode = String(d.as_of_mode || "").toLowerCase();
            let asOfLabel = "";
            if (d.as_of) {
                const asOfDate = new Date(d.as_of);
                if (!Number.isNaN(asOfDate.getTime())) {
                    asOfLabel = asOfDate.toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        hour: "numeric",
                        minute: "2-digit",
                        hour12: true,
                        timeZone: "Asia/Kolkata",
                    });
                }
            }
            let modeLabel = "";
            if (mode === "session_close" && asOfLabel) {
                modeLabel = ` · session-close analysis as of ${asOfLabel} IST`;
            } else if (mode === "live" && asOfLabel) {
                modeLabel = ` · live as of ${asOfLabel} IST`;
            } else if (mode === "session_close") {
                modeLabel = " · session-close analysis (not live)";
            }
            showToast(
                `${list.join(", ")}: ${d.status || "done"}${modeLabel} · Eligible ${d.eligible ?? "—"} · ` +
                `Excluded ${d.excluded ?? "—"} · decisions ${d.decisions ?? "—"}`,
                ok ? (mode === "session_close" ? "warning" : "success") : "warning"
            );
            if (typeof loadMarketIntelligence === "function") {
                await loadMarketIntelligence();
            }
            if (refreshDecisions && typeof loadDecisionsWorkspace === "function") {
                await loadDecisionsWorkspace({
                    preferInstrumentId: list.length === 1 ? list[0] : null,
                });
            }
            return valRes;
        } finally {
            if (button) {
                button.disabled = false;
                if (prev != null) button.innerHTML = prev;
            }
            hideValidateOverlay();
        }
    }

    async function removeCandidateNow(symbol, { button = null } = {}) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return false;
        const confirmed = window.confirm(
            `Remove ${bare} from future validation?\n\n` +
            "Existing decisions, traces, and replay evidence will be preserved."
        );
        if (!confirmed) return false;

        const previous = button ? button.innerHTML : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing…';
        }
        try {
            await apiRequest(
                `/api/v1/market/candidates/${encodeURIComponent(bare)}`,
                { method: "DELETE", skipToast: true }
            );
            showToast(
                `${bare} removed from future validation · decision history preserved`,
                "success"
            );
            if (typeof loadCandidateList === "function") {
                await loadCandidateList();
            }
            return true;
        } catch (err) {
            if (err?.status === 404) {
                showToast(`${bare} is not in the active validation list`, "warning");
            } else {
                const detail = err?.data?.detail;
                showToast(
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : `Failed to remove ${bare} from validation`,
                    "danger"
                );
            }
            return false;
        } finally {
            if (button && !button.disabled && previous != null) {
                button.innerHTML = previous;
            } else if (button && previous != null) {
                button.disabled = false;
                button.innerHTML = previous;
            }
        }
    }

    // Cache for universe trace results to speed up detail views
    let universeCache = {};

    // MI-2: real 4-dimension categorical Market Health breakdown (breadth/
    // trend_quality/momentum/volatility) — reuses the exact contextMetricCard/
    // contextChipTone/friendlyLabel helpers already established for the
    // Decision Brief's own Market Context rendering (15-decision-brief-
    // context.js), same MarketHealthLabel enum, one component language.
    function renderMarketHealthGrid(dimensions) {
        const host = document.getElementById("market-health-grid");
        if (!host) return;
        const entries = Object.entries(dimensions || {});
        if (!entries.length) {
            host.innerHTML = '<p class="context-caption unknown">Not available yet — re-run validation to capture a market-health assessment.</p>';
            return;
        }
        host.innerHTML = entries
            .map(([key, label]) => {
                const displayName = key === "volatility"
                    ? "Volatility Quality"
                    : friendlyLabel(key);
                return contextMetricCard(displayName, label, contextChipTone(label));
            })
            .join("");
    }

    // MI-3: Validation Pipeline funnel — typed stages from
    // GET /api/v1/pipelines/validation-funnel (Universe→Eligible→Filtered→
    // Watch→Trade). Filtered is server-side arithmetic; UI never recomputes.
    function renderValidationFunnel(funnel) {
        const host = document.getElementById("validation-funnel");
        const asOfEl = document.getElementById("validation-funnel-asof");
        const emptyEl = document.getElementById("validation-funnel-empty");
        if (!host) return;

        const stages = (funnel && funnel.stages) || [];
        const available = !!(funnel && funnel.available);

        if (asOfEl) {
            asOfEl.textContent = available && funnel.as_of
                ? `Last Updated: ${formatDecisionTime(funnel.as_of)}`
                : "";
        }
        if (emptyEl) {
            emptyEl.hidden = available;
        }

        if (!stages.length) {
            host.innerHTML = '<div class="text-muted">No funnel data.</div>';
            return;
        }

        host.innerHTML = stages.map((stage) => {
            const iconByStage = {
                universe: "fa-circle-nodes",
                eligible: "fa-tags",
                filtered: "fa-filter-circle-xmark",
                watch: "fa-tag",
                trade: "fa-stamp",
            };
            const pct = stage.pct_of_universe == null
                ? "—"
                : `${Number(stage.pct_of_universe).toFixed(1)}%`;
            const tradeClass = stage.id === "trade" ? " is-trade" : "";
            const countLabel = stage.id === "universe"
                ? `${stage.count} Symbols`
                : String(stage.count);
            // Labels/ids come from the typed ValidationFunnel DTO only —
            // never free-form user input. Still coerce via String().
            const id = String(stage.id || "");
            const label = String(stage.label || "");
            return (
                `<div class="validation-funnel-stage${tradeClass}" data-stage="${id}">` +
                `<span class="validation-funnel-stage-icon" aria-hidden="true">` +
                `<i class="fa-solid ${iconByStage[id] || "fa-circle"}"></i></span>` +
                `<span class="validation-funnel-stage-label">${label}</span>` +
                `<strong class="validation-funnel-stage-count">${countLabel}</strong>` +
                `<span class="validation-funnel-stage-pct">${pct}</span>` +
                `</div>`
            );
        }).join("");
    }

    async function loadMarketIntelligence() {
        try {
            await loadCandidateList();
            await loadSavedSymbols();

            // 1. Fetch Volatility Regime / Universe from latest Pipeline run,
            //    and the typed Validation Pipeline funnel (MI-3) in parallel.
            const [runsRes, funnelRes] = await Promise.all([
                apiRequest("/api/v1/pipelines/runs").catch(() => null),
                apiRequest("/api/v1/pipelines/validation-funnel").catch(() => null),
            ]);
            renderValidationFunnel(funnelRes && funnelRes.data ? funnelRes.data : null);
            let regime = null;
            let regimeAsOf = null;
            let universe = {};
            let qualified = [];
            let universeNote = null;

            if (runsRes && runsRes.data && runsRes.data.length > 0) {
                const extractData = (r) => {
                    const ctx =
                        r.final_context ||
                        (r.pipeline_runs && r.pipeline_runs[0]
                            ? r.pipeline_runs[0].final_context
                            : null);
                    return ctx && ctx.data ? ctx.data : {};
                };
                // Newest first — prefer known volatility over older UNKNOWN payloads
                const runs = [...runsRes.data].sort(
                    (a, b) => new Date(b.as_of || 0) - new Date(a.as_of || 0)
                );
                const isUnknownVol = (reg) => {
                    const v = String((reg && reg.volatility) || "").toUpperCase();
                    return !v || v.includes("UNKNOWN");
                };

                // A scoped validate writes a run holding only the symbols it was
                // asked about, so reading the newest run alone showed just that
                // symbol and hid everything validated earlier the same day. Each
                // symbol keeps the verdict of the newest run that covered it —
                // the same merge the Universe table and the funnel counts use.
                const dayKey = (iso) => new Date(iso || 0).toDateString();
                let leading = null;
                for (const r of runs) {
                    const status = (r.overall_status || "").toString().toUpperCase();
                    if (status === "FAILED" || status === "RUNNING") continue;
                    const data = extractData(r);
                    const members = data.universe_members || {};
                    const hasMembers = Object.keys(members).length > 0;
                    const reg = data.regime_assessment || null;

                    if (!regime && reg) {
                        regime = reg;
                        regimeAsOf = r.as_of || null;
                    } else if (
                        regime &&
                        isUnknownVol(regime) &&
                        reg &&
                        !isUnknownVol(reg)
                    ) {
                        regime = reg;
                        regimeAsOf = r.as_of || null;
                    }
                    if (!hasMembers) continue;
                    if (!leading) {
                        leading = r;
                        universeNote = data.universe_note || null;
                        const summary = data.universe_summary || {};
                        if (!universeNote && summary.excluded != null && summary.included === 0 && summary.evaluated > 0) {
                            universeNote =
                                `All ${summary.evaluated} evaluated symbols were Excluded (e.g. need ≥30 daily bars). ` +
                                "Inspect Trace for rule evidence. Increase ingestion lookback_days if history is short.";
                        }
                    } else if (dayKey(r.as_of) !== dayKey(leading.as_of)) {
                        continue;
                    }
                    // A symbol's decision comes from the same run that judged
                    // it, so a name re-validated without qualifying does not
                    // keep the WATCH/TRADE it earned in an earlier run.
                    const runQualified = data.qualified_today || [];
                    for (const [sym, member] of Object.entries(members)) {
                        if (sym in universe) continue;
                        universe[sym] = member;
                        for (const row of runQualified) {
                            if (String(row.symbol || "").toUpperCase() === sym.toUpperCase()) {
                                qualified.push(row);
                            }
                        }
                    }
                }
                qualified.sort((a, b) =>
                    String(a.symbol || "").localeCompare(String(b.symbol || ""))
                );
                universeCache = universe;
            }

            // 2. Render Market Summary Hero (MI-2). Trend/Volatility/Gap reuse
            // the exact contextChipTone()/friendlyLabel() tone logic already
            // established for the Decision Brief's own regime rendering — one
            // tone system for the same RegimeLabel enum, not two parallel ones.
            const trendBadge = document.getElementById("regime-trend-badge");
            const volBadge = document.getElementById("regime-vol-badge");
            const gapBadge = document.getElementById("regime-gap-badge");
            const evidenceText = document.getElementById("regime-evidence-text");
            const asOfEl = document.getElementById("market-summary-asof");

            if (regime && trendBadge && volBadge && gapBadge && evidenceText) {
                if (asOfEl) {
                    asOfEl.textContent = regimeAsOf ? `As of ${formatDecisionTime(regimeAsOf)}` : "";
                }

                // Falls back to each dimension's own *_UNKNOWN sentinel, never a
                // specific assessed-looking state (e.g. "no gap"/"normal
                // volatility") for a field that's actually just missing.
                const trendRaw = regime.trend || "TREND_UNKNOWN";
                trendBadge.textContent = friendlyLabel(trendRaw);
                trendBadge.className = `hero-metric-band tone-${contextChipTone(trendRaw)}-text`;

                const volRaw = regime.volatility || "VOLATILITY_UNKNOWN";
                volBadge.textContent = friendlyLabel(volRaw);
                volBadge.className = `hero-metric-band tone-${contextChipTone(volRaw)}-text`;

                const gapRaw = regime.gap || "GAP_UNKNOWN";
                gapBadge.textContent = friendlyLabel(gapRaw);
                gapBadge.className = `hero-metric-band tone-${contextChipTone(gapRaw)}-text`;

                renderMarketHealthGrid(regime.market_health);

                // Explanation — soften raw enum tokens for display
                let evidence = regime.explanation || "No attribution summary available.";
                evidence = evidence
                    .replace(/NORMAL_VOLATILITY/g, "Normal volatility")
                    .replace(/HIGH_VOLATILITY/g, "High volatility")
                    .replace(/LOW_VOLATILITY/g, "Low volatility")
                    .replace(/VOLATILITY_UNKNOWN/g, "Volatility unknown (VIX missing)")
                    .replace(/BULL_TREND/g, "Bullish")
                    .replace(/BEAR_TREND/g, "Bearish")
                    .replace(/GAP_DOWN/g, "Gap down")
                    .replace(/GAP_UP/g, "Gap up")
                    .replace(/NO_GAP/g, "No gap")
                    .replace(/SIDEWAYS/g, "Sideways");
                evidenceText.textContent = evidence;
            } else if (trendBadge && volBadge && gapBadge && evidenceText) {
                if (asOfEl) asOfEl.textContent = "";
                trendBadge.textContent = "Unknown";
                trendBadge.className = "hero-metric-band tone-unknown-text";
                volBadge.textContent = "Unknown";
                volBadge.className = "hero-metric-band tone-unknown-text";
                gapBadge.textContent = "Unknown";
                gapBadge.className = "hero-metric-band tone-unknown-text";
                renderMarketHealthGrid({});
                evidenceText.textContent =
                    "No regime assessment from the latest validation run yet. " +
                    "Re-run ./athena-daily smoke (after the latest update) — regime is written from the scan. " +
                    "Volatility can stay unavailable without India VIX in the snapshot.";
            }

            // 3. Fetch and Render Calendar Grid & Events
            const calRes = await apiRequest("/api/v1/dashboard/calendar").catch(() => null);
            if (calRes && calRes.data) {
                renderCalendar(calRes.data);
                renderUpcomingEvents(calRes.data);
            }

            // 4. Render Universe list table + qualified layer
            renderUniverseTable(universe, universeNote);
            renderQualifiedToday(qualified);

            // 5. MI-5: Recent Activity from the same runs we already fetched.
            if (runsRes && runsRes.data) {
                renderRecentActivity(runsRes.data);
            } else {
                renderRecentActivity([]);
            }
            // Resume an in-flight full-validation poll if the host still has one.
            pollFullValidationStatus({ silent: true });

        } catch (err) {
            console.error("Failed to load market intelligence data", err);
            const trendBadge = document.getElementById("regime-trend-badge");
            const volBadge = document.getElementById("regime-vol-badge");
            const gapBadge = document.getElementById("regime-gap-badge");
            const evidenceText = document.getElementById("regime-evidence-text");
            const universeBody = document.getElementById("universe-list-body");
            if (trendBadge) trendBadge.textContent = "ERROR";
            if (volBadge) volBadge.textContent = "ERROR";
            if (gapBadge) gapBadge.textContent = "ERROR";
            if (evidenceText) evidenceText.textContent = "Market intelligence failed to load. Use refresh to retry.";
            if (universeBody) {
                universeBody.innerHTML = `<tr><td colspan="3" class="text-muted text-center" style="padding: 24px;">Failed to load universe members.</td></tr>`;
            }
            showToast("Failed to load market intelligence data", "danger");
        }
    }

    function renderRecentActivity(runs) {
        const host = document.getElementById("market-recent-activity");
        if (!host) return;
        const sorted = [...(runs || [])].sort(
            (a, b) => new Date(b.as_of || 0) - new Date(a.as_of || 0)
        ).slice(0, 12);
        if (!sorted.length) {
            host.innerHTML = '<li class="text-muted">No validation runs yet.</li>';
            return;
        }
        host.innerHTML = sorted.map((r) => {
            const status = String(r.overall_status || "unknown");
            const failed = status.toUpperCase() === "FAILED";
            const when = r.as_of ? formatDecisionTime(r.as_of) : "—";
            const runId = String(r.run_id || "").slice(0, 18);
            const label = failed ? "Validation failed" : "Market validation completed";
            return (
                `<li>` +
                `<span class="market-activity-dot${failed ? " is-failed" : ""}" aria-hidden="true"></span>` +
                `<span class="market-activity-main">${label}` +
                (runId ? `<br><span class="text-muted">${runId}</span>` : "") +
                `</span>` +
                `<span class="market-activity-meta">${when}</span>` +
                `</li>`
            );
        }).join("");
    }

    let _fullValidationPollTimer = null;

    function renderFullValidationProgress(progress) {
        const el = document.getElementById("full-validation-progress");
        const runBtn = document.getElementById("mi-run-full-validation-btn");
        const allBtn = document.getElementById("universe-validate-all-btn");
        if (!el) return;
        if (!progress) {
            el.hidden = true;
            el.textContent = "";
            el.className = "full-validation-progress text-muted";
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
            return;
        }
        const state = String(progress.state || "idle");
        const stage = String(progress.stage || "idle");
        const total = progress.symbols_total ?? 0;
        const done = progress.symbols_completed ?? 0;
        el.hidden = state === "idle";
        el.className = `full-validation-progress text-muted is-${state}`;
        if (state === "running") {
            el.textContent =
                `Running full validation… ${stage}` +
                (total ? ` · ${done}/${total} symbols` : "") +
                " (this can take several minutes)";
            if (runBtn) runBtn.disabled = true;
            if (allBtn) allBtn.disabled = true;
        } else if (state === "completed") {
            el.textContent =
                `Full validation completed` +
                (progress.run_id ? ` · ${progress.run_id}` : "") +
                (total ? ` · ${total} symbols` : "");
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
        } else if (state === "failed") {
            el.textContent =
                `Full validation failed` +
                (progress.detail ? `: ${progress.detail}` : "");
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
        } else {
            el.hidden = true;
            if (runBtn) runBtn.disabled = false;
            if (allBtn) allBtn.disabled = false;
        }
    }

    async function pollFullValidationStatus({ silent = false } = {}) {
        try {
            const res = await apiRequest("/api/v1/market/validate-all", { skipToast: true });
            const progress = res && res.data ? res.data : null;
            renderFullValidationProgress(progress);
            if (progress && progress.state === "running") {
                if (_fullValidationPollTimer) clearTimeout(_fullValidationPollTimer);
                _fullValidationPollTimer = setTimeout(() => pollFullValidationStatus(), 3000);
            } else if (progress && progress.state === "completed" && !silent) {
                showToast("Full validation completed", "success");
                if (typeof loadMarketIntelligence === "function") {
                    await loadMarketIntelligence();
                }
            } else if (progress && progress.state === "failed" && !silent) {
                showToast(progress.detail || "Full validation failed", "danger");
            }
        } catch (err) {
            if (!silent) {
                console.error("full validation status poll failed", err);
            }
        }
    }

    async function startFullUniverseValidation() {
        try {
            const res = await apiRequest("/api/v1/market/validate-all", {
                method: "POST",
                skipToast: true,
            });
            renderFullValidationProgress(res && res.data ? res.data : null);
            showToast("Full validation started in the background", "success");
            pollFullValidationStatus();
        } catch (err) {
            const status = err?.status;
            const detail = err?.data?.detail || err?.data?.title;
            if (status === 404) {
                showToast(
                    "Full validation API not loaded — restart ./athena-serve and hard-refresh",
                    "danger"
                );
                return;
            }
            showToast(
                typeof detail === "string" && detail.trim()
                    ? detail
                    : "Could not start full validation",
                "danger"
            );
        }
    }

    function renderCalendar(calData) {
        const gridContainer = document.getElementById("calendar-grid-container");
        const monthYearLabel = document.getElementById("calendar-month-year");
        if (!gridContainer) return;

        gridContainer.innerHTML = "";

        // Build weekday headers (Mon - Sun)
        const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        days.forEach(day => {
            const header = document.createElement("div");
            header.className = "calendar-day-header";
            header.textContent = day;
            gridContainer.appendChild(header);
        });

        // Use the current month for display
        const displayDate = new Date();
        const displayYear = displayDate.getFullYear();
        const displayMonth = displayDate.getMonth(); // 0-indexed

        // Set Month/Year label
        const monthNames = [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ];
        monthYearLabel.textContent = `${monthNames[displayMonth]} ${displayYear}`;

        // Get first day of month (0 = Sunday, 1 = Monday...)
        const firstDay = new Date(displayYear, displayMonth, 1).getDay();
        // Convert to Mon-first offset (0 = Monday, 6 = Sunday)
        const startOffset = firstDay === 0 ? 6 : firstDay - 1;

        // Get total days in month
        const totalDays = new Date(displayYear, displayMonth + 1, 0).getDate();

        // Create mapping sets for fast lookups
        const holidaysMap = new Map((calData.holidays || []).map(h => [h.date, h.name]));
        const specialMap = new Map((calData.special_sessions || []).map(s => [s.date, s]));
        const weeklyExpiries = new Set(calData.weekly_expiries || []);
        const monthlyExpiries = new Set(calData.monthly_expiries || []);

        // Inject empty offset cells
        for (let i = 0; i < startOffset; i++) {
            const emptyCell = document.createElement("div");
            emptyCell.className = "calendar-cell empty";
            gridContainer.appendChild(emptyCell);
        }

        // Inject day cells
        for (let dayNum = 1; dayNum <= totalDays; dayNum++) {
            const cell = document.createElement("div");
            cell.className = "calendar-cell";

            // Format date string YYYY-MM-DD (zero-padded)
            const dateStr = `${displayYear}-${String(displayMonth + 1).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;

            // Add day number
            const label = document.createElement("span");
            label.textContent = dayNum;
            cell.appendChild(label);

            // Check attributes
            const isWeekend = new Date(displayYear, displayMonth, dayNum).getDay() === 0 || 
                              new Date(displayYear, displayMonth, dayNum).getDay() === 6;
            const holidayName = holidaysMap.get(dateStr);
            const specialSession = specialMap.get(dateStr);
            const isWeeklyExp = weeklyExpiries.has(dateStr);
            const isMonthlyExp = monthlyExpiries.has(dateStr);
            const isToday = displayDate.getDate() === dayNum && displayDate.getMonth() === displayMonth;

            // Apply classes
            if (isWeekend) cell.classList.add("weekend");
            if (holidayName) cell.classList.add("holiday");
            if (specialSession) cell.classList.add("special");
            if (isWeeklyExp || isMonthlyExp) cell.classList.add("expiry");
            if (isToday) cell.classList.add("today-cell");

            // Add hover tooltip detail (HTML title attribute for ease)
            let tooltip = `Date: ${dateStr}`;
            if (holidayName) tooltip += `\nHoliday: ${holidayName}`;
            if (specialSession) tooltip += `\nSpecial: ${specialSession.name} (${specialSession.timings_note || 'Muhurat session'})`;
            if (isWeeklyExp) tooltip += `\nWeekly Expiry`;
            if (isMonthlyExp) tooltip += `\nMonthly Expiry`;
            cell.title = tooltip;

            // Add cell dots indicators
            const dotsContainer = document.createElement("div");
            dotsContainer.className = "calendar-cell-indicators";

            if (holidayName) {
                const dot = document.createElement("span");
                dot.className = "cell-dot holiday";
                dotsContainer.appendChild(dot);
            }
            if (specialSession) {
                const dot = document.createElement("span");
                dot.className = "cell-dot special";
                dotsContainer.appendChild(dot);
            }
            if (isWeeklyExp || isMonthlyExp) {
                const dot = document.createElement("span");
                dot.className = "cell-dot expiry";
                dotsContainer.appendChild(dot);
            }

            cell.appendChild(dotsContainer);
            gridContainer.appendChild(cell);
        }
    }

    function renderUpcomingEvents(calData) {
        const container = document.getElementById("upcoming-events-container");
        if (!container) return;

        container.innerHTML = "";

        const allEvents = [];

        // Aggregate weekly expiries
        (calData.weekly_expiries || []).forEach(date => {
            allEvents.push({ date, kind: "weekly_expiry", name: "Weekly F&O Expiry", tagClass: "expiry-tag", tagText: "weekly exp" });
        });
        // Aggregate monthly expiries
        (calData.monthly_expiries || []).forEach(date => {
            allEvents.push({ date, kind: "monthly_expiry", name: "Monthly F&O Expiry", tagClass: "expiry-tag", tagText: "monthly exp" });
        });
        // Aggregate holidays
        (calData.holidays || []).forEach(h => {
            allEvents.push({ date: h.date, kind: "holiday", name: h.name, tagClass: "holiday-tag", tagText: "holiday" });
        });
        // Aggregate events
        (calData.events || []).forEach(e => {
            allEvents.push({ date: e.date, kind: e.kind, name: e.name, tagClass: "macro", tagText: e.kind });
        });

        // Filter events for displays after today or within display range
        const displayDate = new Date();
        const displayYear = displayDate.getFullYear();
        const displayMonth = displayDate.getMonth();
        const displayMonthStr = String(displayMonth + 1).padStart(2, '0');

        const currentMonthEvents = allEvents.filter(ev => {
            return ev.date.startsWith(`${displayYear}-${displayMonthStr}`);
        });

        // Sort by date ascending
        currentMonthEvents.sort((a, b) => a.date.localeCompare(b.date));

        if (currentMonthEvents.length === 0) {
            container.innerHTML = `<div class="text-muted text-center" style="padding: 12px 0; font-size: 0.85rem;">No scheduled events this month.</div>`;
            return;
        }

        currentMonthEvents.forEach(ev => {
            const item = document.createElement("div");
            item.className = "event-item";

            // Format date for display
            const dateObj = new Date(ev.date);
            const dateText = dateObj.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

            item.innerHTML = `
                <div class="event-info">
                    <span class="event-title">${ev.name}</span>
                    <span class="event-meta">${dateText} (${ev.date})</span>
                </div>
                <span class="event-tag ${ev.tagClass}">${ev.tagText}</span>
            `;
            container.appendChild(item);
        });
    }

    function renderUniverseTable(universeMembers, universeNote) {
        const tbody = document.getElementById("universe-list-body");
        if (!tbody) return;

        tbody.innerHTML = "";

        const symbols = Object.keys(universeMembers);

        if (symbols.length === 0) {
            const note = universeNote
                ? universeNote
                : "No eligibility results yet. Add symbols above, then run <code>athena cycle</code> / <code>./athena-run-due</code>.";
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="text-muted text-center" style="padding: 24px;">
                        ${note}
                    </td>
                </tr>
            `;
            return;
        }

        symbols.forEach(sym => {
            const member = universeMembers[sym];
            const tr = document.createElement("tr");
            tr.setAttribute("data-symbol", sym.toUpperCase());

            const statusBadge = member.included 
                ? '<span class="symbol-status-badge included"><i class="fas fa-check"></i> Eligible</span>'
                : '<span class="symbol-status-badge excluded"><i class="fas fa-ban"></i> Excluded</span>';

            tr.innerHTML = `
                <td class="symbol-name-col">${sym}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="inspect-btn" onclick="openTraceModal('${sym}')">
                        <i class="fas fa-search-plus"></i> Inspect Trace
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderQualifiedToday(qualified) {
        const body = document.getElementById("qualified-today-body");
        if (!body) return;
        const rows = Array.isArray(qualified) ? qualified : [];
        if (rows.length === 0) {
            body.className = "text-muted text-center";
            body.style.padding = "12px 0";
            body.innerHTML = "No Watch or Trade candidates from the latest validation run.";
            return;
        }
        body.className = "";
        body.style.padding = "0";
        body.innerHTML = `
            <div class="qualified-list">
                ${rows.map(r => {
                    const type = r.decision_type || "";
                    const stance = decisionStance(type, r.direction || "NONE");
                    const summary = formatDecisionSummary(r.explanation || "", type, []);
                    return `
                        <div class="qualified-row">
                            <div class="qualified-row-top">
                                <span class="symbol-name-col">${r.symbol || r.instrument_id || ""}</span>
                                <span class="stance-chip ${stance.cls}">${stance.label}</span>
                                <span class="type-chip type-${String(type).toLowerCase()}">${type ? escapeDecisionHtml(friendlyAnalysisName(type)) : "—"}</span>
                            </div>
                            <p class="qualified-summary">${summary.headline}</p>
                            ${summary.scoreChip}
                            ${summary.gateChips}
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    }

    async function loadCandidateList() {
        const bodyEl = document.getElementById("candidate-list-body");
        const emptyEl = document.getElementById("candidate-list-empty");
        const countEl = document.getElementById("candidate-count");
        const candidateSearch = document.getElementById("candidate-search-input");
        if (!bodyEl) return;
        try {
            const res = await apiRequest("/api/v1/market/candidates");
            const rows = (res && res.data && res.data.candidates) ? res.data.candidates : [];
            bodyEl.innerHTML = "";
            populateUniverseSectorFilter(rows);
            if (countEl) {
                countEl.textContent = `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
            }
            if (rows.length === 0) {
                if (emptyEl) {
                    emptyEl.textContent = "No symbols in the universe yet.";
                    emptyEl.style.display = "block";
                }
                return;
            }
            if (emptyEl) emptyEl.style.display = "none";
            rows.forEach(c => {
                const tr = document.createElement("tr");
                const status = String(c.status || "PENDING").toUpperCase();
                const sector = c.sector || "";
                tr.dataset.symbol = String(c.symbol || "").toUpperCase();
                tr.dataset.status = status;
                tr.dataset.sector = sector.toUpperCase();
                const statusClass = status === "ELIGIBLE"
                    ? "included"
                    : status === "EXCLUDED"
                        ? "excluded"
                        : status === "UNRESOLVED"
                            ? "unresolved"
                            : "pending";
                const statusLabel = status === "ELIGIBLE"
                    ? "Eligible"
                    : status === "EXCLUDED"
                        ? "Excluded"
                        : status === "UNRESOLVED"
                            ? "Unresolved"
                            : "Pending";
                const statusIcon = status === "ELIGIBLE"
                    ? "fa-check"
                    : status === "EXCLUDED"
                        ? "fa-ban"
                        : status === "UNRESOLVED"
                            ? "fa-triangle-exclamation"
                            : "fa-clock";
                const eligibility = c.eligibility_summary
                    ? String(c.eligibility_summary)
                    : "—";
                const eligibilityShort = eligibility.length > 42
                    ? `${eligibility.slice(0, 40)}…`
                    : eligibility;
                const lastValidated = c.last_validated_ts
                    ? formatDecisionTime(c.last_validated_ts)
                    : "—";
                const canTrace = status === "ELIGIBLE" || status === "EXCLUDED";
                tr.innerHTML = `
                    <td><strong class="symbol-name-col">${c.symbol}</strong></td>
                    <td class="text-muted">${sector || "—"}</td>
                    <td>
                        <span class="symbol-status-badge ${statusClass}">
                            <i class="fas ${statusIcon}"></i>
                            ${statusLabel}
                        </span>
                    </td>
                    <td class="universe-eligibility-cell" title="${eligibility.replace(/"/g, "&quot;")}">${eligibilityShort}</td>
                    <td class="text-muted">${lastValidated}</td>
                    <td>
                        <div class="candidate-row-actions">
                            <button type="button" class="inspect-btn candidate-validate-btn" data-symbol="${c.symbol}" title="Re-run ingest + score">
                                <i class="fas fa-bolt"></i>
                            </button>
                            ${canTrace ? `<button type="button" class="inspect-btn candidate-trace-btn" data-symbol="${c.symbol}" title="Inspect Trace"><i class="fas fa-search"></i></button>` : ""}
                            <button type="button" class="inspect-btn candidate-remove-btn" data-symbol="${c.symbol}" title="Remove candidate">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    </td>
                `;
                bodyEl.appendChild(tr);
            });
            applyUniverseFilters();
            bodyEl.querySelectorAll(".candidate-validate-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await validateSymbolsNow([sym], { button: btn, refreshDecisions: true });
                });
            });
            bodyEl.querySelectorAll(".candidate-remove-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await removeCandidateNow(sym, { button: btn });
                });
            });
            bodyEl.querySelectorAll(".candidate-trace-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const sym = btn.getAttribute("data-symbol");
                    if (sym && typeof window.openTraceModal === "function") {
                        window.openTraceModal(sym);
                    }
                });
            });
        } catch (err) {
            console.error("Failed to load candidates", err);
            if (emptyEl) {
                emptyEl.style.display = "block";
                emptyEl.textContent = "Failed to load universe list.";
            }
            if (countEl) countEl.textContent = "Unavailable";
        }
    }

    function populateUniverseSectorFilter(rows) {
        const select = document.getElementById("universe-sector-filter");
        if (!select) return;
        const current = select.value || "all";
        const sectors = [...new Set(
            rows.map(r => String(r.sector || "").trim()).filter(Boolean)
        )].sort((a, b) => a.localeCompare(b));
        select.innerHTML = '<option value="all">All sectors</option>' +
            sectors.map(s => `<option value="${s}">${s}</option>`).join("");
        select.value = sectors.includes(current) ? current : "all";
    }

    function applyUniverseFilters() {
        const bodyEl = document.getElementById("candidate-list-body");
        const emptyEl = document.getElementById("candidate-list-empty");
        const countEl = document.getElementById("candidate-count");
        const searchEl = document.getElementById("candidate-search-input");
        const statusEl = document.getElementById("universe-status-filter");
        const sectorEl = document.getElementById("universe-sector-filter");
        if (!bodyEl) return;
        const query = String((searchEl && searchEl.value) || "").trim().toUpperCase();
        const statusFilter = String((statusEl && statusEl.value) || "all").toUpperCase();
        const sectorFilter = String((sectorEl && sectorEl.value) || "all").toUpperCase();
        const rows = Array.from(bodyEl.querySelectorAll("tr"));
        let visible = 0;
        rows.forEach(row => {
            const matchesQuery = !query || (row.dataset.symbol || "").includes(query);
            const matchesStatus = statusFilter === "ALL" || (row.dataset.status || "") === statusFilter;
            const matchesSector = sectorFilter === "ALL" || (row.dataset.sector || "") === sectorFilter;
            const show = matchesQuery && matchesStatus && matchesSector;
            row.hidden = !show;
            if (show) visible += 1;
        });
        if (countEl) {
            const filtering = query || statusFilter !== "ALL" || sectorFilter !== "ALL";
            countEl.textContent = filtering
                ? `${visible} of ${rows.length}`
                : `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
        }
        if (emptyEl) {
            emptyEl.textContent = visible === 0
                ? (rows.length === 0 ? "No symbols in the universe yet." : "No symbols match the current filters.")
                : "No symbols in the universe yet.";
            emptyEl.style.display = visible === 0 ? "block" : "none";
        }
    }

    function filterCandidateList(rawQuery) {
        applyUniverseFilters();
    }

    const candidateAddBtn = document.getElementById("candidate-add-btn");
    const candidateInput = document.getElementById("candidate-symbol-input");
    const candidateSearchInput = document.getElementById("candidate-search-input");
    if (candidateSearchInput) {
        candidateSearchInput.addEventListener("input", () => applyUniverseFilters());
    }
    const universeStatusFilter = document.getElementById("universe-status-filter");
    if (universeStatusFilter) {
        universeStatusFilter.addEventListener("change", () => applyUniverseFilters());
    }
    const universeSectorFilter = document.getElementById("universe-sector-filter");
    if (universeSectorFilter) {
        universeSectorFilter.addEventListener("change", () => applyUniverseFilters());
    }
    if (candidateAddBtn && candidateInput) {
        const addAndValidateCandidate = async () => {
            const symbol = (candidateInput.value || "").trim().toUpperCase();
            if (!symbol) {
                showToast("Enter a symbol", "danger");
                return;
            }
            candidateInput.value = "";
            await validateSymbolsNow([symbol], { button: candidateAddBtn, refreshDecisions: true });
        };
        candidateAddBtn.addEventListener("click", addAndValidateCandidate);
        candidateInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                addAndValidateCandidate();
            }
        });
    }

    // UX-9b: "Saved Symbols" — a passive personal watch list, deliberately
    // independent of the Stock List / owner-candidates validation list above
    // (saving a symbol here never seeds ingest/scoring) and of the automated
    // M4.3 watchlist package (that one is fully config-driven, no owner input).
    async function removeSavedSymbolNow(symbol, { button = null } = {}) {
        const bare = String(symbol || "").trim().toUpperCase().replace(/^NSE:|^BSE:/, "");
        if (!bare) return false;
        const previous = button ? button.innerHTML : null;
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Removing…';
        }
        try {
            await apiRequest(
                `/api/v1/saved-symbols/${encodeURIComponent(bare)}`,
                { method: "DELETE", skipToast: true }
            );
            showToast(`${bare} removed from Saved Symbols`, "success");
            await loadSavedSymbols();
            return true;
        } catch (err) {
            if (err?.status === 404) {
                showToast(`${bare} is not in Saved Symbols`, "warning");
            } else {
                const detail = err?.data?.detail;
                showToast(
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : `Failed to remove ${bare} from Saved Symbols`,
                    "danger"
                );
            }
            return false;
        } finally {
            if (button) {
                button.disabled = false;
                if (previous != null) button.innerHTML = previous;
            }
        }
    }

    async function loadSavedSymbols() {
        const listEl = document.getElementById("saved-symbols-list");
        const emptyEl = document.getElementById("saved-symbols-empty");
        const countEl = document.getElementById("saved-symbols-count");
        if (!listEl) return;
        try {
            const res = await apiRequest("/api/v1/saved-symbols");
            const rows = (res && res.data && res.data.symbols) ? res.data.symbols : [];
            listEl.innerHTML = "";
            if (countEl) {
                countEl.textContent = `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
            }
            if (rows.length === 0) {
                if (emptyEl) emptyEl.style.display = "block";
                return;
            }
            if (emptyEl) emptyEl.style.display = "none";
            rows.forEach(s => {
                const li = document.createElement("li");
                li.className = "candidate-row";
                li.dataset.symbol = String(s.symbol || "").toUpperCase();
                li.innerHTML = `
                    <span class="symbol-name-col">${s.symbol}</span>
                    <div class="candidate-row-actions">
                        <button type="button" class="inspect-btn saved-symbol-remove-btn" data-symbol="${s.symbol}">
                            <i class="fas fa-times"></i> Remove
                        </button>
                    </div>
                `;
                listEl.appendChild(li);
            });
            listEl.querySelectorAll(".saved-symbol-remove-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await removeSavedSymbolNow(sym, { button: btn });
                });
            });
        } catch (err) {
            console.error("Failed to load saved symbols", err);
            if (emptyEl) {
                emptyEl.style.display = "block";
                emptyEl.textContent = "Failed to load Saved Symbols.";
            }
            if (countEl) countEl.textContent = "Unavailable";
        }
    }

    const savedSymbolAddBtn = document.getElementById("saved-symbol-add-btn");
    const savedSymbolInput = document.getElementById("saved-symbol-input");
    if (savedSymbolAddBtn && savedSymbolInput) {
        const addSavedSymbol = async () => {
            const symbol = (savedSymbolInput.value || "").trim().toUpperCase();
            if (!symbol) {
                showToast("Enter a symbol", "danger");
                return;
            }
            const previous = savedSymbolAddBtn.innerHTML;
            savedSymbolAddBtn.disabled = true;
            savedSymbolAddBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';
            try {
                await apiRequest("/api/v1/saved-symbols", {
                    method: "POST",
                    body: JSON.stringify({ symbol }),
                    skipToast: true,
                });
                savedSymbolInput.value = "";
                showToast(`${symbol} saved to your watch list`, "success");
                await loadSavedSymbols();
            } catch (err) {
                const detail = err?.data?.detail;
                showToast(
                    typeof detail === "string" && detail.trim()
                        ? detail
                        : `Failed to save ${symbol}`,
                    "danger"
                );
            } finally {
                savedSymbolAddBtn.disabled = false;
                savedSymbolAddBtn.innerHTML = previous;
            }
        };
        savedSymbolAddBtn.addEventListener("click", addSavedSymbol);
        savedSymbolInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                addSavedSymbol();
            }
        });
    }

    // Attach search event
    const searchInput = document.getElementById("universe-search");
    if (searchInput) {
        searchInput.addEventListener("keyup", (e) => {
            const query = e.target.value.toUpperCase();
            const rows = document.querySelectorAll("#universe-list-body tr");
            
            rows.forEach(row => {
                const sym = row.getAttribute("data-symbol") || "";
                if (sym.includes(query)) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            });
        });
    }

    // MI-3 polish: View Details opens a modal (Eligible/Excluded + Qualified)
    // instead of expanding inline — keeps the funnel compact and the Stock List
    // as the only primary scroll region in the right column.
    const funnelDetailsBtn = document.getElementById("validation-funnel-details-btn");
    const funnelDetailsModal = document.getElementById("validation-funnel-modal");
    const funnelDetailsClose = document.getElementById("validation-funnel-modal-close");

    const runFullValidationBtn = document.getElementById("mi-run-full-validation-btn");
    const universeValidateAllBtn = document.getElementById("universe-validate-all-btn");
    const focusAddSymbolBtn = document.getElementById("mi-focus-add-symbol-btn");
    const refreshMarketBtn = document.getElementById("mi-refresh-market-btn");
    if (runFullValidationBtn) {
        runFullValidationBtn.addEventListener("click", () => startFullUniverseValidation());
    }
    if (universeValidateAllBtn) {
        universeValidateAllBtn.addEventListener("click", () => startFullUniverseValidation());
    }
    if (focusAddSymbolBtn) {
        focusAddSymbolBtn.addEventListener("click", () => {
            const input = document.getElementById("candidate-symbol-input");
            if (input) {
                input.focus();
                input.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
    }
    if (refreshMarketBtn) {
        refreshMarketBtn.addEventListener("click", async () => {
            showToast("Refreshing market view…", "info");
            if (typeof loadMarketIntelligence === "function") {
                await loadMarketIntelligence();
            }
        });
    }
    if (funnelDetailsBtn && funnelDetailsModal) {
        funnelDetailsBtn.addEventListener("click", () => openModal(funnelDetailsModal));
    }
    if (funnelDetailsClose) {
        funnelDetailsClose.addEventListener("click", () => closeModal(funnelDetailsModal));
    }
    if (funnelDetailsModal) {
        funnelDetailsModal.addEventListener("click", (event) => {
            if (event.target === funnelDetailsModal) closeModal(funnelDetailsModal);
        });
    }

    // Modal drawer helpers — keep inactive overlays fully out of layout
    const traceModal = document.getElementById("trace-modal");
    const traceModalClose = document.getElementById("trace-modal-close");
    const traceModalTitle = document.getElementById("trace-modal-title");
    const traceModalBody = document.getElementById("trace-modal-body");

    window.openTraceModal = function(symbol) {
        const member = universeCache[symbol];
        if (!member) return;

        traceModalTitle.textContent = `${symbol} Universe Inclusion Trace`;
        traceModalBody.innerHTML = "";

        const traceList = document.createElement("div");
        traceList.className = "trace-logs-list";

        if (member.trace && member.trace.length > 0) {
            member.trace.forEach(logLine => {
                const step = document.createElement("div");
                
                const isPass = logLine.includes("(PASS)");
                step.className = `trace-step-item ${isPass ? 'pass' : 'fail'}`;

                // Parse rule name and outcome detail
                const idx = logLine.indexOf("(");
                const ruleText = idx !== -1 ? logLine.substring(0, idx).trim() : logLine;
                const outcome = isPass ? "PASS" : "FAIL";

                step.innerHTML = `
                    <div class="trace-step-header">
                        <span class="trace-step-rule">${ruleText}</span>
                        <span class="trace-step-status ${isPass ? 'pass' : 'fail'}">${outcome}</span>
                    </div>
                    <span class="trace-step-detail">Eligibility validation check executed for ${symbol}</span>
                `;
                traceList.appendChild(step);
            });
        } else {
            traceList.innerHTML = `<div class="text-muted text-center">No step-by-step trace logged for this symbol.</div>`;
        }

        traceModalBody.appendChild(traceList);
        openModal(traceModal);
    };

    if (traceModalClose) {
        traceModalClose.addEventListener("click", () => {
            closeModal(traceModal);
        });
    }
    window.addEventListener("click", (e) => {
        if (e.target === traceModal) {
            closeModal(traceModal);
        }
    });