/* ATHENA Workstation Coordinator Script (P9.1) */

document.addEventListener("DOMContentLoaded", () => {
    // ---------------------------------------------------------------------------
    // State Registry
    // ---------------------------------------------------------------------------
    const state = {
        activeTab: "overview",
        telemetry: {
            requestId: "unknown",
            correlationId: "unknown",
            latencyMs: 0
        }
    };

    // ---------------------------------------------------------------------------
    // Selector Bindings
    // ---------------------------------------------------------------------------
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("page-title");
    const refreshTrigger = document.getElementById("refresh-trigger");
    const healthIndicator = document.getElementById("system-health-indicator");
    
    // Telemetry DOM Bindings
    const reqIdElement = document.getElementById("header-req-id");
    const corrIdElement = document.getElementById("header-corr-id");
    const latencyElement = document.getElementById("header-latency");

    // Portfolio DOM Bindings
    const valTotalPortfolio = document.getElementById("val-total-portfolio");
    const valCashAvailable = document.getElementById("val-cash-available");
    const valCashReserved = document.getElementById("val-cash-reserved");
    const valActivePositions = document.getElementById("val-active-positions");
    const valTotalClosed = document.getElementById("val-total-closed");
    const valDayChange = document.getElementById("val-day-change");
    const valDayChangeText = document.getElementById("val-day-change-text");
    const poolAllocatedVal = document.getElementById("pool-allocated-val");
    const poolAllocatedBar = document.getElementById("pool-allocated-bar");
    const poolReserveVal = document.getElementById("pool-reserve-val");
    const poolReserveBar = document.getElementById("pool-reserve-bar");
    const holdingsTbody = document.getElementById("holdings-tbody");
    
    // Charts DOM Bindings
    const navChartCtx = document.getElementById("nav-chart")?.getContext("2d");
    const sectorChartCtx = document.getElementById("sector-chart")?.getContext("2d");
    const backtestComparisonChartCtx = document.getElementById("backtest-comparison-chart")?.getContext("2d");
    const opsTelemetryChartCtx = document.getElementById("ops-telemetry-chart")?.getContext("2d");
    let navChart = null;
    let sectorChart = null;
    let backtestComparisonChart = null;
    let opsTelemetryChart = null;
    let opsEventSource = null;

    // ---------------------------------------------------------------------------
    // Routing & Tab Switcher
    // ---------------------------------------------------------------------------
    function switchTab(tabId) {
        state.activeTab = tabId;
        
        // 1. Toggle Active Nav Link
        navItems.forEach(item => {
            if (item.getAttribute("data-tab") === tabId) {
                item.classList.add("active");
                // Update header title based on nav text
                pageTitle.textContent = item.querySelector("span").textContent;
            } else {
                item.classList.remove("active");
            }
        });

        // 2. Toggle Tab Panel Visibility
        tabPanes.forEach(pane => {
            if (pane.id === `tab-${tabId}`) {
                pane.classList.add("active");
            } else {
                pane.classList.remove("active");
            }
        });

        // 3. Trigger API data loading for specific tab
        if (tabId !== "operations") {
            stopOpsStream();
        }
        loadTabData(tabId);
    }

    // Bind sidebar clicks
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const tabId = item.getAttribute("data-tab");
            
            // Push history state (for clean browser URL mapping)
            const targetUrl = `/dashboard/${tabId}`;
            window.history.pushState({ tabId }, "", targetUrl);
            
            switchTab(tabId);
        });
    });

    // Handle browser back/forward buttons
    window.addEventListener("popstate", (e) => {
        if (e.state && e.state.tabId) {
            switchTab(e.state.tabId);
        } else {
            // Default fallback
            const pathParts = window.location.pathname.split("/");
            const pathTab = pathParts[pathParts.length - 1];
            if (["overview", "market", "strategies", "decisions", "operations"].includes(pathTab)) {
                switchTab(pathTab);
            } else {
                switchTab("overview");
            }
        }
    });

    // Parse URL path on initial load to set active tab
    function initializeRoute() {
        const pathParts = window.location.pathname.split("/");
        const pathTab = pathParts[pathParts.length - 1];
        if (["overview", "market", "strategies", "decisions", "operations"].includes(pathTab)) {
            switchTab(pathTab);
        } else {
            switchTab("overview");
        }
    }

    // ---------------------------------------------------------------------------
    // API Client & Headers Capture
    // ---------------------------------------------------------------------------
    async function apiRequest(url, options = {}) {
        const start = performance.now();
        
        // Add default Headers
        const headers = {
            "Content-Type": "application/json",
            ...options.headers
        };

        try {
            const response = await fetch(url, { ...options, headers });
            
            // Record Latency
            const end = performance.now();
            const latency = Math.round(end - start);
            
            // Capture Standard Tracing Headers
            const reqId = response.headers.get("X-Request-ID") || "unknown";
            const corrId = response.headers.get("X-Correlation-ID") || "unknown";
            
            updateTelemetry(reqId, corrId, latency);
            
            if (!response.ok) {
                // Parse Problem Details structure if possible
                const errorData = await response.json().catch(() => ({}));
                throw { status: response.status, data: errorData };
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${url}`, error);
            const detail = error?.data?.detail;
            let message = "Network request failed";
            if (typeof detail === "string") {
                message = detail;
            } else if (detail && typeof detail === "object" && detail.title) {
                message = detail.title;
            } else if (error?.status) {
                message = `Request failed (${error.status})`;
            }
            showToast(message, "danger");
            throw error;
        }
    }

    function updateTelemetry(reqId, corrId, latency) {
        state.telemetry = { requestId: reqId, correlationId: corrId, latencyMs: latency };
        
        // Update DOM
        reqIdElement.textContent = reqId.slice(0, 8) + "...";
        reqIdElement.title = reqId;
        corrIdElement.textContent = corrId.slice(0, 8) + "...";
        corrIdElement.title = corrId;
        latencyElement.textContent = `${latency} ms`;
    }

    // ---------------------------------------------------------------------------
    // Telemetry & Diagnostic Data Handlers
    // ---------------------------------------------------------------------------
    async function checkSystemHealth() {
        try {
            const health = await apiRequest("/health");
            if (health && health.status === "UP") {
                healthIndicator.className = "btn btn-health healthy";
                healthIndicator.querySelector("span").textContent = "HEALTHY";
            } else {
                healthIndicator.className = "btn btn-health warning";
                healthIndicator.querySelector("span").textContent = "DEGRADED";
            }
        } catch (err) {
            healthIndicator.className = "btn btn-health danger";
            healthIndicator.querySelector("span").textContent = "OFFLINE";
        }
    }

    async function loadTabData(tabId) {
        if (tabId === "overview") {
            await loadPortfolioData();
        } else if (tabId === "market") {
            await loadMarketIntelligence();
        } else if (tabId === "strategies") {
            await loadStrategiesWorkspace();
        } else if (tabId === "decisions") {
            await loadDecisionsWorkspace();
        } else if (tabId === "operations") {
            await loadOperationsWorkspace();
        }
    }

    async function loadPortfolioData() {
        try {
            // 1. Fetch Consolidated Summary
            const summaryRes = await apiRequest("/api/v1/dashboard/summary").catch(() => null);
            
            if (summaryRes && summaryRes.data) {
                const s = summaryRes.data;
                valTotalPortfolio.textContent = `₹ ${parseFloat(s.portfolio_value).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                valCashAvailable.textContent = `₹ ${parseFloat(s.cash_available).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                valCashReserved.textContent = `₹ ${parseFloat(s.cash_reserved).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                valActivePositions.textContent = s.active_positions;
                valTotalClosed.textContent = s.closed_positions;

                // Render capital progress bars
                const totalCash = parseFloat(s.portfolio_value);
                const reservedCash = parseFloat(s.cash_reserved);
                const availableCash = parseFloat(s.cash_available);
                const allocatedCash = totalCash - availableCash - reservedCash;

                const allocatedPct = totalCash > 0 ? (allocatedCash / totalCash) * 100 : 0;
                const reservePct = totalCash > 0 ? (reservedCash / totalCash) * 100 : 0;

                poolAllocatedVal.textContent = `₹ ${allocatedCash.toFixed(2)}`;
                poolAllocatedBar.style.width = `${Math.max(0, allocatedPct)}%`;

                poolReserveVal.textContent = `₹ ${reservedCash.toFixed(2)}`;
                poolReserveBar.style.width = `${reservePct}%`;

                // Day change from consecutive NAV snapshots (null → em dash, never fake --)
                updateDayChange(s.day_change_pct);

                // Render Sector Exposure Chart (absolute ₹ slices from summary)
                renderSectorChart(s.exposure_by_sector || {});
            }

            // 2. Fetch Holdings list detail
            const portData = await apiRequest("/api/v1/portfolio").catch(() => null);
            if (portData && portData.data) {
                renderHoldingsTable(portData.data.positions || []);
            } else {
                renderHoldingsTable([]);
            }

            // 3. Fetch Analytics Performance Snapshots for NAV Chart
            const analyticsRes = await apiRequest("/api/v1/analytics/performance/snapshots").catch(() => null);
            if (analyticsRes && analyticsRes.data) {
                renderNavChart(analyticsRes.data);
            } else {
                renderNavChart([]);
            }
        } catch (err) {
            setEmptyPortfolioState();
        }
    }

    function setEmptyPortfolioState() {
        valTotalPortfolio.textContent = "₹ 0.00";
        valCashAvailable.textContent = "₹ 0.00";
        valCashReserved.textContent = "₹ 0.00";
        valActivePositions.textContent = "0";
        valTotalClosed.textContent = "0";
        updateDayChange(null);
        
        poolAllocatedVal.textContent = "₹ 0.00";
        poolAllocatedBar.style.width = "0%";
        poolReserveVal.textContent = "₹ 0.00";
        poolReserveBar.style.width = "0%";

        holdingsTbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted">No active positions currently held.</td>
            </tr>
        `;
        renderSectorChart({});
    }

    function updateDayChange(dayChangePct) {
        if (!valDayChange || !valDayChangeText) return;

        if (dayChangePct === null || dayChangePct === undefined || dayChangePct === "") {
            valDayChange.className = "metric-change";
            valDayChange.innerHTML = '<i class="fa-solid fa-minus"></i> <span id="val-day-change-text">— % today</span>';
            return;
        }

        const pct = parseFloat(dayChangePct);
        if (Number.isNaN(pct)) {
            valDayChange.className = "metric-change";
            valDayChange.innerHTML = '<i class="fa-solid fa-minus"></i> <span id="val-day-change-text">— % today</span>';
            return;
        }

        const positive = pct >= 0;
        const icon = positive ? "fa-arrow-trend-up" : "fa-arrow-trend-down";
        const sign = positive ? "+" : "";
        valDayChange.className = `metric-change ${positive ? "positive" : "negative"}`;
        valDayChange.innerHTML = `<i class="fa-solid ${icon}"></i> <span id="val-day-change-text">${sign}${pct.toFixed(2)} % today</span>`;
    }

    function renderHoldingsTable(holdings) {
        if (holdings.length === 0) {
            holdingsTbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-muted">No active positions currently held.</td>
                </tr>
            `;
            return;
        }

        holdingsTbody.innerHTML = holdings.map(pos => {
            const currentPrice = parseFloat(pos.meta?.current_price || pos.avg_price);
            const currentVal = parseFloat(pos.quantity) * currentPrice;
            const cost = parseFloat(pos.quantity) * parseFloat(pos.avg_price);
            const pnl = currentVal - cost;
            const pnlClass = pnl >= 0 ? "positive" : "negative";
            const pnlSign = pnl >= 0 ? "+" : "";

            return `
                <tr>
                    <td class="font-mono"><strong>${pos.instrument_id}</strong></td>
                    <td>${pos.quantity}</td>
                    <td class="font-mono">₹ ${parseFloat(pos.avg_price).toFixed(2)}</td>
                    <td class="font-mono">₹ ${currentVal.toFixed(2)}</td>
                    <td class="font-mono ${pnlClass}"><strong>${pnlSign}₹ ${pnl.toFixed(2)}</strong></td>
                </tr>
            `;
        }).join("");
    }

    function renderNavChart(snapshots) {
        if (!navChartCtx) return;

        // Sort snapshots chronologically
        const sorted = [...snapshots].sort((a, b) => new Date(a.as_of) - new Date(b.as_of));

        const labels = [];
        const data = [];

        sorted.forEach(s => {
            const date = new Date(s.as_of);
            labels.push(date.toLocaleDateString("en-IN", { month: "short", day: "numeric" }));
            data.push(parseFloat(s.portfolio_performance?.portfolio_value || 0));
        });

        if (labels.length === 0) {
            const today = new Date();
            labels.push(today.toLocaleDateString("en-IN", { month: "short", day: "numeric" }));
            data.push(parseFloat(valTotalPortfolio.textContent.replace(/[^0-9.]/g, '')) || 0);
        }

        if (navChart) {
            navChart.data.labels = labels;
            navChart.data.datasets[0].data = data;
            navChart.update();
            return;
        }

        navChart = new Chart(navChartCtx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Net Asset Value (NAV)",
                    data: data,
                    borderColor: "#38bdf8",
                    backgroundColor: "rgba(56, 189, 248, 0.15)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: "#38bdf8",
                    pointBorderColor: "#0f172a",
                    pointHoverRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: "index",
                        intersect: false,
                        backgroundColor: "#1e293b",
                        titleColor: "#94a3b8",
                        bodyColor: "#ffffff",
                        borderColor: "#334155",
                        borderWidth: 1,
                        callbacks: {
                            label: function(context) {
                                return `₹ ${context.parsed.y.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.02)" },
                        ticks: { color: "#94a3b8", font: { size: 10 } }
                    },
                    y: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: {
                            color: "#94a3b8",
                            font: { size: 10 },
                            callback: function(value) {
                                return "₹ " + value.toLocaleString('en-IN');
                            }
                        }
                    }
                }
            }
        });
    }

    function renderSectorChart(exposure) {
        if (!sectorChartCtx) return;

        const labels = Object.keys(exposure);
        const data = Object.values(exposure).map(val => parseFloat(val));

        if (labels.length === 0) {
            labels.push("No exposure data");
            data.push(1);
        }

        if (sectorChart) {
            sectorChart.data.labels = labels;
            sectorChart.data.datasets[0].data = data;
            sectorChart.update();
            return;
        }

        sectorChart = new Chart(sectorChartCtx, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        "#38bdf8",
                        "#10b981",
                        "#a855f7",
                        "#f59e0b",
                        "#ec4899",
                        "#6366f1",
                    ],
                    borderWidth: 2,
                    borderColor: "#0f172a",
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: {
                            color: "#94a3b8",
                            font: { size: 11 },
                            boxWidth: 12
                        }
                    },
                    tooltip: {
                        backgroundColor: "#1e293b",
                        titleColor: "#94a3b8",
                        bodyColor: "#ffffff",
                        callbacks: {
                            label: (ctx) => {
                                const value = ctx.parsed || 0;
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0) || 1;
                                const pct = ((value / total) * 100).toFixed(1);
                                return ` ₹ ${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${pct}%)`;
                            }
                        }
                    }
                },
                cutout: "70%",
            }
        });
    }

    // ---------------------------------------------------------------------------
    // Alert / Toast notification panel
    // ---------------------------------------------------------------------------
    function showToast(message, type = "info") {
        const container = document.getElementById("toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        let icon = "fa-info-circle";
        if (type === "success") icon = "fa-check-circle";
        if (type === "warning") icon = "fa-triangle-exclamation";
        if (type === "danger") icon = "fa-circle-xmark";

        toast.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        // Remove toast automatically after 4 seconds
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Cache for universe trace results to speed up detail views
    let universeCache = {};

    async function loadMarketIntelligence() {
        try {
            // 1. Fetch Volatility Regime and Universe from the latest Pipeline run
            const runsRes = await apiRequest("/api/v1/pipelines/runs").catch(() => null);
            let regime = null;
            let universe = {};

            if (runsRes && runsRes.data && runsRes.data.length > 0) {
                const latestRun = runsRes.data[0];
                // Prefer top-level final_context; fall back to nested pipeline run context
                const ctx =
                    latestRun.final_context ||
                    (latestRun.pipeline_runs && latestRun.pipeline_runs[0]
                        ? latestRun.pipeline_runs[0].final_context
                        : null);
                const data = ctx && ctx.data ? ctx.data : {};
                
                regime = data.regime_assessment || null;
                universe = data.universe_members || {};
                universeCache = universe; // Store in cache for modal inspects
            }

            // 2. Render Volatility Regime Indicators
            const trendBadge = document.getElementById("regime-trend-badge");
            const volBadge = document.getElementById("regime-vol-badge");
            const gapBadge = document.getElementById("regime-gap-badge");
            const healthBar = document.getElementById("market-health-bar");
            const healthValue = document.getElementById("market-health-value");
            const evidenceText = document.getElementById("regime-evidence-text");

            if (regime && trendBadge && volBadge && gapBadge && healthBar && healthValue && evidenceText) {
                // Trend Class badge
                const trendStr = (regime.trend || "NEUTRAL").replace("_TREND", "");
                trendBadge.textContent = trendStr;
                trendBadge.className = `regime-badge ${trendStr === "BULL" ? "bull" : trendStr === "BEAR" ? "bear" : "neutral"}`;

                // Volatility level badge
                const volStr = regime.volatility || "NORMAL";
                const volClean = volStr.replace("_VOLATILITY", "");
                volBadge.textContent = volClean;
                volBadge.className = `regime-badge ${volClean === "LOW" ? "bull" : volClean === "HIGH" ? "bear" : "neutral"}`;

                // Gap state badge
                const gapStr = (regime.gap || "NO_GAP").replace("_", " ");
                gapBadge.textContent = gapStr;
                gapBadge.className = `regime-badge ${gapStr === "NO GAP" ? "bull" : "neutral"}`;

                // Health gauge
                const score = regime.market_health || 0;
                healthBar.style.width = `${score}%`;
                healthValue.textContent = `${score}/100`;

                // Explanation
                evidenceText.textContent = regime.explanation || "No attribution summary available.";
            } else if (trendBadge && volBadge && gapBadge && healthBar && healthValue && evidenceText) {
                trendBadge.textContent = "UNKNOWN";
                trendBadge.className = "regime-badge neutral";
                volBadge.textContent = "UNKNOWN";
                volBadge.className = "regime-badge neutral";
                gapBadge.textContent = "UNKNOWN";
                gapBadge.className = "regime-badge neutral";
                healthBar.style.width = "0%";
                healthValue.textContent = "0/100";
                evidenceText.textContent = "No volatility regime details available for the latest run.";
            }

            // 3. Fetch and Render Calendar Grid & Events
            const calRes = await apiRequest("/api/v1/dashboard/calendar").catch(() => null);
            if (calRes && calRes.data) {
                renderCalendar(calRes.data);
                renderUpcomingEvents(calRes.data);
            }

            // 4. Render Universe list table
            renderUniverseTable(universe);

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

    function renderUniverseTable(universeMembers) {
        const tbody = document.getElementById("universe-list-body");
        if (!tbody) return;

        tbody.innerHTML = "";

        const symbols = Object.keys(universeMembers);

        if (symbols.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="text-muted text-center" style="padding: 24px;">No universe members selected in the latest run.</td>
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

    // Modal drawer helpers — keep inactive overlays fully out of layout
    const traceModal = document.getElementById("trace-modal");
    const traceModalClose = document.getElementById("trace-modal-close");
    const traceModalTitle = document.getElementById("trace-modal-title");
    const traceModalBody = document.getElementById("trace-modal-body");

    function openModal(modalEl) {
        if (!modalEl) return;
        modalEl.hidden = false;
        modalEl.setAttribute("aria-hidden", "false");
        modalEl.classList.add("active");
    }

    function closeModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.remove("active");
        modalEl.hidden = true;
        modalEl.setAttribute("aria-hidden", "true");
    }

    function closeAllModals() {
        closeModal(traceModal);
        closeModal(document.getElementById("backtest-modal"));
    }

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
            traceList.innerHTML = `<div class="text-muted text-center">No step-by-step trace logs stored for this member.</div>`;
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

    // ---------------------------------------------------------------------------
    // Strategies & Backtests Handlers
    // ---------------------------------------------------------------------------
    const strategyProfilesContainer = document.getElementById("strategy-profiles-container");
    const backtestListBody = document.getElementById("backtest-list-body");
    const backtestModal = document.getElementById("backtest-modal");
    const backtestModalTitle = document.getElementById("backtest-modal-title");
    const backtestModalClose = document.getElementById("backtest-modal-close");
    const backtestStepsContainer = document.getElementById("backtest-steps-container");
    const backtestPerformanceContainer = document.getElementById("backtest-performance-container");

    async function loadStrategiesWorkspace() {
        try {
            // 1. Fetch strategy profiles
            const strategiesRes = await apiRequest("/api/v1/strategies/profiles");
            if (strategiesRes && strategiesRes.status === "success") {
                renderStrategyProfiles(strategiesRes.data || []);
            }

            // 2. Fetch backtest runs
            const backtestsRes = await apiRequest("/api/v1/backtests/runs");
            if (backtestsRes && backtestsRes.status === "success") {
                renderBacktestRuns(backtestsRes.data || []);
                renderBacktestComparisonChart(backtestsRes.data || []);
            }
        } catch (err) {
            console.error("Failed to load strategies workspace", err);
            if (strategyProfilesContainer) {
                strategyProfilesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">Failed to load strategy profiles. Use refresh to retry.</div>';
            }
            if (backtestListBody) {
                backtestListBody.innerHTML = '<tr><td colspan="4" class="text-muted text-center" style="padding: 24px;">Failed to load backtest runs.</td></tr>';
            }
            showToast("Failed to load strategies workspace", "danger");
        }
    }

    function formatStrategyName(name) {
        return String(name || "")
            .split("_")
            .filter(Boolean)
            .map(part => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" ");
    }

    function renderStrategyProfiles(profiles) {
        if (!strategyProfilesContainer) return;
        strategyProfilesContainer.innerHTML = "";

        if (profiles.length === 0) {
            strategyProfilesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">No strategy profiles registered.</div>';
            return;
        }

        profiles.forEach(p => {
            const card = document.createElement("div");
            card.className = "strategy-profile-card";

            const statusClass = p.enabled ? "active" : "disabled";
            const statusText = p.enabled ? "Active" : "Disabled";

            // Decisions display
            const decisionsHtml = p.decisions.map(d => `<span class="badge text-primary" style="margin-right: 4px; border: 1px solid rgba(56, 189, 248, 0.2); background: rgba(56, 189, 248, 0.05);">${d}</span>`).join("");

            // Criteria values list
            let criteriaHtml = "";
            if (p.min_score !== null) {
                criteriaHtml += `
                    <div class="strategy-criteria-item">
                        <span class="criteria-label">Min Score</span>
                        <span class="criteria-value">${p.min_score}</span>
                    </div>
                `;
            }
            if (p.max_risk !== null) {
                criteriaHtml += `
                    <div class="strategy-criteria-item">
                        <span class="criteria-label">Max Risk</span>
                        <span class="criteria-value">${p.max_risk}</span>
                    </div>
                `;
            }
            if (p.min_confidence !== null) {
                criteriaHtml += `
                    <div class="strategy-criteria-item">
                        <span class="criteria-label">Min Confidence</span>
                        <span class="criteria-value">${p.min_confidence}</span>
                    </div>
                `;
            }
            if (p.watchlists_any && p.watchlists_any.length > 0) {
                criteriaHtml += `
                    <div class="strategy-criteria-item">
                        <span class="criteria-label">Watchlists</span>
                        <span class="criteria-value" title="${p.watchlists_any.join(", ")}">${p.watchlists_any.join(", ")}</span>
                    </div>
                `;
            }
            if (p.direction !== null) {
                criteriaHtml += `
                    <div class="strategy-criteria-item">
                        <span class="criteria-label">Direction</span>
                        <span class="criteria-value">${p.direction}</span>
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="strategy-profile-header">
                    <span class="strategy-profile-title">${formatStrategyName(p.name)}</span>
                    <span class="strategy-status-pill ${statusClass}">${statusText}</span>
                </div>
                <p class="strategy-profile-desc">${p.description}</p>
                <div style="margin-top: 4px; display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 0.75rem; color: var(--text-muted);">Decisions:</span>
                    <div>${decisionsHtml || '<span class="text-muted">None</span>'}</div>
                </div>
                <div class="strategy-criteria-grid">
                    ${criteriaHtml || '<div class="text-muted text-center" style="font-size: 0.8rem; grid-column: 1/-1;">No filtering constraints</div>'}
                </div>
            `;
            strategyProfilesContainer.appendChild(card);
        });
    }

    function renderBacktestRuns(runs) {
        if (!backtestListBody) return;
        backtestListBody.innerHTML = "";

        if (runs.length === 0) {
            backtestListBody.innerHTML = '<tr><td colspan="4" class="text-muted text-center" style="padding: 24px;">No backtest runs found.</td></tr>';
            return;
        }

        runs.forEach(r => {
            const row = document.createElement("tr");
            
            // Format dates
            const start = r.first_replay_date || "N/A";
            const end = r.last_replay_date || "N/A";
            const period = `${start} to ${end}`;

            row.innerHTML = `
                <td class="backtest-run-id">${r.run_id}</td>
                <td>${period}</td>
                <td>
                    <span class="backtest-steps-badge">${r.completed_steps}/${r.total_steps} Steps</span>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline btn-inspect-backtest" data-id="${r.run_id}">
                        <i class="fas fa-search-plus" style="margin-right: 4px;"></i>Inspect
                    </button>
                </td>
            `;

            // Row click inspect action
            row.addEventListener("click", () => {
                openBacktestModal(r.run_id);
            });
            
            // Inspect button click (prevent propagation)
            row.querySelector(".btn-inspect-backtest").addEventListener("click", (e) => {
                e.stopPropagation();
                openBacktestModal(r.run_id);
            });

            backtestListBody.appendChild(row);
        });
    }

    function renderBacktestComparisonChart(runs) {
        if (!backtestComparisonChartCtx) return;

        // If no runs, skip
        if (runs.length === 0) return;

        // We compile a chart showing completed steps vs total steps for each backtest run
        const labels = runs.map(r => r.run_id);
        const completedData = runs.map(r => r.completed_steps);
        const failedData = runs.map(r => r.failed_steps);

        if (backtestComparisonChart) {
            backtestComparisonChart.data.labels = labels;
            backtestComparisonChart.data.datasets[0].data = completedData;
            backtestComparisonChart.data.datasets[1].data = failedData;
            backtestComparisonChart.update();
            return;
        }

        backtestComparisonChart = new Chart(backtestComparisonChartCtx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Completed Steps",
                        data: completedData,
                        backgroundColor: "#10b981",
                        borderColor: "#0f172a",
                        borderWidth: 1
                    },
                    {
                        label: "Failed Steps",
                        data: failedData,
                        backgroundColor: "#f43f5e",
                        borderColor: "#0f172a",
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "top",
                        labels: { color: "#94a3b8", font: { size: 10 } }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: "rgba(255, 255, 255, 0.02)" },
                        ticks: { color: "#94a3b8", font: { size: 10 } }
                    },
                    y: {
                        stacked: true,
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#94a3b8", font: { size: 10 } }
                    }
                }
            }
        });
    }

    async function openBacktestModal(runId) {
        try {
            const res = await apiRequest(`/api/v1/backtests/runs/${runId}`);
            if (!res || res.status !== "success") return;

            const run = res.data;
            backtestModalTitle.textContent = `Backtest Run Details: ${run.run_id}`;

            // Render steps timeline chronology
            if (backtestStepsContainer) {
                backtestStepsContainer.innerHTML = "";
                run.steps.forEach(s => {
                    const stepItem = document.createElement("div");
                    stepItem.className = "bt-step-item";
                    
                    const statusClass = s.status.toLowerCase();
                    const statusText = s.status;

                    stepItem.innerHTML = `
                        <span class="bt-step-date">${s.replay_date}</span>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 0.8rem; color: var(--text-secondary);">${s.note}</span>
                            <span class="bt-step-status ${statusClass}">${statusText}</span>
                        </div>
                    `;
                    backtestStepsContainer.appendChild(stepItem);
                });
            }

            // Render strategy performance matches bars
            if (backtestPerformanceContainer) {
                backtestPerformanceContainer.innerHTML = "";
                
                const performance = run.summary.performance;
                if (!performance || performance.length === 0) {
                    backtestPerformanceContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">No strategy performance metrics recorded.</div>';
                } else {
                    // Find max matches to scale bars
                    const maxMatches = Math.max(...performance.map(p => p.total_matches), 1);

                    performance.forEach(p => {
                        const barItem = document.createElement("div");
                        barItem.className = "perf-bar-item";

                        const widthPercent = (p.total_matches / maxMatches) * 100;
                        const instrumentsText = p.instruments.length > 0 ? p.instruments.join(", ") : "None";

                        barItem.innerHTML = `
                            <div class="perf-bar-header">
                                <span class="perf-bar-strategy">${p.strategy}</span>
                                <span class="perf-bar-count" title="Distinct Instruments: ${instrumentsText}">${p.total_matches} matches (${p.steps_with_matches} active steps)</span>
                            </div>
                            <div class="perf-bar-track">
                                <div class="perf-bar-fill" style="width: ${widthPercent}%;"></div>
                            </div>
                            <span style="font-size: 0.75rem; color: var(--text-muted); margin-top: -2px;">Instruments matched: ${instrumentsText}</span>
                        `;
                        backtestPerformanceContainer.appendChild(barItem);
                    });
                }
            }

            openModal(backtestModal);
        } catch (err) {
            console.error("Failed to open backtest modal", err);
            showToast("Failed to open backtest run details", "danger");
        }
    }

    if (backtestModalClose) {
        backtestModalClose.addEventListener("click", () => {
            closeModal(backtestModal);
        });
    }
    
    window.addEventListener("click", (e) => {
        if (e.target === backtestModal) {
            closeModal(backtestModal);
        }
    });

    // ---------------------------------------------------------------------------
    // Decisions & Trace DAG Handlers
    // ---------------------------------------------------------------------------
    const briefingListContainer = document.getElementById("briefing-list-container");
    const briefingSearch = document.getElementById("briefing-search");
    const dagNodesContainer = document.getElementById("dag-nodes-container");
    const dagSvgLines = document.getElementById("dag-svg-lines");
    const dagDetailsPanel = document.getElementById("dag-details-panel");
    const dagDetailsTitle = document.getElementById("dag-details-title");
    const dagDetailsStatus = document.getElementById("dag-details-status");
    const dagDetailsSummary = document.getElementById("dag-details-summary");
    const dagDetailsGrid = document.getElementById("dag-details-grid");

    let activeTrace = null;
    let traceDecisionsList = [];

    async function loadDecisionsWorkspace() {
        try {
            const res = await apiRequest("/api/v1/decisions");
            if (res && res.status === "success") {
                traceDecisionsList = res.data || [];
                renderBriefingList(traceDecisionsList);
                
                // Select first decision by default if available
                if (traceDecisionsList.length > 0) {
                    selectBriefing(traceDecisionsList[0].metadata.decision_id);
                } else {
                    if (dagNodesContainer) {
                        dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">No decisions logged in journal.</div>';
                    }
                }
            }
        } catch (err) {
            console.error("Failed to load decisions", err);
            if (briefingListContainer) {
                briefingListContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">Failed to load decisions. Use refresh to retry.</div>';
            }
            if (dagNodesContainer) {
                dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">Decision trace unavailable until briefings load.</div>';
            }
            showToast("Failed to load decisions workspace", "danger");
        }
    }

    function renderBriefingList(decisions) {
        if (!briefingListContainer) return;
        briefingListContainer.innerHTML = "";

        if (decisions.length === 0) {
            briefingListContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">No decisions match query.</div>';
            return;
        }

        decisions.forEach(d => {
            const card = document.createElement("div");
            card.className = "briefing-card";
            card.setAttribute("data-id", d.metadata.decision_id);

            const symbol = d.metadata.instrument_id || "INDEX";
            const type = d.metadata.decision_type;
            const dir = d.metadata.direction === "NONE" ? "" : ` (${d.metadata.direction})`;
            
            const dateObj = new Date(d.metadata.ts);
            const dateStr = dateObj.toLocaleDateString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

            card.innerHTML = `
                <div class="briefing-card-header">
                    <span class="briefing-symbol">${symbol}${dir}</span>
                    <span class="badge text-primary" style="font-size: 0.65rem; border: 1px solid rgba(56, 189, 248, 0.2);">${type}</span>
                </div>
                <p class="briefing-desc">${(d.explanation || "No explanation recorded").substring(0, 80)}...</p>
                <div class="briefing-date">${dateStr}</div>
            `;

            card.addEventListener("click", () => {
                selectBriefing(d.metadata.decision_id);
            });

            briefingListContainer.appendChild(card);
        });
    }

    function selectBriefing(decisionId) {
        // Toggle active card class
        const cards = briefingListContainer.querySelectorAll(".briefing-card");
        cards.forEach(c => {
            if (c.getAttribute("data-id") === decisionId) {
                c.classList.add("active");
            } else {
                c.classList.remove("active");
            }
        });

        // Load trace details
        loadDecisionTrace(decisionId);
    }

    async function loadDecisionTrace(decisionId) {
        try {
            const res = await apiRequest(`/api/v1/decisions/${decisionId}/trace`);
            if (res && res.status === "success") {
                activeTrace = res.data;
                renderTraceDAG(activeTrace);
            }
        } catch (err) {
            console.error(`Failed to load trace for ${decisionId}`, err);
        }
    }

    function renderTraceDAG(trace) {
        if (!dagNodesContainer) return;
        dagNodesContainer.innerHTML = "";
        if (dagSvgLines) dagSvgLines.innerHTML = "";

        // Icon mappings for each stage ID
        const iconMap = {
            "universe_ingest": "fa-globe",
            "technical_indicators": "fa-chart-area",
            "scoring_engine": "fa-calculator",
            "confidence_engine": "fa-shield-halved",
            "risk_assessment": "fa-triangle-exclamation",
            "quality_gates": "fa-circle-check",
            "final_decision": "fa-brain"
        };

        trace.stages.forEach((stage, idx) => {
            const node = document.createElement("div");
            node.className = "dag-node";
            node.setAttribute("data-stage", stage.stage_id);

            const icon = iconMap[stage.stage_id] || "fa-circle-notch";
            const statusClass = stage.status.toLowerCase();

            node.innerHTML = `
                <i class="fa-solid ${icon} dag-node-icon"></i>
                <span class="dag-node-name">${stage.name}</span>
                <span class="dag-node-status ${statusClass}">${stage.status}</span>
            `;

            node.addEventListener("click", () => {
                selectNode(stage.stage_id);
            });

            dagNodesContainer.appendChild(node);
        });

        // Add resize observer to draw SVG lines dynamically when nodes position shifts
        const resizeObserver = new ResizeObserver(() => {
            drawDAGLines();
        });
        resizeObserver.observe(dagNodesContainer);

        // Draw initial connector lines
        setTimeout(drawDAGLines, 100);

        // Select the first node by default
        if (trace.stages.length > 0) {
            selectNode(trace.stages[0].stage_id);
        }
    }

    function selectNode(stageId) {
        const nodes = dagNodesContainer.querySelectorAll(".dag-node");
        nodes.forEach(n => {
            if (n.getAttribute("data-stage") === stageId) {
                n.classList.add("active");
            } else {
                n.classList.remove("active");
            }
        });

        const stage = activeTrace.stages.find(s => s.stage_id === stageId);
        if (stage) {
            showStageDetails(stage);
        }
    }

    function showStageDetails(stage) {
        if (!dagDetailsPanel) return;
        
        dagDetailsTitle.textContent = stage.name;
        dagDetailsStatus.className = `badge ${stage.status.toLowerCase()}`;
        dagDetailsStatus.textContent = stage.status;
        dagDetailsSummary.textContent = stage.summary;

        // Render key-value parameters grid
        if (dagDetailsGrid) {
            dagDetailsGrid.innerHTML = "";
            const keys = Object.keys(stage.details);
            if (keys.length === 0) {
                dagDetailsGrid.innerHTML = '<div class="text-muted text-center" style="grid-column: 1/-1;">No parameter details captured.</div>';
            } else {
                keys.forEach(k => {
                    const val = stage.details[k];
                    const item = document.createElement("div");
                    item.className = "strategy-criteria-item";

                    let displayVal = val;
                    if (typeof val === "boolean") {
                        displayVal = val ? "TRUE" : "FALSE";
                    } else if (Array.isArray(val)) {
                        // Gates list formatting
                        displayVal = `${val.length} rules checked`;
                    }

                    item.innerHTML = `
                        <span class="criteria-label">${k.replace(/_/g, " ")}</span>
                        <span class="criteria-value">${displayVal}</span>
                    `;
                    dagDetailsGrid.appendChild(item);
                });
            }
        }

        dagDetailsPanel.style.display = "block";
    }

    function drawDAGLines() {
        if (!dagSvgLines || !dagNodesContainer) return;
        dagSvgLines.innerHTML = "";

        const nodes = Array.from(dagNodesContainer.querySelectorAll(".dag-node"));
        if (nodes.length < 2) return;

        // Get container bounding rect
        const containerRect = dagNodesContainer.getBoundingClientRect();
        
        // Match SVG viewport to container dimensions
        dagSvgLines.setAttribute("width", containerRect.width);
        dagSvgLines.setAttribute("height", containerRect.height);

        for (let i = 0; i < nodes.length - 1; i++) {
            const current = nodes[i].getBoundingClientRect();
            const next = nodes[i+1].getBoundingClientRect();

            // Calculate center coordinates relative to container
            const startX = (current.left + current.width / 2) - containerRect.left;
            const startY = (current.top + current.height / 2) - containerRect.top;
            
            const endX = (next.left + next.width / 2) - containerRect.left;
            const endY = (next.top + next.height / 2) - containerRect.top;

            // Draw line
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", startX);
            line.setAttribute("y1", startY);
            line.setAttribute("x2", endX);
            line.setAttribute("y2", endY);
            line.setAttribute("stroke", "rgba(56, 189, 248, 0.2)");
            line.setAttribute("stroke-width", "2");
            line.setAttribute("stroke-dasharray", "4 4");

            // Animation effect if active trace node is selected
            if (nodes[i].classList.contains("active") || nodes[i+1].classList.contains("active")) {
                line.setAttribute("stroke", "rgba(56, 189, 248, 0.6)");
                line.setAttribute("stroke-width", "3");
            }

            dagSvgLines.appendChild(line);
        }
    }

    // Search filter briefing list
    if (briefingSearch) {
        briefingSearch.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase();
            const filtered = traceDecisionsList.filter(d => {
                const symbol = (d.metadata.instrument_id || "INDEX").toLowerCase();
                const type = (d.metadata.decision_type || "").toLowerCase();
                const exp = (d.explanation || "").toLowerCase();
                return symbol.includes(query) || type.includes(query) || exp.includes(query);
            });
            renderBriefingList(filtered);
        });
    }

    // Wire refresh trigger
    refreshTrigger.addEventListener("click", () => {
        checkSystemHealth();
        loadTabData(state.activeTab);
        showToast("Workstation workspace refreshed", "success");
    });

    // ---------------------------------------------------------------------------
    // Live Operations (P9.7)
    // ---------------------------------------------------------------------------
    const opsWarningsFeed = document.getElementById("ops-warnings-feed");
    const opsStreamStatus = document.getElementById("ops-stream-status");
    const opsTelemetryMeta = document.getElementById("ops-telemetry-meta");
    const opsBackupsBody = document.getElementById("ops-backups-body");
    const opsCreateBackupBtn = document.getElementById("ops-create-backup-btn");
    const opsRefreshBackupsBtn = document.getElementById("ops-refresh-backups-btn");
    const opsRestoreConfirm = document.getElementById("ops-restore-confirm");

    async function loadOperationsWorkspace() {
        await Promise.all([
            loadOpsTelemetry(),
            loadOpsBackups(),
        ]);
        startOpsStream();
        wireOpsAdminControls();
    }

    function setOpsStreamStatus(connected) {
        if (!opsStreamStatus) return;
        opsStreamStatus.textContent = connected ? "Connected" : "Disconnected";
        opsStreamStatus.className = `ops-stream-pill ${connected ? "connected" : "disconnected"}`;
    }

    function stopOpsStream() {
        if (opsEventSource) {
            opsEventSource.close();
            opsEventSource = null;
        }
        setOpsStreamStatus(false);
    }

    function startOpsStream() {
        stopOpsStream();
        if (!opsWarningsFeed) return;

        opsWarningsFeed.innerHTML = "";
        try {
            opsEventSource = new EventSource("/api/v1/ops/stream");
        } catch (err) {
            console.error("Failed to open ops SSE", err);
            opsWarningsFeed.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">Failed to open warning stream.</div>';
            setOpsStreamStatus(false);
            return;
        }

        opsEventSource.addEventListener("open", () => setOpsStreamStatus(true));
        opsEventSource.addEventListener("heartbeat", (ev) => {
            appendOpsWarning(JSON.parse(ev.data));
        });
        opsEventSource.addEventListener("warning", (ev) => {
            appendOpsWarning(JSON.parse(ev.data));
        });
        opsEventSource.onerror = () => {
            setOpsStreamStatus(false);
        };
    }

    function appendOpsWarning(event) {
        if (!opsWarningsFeed || !event) return;
        if (opsWarningsFeed.querySelector(".text-muted.text-center")) {
            opsWarningsFeed.innerHTML = "";
        }

        const row = document.createElement("div");
        row.className = `ops-warning-row ${event.severity || "info"}`;
        const ts = event.as_of ? new Date(event.as_of).toLocaleTimeString("en-IN") : "--";
        row.innerHTML = `
            <div class="ops-warning-header">
                <span>${event.severity || "info"} · ${event.source || "ops"}</span>
                <span>${ts}</span>
            </div>
            <div class="ops-warning-message">${event.message || ""}</div>
        `;
        opsWarningsFeed.prepend(row);

        // Cap feed length
        while (opsWarningsFeed.children.length > 40) {
            opsWarningsFeed.removeChild(opsWarningsFeed.lastChild);
        }
    }

    async function loadOpsTelemetry() {
        try {
            const res = await apiRequest("/api/v1/ops/telemetry");
            if (!res || res.status !== "success") return;
            const data = res.data;
            if (opsTelemetryMeta) {
                if (!data.run_id) {
                    opsTelemetryMeta.textContent = "No pipeline run loaded.";
                } else {
                    const asOf = data.as_of ? new Date(data.as_of).toLocaleString("en-IN") : "--";
                    opsTelemetryMeta.textContent = `Run ${data.run_id} · ${data.overall_status || "UNKNOWN"} · ${asOf}`;
                }
            }
            renderOpsTelemetryChart(data.stages || []);
        } catch (err) {
            console.error("Failed to load ops telemetry", err);
            if (opsTelemetryMeta) {
                opsTelemetryMeta.textContent = "Failed to load stage telemetry.";
            }
        }
    }

    function renderOpsTelemetryChart(stages) {
        if (!opsTelemetryChartCtx) return;

        const labels = stages.map(s => s.stage_id);
        const successData = stages.map(s => {
            const st = (s.status || "").toUpperCase();
            return (st === "SUCCESS" || st === "COMPLETED" || st === "PASSED") ? 1 : 0;
        });
        const failedData = stages.map(s => {
            const st = (s.status || "").toUpperCase();
            return (st === "FAILED" || st === "ERROR" || st === "TIMEOUT") ? 1 : 0;
        });
        const otherData = stages.map((_, idx) => (successData[idx] || failedData[idx]) ? 0 : 1);

        if (labels.length === 0) {
            labels.push("no_stages");
            successData.push(0);
            failedData.push(0);
            otherData.push(1);
        }

        if (opsTelemetryChart) {
            opsTelemetryChart.data.labels = labels;
            opsTelemetryChart.data.datasets[0].data = successData;
            opsTelemetryChart.data.datasets[1].data = failedData;
            opsTelemetryChart.data.datasets[2].data = otherData;
            opsTelemetryChart.update();
            return;
        }

        opsTelemetryChart = new Chart(opsTelemetryChartCtx, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Success",
                        data: successData,
                        backgroundColor: "#10b981",
                        stack: "status",
                    },
                    {
                        label: "Failed",
                        data: failedData,
                        backgroundColor: "#f43f5e",
                        stack: "status",
                    },
                    {
                        label: "Other",
                        data: otherData,
                        backgroundColor: "#64748b",
                        stack: "status",
                    },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "top",
                        labels: { color: "#94a3b8", font: { size: 10 } },
                    },
                },
                scales: {
                    x: {
                        stacked: true,
                        beginAtZero: true,
                        max: 1,
                        ticks: { stepSize: 1, color: "#94a3b8", font: { size: 10 } },
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                    },
                    y: {
                        stacked: true,
                        ticks: { color: "#94a3b8", font: { size: 10 } },
                        grid: { color: "rgba(255, 255, 255, 0.02)" },
                    },
                },
            },
        });
    }

    async function loadOpsBackups() {
        if (!opsBackupsBody) return;
        try {
            const res = await apiRequest("/api/v1/ops/backups");
            if (!res || res.status !== "success") return;
            renderOpsBackups(res.data || []);
        } catch (err) {
            console.error("Failed to load backups", err);
            opsBackupsBody.innerHTML = '<tr><td colspan="4" class="text-muted text-center" style="padding: 24px;">Failed to load backups.</td></tr>';
        }
    }

    function renderOpsBackups(backups) {
        if (!opsBackupsBody) return;
        if (!backups.length) {
            opsBackupsBody.innerHTML = '<tr><td colspan="4" class="text-muted text-center" style="padding: 24px;">No backups found.</td></tr>';
            return;
        }

        const confirmOk = opsRestoreConfirm && opsRestoreConfirm.value === "CONFIRM";
        opsBackupsBody.innerHTML = "";
        backups.forEach(b => {
            const row = document.createElement("tr");
            const modified = b.modified_at
                ? new Date(b.modified_at).toLocaleString("en-IN")
                : "--";
            const sizeKb = Math.max(1, Math.round((b.size_bytes || 0) / 1024));
            row.innerHTML = `
                <td class="font-mono">${b.backup_id}</td>
                <td>${modified}</td>
                <td>${sizeKb} KB</td>
                <td>
                    <button class="btn btn-sm btn-outline ops-restore-btn" data-id="${b.backup_id}" ${confirmOk ? "" : "disabled"}>
                        Restore
                    </button>
                </td>
            `;
            const btn = row.querySelector(".ops-restore-btn");
            btn.addEventListener("click", () => restoreOpsBackup(b.backup_id));
            opsBackupsBody.appendChild(row);
        });
    }

    function refreshRestoreButtonState() {
        const confirmOk = opsRestoreConfirm && opsRestoreConfirm.value === "CONFIRM";
        document.querySelectorAll(".ops-restore-btn").forEach(btn => {
            btn.disabled = !confirmOk;
        });
    }

    async function restoreOpsBackup(backupId) {
        if (!opsRestoreConfirm || opsRestoreConfirm.value !== "CONFIRM") {
            showToast("Type CONFIRM before restoring", "warning");
            return;
        }
        try {
            const res = await apiRequest(`/api/v1/ops/backups/${encodeURIComponent(backupId)}/restore`, {
                method: "POST",
                body: JSON.stringify({ confirmation: "CONFIRM" }),
            });
            if (res && res.status === "success") {
                const ok = res.data.ok;
                showToast(
                    ok ? `Restored from ${backupId}` : `Restore completed with issues: ${(res.data.issues || []).join("; ") || "see details"}`,
                    ok ? "success" : "warning"
                );
                opsRestoreConfirm.value = "";
                refreshRestoreButtonState();
                await loadOpsBackups();
            }
        } catch (err) {
            console.error("Restore failed", err);
        }
    }

    let opsAdminWired = false;
    function wireOpsAdminControls() {
        if (opsAdminWired) return;
        opsAdminWired = true;

        if (opsCreateBackupBtn) {
            opsCreateBackupBtn.addEventListener("click", async () => {
                try {
                    opsCreateBackupBtn.disabled = true;
                    const res = await apiRequest("/api/v1/ops/backups", { method: "POST" });
                    if (res && res.status === "success") {
                        showToast(`Backup created: ${res.data.backup_id}`, "success");
                        await loadOpsBackups();
                    }
                } catch (err) {
                    console.error("Backup create failed", err);
                } finally {
                    opsCreateBackupBtn.disabled = false;
                }
            });
        }

        if (opsRefreshBackupsBtn) {
            opsRefreshBackupsBtn.addEventListener("click", () => loadOpsBackups());
        }

        if (opsRestoreConfirm) {
            opsRestoreConfirm.addEventListener("input", refreshRestoreButtonState);
        }
    }

    // Escape closes any open modal
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeAllModals();
        }
    });

    // Initialize Startup Flows
    closeAllModals();
    initializeRoute();
    checkSystemHealth();
});
