

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
            if (typeof setAdvisorPulse === "function") {
                setAdvisorPulse("Kite reconnect required · Live quotes may be unavailable", "warning", 0);
            }
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
