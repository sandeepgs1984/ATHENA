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
        }
        // Placeholders for future milestones (market, strategies, decisions, operations)
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
            }

            // 2. Fetch Holdings list detail
            const portData = await apiRequest("/api/v1/portfolio").catch(() => null);
            if (portData && portData.data) {
                renderHoldingsTable(portData.data.positions || []);
            } else {
                renderHoldingsTable([]);
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
