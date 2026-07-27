

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