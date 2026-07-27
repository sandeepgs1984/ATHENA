

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

    function updateTelemetry(reqId, corrId, latency) {
        state.telemetry = { requestId: reqId, correlationId: corrId, latencyMs: latency };
        
        // Update DOM
        reqIdElement.textContent = reqId.slice(0, 8) + "...";
        reqIdElement.title = reqId;
        corrIdElement.textContent = corrId.slice(0, 8) + "...";
        corrIdElement.title = corrId;
        latencyElement.textContent = `${latency} ms`;
    }