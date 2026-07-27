

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