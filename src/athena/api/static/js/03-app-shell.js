

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

    // Called on every silent session bootstrap (auth not required, or a
    // plain page reload/reopen with an already-valid stored token) — parses
    // the current URL so a reload stays on whatever tab the browser was
    // already showing (owner-reported: forcing Overview here made every
    // Cmd+R "very annoying," since it's not a new session, just the same
    // one continuing). Never used for an actual login — see
    // resetToOverviewTab below.
    function initializeRoute() {
        const pathParts = window.location.pathname.split("/");
        const pathTab = pathParts[pathParts.length - 1];
        if (["overview", "market", "strategies", "decisions", "operations"].includes(pathTab)) {
            switchTab(pathTab);
        } else {
            switchTab("overview");
        }
    }

    // Called only when the owner actively submits the login form — a fresh
    // login (or a re-login after session expiry) always starts on Portfolio
    // Overview, regardless of whatever tab's URL the browser happened to
    // still be showing (owner-reported: a stale /dashboard/decisions in the
    // address bar from a previous session could reopen that same tab on
    // login instead of Overview). Never called for a plain reload of an
    // already-valid session — that's initializeRoute above, which
    // deliberately does the opposite (preserves the current tab).
    function resetToOverviewTab() {
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

    // ---------------------------------------------------------------------------
    // Collapsible global sidebar (owner-requested) — icon-only when
    // collapsed, .console-main (flex-grow: 1) reflows to fill the freed
    // width automatically via the CSS width transition on .sidebar, no JS
    // recalculation needed. Preference persisted across reloads, same
    // pattern as the existing dismissed-decisions localStorage key.
    // ---------------------------------------------------------------------------
    const sidebarEl = document.querySelector(".sidebar");
    const sidebarCollapseToggle = document.getElementById("sidebar-collapse-toggle");
    const SIDEBAR_COLLAPSED_KEY = "athena.sidebar-collapsed";

    function applySidebarCollapsed(collapsed) {
        if (!sidebarEl) return;
        sidebarEl.classList.toggle("collapsed", collapsed);
        if (sidebarCollapseToggle) {
            sidebarCollapseToggle.setAttribute("aria-expanded", String(!collapsed));
            sidebarCollapseToggle.setAttribute(
                "title", collapsed ? "Expand sidebar" : "Collapse sidebar"
            );
            sidebarCollapseToggle.setAttribute(
                "aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar"
            );
        }
    }

    applySidebarCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1");

    sidebarCollapseToggle?.addEventListener("click", () => {
        const collapsed = !sidebarEl.classList.contains("collapsed");
        applySidebarCollapsed(collapsed);
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
    });

    // Wire refresh trigger
    refreshTrigger.addEventListener("click", () => {
        checkSystemHealth();
        loadTabData(state.activeTab);
        showToast("Workstation workspace refreshed", "success");
    });