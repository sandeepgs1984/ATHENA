
    const myPortfolioFileInput = document.getElementById("my-portfolio-file");
    const myPortfolioAlert = document.getElementById("my-portfolio-alert");
    const myPortfolioSelectedFile = document.getElementById("my-portfolio-selected-file");
    const myPortfolioUploadState = document.getElementById("my-portfolio-upload-state");
    const myPortfolioPreview = document.getElementById("my-portfolio-preview");
    const myPortfolioConfirm = document.getElementById("my-portfolio-confirm");
    const myPortfolioCancelPreview = document.getElementById("my-portfolio-cancel-preview");
    const myPortfolioSync = document.getElementById("my-portfolio-sync");
    const myPortfolioHoldingCount = document.getElementById("my-portfolio-holding-count");
    const myPortfolioTotalInvestment = document.getElementById("my-portfolio-total-investment");
    const myPortfolioCurrentValue = document.getElementById("my-portfolio-current-value");
    const myPortfolioTotalPnl = document.getElementById("my-portfolio-total-pnl");
    const myPortfolioTotalPnlDetail = document.getElementById("my-portfolio-total-pnl-detail");
    const myPortfolioLatestImport = document.getElementById("my-portfolio-latest-import");
    const myPortfolioLatestImportDetail = document.getElementById("my-portfolio-latest-import-detail");
    const myPortfolioLastSynced = document.getElementById("my-portfolio-last-synced");
    const myPortfolioMarketDataThrough = document.getElementById("my-portfolio-market-data-through");
    const myPortfolioPreviewTotal = document.getElementById("my-portfolio-preview-total");
    const myPortfolioPreviewValid = document.getElementById("my-portfolio-preview-valid");
    const myPortfolioPreviewInvalid = document.getElementById("my-portfolio-preview-invalid");
    const myPortfolioPreviewUnresolved = document.getElementById("my-portfolio-preview-unresolved");
    const myPortfolioPreviewAmbiguous = document.getElementById("my-portfolio-preview-ambiguous");
    const myPortfolioPreviewDuplicates = document.getElementById("my-portfolio-preview-duplicates");
    const myPortfolioPreviewRows = document.getElementById("my-portfolio-preview-rows");
    const myPortfolioReconciliationSummary = document.getElementById("my-portfolio-reconciliation-summary");
    const myPortfolioReconciliationRows = document.getElementById("my-portfolio-reconciliation-rows");
    const myPortfolioHoldingsRows = document.getElementById("my-portfolio-holdings-rows");
    const myPortfolioHistoryRows = document.getElementById("my-portfolio-history-rows");

    const myPortfolioState = {
        preview: null,
        selectedFile: null,
        loading: false,
        previewing: false,
        confirming: false,
        syncing: false,
        syncPollTimer: null,
        syncRun: null,
        snapshot: null,
        holdings: [],
        imports: [],
    };

    function escapeMyPortfolioHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatMyPortfolioMoney(value) {
        const amount = Number(value);
        if (!Number.isFinite(amount)) return "₹ —";
        return `₹ ${amount.toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    function formatMyPortfolioNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return "—";
        return number.toLocaleString("en-IN");
    }

    function formatMyPortfolioPct(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return "—";
        return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
    }

    function formatMyPortfolioTime(value) {
        if (!value) return "—";
        return formatDecisionTime(value);
    }

    function bareMyPortfolioSymbol(instrumentId) {
        const raw = String(instrumentId || "");
        return raw.includes(":") ? raw.split(":").pop() : raw;
    }

    function myPortfolioStatus(label, tone = "neutral", icon = "fa-circle-info") {
        return `<span class="my-portfolio-status ${tone}"><i class="fa-solid ${icon}" aria-hidden="true"></i>${escapeMyPortfolioHtml(label)}</span>`;
    }

    function myPortfolioSnapshotIsStale(snapshot = myPortfolioState.snapshot) {
        return snapshot?.currentness === "STALE_HOLDINGS_CHANGED"
            || snapshot?.portfolio_changed_since_sync === true;
    }

    function myPortfolioSnapshotCurrentnessIsUnknown(snapshot = myPortfolioState.snapshot) {
        return snapshot?.currentness === "UNKNOWN";
    }

    function myPortfolioSyncFailureSummary(run) {
        const failed = Object.entries(run?.per_symbol || {})
            .filter(([, item]) => String(item?.status || "").toUpperCase() === "FAILED")
            .map(([symbol, item]) => {
                const reason = (item?.errors || item?.unavailable || [])
                    .map(value => String(value).replaceAll("_", " ").toLowerCase())
                    .join(", ");
                return `${symbol}: ${reason || "analysis unavailable"}`;
            });
        if (!failed.length) return "";
        return ` Failed: ${failed.slice(0, 4).join("; ")}${failed.length > 4 ? `; +${failed.length - 4} more` : ""}.`;
    }

    function myPortfolioReasonSummary(row) {
        const codes = row?.provenance?.interpretation_reason_codes || [];
        const labels = {
            STALE_HOLDINGS_CHANGED: "Holdings changed after this analysis.",
            STALE_PRICE_SESSION: "Price session is stale.",
            STALE_DECISION_EVIDENCE: "Decision evidence is stale.",
            PRICE_UNAVAILABLE: "Valuation is unavailable.",
            NO_CURRENT_DECISION: "Current Decision evidence is unavailable.",
            CURRENT_TRADE_PLAN: "Current active TradePlan supports the row.",
            ALL_DECISION_GATES_PASSED: "Decision gates passed.",
            ENTRY_QUALIFICATION_READY: "EntryQualification is qualified.",
            ADD_NOT_CONFIRMED: "ADD is not confirmed by current actionability evidence.",
            TRADE_PLAN_ENTRY_TRIGGER_ACTIVE: "TradePlan entry-low trigger remains active.",
            ENTRY_TRIGGER_CONSUMED: "Entry trigger has already been consumed.",
            TRADE_PLAN_STOP_AVAILABLE: "TradePlan stop is available as Major Support / Exit.",
            TRADE_PLAN_STOP_BREACHED: "TradePlan stop has been breached.",
            MAJOR_INVALIDATION_BREACHED: "Major invalidation level has been breached.",
            NO_TRADE_DECISION_EVIDENCE: "Current Decision evidence is cautionary.",
            DECISION_GATE_FAILED_DATA: "Data quality gate failed.",
            DECISION_GATE_FAILED_EVIDENCE: "Evidence gate failed.",
            DECISION_GATE_FAILED_RISK: "Risk gate failed.",
            DECISION_GATE_FAILED_CONFIDENCE: "Confidence gate failed.",
            DECISION_GATE_FAILED_MARKET: "Market gate failed.",
            SUPPORT_1_METHODOLOGY_UNAVAILABLE: "Support 1 is intentionally unavailable.",
            NO_APPROVED_SECONDARY_TARGET: "Target 2/3 are intentionally unavailable.",
            CONFIDENCE_EVIDENCE_UNAVAILABLE: "Conviction evidence is unavailable.",
            CONVICTION_FROM_CONFIDENCE: "Conviction reflects ATHENA Decision confidence/reliability.",
            CONVICTION_CONFIDENCE_UNAVAILABLE: "Decision confidence evidence is unavailable.",
            CONVICTION_CONFIDENCE_INCOHERENT: "Decision confidence evidence is not coherent with the accepted Decision.",
            TREND_UP_FROM_D1_SMA_STRUCTURE: "D1 trend: SMA20 above SMA50 with price at/above SMA50.",
            TREND_DOWN_FROM_D1_SMA_STRUCTURE: "D1 trend: SMA20 below SMA50 with price at/below SMA50.",
            TREND_MIXED_FROM_D1_SMA_STRUCTURE: "D1 trend: price and SMA20/SMA50 structure are not directionally aligned.",
            TREND_D1_EVIDENCE_UNAVAILABLE: "D1 trend evidence is unavailable.",
            TREND_D1_EVIDENCE_INCOHERENT: "D1 trend evidence is not coherent with the accepted Portfolio session.",
            SETUP_METHODOLOGY_DEFERRED: "Setup methodology is intentionally deferred.",
            SETUP_BREAKOUT_FROM_OPENING_RANGE_AGREEMENT: "Setup: OR15 and OR30 both show an upside breakout.",
            SETUP_BREAKDOWN_FROM_OPENING_RANGE_AGREEMENT: "Setup: OR15 and OR30 both show a downside breakdown.",
            SETUP_EVIDENCE_INCOHERENT: "Setup evidence is not coherent with the accepted Portfolio session.",
            SETUP_EVIDENCE_STALE: "Setup evidence is stale for the accepted Portfolio session.",
            SETUP_EVIDENCE_UNAVAILABLE: "Setup evidence is unavailable.",
            SETUP_OR_INCOMPLETE: "Setup: OR15 or OR30 is not complete.",
            SETUP_OR_WINDOWS_CONFLICT: "Setup: OR15 and OR30 disagree.",
            SETUP_RETURNED_INSIDE_RANGE: "Setup: price returned inside a required opening range.",
            SETUP_SINGLE_WINDOW_ONLY: "Setup: only one opening range window has an active event.",
            SETUP_NOT_PRESENT: "Setup: no opening range setup is present.",
        };
        const messages = codes.map(code => labels[code]).filter(Boolean);
        const failures = row?.provenance?.failed_components || [];
        failures.forEach(reason => messages.unshift(`Sync component failed: ${String(reason).replaceAll("_", " ").toLowerCase()}.`));
        return [...new Set(messages)].slice(0, 4).join(" ");
    }

    function myPortfolioStatusPill(value, row) {
        const status = String(value || "UNAVAILABLE").toUpperCase();
        const map = {
            STRONG: ["Strong", "good", "fa-circle-check"],
            HEALTHY: ["Healthy", "good", "fa-circle-check"],
            CAUTION: ["Caution", "warning", "fa-triangle-exclamation"],
            AT_RISK: ["At risk", "danger", "fa-circle-exclamation"],
            UNAVAILABLE: ["Unavailable", "neutral", "fa-circle-info"],
        };
        const [label, tone, icon] = map[status] || [status, "neutral", "fa-circle-info"];
        const reason = myPortfolioReasonSummary(row);
        return `${myPortfolioStatus(label, tone, icon)}${reason ? `<br><span class="my-portfolio-row-note" title="${escapeMyPortfolioHtml(reason)}">${escapeMyPortfolioHtml(reason)}</span>` : ""}`;
    }

    function myPortfolioActionPill(value, row) {
        const action = String(value || "WATCH").toUpperCase();
        const map = {
            ADD: ["Add", "good", "fa-circle-plus"],
            EXIT: ["Exit", "danger", "fa-arrow-right-from-bracket"],
            WATCH: ["Watch", "warning", "fa-eye"],
            HOLD: ["Hold", "neutral", "fa-pause"],
        };
        const [label, tone, icon] = map[action] || [action, "neutral", "fa-circle-info"];
        const reason = myPortfolioReasonSummary(row);
        return `${myPortfolioStatus(label, tone, icon)}${reason ? `<br><span class="my-portfolio-row-note" title="${escapeMyPortfolioHtml(reason)}">Why: ${escapeMyPortfolioHtml(reason)}</span>` : ""}`;
    }

    function myPortfolioConvictionCell(value, row) {
        const conviction = value ? String(value).toUpperCase() : null;
        const label = conviction || "—";
        const detail = conviction
            ? `Decision confidence: ${conviction}. Conviction reflects ATHENA Decision confidence/reliability, not buy strength.`
            : myPortfolioReasonSummary(row) || "Decision confidence evidence is unavailable.";
        return `<span title="${escapeMyPortfolioHtml(detail)}">${escapeMyPortfolioHtml(label)}</span>`;
    }

    function myPortfolioTrendCell(value, row) {
        const trend = value ? String(value).toUpperCase() : null;
        const detail = myPortfolioReasonSummary(row) || "D1 trend evidence is unavailable.";
        return `<span title="${escapeMyPortfolioHtml(detail)}">${escapeMyPortfolioHtml(trend || "—")}</span>`;
    }

    function showMyPortfolioAlert(message, tone = "neutral") {
        if (!myPortfolioAlert) return;
        myPortfolioAlert.textContent = message;
        myPortfolioAlert.className = `my-portfolio-alert ${tone}`;
        myPortfolioAlert.hidden = !message;
    }

    function clearMyPortfolioAlert() {
        showMyPortfolioAlert("");
    }

    function rowHasDuplicateError(row) {
        return (row.validation_errors || []).some(error =>
            String(error).includes("DUPLICATE_CANONICAL_INSTRUMENT")
        );
    }

    function countMyPortfolioDuplicateRows(preview) {
        return (preview?.rows || []).filter(rowHasDuplicateError).length;
    }

    function previewCanConfirm(preview) {
        if (!preview || preview.status !== "PREVIEWED") return false;
        return Number(preview.rejected_rows || 0) === 0
            && Number(preview.unresolved_rows || 0) === 0
            && Number(preview.ambiguous_rows || 0) === 0
            && countMyPortfolioDuplicateRows(preview) === 0
            && (preview.rows || []).every(row => (row.validation_errors || []).length === 0);
    }

    function setMyPortfolioBusy(next = {}) {
        myPortfolioState.previewing = Boolean(next.previewing);
        myPortfolioState.confirming = Boolean(next.confirming);
        if (Object.prototype.hasOwnProperty.call(next, "syncing")) {
            myPortfolioState.syncing = Boolean(next.syncing);
        }
        const busy = myPortfolioState.previewing || myPortfolioState.confirming;
        if (myPortfolioFileInput) myPortfolioFileInput.disabled = busy;
        if (myPortfolioCancelPreview) {
            myPortfolioCancelPreview.disabled = busy || !myPortfolioState.preview;
        }
        if (myPortfolioConfirm) {
            myPortfolioConfirm.disabled = busy || !previewCanConfirm(myPortfolioState.preview);
            const label = myPortfolioConfirm.querySelector("span");
            if (label) label.textContent = myPortfolioState.confirming ? "Confirming" : "Confirm Portfolio Update";
        }
        if (myPortfolioSync) {
            myPortfolioSync.disabled = myPortfolioState.syncing;
            const label = myPortfolioSync.querySelector("span");
            if (label) label.textContent = myPortfolioState.syncing ? "Syncing Portfolio" : "Sync Portfolio";
        }
    }

    function setMyPortfolioCancelLabel(label) {
        if (myPortfolioCancelPreview) myPortfolioCancelPreview.textContent = label;
    }

    async function loadMyPortfolioWorkspace() {
        if (!myPortfolioHoldingsRows) return;
        myPortfolioState.loading = true;
        clearMyPortfolioAlert();
        myPortfolioHoldingsRows.innerHTML = '<tr><td colspan="20" class="text-center text-muted">Loading holdings...</td></tr>';
        myPortfolioHistoryRows.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Loading import history...</td></tr>';
        try {
            const [holdingsRes, historyRes] = await Promise.all([
                apiRequest("/api/v1/my-portfolio/holdings", { skipToast: true }),
                apiRequest("/api/v1/my-portfolio/imports", { skipToast: true }),
            ]);
            myPortfolioState.holdings = holdingsRes?.data || [];
            myPortfolioState.imports = historyRes?.data?.imports || [];
            try {
                const snapshotRes = await apiRequest("/api/v1/my-portfolio/snapshot", { skipToast: true });
                myPortfolioState.snapshot = snapshotRes?.data || null;
            } catch (snapshotErr) {
                myPortfolioState.snapshot = null;
            }
            renderMyPortfolioHoldings(myPortfolioState.holdings);
            renderMyPortfolioHistory(myPortfolioState.imports);
            renderMyPortfolioSummary();
        } catch (err) {
            console.error("Failed to load My Portfolio workspace", err);
            showMyPortfolioAlert("Could not load My Portfolio holdings or import history.", "danger");
            myPortfolioState.snapshot = null;
            renderMyPortfolioHoldings([]);
            renderMyPortfolioHistory([]);
            renderMyPortfolioSummary();
        } finally {
            myPortfolioState.loading = false;
        }
    }

    function renderMyPortfolioSummary() {
        const holdings = myPortfolioState.holdings || [];
        const imports = myPortfolioState.imports || [];
        const snapshot = myPortfolioState.snapshot;
        const summary = snapshot?.summary || null;
        const latestConfirmed = imports.find(item => item.status === "CONFIRMED");
        const totalInvestment = summary
            ? summary.total_investment
            : holdings.reduce((sum, holding) => {
                const investment = Number(holding.investment);
                return sum + (Number.isFinite(investment) ? investment : 0);
            }, 0);
        myPortfolioHoldingCount.textContent = formatMyPortfolioNumber(summary ? summary.holding_count : holdings.length);
        myPortfolioTotalInvestment.textContent = formatMyPortfolioMoney(totalInvestment);
        myPortfolioCurrentValue.textContent = summary && summary.total_current_value != null
            ? formatMyPortfolioMoney(summary.total_current_value)
            : "₹ —";
        myPortfolioTotalPnl.textContent = summary && summary.total_pnl != null
            ? formatMyPortfolioMoney(summary.total_pnl)
            : "₹ —";
        myPortfolioTotalPnlDetail.textContent = summary && summary.total_pnl_pct != null
            ? `${formatMyPortfolioPct(summary.total_pnl_pct)} total return`
            : "Unavailable until all rows are priced";
        if (latestConfirmed) {
            myPortfolioLatestImport.textContent = formatMyPortfolioTime(latestConfirmed.confirmed_at || latestConfirmed.uploaded_at);
            const asOf = latestConfirmed.holdings_as_of
                ? `Holdings as of ${formatMyPortfolioTime(latestConfirmed.holdings_as_of)}`
                : "Holdings as-of not supplied";
            myPortfolioLatestImportDetail.textContent = `${latestConfirmed.filename} · ${asOf}`;
        } else {
            myPortfolioLatestImport.textContent = "—";
            myPortfolioLatestImportDetail.textContent = "No import confirmed yet";
        }
        myPortfolioLastSynced.textContent = summary?.last_synced_at
            ? formatMyPortfolioTime(summary.last_synced_at)
            : "—";
        myPortfolioMarketDataThrough.textContent = summary?.market_data_through
            ? `Market data through ${formatMyPortfolioTime(summary.market_data_through)}`
            : "Market data through —";
        if (myPortfolioSnapshotIsStale(snapshot)) {
            showMyPortfolioAlert(
                "Portfolio holdings changed since this analysis. Previous snapshot remains visible; Sync Portfolio to refresh ATHENA analysis.",
                "warning"
            );
        } else if (myPortfolioSnapshotCurrentnessIsUnknown(snapshot)) {
            showMyPortfolioAlert(
                "Portfolio analysis currentness could not be verified. Sync Portfolio to generate a current verified snapshot.",
                "warning"
            );
        } else if (!snapshot && holdings.length) {
            showMyPortfolioAlert("Portfolio holdings are imported. Sync Portfolio to generate ATHENA analysis.", "warning");
        }
    }

    function renderMyPortfolioHoldings(holdings) {
        if (myPortfolioState.snapshot?.rows?.length) {
            renderMyPortfolioSnapshotRows(myPortfolioState.snapshot.rows);
            return;
        }
        if (!holdings.length) {
            myPortfolioHoldingsRows.innerHTML = '<tr><td colspan="20" class="text-center text-muted">No holdings imported yet. Upload Portfolio to begin.</td></tr>';
            return;
        }
        myPortfolioHoldingsRows.innerHTML = holdings.map(holding => `
            <tr>
                <td class="font-mono"><strong>${escapeMyPortfolioHtml(holding.symbol || bareMyPortfolioSymbol(holding.instrument_id))}</strong></td>
                <td>${formatMyPortfolioNumber(holding.quantity)}</td>
                <td class="font-mono">${formatMyPortfolioMoney(holding.avg_price)}</td>
                <td class="text-muted">—</td>
                <td class="text-muted">Not synced</td>
                <td class="font-mono">${formatMyPortfolioMoney(holding.investment)}</td>
                <td class="text-muted">—</td>
                <td class="text-muted">—</td>
                <td class="text-muted">—</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">—</td>
                <td class="text-muted">—</td>
                <td class="text-muted">—</td>
                <td class="text-muted">Not available</td>
                <td class="text-muted">Not synced</td>
            </tr>
        `).join("");
    }

    function renderMyPortfolioSnapshotRows(rows) {
        myPortfolioHoldingsRows.innerHTML = rows.map(row => `
            <tr>
                <td class="font-mono"><strong>${escapeMyPortfolioHtml(row.symbol)}</strong></td>
                <td>${formatMyPortfolioNumber(row.qty ?? row.quantity)}</td>
                <td class="font-mono">${formatMyPortfolioMoney(row.avg_price)}</td>
                <td class="font-mono">${row.last_price == null ? "₹ —" : formatMyPortfolioMoney(row.last_price)}</td>
                <td>${row.price_as_of ? formatMyPortfolioTime(row.price_as_of) : "Not available"}</td>
                <td class="font-mono">${formatMyPortfolioMoney(row.investment)}</td>
                <td class="font-mono">${row.current_value == null ? "₹ —" : formatMyPortfolioMoney(row.current_value)}</td>
                <td class="font-mono">${row.pnl == null ? "₹ —" : formatMyPortfolioMoney(row.pnl)}</td>
                <td>${row.pnl_pct == null ? "—" : formatMyPortfolioPct(row.pnl_pct)}</td>
                <td>${myPortfolioStatusPill(row.status, row)}</td>
                <td>${myPortfolioConvictionCell(row.conviction, row)}</td>
                <td>${myPortfolioTrendCell(row.trend_or_setup, row)}</td>
                <td>${escapeMyPortfolioHtml(row.key_trigger || "Not available")}</td>
                <td class="font-mono">${row.support_1 == null ? "₹ —" : formatMyPortfolioMoney(row.support_1)}</td>
                <td class="font-mono">${row.major_support_exit == null ? "₹ —" : formatMyPortfolioMoney(row.major_support_exit)}</td>
                <td class="font-mono">${row.target_1 == null ? "₹ —" : formatMyPortfolioMoney(row.target_1)}</td>
                <td class="font-mono">${row.target_2 == null ? "₹ —" : formatMyPortfolioMoney(row.target_2)}</td>
                <td class="font-mono">${row.target_3 == null ? "₹ —" : formatMyPortfolioMoney(row.target_3)}</td>
                <td>${myPortfolioActionPill(row.next_action, row)}</td>
                <td>${row.last_review ? formatMyPortfolioTime(row.last_review) : "Not available"}</td>
            </tr>
        `).join("");
    }

    function renderMyPortfolioHistory(imports) {
        if (!imports.length) {
            myPortfolioHistoryRows.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No import history yet.</td></tr>';
            return;
        }
        myPortfolioHistoryRows.innerHTML = imports.map(item => {
            const counts = `${item.accepted_rows}/${item.total_rows} accepted`;
            const issues = [];
            if (item.rejected_rows) issues.push(`${item.rejected_rows} invalid`);
            if (item.unresolved_rows) issues.push(`${item.unresolved_rows} unresolved`);
            if (item.ambiguous_rows) issues.push(`${item.ambiguous_rows} ambiguous`);
            const statusTone = item.status === "CONFIRMED"
                ? "good"
                : item.status === "FAILED" ? "danger" : "warning";
            return `
                <tr>
                    <td>${formatMyPortfolioTime(item.uploaded_at)}</td>
                    <td>${escapeMyPortfolioHtml(item.filename)}</td>
                    <td>${myPortfolioStatus(item.status, statusTone)}</td>
                    <td>${escapeMyPortfolioHtml(counts)}${issues.length ? `<br><span class="text-muted">${escapeMyPortfolioHtml(issues.join(" · "))}</span>` : ""}</td>
                    <td>${formatMyPortfolioTime(item.confirmed_at)}</td>
                </tr>
            `;
        }).join("");
    }

    function mappingStatus(row) {
        const state = String(row.mapping_state || "UNRESOLVED").toUpperCase();
        if (state === "RESOLVED") return myPortfolioStatus("Resolved", "good", "fa-circle-check");
        if (state === "AMBIGUOUS") return myPortfolioStatus("Ambiguous", "warning", "fa-triangle-exclamation");
        return myPortfolioStatus("Unresolved", "danger", "fa-circle-xmark");
    }

    function validationStatus(row) {
        const errors = row.validation_errors || [];
        const warnings = row.warnings || [];
        if (errors.length) {
            const text = errors.join(" · ");
            return `${myPortfolioStatus(rowHasDuplicateError(row) ? "Duplicate" : "Invalid", "danger", "fa-circle-xmark")}<br><span class="text-muted">${escapeMyPortfolioHtml(text)}</span>`;
        }
        if (warnings.length) {
            return `${myPortfolioStatus("Warning", "warning", "fa-triangle-exclamation")}<br><span class="text-muted">${escapeMyPortfolioHtml(warnings.join(" · "))}</span>`;
        }
        return myPortfolioStatus("Valid", "good", "fa-circle-check");
    }

    function renderMyPortfolioPreview(preview) {
        myPortfolioState.preview = preview;
        if (!preview || !myPortfolioPreview) {
            if (myPortfolioPreview) myPortfolioPreview.hidden = true;
            setMyPortfolioBusy();
            return;
        }
        myPortfolioPreview.hidden = false;
        myPortfolioPreviewTotal.textContent = formatMyPortfolioNumber(preview.total_rows);
        myPortfolioPreviewValid.textContent = formatMyPortfolioNumber(preview.accepted_rows);
        myPortfolioPreviewInvalid.textContent = formatMyPortfolioNumber(preview.rejected_rows);
        myPortfolioPreviewUnresolved.textContent = formatMyPortfolioNumber(preview.unresolved_rows);
        myPortfolioPreviewAmbiguous.textContent = formatMyPortfolioNumber(preview.ambiguous_rows);
        myPortfolioPreviewDuplicates.textContent = formatMyPortfolioNumber(countMyPortfolioDuplicateRows(preview));

        const topMessages = [...(preview.errors || []), ...(preview.warnings || [])];
        if (preview.status === "FAILED") {
            showMyPortfolioAlert(topMessages.join(" ") || "The uploaded file could not be parsed. Review the required columns and upload again.", "danger");
        } else if (previewCanConfirm(preview)) {
            showMyPortfolioAlert("Preview is clean. Review the reconciliation diff before confirming.", "good");
        } else {
            showMyPortfolioAlert("Preview has invalid, unresolved, ambiguous, or duplicate rows. Fix the file and upload again before confirming.", "warning");
        }
        setMyPortfolioCancelLabel("Cancel");

        renderMyPortfolioPreviewRows(preview.rows || []);
        renderMyPortfolioReconciliation(preview.proposed_changes || []);
        myPortfolioUploadState.textContent = `Preview ${preview.import_id} ready for ${preview.filename}.`;
        setMyPortfolioBusy();
    }

    function renderMyPortfolioPreviewRows(rows) {
        if (!rows.length) {
            myPortfolioPreviewRows.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No preview rows available.</td></tr>';
            return;
        }
        myPortfolioPreviewRows.innerHTML = rows.map(row => {
            const candidates = (row.candidates || []).map(candidate =>
                candidate.instrument_id || candidate.symbol
            ).filter(Boolean).join(", ");
            const resolved = row.resolved_instrument_id
                ? row.resolved_instrument_id
                : candidates || "Not resolved";
            return `
                <tr>
                    <td>${escapeMyPortfolioHtml(row.source_row_id)}</td>
                    <td class="font-mono">${escapeMyPortfolioHtml(row.raw_symbol)}</td>
                    <td class="font-mono">${escapeMyPortfolioHtml(resolved)}</td>
                    <td>${row.quantity == null ? "—" : formatMyPortfolioNumber(row.quantity)}</td>
                    <td class="font-mono">${row.avg_price == null ? "₹ —" : formatMyPortfolioMoney(row.avg_price)}</td>
                    <td>${mappingStatus(row)}</td>
                    <td>${validationStatus(row)}</td>
                </tr>
            `;
        }).join("");
    }

    function reconciliationMeaning(action) {
        if (action === "ADDED") return "New current holding from uploaded snapshot.";
        if (action === "UPDATED") return "Existing current holding will be replaced by uploaded quantity and average price.";
        if (action === "REMOVED") return "Absent from uploaded current-holdings snapshot; no sale inferred.";
        return "No canonical holding change.";
    }

    function reconciliationTone(action) {
        if (action === "ADDED" || action === "UPDATED") return "warning";
        if (action === "REMOVED") return "danger";
        return "neutral";
    }

    function renderMyPortfolioReconciliation(changes) {
        const counts = changes.reduce((acc, change) => {
            const action = String(change.action || "UNCHANGED").toUpperCase();
            acc[action] = (acc[action] || 0) + 1;
            return acc;
        }, {});
        myPortfolioReconciliationSummary.innerHTML = ["ADDED", "UPDATED", "REMOVED", "UNCHANGED"]
            .map(action => myPortfolioStatus(`${action}: ${counts[action] || 0}`, reconciliationTone(action)))
            .join("");
        if (!changes.length) {
            myPortfolioReconciliationRows.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No reconciliation changes available.</td></tr>';
            return;
        }
        myPortfolioReconciliationRows.innerHTML = changes.map(change => {
            const action = String(change.action || "UNCHANGED").toUpperCase();
            const before = change.before || {};
            const after = change.after || {};
            return `
                <tr>
                    <td>${myPortfolioStatus(action, reconciliationTone(action))}</td>
                    <td class="font-mono">${escapeMyPortfolioHtml(change.instrument_id)}</td>
                    <td>${before.quantity == null ? "—" : formatMyPortfolioNumber(before.quantity)}</td>
                    <td>${after.quantity == null ? "—" : formatMyPortfolioNumber(after.quantity)}</td>
                    <td class="font-mono">${before.avg_price == null ? "₹ —" : formatMyPortfolioMoney(before.avg_price)}</td>
                    <td class="font-mono">${after.avg_price == null ? "₹ —" : formatMyPortfolioMoney(after.avg_price)}</td>
                    <td>${escapeMyPortfolioHtml(reconciliationMeaning(action))}</td>
                </tr>
            `;
        }).join("");
    }

    async function uploadMyPortfolioFile(file) {
        if (!file || myPortfolioState.previewing || myPortfolioState.confirming) return;
        myPortfolioState.selectedFile = file;
        myPortfolioSelectedFile.textContent = file.name;
        myPortfolioUploadState.textContent = "Uploading and parsing on the server...";
        clearMyPortfolioAlert();
        renderMyPortfolioPreview(null);
        setMyPortfolioBusy({ previewing: true });
        try {
            const response = await apiRequest(
                `/api/v1/my-portfolio/imports?filename=${encodeURIComponent(file.name)}`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/octet-stream" },
                    body: file,
                    skipToast: true,
                }
            );
            renderMyPortfolioPreview(response.data);
        } catch (err) {
            const failedPreview = err?.data?.data;
            if (err?.status === 400 && failedPreview?.import_id) {
                renderMyPortfolioPreview(failedPreview);
            } else {
                console.error("My Portfolio upload failed", err);
                showMyPortfolioAlert("Upload failed before ATHENA could create a preview.", "danger");
                myPortfolioUploadState.textContent = "Upload failed. Choose the file again to retry.";
            }
        } finally {
            setMyPortfolioBusy();
        }
    }

    async function confirmMyPortfolioPreview() {
        const preview = myPortfolioState.preview;
        if (!previewCanConfirm(preview) || myPortfolioState.confirming) return;
        setMyPortfolioBusy({ confirming: true });
        myPortfolioUploadState.textContent = "Confirming portfolio update...";
        try {
            const response = await apiRequest(
                `/api/v1/my-portfolio/imports/${encodeURIComponent(preview.import_id)}/confirm`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ import_id: preview.import_id, confirmation: "CONFIRM" }),
                    skipToast: true,
                }
            );
            const result = response.data;
            const changes = result?.reconciliation || [];
            const counts = changes.reduce((acc, change) => {
                const action = String(change.action || "UNCHANGED").toUpperCase();
                acc[action] = (acc[action] || 0) + 1;
                return acc;
            }, {});
            const successMessage = `Portfolio update confirmed. Added ${counts.ADDED || 0}, updated ${counts.UPDATED || 0}, removed ${counts.REMOVED || 0}, unchanged ${counts.UNCHANGED || 0}.`;
            if (myPortfolioFileInput) myPortfolioFileInput.value = "";
            if (myPortfolioSelectedFile) myPortfolioSelectedFile.textContent = "No file selected";
            myPortfolioState.preview = null;
            myPortfolioState.selectedFile = null;
            if (myPortfolioPreview) myPortfolioPreview.hidden = true;
            myPortfolioUploadState.textContent = "Choose a holdings file to create a preview.";
            await loadMyPortfolioWorkspace();
            if (myPortfolioSnapshotIsStale()) {
                showMyPortfolioAlert(`${successMessage} Portfolio analysis is now stale. Sync Portfolio to refresh ATHENA analysis.`, "warning");
            } else {
                showMyPortfolioAlert(successMessage, "good");
            }
        } catch (err) {
            console.error("My Portfolio confirmation failed", err);
            const detail = String(err?.data?.detail || "");
            const type = String(err?.data?.type || "");
            if (err?.status === 409 && type.includes("portfolio-sync-active")) {
                showMyPortfolioAlert(
                    "Portfolio Sync is currently running. Wait for it to finish before confirming holdings changes.",
                    "warning"
                );
                myPortfolioUploadState.textContent = "Preview remains available. Confirm after Portfolio Sync finishes.";
            } else if (err?.status === 409 || detail.includes("STALE_PREVIEW") || type.includes("stale")) {
                showMyPortfolioAlert(
                    "Portfolio holdings changed after this preview was generated. Please generate a fresh preview before confirming.",
                    "warning"
                );
                setMyPortfolioCancelLabel("Upload Again");
                myPortfolioUploadState.textContent = "Preview is stale. Use Upload Again or re-select the file to refresh the preview.";
            } else {
                showMyPortfolioAlert("Confirmation failed. Review the preview and retry.", "danger");
            }
        } finally {
            setMyPortfolioBusy();
        }
    }

    function syncRunTerminal(status) {
        return ["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"].includes(String(status || "").toUpperCase());
    }

    function renderMyPortfolioSyncStatus(run) {
        if (!run) return;
        myPortfolioState.syncRun = run;
        const processed = Number(run.progress?.processed_holdings || 0);
        const total = Number(run.total_holdings || 0);
        const status = String(run.status || "QUEUED").toUpperCase();
        const message = run.progress?.message || `Portfolio Sync ${status}`;
        const detail = total > 0 ? ` — ${processed} of ${total} analyzed` : "";
        const tone = status === "SUCCESS"
            ? "good"
            : status === "PARTIAL" || status === "QUEUED" || status === "RUNNING"
                ? "warning"
                : "danger";
        showMyPortfolioAlert(`${message}${detail}.${myPortfolioSyncFailureSummary(run)}`, tone);
        if (myPortfolioUploadState) {
            myPortfolioUploadState.textContent = `Sync ${run.sync_run_id}: ${status}${detail}`;
        }
        setMyPortfolioBusy({ syncing: !syncRunTerminal(status) });
    }

    async function startMyPortfolioSync() {
        if (myPortfolioState.syncing) return;
        setMyPortfolioBusy({ syncing: true });
        try {
            const response = await apiRequest("/api/v1/my-portfolio/sync", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force_ingestion: false }),
                skipToast: true,
            });
            renderMyPortfolioSyncStatus(response.data);
            pollMyPortfolioSync(response.data.sync_run_id);
        } catch (err) {
            console.error("Failed to start My Portfolio Sync", err);
            showMyPortfolioAlert("Could not start Portfolio Sync. Existing holdings and last good snapshot are unchanged.", "danger");
            setMyPortfolioBusy({ syncing: false });
        }
    }

    async function pollMyPortfolioSync(syncRunId) {
        if (!syncRunId) return;
        if (myPortfolioState.syncPollTimer) {
            clearTimeout(myPortfolioState.syncPollTimer);
            myPortfolioState.syncPollTimer = null;
        }
        try {
            const response = await apiRequest(
                `/api/v1/my-portfolio/sync/${encodeURIComponent(syncRunId)}`,
                { skipToast: true }
            );
            const run = response.data;
            renderMyPortfolioSyncStatus(run);
            if (syncRunTerminal(run.status)) {
                setMyPortfolioBusy({ syncing: false });
                if (run.status === "SUCCESS" || run.status === "PARTIAL") {
                    const snapshotRes = await apiRequest("/api/v1/my-portfolio/snapshot", { skipToast: true });
                    myPortfolioState.snapshot = snapshotRes?.data || null;
                    renderMyPortfolioHoldings(myPortfolioState.holdings);
                    renderMyPortfolioSummary();
                    if (run.status === "PARTIAL") {
                        showMyPortfolioAlert(
                            `Portfolio Sync partial — ${run.succeeded_holdings} of ${run.total_holdings} holdings analyzed.${myPortfolioSyncFailureSummary(run)} Failed rows remain visible in the table.`,
                            "warning"
                        );
                    } else {
                        showMyPortfolioAlert("Portfolio Sync completed. Snapshot refreshed.", "good");
                    }
                } else {
                    showMyPortfolioAlert("Portfolio Sync failed. Previous completed snapshot remains unchanged.", "danger");
                }
                return;
            }
            myPortfolioState.syncPollTimer = setTimeout(() => pollMyPortfolioSync(syncRunId), 1500);
        } catch (err) {
            console.error("Failed to poll My Portfolio Sync", err);
            showMyPortfolioAlert("Could not read Portfolio Sync status. Previous completed snapshot remains unchanged.", "danger");
            setMyPortfolioBusy({ syncing: false });
        }
    }

    function clearMyPortfolioPreview() {
        myPortfolioState.preview = null;
        myPortfolioState.selectedFile = null;
        if (myPortfolioFileInput) myPortfolioFileInput.value = "";
        if (myPortfolioSelectedFile) myPortfolioSelectedFile.textContent = "No file selected";
        if (myPortfolioPreview) myPortfolioPreview.hidden = true;
        if (myPortfolioUploadState) myPortfolioUploadState.textContent = "Choose a holdings file to create a preview.";
        setMyPortfolioCancelLabel("Cancel");
        clearMyPortfolioAlert();
        setMyPortfolioBusy();
        myPortfolioFileInput?.focus();
    }

    myPortfolioFileInput?.addEventListener("change", event => {
        const file = event.target.files && event.target.files[0];
        uploadMyPortfolioFile(file);
    });
    myPortfolioConfirm?.addEventListener("click", confirmMyPortfolioPreview);
    myPortfolioCancelPreview?.addEventListener("click", clearMyPortfolioPreview);
    myPortfolioSync?.addEventListener("click", startMyPortfolioSync);
