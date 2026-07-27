

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