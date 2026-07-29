

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

    function advisorLatencyTone(latency) {
        const ms = Number(latency);
        if (!Number.isFinite(ms)) return "neutral";
        if (ms >= 2500) return "danger";
        if (ms >= 1000) return "warning";
        return "good";
    }

    function setAdvisorPulse(message, tone = "neutral", priority = 0) {
        if (Number(priority) < Number(state.advisorPulse.priority || 0)) return;
        const text = String(message || "").trim()
            || "ATHENA advisor ready · Select a symbol to review actionability";
        state.advisorPulse = { message: text, tone, priority };
        if (advisorPulseMessage) advisorPulseMessage.textContent = text;
        if (advisorPulse) {
            advisorPulse.className = `advisor-pulse tone-${tone}`;
            advisorPulse.title = text;
        }
    }

    function clearAdvisorPulsePriority(priority = 1) {
        if (Number(state.advisorPulse.priority || 0) >= Number(priority)) {
            state.advisorPulse.priority = 0;
        }
    }

    function closeDiagnosticsPopover() {
        if (!diagnosticsPopover || !diagnosticsToggle) return;
        diagnosticsPopover.hidden = true;
        diagnosticsToggle.setAttribute("aria-expanded", "false");
    }

    diagnosticsToggle?.addEventListener("click", event => {
        event.stopPropagation();
        if (!diagnosticsPopover) return;
        const opening = diagnosticsPopover.hidden;
        diagnosticsPopover.hidden = !opening;
        diagnosticsToggle.setAttribute("aria-expanded", opening ? "true" : "false");
    });

    document.addEventListener("click", event => {
        if (diagnosticsPopover && !diagnosticsPopover.hidden
            && !diagnosticsPopover.contains(event.target)
            && event.target !== diagnosticsToggle) {
            closeDiagnosticsPopover();
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") closeDiagnosticsPopover();
    });

    function updateTelemetry(reqId, corrId, latency) {
        state.telemetry = { requestId: reqId, correlationId: corrId, latencyMs: latency };
        
        if (reqIdElement) {
            reqIdElement.textContent = reqId.slice(0, 8) + "...";
            reqIdElement.title = reqId;
        }
        if (corrIdElement) {
            corrIdElement.textContent = corrId.slice(0, 8) + "...";
            corrIdElement.title = corrId;
        }
        if (latencyElement) {
            latencyElement.textContent = `${latency} ms`;
            latencyElement.className = `telemetry-value font-mono latency-${advisorLatencyTone(latency)}`;
        }
        if (diagnosticsToggle) {
            diagnosticsToggle.classList.remove("latency-good", "latency-warning", "latency-danger", "latency-neutral");
            diagnosticsToggle.classList.add(`latency-${advisorLatencyTone(latency)}`);
            diagnosticsToggle.title = `Diagnostics · last request ${latency} ms`;
        }
    }
