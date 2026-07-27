

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