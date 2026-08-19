

    // ---------------------------------------------------------------------------
    // Routing & Tab Switcher
    // ---------------------------------------------------------------------------
    const headerMarketTicker = document.getElementById("header-market-ticker");
    // MI-1: shared ticker strip lives on both Decisions & Trace and Market
    // Intelligence — one component/endpoint, not two.
    const TICKER_TABS = new Set(["decisions", "market"]);
    let lastAdvisoryFreshness = null;
    let advisoryFreshnessLoading = false;
    let advisoryFreshnessFailureMode = "";
    let lastAthenaCycleStatus = null;
    let athenaCycleStatusLoading = false;

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
        if (advisoryFreshnessMenu) advisoryFreshnessMenu.hidden = !TICKER_TABS.has(tabId);
        if (TICKER_TABS.has(tabId)) {
            startTickerRefresh();
        } else {
            closeAdvisoryFreshnessPopover();
            stopTickerRefresh();
        }
        if (state.activeTab === "decisions") {
            startDecisionsAutoRefresh();
        } else {
            stopDecisionsAutoRefresh();
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
            // Owner-reported: the Index filter was silently empty until the
            // owner happened to visit Market Intelligence first, with no
            // indication why. Loads the same index catalog independently
            // here so the filter is populated regardless of tab visit order.
            ensureIndexFilterCatalogLoaded();
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

    function formatFreshnessDate(value) {
        if (!value) return "Unavailable";
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return "Unavailable";
        return parsed.toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
            hour12: true
        }) + " IST";
    }

    function advisoryFreshnessToggleLabel(data) {
        const status = String(data?.status || "UNAVAILABLE").toUpperCase();
        const session = String(data?.market_session || "").toUpperCase();
        if (status === "CURRENT") {
            return session === "CLOSED" || session === "NO_SESSION"
                ? "Closed review"
                : "Data current";
        }
        if (status === "AGING") return "Data aging";
        if (status === "STALE") return "Data stale";
        return "Data unavailable";
    }

    function renderSharedFreshnessIndicator() {
        if (!advisoryFreshnessToggle) return;
        const cycleStatus = String(lastAthenaCycleStatus?.status || "").toUpperCase();
        const cycleEscalated = cycleStatus === "FAILED" || cycleStatus === "OVERDUE";
        const source = cycleEscalated ? lastAthenaCycleStatus : lastAdvisoryFreshness;
        const tone = String(source?.tone || "NEUTRAL").toLowerCase();
        advisoryFreshnessToggle.className = `btn freshness-toggle tone-${tone}`;
        advisoryFreshnessToggle.classList.toggle(
            "refresh-failed",
            Boolean(advisoryFreshnessFailureMode)
        );
        advisoryFreshnessLabel.textContent = cycleEscalated
            ? cycleStatus === "FAILED" ? "Cycle failed" : "Cycle overdue"
            : advisoryFreshnessToggleLabel(lastAdvisoryFreshness);
    }

    function renderAdvisoryFreshness(data, failureMode = "") {
        if (!advisoryFreshnessToggle || !data) return;
        advisoryFreshnessFailureMode = failureMode;
        advisoryFreshnessHeadline.textContent = data.headline || "Freshness unavailable";
        advisoryFreshnessExplanation.textContent = data.explanation || "No freshness explanation is available.";
        advisoryFreshnessObserved.textContent = formatFreshnessDate(data.observed_at);
        advisoryFreshnessSource.textContent = data.source || "Unavailable";
        advisoryFreshnessSession.textContent = data.market_session || "Unavailable";
        advisoryFreshnessNextLive.textContent = formatFreshnessDate(data.next_live_at);
        advisoryFreshnessRefreshNote.hidden = !failureMode;
        advisoryFreshnessRefreshNote.textContent = failureMode === "retained"
            ? "Refresh failed. Showing the last successful reading."
            : failureMode === "unavailable"
                ? "No freshness reading was loaded. Retry after ATHENA finishes restarting."
                : "";
        advisoryFreshnessRetry.hidden = !failureMode;
        renderSharedFreshnessIndicator();
    }

    function renderAthenaCycleStatus(data, failureMode = "") {
        if (!athenaCycleHeadline || !data) return;
        athenaCycleHeadline.textContent = data.headline || "Cycle history unavailable";
        athenaCycleExplanation.textContent = failureMode
            ? "ATHENA could not load persisted cycle history. Market-data freshness above is unaffected."
            : data.explanation || "No cycle explanation is available.";
        athenaCycleLastSuccess.textContent = formatFreshnessDate(data.last_successful_at);
        athenaCycleLatestAttempt.textContent = data.latest_attempt_status
            ? `${data.latest_attempt_status} · ${formatFreshnessDate(data.latest_attempt_at)}`
            : "Unavailable";
        const status = String(data.status || "UNAVAILABLE").toUpperCase();
        athenaCycleExpectedBy.textContent = formatFreshnessDate(data.expected_by);
        if (athenaCycleExpectedRow) {
            athenaCycleExpectedRow.hidden = status === "CLOSED";
        }
        athenaCycleOperations.hidden = !(status === "FAILED" || status === "OVERDUE");
        renderSharedFreshnessIndicator();
    }

    async function loadAdvisoryFreshness() {
        if (advisoryFreshnessLoading) return;
        advisoryFreshnessLoading = true;
        if (advisoryFreshnessRetry) {
            advisoryFreshnessRetry.disabled = true;
            advisoryFreshnessRetry.querySelector("span").textContent = "Checking";
        }
        try {
            const res = await apiRequest("/api/v1/dashboard/advisory-freshness", { skipToast: true });
            lastAdvisoryFreshness = res && res.data ? res.data : null;
            renderAdvisoryFreshness(lastAdvisoryFreshness);
        } catch (err) {
            console.error("Failed to load advisory freshness", err);
            if (lastAdvisoryFreshness) {
                renderAdvisoryFreshness(lastAdvisoryFreshness, "retained");
            } else {
                renderAdvisoryFreshness({
                    status: "UNAVAILABLE",
                    tone: "NEUTRAL",
                    headline: "Freshness unavailable",
                    explanation: "ATHENA could not reach the freshness service.",
                    source: "Unavailable",
                    market_session: "Unavailable"
                }, "unavailable");
            }
        } finally {
            advisoryFreshnessLoading = false;
            if (advisoryFreshnessRetry) {
                advisoryFreshnessRetry.disabled = false;
                advisoryFreshnessRetry.querySelector("span").textContent = "Retry";
            }
        }
    }

    async function loadAthenaCycleStatus() {
        if (athenaCycleStatusLoading) return;
        athenaCycleStatusLoading = true;
        try {
            const res = await apiRequest("/api/v1/dashboard/cycle-status", { skipToast: true });
            lastAthenaCycleStatus = res && res.data ? res.data : null;
            renderAthenaCycleStatus(lastAthenaCycleStatus);
        } catch (err) {
            console.error("Failed to load ATHENA cycle status", err);
            if (lastAthenaCycleStatus) {
                renderAthenaCycleStatus(lastAthenaCycleStatus, "retained");
            } else {
                lastAthenaCycleStatus = {
                    status: "UNAVAILABLE",
                    tone: "NEUTRAL",
                    headline: "Cycle history unavailable"
                };
                renderAthenaCycleStatus(lastAthenaCycleStatus, "unavailable");
            }
        } finally {
            athenaCycleStatusLoading = false;
        }
    }

    async function loadHeaderAuthorityStatus() {
        await Promise.all([loadAdvisoryFreshness(), loadAthenaCycleStatus()]);
    }

    function closeAdvisoryFreshnessPopover() {
        if (!advisoryFreshnessPopover || !advisoryFreshnessToggle) return;
        advisoryFreshnessPopover.hidden = true;
        advisoryFreshnessToggle.setAttribute("aria-expanded", "false");
    }

    if (advisoryFreshnessToggle && advisoryFreshnessPopover) {
        advisoryFreshnessToggle.addEventListener("click", () => {
            const willOpen = advisoryFreshnessPopover.hidden;
            advisoryFreshnessPopover.hidden = !willOpen;
            advisoryFreshnessToggle.setAttribute("aria-expanded", String(willOpen));
        });
        advisoryFreshnessClose?.addEventListener("click", () => {
            closeAdvisoryFreshnessPopover();
            advisoryFreshnessToggle.focus();
        });
        advisoryFreshnessRetry?.addEventListener("click", event => {
            event.stopPropagation();
            loadHeaderAuthorityStatus();
        });
        athenaCycleOperations?.addEventListener("click", event => {
            event.stopPropagation();
            closeAdvisoryFreshnessPopover();
            window.history.pushState({ tabId: "operations" }, "", "/dashboard/operations");
            switchTab("operations");
        });
        document.addEventListener("click", (event) => {
            if (advisoryFreshnessMenu && !advisoryFreshnessMenu.contains(event.target)) {
                closeAdvisoryFreshnessPopover();
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !advisoryFreshnessPopover.hidden) {
                closeAdvisoryFreshnessPopover();
                advisoryFreshnessToggle.focus();
            }
        });
    }

    async function loadMarketTicker() {
        if (!headerMarketTicker) return;
        try {
            await loadMarketSessionStatus();
            const [res] = await Promise.all([
                apiRequest("/api/v1/market/ticker", { skipToast: true }),
                loadHeaderAuthorityStatus()
            ]);
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
    // Scoped to read-only market observations (not the decisions
    // list/briefing, whose refresh would reset scroll position/selection).
    // Index context refreshes only while Market Intelligence is active.
    // Extended (owner-requested, 2026-08-03) to also refresh Top
    // Opportunities Today on the same 60s tick — same read-only-market-
    // observation scope, same active-tab gating.
    const TICKER_REFRESH_INTERVAL_MS = 60000;
    let tickerRefreshIntervalId = null;

    function startTickerRefresh() {
        stopTickerRefresh();
        tickerRefreshIntervalId = setInterval(() => {
            loadMarketTicker();
            if (state.activeTab === "market") {
                if (typeof loadIndexLeadership === "function") loadIndexLeadership();
                if (typeof loadTopOpportunities === "function") loadTopOpportunities();
                if (typeof refreshMarketSummary === "function") refreshMarketSummary();
            }
        }, TICKER_REFRESH_INTERVAL_MS);
    }

    function stopTickerRefresh() {
        if (tickerRefreshIntervalId != null) {
            clearInterval(tickerRefreshIntervalId);
            tickerRefreshIntervalId = null;
        }
    }

    // Decisions & Trace auto-refresh (owner-requested, 2026-08-04): the board
    // otherwise only updated on tab-switch, a filter/search/sort change, or a
    // manual click — the same manual-refresh-only gap the ticker refresh
    // above already closed for market data. Same pattern: poll while the tab
    // is active, pause while the document is hidden, silent on failure (last-
    // good view stays up, next tick retries). Safe against disrupting an open
    // decision brief: applyDecisionsView (12-decisions-list.js) only re-runs
    // selectBriefing — the full detail/trace refetch + scroll reset — when
    // the decision that would be shown has actually changed, so a tick that
    // finds nothing new leaves the open brief (scroll position, open tab,
    // in-progress journal draft) completely untouched.
    const DECISIONS_REFRESH_INTERVAL_MS = 60000;
    let decisionsRefreshIntervalId = null;
    let decisionsAutoRefreshInFlight = false;

    async function autoRefreshDecisionsWorkspace() {
        if (document.hidden || state.activeTab !== "decisions" || decisionsAutoRefreshInFlight) return;
        decisionsAutoRefreshInFlight = true;
        try {
            await loadDecisionsWorkspace({ silent: true });
        } finally {
            decisionsAutoRefreshInFlight = false;
        }
    }

    function startDecisionsAutoRefresh() {
        stopDecisionsAutoRefresh();
        decisionsRefreshIntervalId = setInterval(autoRefreshDecisionsWorkspace, DECISIONS_REFRESH_INTERVAL_MS);
    }

    function stopDecisionsAutoRefresh() {
        if (decisionsRefreshIntervalId != null) {
            clearInterval(decisionsRefreshIntervalId);
            decisionsRefreshIntervalId = null;
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
