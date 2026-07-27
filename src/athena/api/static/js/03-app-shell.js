

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

    // Called once per successful login/bootstrap (never for in-session
    // navigation — that goes through switchTab directly via nav clicks and
    // popstate). Owner-reported: the browser's address bar can still point
    // at whatever tab was open before (e.g. /dashboard/decisions) when a
    // session expires or the app is reloaded, and this used to honor that
    // stale path instead of resetting — so a login could land back on a
    // previous tab instead of Portfolio Overview. Every session now always
    // starts on Overview, mirroring the same reset the logout handler
    // already does.
    function initializeRoute() {
        window.history.replaceState({ tabId: "overview" }, "", "/dashboard/overview");
        switchTab("overview");
    }

    // ---------------------------------------------------------------------------
    // Telemetry & Diagnostic Data Handlers
    // ---------------------------------------------------------------------------
    async function checkSystemHealth() {
        const sessionStatus = document.getElementById("session-status");
        try {
            const platform = await fetch("/health").then((r) => r.json()).catch(() => null);
            const v1 = await apiRequest("/api/v1/health", { skipAuthRedirect: true }).catch(() => null);
            const data = v1?.data;

            if (platform && platform.status === "UP") {
                healthIndicator.className = "btn btn-health healthy";
                healthIndicator.querySelector("span").textContent = "HEALTHY";
            } else {
                healthIndicator.className = "btn btn-health warning";
                healthIndicator.querySelector("span").textContent = "DEGRADED";
            }

            if (sessionStatus && data) {
                if (state.kiteRequired && !state.kiteConnected) {
                    sessionStatus.textContent = "KITE CONNECTION REQUIRED";
                } else if (data.cycles_enabled) {
                    sessionStatus.textContent = "LIVE ENGINE ACTIVE";
                } else {
                    sessionStatus.textContent = "API UP · MANUAL CYCLES";
                }
            }
        } catch (err) {
            healthIndicator.className = "btn btn-health danger";
            healthIndicator.querySelector("span").textContent = "OFFLINE";
            if (sessionStatus) sessionStatus.textContent = "API OFFLINE";
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

    // Wire refresh trigger
    refreshTrigger.addEventListener("click", () => {
        checkSystemHealth();
        loadTabData(state.activeTab);
        showToast("Workstation workspace refreshed", "success");
    });