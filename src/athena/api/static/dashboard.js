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
    const poolAllocatedVal = document.getElementById("pool-allocated-val");
    const poolAllocatedBar = document.getElementById("pool-allocated-bar");
    const poolReserveVal = document.getElementById("pool-reserve-val");
    const poolReserveBar = document.getElementById("pool-reserve-bar");
    const holdingsTbody = document.getElementById("holdings-tbody");
    
    // Charts DOM Bindings
    const navChartCtx = document.getElementById("nav-chart")?.getContext("2d");
    const sectorChartCtx = document.getElementById("sector-chart")?.getContext("2d");
    let navChart = null;
    let sectorChart = null;

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
            showToast(error.data?.detail || "Network request failed", "danger");
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
            loadPortfolioData();
        } else if (tabId === "market") {
            loadMarketIntelligence();
        }
        // Placeholders for future milestones (strategies, decisions, operations)
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

                // Render Sector Exposure Chart
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
        
        poolAllocatedVal.textContent = "₹ 0.00";
        poolAllocatedBar.style.width = "0%";
        poolReserveVal.textContent = "₹ 0.00";
        poolReserveBar.style.width = "0%";

        holdingsTbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-muted">No active positions currently held.</td>
            </tr>
        `;
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
            labels.push("Cash (Unallocated)");
            data.push(100);
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
                        "#a855f7",
                        "#10b981",
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
                        borderColor: "#334155",
                        borderWidth: 1,
                        callbacks: {
                            label: function(context) {
                                const val = context.parsed;
                                return ` ${context.label}: ₹ ${val.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
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
                const data = latestRun.final_context ? latestRun.final_context.data : {};
                
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

            if (regime) {
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
            } else {
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
        const holidaysMap = new Map(calData.holidays.map(h => [h.date, h.name]));
        const specialMap = new Map(calData.special_sessions.map(s => [s.date, s]));
        const weeklyExpiries = new Set(calData.weekly_expiries);
        const monthlyExpiries = new Set(calData.monthly_expiries);

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
        calData.weekly_expiries.forEach(date => {
            allEvents.push({ date, kind: "weekly_expiry", name: "Weekly F&O Expiry", tagClass: "expiry-tag", tagText: "weekly exp" });
        });
        // Aggregate monthly expiries
        calData.monthly_expiries.forEach(date => {
            allEvents.push({ date, kind: "monthly_expiry", name: "Monthly F&O Expiry", tagClass: "expiry-tag", tagText: "monthly exp" });
        });
        // Aggregate holidays
        calData.holidays.forEach(h => {
            allEvents.push({ date: h.date, kind: "holiday", name: h.name, tagClass: "holiday-tag", tagText: "holiday" });
        });
        // Aggregate events
        calData.events.forEach(e => {
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

    // Modal drawer triggers
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
            traceList.innerHTML = `<div class="text-muted text-center">No step-by-step trace logs stored for this member.</div>`;
        }

        traceModalBody.appendChild(traceList);
        traceModal.classList.add("active");
    };

    if (traceModalClose) {
        traceModalClose.addEventListener("click", () => {
            traceModal.classList.remove("active");
        });
    }
    window.addEventListener("click", (e) => {
        if (e.target === traceModal) {
            traceModal.classList.remove("active");
        }
    });

    // Wire refresh trigger
    refreshTrigger.addEventListener("click", () => {
        checkSystemHealth();
        loadTabData(state.activeTab);
        showToast("Workstation workspace refreshed", "success");
    });

    // Initialize Startup Flows
    initializeRoute();
    checkSystemHealth();
});
