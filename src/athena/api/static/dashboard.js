/* ATHENA Workstation Coordinator Script (P9.1) */

document.addEventListener("DOMContentLoaded", () => {
    // ---------------------------------------------------------------------------
    // State Registry
    // ---------------------------------------------------------------------------
    const AUTH_ACCESS_KEY = "athena.access_token";
    const AUTH_REFRESH_KEY = "athena.refresh_token";

    const state = {
        activeTab: "overview",
        authRequired: false,
        authenticated: false,
        kiteRequired: false,
        kiteConnected: false,
        kiteBlocking: false,
        kiteUserId: null,
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
    const appShell = document.getElementById("app");
    const unlockGate = document.getElementById("unlock-gate");
    const unlockForm = document.getElementById("unlock-form");
    const unlockUsername = document.getElementById("unlock-username");
    const unlockPassword = document.getElementById("unlock-password");
    const unlockError = document.getElementById("unlock-error");
    const unlockSubmit = document.getElementById("unlock-submit");
    const logoutBtn = document.getElementById("logout-btn");
    const profileName = document.getElementById("profile-name");
    const profileRole = document.getElementById("profile-role");
    const kiteGate = document.getElementById("kite-gate");
    const kiteGateDetail = document.getElementById("kite-gate-detail");
    const kiteGateTitle = document.getElementById("kite-gate-title");
    const kiteGateError = document.getElementById("kite-gate-error");
    const kiteGateClose = document.getElementById("kite-gate-close");
    const kiteStartAuth = document.getElementById("kite-start-auth");
    const kiteCompleteAuth = document.getElementById("kite-complete-auth");
    const kiteRecheck = document.getElementById("kite-recheck");
    const kiteDisconnect = document.getElementById("kite-disconnect");
    const kiteRequestToken = document.getElementById("kite-request-token");
    const kiteStatusBtn = document.getElementById("kite-status-btn");
    const kiteStatusLabel = document.getElementById("kite-status-label");
    
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
    // Session / Unlock helpers
    // ---------------------------------------------------------------------------
    function getAccessToken() {
        return sessionStorage.getItem(AUTH_ACCESS_KEY) || "";
    }

    function getRefreshToken() {
        return sessionStorage.getItem(AUTH_REFRESH_KEY) || "";
    }

    function storeTokens(accessToken, refreshToken) {
        sessionStorage.setItem(AUTH_ACCESS_KEY, accessToken);
        sessionStorage.setItem(AUTH_REFRESH_KEY, refreshToken);
    }

    function clearTokens() {
        sessionStorage.removeItem(AUTH_ACCESS_KEY);
        sessionStorage.removeItem(AUTH_REFRESH_KEY);
    }

    function showUnlock(message) {
        state.authenticated = false;
        hideKiteGate();
        if (appShell) appShell.hidden = true;
        if (unlockGate) unlockGate.hidden = false;
        if (unlockError) {
            if (message) {
                unlockError.hidden = false;
                unlockError.textContent = message;
            } else {
                unlockError.hidden = true;
                unlockError.textContent = "";
            }
        }
        if (unlockPassword) unlockPassword.value = "";
        if (unlockUsername) unlockUsername.focus();
    }

    function showAppShell() {
        if (unlockGate) unlockGate.hidden = true;
        if (appShell) appShell.hidden = false;
        state.authenticated = true;
    }

    function applyPrincipal(principal) {
        if (profileName) profileName.textContent = principal?.username || "Owner";
        if (profileRole) profileRole.textContent = principal?.role ? `${principal.role} ROLE` : "ADMIN ROLE";
    }

    function updateKiteStatusButton() {
        if (!kiteStatusBtn || !kiteStatusLabel) return;
        if (!state.kiteRequired) {
            kiteStatusBtn.hidden = true;
            return;
        }
        kiteStatusBtn.hidden = false;
        if (state.kiteConnected) {
            kiteStatusBtn.className = "btn btn-kite connected";
            kiteStatusLabel.textContent = state.kiteUserId
                ? `KITE · ${state.kiteUserId}`
                : "KITE · CONNECTED";
            kiteStatusBtn.title = "Kite market-data session is valid. Click to reconnect.";
        } else {
            kiteStatusBtn.className = "btn btn-kite required";
            kiteStatusLabel.textContent = "KITE · RECONNECT";
            kiteStatusBtn.title = "Kite market-data session required. Click to connect.";
        }
    }

    function showKiteGate(detail, { blocking = true, title = null } = {}) {
        state.kiteBlocking = Boolean(blocking);
        if (kiteGateTitle) {
            kiteGateTitle.textContent = title
                || (blocking ? "Connect Kite to go live" : "Reconnect Kite");
        }
        if (kiteGateDetail) {
            kiteGateDetail.textContent = detail || "Connect Kite to continue.";
        }
        if (kiteGateClose) kiteGateClose.hidden = blocking;
        if (kiteDisconnect) kiteDisconnect.hidden = !state.kiteConnected;
        if (kiteGate) {
            kiteGate.hidden = false;
            kiteGate.setAttribute("aria-hidden", "false");
        }
        updateKiteStatusButton();
    }

    function hideKiteGate() {
        state.kiteBlocking = false;
        if (kiteGate) {
            kiteGate.hidden = true;
            kiteGate.setAttribute("aria-hidden", "true");
        }
        if (kiteGateError) {
            kiteGateError.hidden = true;
            kiteGateError.textContent = "";
        }
    }

    function setKiteGateError(message) {
        if (!kiteGateError) return;
        kiteGateError.textContent = message || "";
        kiteGateError.hidden = !message;
    }

    function setKiteButtonsBusy(busy) {
        [kiteStartAuth, kiteCompleteAuth, kiteRecheck, kiteDisconnect, kiteStatusBtn].forEach((button) => {
            if (button) button.disabled = busy;
        });
    }

    async function checkKiteGate({ forcePanel = false } = {}) {
        if (!state.authenticated) return null;
        try {
            const response = await apiRequest("/api/v1/ops/kite/status", {
                skipAuthRedirect: true,
            });
            const data = response?.data;
            state.kiteRequired = Boolean(data?.required);
            state.kiteConnected = Boolean(data?.connected);
            state.kiteUserId = data?.user_id || null;
            updateKiteStatusButton();

            if (!state.kiteRequired) {
                hideKiteGate();
            } else if (!state.kiteConnected) {
                showKiteGate(
                    data?.detail || "Kite market-data session is not connected.",
                    { blocking: true }
                );
            } else if (forcePanel) {
                showKiteGate(
                    data?.detail
                        || "Session is valid. Clear it to force a fresh Zerodha authorize, or renew now.",
                    {
                        blocking: false,
                        title: "Kite market-data session",
                    }
                );
            } else {
                hideKiteGate();
            }
            await checkSystemHealth();
            return data;
        } catch (err) {
            console.error("Kite status check failed", err);
            state.kiteRequired = true;
            state.kiteConnected = false;
            state.kiteUserId = null;
            updateKiteStatusButton();
            showKiteGate("Could not verify Kite. Recheck the connection before going live.", {
                blocking: true,
            });
            return null;
        }
    }

    if (kiteStatusBtn) {
        kiteStatusBtn.addEventListener("click", async () => {
            setKiteGateError("");
            setKiteButtonsBusy(true);
            try {
                await checkKiteGate({ forcePanel: true });
            } finally {
                setKiteButtonsBusy(false);
            }
        });
    }

    if (kiteGateClose) {
        kiteGateClose.addEventListener("click", () => {
            if (!state.kiteBlocking) hideKiteGate();
        });
    }

    if (kiteStartAuth) {
        kiteStartAuth.addEventListener("click", async () => {
            setKiteGateError("");
            setKiteButtonsBusy(true);
            // Open synchronously to avoid browser popup blocking after fetch.
            const loginWindow = window.open("about:blank", "_blank");
            try {
                const response = await apiRequest("/api/v1/ops/kite/start-auth", {
                    method: "POST",
                    skipAuthRedirect: true,
                });
                const data = response?.data;
                if (!data?.ready || !data?.login_url) {
                    if (loginWindow) loginWindow.close();
                    setKiteGateError(data?.detail || "Kite login is not configured.");
                    return;
                }
                if (loginWindow) {
                    loginWindow.opener = null;
                    loginWindow.location.href = data.login_url;
                } else {
                    window.open(data.login_url, "_blank", "noopener");
                }
                if (kiteGateDetail) kiteGateDetail.textContent = data.detail;
                kiteRequestToken?.focus();
            } catch (err) {
                if (loginWindow) loginWindow.close();
                setKiteGateError(err?.data?.detail || "Could not start Kite login.");
            } finally {
                setKiteButtonsBusy(false);
            }
        });
    }

    if (kiteCompleteAuth) {
        kiteCompleteAuth.addEventListener("click", async () => {
            const raw = kiteRequestToken?.value?.trim() || "";
            if (!raw) {
                setKiteGateError("Paste the redirect URL or request_token first.");
                kiteRequestToken?.focus();
                return;
            }
            setKiteGateError("");
            setKiteButtonsBusy(true);
            try {
                const response = await apiRequest("/api/v1/ops/kite/complete-auth", {
                    method: "POST",
                    body: JSON.stringify({ redirect_or_token: raw }),
                    skipAuthRedirect: true,
                });
                const data = response?.data;
                if (!data?.connected) {
                    setKiteGateError(data?.detail || "Kite verification failed.");
                    return;
                }
                state.kiteRequired = Boolean(data.required);
                state.kiteConnected = true;
                state.kiteUserId = data.user_id || null;
                if (kiteRequestToken) kiteRequestToken.value = "";
                hideKiteGate();
                updateKiteStatusButton();
                await checkSystemHealth();
                showToast("Kite connected — market data is live", "success");
            } catch (err) {
                setKiteGateError(err?.data?.detail || "Kite token exchange failed.");
            } finally {
                setKiteButtonsBusy(false);
            }
        });
    }

    if (kiteDisconnect) {
        kiteDisconnect.addEventListener("click", async () => {
            setKiteGateError("");
            setKiteButtonsBusy(true);
            try {
                const response = await apiRequest("/api/v1/ops/kite/disconnect", {
                    method: "POST",
                    skipAuthRedirect: true,
                });
                const data = response?.data;
                state.kiteRequired = Boolean(data?.required);
                state.kiteConnected = false;
                state.kiteUserId = null;
                if (kiteRequestToken) kiteRequestToken.value = "";
                updateKiteStatusButton();
                showKiteGate(
                    data?.detail || "Session cleared. Authorize Kite again to continue.",
                    { blocking: true, title: "Connect Kite to go live" }
                );
                await checkSystemHealth();
                showToast("Kite session cleared — reconnect to go live", "info");
            } catch (err) {
                setKiteGateError(err?.data?.detail || "Could not clear Kite session.");
            } finally {
                setKiteButtonsBusy(false);
            }
        });
    }

    if (kiteRecheck) {
        kiteRecheck.addEventListener("click", async () => {
            setKiteGateError("");
            setKiteButtonsBusy(true);
            try {
                await checkKiteGate({ forcePanel: true });
            } finally {
                setKiteButtonsBusy(false);
            }
        });
    }

    async function refreshAccessToken() {
        const refreshToken = getRefreshToken();
        if (!refreshToken) return false;
        const response = await fetch("/api/v1/auth/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) {
            clearTokens();
            return false;
        }
        const payload = await response.json();
        const data = payload?.data;
        if (!data?.access_token || !data?.refresh_token) {
            clearTokens();
            return false;
        }
        storeTokens(data.access_token, data.refresh_token);
        return true;
    }

    async function fetchAuthStatus() {
        const response = await fetch("/api/v1/auth/status");
        if (!response.ok) {
            const err = new Error(`auth status HTTP ${response.status}`);
            err.status = response.status;
            throw err;
        }
        const payload = await response.json();
        return payload?.data || { auth_required: false, owner_configured: false };
    }

    async function fetchMe() {
        return apiRequest("/api/v1/auth/me", { skipAuthRedirect: true });
    }

    async function bootstrapSession() {
        let status;
        try {
            status = await fetchAuthStatus();
        } catch (err) {
            console.error(err);
            const code = err?.status;
            if (code === 404) {
                showUnlock("Auth API missing (404). Restart the ATHENA API with the latest code, then hard-refresh.");
            } else if (code) {
                showUnlock(`Cannot reach auth API (HTTP ${code}). Restart the server and hard-refresh.`);
            } else {
                showUnlock("Cannot reach ATHENA API. Is the server running?");
            }
            return;
        }

        state.authRequired = Boolean(status.auth_required);

        if (!state.authRequired) {
            applyPrincipal({ username: "Administrator", role: "ADMIN" });
            showAppShell();
            closeAllModals();
            initializeRoute();
            checkSystemHealth();
            checkKiteGate();
            return;
        }

        if (!getAccessToken()) {
            showUnlock();
            return;
        }

        try {
            const me = await fetchMe();
            applyPrincipal(me?.data || me);
            showAppShell();
            closeAllModals();
            initializeRoute();
            checkSystemHealth();
            checkKiteGate();
        } catch (err) {
            clearTokens();
            showUnlock("Session expired. Unlock again.");
        }
    }

    if (unlockForm) {
        unlockForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (unlockSubmit) unlockSubmit.disabled = true;
            if (unlockError) {
                unlockError.hidden = true;
                unlockError.textContent = "";
            }
            try {
                const response = await fetch("/api/v1/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        username: unlockUsername?.value?.trim() || "",
                        password: unlockPassword?.value || "",
                    }),
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) {
                    const detail = payload?.detail || payload?.title || "Invalid credentials";
                    showUnlock(typeof detail === "string" ? detail : "Invalid credentials");
                    return;
                }
                const data = payload?.data;
                if (!data?.access_token || !data?.refresh_token) {
                    showUnlock("Login response missing tokens");
                    return;
                }
                storeTokens(data.access_token, data.refresh_token);
                const me = await fetchMe();
                applyPrincipal(me?.data || me);
                showAppShell();
                closeAllModals();
                initializeRoute();
                checkSystemHealth();
                checkKiteGate();
            } catch (err) {
                console.error(err);
                showUnlock("Unlock failed. Check network and try again.");
            } finally {
                if (unlockSubmit) unlockSubmit.disabled = false;
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            try {
                if (state.authRequired && getAccessToken()) {
                    await apiRequest("/api/v1/auth/logout", {
                        method: "POST",
                        skipAuthRedirect: true,
                    }).catch(() => null);
                }
            } finally {
                clearTokens();
                stopOpsStream();
                // Reset navigation so the next session always lands on Portfolio
                // Overview, never wherever the previous session happened to be.
                window.history.replaceState({ tabId: "overview" }, "", "/dashboard/overview");
                if (state.authRequired) {
                    showUnlock();
                } else {
                    window.location.reload();
                }
            }
        });
    }

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
        const {
            skipAuthRedirect = false,
            skipToast = false,
            _retried = false,
            ...fetchOptions
        } = options;
        
        // Add default Headers
        const headers = {
            "Content-Type": "application/json",
            ...fetchOptions.headers
        };

        const accessToken = getAccessToken();
        if (accessToken && !headers.Authorization) {
            headers.Authorization = `Bearer ${accessToken}`;
        }

        try {
            const response = await fetch(url, { ...fetchOptions, headers });
            
            // Record Latency
            const end = performance.now();
            const latency = Math.round(end - start);
            
            // Capture Standard Tracing Headers
            const reqId = response.headers.get("X-Request-ID") || "unknown";
            const corrId = response.headers.get("X-Correlation-ID") || "unknown";
            
            updateTelemetry(reqId, corrId, latency);

            if (response.status === 401 && state.authRequired && !_retried) {
                const refreshed = await refreshAccessToken();
                if (refreshed) {
                    return apiRequest(url, { ...options, _retried: true });
                }
                clearTokens();
                if (!skipAuthRedirect) {
                    showUnlock("Session expired. Unlock again.");
                }
                throw { status: 401, data: { detail: "Unauthorized" } };
            }
            
            if (!response.ok) {
                // Parse Problem Details structure if possible
                const errorData = await response.json().catch(() => ({}));
                throw { status: response.status, data: errorData };
            }

            return await response.json();
        } catch (error) {
            console.error(`API request failed: ${url}`, error);
            const detail = error?.data?.detail;
            const title = error?.data?.title;
            let message = "Network request failed";
            if (typeof detail === "string" && detail.trim()) {
                message = detail;
            } else if (detail && typeof detail === "object" && detail.title) {
                message = detail.title;
            } else if (typeof title === "string" && title.trim()) {
                message = title;
            } else if (error?.status) {
                message = `Request failed (${error.status})`;
            }
            if (!skipToast && !(error?.status === 401 && state.authRequired)) {
                showToast(message, "danger");
            }
            throw error;
        }
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
        try {
            for (const symbol of list) {
                await apiRequest("/api/v1/market/candidates", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ symbol }),
                });
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
                <td colspan="6" class="text-center text-muted">No owner-entered positions yet. Log a fill above.</td>
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
        const open = holdings.filter(pos => !pos.closed_ts);
        if (open.length === 0) {
            holdingsTbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">No owner-entered positions yet. Log a fill on the right.</td>
                </tr>
            `;
            return;
        }

        holdingsTbody.innerHTML = open.map(pos => {
            const hasMark = pos.meta && pos.meta.current_price != null;
            const currentPrice = parseFloat(hasMark ? pos.meta.current_price : pos.avg_price);
            const currentVal = parseFloat(pos.quantity) * currentPrice;
            const cost = parseFloat(pos.quantity) * parseFloat(pos.avg_price);
            const pnl = currentVal - cost;
            const pnlClass = pnl >= 0 ? "positive" : "negative";
            const pnlSign = pnl >= 0 ? "+" : "";
            const pnlLabel = hasMark
                ? `${pnlSign}₹ ${pnl.toFixed(2)}`
                : `cost ₹ ${cost.toFixed(2)} (no mark)`;
            const bare = String(pos.instrument_id || "").includes(":")
                ? String(pos.instrument_id).split(":").pop()
                : String(pos.instrument_id || "");

            return `
                <tr>
                    <td class="font-mono"><strong>${bare || pos.instrument_id}</strong></td>
                    <td>${pos.quantity}</td>
                    <td class="font-mono">₹ ${parseFloat(pos.avg_price).toFixed(2)}</td>
                    <td class="font-mono">₹ ${currentVal.toFixed(2)}</td>
                    <td class="font-mono ${hasMark ? pnlClass : "text-muted"}"><strong>${pnlLabel}</strong></td>
                    <td class="holdings-actions">
                        <button type="button" class="inspect-btn" data-validate-symbol="${bare}" title="Ingest + score this symbol">
                            <i class="fas fa-bolt"></i> Add &amp; validate
                        </button>
                        <button type="button" class="inspect-btn" data-close-id="${pos.position_id}">
                            Close
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        holdingsTbody.querySelectorAll("[data-close-id]").forEach(btn => {
            btn.addEventListener("click", () => {
                const id = btn.getAttribute("data-close-id");
                promptClosePosition(id);
            });
        });
        holdingsTbody.querySelectorAll("[data-validate-symbol]").forEach(btn => {
            btn.addEventListener("click", async () => {
                const sym = btn.getAttribute("data-validate-symbol");
                await validateSymbolsNow([sym], { button: btn, refreshDecisions: true });
            });
        });
    }

    async function promptClosePosition(positionId) {
        const raw = window.prompt("Exit price for this fill?");
        if (raw === null || raw.trim() === "") return;
        const exitPrice = parseFloat(raw);
        if (!Number.isFinite(exitPrice) || exitPrice <= 0) {
            showToast("Exit price must be a positive number", "danger");
            return;
        }
        try {
            await apiRequest(`/api/v1/portfolio/positions/${encodeURIComponent(positionId)}/close`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ exit_price: String(exitPrice) }),
            });
            showToast("Position closed", "success");
            await loadPortfolioData();
        } catch (err) {
            console.error(err);
            showToast("Failed to close position", "danger");
        }
    }

    const ownerPositionForm = document.getElementById("owner-position-form");
    if (ownerPositionForm) {
        ownerPositionForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const instrument_id = document.getElementById("pos-symbol").value.trim();
            const quantity = parseInt(document.getElementById("pos-qty").value, 10);
            const avg_price = document.getElementById("pos-entry").value;
            const broker = document.getElementById("pos-broker").value;
            const sector = document.getElementById("pos-sector").value.trim();
            const notes = document.getElementById("pos-notes").value.trim();
            if (!instrument_id || !quantity || !avg_price) {
                showToast("Symbol, quantity, and entry are required", "danger");
                return;
            }
            try {
                await apiRequest("/api/v1/portfolio/positions", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        instrument_id,
                        quantity,
                        avg_price: String(avg_price),
                        broker,
                        sector,
                        notes,
                    }),
                });
                ownerPositionForm.reset();
                document.getElementById("pos-broker").value = "kite";
                showToast(`Logged ${instrument_id} fill`, "success");
                await loadPortfolioData();
            } catch (err) {
                console.error(err);
                showToast("Failed to log fill", "danger");
            }
        });
    }

    const portfolioResetConfirm = document.getElementById("portfolio-reset-confirm");
    const portfolioResetGateStatus = document.getElementById("portfolio-reset-gate-status");
    function syncPortfolioResetGate() {
        const unlocked = portfolioResetConfirm && portfolioResetConfirm.value === "CONFIRM";
        if (portfolioResetGateStatus) {
            portfolioResetGateStatus.textContent = unlocked
                ? "Reset unlocked — choose Reset open or Reset all."
                : "Reset locked until CONFIRM matches exactly.";
            portfolioResetGateStatus.className = `ops-restore-gate-status ${unlocked ? "unlocked" : "locked"}`;
        }
        document.querySelectorAll(".portfolio-reset-btn").forEach(btn => {
            btn.disabled = !unlocked;
        });
    }
    if (portfolioResetConfirm) {
        portfolioResetConfirm.addEventListener("input", syncPortfolioResetGate);
        syncPortfolioResetGate();
    }
    document.querySelectorAll(".portfolio-reset-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const scope = btn.getAttribute("data-scope");
            if (!scope || !portfolioResetConfirm || portfolioResetConfirm.value !== "CONFIRM") return;
            const label = scope === "all" ? "ALL fills (open + closed)" : "open fills only";
            if (!window.confirm(`Reset ${label}? A backup will be created first.`)) return;
            try {
                const res = await apiRequest("/api/v1/portfolio/positions/reset", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ confirmation: "CONFIRM", scope }),
                });
                const n = res && res.data ? res.data.deleted_count : 0;
                showToast(`Reset ${scope}: deleted ${n} fill(s)`, "success");
                portfolioResetConfirm.value = "";
                syncPortfolioResetGate();
                await loadPortfolioData();
            } catch (err) {
                console.error(err);
                showToast("Portfolio reset failed", "danger");
            }
        });
    });

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
            await loadCandidateList();

            // 1. Fetch Volatility Regime and Universe from the latest Pipeline run
            const runsRes = await apiRequest("/api/v1/pipelines/runs").catch(() => null);
            let regime = null;
            let universe = {};
            let qualified = [];
            let universeNote = null;
            let validationSummary = null;

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

                for (const r of runs) {
                    const status = (r.overall_status || "").toString().toUpperCase();
                    if (status === "FAILED" || status === "RUNNING") continue;
                    const data = extractData(r);
                    const members = data.universe_members || {};
                    const hasMembers = Object.keys(members).length > 0;
                    const reg = data.regime_assessment || null;

                    if (!regime && reg) {
                        regime = reg;
                    } else if (
                        regime &&
                        isUnknownVol(regime) &&
                        reg &&
                        !isUnknownVol(reg)
                    ) {
                        regime = reg;
                    }
                    if (Object.keys(universe).length === 0 && hasMembers) {
                        universe = members;
                        qualified = data.qualified_today || [];
                        universeNote = data.universe_note || null;
                        validationSummary = data.validation_summary || null;
                        const summary = data.universe_summary || {};
                        if (!universeNote && summary.excluded != null && summary.included === 0 && summary.evaluated > 0) {
                            universeNote =
                                `All ${summary.evaluated} evaluated symbols were Excluded (e.g. need ≥30 daily bars). ` +
                                "Inspect Trace for rule evidence. Increase ingestion lookback_days if history is short.";
                        }
                    } else if (hasMembers && (!qualified || !qualified.length) && data.qualified_today) {
                        qualified = data.qualified_today;
                    }
                    if (!validationSummary && data.validation_summary) {
                        validationSummary = data.validation_summary;
                    }
                }
                // Fallback: any run with members if still empty
                if (Object.keys(universe).length === 0) {
                    for (const r of runs) {
                        const data = extractData(r);
                        if (Object.keys(data.universe_members || {}).length > 0) {
                            universe = data.universe_members;
                            qualified = data.qualified_today || [];
                            universeNote = data.universe_note || null;
                            validationSummary = data.validation_summary || null;
                            if (!regime) regime = data.regime_assessment || null;
                            break;
                        }
                    }
                }
                universeCache = universe;
            }

            const summaryStrip = document.getElementById("validation-summary-strip");
            if (summaryStrip) {
                if (validationSummary) {
                    const counts = validationSummary.decision_counts || {};
                    summaryStrip.innerHTML =
                        `<strong>${validationSummary.eligible ?? 0}</strong> Eligible · ` +
                        `<strong>${validationSummary.excluded ?? 0}</strong> Excluded · ` +
                        `<strong>${validationSummary.qualified_watch_trade ?? 0}</strong> WATCH/TRADE · ` +
                        `NO_TRADE ${counts.NO_TRADE || 0} · evaluated ${validationSummary.evaluated ?? 0}`;
                } else if (Object.keys(universe).length > 0) {
                    const eligible = Object.values(universe).filter(m => m.included).length;
                    const excluded = Object.keys(universe).length - eligible;
                    summaryStrip.innerHTML =
                        `<strong>${eligible}</strong> Eligible · <strong>${excluded}</strong> Excluded in latest cycle`;
                } else {
                    summaryStrip.innerHTML =
                        `Run <code>./athena-daily smoke</code> or <code>./athena-daily</code> to populate Eligible / Excluded.`;
                }
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
                const trendLabel = ({ BULL: "Bullish", BEAR: "Bearish", SIDEWAYS: "Sideways", NEUTRAL: "Neutral", UNKNOWN: "Unknown" })[trendStr] || trendStr;
                trendBadge.textContent = trendLabel;
                trendBadge.className = `regime-badge ${trendStr === "BULL" ? "bull" : trendStr === "BEAR" ? "bear" : "neutral"}`;

                // Volatility level badge (friendly labels; UNKNOWN = missing India VIX)
                const volStr = regime.volatility || "NORMAL_VOLATILITY";
                const volMeta = formatVolatilityLabel(volStr);
                volBadge.textContent = volMeta.label;
                volBadge.title = volMeta.hint || "";
                volBadge.className = `regime-badge ${volMeta.cls}`;

                // Gap state badge
                const gapRaw = regime.gap || "NO_GAP";
                const gapMeta = {
                    NO_GAP: { label: "No gap", cls: "bull" },
                    GAP_UP: { label: "Gap up", cls: "neutral" },
                    GAP_DOWN: { label: "Gap down", cls: "neutral" },
                    GAP_UNKNOWN: { label: "Gap unknown", cls: "neutral" },
                }[gapRaw] || { label: String(gapRaw).replace(/_/g, " "), cls: "neutral" };
                gapBadge.textContent = gapMeta.label;
                gapBadge.className = `regime-badge ${gapMeta.cls}`;

                // Health gauge
                const score = regime.market_health || 0;
                healthBar.style.width = `${score}%`;
                healthValue.textContent = `${score}/100`;

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
            } else if (trendBadge && volBadge && gapBadge && healthBar && healthValue && evidenceText) {
                trendBadge.textContent = "UNKNOWN";
                trendBadge.className = "regime-badge neutral";
                volBadge.textContent = "UNKNOWN";
                volBadge.className = "regime-badge neutral";
                gapBadge.textContent = "UNKNOWN";
                gapBadge.className = "regime-badge neutral";
                healthBar.style.width = "0%";
                healthValue.textContent = "0/100";
                evidenceText.textContent =
                    "No regime payload in the latest validation run yet. " +
                    "Re-run ./athena-daily smoke (after the latest update) — regime is written from the scan. " +
                    "Volatility can stay UNKNOWN without India VIX in the snapshot.";
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
            body.innerHTML = "No WATCH/TRADE names for the latest validation day.";
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
                                <span class="type-chip type-${String(type).toLowerCase()}">${type || "—"}</span>
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
        const listEl = document.getElementById("candidate-list");
        const emptyEl = document.getElementById("candidate-list-empty");
        const countEl = document.getElementById("candidate-count");
        const candidateSearch = document.getElementById("candidate-search-input");
        if (!listEl) return;
        try {
            const res = await apiRequest("/api/v1/market/candidates");
            const rows = (res && res.data && res.data.candidates) ? res.data.candidates : [];
            listEl.innerHTML = "";
            if (countEl) {
                countEl.textContent = `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
            }
            if (rows.length === 0) {
                if (emptyEl) {
                    emptyEl.textContent = "No symbols in the stock list.";
                    emptyEl.style.display = "block";
                }
                return;
            }
            if (emptyEl) emptyEl.style.display = "none";
            rows.forEach(c => {
                const li = document.createElement("li");
                li.className = "candidate-row";
                li.dataset.symbol = String(c.symbol || "").toUpperCase();
                li.innerHTML = `
                    <span class="symbol-name-col">${c.symbol}</span>
                    <div class="candidate-row-actions">
                        <button type="button" class="inspect-btn candidate-validate-btn" data-symbol="${c.symbol}" title="Re-run ingest + score">
                            <i class="fas fa-bolt"></i> Validate
                        </button>
                        <button type="button" class="inspect-btn candidate-remove-btn" data-symbol="${c.symbol}">
                            <i class="fas fa-times"></i> Remove
                        </button>
                    </div>
                `;
                listEl.appendChild(li);
            });
            if (candidateSearch && candidateSearch.value) {
                filterCandidateList(candidateSearch.value);
            }
            listEl.querySelectorAll(".candidate-validate-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await validateSymbolsNow([sym], { button: btn, refreshDecisions: true });
                });
            });
            listEl.querySelectorAll(".candidate-remove-btn").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const sym = btn.getAttribute("data-symbol");
                    await removeCandidateNow(sym, { button: btn });
                });
            });
        } catch (err) {
            console.error("Failed to load candidates", err);
            if (emptyEl) {
                emptyEl.style.display = "block";
                emptyEl.textContent = "Failed to load validation list.";
            }
            if (countEl) countEl.textContent = "Unavailable";
        }
    }

    function filterCandidateList(rawQuery) {
        const listEl = document.getElementById("candidate-list");
        const emptyEl = document.getElementById("candidate-list-empty");
        const countEl = document.getElementById("candidate-count");
        if (!listEl) return;
        const query = String(rawQuery || "").trim().toUpperCase();
        const rows = Array.from(listEl.querySelectorAll(".candidate-row"));
        let visible = 0;
        rows.forEach(row => {
            const matches = !query || (row.dataset.symbol || "").includes(query);
            row.hidden = !matches;
            if (matches) visible += 1;
        });
        if (countEl) {
            countEl.textContent = query
                ? `${visible} of ${rows.length}`
                : `${rows.length} symbol${rows.length === 1 ? "" : "s"}`;
        }
        if (emptyEl) {
            emptyEl.textContent = query
                ? `No symbols match “${rawQuery}”.`
                : "No symbols in the stock list.";
            emptyEl.style.display = visible === 0 ? "block" : "none";
        }
    }

    const candidateAddBtn = document.getElementById("candidate-add-btn");
    const candidateInput = document.getElementById("candidate-symbol-input");
    const candidateSearchInput = document.getElementById("candidate-search-input");
    if (candidateSearchInput) {
        candidateSearchInput.addEventListener("input", (e) => {
            filterCandidateList(e.target.value);
        });
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
        if (!state.kiteBlocking) hideKiteGate();
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
    const decisionsCarouselContainer = document.getElementById("decisions-carousel-groups");
    const briefingSearch = document.getElementById("briefing-search");
    const dagNodesContainer = document.getElementById("dag-nodes-container");
    const dagSvgLines = document.getElementById("dag-svg-lines");
    const dagDetailsPanel = document.getElementById("dag-details-panel");
    const dagDetailsTitle = document.getElementById("dag-details-title");
    const dagDetailsStatus = document.getElementById("dag-details-status");
    const dagDetailsSummary = document.getElementById("dag-details-summary");
    const dagDetailsGrid = document.getElementById("dag-details-grid");
    const decisionBriefTitle = document.getElementById("decision-brief-title");
    const decisionBriefStanceChip = document.getElementById("decision-brief-stance-chip");
    const decisionBriefTypeChip = document.getElementById("decision-brief-type-chip");
    const decisionBriefAsOf = document.getElementById("decision-brief-asof");
    const decisionBriefBody = document.getElementById("decision-brief-body");
    const decisionBriefGauges = document.getElementById("decision-brief-gauges");
    const decisionBriefTabstrip = document.getElementById("decision-brief-tabstrip");
    const decisionBriefActionbar = document.getElementById("decision-brief-actionbar");
    const decisionBriefRevalidateHeader = document.getElementById("decision-brief-revalidate-header");

    let activeTrace = null;
    let allTraceDecisionsList = [];
    let traceDecisionsList = [];
    let activeDecisionId = null;
    let activeDecisionData = null;
    let activeDepth = null;
    let activeContextData = null;
    let activeJournalEntry = null;
    let activeTradeOutcome = null;
    let activeAnalogs = null;
    let activeCounterfactual = null;
    let activePlanFreshness = null;
    let selectedStageId = null;
    // Persists across decision switches on purpose — flipping through several
    // decisions to compare the same aspect (e.g. Analysis) should not keep
    // resetting back to Setup each time (graceful selection, UI overhaul).
    let activeBriefTab = "setup";

    function escapeDecisionHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function istDateKey() {
        const parts = new Intl.DateTimeFormat("en-GB", {
            timeZone: "Asia/Kolkata",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }).formatToParts(new Date());
        const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
        return `${values.year}-${values.month}-${values.day}`;
    }

    function dismissedDecisionStorageKey() {
        return `athena.dismissed-decisions.${istDateKey()}`;
    }

    function loadDismissedDecisionSymbols() {
        try {
            const raw = JSON.parse(localStorage.getItem(dismissedDecisionStorageKey()) || "[]");
            return new Set(Array.isArray(raw) ? raw.map(v => String(v).toUpperCase()) : []);
        } catch (_err) {
            return new Set();
        }
    }

    const dismissedDecisionSymbols = loadDismissedDecisionSymbols();

    function persistDismissedDecisionSymbols() {
        try {
            localStorage.setItem(
                dismissedDecisionStorageKey(),
                JSON.stringify(Array.from(dismissedDecisionSymbols).sort())
            );
        } catch (_err) {
            showToast("Could not persist dismissed decisions in this browser", "warning");
        }
    }

    function decisionInstrumentKey(decision) {
        const meta = decision && decision.metadata ? decision.metadata : {};
        return String(meta.instrument_id || meta.decision_id || "").toUpperCase();
    }

    function dismissDecisionForToday(decision) {
        const key = decisionInstrumentKey(decision);
        if (!key) return;
        dismissedDecisionSymbols.add(key);
        persistDismissedDecisionSymbols();
        showToast(`${key.includes(":") ? key.split(":").pop() : key} dismissed for today`, "success");
        applyDecisionsView();
    }

    function restoreDismissedDecisions() {
        dismissedDecisionSymbols.clear();
        persistDismissedDecisionSymbols();
        showToast("Dismissed decisions restored", "success");
        applyDecisionsView();
    }

    /** Keep the newest decision per instrument (or decision_id when instrument is missing). */
    function latestDecisionPerInstrument(rows) {
        const byInstrument = new Map();
        for (const d of rows || []) {
            const meta = d && d.metadata ? d.metadata : {};
            const key = meta.instrument_id || meta.decision_id;
            if (!key) continue;
            const prev = byInstrument.get(key);
            const ts = new Date(meta.ts || 0).getTime();
            const prevTs = prev
                ? new Date((prev.metadata && prev.metadata.ts) || 0).getTime()
                : -1;
            if (!prev || ts >= prevTs) {
                byInstrument.set(key, d);
            }
        }
        return Array.from(byInstrument.values());
    }

    /**
     * Walk /api/v1/decisions pages before client dedupe.
     * Default API page_size is 20 (max 100); a single page silently drops symbols
     * after large validate/seed runs.
     */
    async function fetchAllDecisionPages() {
        const pageSize = 100;
        const maxPages = 50;
        const collected = [];
        let page = 1;
        let hasNext = true;

        while (hasNext && page <= maxPages) {
            const qs = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
                sort_by: "ts",
                sort_dir: "desc",
            });
            const res = await apiRequest(`/api/v1/decisions?${qs.toString()}`);
            if (!res || res.status !== "success") {
                throw new Error("decisions list returned a non-success envelope");
            }
            const batch = Array.isArray(res.data) ? res.data : [];
            collected.push(...batch);
            hasNext = Boolean(res.pagination && res.pagination.has_next);
            page += 1;
            if (!batch.length) {
                break;
            }
        }
        return collected;
    }

    async function loadDecisionsWorkspace(options = {}) {
        try {
            const raw = await fetchAllDecisionPages();
            allTraceDecisionsList = raw;
            // Latest decision per instrument for "Today's Decisions" (avoid duplicate cards)
            traceDecisionsList = latestDecisionPerInstrument(raw);
            applyDecisionsView(options);
        } catch (err) {
            console.error("Failed to load decisions", err);
            if (decisionsCarouselContainer) {
                decisionsCarouselContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">Failed to load decisions. Use refresh to retry.</div>';
            }
            if (dagNodesContainer) {
                dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">Decision trace unavailable until briefings load.</div>';
            }
            showToast("Failed to load decisions workspace", "danger");
        }
    }

    function decisionScoreValue(d) {
        const fromText = extractScoreFromText(d.explanation || "");
        if (fromText != null) return Number(fromText);
        return -1;
    }

    const DECISION_TYPE_PRIORITY = { TRADE: 0, WATCH: 1, NO_TRADE: 2, INSUFFICIENT_DATA: 3 };
    function decisionTypePriority(d) {
        const t = String((d.metadata && d.metadata.decision_type) || "").toUpperCase();
        return DECISION_TYPE_PRIORITY[t] ?? 9;
    }

    function applyDecisionsView(options = {}) {
        const query = (briefingSearch && briefingSearch.value || "").toLowerCase().trim();
        const stanceFilter = (document.getElementById("decisions-filter-stance") || {}).value || "all";
        const typeFilter = (document.getElementById("decisions-filter-type") || {}).value || "all";
        const sortMode = (document.getElementById("decisions-sort") || {}).value || "newest";
        const preferDecisionId = options.preferDecisionId || activeDecisionId || null;
        let preferInstrumentId = options.preferInstrumentId
            ? String(options.preferInstrumentId).toUpperCase().replace(/^NSE:|^BSE:/, "")
            : null;

        if (!preferInstrumentId && preferDecisionId) {
            const prior = [...allTraceDecisionsList, ...traceDecisionsList].find(
                d => d && d.metadata && d.metadata.decision_id === preferDecisionId
            );
            if (prior && prior.metadata.instrument_id) {
                preferInstrumentId = String(prior.metadata.instrument_id)
                    .toUpperCase()
                    .replace(/^NSE:|^BSE:/, "");
            }
        }

        let rows = [...traceDecisionsList];
        rows = rows.filter(d => {
            if (dismissedDecisionSymbols.has(decisionInstrumentKey(d))) return false;
            const type = (d.metadata && d.metadata.decision_type) || "";
            const dir = (d.metadata && d.metadata.direction) || "NONE";
            const stance = decisionStance(type, dir).label;
            if (stanceFilter !== "all" && stance !== stanceFilter) return false;
            if (typeFilter !== "all" && String(type).toUpperCase() !== typeFilter) return false;
            if (!query) return true;
            const symbol = (d.metadata.instrument_id || "INDEX").toLowerCase();
            const exp = (d.explanation || "").toLowerCase();
            return symbol.includes(query) || type.toLowerCase().includes(query) || exp.includes(query)
                || stance.toLowerCase().includes(query);
        });

        const stanceRank = { BUY: 0, SELL: 1, HOLD: 2, WAIT: 3, PASS: 4 };
        rows.sort((a, b) => {
            const sa = (a.metadata && a.metadata.instrument_id) || "";
            const sb = (b.metadata && b.metadata.instrument_id) || "";
            const ta = new Date((a.metadata && a.metadata.ts) || 0).getTime();
            const tb = new Date((b.metadata && b.metadata.ts) || 0).getTime();
            const scoreA = decisionScoreValue(a);
            const scoreB = decisionScoreValue(b);
            const stanceA = decisionStance(a.metadata.decision_type, a.metadata.direction).label;
            const stanceB = decisionStance(b.metadata.decision_type, b.metadata.direction).label;
            switch (sortMode) {
                case "oldest": return ta - tb;
                case "symbol-asc": return sa.localeCompare(sb);
                case "symbol-desc": return sb.localeCompare(sa);
                case "score-desc": return scoreB - scoreA || tb - ta;
                case "score-asc": return scoreA - scoreB || tb - ta;
                case "stance":
                    return (stanceRank[stanceA] ?? 9) - (stanceRank[stanceB] ?? 9) || tb - ta;
                case "newest":
                default:
                    return tb - ta;
            }
        });

        renderDecisionCarousels(rows);
        if (rows.length > 0) {
            let next = preferDecisionId
                ? rows.find(d => d.metadata && d.metadata.decision_id === preferDecisionId)
                : null;
            if (!next && preferInstrumentId) {
                next = rows.find(d => {
                    const instrument = String(d.metadata && d.metadata.instrument_id || "")
                        .toUpperCase()
                        .replace(/^NSE:|^BSE:/, "");
                    return instrument === preferInstrumentId;
                });
            }
            // Default selection follows outcome priority (Trade -> Watch ->
            // No trade -> everything else), never plain recency, matching the
            // carousel display order (owner: 2026-07-25, regardless of timestamp).
            const fallback = next || rows.reduce(
                (best, d) => (decisionTypePriority(d) < decisionTypePriority(best) ? d : best),
                rows[0]
            );
            selectBriefing(fallback.metadata.decision_id);
        } else if (dagNodesContainer) {
            dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">No decisions match the current filters.</div>';
            renderDecisionBriefEmpty("No visible decision", "Restore dismissed symbols or change the filters.");
        }
    }

    function formatVolatilityLabel(volStr) {
        const key = String(volStr || "").toUpperCase();
        const map = {
            HIGH_VOLATILITY: { label: "High", cls: "bear", hint: "India VIX above high band" },
            LOW_VOLATILITY: { label: "Low", cls: "bull", hint: "India VIX below low band" },
            NORMAL_VOLATILITY: { label: "Normal", cls: "neutral", hint: "India VIX in normal band" },
            VOLATILITY_UNKNOWN: {
                label: "Unknown",
                cls: "neutral",
                hint: "India VIX was not in the market snapshot — re-run validate/smoke after this update",
            },
            UNKNOWN: {
                label: "Unknown",
                cls: "neutral",
                hint: "Volatility not assessed yet",
            },
        };
        if (map[key]) return map[key];
        const cleaned = key.replace(/_VOLATILITY$/, "").replace(/_/g, " ");
        return { label: cleaned || "Unknown", cls: "neutral", hint: "" };
    }

    function decisionStance(type, direction) {
        const t = String(type || "").toUpperCase();
        const dir = String(direction || "NONE").toUpperCase();
        if (t === "TRADE" && dir === "LONG") return { label: "BUY", cls: "stance-buy" };
        if (t === "TRADE" && dir === "SHORT") return { label: "SELL", cls: "stance-sell" };
        if (t === "TRADE") return { label: "TRADE", cls: "stance-buy" };
        if (t === "WATCH") return { label: "HOLD", cls: "stance-hold" };
        if (t === "NO_TRADE") return { label: "PASS", cls: "stance-pass" };
        if (t === "INSUFFICIENT_DATA") return { label: "WAIT", cls: "stance-wait" };
        return { label: t || "—", cls: "stance-pass" };
    }

    function friendlyGateName(gate) {
        const map = {
            DATA: "Data",
            EVIDENCE: "Evidence",
            RISK: "Risk",
            EXPLAINABILITY: "Explain",
            CONFIDENCE: "Confidence",
            MARKET: "Market",
        };
        return map[String(gate || "").toUpperCase()] || String(gate || "");
    }

    function extractScoreFromText(text) {
        const m = String(text || "").match(/score\s+(\d+(?:\.\d+)?)/i)
            || String(text || "").match(/composite\s+(\d+(?:\.\d+)?)/i);
        if (!m) return null;
        const n = Number(m[1]);
        return Number.isFinite(n) ? n.toFixed(n % 1 === 0 ? 0 : 1) : null;
    }

    /** Round long Decimal strings for display without inventing new values. */
    function sanitizeNumericText(text) {
        return String(text || "").replace(/\d+\.\d{3,}/g, match => {
            const number = Number(match);
            return Number.isFinite(number) ? number.toFixed(1) : match;
        });
    }

    function formatDecisionSummary(explanation, type, gateResults) {
        let headline = sanitizeNumericText(String(explanation || "").trim());
        // Soften any leftover machine phrasing from older runs
        headline = headline
            .replace(/gates failed:\s*\[([^\]]*)\]/gi, (_, inner) => {
                const parts = inner.split(",").map(s => s.replace(/['"]/g, "").trim()).filter(Boolean);
                return parts.length ? `still blocked on ${parts.map(friendlyGateName).join(", ")}` : "safety checks pending";
            })
            .replace(/\bcomposite\s+(\d+(?:\.\d+)?)/gi, "score $1")
            .replace(/\bcomposite\b/gi, "score");

        if (!headline) {
            const t = String(type || "").toUpperCase();
            if (t === "WATCH") headline = "Hold / watch — interesting score, not ready to trade yet.";
            else if (t === "TRADE") headline = "Trade setup — score and safety checks cleared.";
            else if (t === "NO_TRADE") headline = "Pass — score below watch level.";
            else headline = "No explanation recorded.";
        }

        const score = extractScoreFromText(headline);
        const scoreChip = score
            ? `<span class="meta-chip score-chip">Score ${score}</span>`
            : "";

        const gates = Array.isArray(gateResults) ? gateResults : [];
        const failed = gates.filter(g => g && g.passed === false);
        let gateChips = "";
        if (failed.length) {
            gateChips = `<div class="gate-chip-row">${failed.map(g =>
                `<span class="gate-chip fail" title="${sanitizeNumericText(g.detail || "").replace(/"/g, "&quot;")}">Needs ${friendlyGateName(g.gate)}</span>`
            ).join("")}</div>`;
        } else if (gates.length && gates.every(g => g.passed)) {
            gateChips = `<div class="gate-chip-row"><span class="gate-chip pass">All checks passed</span></div>`;
        }

        return { headline, scoreChip, gateChips };
    }

    function humanizeDecisionText(text) {
        if (!text) return "No explanation recorded";
        return formatDecisionSummary(text, "", []).headline;
    }

    function decisionTypeBadge(type) {
        const t = (type || "").toUpperCase();
        return `<span class="type-chip type-${t.toLowerCase()}">${t || "—"}</span>`;
    }

    function formatDecisionPrice(value) {
        const amount = Number(value);
        if (!Number.isFinite(amount)) return "—";
        return `₹${amount.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    function formatDecisionRatio(value) {
        const ratio = Number(value);
        if (!Number.isFinite(ratio)) return "—";
        return `${ratio.toFixed(2)} : 1`;
    }

    function formatDecisionTime(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "Unknown time";
        return date.toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        }) + " IST";
    }

    function renderDecisionBriefEmpty(title, detail) {
        if (decisionBriefTitle) {
            decisionBriefTitle.textContent = "Select a symbol";
            decisionBriefTitle.title = "";
        }
        if (decisionBriefAsOf) decisionBriefAsOf.textContent = "Select a symbol";
        if (decisionBriefStanceChip) decisionBriefStanceChip.innerHTML = "";
        if (decisionBriefTypeChip) decisionBriefTypeChip.innerHTML = "";
        if (decisionBriefGauges) decisionBriefGauges.hidden = true;
        if (decisionBriefTabstrip) decisionBriefTabstrip.hidden = true;
        if (decisionBriefActionbar) decisionBriefActionbar.hidden = true;
        resetCockpitGauges();
        setHeaderRevalidateEnabled(false);
        if (!decisionBriefBody) return;
        decisionBriefBody.innerHTML = `
            <div class="decision-brief-empty">
                <i class="fa-solid fa-chart-line"></i>
                <strong>${escapeDecisionHtml(title || "Select a decision")}</strong>
                <span>${escapeDecisionHtml(detail || "ATHENA will show the current thesis, safety gates, and advisory TradePlan.")}</span>
            </div>
        `;
    }

    // Expected Return % (owner audit #10) — pure arithmetic over the plan's
    // own persisted entry_low/entry_high/targets[0], nothing invented. Uses
    // the nearest target (targets[0]) since that's the one most likely to
    // be hit; when there's more than one target the label says "to T1" so
    // it's never ambiguous which target the % refers to.
    function computeExpectedReturnPct(plan, direction) {
        if (!plan || !Array.isArray(plan.targets) || !plan.targets.length) return null;
        const entryMid = (Number(plan.entry_low) + Number(plan.entry_high)) / 2;
        const target = Number(plan.targets[0]);
        if (!Number.isFinite(entryMid) || entryMid === 0 || !Number.isFinite(target)) return null;
        const isShort = String(direction || "").toUpperCase() === "SHORT";
        return isShort ? ((entryMid - target) / entryMid) * 100 : ((target - entryMid) / entryMid) * 100;
    }

    function renderTradePlan(plan, decisionType, direction) {
        if (!plan) {
            const label = String(decisionType || "").toUpperCase();
            return `
                <div class="decision-brief-section">
                    <h4>ATHENA TradePlan</h4>
                    <div class="no-trade-plan">
                        No actionable entry or exit plan is authorized for a
                        <strong>${escapeDecisionHtml(label || "non-TRADE")}</strong> decision.
                        Re-validate when new market data arrives; do not infer levels from this screen.
                    </div>
                </div>
            `;
        }

        const validFrom = new Date(plan.valid_from);
        const validUntil = new Date(plan.valid_until);
        const now = new Date();
        let statusLabel = "Active";
        let statusClass = "active";
        if (!Number.isNaN(validUntil.getTime()) && now > validUntil) {
            statusLabel = "Expired";
            statusClass = "expired";
        } else if (!Number.isNaN(validFrom.getTime()) && now < validFrom) {
            statusLabel = "Pending";
            statusClass = "pending";
        }
        const targetList = Array.isArray(plan.targets) ? plan.targets : [];
        const targets = targetList.length ? targetList.map(formatDecisionPrice).join(" · ") : "—";
        const returnPct = computeExpectedReturnPct(plan, direction);
        const returnLabel = returnPct !== null
            ? `${returnPct >= 0 ? "+" : ""}${returnPct.toFixed(1)}%`
            : "—";
        const returnCaption = targetList.length > 1 ? "to T1" : "to target";
        // A single point entry (low == high) reading as "X - X" looks like
        // a rendering glitch, not a real zone (owner-reported).
        const entryZoneLabel = Number(plan.entry_low) === Number(plan.entry_high)
            ? formatDecisionPrice(plan.entry_low)
            : `${formatDecisionPrice(plan.entry_low)} – ${formatDecisionPrice(plan.entry_high)}`;

        return `
            <div class="decision-brief-section">
                <div class="decision-brief-section-header">
                    <h4>ATHENA TradePlan</h4>
                    <span class="trade-plan-label">Advisory · not an order</span>
                </div>
                <div class="trade-plan-hero-grid">
                    <div class="trade-plan-hero-metric">
                        <span class="trade-plan-hero-label">Entry zone</span>
                        <strong class="trade-plan-hero-value">${entryZoneLabel}</strong>
                    </div>
                    <div class="trade-plan-hero-metric invalidation">
                        <span class="trade-plan-hero-label">Stop</span>
                        <strong class="trade-plan-hero-value">${formatDecisionPrice(plan.stop_loss)}</strong>
                    </div>
                    <div class="trade-plan-hero-metric target">
                        <span class="trade-plan-hero-label">${targetList.length > 1 ? "Targets" : "Target"}</span>
                        <strong class="trade-plan-hero-value">${targets}</strong>
                    </div>
                    <div class="trade-plan-hero-metric">
                        <span class="trade-plan-hero-label">Expected return</span>
                        <strong class="trade-plan-hero-value">${returnLabel}</strong>
                        <span class="trade-plan-hero-caption">${escapeDecisionHtml(returnCaption)}</span>
                    </div>
                    <div class="trade-plan-hero-metric">
                        <span class="trade-plan-hero-label">Risk : reward</span>
                        <strong class="trade-plan-hero-value">${formatDecisionRatio(plan.risk_reward)}</strong>
                    </div>
                </div>
                <div class="trade-plan-secondary-row">
                    <span>Model units · risk</span>
                    <strong>${escapeDecisionHtml(plan.position_size || 0)} · ${formatDecisionPrice(plan.risk_amount)}</strong>
                </div>
                <div class="trade-plan-validity">
                    <span>${formatDecisionTime(plan.valid_from)} → ${formatDecisionTime(plan.valid_until)}</span>
                    <span class="plan-status-group">
                        <span class="plan-status ${statusClass}">${statusLabel}</span>
                        <span id="trade-plan-freshness-badge" class="plan-freshness-badge"></span>
                    </span>
                </div>
            </div>
        `;
    }

    function renderPlanFreshnessBadge(data) {
        const badge = document.getElementById("trade-plan-freshness-badge");
        if (!badge) return;
        if (!data || !data.has_trade_plan) {
            badge.textContent = "";
            badge.title = "";
            badge.className = "plan-freshness-badge";
            return;
        }
        const pct = data.decay_fraction !== null && data.decay_fraction !== undefined
            ? Math.round(Number(data.decay_fraction) * 100) : null;
        badge.className = `plan-freshness-badge tone-${String(data.status).toLowerCase()}`;
        badge.textContent = pct !== null ? `${pct}% decayed` : friendlyLabel(data.status);
        badge.title = data.summary || "";
    }

    async function loadDecisionPlanFreshness(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/plan-freshness`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activePlanFreshness = response && response.data;
            renderPlanFreshnessBadge(activePlanFreshness);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load plan freshness for ${decisionId}`, err);
        }
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

    function renderCandlestickSvg(series, plan) {
        const host = document.getElementById("decision-chart-canvas");
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

    function friendlyAnalysisName(value) {
        return String(value || "unknown")
            .replace(/_/g, " ")
            .replace(/\b\w/g, char => char.toUpperCase());
    }

    function analysisPercent(value) {
        const number = Number(value);
        return Number.isFinite(number) ? `${number.toFixed(1)}` : "UNKNOWN";
    }

    function analysisMeterWidth(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return 0;
        return Math.max(0, Math.min(100, number));
    }

    function analysisPresentation(label, block, tone) {
        const data = block || {};
        const status = String(data.status || "UNKNOWN").toUpperCase();
        const level = data.level ? String(data.level).toUpperCase() : "";
        const completeness = Number(data.completeness);
        const completenessLabel = Number.isFinite(completeness)
            ? `${Math.round(completeness * 100)}% complete`
            : "Completeness unknown";
        const config = {
            score: {
                icon: "fa-chart-line",
                eyebrow: "Opportunity quality",
                guidance: "Higher means stronger alignment with the active strategy.",
            },
            confidence: {
                icon: "fa-shield-halved",
                eyebrow: "Evidence reliability",
                guidance: "Higher means the assessment is better supported.",
            },
            risk: {
                icon: "fa-triangle-exclamation",
                eyebrow: "Exposure level",
                guidance: "Higher means more uncertainty or market exposure.",
            },
        }[tone];
        // Score has no backend-computed level (scoring.json carries no
        // levels block) — band it client-side from the same value everyone
        // else already sees, same convention as the Hero cockpit gauges.
        // Confidence/Risk keep their real backend level; never invented.
        const isOk = status === "OK";
        const displayBand = tone === "score"
            ? (isOk ? qualityBand(data.value) : null)
            : (isOk && level ? friendlyAnalysisName(level) : null);
        return {
            data,
            status,
            level,
            displayBand,
            completenessLabel,
            icon: config.icon,
            eyebrow: config.eyebrow,
            guidance: config.guidance,
            label,
            tone,
            valueLabel: analysisPercent(data.value),
            meterWidth: analysisMeterWidth(data.value),
        };
    }

    function renderEligibilityDepth(eligibility) {
        const host = document.getElementById("decision-eligibility-depth");
        if (!host) return;
        const data = eligibility || {};
        const status = String(data.status || "UNKNOWN").toUpperCase();
        const statusClass =
            status === "INCLUDED" ? "included" : (status === "EXCLUDED" ? "excluded" : "unknown");
        const exclusions = Array.isArray(data.exclusion_reasons) ? data.exclusion_reasons : [];
        const rules = Array.isArray(data.rules) ? data.rules : [];
        host.innerHTML = `
            <div class="eligibility-summary">
                <span class="depth-status ${statusClass}">${escapeDecisionHtml(status)}</span>
                <span>${escapeDecisionHtml(data.summary || "No persisted eligibility assessment.")}</span>
            </div>
            ${exclusions.length ? `
                <div class="eligibility-exclusions">
                    ${exclusions.map(reason => `<span>${escapeDecisionHtml(reason)}</span>`).join("")}
                </div>
            ` : ""}
            ${rules.length ? `
                <details class="decision-depth-details">
                    <summary>${rules.length} eligibility rule${rules.length === 1 ? "" : "s"}</summary>
                    <div class="eligibility-rule-list">
                        ${rules.map(rule => `
                            <div class="eligibility-rule">
                                <i class="fa-solid ${rule.passed ? "fa-circle-check pass" : "fa-circle-xmark fail"}"></i>
                                <div>
                                    <strong>${escapeDecisionHtml(friendlyAnalysisName(rule.rule))}</strong>
                                    <p>${escapeDecisionHtml(rule.explanation || "No rationale recorded.")}</p>
                                </div>
                            </div>
                        `).join("")}
                    </div>
                </details>
            ` : ""}
        `;
    }

    const QUALITY_LADDER_BANDS = ["Weak", "Fair", "Good", "Strong", "Excellent"];

    function qualityLadder(band) {
        return `
            <div class="quality-ladder" aria-hidden="true">
                ${QUALITY_LADDER_BANDS.map(b => `<span class="quality-ladder-seg${b === band ? " active" : ""}"></span>`).join("")}
            </div>
        `;
    }

    function renderAnalysisSummaryCard(label, block, tone) {
        const view = analysisPresentation(label, block, tone);
        const band = view.displayBand || "Unknown";
        return `
            <article class="analysis-summary-card ${escapeDecisionHtml(tone)}">
                <div class="analysis-summary-top">
                    <span class="analysis-summary-icon">
                        <i class="fa-solid ${escapeDecisionHtml(view.icon)}"></i>
                    </span>
                    <div>
                        <span class="analysis-summary-eyebrow">${escapeDecisionHtml(view.eyebrow)}</span>
                        <h5>${escapeDecisionHtml(label)}</h5>
                    </div>
                    <span class="depth-status ${view.status === "OK" ? "included" : "unknown"}">
                        ${escapeDecisionHtml(view.status)}
                    </span>
                </div>
                <div class="analysis-summary-band">${escapeDecisionHtml(band)}</div>
                <div class="analysis-summary-score">
                    <strong>${escapeDecisionHtml(view.valueLabel)}</strong>
                    <span>/ 100</span>
                </div>
                <div class="analysis-meter" aria-hidden="true">
                    <span style="width: ${view.meterWidth}%"></span>
                </div>
                ${tone === "score" ? qualityLadder(view.displayBand) : ""}
                <div class="analysis-summary-foot">
                    <span>${escapeDecisionHtml(view.completenessLabel)}</span>
                </div>
            </article>
        `;
    }

    // Real, already-persisted weight/weighted fields (AnalysisDimensionDTO) —
    // never a client-side re-derivation of config weights, per "Why?"
    // contribution breakdown (owner audit #36).
    function dimensionContributionPct(dimensions) {
        const total = dimensions.reduce((sum, d) => {
            const w = Number(d.weighted);
            return sum + (Number.isFinite(w) ? w : 0);
        }, 0);
        return dimensions.map(d => {
            const w = Number(d.weighted);
            const pct = total > 0 && Number.isFinite(w) ? (w / total) * 100 : null;
            return Object.assign({}, d, { contributionPct: pct });
        });
    }

    function dimensionExplanationBody(dimension) {
        const contributions = Array.isArray(dimension.contributions) ? dimension.contributions : [];
        const explanation = sanitizeNumericText(dimension.explanation || "No component rationale recorded.");
        return `
            <div class="analysis-component-body">
                <p>${escapeDecisionHtml(explanation)}</p>
                ${contributions.length ? `
                    <div class="analysis-inputs">
                        <span>Recorded inputs</span>
                        <ul>
                    ${contributions.map(item => `
                        <li>${escapeDecisionHtml(sanitizeNumericText(item.description || item.source || "Recorded contribution"))}</li>
                    `).join("")}
                        </ul>
                    </div>
                ` : ""}
            </div>
        `;
    }

    function starRating(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return 0;
        return Math.max(1, Math.min(5, Math.round(n / 20)));
    }

    function starGlyphs(count) {
        return "★".repeat(count) + "☆".repeat(5 - count);
    }

    // Score contributors as storytelling (owner audit #7): ranked by actual
    // value, star rating plus the real contribution % from weight/weighted —
    // never a re-derived config-weight table client-side.
    function renderScoreContributors(dimensions) {
        const withPct = dimensionContributionPct(dimensions);
        // Sort by actual contribution (weight x value), not star rating —
        // a 4-star dimension worth 12% of the score must never rank above a
        // 3-star one worth 21% (owner-reported mismatch between order and %).
        const sorted = [...withPct].sort((a, b) => {
            const pa = a.contributionPct;
            const pb = b.contributionPct;
            if (pa === null && pb === null) return (Number(b.value) || -1) - (Number(a.value) || -1);
            if (pa === null) return 1;
            if (pb === null) return -1;
            return pb - pa;
        });
        return `<div class="analysis-component-list">${sorted.map(d => {
            const known = d.status === "OK";
            const stars = known ? starRating(d.value) : 0;
            const pctLabel = d.contributionPct !== null
                ? `${d.contributionPct.toFixed(0)}% of score`
                : "not counted";
            return `
                <details class="score-contributor-row">
                    <summary>
                        <span class="contributor-name">${escapeDecisionHtml(friendlyAnalysisName(d.name))}</span>
                        <span class="contributor-stars" aria-hidden="true">${known ? escapeDecisionHtml(starGlyphs(stars)) : "—"}</span>
                        <span class="contributor-pct">${escapeDecisionHtml(pctLabel)}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </summary>
                    ${dimensionExplanationBody(d)}
                </details>
            `;
        }).join("")}</div>`;
    }

    // "Why ATHENA trusts this" (owner audit #8) — a checklist, not a bar
    // chart. Trust/flag comes entirely from the backend's own persisted
    // level (LOW/MODERATE/HIGH), never a new client-side threshold.
    const CONFIDENCE_TRUST_LABELS = {
        evidence_completeness: "Evidence is complete",
        data_freshness: "Data is fresh",
        indicator_availability: "Indicators fully available",
        cross_engine_agreement: "Engines agree with each other",
        unknown_ratio: "No unknown or missing signals",
        consistency: "No conflicting signals",
    };

    function renderConfidenceChecklist(dimensions) {
        return `<div class="analysis-component-list">${dimensions.map(d => {
            const known = d.status === "OK";
            const level = String(d.level || "").toUpperCase();
            const trusted = known && level && !level.includes("LOW");
            const icon = !known ? "fa-circle-question unknown" : (trusted ? "fa-circle-check pass" : "fa-circle-xmark fail");
            const label = CONFIDENCE_TRUST_LABELS[d.name] || friendlyAnalysisName(d.name);
            return `
                <details class="trust-checklist-row">
                    <summary>
                        <i class="fa-solid ${icon}"></i>
                        <span class="contributor-name">${escapeDecisionHtml(label)}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </summary>
                    ${dimensionExplanationBody(d)}
                </details>
            `;
        }).join("")}</div>`;
    }

    // Major Risks (owner audit #9) — categorized by hazard, highest first.
    // Same 3-band Low/Medium/High scale as the Hero cockpit gauge, applied
    // per-dimension instead of only to the overall risk value.
    function renderRiskSummary(dimensions) {
        const sorted = [...dimensions].sort((a, b) => (Number(b.value) || -1) - (Number(a.value) || -1));
        return `<div class="analysis-component-list">${sorted.map(d => {
            const known = d.status === "OK";
            const band = known ? riskBand(d.value) : null;
            const tone = band === "High" ? "fail" : (band === "Medium" ? "warn" : "pass");
            return `
                <details class="risk-summary-row">
                    <summary>
                        <span class="contributor-name">${escapeDecisionHtml(friendlyAnalysisName(d.name))}</span>
                        <span class="risk-band-chip ${known ? tone : "unknown"}">${escapeDecisionHtml(band || "Unknown")}</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </summary>
                    ${dimensionExplanationBody(d)}
                </details>
            `;
        }).join("")}</div>`;
    }

    function renderAnalysisBlock(label, block, tone) {
        const view = analysisPresentation(label, block, tone);
        const data = view.data;
        const dimensions = Array.isArray(data.dimensions) ? data.dimensions : [];
        const explanation = sanitizeNumericText(
            data.explanation || `No persisted ${label.toLowerCase()} explanation.`
        );
        const componentsHtml = !dimensions.length
            ? '<div class="analysis-no-components">No component detail was persisted.</div>'
            : (tone === "score" ? renderScoreContributors(dimensions)
                : tone === "confidence" ? renderConfidenceChecklist(dimensions)
                : renderRiskSummary(dimensions));
        return `
            <details class="analysis-detail-panel ${escapeDecisionHtml(tone)}">
                <summary>
                    <span class="analysis-detail-icon">
                        <i class="fa-solid ${escapeDecisionHtml(view.icon)}"></i>
                    </span>
                    <span class="analysis-detail-title">
                        <strong>${escapeDecisionHtml(label)} breakdown</strong>
                        <small>${dimensions.length} component${dimensions.length === 1 ? "" : "s"} · ${escapeDecisionHtml(view.guidance)}</small>
                    </span>
                    <span class="analysis-detail-value">${escapeDecisionHtml(view.valueLabel)}</span>
                    <i class="fa-solid fa-chevron-down analysis-detail-chevron"></i>
                </summary>
                <div class="analysis-detail-content">
                    <p class="analysis-detail-explanation">${escapeDecisionHtml(explanation)}</p>
                    ${componentsHtml}
                </div>
            </details>
        `;
    }

    // The action bar is static (wired once, not rebuilt per decision) so a
    // "Removed" state from a previous symbol must not leak onto the next one.
    function resetActionButtons() {
        const removeBtn = document.getElementById("decision-brief-remove-candidate");
        if (removeBtn) {
            removeBtn.disabled = false;
            const icon = removeBtn.querySelector("i");
            const label = removeBtn.querySelector("span");
            if (icon) icon.className = "fa-solid fa-list-check";
            if (label) label.textContent = "Remove candidate";
        }
    }

    // Meaning over decimals (UX-2/owner audit): a 0-100 value on its own
    // means nothing to a trader in under 5 seconds — band it into a word
    // first, keep the number as a secondary caption.
    function qualityBand(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return null;
        if (n >= 85) return "Excellent";
        if (n >= 70) return "Strong";
        if (n >= 55) return "Good";
        if (n >= 40) return "Fair";
        return "Weak";
    }

    // Risk reads as a hazard level (Low/Medium/High), not a quality score —
    // a "Weak risk" would be nonsensical, so it gets its own 3-band scale.
    function riskBand(value) {
        const n = Number(value);
        if (!Number.isFinite(n)) return null;
        if (n < 35) return "Low";
        if (n < 65) return "Medium";
        return "High";
    }

    // Sticky cockpit gauges reuse the exact same status/level/value already
    // computed for the Analysis tab's summary cards — never a second
    // client-derived score, just a different rendering of the same numbers.
    function resetCockpitGauges() {
        ["score", "confidence", "risk"].forEach(tone => {
            const valueEl = document.getElementById(`gauge-${tone}-value`);
            const bandEl = document.getElementById(`gauge-${tone}-band`);
            const barEl = document.getElementById(`gauge-${tone}-bar`);
            if (valueEl) valueEl.textContent = "—";
            if (bandEl) bandEl.textContent = "—";
            if (barEl) {
                barEl.style.width = "0%";
                barEl.style.background = "var(--text-muted)";
            }
        });
        const rrEl = document.getElementById("hero-rr-value");
        if (rrEl) rrEl.textContent = "—";
    }

    function gaugeToneColor(view) {
        const level = String(view.level || "").toUpperCase();
        if (view.status !== "OK" || !level) return "var(--text-muted)";
        const highIsGood = view.tone !== "risk";
        if (level.includes("HIGH") || level.includes("STRONG")) {
            return highIsGood ? "var(--success)" : "var(--danger)";
        }
        if (level.includes("LOW") || level.includes("WEAK")) {
            return highIsGood ? "var(--danger)" : "var(--success)";
        }
        return "var(--warning)";
    }

    function renderCockpitGauges(depth) {
        [
            ["score", depth && depth.score],
            ["confidence", depth && depth.confidence],
            ["risk", depth && depth.risk],
        ].forEach(([tone, block]) => {
            const view = analysisPresentation(friendlyAnalysisName(tone), block, tone);
            const valueEl = document.getElementById(`gauge-${tone}-value`);
            const bandEl = document.getElementById(`gauge-${tone}-band`);
            const barEl = document.getElementById(`gauge-${tone}-bar`);
            // A block that isn't OK (UNKNOWN status) must never be banded as
            // a real "Weak" score — that's fabricating a value that was
            // never actually computed (owner-reported mismatch: banner said
            // 66.92, gauge said 0.0/Weak).
            const known = view.status === "OK";
            const color = known ? gaugeToneColor(view) : "var(--text-muted)";
            const band = known
                ? (tone === "risk" ? riskBand(view.data.value) : qualityBand(view.data.value))
                : null;
            if (valueEl) valueEl.textContent = known ? view.valueLabel : "—";
            if (bandEl) {
                bandEl.textContent = band || "Unknown";
                bandEl.style.color = color;
            }
            if (barEl) {
                barEl.style.width = known ? `${view.meterWidth}%` : "0%";
                barEl.style.background = color;
            }
        });
        renderExecutiveSummary();
    }

    function renderDecisionDepth(depth) {
        renderEligibilityDepth(depth && depth.eligibility);
        renderCockpitGauges(depth);
        const host = document.getElementById("decision-analysis-depth");
        if (!host) return;
        const blocks = [
            ["Score", depth && depth.score, "score"],
            ["Confidence", depth && depth.confidence, "confidence"],
            ["Risk", depth && depth.risk, "risk"],
        ];
        host.innerHTML = `
            <div class="analysis-overview-grid">
                ${blocks.map(args => renderAnalysisSummaryCard(...args)).join("")}
            </div>
            <div class="analysis-detail-stack">
                ${blocks.map(args => renderAnalysisBlock(...args)).join("")}
            </div>
        `;
    }

    // Five plain-English lines, composed entirely from strings the engines
    // already wrote (score/confidence/risk .explanation, gate results) —
    // never generated, per ADR-005. "Building summary..." until score depth
    // arrives; gates + suitability show immediately since they're synchronous.
    function buildExecutiveSummaryLines(decision, depth) {
        const lines = [];
        const gates = decision.analysis && Array.isArray(decision.analysis.gate_results)
            ? decision.analysis.gate_results
            : [];
        if (gates.length) {
            const failed = gates.filter(g => g && g.passed === false);
            lines.push(failed.length
                ? `Blocked on ${failed.length} of ${gates.length} safety gates: ${failed.map(g => friendlyGateName(g.gate)).join(", ")}.`
                : `Passed all ${gates.length} safety gates.`);
        }
        [["score", "Score"], ["confidence", "Confidence"], ["risk", "Risk"]].forEach(([key, label]) => {
            const block = depth && depth[key];
            if (block && block.status === "OK" && block.explanation) {
                lines.push(sanitizeNumericText(block.explanation));
            }
        });
        const suitability = {
            TRADE: "All safety checks cleared — ready for entry.",
            WATCH: "Above the watch threshold, not yet ready to trade.",
            NO_TRADE: "Below the bar for a trade right now.",
            INSUFFICIENT_DATA: "Not enough data to assess yet.",
        }[String(decision.metadata.decision_type || "").toUpperCase()];
        if (suitability) lines.push(suitability);
        return lines;
    }

    function renderExecutiveSummary() {
        const host = document.getElementById("decision-executive-summary");
        if (!host || !activeDecisionData) return;
        const lines = buildExecutiveSummaryLines(activeDecisionData, activeDepth);
        if (!lines.length) {
            host.innerHTML = '<div class="decision-depth-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> Building summary…</div>';
            return;
        }
        host.innerHTML = `<ul class="executive-summary-list">${
            lines.map(l => `<li>${escapeDecisionHtml(l)}</li>`).join("")
        }</ul>`;
    }

    async function loadDecisionDepth(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/depth`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeDepth = response && response.data;
            renderDecisionDepth(activeDepth);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load decision depth for ${decisionId}`, err);
            renderDecisionDepth(null);
        }
    }

    function friendlySessionType(type) {
        const map = {
            NORMAL: "Normal trading session",
            WEEKEND: "Weekend — market closed",
            HOLIDAY: "Exchange holiday",
            MUHURAT: "Muhurat / special session",
            SPECIAL: "Special session",
        };
        return map[type] || type || "Unknown";
    }

    function sessionChipTone(type) {
        if (type === "NORMAL") return "good";
        if (type === "HOLIDAY" || type === "WEEKEND") return "neutral";
        return "unknown";
    }

    function contextChipTone(label) {
        const s = String(label || "").toUpperCase();
        if (s.includes("UNKNOWN")) return "unknown";
        if (/(BULL|STRONG|HEALTHY|CALM)$|GAP_UP/.test(s)) return "good";
        if (/(BEAR|WEAK|ELEVATED)$|HIGH_VOLATILITY|GAP_DOWN/.test(s)) return "bad";
        if (/(MIXED|FLAT|SIDEWAYS)/.test(s)) return "warn";
        return "neutral";
    }

    function friendlyLabel(label) {
        return String(label || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    }

    function contextChip(label, tone) {
        return `<span class="context-chip tone-${tone}">${escapeDecisionHtml(friendlyLabel(label))}</span>`;
    }

    function renderDecisionContext(context) {
        const host = document.getElementById("decision-context-lane");
        if (!host) return;
        if (!context) {
            host.innerHTML = '<div class="decision-depth-loading">Context unavailable.</div>';
            return;
        }
        const cal = context.calendar || {};
        const regime = context.regime || { status: "UNKNOWN" };
        const mh = context.market_health || { status: "UNKNOWN" };
        const links = Array.isArray(context.external_links) ? context.external_links : [];

        const sessionChips = [
            contextChip(friendlySessionType(cal.session_type), sessionChipTone(cal.session_type)),
            cal.is_weekly_expiry ? contextChip("Weekly expiry", "warn") : "",
            cal.is_monthly_expiry ? contextChip("Monthly expiry", "warn") : "",
            cal.holiday_name ? contextChip(cal.holiday_name, "warn") : "",
        ].filter(Boolean).join("");

        const eventRows = (cal.events || []).map(ev => `
            <li><i class="fa-solid fa-star-of-life"></i>
                <strong>${escapeDecisionHtml(friendlyLabel(ev.kind || "Event"))}</strong>
                <span>${escapeDecisionHtml(ev.name || "")}</span></li>
        `).join("");

        const regimeBlock = regime.status === "ASSESSED"
            ? `<div class="context-chip-row">${(regime.labels || [])
                  .map(l => contextChip(l, contextChipTone(l))).join("")}</div>
               <p class="context-caption">${escapeDecisionHtml(regime.explanation || "")}</p>`
            : '<p class="context-caption unknown">UNKNOWN — re-validate to persist a regime assessment for this decision.</p>';

        const dimensions = mh.dimensions || {};
        const healthBlock = mh.status === "ASSESSED"
            ? `<div class="context-chip-row">${Object.values(dimensions)
                  .map(label => contextChip(label, contextChipTone(label))).join("")}</div>`
            : '<p class="context-caption unknown">UNKNOWN — re-validate to persist a market-health assessment for this decision.</p>';

        const linkRows = links.length
            ? `<ul class="context-links-list">
                   ${links.map(l => `
                       <li><i class="fa-solid fa-arrow-up-right-from-square"></i>
                           <a href="${escapeDecisionHtml(l.url)}" target="_blank" rel="noopener noreferrer">
                               ${escapeDecisionHtml(l.title)}
                           </a>
                           <small>${escapeDecisionHtml(l.source)}</small>
                       </li>
                   `).join("")}
               </ul>`
            : '<p class="context-caption">No curated external links for this instrument.</p>';

        host.innerHTML = `
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-calendar-day"></i> Session</h5>
                <div class="context-chip-row">${sessionChips}</div>
                ${eventRows ? `<ul class="context-events-list">${eventRows}</ul>` : ""}
            </div>
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-chart-line"></i> Regime</h5>
                ${regimeBlock}
            </div>
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-heart-pulse"></i> Market health</h5>
                ${healthBlock}
            </div>
            <div class="context-lane-block">
                <h5><i class="fa-solid fa-link"></i> External research</h5>
                ${linkRows}
            </div>
        `;
    }

    async function loadDecisionContext(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/context`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeContextData = response && response.data;
            renderDecisionContext(activeContextData);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load decision context for ${decisionId}`, err);
            renderDecisionContext(null);
        }
    }

    async function exportDecisionBrief(decisionId, button) {
        if (button) {
            button.disabled = true;
            button.dataset.originalHtml = button.innerHTML;
            button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Exporting…';
        }
        try {
            const jobRes = await apiRequest("/api/v1/exports", {
                method: "POST",
                body: JSON.stringify({
                    source: { artifact_id: decisionId, artifact_type: "DECISION_BRIEF" },
                    format: "JSON",
                    options: {},
                }),
            });
            const artifactId = jobRes && jobRes.data && jobRes.data.result_artifact_id;
            if (!artifactId) throw new Error("Export produced no artifact");
            const artRes = await apiRequest(
                `/api/v1/exports/artifacts/${encodeURIComponent(artifactId)}`
            );
            const artifact = artRes && artRes.data;
            if (!artifact) throw new Error("Export artifact unavailable");
            const blob = new Blob(
                [artifact.payload],
                { type: (artifact.metadata && artifact.metadata.content_type) || "application/json" }
            );
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = (artifact.metadata && artifact.metadata.filename) || `decision_brief_${decisionId}.json`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
            showToast("Decision brief exported.", "success");
        } catch (err) {
            console.error(`Failed to export decision brief for ${decisionId}`, err);
            showToast("Failed to export decision brief.", "danger");
        } finally {
            if (button) {
                button.disabled = false;
                button.innerHTML = button.dataset.originalHtml
                    || '<i class="fa-solid fa-file-export"></i> Export Brief';
            }
        }
    }

    function journalActionTone(userAction) {
        if (userAction === "ACCEPTED") return "good";
        if (userAction === "REJECTED") return "bad";
        return "neutral";
    }

    function renderJournalPanel(decisionId) {
        const host = document.getElementById("decision-journal-panel");
        if (!host) return;

        const entry = activeJournalEntry;
        const actionRow = `
            <div class="journal-action-row">
                <button type="button" class="btn btn-outline journal-action-btn" data-action="ACCEPTED">
                    <i class="fa-solid fa-check"></i> Accept
                </button>
                <button type="button" class="btn btn-outline journal-action-btn" data-action="REJECTED">
                    <i class="fa-solid fa-xmark"></i> Reject
                </button>
                <button type="button" class="btn btn-outline journal-action-btn" data-action="IGNORED">
                    <i class="fa-solid fa-eye-slash"></i> Ignore
                </button>
            </div>
            <textarea id="journal-notes-input" class="journal-notes-input" rows="2"
                placeholder="Optional notes (why, sizing, conviction…)"></textarea>
        `;

        const statusBadge = entry
            ? `<div class="journal-status-row">
                   <span class="context-chip tone-${journalActionTone(entry.user_action)}">${escapeDecisionHtml(entry.user_action)}</span>
                   <span class="text-muted">recorded ${escapeDecisionHtml(formatDecisionTime(entry.action_ts))}</span>
                   ${entry.notes ? `<p class="context-caption">${escapeDecisionHtml(entry.notes)}</p>` : ""}
               </div>`
            : "";

        let outcomeBlock = "";
        if (entry && entry.user_action === "ACCEPTED") {
            outcomeBlock = activeTradeOutcome
                ? renderOutcomeResult(activeTradeOutcome)
                : renderOutcomeForm();
        }

        host.innerHTML = `
            ${statusBadge}
            <details class="decision-depth-details" ${entry ? "" : "open"}>
                <summary>${entry ? "Change response" : "Record your response"}</summary>
                ${actionRow}
            </details>
            ${outcomeBlock}
        `;

        host.querySelectorAll(".journal-action-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const notesEl = document.getElementById("journal-notes-input");
                recordJournalEntry(decisionId, btn.getAttribute("data-action"), notesEl ? notesEl.value : "", btn);
            });
        });

        const outcomeSubmit = document.getElementById("outcome-submit-btn");
        if (outcomeSubmit) {
            outcomeSubmit.addEventListener("click", () => recordTradeOutcomeNow(decisionId, outcomeSubmit));
        }
    }

    function renderOutcomeForm() {
        const plan = activeDecisionData && activeDecisionData.trade_plan;
        const defaultQty = plan ? plan.position_size : 1;
        return `
            <div class="outcome-form">
                <h5>Log realized outcome</h5>
                <p class="context-caption">
                    PnL, holding time, and TradePlan adherence are computed here — never entered
                    manually.
                </p>
                <div class="outcome-form-grid">
                    <label>Entry price
                        <input id="outcome-entry-price" type="number" step="0.01"
                            value="${plan ? plan.entry_low : ""}">
                    </label>
                    <label>Exit price
                        <input id="outcome-exit-price" type="number" step="0.01">
                    </label>
                    <label>Quantity
                        <input id="outcome-quantity" type="number" step="1" min="1" value="${defaultQty}">
                    </label>
                </div>
                <button id="outcome-submit-btn" class="btn btn-outline" type="button">
                    <i class="fa-solid fa-flag-checkered"></i> Log outcome
                </button>
            </div>
        `;
    }

    function renderOutcomeResult(outcome) {
        const pnlValue = Number(outcome.pnl);
        const pnlTone = pnlValue > 0 ? "good" : (pnlValue < 0 ? "bad" : "neutral");
        const adherence = outcome.adherence || {};
        const adherenceChips = Object.entries(adherence).map(([key, value]) => {
            const label = key.replace(/_/g, " ");
            return `<span class="context-chip tone-${value ? "good" : "bad"}">${escapeDecisionHtml(label)}: ${value ? "yes" : "no"}</span>`;
        }).join("");
        return `
            <div class="outcome-result">
                <h5>Realized outcome</h5>
                <div class="outcome-result-grid">
                    <div><span>Entry</span><strong>${formatDecisionPrice(outcome.entry_price)}</strong></div>
                    <div><span>Exit</span><strong>${formatDecisionPrice(outcome.exit_price)}</strong></div>
                    <div><span>PnL</span><strong class="tone-${pnlTone}-text">${formatDecisionPrice(outcome.pnl)}</strong></div>
                    <div><span>Holding</span><strong>${Math.round(outcome.holding_seconds / 60)} min</strong></div>
                </div>
                <div class="context-chip-row">${adherenceChips}</div>
                <p class="context-caption">Closed ${escapeDecisionHtml(formatDecisionTime(outcome.closed_ts))}</p>
            </div>
        `;
    }

    async function loadJournalPanel(decisionId) {
        try {
            const [journalRes, outcomeRes] = await Promise.all([
                apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/journal`, { skipToast: true }),
                apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/outcome`, { skipToast: true }),
            ]);
            if (activeDecisionId !== decisionId) return;
            activeJournalEntry = journalRes && journalRes.data;
            activeTradeOutcome = outcomeRes && outcomeRes.data;
            renderJournalPanel(decisionId);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load journal/outcome for ${decisionId}`, err);
            const host = document.getElementById("decision-journal-panel");
            if (host) host.innerHTML = '<div class="context-caption">Unable to load your response.</div>';
        }
    }

    async function recordJournalEntry(decisionId, userAction, notes, button) {
        if (button) button.disabled = true;
        try {
            const res = await apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/journal`, {
                method: "POST",
                body: JSON.stringify({ user_action: userAction, notes: notes || "" }),
            });
            activeJournalEntry = res && res.data;
            showToast(`Response recorded: ${userAction}`, "success");
            renderJournalPanel(decisionId);
        } catch (err) {
            console.error(`Failed to record journal entry for ${decisionId}`, err);
        } finally {
            if (button) button.disabled = false;
        }
    }

    async function recordTradeOutcomeNow(decisionId, button) {
        const entryEl = document.getElementById("outcome-entry-price");
        const exitEl = document.getElementById("outcome-exit-price");
        const qtyEl = document.getElementById("outcome-quantity");
        const entryPrice = entryEl ? entryEl.value : "";
        const exitPrice = exitEl ? exitEl.value : "";
        const quantity = qtyEl ? qtyEl.value : "";
        if (!entryPrice || !exitPrice || !quantity) {
            showToast("Entry price, exit price, and quantity are required", "danger");
            return;
        }
        if (button) {
            button.disabled = true;
            button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Logging…';
        }
        try {
            const res = await apiRequest(`/api/v1/decisions/${encodeURIComponent(decisionId)}/outcome`, {
                method: "POST",
                body: JSON.stringify({
                    entry_price: entryPrice,
                    exit_price: exitPrice,
                    quantity: Number(quantity),
                }),
            });
            activeTradeOutcome = res && res.data;
            showToast("Outcome logged.", "success");
            renderJournalPanel(decisionId);
        } catch (err) {
            console.error(`Failed to record trade outcome for ${decisionId}`, err);
            showToast("Failed to log outcome.", "danger");
            if (button) {
                button.disabled = false;
                button.innerHTML = '<i class="fa-solid fa-flag-checkered"></i> Log outcome';
            }
        }
    }

    // Max possible distance across 3 dimensions each 0-100 (sqrt(100^2*3)) —
    // used only to render an intuitive similarity %, never persisted or compared.
    const ANALOG_MAX_DISTANCE = 173.2;

    function renderAnalogsPanel(analogs) {
        const host = document.getElementById("decision-analogs-panel");
        if (!host) return;
        const data = analogs || { analogs: [], compared_count: 0 };
        const rows = Array.isArray(data.analogs) ? data.analogs : [];

        if (!rows.length) {
            host.innerHTML = `<div class="context-caption">
                ${data.compared_count === 0
                    ? "No comparable historical decisions yet (needs a persisted score/confidence/risk fingerprint)."
                    : "No similar setups found."}
            </div>`;
            return;
        }

        host.innerHTML = `
            <div class="analog-list">
                ${rows.map(row => {
                    const symbol = (row.instrument_id || "").split(":").pop() || "—";
                    const similarity = Math.max(
                        0, Math.round(100 - (Number(row.distance) / ANALOG_MAX_DISTANCE) * 100)
                    );
                    const stance = decisionStance(row.decision_type, row.direction);
                    const responseChip = row.user_action
                        ? contextChip(row.user_action, journalActionTone(row.user_action))
                        : `<span class="context-chip tone-unknown">no response</span>`;
                    const pnlValue = row.outcome_pnl !== null && row.outcome_pnl !== undefined
                        ? Number(row.outcome_pnl) : null;
                    const outcomeChip = pnlValue !== null
                        ? `<span class="context-chip tone-${pnlValue > 0 ? "good" : (pnlValue < 0 ? "bad" : "neutral")}">${escapeDecisionHtml(formatDecisionPrice(row.outcome_pnl))}</span>`
                        : `<span class="context-chip tone-unknown">no outcome logged</span>`;
                    return `
                        <button type="button" class="analog-row" data-decision-id="${escapeDecisionHtml(row.decision_id)}">
                            <span class="analog-row-main">
                                <strong>${escapeDecisionHtml(symbol)}</strong>
                                <span class="stance-chip ${stance.cls}">${stance.label}</span>
                                <small>${escapeDecisionHtml(formatDecisionTime(row.ts))}</small>
                            </span>
                            <span class="analog-row-chips">
                                <span class="context-chip tone-neutral">${similarity}% similar</span>
                                ${responseChip}
                                ${outcomeChip}
                            </span>
                        </button>
                    `;
                }).join("")}
            </div>
            <p class="context-caption">Compared against ${data.compared_count} historical decision(s) with a comparable fingerprint.</p>
        `;

        host.querySelectorAll(".analog-row").forEach(row => {
            row.addEventListener("click", () => {
                const id = row.getAttribute("data-decision-id");
                if (id && id !== activeDecisionId) selectBriefing(id);
            });
        });
    }

    async function loadDecisionAnalogs(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/analogs`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeAnalogs = response && response.data;
            renderAnalogsPanel(activeAnalogs);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load analogs for ${decisionId}`, err);
            const host = document.getElementById("decision-analogs-panel");
            if (host) host.innerHTML = '<div class="context-caption">Unable to load similar setups.</div>';
        }
    }

    function formatCounterfactualNumber(value) {
        const num = Number(value);
        return Number.isFinite(num) ? num.toFixed(2) : "—";
    }

    function renderCounterfactualPanel(data) {
        const host = document.getElementById("decision-counterfactual-panel");
        if (!host) return;
        if (!data) {
            host.innerHTML = '<div class="context-caption">Unable to compute the gap to TRADE.</div>';
            return;
        }

        if (data.is_trade) {
            host.innerHTML = `
                <div class="counterfactual-cleared">
                    <span class="context-chip tone-good"><i class="fa-solid fa-check"></i> All gates cleared</span>
                    <p class="context-caption">${escapeDecisionHtml(data.summary)}</p>
                </div>
            `;
            return;
        }

        const scoreRow = data.score_current !== null && data.score_current !== undefined
            ? `
                <div class="counterfactual-row">
                    <span class="counterfactual-row-label">Composite score</span>
                    <span class="counterfactual-row-values">
                        <strong>${formatCounterfactualNumber(data.score_current)}</strong>
                        <small>/ ${formatCounterfactualNumber(data.score_required)} required</small>
                    </span>
                    ${data.score_gap !== null && data.score_gap !== undefined && Number(data.score_gap) > 0
                        ? `<span class="context-chip tone-bad">+${formatCounterfactualNumber(data.score_gap)} short</span>`
                        : `<span class="context-chip tone-good">met</span>`}
                </div>
            `
            : "";

        const gateRows = (Array.isArray(data.gates) ? data.gates : []).map(gate => {
            const hasNumbers = gate.current !== null && gate.current !== undefined
                && gate.required !== null && gate.required !== undefined;
            const gapPositive = gate.gap !== null && gate.gap !== undefined && Number(gate.gap) > 0;
            return `
                <div class="counterfactual-row">
                    <span class="counterfactual-row-label">${escapeDecisionHtml(friendlyLabel(gate.gate))}</span>
                    ${hasNumbers
                        ? `<span class="counterfactual-row-values">
                            <strong>${formatCounterfactualNumber(gate.current)}</strong>
                            <small>vs ${formatCounterfactualNumber(gate.required)} required</small>
                        </span>`
                        : `<span class="counterfactual-row-values"><small>${escapeDecisionHtml(gate.detail)}</small></span>`}
                    ${hasNumbers
                        ? (gapPositive
                            ? `<span class="context-chip tone-bad">gap ${formatCounterfactualNumber(gate.gap)}</span>`
                            : `<span class="context-chip tone-good">met</span>`)
                        : `<span class="context-chip tone-unknown">blocked</span>`}
                </div>
            `;
        }).join("");

        host.innerHTML = `
            <div class="counterfactual-body">
                ${scoreRow}
                ${gateRows}
                <p class="counterfactual-summary">${escapeDecisionHtml(data.summary)}</p>
            </div>
        `;
    }

    async function loadDecisionCounterfactual(decisionId) {
        try {
            const response = await apiRequest(
                `/api/v1/decisions/${encodeURIComponent(decisionId)}/counterfactual`,
                { skipToast: true }
            );
            if (activeDecisionId !== decisionId) return;
            activeCounterfactual = response && response.data;
            renderCounterfactualPanel(activeCounterfactual);
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load counterfactual for ${decisionId}`, err);
            const host = document.getElementById("decision-counterfactual-panel");
            if (host) host.innerHTML = '<div class="context-caption">Unable to compute the gap to TRADE.</div>';
        }
    }

    function renderDecisionTimeline(decision) {
        const host = document.getElementById("decision-history-timeline");
        if (!host || !decision || !decision.metadata) return;
        const instrument = String(decision.metadata.instrument_id || "").toUpperCase();
        const bare = instrument.split(":").pop();
        const rows = allTraceDecisionsList
            .filter(item => {
                const candidate = String(item?.metadata?.instrument_id || "").toUpperCase();
                return candidate === instrument || candidate.split(":").pop() === bare;
            })
            .sort((a, b) => new Date(b.metadata.ts || 0) - new Date(a.metadata.ts || 0))
            .slice(0, 8);
        if (!rows.length) {
            host.innerHTML = '<div class="text-muted">No persisted decision history.</div>';
            return;
        }
        host.innerHTML = rows.map(item => {
            const meta = item.metadata || {};
            const current = meta.decision_id === decision.metadata.decision_id;
            const stance = decisionStance(meta.decision_type, meta.direction);
            return `
                <button type="button" class="decision-timeline-row ${current ? "current" : ""}"
                        data-decision-id="${escapeDecisionHtml(meta.decision_id || "")}">
                    <span class="decision-timeline-dot"></span>
                    <span>
                        <strong>${escapeDecisionHtml(formatDecisionTime(meta.ts))}</strong>
                        <small>${escapeDecisionHtml(stance.label)} · ${escapeDecisionHtml(meta.decision_type || "UNKNOWN")}</small>
                    </span>
                    ${current ? '<em>Current</em>' : ""}
                </button>
            `;
        }).join("");
        host.querySelectorAll(".decision-timeline-row").forEach(row => {
            row.addEventListener("click", () => {
                const id = row.getAttribute("data-decision-id");
                if (id && id !== activeDecisionId) selectBriefing(id);
            });
        });
    }

    function renderDecisionBrief(decision) {
        if (!decisionBriefBody || !decision || !decision.metadata) return;
        activeDecisionData = decision;
        const meta = decision.metadata;
        const rawSymbol = meta.instrument_id || "INDEX";
        const symbol = rawSymbol.includes(":") ? rawSymbol.split(":").pop() : rawSymbol;
        const stance = decisionStance(meta.decision_type, meta.direction);
        const gates = decision.analysis && Array.isArray(decision.analysis.gate_results)
            ? decision.analysis.gate_results
            : [];
        const summary = formatDecisionSummary(decision.explanation, meta.decision_type, gates);

        if (decisionBriefTitle) {
            decisionBriefTitle.textContent = symbol;
            decisionBriefTitle.title = rawSymbol;
        }
        if (decisionBriefAsOf) decisionBriefAsOf.textContent = `As of ${formatDecisionTime(meta.ts)}`;
        if (decisionBriefStanceChip) {
            decisionBriefStanceChip.innerHTML = `<span class="stance-chip ${stance.cls}">${stance.label}</span>`;
        }
        if (decisionBriefTypeChip) {
            decisionBriefTypeChip.innerHTML = decisionTypeBadge(meta.decision_type);
        }
        if (decisionBriefGauges) decisionBriefGauges.hidden = false;
        if (decisionBriefTabstrip) decisionBriefTabstrip.hidden = false;
        if (decisionBriefActionbar) decisionBriefActionbar.hidden = false;
        resetCockpitGauges();
        resetActionButtons();

        const heroRR = document.getElementById("hero-rr-value");
        if (heroRR) {
            const rr = decision.trade_plan ? Number(decision.trade_plan.risk_reward) : NaN;
            heroRR.textContent = Number.isFinite(rr) ? `${rr.toFixed(1)} : 1` : "—";
        }

        const gateRows = gates.length
            ? gates.map(gate => `
                <div class="decision-gate-row">
                    <i class="fa-solid ${gate.passed ? "fa-circle-check pass" : "fa-circle-xmark fail"}"></i>
                    <span class="decision-gate-name">${escapeDecisionHtml(friendlyGateName(gate.gate))}</span>
                    <span class="decision-gate-detail">${escapeDecisionHtml(sanitizeNumericText(gate.detail || "No rationale recorded"))}</span>
                </div>
            `).join("")
            : '<div class="text-muted">No gate results were persisted for this decision.</div>';

        // Safety checklist summary (owner audit #20) — a reassuring headline
        // over the same gate results, not a separate computation.
        const gatesFailed = gates.filter(g => g && g.passed === false).length;
        const gatesSummary = !gates.length
            ? ""
            : gatesFailed === 0
                ? '<div class="safety-checklist-summary pass"><i class="fa-solid fa-shield-halved"></i> All safety checks passed</div>'
                : `<div class="safety-checklist-summary fail"><i class="fa-solid fa-shield-halved"></i> Blocked on ${gatesFailed} of ${gates.length} safety checks</div>`;

        const references = ["score_ref", "confidence_ref", "risk_ref"]
            .map(key => decision.analysis ? decision.analysis[key] : null)
            .filter(Boolean)
            .map(ref => `
                <span class="provenance-chip" title="${escapeDecisionHtml(ref.id)}">
                    ${escapeDecisionHtml(ref.resource_type)} · ${escapeDecisionHtml(ref.id)}
                </span>
            `).join("");

        const paneActive = name => (activeBriefTab === name ? " active" : "");

        decisionBriefBody.innerHTML = `
            <section class="decision-brief-hero">
                <div class="decision-banner ${stance.cls}">
                    <div class="decision-banner-head">
                        <span class="decision-banner-label">ATHENA Recommendation</span>
                        <span class="decision-banner-stance">${stance.label}</span>
                    </div>
                    <p class="decision-banner-reason" title="${escapeDecisionHtml(summary.headline)}">${escapeDecisionHtml(summary.headline)}</p>
                </div>
                <div id="decision-executive-summary" class="executive-summary">
                    <div class="decision-depth-loading">
                        <i class="fa-solid fa-circle-notch fa-spin"></i> Building summary…
                    </div>
                </div>
                <div class="decision-brief-section decision-timeline-section">
                    <div class="decision-brief-section-header">
                        <h4>Decision timeline</h4>
                        <span class="decision-timeline-hint">Click an entry to view ATHENA's assessment at that point in time</span>
                    </div>
                    <div id="decision-history-timeline" class="decision-history-timeline"></div>
                </div>
            </section>

            <div class="tabpane${paneActive("setup")}" id="brief-pane-setup" data-brief-pane="setup">
                <section class="decision-brief-section">
                    <h4>Universe eligibility</h4>
                    <div id="decision-eligibility-depth" class="decision-depth-loading">
                        <i class="fa-solid fa-circle-notch fa-spin"></i> Loading persisted assessment…
                    </div>
                </section>

                ${renderTradePlan(decision.trade_plan, meta.decision_type, meta.direction)}

                <section class="decision-brief-section decision-chart-section">
                    <div class="decision-brief-section-header">
                        <h4>Intraday price context · 5 minute</h4>
                        <span id="decision-chart-status" class="chart-freshness-badge no_data">LOADING</span>
                    </div>
                    <p id="decision-chart-meta" class="decision-chart-meta">Loading persisted OHLCV…</p>
                    <div id="decision-chart-warning" class="decision-chart-warning" hidden></div>
                    <div id="decision-chart-canvas" class="decision-chart-canvas"></div>
                    <div class="decision-chart-legend">
                        <span><i class="legend-box entry"></i> Entry zone</span>
                        <span><i class="legend-line stop"></i> Invalidation</span>
                        <span><i class="legend-line target"></i> Targets</span>
                        <span><i class="legend-line ma"></i> Moving average</span>
                        <span><i class="legend-box atr"></i> ATR band</span>
                        <span><i class="legend-box volume"></i> Volume</span>
                    </div>
                </section>
            </div>

            <div class="tabpane${paneActive("analysis")}" id="brief-pane-analysis" data-brief-pane="analysis">
                <section class="decision-brief-section">
                    <h4>Score · confidence · risk</h4>
                    <p class="analysis-section-intro">
                        Read the three headline assessments first. Expand a category, then a component,
                        only when you need the recorded rationale and inputs.
                    </p>
                    <div id="decision-analysis-depth" class="analysis-depth-grid">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Loading analytical artifacts…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section" id="decision-counterfactual-section">
                    <h4>Why not a trade?</h4>
                    <p class="analysis-section-intro">
                        Exact arithmetic over persisted values vs. current config thresholds —
                        never a recomputed score, confidence, or risk.
                    </p>
                    <div id="decision-counterfactual-panel" class="decision-counterfactual-panel">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Computing gap to TRADE…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section">
                    <h4>Safety &amp; quality gates</h4>
                    ${gatesSummary}
                    <div class="decision-gates-list">${gateRows}</div>
                </section>
            </div>

            <div class="tabpane${paneActive("context")}" id="brief-pane-context" data-brief-pane="context">
                <section class="decision-brief-section">
                    <h4>Session &amp; market context</h4>
                    <p class="analysis-section-intro">
                        Trading-day session state, persisted regime/market-health, and owner-curated
                        research links. No news ingestion, no generated rationale.
                    </p>
                    <div id="decision-context-lane" class="decision-context-lane">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Loading session &amp; market context…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section">
                    <h4>Analytical provenance</h4>
                    <div class="decision-provenance">
                        ${references || '<span class="text-muted">No analytical references persisted.</span>'}
                    </div>
                </section>
            </div>

            <div class="tabpane${paneActive("response")}" id="brief-pane-response" data-brief-pane="response">
                <section class="decision-brief-section">
                    <h4>Your response</h4>
                    <p class="analysis-section-intro">
                        Every recommendation gets a recorded human response — nothing is
                        unrecorded. This is the only source of real feedback the AI Playbook
                        Diagnostics learning loop has.
                    </p>
                    <div id="decision-journal-panel" class="decision-journal-panel">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Loading your response…
                        </div>
                    </div>
                </section>

                <section class="decision-brief-section">
                    <h4>Similar past setups</h4>
                    <p class="analysis-section-intro">
                        Deterministic nearest-neighbor retrieval by score/confidence/risk
                        fingerprint across your persisted decision history — factual retrieval
                        only, nothing generated.
                    </p>
                    <div id="decision-analogs-panel" class="decision-analogs-panel">
                        <div class="decision-depth-loading">
                            <i class="fa-solid fa-circle-notch fa-spin"></i> Finding similar setups…
                        </div>
                    </div>
                </section>
            </div>

            <p class="decision-brief-footnote">
                Dismiss only hides this symbol in this browser until the next IST day.
                Removing a candidate stops future validation only. Decision history and replay evidence are never deleted.
            </p>
        `;

        renderDecisionTimeline(decision);
        renderExecutiveSummary();
        loadDecisionDepth(meta.decision_id);
        loadDecisionContext(meta.decision_id);
        loadDecisionChart(rawSymbol, decision.trade_plan, meta.decision_id);
        loadJournalPanel(meta.decision_id);
        loadDecisionAnalogs(meta.decision_id);
        loadDecisionCounterfactual(meta.decision_id);
        loadDecisionPlanFreshness(meta.decision_id);
        setHeaderRevalidateEnabled(true);
    }

    async function loadDecisionDetail(decisionId) {
        if (!decisionBriefBody) return;
        decisionBriefBody.innerHTML =
            '<div class="decision-brief-empty"><i class="fa-solid fa-circle-notch fa-spin"></i><strong>Loading decision brief…</strong></div>';
        try {
            const res = await apiRequest(`/api/v1/decisions/${decisionId}`);
            if (activeDecisionId !== decisionId) return;
            if (res && res.status === "success") {
                renderDecisionBrief(res.data);
            }
        } catch (err) {
            if (activeDecisionId !== decisionId) return;
            console.error(`Failed to load decision detail for ${decisionId}`, err);
            renderDecisionBriefEmpty(
                "Decision brief unavailable",
                "The decision list remains available. Refresh or select another symbol."
            );
        }
    }

    // Priority order always — Trade first, then Watch, then No trade, then
    // Insufficient data — regardless of timestamp (owner: 2026-07-25). Any
    // decision_type not in this list still gets its own carousel, appended
    // after these four, so nothing is ever silently hidden.
    const DECISION_CAROUSEL_SECTIONS = [
        { type: "TRADE", label: "Trade", dot: "var(--success)", hint: "acted on now" },
        { type: "WATCH", label: "Watch", dot: "var(--warning)", hint: "borderline, monitor" },
        { type: "NO_TRADE", label: "No trade", dot: "var(--text-muted)", hint: "nothing to act on" },
        { type: "INSUFFICIENT_DATA", label: "Insufficient data", dot: "var(--text-muted)", hint: "not enough data yet" },
    ];

    function decisionCardStanceColor(type) {
        const t = String(type || "").toUpperCase();
        if (t === "TRADE") return "var(--success)";
        if (t === "WATCH") return "var(--warning)";
        return "var(--text-muted)";
    }

    function renderDeckCard(d) {
        const rawSym = d.metadata.instrument_id || "INDEX";
        const symbol = rawSym.includes(":") ? rawSym.split(":").pop() : rawSym;
        const type = d.metadata.decision_type;
        const dateObj = new Date(d.metadata.ts);
        const dateStr = dateObj.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
        const gates = (d.analysis && d.analysis.gate_results) ? d.analysis.gate_results : [];
        const failed = gates.filter(g => g && g.passed === false);
        const score = decisionScoreValue(d);
        const scoreLabel = score >= 0 ? score.toFixed(1) : "—";
        const noteText = gates.length === 0
            ? "no gates recorded"
            : (failed.length ? `${failed.length} of ${gates.length} gates open` : "all gates cleared");
        const noteTitle = failed.length
            ? `Needs ${failed.map(g => friendlyGateName(g.gate)).join(", ")}`
            : noteText;
        // Quick-glance severity without a hover — many cards otherwise show
        // the same generic "N of M gates open" in identical muted gray.
        const noteTone = gates.length === 0
            ? ""
            : (failed.length === 0 ? "tone-good-text" : (failed.length <= 2 ? "tone-warn-text" : "tone-bad-text"));

        const card = document.createElement("div");
        card.className = "deck-card";
        card.style.setProperty("--stance-color", decisionCardStanceColor(type));
        card.setAttribute("data-id", d.metadata.decision_id);
        card.innerHTML = `
            <div class="deck-top">
                <span class="deck-sym" title="${escapeDecisionHtml(rawSym)}">${escapeDecisionHtml(symbol)}</span>
                <button class="deck-dismiss-btn" type="button"
                    title="Hide ${escapeDecisionHtml(symbol)} from Today's Decisions until tomorrow"
                    aria-label="Dismiss ${escapeDecisionHtml(symbol)} for today">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="deck-mid">
                <span class="deck-score">${escapeDecisionHtml(scoreLabel)}</span>
                <span class="deck-time">${escapeDecisionHtml(dateStr)}</span>
            </div>
            <div class="deck-note ${noteTone}" title="${escapeDecisionHtml(noteTitle)}">${escapeDecisionHtml(noteText)}</div>
        `;

        card.addEventListener("click", () => {
            selectBriefing(d.metadata.decision_id);
        });
        card.querySelector(".deck-dismiss-btn")?.addEventListener("click", event => {
            event.stopPropagation();
            dismissDecisionForToday(d);
        });
        return card;
    }

    function renderDecisionCarousels(decisions) {
        if (!decisionsCarouselContainer) return;

        const summaryEl = document.getElementById("decisions-summary-strip");
        if (summaryEl) {
            const dismissedCount = traceDecisionsList.filter(
                d => dismissedDecisionSymbols.has(decisionInstrumentKey(d))
            ).length;
            const counts = {};
            decisions.forEach(d => {
                const t = (d.metadata && d.metadata.decision_type) || "OTHER";
                counts[t] = (counts[t] || 0) + 1;
            });
            if (decisions.length === 0) {
                summaryEl.textContent = traceDecisionsList.length
                    ? "No visible decisions — restore dismissed symbols or change filters."
                    : "No decisions yet — run ./athena-daily smoke after Kite auth.";
            } else {
                summaryEl.innerHTML =
                    `<strong>${decisions.length}</strong> symbols (latest each) · ` +
                    `BUY/SELL ${counts.TRADE || 0} · HOLD ${counts.WATCH || 0} · ` +
                    `PASS ${counts.NO_TRADE || 0} · other ${
                        decisions.length - (counts.TRADE || 0) - (counts.WATCH || 0) - (counts.NO_TRADE || 0)
                    }. ` +
                    `<span class="text-muted">HOLD = interesting but blocked; PASS = below watch score. Grouped by outcome below — Trade first, always.</span>`;
            }
            if (dismissedCount > 0) {
                summaryEl.innerHTML +=
                    ` · <strong>${dismissedCount}</strong> hidden today ` +
                    `<button id="restore-dismissed-decisions" class="restore-dismissed-btn" type="button">Restore</button>`;
                document.getElementById("restore-dismissed-decisions")
                    ?.addEventListener("click", restoreDismissedDecisions);
            }
        }

        decisionsCarouselContainer.innerHTML = "";

        if (decisions.length === 0) {
            decisionsCarouselContainer.innerHTML = '<div class="text-muted text-center" style="padding: 24px;">No decisions match query.</div>';
            return;
        }

        const byType = new Map();
        decisions.forEach(d => {
            const t = String((d.metadata && d.metadata.decision_type) || "OTHER").toUpperCase();
            if (!byType.has(t)) byType.set(t, []);
            byType.get(t).push(d);
        });

        const knownTypes = new Set(DECISION_CAROUSEL_SECTIONS.map(s => s.type));
        const extraTypes = Array.from(byType.keys()).filter(t => !knownTypes.has(t));
        const sections = [
            ...DECISION_CAROUSEL_SECTIONS,
            ...extraTypes.map(t => ({ type: t, label: friendlyLabel(t), dot: "var(--text-muted)", hint: "" })),
        ];

        sections.forEach(section => {
            const rows = byType.get(section.type) || [];
            if (!rows.length) return;

            const sectionEl = document.createElement("div");
            sectionEl.className = "decision-carousel-section";
            sectionEl.setAttribute("data-section", section.type);
            sectionEl.innerHTML = `
                <div class="decision-carousel-head" data-toggle>
                    <span class="decision-carousel-dot" style="background: ${section.dot}"></span>
                    <span class="decision-carousel-name">${escapeDecisionHtml(section.label)}</span>
                    <span class="decision-carousel-count">${rows.length}</span>
                    ${section.hint ? `<span class="decision-carousel-hint">${escapeDecisionHtml(section.hint)}</span>` : ""}
                    <i class="fa-solid fa-chevron-down decision-carousel-chevron"></i>
                </div>
                <div class="decision-carousel-body">
                    <button class="decision-carousel-nav prev" type="button" aria-label="Scroll ${escapeDecisionHtml(section.label)} left">
                        <i class="fa-solid fa-chevron-left"></i>
                    </button>
                    <div class="decision-carousel-track"></div>
                    <button class="decision-carousel-nav next" type="button" aria-label="Scroll ${escapeDecisionHtml(section.label)} right">
                        <i class="fa-solid fa-chevron-right"></i>
                    </button>
                </div>
            `;

            const track = sectionEl.querySelector(".decision-carousel-track");
            const body = sectionEl.querySelector(".decision-carousel-body");
            rows.forEach(d => track.appendChild(renderDeckCard(d)));

            sectionEl.querySelector("[data-toggle]").addEventListener("click", () => {
                sectionEl.classList.toggle("collapsed");
            });
            sectionEl.querySelectorAll(".decision-carousel-nav").forEach(btn => {
                const dir = btn.classList.contains("prev") ? -1 : 1;
                btn.addEventListener("click", event => {
                    event.stopPropagation();
                    track.scrollBy({ left: dir * 340, behavior: "smooth" });
                });
            });

            decisionsCarouselContainer.appendChild(sectionEl);
            wireCarouselOverflow(body, track);
        });
    }

    // Nav arrows and edge fades only show when a row actually overflows, and
    // each arrow disables at its own end — no dead-end clicks, no "scroll
    // hint" shown when there's nothing to scroll (owner-reported).
    function wireCarouselOverflow(body, track) {
        const updateEdges = () => {
            const overflowing = track.scrollWidth > track.clientWidth + 1;
            body.classList.toggle("scrollable", overflowing);
            if (!overflowing) return;
            body.classList.toggle("at-start", track.scrollLeft <= 1);
            body.classList.toggle(
                "at-end", track.scrollLeft >= track.scrollWidth - track.clientWidth - 1
            );
        };
        track.addEventListener("scroll", updateEdges, { passive: true });
        new ResizeObserver(updateEdges).observe(track);
        updateEdges();
    }

    function selectBriefing(decisionId) {
        activeDecisionId = decisionId;
        // Clear cross-decision caches so a stale card never renders under a new symbol
        activeDepth = null;
        activeContextData = null;
        activeJournalEntry = null;
        activeTradeOutcome = null;
        activeAnalogs = null;
        activeCounterfactual = null;
        activePlanFreshness = null;
        // Toggle active card class across every outcome carousel, and bring the
        // selected card into view within its own track (graceful selection).
        if (decisionsCarouselContainer) {
            decisionsCarouselContainer.querySelectorAll(".deck-card").forEach(c => {
                const isActive = c.getAttribute("data-id") === decisionId;
                c.classList.toggle("active", isActive);
                if (isActive) {
                    c.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" });
                }
            });
        }

        // Load selected instrument brief and its independent reasoning trace.
        loadDecisionDetail(decisionId);
        loadDecisionTrace(decisionId);
    }

    async function loadDecisionTrace(decisionId) {
        try {
            const res = await apiRequest(`/api/v1/decisions/${decisionId}/trace`);
            if (activeDecisionId !== decisionId) return;
            if (res && res.status === "success") {
                activeTrace = res.data;
                renderTraceDAG(activeTrace);
            }
        } catch (err) {
            console.error(`Failed to load trace for ${decisionId}`, err);
        }
    }

    // Shared by the node list and the detail card header.
    const STAGE_ICONS = {
        "universe_ingest": "fa-globe",
        "technical_indicators": "fa-chart-area",
        "scoring_engine": "fa-calculator",
        "confidence_engine": "fa-shield-halved",
        "risk_assessment": "fa-triangle-exclamation",
        "quality_gates": "fa-circle-check",
        "final_decision": "fa-brain",
        "regime": "fa-chart-line",
        "market_health": "fa-heartbeat",
        "sector_health": "fa-industry",
        "evidence": "fa-layer-group",
        "score": "fa-calculator",
        "confidence": "fa-shield-halved",
        "risk": "fa-triangle-exclamation",
        "decision": "fa-brain",
        "trade_plan": "fa-list-check",
    };

    // Every stage maps to exactly one brief tab — the DAG points, the tab
    // explains. Covers both stage-id vocabularies seen in persisted traces.
    const STAGE_TAB_MAP = {
        universe_ingest: "setup",
        technical_indicators: "setup",
        trade_plan: "setup",
        scoring_engine: "analysis",
        confidence_engine: "analysis",
        risk_assessment: "analysis",
        quality_gates: "analysis",
        final_decision: "analysis",
        score: "analysis",
        confidence: "analysis",
        risk: "analysis",
        decision: "analysis",
        evidence: "analysis",
        regime: "context",
        market_health: "context",
        sector_health: "context",
    };

    function renderTraceDAG(trace) {
        if (!dagNodesContainer) return;
        dagNodesContainer.innerHTML = "";
        if (dagSvgLines) dagSvgLines.innerHTML = "";
        selectedStageId = null;

        if (!trace.stages || trace.stages.length === 0) {
            dagNodesContainer.innerHTML = '<div class="text-muted text-center" style="padding: 48px;">No stored reasoning trace for this decision yet.</div>';
            if (dagDetailsSummary) dagDetailsSummary.textContent = "Trace empty — decision has no persisted DecisionTrace stages.";
            return;
        }

        trace.stages.forEach((stage, idx) => {
            const node = document.createElement("div");
            node.className = "dag-node";
            node.setAttribute("data-stage", stage.stage_id);

            const icon = STAGE_ICONS[stage.stage_id] || "fa-circle-notch";
            const statusClass = stage.status.toLowerCase();

            node.innerHTML = `
                <i class="fa-solid ${icon} dag-node-icon"></i>
                <span class="dag-node-name" title="${escapeDecisionHtml(stage.name)}">${escapeDecisionHtml(stage.name)}</span>
                <span class="dag-node-status ${statusClass}">${stage.status}</span>
            `;

            node.addEventListener("click", () => {
                selectNode(stage.stage_id, { userInitiated: true });
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

        // Highlight the first node by default, but never jump tabs for it —
        // only an actual click should navigate away from whichever tab the
        // trader is currently comparing across decisions (owner-reported:
        // picking a new decision was silently yanking them back to Context).
        if (trace.stages.length > 0) {
            selectNode(trace.stages[0].stage_id, { userInitiated: false });
        }
    }

    function selectNode(stageId, { userInitiated = false } = {}) {
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
            const tab = STAGE_TAB_MAP[stage.stage_id];
            if (userInitiated && tab) switchBriefTab(tab);
        }
    }

    function renderStageProvenance(stage) {
        if (!dagDetailsGrid) return;
        const refIds = Array.isArray(stage.details && stage.details.ref_ids)
            ? stage.details.ref_ids
            : [];
        if (!refIds.length) {
            dagDetailsGrid.innerHTML = '<div class="text-muted" style="grid-column: 1/-1; font-size: 0.72rem;">No provenance references captured.</div>';
            return;
        }
        const label = refIds.length === 1 ? "reference" : "references";
        const shown = refIds.length > 2
            ? `${refIds.slice(0, 2).join(", ")} +${refIds.length - 2} more`
            : refIds.join(", ");
        dagDetailsGrid.innerHTML = `
            <div class="strategy-criteria-item" style="grid-column: 1/-1;">
                <span class="criteria-label">${escapeDecisionHtml(label)}</span>
                <span class="criteria-value" title="${escapeDecisionHtml(refIds.join(", "))}">${escapeDecisionHtml(shown)}</span>
            </div>
        `;
    }

    // Full detail for every stage already lives in one of the four brief tabs
    // (Setup/Analysis/Context) — this panel shows only what isn't duplicated
    // there: the stage's own status and its provenance references.
    function showStageDetails(stage) {
        if (!dagDetailsPanel) return;
        selectedStageId = stage.stage_id;

        const icon = STAGE_ICONS[stage.stage_id] || "fa-circle-notch";
        dagDetailsTitle.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeDecisionHtml(stage.name)}</span>`;
        dagDetailsStatus.className = `badge ${stage.status.toLowerCase()}`;
        dagDetailsStatus.textContent = stage.status;

        const tab = STAGE_TAB_MAP[stage.stage_id];
        dagDetailsSummary.innerHTML = tab
            ? `<p class="context-caption">Full detail lives in the <strong>${escapeDecisionHtml(friendlyLabel(tab))}</strong> tab — opened automatically.</p>`
            : `<p class="context-caption">${escapeDecisionHtml(stage.summary || "")}</p>`;

        renderStageProvenance(stage);
        dagDetailsPanel.style.display = "block";
    }

    const BRIEF_TAB_NAMES = new Set(["setup", "analysis", "context", "response"]);

    // Sticky-cockpit tab strip. Deliberately not reset when the selected
    // decision changes (selectBriefing) — flipping through several decisions
    // to compare the same aspect should keep you on that aspect.
    function switchBriefTab(name) {
        if (!BRIEF_TAB_NAMES.has(name)) return;
        activeBriefTab = name;
        if (decisionBriefTabstrip) {
            decisionBriefTabstrip.querySelectorAll(".brief-tab").forEach(btn => {
                btn.classList.toggle("active", btn.getAttribute("data-brief-tab") === name);
            });
        }
        if (decisionBriefBody) {
            decisionBriefBody.querySelectorAll(".tabpane").forEach(pane => {
                pane.classList.toggle("active", pane.getAttribute("data-brief-pane") === name);
            });
        }
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

    // Search / filter / sort for Today's Decisions
    const wireDecisionsControls = () => {
        ["decisions-filter-stance", "decisions-filter-type", "decisions-sort"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener("change", applyDecisionsView);
        });
        if (briefingSearch) {
            briefingSearch.addEventListener("input", applyDecisionsView);
        }
    };
    wireDecisionsControls();

    // Header Re-validate — always visible next to the "as of" timestamp,
    // rather than buried at the bottom of the brief (owner feedback).
    function setHeaderRevalidateEnabled(enabled) {
        if (!decisionBriefRevalidateHeader) return;
        decisionBriefRevalidateHeader.disabled = !enabled;
    }

    decisionBriefRevalidateHeader?.addEventListener("click", event => {
        const instrumentId = activeDecisionData && activeDecisionData.metadata
            ? activeDecisionData.metadata.instrument_id
            : null;
        if (!instrumentId) return;
        const bareSymbol = String(instrumentId).replace(/^NSE:|^BSE:/, "");
        validateSymbolsNow([bareSymbol], { button: event.currentTarget, refreshDecisions: true });
    });

    // Tab strip and action bar live in the static sticky header (not rebuilt
    // per decision), so they're wired exactly once here and read
    // activeDecisionData/activeDecisionId at click time.
    decisionBriefTabstrip?.querySelectorAll(".brief-tab").forEach(btn => {
        btn.addEventListener("click", () => switchBriefTab(btn.getAttribute("data-brief-tab")));
    });

    document.getElementById("decision-brief-market")?.addEventListener("click", () => {
        switchTab("market");
    });
    document.getElementById("decision-brief-dismiss")?.addEventListener("click", () => {
        if (activeDecisionData) dismissDecisionForToday(activeDecisionData);
    });
    document.getElementById("decision-brief-remove-candidate")?.addEventListener("click", async event => {
        const instrumentId = activeDecisionData && activeDecisionData.metadata
            ? activeDecisionData.metadata.instrument_id
            : null;
        if (!instrumentId) return;
        const bareSymbol = String(instrumentId).replace(/^NSE:|^BSE:/, "");
        const removed = await removeCandidateNow(bareSymbol, { button: event.currentTarget });
        if (removed) {
            event.currentTarget.disabled = true;
            event.currentTarget.querySelector("i").className = "fa-solid fa-check";
            event.currentTarget.querySelector("span").textContent = "Removed";
        }
    });
    document.getElementById("decision-brief-export")?.addEventListener("click", event => {
        const decisionId = activeDecisionData && activeDecisionData.metadata
            ? activeDecisionData.metadata.decision_id
            : null;
        if (!decisionId) return;
        exportDecisionBrief(decisionId, event.currentTarget);
    });

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
    const opsRestoreGateStatus = document.getElementById("ops-restore-gate-status");
    const opsLastRestore = document.getElementById("ops-last-restore");

    function isRestoreConfirmUnlocked() {
        return !!(opsRestoreConfirm && opsRestoreConfirm.value.trim() === "CONFIRM");
    }

    function updateRestoreGateStatus() {
        const unlocked = isRestoreConfirmUnlocked();
        if (opsRestoreGateStatus) {
            opsRestoreGateStatus.className = `ops-restore-gate-status ${unlocked ? "unlocked" : "locked"}`;
            opsRestoreGateStatus.textContent = unlocked
                ? "Restore unlocked — click Restore on a backup row above."
                : "Restore locked — buttons stay disabled until CONFIRM matches exactly.";
        }
        document.querySelectorAll(".ops-restore-btn").forEach(btn => {
            btn.disabled = !unlocked;
            btn.title = unlocked
                ? "Overwrite live database from this backup"
                : "Type CONFIRM below to unlock";
        });
    }

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
            const token = getAccessToken();
            const streamUrl = token
                ? `/api/v1/ops/stream?access_token=${encodeURIComponent(token)}`
                : "/api/v1/ops/stream";
            opsEventSource = new EventSource(streamUrl);
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
            updateRestoreGateStatus();
            return;
        }

        const confirmOk = isRestoreConfirmUnlocked();
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
                    <button class="btn btn-sm btn-outline ops-restore-btn" type="button" data-id="${b.backup_id}" ${confirmOk ? "" : "disabled"}>
                        Restore
                    </button>
                </td>
            `;
            const btn = row.querySelector(".ops-restore-btn");
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                restoreOpsBackup(b.backup_id);
            });
            opsBackupsBody.appendChild(row);
        });
        updateRestoreGateStatus();
    }

    async function restoreOpsBackup(backupId) {
        if (!isRestoreConfirmUnlocked()) {
            showToast("Type CONFIRM exactly, then click Restore on a backup row", "warning");
            return;
        }
        try {
            showToast(`Restoring ${backupId}…`, "info");
            const res = await apiRequest(`/api/v1/ops/backups/${encodeURIComponent(backupId)}/restore`, {
                method: "POST",
                body: JSON.stringify({ confirmation: "CONFIRM" }),
            });
            if (res && res.status === "success") {
                const ok = res.data.ok;
                const counts = res.data.record_counts || {};
                const total = Object.values(counts).reduce((a, b) => a + Number(b || 0), 0);
                const detail = ok
                    ? `Restored ${backupId} → live DB (${total} records). Identical empty backups can look unchanged.`
                    : `Restore finished with issues: ${(res.data.issues || []).join("; ") || "see details"}`;
                showToast(detail, ok ? "success" : "warning");
                if (opsLastRestore) {
                    opsLastRestore.textContent = `${new Date().toLocaleTimeString("en-IN")} — ${detail}`;
                }
                opsRestoreConfirm.value = "";
                updateRestoreGateStatus();
                await loadOpsBackups();
            }
        } catch (err) {
            console.error("Restore failed", err);
            showToast("Restore failed — check toast/network details", "danger");
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
            opsRestoreConfirm.addEventListener("input", updateRestoreGateStatus);
            opsRestoreConfirm.addEventListener("keyup", updateRestoreGateStatus);
            opsRestoreConfirm.addEventListener("change", updateRestoreGateStatus);
        }
        updateRestoreGateStatus();
    }

    // Escape closes any open modal
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeAllModals();
        }
    });

    // Initialize Startup Flows (auth gate first)
    bootstrapSession();
});
