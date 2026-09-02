
    const myPortfolioFileInput = document.getElementById("my-portfolio-file");
    const myPortfolioAlert = document.getElementById("my-portfolio-alert");
    const myPortfolioSelectedFile = document.getElementById("my-portfolio-selected-file");
    const myPortfolioUploadState = document.getElementById("my-portfolio-upload-state");
    const myPortfolioPreview = document.getElementById("my-portfolio-preview");
    const myPortfolioConfirm = document.getElementById("my-portfolio-confirm");
    const myPortfolioCancelPreview = document.getElementById("my-portfolio-cancel-preview");
    const myPortfolioHoldingCount = document.getElementById("my-portfolio-holding-count");
    const myPortfolioTotalInvestment = document.getElementById("my-portfolio-total-investment");
    const myPortfolioLatestImport = document.getElementById("my-portfolio-latest-import");
    const myPortfolioLatestImportDetail = document.getElementById("my-portfolio-latest-import-detail");
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
    }

    function setMyPortfolioCancelLabel(label) {
        if (myPortfolioCancelPreview) myPortfolioCancelPreview.textContent = label;
    }

    async function loadMyPortfolioWorkspace() {
        if (!myPortfolioHoldingsRows) return;
        myPortfolioState.loading = true;
        clearMyPortfolioAlert();
        myPortfolioHoldingsRows.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Loading holdings...</td></tr>';
        myPortfolioHistoryRows.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Loading import history...</td></tr>';
        try {
            const [holdingsRes, historyRes] = await Promise.all([
                apiRequest("/api/v1/my-portfolio/holdings", { skipToast: true }),
                apiRequest("/api/v1/my-portfolio/imports", { skipToast: true }),
            ]);
            myPortfolioState.holdings = holdingsRes?.data || [];
            myPortfolioState.imports = historyRes?.data?.imports || [];
            renderMyPortfolioHoldings(myPortfolioState.holdings);
            renderMyPortfolioHistory(myPortfolioState.imports);
            renderMyPortfolioSummary();
        } catch (err) {
            console.error("Failed to load My Portfolio workspace", err);
            showMyPortfolioAlert("Could not load My Portfolio holdings or import history.", "danger");
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
        const latestConfirmed = imports.find(item => item.status === "CONFIRMED");
        const totalInvestment = holdings.reduce((sum, holding) => {
            const investment = Number(holding.investment);
            return sum + (Number.isFinite(investment) ? investment : 0);
        }, 0);
        myPortfolioHoldingCount.textContent = formatMyPortfolioNumber(holdings.length);
        myPortfolioTotalInvestment.textContent = formatMyPortfolioMoney(totalInvestment);
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
    }

    function renderMyPortfolioHoldings(holdings) {
        if (!holdings.length) {
            myPortfolioHoldingsRows.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No holdings imported yet. Upload Portfolio to begin.</td></tr>';
            return;
        }
        myPortfolioHoldingsRows.innerHTML = holdings.map(holding => `
            <tr>
                <td class="font-mono"><strong>${escapeMyPortfolioHtml(holding.symbol || bareMyPortfolioSymbol(holding.instrument_id))}</strong></td>
                <td>${formatMyPortfolioNumber(holding.quantity)}</td>
                <td class="font-mono">${formatMyPortfolioMoney(holding.avg_price)}</td>
                <td class="font-mono">${formatMyPortfolioMoney(holding.investment)}</td>
                <td>${formatMyPortfolioTime(holding.imported_at)}</td>
                <td class="font-mono">${escapeMyPortfolioHtml(holding.source_import_id)}</td>
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
            showMyPortfolioAlert(successMessage, "good");
        } catch (err) {
            console.error("My Portfolio confirmation failed", err);
            const detail = String(err?.data?.detail || "");
            const type = String(err?.data?.type || "");
            if (err?.status === 409 || detail.includes("STALE_PREVIEW") || type.includes("stale")) {
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
