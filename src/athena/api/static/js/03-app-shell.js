

    // ---------------------------------------------------------------------------
    // Routing & Tab Switcher
    // ---------------------------------------------------------------------------
    const headerMarketTicker = document.getElementById("header-market-ticker");
    // MI-1: shared ticker strip lives on both Decisions & Trace and Market
    // Intelligence — one component/endpoint, not two.
    const TICKER_TABS = new Set(["decisions", "market"]);

    function switchTab(tabId, options = {}) {
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

        // DT-2 header market ticker, generalized in MI-1 (Market Intelligence
        // redesign) to also cover Market Intelligence — both tabs share the
        // exact same component/endpoint, no duplication.
        if (headerMarketTicker) headerMarketTicker.hidden = !TICKER_TABS.has(tabId);
        if (TICKER_TABS.has(tabId)) {
            startTickerRefresh();
        } else {
            stopTickerRefresh();
        }
        if (tabId !== "decisions") {
            stopBriefPriceRefresh();
            if (typeof clearAdvisorPulsePriority === "function") {
                clearAdvisorPulsePriority(1);
            }
        }

        // 3. Trigger API data loading for specific tab
        if (tabId !== "operations") {
            stopOpsStream();
        }
        if (options.skipLoad) {
            return Promise.resolve();
        }
        return loadTabData(tabId);
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
            await loadMarketTicker();
        } else if (tabId === "strategies") {
            await loadStrategiesWorkspace();
        } else if (tabId === "decisions") {
            await loadDecisionsWorkspace();
            await loadMarketTicker();
        } else if (tabId === "operations") {
            await loadOperationsWorkspace();
        }
    }

    // DT-2 header market ticker — NIFTY 50 / BANK NIFTY / INDIA VIX only,
    // real level + real day-change % from GET /api/v1/market/ticker (which
    // itself derives everything from already-persisted Kite snapshot +
    // daily candle data — no new calculations beyond simple arithmetic).
    // Market breadth and an overall health score are deliberately not
    // rendered here — neither exists as real data anywhere in ATHENA today.
    // MI-1: shared verbatim with Market Intelligence (TICKER_TABS above) —
    // same component, same endpoint, no per-tab duplication.
    function renderTickerIndex(prefix, index) {
        const levelEl = document.getElementById(`ticker-${prefix}-level`);
        const changeEl = document.getElementById(`ticker-${prefix}-change`);
        if (!levelEl || !changeEl) return;
        if (index.level == null) {
            levelEl.textContent = "—";
            changeEl.textContent = "—";
            changeEl.className = "ticker-change";
            return;
        }
        const level = Number(index.level);
        levelEl.textContent = level.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        if (index.change_pct == null) {
            changeEl.textContent = "—";
            changeEl.className = "ticker-change";
            return;
        }
        const pct = Number(index.change_pct);
        const positive = pct >= 0;
        changeEl.textContent = `${positive ? "+" : ""}${pct.toFixed(2)}%`;
        changeEl.className = `ticker-change ${positive ? "positive" : "negative"}`;
    }

    function marketSessionPulse(session) {
        const kiteSuffix = state.kiteRequired
            ? (state.kiteConnected ? " · Kite connected" : " · Kite reconnect required")
            : "";
        if (session && session.is_market_open === true) {
            return {
                message: `Market live${kiteSuffix}`,
                tone: state.kiteRequired && !state.kiteConnected ? "warning" : "good",
            };
        }
        if (session && session.is_market_open === false) {
            return {
                message: `${session.message || "Market closed · review mode"}${kiteSuffix}`,
                tone: "warning",
            };
        }
        return {
            message: `Checking market hours${kiteSuffix || " · advisor ready"}`,
            tone: "warning",
        };
    }

    function updateMarketPulse(data) {
        if (typeof setAdvisorPulse !== "function") return;
        const sessionView = marketSessionPulse(state.marketSession);
        const hasTicker = Boolean(
            (data.nifty && data.nifty.level != null)
            || (data.bank_nifty && data.bank_nifty.level != null)
            || (data.india_vix && data.india_vix.level != null)
        );
        if (!hasTicker) {
            setAdvisorPulse(`${sessionView.message} · Market pulse unavailable`, "warning", 0);
            return;
        }
        setAdvisorPulse(sessionView.message, sessionView.tone, 0);
    }

    async function loadMarketSessionStatus() {
        try {
            const res = await apiRequest("/api/v1/dashboard/session-status", { skipToast: true });
            state.marketSession = res && res.data ? res.data : null;
            if (typeof renderDecisionActionability === "function") {
                renderDecisionActionability(activePlanFreshness);
            }
            return state.marketSession;
        } catch (err) {
            console.error("Failed to load market session status", err);
            state.marketSession = null;
            return null;
        }
    }

    async function loadMarketTicker() {
        if (!headerMarketTicker) return;
        try {
            await loadMarketSessionStatus();
            const res = await apiRequest("/api/v1/market/ticker", { skipToast: true });
            const data = (res && res.data) ? res.data : {};
            renderTickerIndex("nifty", data.nifty || {});
            renderTickerIndex("banknifty", data.bank_nifty || {});
            renderTickerIndex("vix", data.india_vix || {});
            updateMarketPulse(data);
        } catch (err) {
            console.error("Failed to load market ticker", err);
            if (typeof setAdvisorPulse === "function") {
                setAdvisorPulse("Market pulse unavailable · Check connection before acting", "warning", 0);
            }
        }
    }

    // Auto-refresh (owner-requested, 2026-07-27): the ticker otherwise only
    // updated on tab-switch or a manual refresh click, same as every other
    // tab in ATHENA — no polling exists anywhere else in this dashboard.
    // Scoped tightly to the ticker only (not the decisions list/briefing —
    // re-fetching those every tick would reset scroll position/selection,
    // which was never asked for) and only while one of TICKER_TABS is the
    // active tab, mirroring the existing start/stop pattern already used
    // for the Operations tab's live stream (see stopOpsStream).
    const TICKER_REFRESH_INTERVAL_MS = 60000;
    let tickerRefreshIntervalId = null;

    function startTickerRefresh() {
        stopTickerRefresh();
        tickerRefreshIntervalId = setInterval(loadMarketTicker, TICKER_REFRESH_INTERVAL_MS);
    }

    function stopTickerRefresh() {
        if (tickerRefreshIntervalId != null) {
            clearInterval(tickerRefreshIntervalId);
            tickerRefreshIntervalId = null;
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

    // Owner-requested (2026-07-29): "kill everything and restart fresh" —
    // a stuck background job (Run Full Validation, or the cycle worker)
    // can only be reliably killed by ending the whole process, since a
    // single Python thread blocked in a slow call can't be force-killed in
    // isolation. Confirmed first (briefly interrupts the whole console),
    // then POSTs /api/v1/ops/restart (the process re-execs itself with its
    // original flags — see serve_runtime.trigger_restart), then polls the
    // unauthenticated /health endpoint until the new process answers, and
    // reloads. skipToast/try-catch on the POST itself because the
    // connection dropping mid-response (the process ending) is the
    // expected, successful outcome, not an error to surface.
    restartServerTrigger?.addEventListener("click", async () => {
        if (!window.confirm(
            "Restart ATHENA?\n\nThis kills any stuck background job and the cycle " +
            "worker, then relaunches the server fresh. The console will be briefly " +
            "unreachable while it restarts."
        )) {
            return;
        }
        restartServerTrigger.disabled = true;
        showToast("Restarting ATHENA…", "info");
        try {
            await apiRequest("/api/v1/ops/restart", { method: "POST", skipToast: true });
        } catch (err) {
            // Expected: the process can end before the response finishes.
        }
        awaitServerRestartThenReload();
    });

    async function awaitServerRestartThenReload() {
        const pollIntervalMs = 1500;
        const maxAttempts = 40; // ~60s
        // Give the old process a moment to actually exit before polling,
        // so the first attempt isn't a false "it's already back" against
        // the still-dying old process.
        await new Promise(resolve => setTimeout(resolve, 1000));
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
                const res = await fetch("/health", { cache: "no-store" });
                if (res.ok) {
                    window.location.reload();
                    return;
                }
            } catch (err) {
                // Expected while the old process is down and the new one
                // hasn't started listening yet.
            }
            await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
        }
        showToast(
            "ATHENA is taking longer than expected to come back — check the terminal.",
            "danger"
        );
        if (restartServerTrigger) restartServerTrigger.disabled = false;
    }
