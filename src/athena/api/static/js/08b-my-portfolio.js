
    const myPortfolioFileInput = document.getElementById("my-portfolio-file");
    const myPortfolioAlert = document.getElementById("my-portfolio-alert");
    const myPortfolioSelectedFile = document.getElementById("my-portfolio-selected-file");
    const myPortfolioUploadState = document.getElementById("my-portfolio-upload-state");
    const myPortfolioConfirmActions = document.getElementById("my-portfolio-confirm-actions");
    const myPortfolioPreview = document.getElementById("my-portfolio-preview-modal");
    const myPortfolioPreviewOpen = document.getElementById("my-portfolio-preview-open");
    const myPortfolioPreviewClose = document.getElementById("my-portfolio-preview-close");
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
    const myPortfolioMiniValue = document.getElementById("my-portfolio-mini-value");
    const myPortfolioMiniPnl = document.getElementById("my-portfolio-mini-pnl");
    const myPortfolioMiniSynced = document.getElementById("my-portfolio-mini-synced");
    const myPortfolioMiniSort = document.getElementById("my-portfolio-mini-sort");
    const myPortfolioMiniTriage = document.getElementById("my-portfolio-mini-triage");
    const myPortfolioQueueAll = document.getElementById("my-portfolio-queue-all");
    const myPortfolioQueueOnly = document.getElementById("my-portfolio-queue-only");
    const myPortfolioTriageClear = document.getElementById("my-portfolio-triage-clear");
    const myPortfolioTriageSummary = document.getElementById("my-portfolio-triage-summary");
    const myPortfolioTriageLead = document.getElementById("my-portfolio-triage-lead");
    const myPortfolioHoldingsScopeBadge = document.getElementById("my-portfolio-holdings-scope-badge");
    const myPortfolioCommandDashboard = document.querySelector(".my-portfolio-command-dashboard");
    const myPortfolioRiskPanel = document.querySelector(".my-portfolio-risk-panel");
    const myPortfolioWorkstation = document.querySelector(".my-portfolio-workstation");
    const myPortfolioKpiStrip = document.querySelector(".my-portfolio-kpi-strip");
    const myPortfolioSectionNav = document.getElementById("my-portfolio-section-nav");
    const myPortfolioStickyHeader = document.getElementById("my-portfolio-sticky-header");
    const myPortfolioRiskBody = document.getElementById("my-portfolio-risk-body");
    const myPortfolioRiskLead = document.getElementById("my-portfolio-risk-lead");
    const myPortfolioRiskToggle = document.getElementById("my-portfolio-risk-toggle");
    const myPortfolioExportToggle = document.getElementById("my-portfolio-export-toggle");
    const myPortfolioExportPanel = document.getElementById("my-portfolio-export-panel");
    const myPortfolioExportScope = document.getElementById("my-portfolio-export-scope");
    const myPortfolioExportFormat = document.getElementById("my-portfolio-export-format");
    const myPortfolioExportAdvanced = document.getElementById("my-portfolio-export-advanced");
    const myPortfolioExportColumnCount = document.getElementById("my-portfolio-export-column-count");
    const myPortfolioExportColumns = document.getElementById("my-portfolio-export-columns");
    const myPortfolioExportPresetEssential = document.getElementById("my-portfolio-export-preset-essential");
    const myPortfolioExportPresetReview = document.getElementById("my-portfolio-export-preset-review");
    const myPortfolioExportSelectAll = document.getElementById("my-portfolio-export-select-all");
    const myPortfolioExportClear = document.getElementById("my-portfolio-export-clear");
    const myPortfolioExportStatus = document.getElementById("my-portfolio-export-status");
    const myPortfolioExportDownload = document.getElementById("my-portfolio-export-download");
    const myPortfolioPrivacyToggle = document.getElementById("my-portfolio-privacy-toggle");
    const myPortfolioPreviewTotal = document.getElementById("my-portfolio-preview-total");
    const myPortfolioPreviewValid = document.getElementById("my-portfolio-preview-valid");
    const myPortfolioPreviewInvalid = document.getElementById("my-portfolio-preview-invalid");
    const myPortfolioPreviewUnresolved = document.getElementById("my-portfolio-preview-unresolved");
    const myPortfolioPreviewAmbiguous = document.getElementById("my-portfolio-preview-ambiguous");
    const myPortfolioPreviewDuplicates = document.getElementById("my-portfolio-preview-duplicates");
    const myPortfolioInlinePreview = document.getElementById("my-portfolio-inline-preview");
    const myPortfolioInlineTotal = document.getElementById("my-portfolio-inline-total");
    const myPortfolioInlineValid = document.getElementById("my-portfolio-inline-valid");
    const myPortfolioInlineSkipped = document.getElementById("my-portfolio-inline-skipped");
    const myPortfolioInlineDuplicates = document.getElementById("my-portfolio-inline-duplicates");
    const myPortfolioPreviewIssues = document.getElementById("my-portfolio-preview-issues");
    const myPortfolioPreviewRows = document.getElementById("my-portfolio-preview-rows");
    const myPortfolioReconciliationSummary = document.getElementById("my-portfolio-reconciliation-summary");
    const myPortfolioReconciliationRows = document.getElementById("my-portfolio-reconciliation-rows");
    const myPortfolioHoldingsRows = document.getElementById("my-portfolio-holdings-rows");
    const myPortfolioSyncOverlay = document.getElementById("my-portfolio-sync-overlay");
    const myPortfolioSyncOverlayDetail = document.getElementById("my-portfolio-sync-overlay-detail");
    const myPortfolioHistoryRows = document.getElementById("my-portfolio-history-rows");
    const myPortfolioSortField = document.getElementById("my-portfolio-sort-field");
    const myPortfolioSortDirection = document.getElementById("my-portfolio-sort-direction");
    const myPortfolioSortReset = document.getElementById("my-portfolio-sort-reset");
    const myPortfolioSortSummary = document.getElementById("my-portfolio-sort-summary");
    const myPortfolioTableProfile = document.getElementById("my-portfolio-table-profile");
    const myPortfolioMiniProfile = document.getElementById("my-portfolio-mini-profile");
    const myPortfolioHeatmapPanel = document.querySelector(".my-portfolio-heatmap-panel");
    const myPortfolioHeatmapLead = document.getElementById("my-portfolio-heatmap-lead");
    const myPortfolioHeatmapBody = document.getElementById("my-portfolio-heatmap-body");
    const myPortfolioHeatmapSize = document.getElementById("my-portfolio-heatmap-size");
    const myPortfolioHeatmapColor = document.getElementById("my-portfolio-heatmap-color");
    const myPortfolioHeatmapToggle = document.getElementById("my-portfolio-heatmap-toggle");
    const myPortfolioExportPresetDailyReview = document.getElementById("my-portfolio-export-preset-daily-review");
    const myPortfolioExportPresetFullAudit = document.getElementById("my-portfolio-export-preset-full-audit");
    const myPortfolioExportPresetPrivate = document.getElementById("my-portfolio-export-preset-private");
    const myPortfolioHoldingsTable = document.getElementById("my-portfolio-holdings-table");
    const myPortfolioHoldingsCard = document.querySelector(".my-portfolio-holdings-card");
    const myPortfolioUploadPanel = document.getElementById("my-portfolio-upload-panel");
    const myPortfolioUploadShortcut = document.getElementById("my-portfolio-upload-shortcut");
    const myPortfolioUploadPanelClose = document.getElementById("my-portfolio-upload-panel-close");
    const myPortfolioHoldingsHeader = document.querySelector(".my-portfolio-holdings-card > .card-header");
    const myPortfolioHoldingsScroll = document.querySelector(".my-portfolio-holdings-scroll");
    const myPortfolioTheadDock = document.getElementById("my-portfolio-holdings-thead-dock");
    const myPortfolioTheadDockScroller = document.querySelector(".my-portfolio-holdings-thead-dock-scroller");
    const myPortfolioTheadClone = document.getElementById("my-portfolio-holdings-thead-clone");
    const myPortfolioWorkspaceViewport = document.querySelector(".workspace-viewport");
    const myPortfolioHistoryPanel = document.querySelector(".my-portfolio-history-panel");
    const myPortfolioHistoryBody = document.getElementById("my-portfolio-history-body");
    const myPortfolioHistoryToggle = document.getElementById("my-portfolio-history-toggle");
    const myPortfolioResetOpen = document.getElementById("my-portfolio-reset-open");
    const myPortfolioResetModal = document.getElementById("my-portfolio-reset-modal");
    const myPortfolioResetClose = document.getElementById("my-portfolio-reset-close");
    const myPortfolioResetConfirm = document.getElementById("my-portfolio-reset-confirm");
    const myPortfolioResetGateStatus = document.getElementById("my-portfolio-reset-gate-status");
    const myPortfolioResetSubmit = document.getElementById("my-portfolio-reset-submit");
    const myPortfolioDetailModal = document.getElementById("my-portfolio-detail-modal");
    const myPortfolioDetailClose = document.getElementById("my-portfolio-detail-close");
    const myPortfolioDetailTitle = document.getElementById("my-portfolio-detail-title");
    const myPortfolioDetailSubtitle = document.getElementById("my-portfolio-detail-subtitle");
    const myPortfolioDetailBody = document.getElementById("my-portfolio-detail-body");

    const myPortfolioState = {
        preview: null,
        selectedFile: null,
        loading: false,
        previewing: false,
        confirming: false,
        syncing: false,
        syncPollTimer: null,
        syncRun: null,
        // True from the moment an Edit/Delete is confirmed until Portfolio
        // Sync actually starts (or the edit/delete itself fails) — bridges
        // the brief gap before `syncing` turns true, so the blocking
        // overlay never flickers off between "saved" and "sync started".
        holdingActionPending: false,
        snapshot: null,
        changes: null,
        timeline: null,
        timelineKey: null,
        timelineLoading: false,
        timelineError: false,
        holdings: [],
        imports: [],
        notes: {},
        snapshotRowsByKey: {},
        sort: {
            key: "pnl_pct",
            direction: "desc",
        },
        density: "compact",
        tableProfile: "compact_scan",
        pinnedInstrumentIds: [],
        heatmap: {
            size: "current_value",
            color: "pnl_pct",
        },
        riskExpanded: false,
        heatmapExpanded: false,
        triageFiltersExpanded: false,
        historyExpanded: false,
        uploadPanelOpen: false,
        valuesHidden: (() => {
            try {
                return window.localStorage.getItem("athena.myPortfolio.valuesHidden") === "true";
            } catch (err) {
                return false;
            }
        })(),
        detailOpenKey: null,
        reviewSession: {
            active: false,
            keys: [],
            index: 0,
        },
        syncCompletion: null,
        exporting: false,
        exportColumnsByScope: {},
        triage: {
            queueView: false,
            attention: [],
            smart: {
                status: [],
                daily_review: [],
                next_action: [],
                trend: [],
                setup: [],
                pnl: [],
                currentness: [],
                evidence: [],
            },
        },
    };

    const MY_PORTFOLIO_EMPTY_SMART_FILTERS = {
        status: [],
        daily_review: [],
        next_action: [],
        trend: [],
        setup: [],
        pnl: [],
        currentness: [],
        evidence: [],
    };

    const MY_PORTFOLIO_ATTENTION_FILTERS = [
        "review_hold_tight",
        "exit_risk",
        "stale_data",
        "unavailable_evidence",
    ];

    const MY_PORTFOLIO_QUEUE_REASON_LABELS = {
        review_hold_tight: "Review / Hold Tight",
        exit_risk: "Exit Risk",
        next_action_exit: "Exit",
        next_action_watch: "Watch",
        next_action_add: "Add",
        status_at_risk: "At Risk",
        status_caution: "Caution",
    };

    const MY_PORTFOLIO_EXPORT_COLUMNS = {
        snapshot: [
            ["no", "No."],
            ["symbol", "Symbol"],
            ["quantity", "Qty"],
            ["avg_price", "Avg Price"],
            ["last_price", "Last Price"],
            ["price_as_of", "Price As Of"],
            ["investment", "Investment"],
            ["current_value", "Current Value"],
            ["pnl", "P&L"],
            ["pnl_pct", "P&L %"],
            ["status", "Status"],
            ["conviction", "Conviction"],
            ["trend_setup", "Trend / Setup"],
            ["daily_review_status", "Daily Review Status"],
            ["supertrend_direction", "SuperTrend Direction"],
            ["supertrend_value", "SuperTrend Value"],
            ["rsi14", "RSI14"],
            ["volume", "Volume"],
            ["volume_ma20", "Volume MA20"],
            ["next_action", "Next Action"],
            ["plan_trigger", "Plan Trigger"],
            ["plan_stop", "Plan Stop"],
            ["plan_t1", "Plan T1"],
            ["structural_support_1", "Structural Support 1"],
            ["structural_major_support", "Structural Major Support"],
            ["structural_review_trigger", "Structural Review Trigger"],
            ["structural_target_1", "Structural Target 1"],
            ["structural_target_2", "Structural Target 2"],
            ["structural_target_3", "Structural Target 3"],
            ["exit_risk", "Exit Risk"],
            ["daily_guidance", "Daily Guidance"],
            ["structural_guidance", "Structural Guidance"],
            ["last_review", "Last Review"],
            ["snapshot_id", "Snapshot ID"],
            ["snapshot_currentness", "Snapshot Currentness"],
        ],
        holdings: [
            ["no", "No."],
            ["instrument_id", "Instrument ID"],
            ["symbol", "Symbol"],
            ["quantity", "Qty"],
            ["avg_price", "Avg Price"],
            ["investment", "Investment"],
            ["imported_at", "Imported At"],
            ["updated_at", "Updated At"],
            ["source_import_id", "Source Import ID"],
            ["source_row_id", "Source Row ID"],
        ],
        imports: [
            ["no", "No."],
            ["import_id", "Import ID"],
            ["filename", "Filename"],
            ["source", "Source"],
            ["uploaded_at", "Uploaded At"],
            ["confirmed_at", "Confirmed At"],
            ["status", "Status"],
            ["total_rows", "Total Rows"],
            ["accepted_rows", "Accepted Rows"],
            ["rejected_rows", "Rejected Rows"],
            ["unresolved_rows", "Unresolved Rows"],
            ["ambiguous_rows", "Ambiguous Rows"],
            ["parser_version", "Parser Version"],
        ],
    };

    const MY_PORTFOLIO_EXPORT_PRESETS = {
        snapshot: {
            essential: ["no", "symbol", "quantity", "last_price", "current_value", "pnl", "pnl_pct", "next_action"],
            review: [
                "no",
                "symbol",
                "status",
                "conviction",
                "trend_setup",
                "daily_review_status",
                "next_action",
                "structural_support_1",
                "structural_target_1",
                "daily_guidance",
                "structural_guidance",
            ],
        },
        holdings: {
            essential: ["no", "symbol", "quantity", "avg_price", "investment"],
            review: ["no", "instrument_id", "symbol", "quantity", "avg_price", "investment", "updated_at"],
        },
        imports: {
            essential: ["no", "filename", "status", "accepted_rows", "rejected_rows", "unresolved_rows"],
            review: [
                "no",
                "import_id",
                "filename",
                "uploaded_at",
                "confirmed_at",
                "status",
                "total_rows",
                "accepted_rows",
                "rejected_rows",
                "unresolved_rows",
                "ambiguous_rows",
            ],
            daily_review: [
                "no",
                "filename",
                "uploaded_at",
                "confirmed_at",
                "status",
                "accepted_rows",
                "rejected_rows",
            ],
            private_sharing: ["no", "filename", "status", "uploaded_at", "confirmed_at"],
        },
    };

    MY_PORTFOLIO_EXPORT_PRESETS.snapshot.daily_review = [
        "no",
        "symbol",
        "status",
        "daily_review_status",
        "supertrend_direction",
        "next_action",
        "daily_guidance",
    ];
    MY_PORTFOLIO_EXPORT_PRESETS.snapshot.private_sharing = [
        "no",
        "symbol",
        "status",
        "conviction",
        "trend_setup",
        "daily_review_status",
        "next_action",
        "daily_guidance",
    ];
    MY_PORTFOLIO_EXPORT_PRESETS.holdings.daily_review = MY_PORTFOLIO_EXPORT_PRESETS.holdings.review;
    MY_PORTFOLIO_EXPORT_PRESETS.holdings.private_sharing = ["no", "symbol", "imported_at", "updated_at"];

    const MY_PORTFOLIO_HEATMAP_SIZES = {
        current_value: { id: "current_value", label: "Current value" },
        investment: { id: "investment", label: "Investment" },
    };
    const MY_PORTFOLIO_HEATMAP_COLORS = {
        pnl_pct: { id: "pnl_pct", label: "P&L %" },
        status: { id: "status", label: "Status" },
        daily_review: { id: "daily_review", label: "Daily Review" },
        trend: { id: "trend", label: "Trend" },
        next_action: { id: "next_action", label: "Next Action" },
    };
    const MY_PORTFOLIO_TABLE_PROFILES = {
        compact_scan: {
            id: "compact_scan",
            label: "Compact Scan",
            density: "compact",
            sort: { key: "pnl_pct", direction: "desc" },
        },
        pnl_review: {
            id: "pnl_review",
            label: "P&L Review",
            density: "comfortable",
            sort: { key: "pnl_pct", direction: "desc" },
        },
        technical_review: {
            id: "technical_review",
            label: "Technical Review",
            density: "comfortable",
            sort: { key: "daily_review", direction: "desc" },
        },
        risk_review: {
            id: "risk_review",
            label: "Risk Review",
            density: "comfortable",
            sort: { key: "status", direction: "desc" },
        },
        full_audit: {
            id: "full_audit",
            label: "Full Audit",
            density: "comfortable",
            sort: { key: "pnl_pct", direction: "desc" },
        },
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
        if (!Number.isFinite(amount)) return "—";
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

    function myPortfolioMaskedValue(label = "Private value masked") {
        return `<span class="my-portfolio-private-value" aria-label="${escapeMyPortfolioHtml(label)}"></span>`;
    }

    function myPortfolioPrivateText(value, formatter, label = "Private portfolio value") {
        if (myPortfolioState.valuesHidden) return "••••";
        return formatter(value);
    }

    function myPortfolioPrivateHtml(value, formatter, label = "Private portfolio value") {
        if (myPortfolioState.valuesHidden) return myPortfolioMaskedValue(label);
        return escapeMyPortfolioHtml(formatter(value));
    }

    function formatMyPortfolioPrivateMoney(value) {
        return myPortfolioPrivateText(value, formatMyPortfolioMoney);
    }

    function formatMyPortfolioPrivateNumber(value) {
        return myPortfolioPrivateText(value, formatMyPortfolioNumber);
    }

    function formatMyPortfolioPrivatePct(value) {
        return myPortfolioPrivateText(value, formatMyPortfolioPct);
    }

    function renderMyPortfolioPrivacyToggle() {
        if (!myPortfolioPrivacyToggle) return;
        const hidden = Boolean(myPortfolioState.valuesHidden);
        const icon = myPortfolioPrivacyToggle.querySelector("i");
        if (icon) icon.className = hidden ? "fa-solid fa-eye-slash" : "fa-solid fa-eye";
        myPortfolioPrivacyToggle.classList.toggle("active", hidden);
        myPortfolioPrivacyToggle.setAttribute("aria-pressed", String(hidden));
        myPortfolioPrivacyToggle.setAttribute(
            "aria-label",
            hidden ? "Show private portfolio values" : "Hide private portfolio values"
        );
        myPortfolioPrivacyToggle.title = hidden ? "Show private portfolio values" : "Hide private portfolio values";
    }

    function setMyPortfolioValuesHidden(hidden) {
        myPortfolioState.valuesHidden = Boolean(hidden);
        try {
            window.localStorage.setItem("athena.myPortfolio.valuesHidden", String(myPortfolioState.valuesHidden));
        } catch (err) {
            // Browser privacy/storage restrictions should not break rendering.
        }
        renderMyPortfolioPrivacyToggle();
        renderMyPortfolioSummary();
        renderMyPortfolioHoldings(myPortfolioState.holdings || []);
        if (myPortfolioState.detailOpenKey && myPortfolioDetailModal && !myPortfolioDetailModal.hidden) {
            renderMyPortfolioDetail(myPortfolioState.snapshotRowsByKey[myPortfolioState.detailOpenKey]);
        }
    }

    function renderMyPortfolioExportPanel() {
        if (!myPortfolioExportPanel || !myPortfolioExportToggle) return;
        const expanded = !myPortfolioExportPanel.hidden;
        myPortfolioExportToggle.setAttribute("aria-expanded", String(expanded));
    }

    function currentMyPortfolioExportScope() {
        return myPortfolioExportScope?.value || "snapshot";
    }

    function selectedMyPortfolioExportColumns(scope = currentMyPortfolioExportScope()) {
        return myPortfolioState.exportColumnsByScope[scope] || null;
    }

    function setMyPortfolioExportColumns(scope, selectedColumns) {
        const available = MY_PORTFOLIO_EXPORT_COLUMNS[scope] || [];
        const allowed = new Set(available.map(([columnId]) => columnId));
        const normalized = selectedColumns.filter((columnId) => allowed.has(columnId));
        myPortfolioState.exportColumnsByScope[scope] =
            normalized.length === available.length ? null : normalized;
        renderMyPortfolioExportColumns();
    }

    function renderMyPortfolioExportColumns() {
        if (!myPortfolioExportColumns) return;
        const scope = currentMyPortfolioExportScope();
        const columns = MY_PORTFOLIO_EXPORT_COLUMNS[scope] || [];
        const selected = selectedMyPortfolioExportColumns(scope);
        const selectedSet = new Set(selected || columns.map(([columnId]) => columnId));
        myPortfolioExportColumns.innerHTML = columns
            .map(
                ([columnId, label]) => `
                    <label class="my-portfolio-export-column">
                        <input type="checkbox" value="${escapeMyPortfolioHtml(columnId)}" ${selectedSet.has(columnId) ? "checked" : ""}>
                        <span>${escapeMyPortfolioHtml(label)}</span>
                    </label>
                `
            )
            .join("");
        if (myPortfolioExportColumnCount) {
            myPortfolioExportColumnCount.textContent =
                !selected || selected.length === columns.length ? "All columns" : `${selected.length}/${columns.length} selected`;
        }
        const hasSelection = selectedSet.size > 0;
        myPortfolioExportDownload?.toggleAttribute("disabled", !hasSelection || myPortfolioState.exporting);
    }

    function applyMyPortfolioExportPreset(presetName) {
        const scope = currentMyPortfolioExportScope();
        if (presetName === "full_audit") {
            setMyPortfolioExportColumns(scope, null);
            return;
        }
        const preset = MY_PORTFOLIO_EXPORT_PRESETS[scope]?.[presetName];
        if (!preset) return;
        setMyPortfolioExportColumns(scope, preset);
    }

    function updateMyPortfolioExportSelectionFromInputs() {
        const scope = currentMyPortfolioExportScope();
        const selected = Array.from(
            myPortfolioExportColumns?.querySelectorAll('input[type="checkbox"]:checked') || []
        ).map(input => input.value);
        setMyPortfolioExportColumns(scope, selected);
    }

    function setMyPortfolioExportStatus(message, tone = "neutral") {
        if (!myPortfolioExportStatus) return;
        myPortfolioExportStatus.textContent = message;
        myPortfolioExportStatus.dataset.tone = tone;
    }

    function myPortfolioExportFilename(response, fallback) {
        const disposition = response.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename="([^"]+)"/i);
        return match ? match[1] : fallback;
    }

    async function downloadMyPortfolioExport() {
        if (myPortfolioState.exporting) return;
        const scope = currentMyPortfolioExportScope();
        const format = myPortfolioExportFormat?.value || "xlsx";
        const selectedColumns = selectedMyPortfolioExportColumns(scope);
        if (Array.isArray(selectedColumns) && selectedColumns.length === 0) {
            setMyPortfolioExportStatus("Select at least one column to export.", "danger");
            return;
        }
        myPortfolioState.exporting = true;
        myPortfolioExportDownload?.setAttribute("disabled", "disabled");
        setMyPortfolioExportStatus("Preparing export…", "neutral");
        try {
            const headers = {};
            const accessToken = getAccessToken();
            if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
            const params = new URLSearchParams({ scope, format });
            if (selectedColumns?.length) params.set("columns", selectedColumns.join(","));
            const response = await fetch(
                `/api/v1/my-portfolio/export?${params.toString()}`,
                { headers }
            );
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const detail = errorData?.detail || errorData?.title || `Export failed (${response.status})`;
                throw new Error(typeof detail === "string" ? detail : "Export failed");
            }
            const blob = await response.blob();
            const filename = myPortfolioExportFilename(
                response,
                `athena-my-portfolio-${scope}.${format}`
            );
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = filename;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            URL.revokeObjectURL(url);
            setMyPortfolioExportStatus(`Downloaded ${filename}`, "good");
        } catch (err) {
            console.error("Failed to export My Portfolio", err);
            setMyPortfolioExportStatus(err?.message || "Could not export My Portfolio.", "danger");
            showToast(err?.message || "Could not export My Portfolio.", "danger");
        } finally {
            myPortfolioState.exporting = false;
            myPortfolioExportDownload?.removeAttribute("disabled");
        }
    }

    function formatMyPortfolioTime(value) {
        if (!value) return "—";
        return String(formatDecisionTime(value)).replace(/([ap]m)IST$/i, "$1 IST");
    }

    function myPortfolioSessionDateKey(value) {
        const dt = new Date(value);
        if (Number.isNaN(dt.getTime())) return "";
        return new Intl.DateTimeFormat("en-CA", {
            timeZone: "Asia/Kolkata",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }).format(dt);
    }

    function myPortfolioMarketSessionLabel(snapshot) {
        const rows = snapshot?.rows || [];
        if (!rows.length) {
            const fallback = snapshot?.summary?.market_data_through;
            return fallback
                ? `Latest accepted market session through ${formatMyPortfolioTime(fallback)}`
                : "Latest accepted market session unavailable";
        }
        const groups = new Map();
        for (const row of rows) {
            const raw = row.price_as_of;
            const key = raw ? myPortfolioSessionDateKey(raw) : "unavailable";
            const group = groups.get(key) || { count: 0, symbols: [], raw: raw || null };
            group.count += 1;
            group.symbols.push(row.symbol);
            groups.set(key, group);
        }
        const dated = [...groups.entries()]
            .filter(([key]) => key !== "unavailable")
            .sort((left, right) => {
                if (right[1].count !== left[1].count) return right[1].count - left[1].count;
                return String(right[0]).localeCompare(String(left[0]));
            });
        if (!dated.length) return "Latest accepted market session unavailable";
        const [majorityKey, majority] = dated[0];
        const through = formatMyPortfolioTime(majority.raw);
        const stale = dated.filter(([key]) => key !== majorityKey);
        const missing = groups.get("unavailable");
        if (!stale.length && !missing) {
            return `Latest accepted market session through ${through}`;
        }
        const parts = [`${majority.count} holdings through ${through}`];
        for (const [, group] of stale) {
            const names = group.symbols.length <= 3
                ? group.symbols.join(", ")
                : `${group.symbols.length} holdings`;
            parts.push(`${names} through ${formatMyPortfolioTime(group.raw)}`);
        }
        if (missing) {
            parts.push(`${missing.count} holding${missing.count === 1 ? "" : "s"} have no accepted session`);
        }
        return parts.join("; ");
    }

    const MY_PORTFOLIO_SORT_LABELS = {
        symbol: "Symbol",
        quantity: "Qty",
        avg_price: "Avg Price",
        last_price: "Last Price",
        pnl: "P&L",
        pnl_pct: "P&L %",
        status: "Status",
        conviction: "Conviction",
        trend: "Trend / Setup",
        daily_review: "Daily Review",
        next_action: "Next Action",
    };

    const MY_PORTFOLIO_SORT_RANKS = {
        conviction: { HIGH: 3, MEDIUM: 2, LOW: 1 },
        next_action: { EXIT: 4, ADD: 3, WATCH: 2, HOLD: 1 },
        status: { AT_RISK: 4, CAUTION: 3, HEALTHY: 2, STRONG: 1, UNAVAILABLE: 0 },
        daily_review: { HOLD_STRONG: 3, HOLD: 2, REVIEW_HOLD_TIGHT: 1 },
    };

    function myPortfolioNumericSortValue(value) {
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function myPortfolioSortValue(row, key) {
        if (key === "quantity") return myPortfolioNumericSortValue(row.qty ?? row.quantity);
        if (["avg_price", "last_price", "pnl", "pnl_pct"].includes(key)) {
            return myPortfolioNumericSortValue(row[key]);
        }
        if (key === "conviction" || key === "next_action" || key === "status") {
            const label = String(row[key] || "").toUpperCase();
            return MY_PORTFOLIO_SORT_RANKS[key][label] ?? -1;
        }
        if (key === "daily_review") {
            const label = String(row?.daily_review?.review_status || "").toUpperCase();
            return MY_PORTFOLIO_SORT_RANKS.daily_review[label] ?? -1;
        }
        if (key === "trend") return String(row.trend_or_setup || "");
        if (key === "symbol") return String(row.symbol || bareMyPortfolioSymbol(row.instrument_id) || "");
        return String(row[key] || "");
    }

    function myPortfolioCompareValues(left, right, direction) {
        const leftMissing = left == null || left === "";
        const rightMissing = right == null || right === "";
        if (leftMissing && rightMissing) return 0;
        if (leftMissing) return 1;
        if (rightMissing) return -1;
        if (typeof left === "number" && typeof right === "number") {
            return direction === "asc" ? left - right : right - left;
        }
        const compared = String(left).localeCompare(String(right), "en", {
            numeric: true,
            sensitivity: "base",
        });
        return direction === "asc" ? compared : -compared;
    }

    function sortedMyPortfolioRows(rows) {
        const key = myPortfolioState.sort.key;
        const direction = myPortfolioState.sort.direction;
        return [...(rows || [])].sort((left, right) => {
            const leftPinned = myPortfolioIsPinned(myPortfolioPinKey(left));
            const rightPinned = myPortfolioIsPinned(myPortfolioPinKey(right));
            if (leftPinned !== rightPinned) return leftPinned ? -1 : 1;
            const primary = myPortfolioCompareValues(
                myPortfolioSortValue(left, key),
                myPortfolioSortValue(right, key),
                direction
            );
            if (primary !== 0) return primary;
            return String(left.symbol || left.instrument_id || "").localeCompare(
                String(right.symbol || right.instrument_id || ""),
                "en",
                { numeric: true, sensitivity: "base" }
            );
        });
    }

    function renderMyPortfolioSortControls() {
        const key = myPortfolioState.sort.key;
        const direction = myPortfolioState.sort.direction;
        if (myPortfolioSortField) myPortfolioSortField.value = key;
        if (myPortfolioSortDirection) {
            const icon = myPortfolioSortDirection.querySelector("i");
            if (icon) {
                icon.className = direction === "asc"
                    ? "fa-solid fa-arrow-up-wide-short"
                    : "fa-solid fa-arrow-down-wide-short";
            }
            myPortfolioSortDirection.title = direction === "asc"
                ? "Sort ascending. Click for descending."
                : "Sort descending. Click for ascending.";
        }
        if (myPortfolioSortSummary) {
            const label = MY_PORTFOLIO_SORT_LABELS[key] || key;
            myPortfolioSortSummary.textContent = `Sorted by ${label} ${direction === "asc" ? "low to high" : "high to low"}.`;
        }
        document.querySelectorAll(".my-portfolio-wide-table th[data-sort-key]").forEach(th => {
            const label = th.textContent.replace(/[↑↓]/g, "").trim();
            const sortKey = th.getAttribute("data-sort-key");
            th.innerHTML = myPortfolioHeader(label, sortKey);
            th.classList.toggle("active", sortKey === key);
            th.setAttribute("aria-sort", sortKey === key ? (direction === "asc" ? "ascending" : "descending") : "none");
        });
        if (myPortfolioMiniSort) {
            const label = MY_PORTFOLIO_SORT_LABELS[key] || key;
            myPortfolioMiniSort.textContent = `${label} ${direction === "asc" ? "low to high" : "high to low"}`;
        }
    }

    function currentMyPortfolioTableProfile() {
        return MY_PORTFOLIO_TABLE_PROFILES[myPortfolioState.tableProfile] || MY_PORTFOLIO_TABLE_PROFILES.compact_scan;
    }

    function applyMyPortfolioTableChrome(table) {
        if (!table) return;
        const comfortable = myPortfolioState.density === "comfortable";
        const profileId = currentMyPortfolioTableProfile().id;
        table.classList.toggle("comfortable-density", comfortable);
        table.classList.toggle("compact-density", !comfortable);
        table.setAttribute("data-table-profile", profileId);
    }

    function renderMyPortfolioDensityControls() {
        const profileId = currentMyPortfolioTableProfile().id;
        applyMyPortfolioTableChrome(myPortfolioHoldingsTable);
        applyMyPortfolioTableChrome(myPortfolioTheadClone);
        myPortfolioHoldingsScroll?.classList.toggle("comfortable-density", myPortfolioState.density === "comfortable");
        myPortfolioHoldingsScroll?.classList.toggle("compact-density", myPortfolioState.density !== "comfortable");
        myPortfolioHoldingsScroll?.setAttribute("data-table-profile", profileId);
        if (myPortfolioTableProfile) myPortfolioTableProfile.value = profileId;
        if (myPortfolioMiniProfile) myPortfolioMiniProfile.textContent = currentMyPortfolioTableProfile().label;
        scheduleMyPortfolioHoldingsScrollChrome();
    }

    function persistMyPortfolioTableProfile(profileId) {
        try {
            window.localStorage.setItem("athena.myPortfolio.tableProfile", profileId);
        } catch (err) {
            // Browser privacy/storage restrictions should not break rendering.
        }
    }

    function persistMyPortfolioPins() {
        try {
            window.localStorage.setItem(
                "athena.myPortfolio.pinnedInstrumentIds",
                JSON.stringify(myPortfolioState.pinnedInstrumentIds)
            );
        } catch (err) {
            // Browser privacy/storage restrictions should not break rendering.
        }
    }

    function setMyPortfolioTableProfile(profileId, options = {}) {
        const profile = MY_PORTFOLIO_TABLE_PROFILES[profileId] || MY_PORTFOLIO_TABLE_PROFILES.compact_scan;
        myPortfolioState.tableProfile = profile.id;
        myPortfolioState.density = profile.density;
        persistMyPortfolioTableProfile(profile.id);
        if (options.applySort !== false) {
            myPortfolioState.sort = { key: profile.sort.key, direction: profile.sort.direction };
        }
        renderMyPortfolioDensityControls();
        if (options.render !== false) {
            renderMyPortfolioHoldings(myPortfolioSourceRows());
        }
        resetMyPortfolioHoldingsHorizontalScroll();
    }

    function resetMyPortfolioHoldingsHorizontalScroll() {
        if (!myPortfolioHoldingsScroll) return;
        myPortfolioHoldingsScroll.scrollLeft = 0;
    }

    function syncMyPortfolioStickyHeaderState() {
        if (!myPortfolioHoldingsCard || !myPortfolioHoldingsHeader) return;
        const cardRect = myPortfolioHoldingsCard.getBoundingClientRect();
        const headerRect = myPortfolioHoldingsHeader.getBoundingClientRect();
        const engaged = cardRect.top < headerRect.top - 1;
        myPortfolioHoldingsCard.classList.toggle("sticky-engaged", engaged);
    }

    function syncMyPortfolioTheadClone() {
        if (!myPortfolioHoldingsTable || !myPortfolioTheadClone || !myPortfolioHoldingsTable.tHead) return;
        const colgroup = myPortfolioHoldingsTable.querySelector("colgroup");
        applyMyPortfolioTableChrome(myPortfolioTheadClone);
        myPortfolioTheadClone.innerHTML = `${colgroup ? colgroup.outerHTML : ""}${myPortfolioHoldingsTable.tHead.outerHTML}`;
        myPortfolioTheadClone.style.width = `${myPortfolioHoldingsTable.scrollWidth}px`;
        myPortfolioTheadClone.style.minWidth = window.getComputedStyle(myPortfolioHoldingsTable).minWidth;
    }

    const myPortfolioNavSections = [
        { key: "overview", el: myPortfolioKpiStrip },
        { key: "triage", el: myPortfolioCommandDashboard },
        { key: "risk-heatmap", el: myPortfolioRiskPanel },
        { key: "holdings", el: myPortfolioHoldingsCard },
    ].filter(section => section.el);

    function setMyPortfolioActiveNavItem(key) {
        myPortfolioSectionNav?.querySelectorAll(".my-portfolio-section-nav-item").forEach(item => {
            item.classList.toggle("active", item.dataset.navTarget === key);
        });
    }

    // Plain, native browser positioning: scrollIntoView() honors each
    // target's own scroll-margin-top (set once, in CSS, from the same
    // --my-portfolio-section-nav-height variable the sticky header's own
    // height is measured into) rather than a hand-computed JS delta.
    // A hand-rolled scrollBy() delta was tried here and, despite passing
    // every synthetic/automated check, produced worse real-world results
    // (a target landing scrolled too far, past the header) than this
    // simpler, standard mechanism ever did — reverted rather than
    // patched further. Shared by the section nav and the pre-existing
    // "Start review" jump-to-holdings action, since both scroll a target
    // in under the same sticky header.
    function scrollMyPortfolioElementIntoView(el) {
        if (!el) return;
        el.scrollIntoView({ block: "start", behavior: "smooth", inline: "nearest" });
    }

    function scrollMyPortfolioToSection(key) {
        const section = myPortfolioNavSections.find(entry => entry.key === key);
        if (section) scrollMyPortfolioElementIntoView(section.el);
    }

    let myPortfolioNavObserver = null;

    function initMyPortfolioSectionNavObserver() {
        if (!myPortfolioSectionNav || !myPortfolioNavSections.length || typeof IntersectionObserver === "undefined") {
            return;
        }
        const stickyHeight = Math.ceil((myPortfolioStickyHeader || myPortfolioSectionNav).getBoundingClientRect().height) || 56;
        myPortfolioNavObserver = new IntersectionObserver(entries => {
            const visible = entries.filter(entry => entry.isIntersecting);
            if (!visible.length) return;
            visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
            const topKey = visible[0].target.dataset.navSectionKey;
            if (topKey) setMyPortfolioActiveNavItem(topKey);
        }, {
            root: myPortfolioWorkspaceViewport || null,
            rootMargin: `-${stickyHeight + 8}px 0px -70% 0px`,
            threshold: 0,
        });
        myPortfolioNavSections.forEach(section => {
            section.el.dataset.navSectionKey = section.key;
            myPortfolioNavObserver.observe(section.el);
        });
    }

    function syncMyPortfolioSectionNavHeight() {
        const stickyHeader = myPortfolioStickyHeader || myPortfolioSectionNav;
        if (!stickyHeader || !myPortfolioWorkstation) return 0;
        // `scrollIntoView` + `scroll-margin-top` anchors against the
        // scrolling container's own border-box top edge, not the sticky
        // header's -- the header is not flush against that edge (the
        // container's own top padding sits between them), so the header's
        // own getBoundingClientRect().height alone always undershoots by
        // that leading gap. Measure the header's bottom edge relative to
        // the container's own top instead, which captures both the leading
        // gap and the header's height in one real, live number (verified
        // empirically: height-only measurement left a consistent ~14px
        // overlap even when it ran successfully, not just when it fell
        // back to a default).
        const container = myPortfolioWorkspaceViewport || myPortfolioWorkstation;
        const stickyHeight = Math.round(
            stickyHeader.getBoundingClientRect().bottom - container.getBoundingClientRect().top
        );
        myPortfolioWorkstation.style.setProperty("--my-portfolio-section-nav-height", `${stickyHeight}px`);
        return stickyHeight;
    }

    function syncMyPortfolioTheadDock() {
        if (!myPortfolioTheadDock || !myPortfolioHoldingsHeader || !myPortfolioHoldingsScroll || !myPortfolioHoldingsTable) {
            return;
        }
        const navHeight = syncMyPortfolioSectionNavHeight();
        const headerHeight = Math.round(myPortfolioHoldingsHeader.getBoundingClientRect().height);
        myPortfolioHoldingsCard?.style.setProperty("--my-portfolio-holdings-thead-top", `${navHeight + headerHeight}px`);
        myPortfolioTheadDock.hidden = false;
        myPortfolioTheadDock.setAttribute("aria-hidden", "false");
        syncMyPortfolioTheadClone();
        if (myPortfolioTheadDockScroller) {
            myPortfolioTheadDockScroller.scrollLeft = myPortfolioHoldingsScroll.scrollLeft;
        }
    }

    let myPortfolioHoldingsChromeFrame = 0;

    function scheduleMyPortfolioHoldingsScrollChrome() {
        if (myPortfolioHoldingsChromeFrame) return;
        myPortfolioHoldingsChromeFrame = window.requestAnimationFrame(() => {
            myPortfolioHoldingsChromeFrame = 0;
            syncMyPortfolioSectionNavHeight();
            syncMyPortfolioStickyHeaderState();
            syncMyPortfolioTheadDock();
        });
    }

    function setMyPortfolioDensity(density) {
        myPortfolioState.density = density === "comfortable" ? "comfortable" : "compact";
        renderMyPortfolioDensityControls();
    }

    function myPortfolioPinKey(row) {
        return String(row?.provenance?.instrument_id || row?.instrument_id || row?.symbol || "");
    }

    function myPortfolioIsPinned(key) {
        return Boolean(key) && myPortfolioState.pinnedInstrumentIds.includes(key);
    }

    function toggleMyPortfolioPin(key) {
        if (!key) return;
        const pinned = new Set(myPortfolioState.pinnedInstrumentIds);
        if (pinned.has(key)) pinned.delete(key);
        else pinned.add(key);
        myPortfolioState.pinnedInstrumentIds = [...pinned];
        persistMyPortfolioPins();
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    }

    function renderMyPortfolioHistoryDisclosure() {
        if (!myPortfolioHistoryPanel || !myPortfolioHistoryBody || !myPortfolioHistoryToggle) return;
        const expanded = Boolean(myPortfolioState.historyExpanded);
        myPortfolioHistoryPanel.classList.toggle("collapsed", !expanded);
        myPortfolioHistoryBody.hidden = !expanded;
        myPortfolioHistoryToggle.setAttribute("aria-expanded", String(expanded));
        const label = myPortfolioHistoryToggle.querySelector("span");
        const icon = myPortfolioHistoryToggle.querySelector("i");
        if (label) label.textContent = expanded ? "Hide" : "Show";
        if (icon) icon.className = expanded ? "fa-solid fa-chevron-up" : "fa-solid fa-chevron-down";
    }

    function applyMyPortfolioSectionDisclosure(panel, body, toggle, expanded) {
        if (panel) panel.classList.toggle("collapsed", !expanded);
        if (body) body.hidden = !expanded;
        if (!toggle) return;
        toggle.setAttribute("aria-expanded", String(expanded));
        const label = toggle.querySelector("span");
        const icon = toggle.querySelector("i");
        if (label) label.textContent = expanded ? "Hide" : "Show";
        if (icon) icon.className = expanded ? "fa-solid fa-chevron-up" : "fa-solid fa-chevron-down";
    }

    function persistMyPortfolioSectionExpanded(key, expanded) {
        try {
            window.localStorage.setItem(key, String(expanded));
        } catch (err) {
            // Browser privacy/storage restrictions should not break rendering.
        }
    }

    function renderMyPortfolioRiskDisclosure() {
        applyMyPortfolioSectionDisclosure(
            myPortfolioRiskPanel,
            myPortfolioRiskBody,
            myPortfolioRiskToggle,
            Boolean(myPortfolioState.riskExpanded)
        );
    }

    function renderMyPortfolioHeatmapDisclosure() {
        applyMyPortfolioSectionDisclosure(
            myPortfolioHeatmapPanel,
            myPortfolioHeatmapBody,
            myPortfolioHeatmapToggle,
            Boolean(myPortfolioState.heatmapExpanded)
        );
    }

    function setMyPortfolioRiskExpanded(expanded) {
        myPortfolioState.riskExpanded = Boolean(expanded);
        persistMyPortfolioSectionExpanded("athena.myPortfolio.riskExpanded", myPortfolioState.riskExpanded);
        renderMyPortfolioRiskDisclosure();
    }

    function setMyPortfolioHeatmapExpanded(expanded) {
        myPortfolioState.heatmapExpanded = Boolean(expanded);
        persistMyPortfolioSectionExpanded("athena.myPortfolio.heatmapExpanded", myPortfolioState.heatmapExpanded);
        renderMyPortfolioHeatmapDisclosure();
    }

    function myPortfolioSmartFilterCount() {
        return Object.values(myPortfolioState.triage.smart).reduce((total, values) => total + (values || []).length, 0);
    }

    function renderMyPortfolioTriageFiltersDisclosure() {
        const panel = document.getElementById("my-portfolio-smart-filters-panel");
        const toggle = document.getElementById("my-portfolio-triage-filters-toggle");
        const expanded = Boolean(myPortfolioState.triageFiltersExpanded);
        if (panel) {
            panel.hidden = !expanded;
            panel.classList.toggle("collapsed", !expanded);
        }
        if (!toggle) return;
        toggle.setAttribute("aria-expanded", String(expanded));
        const label = toggle.querySelector("span");
        if (label) label.textContent = expanded ? "Hide filters" : "Filters";
    }

    function setMyPortfolioTriageFiltersExpanded(expanded) {
        myPortfolioState.triageFiltersExpanded = Boolean(expanded);
        persistMyPortfolioSectionExpanded(
            "athena.myPortfolio.triageFiltersExpanded",
            myPortfolioState.triageFiltersExpanded
        );
        renderMyPortfolioTriageFiltersDisclosure();
    }

    function myPortfolioRowStateClass(row) {
        const status = String(row?.status || "").toUpperCase();
        const action = String(row?.next_action || "").toUpperCase();
        const dailyStatus = String(row?.daily_review?.review_status || "").toUpperCase();
        const pnl = Number(row?.pnl);
        if (status === "AT_RISK" || action === "EXIT" || dailyStatus === "REVIEW_HOLD_TIGHT") return "state-danger";
        if (status === "CAUTION" || action === "WATCH") return "state-warning";
        if (status === "UNAVAILABLE" || !status) return "state-muted";
        if (Number.isFinite(pnl) && pnl < 0) return "state-negative";
        if (status === "STRONG" || status === "HEALTHY" || Number.isFinite(pnl) && pnl >= 0) return "state-positive";
        return "state-muted";
    }

    function myPortfolioUnavailableChip(label = "Unavailable") {
        return `<span class="my-portfolio-unavailable-chip"><i class="fa-solid fa-minus" aria-hidden="true"></i>${escapeMyPortfolioHtml(label)}</span>`;
    }

    function myPortfolioHeader(label, key) {
        if (!key || key !== myPortfolioState.sort.key) return escapeMyPortfolioHtml(label);
        const icon = myPortfolioState.sort.direction === "asc" ? "fa-arrow-up" : "fa-arrow-down";
        return `<span class="my-portfolio-sortable-th">${escapeMyPortfolioHtml(label)}<i class="fa-solid ${icon} my-portfolio-sort-indicator" aria-hidden="true"></i></span>`;
    }

    function bareMyPortfolioSymbol(instrumentId) {
        const raw = String(instrumentId || "");
        return raw.includes(":") ? raw.split(":").pop() : raw;
    }

    function myPortfolioStatus(label, tone = "neutral", icon = "fa-circle-info") {
        return `<span class="my-portfolio-status ${tone}"><i class="fa-solid ${icon}" aria-hidden="true"></i>${escapeMyPortfolioHtml(label)}</span>`;
    }

    function myPortfolioCell(value, className = "") {
        const attr = className ? ` class="${escapeMyPortfolioHtml(className)}"` : "";
        return `<span${attr}>${escapeMyPortfolioHtml(value)}</span>`;
    }

    function myPortfolioToneFromNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return "neutral";
        if (number > 0) return "positive";
        if (number < 0) return "negative";
        return "neutral";
    }

    function setMyPortfolioToneClass(el, value, baseClass) {
        if (!el) return;
        const tone = myPortfolioToneFromNumber(value);
        el.classList.remove(`${baseClass}-positive`, `${baseClass}-negative`, `${baseClass}-neutral`);
        el.classList.add(`${baseClass}-${tone}`);
    }

    function myPortfolioSignedCell(value, formatter, extraClass = "") {
        const tone = myPortfolioToneFromNumber(value);
        const classes = ["my-portfolio-signed-value", tone, extraClass].filter(Boolean).join(" ");
        if (myPortfolioState.valuesHidden) {
            return `<span class="${escapeMyPortfolioHtml(classes)}">${myPortfolioMaskedValue()}</span>`;
        }
        return myPortfolioCell(formatter(value), classes);
    }

    function myPortfolioPriceToneCell(value, compareTo) {
        if (value == null) return myPortfolioDash();
        const price = Number(value);
        const avg = Number(compareTo);
        const tone = Number.isFinite(price) && Number.isFinite(avg)
            ? price >= avg ? "positive" : "negative"
            : "neutral";
        if (myPortfolioState.valuesHidden) {
            return `<span class="my-portfolio-price-value ${tone}">${myPortfolioMaskedValue()}</span>`;
        }
        return myPortfolioCell(formatMyPortfolioMoney(value), `my-portfolio-price-value ${tone}`);
    }

    function myPortfolioMoneyCell(value) {
        if (myPortfolioState.valuesHidden) return myPortfolioMaskedValue();
        return myPortfolioCell(formatMyPortfolioMoney(value), "my-portfolio-nowrap");
    }

    function myPortfolioPrivateNumberCell(value) {
        if (myPortfolioState.valuesHidden) return myPortfolioMaskedValue();
        return escapeMyPortfolioHtml(formatMyPortfolioNumber(value));
    }

    function myPortfolioDash() {
        return '<span class="my-portfolio-muted-dash">-</span>';
    }

    function myPortfolioSnapshotIsStale(snapshot = myPortfolioState.snapshot) {
        return snapshot?.currentness === "STALE_HOLDINGS_CHANGED"
            || snapshot?.portfolio_changed_since_sync === true;
    }

    function myPortfolioSnapshotCurrentnessIsUnknown(snapshot = myPortfolioState.snapshot) {
        return snapshot?.currentness === "UNKNOWN";
    }

    function resetMyPortfolioTriageState() {
        myPortfolioState.triage = {
            queueView: false,
            attention: [],
            smart: {
                status: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.status],
                daily_review: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.daily_review],
                next_action: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.next_action],
                trend: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.trend],
                setup: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.setup],
                pnl: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.pnl],
                currentness: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.currentness],
                evidence: [...MY_PORTFOLIO_EMPTY_SMART_FILTERS.evidence],
            },
        };
    }

    function myPortfolioHasActiveTriage() {
        const triage = myPortfolioState.triage;
        if (triage.queueView || triage.attention.length) return true;
        return Object.values(triage.smart).some(values => values.length);
    }

    function myPortfolioSourceRows() {
        if (myPortfolioState.snapshot?.rows?.length) return myPortfolioState.snapshot.rows;
        return myPortfolioState.holdings || [];
    }

    function myPortfolioTriageContext() {
        const snapshot = myPortfolioState.snapshot;
        const hasSnapshot = Boolean(snapshot?.rows?.length);
        return {
            hasSnapshot,
            snapshotStale: myPortfolioSnapshotIsStale(snapshot),
            snapshotUnknown: myPortfolioSnapshotCurrentnessIsUnknown(snapshot),
            snapshotCurrent: hasSnapshot && !myPortfolioSnapshotIsStale(snapshot) && !myPortfolioSnapshotCurrentnessIsUnknown(snapshot),
        };
    }

    function myPortfolioDailyStatus(row) {
        return String(row?.daily_review?.review_status || "").toUpperCase();
    }

    function myPortfolioRowStatus(row) {
        return String(row?.status || "").toUpperCase();
    }

    function myPortfolioRowAction(row) {
        return String(row?.next_action || "").toUpperCase();
    }

    function myPortfolioTrendParts(row) {
        const raw = row?.trend_or_setup ? String(row.trend_or_setup).toUpperCase() : "";
        return {
            trend: raw.split("/")[0]?.trim() || "",
            setup: raw.includes("/") ? raw.split("/")[1]?.trim() || "" : "",
        };
    }

    function myPortfolioRowHasStaleProvenance(row) {
        return (row?.provenance?.interpretation_reason_codes || []).some(code =>
            String(code).startsWith("STALE_")
        );
    }

    function myPortfolioRowMatchesReviewHoldTight(row) {
        return myPortfolioDailyStatus(row) === "REVIEW_HOLD_TIGHT";
    }

    function myPortfolioRowMatchesExitRisk(row) {
        return row?.structural_review?.exit_risk === true;
    }

    function myPortfolioRowMatchesStaleData(row, ctx) {
        if (!ctx.hasSnapshot) return false;
        return ctx.snapshotStale || ctx.snapshotUnknown || myPortfolioRowHasStaleProvenance(row);
    }

    function myPortfolioRowMatchesUnavailableEvidence(row, ctx) {
        if (!ctx.hasSnapshot) return true;
        const dailyMissing = !myPortfolioDailyStatus(row);
        const statusMissing = !myPortfolioRowStatus(row) || myPortfolioRowStatus(row) === "UNAVAILABLE";
        const trendMissing = !myPortfolioTrendParts(row).trend;
        const structuralMissing = !row?.structural_review || row.structural_review.is_coherent === false;
        return dailyMissing || statusMissing || trendMissing || structuralMissing;
    }

    function myPortfolioRowIsActionable(row, ctx) {
        if (!ctx.hasSnapshot) return false;
        const status = myPortfolioRowStatus(row);
        const action = myPortfolioRowAction(row);
        return myPortfolioRowMatchesReviewHoldTight(row)
            || myPortfolioRowMatchesExitRisk(row)
            || action === "EXIT"
            || action === "WATCH"
            || action === "ADD"
            || status === "AT_RISK"
            || status === "CAUTION";
    }

    function myPortfolioRowMatchesAttentionFilter(row, filterId, ctx) {
        if (filterId === "review_hold_tight") return myPortfolioRowMatchesReviewHoldTight(row);
        if (filterId === "exit_risk") return myPortfolioRowMatchesExitRisk(row);
        if (filterId === "stale_data") return myPortfolioRowMatchesStaleData(row, ctx);
        if (filterId === "unavailable_evidence") return myPortfolioRowMatchesUnavailableEvidence(row, ctx);
        return false;
    }

    function myPortfolioRowMatchesAttentionFilters(row, ctx) {
        const selected = myPortfolioState.triage.attention;
        if (!selected.length) return true;
        return selected.some(filterId => myPortfolioRowMatchesAttentionFilter(row, filterId, ctx));
    }

    function myPortfolioRowMatchesSmartGroup(row, group, values, ctx) {
        if (!values.length) return true;
        if (group === "status") return values.includes(myPortfolioRowStatus(row));
        if (group === "daily_review") return values.includes(myPortfolioDailyStatus(row));
        if (group === "next_action") return values.includes(myPortfolioRowAction(row));
        if (group === "trend") return values.includes(myPortfolioTrendParts(row).trend);
        if (group === "setup") return values.includes(myPortfolioTrendParts(row).setup);
        if (group === "pnl") {
            const pnl = Number(row?.pnl);
            return values.some(value => {
                if (value === "unpriced") return row?.pnl == null || !Number.isFinite(pnl);
                if (value === "winner") return Number.isFinite(pnl) && pnl > 0;
                if (value === "loser") return Number.isFinite(pnl) && pnl < 0;
                return false;
            });
        }
        if (group === "currentness") {
            return values.some(value => {
                if (value === "CURRENT") return ctx.snapshotCurrent;
                if (value === "STALE") return ctx.hasSnapshot && ctx.snapshotStale;
                if (value === "UNKNOWN") return !ctx.hasSnapshot || ctx.snapshotUnknown;
                return false;
            });
        }
        if (group === "evidence") {
            return values.some(value => {
                if (value === "daily_review") return Boolean(myPortfolioDailyStatus(row));
                if (value === "structural") return row?.structural_review?.is_coherent === true;
                return false;
            });
        }
        return true;
    }

    function myPortfolioRowMatchesSmartFilters(row, ctx) {
        return Object.entries(myPortfolioState.triage.smart).every(([group, values]) =>
            myPortfolioRowMatchesSmartGroup(row, group, values, ctx)
        );
    }

    function myPortfolioRowVisible(row, ctx) {
        if (myPortfolioState.triage.queueView && !myPortfolioRowIsActionable(row, ctx)) return false;
        if (!myPortfolioRowMatchesAttentionFilters(row, ctx)) return false;
        return myPortfolioRowMatchesSmartFilters(row, ctx);
    }

    function myPortfolioVisibleRows(rows) {
        const ctx = myPortfolioTriageContext();
        return (rows || []).filter(row =>
            myPortfolioIsPinned(myPortfolioPinKey(row)) || myPortfolioRowVisible(row, ctx)
        );
    }

    function myPortfolioQueueReasons(row) {
        const reasons = [];
        if (myPortfolioRowMatchesReviewHoldTight(row)) reasons.push("review_hold_tight");
        if (myPortfolioRowMatchesExitRisk(row)) reasons.push("exit_risk");
        const action = myPortfolioRowAction(row);
        if (action === "EXIT") reasons.push("next_action_exit");
        if (action === "WATCH") reasons.push("next_action_watch");
        if (action === "ADD") reasons.push("next_action_add");
        const status = myPortfolioRowStatus(row);
        if (status === "AT_RISK") reasons.push("status_at_risk");
        if (status === "CAUTION") reasons.push("status_caution");
        return reasons;
    }

    function myPortfolioQueueReasonChips(row) {
        if (!myPortfolioState.triage.queueView) return "";
        const reasons = myPortfolioQueueReasons(row);
        if (!reasons.length) return "";
        return `<span class="my-portfolio-queue-reasons">${reasons.map(reason =>
            `<span class="my-portfolio-queue-reason">${escapeMyPortfolioHtml(MY_PORTFOLIO_QUEUE_REASON_LABELS[reason] || reason)}</span>`
        ).join("")}</span>`;
    }

    function myPortfolioChangeForRow(row) {
        const key = myPortfolioRowKey(row);
        return (myPortfolioState.changes?.rows || []).find(item => item.instrument_id === key) || null;
    }

    function myPortfolioDisplayChangeBadge(badge) {
        const text = String(badge || "");
        if (myPortfolioState.valuesHidden && /^P&L moved /i.test(text)) return "P&L moved";
        return text;
    }

    function myPortfolioChangeBadgeChips(row) {
        const change = myPortfolioChangeForRow(row);
        const badges = (change?.badges || []).filter(badge => badge !== "Removed holding");
        if (!badges.length) return "";
        return `<span class="my-portfolio-change-badges">${badges.map(badge =>
            `<span class="my-portfolio-change-badge">${escapeMyPortfolioHtml(myPortfolioDisplayChangeBadge(badge))}</span>`
        ).join("")}</span>`;
    }

    function myPortfolioChangeFieldValueHtml(field, side) {
        const raw = field?.[side];
        if (raw == null || raw === "") return "—";
        const fieldId = field.field_id;
        const privateIds = new Set(["current_value", "pnl_pct", "target_reached", "last_price"]);
        if (myPortfolioState.valuesHidden && privateIds.has(fieldId)) {
            return myPortfolioMaskedValue(`${field.label} masked`);
        }
        if (fieldId === "pnl_pct") return escapeMyPortfolioHtml(formatMyPortfolioPct(raw));
        if (fieldId === "current_value" || fieldId === "last_price" || fieldId === "target_reached") {
            return escapeMyPortfolioHtml(formatMyPortfolioMoney(raw));
        }
        if (
            fieldId === "status"
            || fieldId === "next_action"
            || fieldId === "daily_review_status"
            || fieldId === "trend"
            || fieldId === "setup"
        ) {
            return escapeMyPortfolioHtml(myPortfolioRiskLabel(raw));
        }
        return escapeMyPortfolioHtml(String(raw));
    }

    function myPortfolioChangeFieldIsGuidance(field) {
        return field?.field_id === "daily_guidance" || field?.field_id === "structural_guidance";
    }

    function myPortfolioChangeFieldDeltaHtml(field) {
        const previous = myPortfolioChangeFieldValueHtml(field, "previous");
        const current = myPortfolioChangeFieldValueHtml(field, "current");
        if (myPortfolioChangeFieldIsGuidance(field)) {
            return `<span class="my-portfolio-change-delta my-portfolio-change-delta-stack">
                <span class="my-portfolio-change-from">${previous}</span>
                <span class="my-portfolio-change-arrow" aria-hidden="true">↓</span>
                <span class="my-portfolio-change-to">${current}</span>
            </span>`;
        }
        return `<span class="my-portfolio-change-delta">${previous} → ${current}</span>`;
    }

    function myPortfolioSinceLastSyncSection(row) {
        const changes = myPortfolioState.changes;
        if (!changes) {
            return `<div class="my-portfolio-detail-section" data-detail-section="since-last-sync">
                <h4>Since last sync</h4>
                <p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Unavailable until Portfolio Sync.</span></p>
            </div>`;
        }
        const note = changes.note
            ? `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>${escapeMyPortfolioHtml(changes.note)}</span></p>`
            : "";
        const compared = changes.previous_generated_at
            ? `<p class="metric-desc">Compared with the previous snapshot from ${escapeMyPortfolioHtml(formatMyPortfolioTime(changes.previous_generated_at))}.</p>`
            : "";
        if (!changes.comparison_available) {
            return `<div class="my-portfolio-detail-section" data-detail-section="since-last-sync">
                <h4>Since last sync</h4>
                ${note || `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>No previous completed snapshot to compare.</span></p>`}
            </div>`;
        }
        const change = myPortfolioChangeForRow(row);
        if (!change) {
            return `<div class="my-portfolio-detail-section" data-detail-section="since-last-sync">
                <h4>Since last sync</h4>
                ${note}${compared}
                <p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>This holding has no previous-snapshot comparison.</span></p>
            </div>`;
        }
        const badgeHtml = (change.badges || []).length
            ? `<div class="my-portfolio-change-badges">${change.badges.map(badge =>
                `<span class="my-portfolio-change-badge">${escapeMyPortfolioHtml(myPortfolioDisplayChangeBadge(badge))}</span>`
            ).join("")}</div>`
            : "";
        let body = "";
        if (change.presence === "ADDED") {
            body = `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-plus" aria-hidden="true"></i><span>This holding was not in the previous snapshot.</span></p>`;
        } else if (!(change.fields || []).length) {
            body = `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-check" aria-hidden="true"></i><span>Latest snapshot matches the previous one. Earlier moves are in Review timeline below.</span></p>`;
        } else {
            body = `<div class="my-portfolio-detail-grid">${change.fields.map(field =>
                myPortfolioDetailRowHtml(
                    field.label,
                    myPortfolioChangeFieldDeltaHtml(field),
                    { icon: "fa-code-compare", wide: myPortfolioChangeFieldIsGuidance(field) }
                )
            ).join("")}</div>`;
        }
        return `<div class="my-portfolio-detail-section" data-detail-section="since-last-sync">
            <h4>Since last sync</h4>
            ${note}${compared}${badgeHtml}${body}
        </div>`;
    }

    function myPortfolioReviewTimelinePresence(presence) {
        if (presence === "ADDED") return "New in this snapshot";
        if (presence === "REMOVED") return "Missing from this snapshot";
        return "Changed";
    }

    function myPortfolioReviewTimelineEventHtml(event) {
        const badges = [...(event.badges || [])];
        if (event.sync_status === "PARTIAL") badges.unshift("Partial sync");
        const badgeHtml = badges.length
            ? `<div class="my-portfolio-change-badges">${badges.map(badge =>
                `<span class="my-portfolio-change-badge">${escapeMyPortfolioHtml(myPortfolioDisplayChangeBadge(badge))}</span>`
            ).join("")}</div>`
            : "";
        const when = event.generated_at
            ? escapeMyPortfolioHtml(formatMyPortfolioTime(event.generated_at))
            : "Snapshot time unavailable";
        let body = "";
        if (event.presence === "ADDED") {
            body = `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-plus" aria-hidden="true"></i><span>This holding was not in the previous snapshot.</span></p>`;
        } else if (event.presence === "REMOVED") {
            body = `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-minus" aria-hidden="true"></i><span>This holding is missing from this snapshot.</span></p>`;
        } else if ((event.fields || []).length) {
            body = `<div class="my-portfolio-detail-grid">${event.fields.map(field =>
                myPortfolioDetailRowHtml(
                    field.label,
                    myPortfolioChangeFieldDeltaHtml(field),
                    { icon: "fa-code-compare", wide: myPortfolioChangeFieldIsGuidance(field) }
                )
            ).join("")}</div>`;
        }
        return `<article class="my-portfolio-review-timeline-event">
            <p class="my-portfolio-review-timeline-meta">
                <span>${when}</span>
                <span>${escapeMyPortfolioHtml(myPortfolioReviewTimelinePresence(event.presence))}</span>
            </p>
            ${badgeHtml}${body}
        </article>`;
    }

    function myPortfolioReviewTimelineSection() {
        if (myPortfolioState.timelineLoading) {
            return `<div class="my-portfolio-detail-section" data-detail-section="review-timeline">
                <h4>Review timeline</h4>
                <p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Loading review timeline…</span></p>
            </div>`;
        }
        if (myPortfolioState.timelineError) {
            return `<div class="my-portfolio-detail-section" data-detail-section="review-timeline">
                <h4>Review timeline</h4>
                <p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Review timeline is unavailable.</span></p>
            </div>`;
        }
        const timeline = myPortfolioState.timeline;
        if (!timeline) {
            return `<div class="my-portfolio-detail-section" data-detail-section="review-timeline">
                <h4>Review timeline</h4>
                <p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Unavailable until Portfolio Sync.</span></p>
            </div>`;
        }
        const note = timeline.note
            ? `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>${escapeMyPortfolioHtml(timeline.note)}</span></p>`
            : "";
        if (!timeline.comparison_available) {
            return `<div class="my-portfolio-detail-section" data-detail-section="review-timeline">
                <h4>Review timeline</h4>
                ${note || `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Two completed snapshots are required to build a review timeline.</span></p>`}
            </div>`;
        }
        if (!(timeline.events || []).length) {
            return `<div class="my-portfolio-detail-section" data-detail-section="review-timeline">
                <h4>Review timeline</h4>
                ${note || `<p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-check" aria-hidden="true"></i><span>No tracked fields changed across recent snapshots.</span></p>`}
            </div>`;
        }
        return `<div class="my-portfolio-detail-section" data-detail-section="review-timeline">
            <h4>Review timeline</h4>
            <p class="metric-desc">Earlier snapshot history. The latest pair is in Since last sync.</p>
            ${note}
            <div class="my-portfolio-review-timeline">${timeline.events.map(myPortfolioReviewTimelineEventHtml).join("")}</div>
        </div>`;
    }

    async function loadMyPortfolioReviewTimeline(key) {
        myPortfolioState.timelineKey = key;
        myPortfolioState.timeline = null;
        myPortfolioState.timelineLoading = true;
        myPortfolioState.timelineError = false;
        try {
            const response = await apiRequest(
                `/api/v1/my-portfolio/snapshot/timeline?instrument_id=${encodeURIComponent(key)}`,
                { skipToast: true }
            );
            if (myPortfolioState.timelineKey !== key) return;
            myPortfolioState.timeline = response?.data || null;
            myPortfolioState.timelineLoading = false;
        } catch (err) {
            if (myPortfolioState.timelineKey !== key) return;
            myPortfolioState.timeline = null;
            myPortfolioState.timelineLoading = false;
            myPortfolioState.timelineError = true;
        }
        if (myPortfolioState.detailOpenKey === key) {
            const row = myPortfolioState.snapshotRowsByKey[key];
            if (row) renderMyPortfolioDetail(row);
        }
    }

    function myPortfolioRiskLabel(value) {
        const map = {
            STRONG: "Strong",
            HEALTHY: "Healthy",
            CAUTION: "Caution",
            AT_RISK: "At risk",
            HOLD_STRONG: "Hold Strong",
            REVIEW_HOLD_TIGHT: "Review / Hold Tight",
            ADD: "Add",
            EXIT: "Exit",
            WATCH: "Watch",
            HOLD: "Hold",
            UPTREND: "Uptrend",
            DOWNTREND: "Downtrend",
            MIXED: "Mixed",
            BREAKOUT: "Breakout",
            BREAKDOWN: "Breakdown",
            HIGH: "High",
            MEDIUM: "Medium",
            LOW: "Low",
            UNAVAILABLE: "Unavailable",
        };
        const key = String(value || "Unavailable").toUpperCase();
        return map[key] || String(value || "Unavailable").replaceAll("_", " ");
    }

    function myPortfolioCountEntries(rows, getter) {
        const counts = new Map();
        (rows || []).forEach(row => {
            const key = getter(row) || "Unavailable";
            counts.set(key, (counts.get(key) || 0) + 1);
        });
        return [...counts.entries()].sort((left, right) => right[1] - left[1] || String(left[0]).localeCompare(String(right[0])));
    }

    function myPortfolioRiskCountList(entries) {
        if (!entries.length) return `<p class="metric-desc">None.</p>`;
        return `<ul class="my-portfolio-risk-list">${entries.map(([key, count]) =>
            `<li><span>${escapeMyPortfolioHtml(myPortfolioRiskLabel(key))}</span><strong>${formatMyPortfolioNumber(count)}</strong></li>`
        ).join("")}</ul>`;
    }

    function myPortfolioRankedHoldings(rows, valueGetter, direction, limit, tone) {
        const ranked = (rows || [])
            .map(row => ({ row, value: valueGetter(row) }))
            .filter(item => Number.isFinite(item.value))
            .sort((left, right) => (direction === "asc" ? left.value - right.value : right.value - left.value))
            .slice(0, limit);
        if (!ranked.length) return `<p class="metric-desc">None.</p>`;
        const toneClass = tone ? ` class="tone-${escapeMyPortfolioHtml(tone)}"` : "";
        return `<ol class="my-portfolio-risk-rank">${ranked.map(item =>
            `<li${toneClass}><span title="${escapeMyPortfolioHtml(item.row.symbol || "—")}">${escapeMyPortfolioHtml(item.row.symbol || "—")}</span><strong>${myPortfolioPrivateHtml(item.value, formatMyPortfolioMoney, "Private portfolio value masked")}</strong></li>`
        ).join("")}</ol>`;
    }

    function myPortfolioExposureValue(row) {
        const current = Number(row?.current_value);
        if (Number.isFinite(current)) return current;
        const investment = Number(row?.investment);
        return Number.isFinite(investment) ? investment : NaN;
    }

    function myPortfolioPnlValue(row) {
        const pnl = Number(row?.pnl);
        return Number.isFinite(pnl) ? pnl : NaN;
    }

    function renderMyPortfolioRiskPanel() {
        if (!myPortfolioRiskBody) return;
        const rows = myPortfolioState.snapshot?.rows || [];
        const changes = myPortfolioState.changes;
        if (myPortfolioRiskLead) {
            myPortfolioRiskLead.textContent = rows.length
                ? "Factual counts and ranks from the latest snapshot. No new risk score."
                : "Unavailable until Portfolio Sync.";
        }
        if (!rows.length) {
            myPortfolioRiskBody.innerHTML = `<p class="metric-desc">Unavailable until Portfolio Sync.</p>`;
            return;
        }
        const note = changes?.note
            ? `<p class="my-portfolio-risk-note">${escapeMyPortfolioHtml(changes.note)}</p>`
            : (!changes?.comparison_available
                ? `<p class="my-portfolio-risk-note">No previous completed snapshot to compare.</p>`
                : "");
        const removed = (changes?.rows || []).filter(item => item.presence === "REMOVED");
        const removedHtml = removed.length
            ? `<div class="my-portfolio-risk-group">
                    <h4>Removed since previous snapshot</h4>
                    <ul class="my-portfolio-risk-list">${removed.map(item =>
                        `<li><span title="${escapeMyPortfolioHtml(item.symbol)}">${escapeMyPortfolioHtml(item.symbol)}</span><strong>Removed</strong></li>`
                    ).join("")}</ul>
                </div>`
            : "";
        const highConviction = rows.filter(row => String(row.conviction || "").toUpperCase() === "HIGH");
        const highConvictionPreview = highConviction.slice(0, 5);
        const highConvictionRemaining = highConviction.length - highConvictionPreview.length;
        myPortfolioRiskBody.innerHTML = `
            ${note}
            <div class="my-portfolio-risk-grid">
                <div class="my-portfolio-risk-group">
                    <h4>Status</h4>
                    ${myPortfolioRiskCountList(myPortfolioCountEntries(rows, row => row.status))}
                </div>
                <div class="my-portfolio-risk-group">
                    <h4>Trend</h4>
                    ${myPortfolioRiskCountList(myPortfolioCountEntries(rows, row => myPortfolioTrendLabelOnly(row.trend_or_setup)))}
                </div>
                <div class="my-portfolio-risk-group">
                    <h4>Next Action</h4>
                    ${myPortfolioRiskCountList(myPortfolioCountEntries(rows, row => row.next_action))}
                </div>
                <div class="my-portfolio-risk-group">
                    <h4>High conviction</h4>
                    <p class="metric-desc">${formatMyPortfolioNumber(highConviction.length)} of ${formatMyPortfolioNumber(rows.length)}</p>
                    ${highConvictionPreview.length
                        ? `<ul class="my-portfolio-risk-list">${highConvictionPreview.map(row =>
                            `<li><span>${escapeMyPortfolioHtml(row.symbol)}</span></li>`
                        ).join("")}</ul>${highConvictionRemaining
                            ? `<p class="metric-desc">+${formatMyPortfolioNumber(highConvictionRemaining)} more</p>`
                            : ""}`
                        : `<p class="metric-desc">None.</p>`}
                </div>
                <div class="my-portfolio-risk-group">
                    <h4>Top holdings</h4>
                    ${myPortfolioRankedHoldings(rows, myPortfolioExposureValue, "desc", 5)}
                </div>
                <div class="my-portfolio-risk-group">
                    <h4>Largest winners</h4>
                    ${myPortfolioRankedHoldings(rows.filter(row => myPortfolioPnlValue(row) > 0), myPortfolioPnlValue, "desc", 3, "positive")}
                </div>
                <div class="my-portfolio-risk-group">
                    <h4>Largest losers</h4>
                    ${myPortfolioRankedHoldings(rows.filter(row => myPortfolioPnlValue(row) < 0), myPortfolioPnlValue, "asc", 3, "negative")}
                </div>
                ${removedHtml}
            </div>
        `;
    }

    function myPortfolioHeatmapSizeValue(row, sizeId) {
        if (sizeId === "investment") {
            const investment = Number(row?.investment);
            return Number.isFinite(investment) && investment > 0 ? investment : NaN;
        }
        return myPortfolioExposureValue(row);
    }

    function myPortfolioHeatmapColorTone(row, colorId, privateMode) {
        if (colorId === "pnl_pct") {
            if (privateMode) return "muted";
            const pct = Number(row?.pnl_pct);
            if (!Number.isFinite(pct)) return "muted";
            if (pct > 0) return "positive";
            if (pct < 0) return "negative";
            return "muted";
        }
        if (colorId === "status") {
            const status = myPortfolioRowStatus(row);
            if (status === "HEALTHY" || status === "STRONG") return "good";
            if (status === "CAUTION") return "warning";
            if (status === "AT_RISK") return "danger";
            return "muted";
        }
        if (colorId === "daily_review") {
            const status = myPortfolioDailyStatus(row);
            if (status === "HOLD_STRONG") return "good";
            if (status === "HOLD") return "neutral";
            if (status === "REVIEW_HOLD_TIGHT") return "warning";
            return "muted";
        }
        if (colorId === "trend") {
            const trend = myPortfolioTrendLabelOnly(row?.trend_or_setup || row?.trend_setup);
            if (trend === "UPTREND") return "up";
            if (trend === "DOWNTREND") return "down";
            if (trend === "MIXED") return "mixed";
            return "muted";
        }
        const action = myPortfolioRowAction(row);
        if (action === "ADD") return "good";
        if (action === "WATCH") return "warning";
        if (action === "EXIT") return "danger";
        if (action === "HOLD") return "neutral";
        return "muted";
    }

    function myPortfolioHeatmapColorLabel(row, colorId, privateMode) {
        if (colorId === "pnl_pct") {
            if (privateMode) return "P&L hidden";
            const pct = Number(row?.pnl_pct);
            return Number.isFinite(pct) ? formatMyPortfolioPct(pct) : "P&L unavailable";
        }
        if (colorId === "status") return myPortfolioRiskLabel(myPortfolioRowStatus(row));
        if (colorId === "daily_review") {
            return myPortfolioRiskLabel(myPortfolioDailyStatus(row) || "UNAVAILABLE");
        }
        if (colorId === "trend") {
            return myPortfolioRiskLabel(
                myPortfolioTrendLabelOnly(row?.trend_or_setup || row?.trend_setup) || "UNAVAILABLE"
            );
        }
        return myPortfolioRiskLabel(myPortfolioRowAction(row));
    }

    function persistMyPortfolioHeatmap() {
        try {
            window.localStorage.setItem("athena.myPortfolio.heatmapSize", myPortfolioState.heatmap.size);
            window.localStorage.setItem("athena.myPortfolio.heatmapColor", myPortfolioState.heatmap.color);
        } catch (err) {
            // Browser privacy/storage restrictions should not break rendering.
        }
    }

    function setMyPortfolioHeatmapSize(sizeId) {
        myPortfolioState.heatmap.size = MY_PORTFOLIO_HEATMAP_SIZES[sizeId]?.id || "current_value";
        persistMyPortfolioHeatmap();
        renderMyPortfolioHeatmap();
    }

    function setMyPortfolioHeatmapColor(colorId) {
        myPortfolioState.heatmap.color = MY_PORTFOLIO_HEATMAP_COLORS[colorId]?.id || "pnl_pct";
        persistMyPortfolioHeatmap();
        renderMyPortfolioHeatmap();
    }

    function renderMyPortfolioHeatmap() {
        if (!myPortfolioHeatmapBody) return;
        const rows = myPortfolioState.snapshot?.rows || [];
        const sizeId = MY_PORTFOLIO_HEATMAP_SIZES[myPortfolioState.heatmap.size]?.id || "current_value";
        const colorId = MY_PORTFOLIO_HEATMAP_COLORS[myPortfolioState.heatmap.color]?.id || "pnl_pct";
        const privateMode = Boolean(myPortfolioState.valuesHidden);
        if (myPortfolioHeatmapSize) myPortfolioHeatmapSize.value = sizeId;
        if (myPortfolioHeatmapColor) myPortfolioHeatmapColor.value = colorId;
        if (myPortfolioHeatmapLead) {
            myPortfolioHeatmapLead.textContent = privateMode
                ? "Private values hidden. Tiles are equal size. Color uses the selected existing field except P&L %, which stays muted."
                : "Latest snapshot tiles. Size is current value or investment. Color is an existing field. Click a tile for detail. No new risk score.";
        }
        if (!rows.length) {
            myPortfolioHeatmapBody.innerHTML = `<p class="metric-desc">Unavailable until Portfolio Sync.</p>`;
            return;
        }
        const sized = rows.map(row => ({ row, value: myPortfolioHeatmapSizeValue(row, sizeId) }));
        const max = sized.reduce((acc, item) => (
            Number.isFinite(item.value) && item.value > acc ? item.value : acc
        ), 0);
        const tiles = sized
            .slice()
            .sort((left, right) => {
                const leftValue = Number.isFinite(left.value) ? left.value : -1;
                const rightValue = Number.isFinite(right.value) ? right.value : -1;
                if (rightValue !== leftValue) return rightValue - leftValue;
                return String(left.row.symbol || "").localeCompare(String(right.row.symbol || ""), "en", {
                    numeric: true,
                    sensitivity: "base",
                });
            })
            .map(item => {
                const key = myPortfolioRowKey(item.row);
                const weight = privateMode || !Number.isFinite(item.value) || !max
                    ? 1
                    : Math.max(1, Math.round((item.value / max) * 8));
                const tone = myPortfolioHeatmapColorTone(item.row, colorId, privateMode);
                const colorLabel = myPortfolioHeatmapColorLabel(item.row, colorId, privateMode);
                const sizeLabel = privateMode || !Number.isFinite(item.value)
                    ? ""
                    : formatMyPortfolioMoney(item.value);
                const title = [item.row.symbol, sizeLabel, colorLabel].filter(Boolean).join(" · ");
                return `<button type="button" class="my-portfolio-heatmap-tile tone-${escapeMyPortfolioHtml(tone)}" data-instrument-id="${escapeMyPortfolioHtml(key)}" style="flex-grow: ${weight}" title="${escapeMyPortfolioHtml(title)}" aria-label="Open detail for ${escapeMyPortfolioHtml(item.row.symbol)}">
                    <strong>${escapeMyPortfolioHtml(item.row.symbol)}</strong>
                    <span>${escapeMyPortfolioHtml(colorLabel)}</span>
                </button>`;
            })
            .join("");
        myPortfolioHeatmapBody.innerHTML = `<div class="my-portfolio-heatmap-grid">${tiles}</div>`;
    }

    function myPortfolioTriageCounts(rows = myPortfolioSourceRows()) {
        const ctx = myPortfolioTriageContext();
        const counts = {
            review_hold_tight: 0,
            exit_risk: 0,
            stale_data: 0,
            unavailable_evidence: 0,
            needs_review: 0,
        };
        (rows || []).forEach(row => {
            if (myPortfolioRowMatchesReviewHoldTight(row)) counts.review_hold_tight += 1;
            if (myPortfolioRowMatchesExitRisk(row)) counts.exit_risk += 1;
            if (myPortfolioRowMatchesStaleData(row, ctx)) counts.stale_data += 1;
            if (myPortfolioRowMatchesUnavailableEvidence(row, ctx)) counts.unavailable_evidence += 1;
            if (myPortfolioRowIsActionable(row, ctx)) counts.needs_review += 1;
        });
        return counts;
    }

    function myPortfolioTriageEmptyMessage(totalCount) {
        if (!totalCount) return "No holdings imported yet. Upload Portfolio to begin.";
        if (myPortfolioState.triage.queueView && !myPortfolioTriageContext().hasSnapshot) {
            return "Sync Portfolio to build the action queue.";
        }
        const refining = myPortfolioState.triage.attention.length
            || Object.values(myPortfolioState.triage.smart).some(values => values.length);
        if (myPortfolioState.triage.queueView && !refining) {
            return "No holdings need attention.";
        }
        if (myPortfolioState.triage.queueView) {
            return "No Action Queue holdings match the current filters.";
        }
        return "No holdings match the current triage filters.";
    }

    function scrollMyPortfolioHoldingsIntoView() {
        window.requestAnimationFrame(() => {
            if (myPortfolioHoldingsCard && myPortfolioStickyHeader && myPortfolioWorkspaceViewport) {
                scrollMyPortfolioElementIntoView(myPortfolioHoldingsCard);
            } else {
                myPortfolioHoldingsCard?.scrollIntoView({ block: "start", behavior: "smooth", inline: "nearest" });
            }
            scheduleMyPortfolioHoldingsScrollChrome();
        });
    }

    function setMyPortfolioUploadPanelOpen(open) {
        myPortfolioState.uploadPanelOpen = Boolean(open);
        const panel = myPortfolioUploadPanel;
        if (panel) {
            if (myPortfolioState.uploadPanelOpen) {
                panel.removeAttribute("inert");
                panel.style.height = `${panel.scrollHeight}px`;
                window.requestAnimationFrame(() => panel.classList.add("open"));
                window.setTimeout(() => {
                    if (myPortfolioState.uploadPanelOpen) panel.style.height = "auto";
                }, 340);
            } else {
                panel.style.height = `${panel.scrollHeight}px`;
                panel.setAttribute("inert", "");
                window.requestAnimationFrame(() => {
                    panel.classList.remove("open");
                    panel.style.height = "0px";
                });
            }
        }
        myPortfolioUploadShortcut?.setAttribute("aria-expanded", String(myPortfolioState.uploadPanelOpen));
    }

    function setMyPortfolioQueueView(queueView) {
        myPortfolioState.triage.queueView = Boolean(queueView);
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    }

    function toggleMyPortfolioAttentionFilter(filterId) {
        if (filterId === "needs_review") {
            setMyPortfolioQueueView(!myPortfolioState.triage.queueView);
            return;
        }
        if (filterId === "near_trigger" || filterId === "near_support" || filterId === "fresh_breakout") {
            return;
        }
        const selected = new Set(myPortfolioState.triage.attention);
        if (selected.has(filterId)) selected.delete(filterId);
        else selected.add(filterId);
        myPortfolioState.triage.attention = MY_PORTFOLIO_ATTENTION_FILTERS.filter(id => selected.has(id));
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    }

    function toggleMyPortfolioSmartFilter(group, value) {
        const current = new Set(myPortfolioState.triage.smart[group] || []);
        if (current.has(value)) current.delete(value);
        else current.add(value);
        myPortfolioState.triage.smart[group] = [...current];
        if (current.size && !myPortfolioState.triageFiltersExpanded) {
            setMyPortfolioTriageFiltersExpanded(true);
        }
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    }

    function clearMyPortfolioTriage() {
        resetMyPortfolioTriageState();
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    }

    function renderMyPortfolioTriage(totalCount, visibleCount) {
        const counts = myPortfolioTriageCounts();
        Object.entries(counts).forEach(([filterId, count]) => {
            const el = document.getElementById(`my-portfolio-triage-count-${filterId}`);
            if (el) el.textContent = formatMyPortfolioNumber(count);
        });
        document.querySelectorAll(".my-portfolio-triage-chip[data-triage-available='true']").forEach(chip => {
            const filterId = chip.getAttribute("data-triage-filter");
            const active = myPortfolioState.triage.attention.includes(filterId);
            chip.classList.toggle("active", active);
            chip.classList.toggle("is-quiet", !active && !Number(counts[filterId]));
            chip.setAttribute("aria-pressed", String(active));
        });
        const smartCount = myPortfolioSmartFilterCount();
        const filterCount = document.getElementById("my-portfolio-triage-filter-count");
        if (filterCount) {
            filterCount.textContent = formatMyPortfolioNumber(smartCount);
            filterCount.hidden = smartCount === 0;
        }
        renderMyPortfolioTriageFiltersDisclosure();
        document.querySelectorAll(".my-portfolio-smart-chip").forEach(chip => {
            const group = chip.getAttribute("data-smart-group");
            const value = chip.getAttribute("data-smart-value");
            const active = (myPortfolioState.triage.smart[group] || []).includes(value);
            chip.classList.toggle("active", active);
            chip.setAttribute("aria-pressed", String(active));
        });
        myPortfolioQueueAll?.classList.toggle("active", !myPortfolioState.triage.queueView);
        myPortfolioQueueOnly?.classList.toggle("active", myPortfolioState.triage.queueView);
        myPortfolioQueueAll?.setAttribute("aria-pressed", String(!myPortfolioState.triage.queueView));
        myPortfolioQueueOnly?.setAttribute("aria-pressed", String(myPortfolioState.triage.queueView));
        if (myPortfolioHoldingsScopeBadge) {
            myPortfolioHoldingsScopeBadge.hidden = !myPortfolioState.triage.queueView;
        }
        const active = myPortfolioHasActiveTriage();
        if (myPortfolioTriageClear) myPortfolioTriageClear.hidden = !active;
        let summary;
        if (myPortfolioState.triage.queueView) {
            summary = totalCount === visibleCount
                ? `Showing ${formatMyPortfolioNumber(visibleCount)} holdings in Action Queue.`
                : `Showing ${formatMyPortfolioNumber(visibleCount)} of ${formatMyPortfolioNumber(totalCount)} holdings in Action Queue.`;
        } else if (totalCount === visibleCount) {
            summary = `Showing all ${formatMyPortfolioNumber(visibleCount)} holdings.`;
        } else {
            summary = `Showing ${formatMyPortfolioNumber(visibleCount)} of ${formatMyPortfolioNumber(totalCount)} holdings.`;
        }
        if (myPortfolioTriageSummary) myPortfolioTriageSummary.textContent = summary;
        const context = myPortfolioTriageContext();
        const matchCount = myPortfolioSourceRows().filter(row => myPortfolioRowVisible(row, context)).length;
        const pinnedExtras = Math.max(0, visibleCount - matchCount);
        if (active && myPortfolioTriageSummary) {
            myPortfolioTriageSummary.textContent = matchCount
                ? `${formatMyPortfolioNumber(matchCount)} of ${formatMyPortfolioNumber(totalCount)} holdings match.`
                : "No matching holdings.";
            if (pinnedExtras) {
                myPortfolioTriageSummary.textContent += ` ${formatMyPortfolioNumber(pinnedExtras)} pinned holding${pinnedExtras === 1 ? " remains" : "s remain"} visible.`;
            }
        }
        const viewHoldings = document.getElementById("my-portfolio-view-holdings");
        if (viewHoldings) viewHoldings.disabled = visibleCount === 0;
        const viewCount = document.getElementById("my-portfolio-view-holdings-count");
        if (viewCount) viewCount.textContent = formatMyPortfolioNumber(visibleCount);
        if (myPortfolioMiniTriage) {
            myPortfolioMiniTriage.textContent = myPortfolioState.triage.queueView
                ? `Queue · ${formatMyPortfolioNumber(visibleCount)}`
                : active
                    ? `Filtered · ${formatMyPortfolioNumber(visibleCount)}`
                    : `All · ${formatMyPortfolioNumber(visibleCount)}`;
        }
        if (myPortfolioTriageLead) {
            myPortfolioTriageLead.textContent = counts.needs_review
                ? `${formatMyPortfolioNumber(counts.needs_review)} holding${counts.needs_review === 1 ? "" : "s"} need attention.`
                : myPortfolioTriageContext().hasSnapshot
                    ? "No holdings currently need attention."
                    : totalCount
                        ? "Sync Portfolio to generate the action queue."
                        : "See what deserves attention before scanning the full book.";
        }
        myPortfolioCommandDashboard?.classList.toggle("queue-active", myPortfolioState.triage.queueView);
        myPortfolioCommandDashboard?.classList.toggle("filters-active", active);
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
            TRADE_PLAN_STOP_AVAILABLE: "TradePlan stop is available as Plan Stop.",
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
            SETUP_METHODOLOGY_DEFERRED: "Legacy v2 snapshot: Setup was not available before PS-P9D. Sync Portfolio to generate v3 Setup evidence.",
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
        return [...new Set(messages)].join(" ");
    }

    function myPortfolioFieldReason(row, prefixes) {
        const codes = row?.provenance?.interpretation_reason_codes || [];
        return codes.find(code => prefixes.some(prefix => String(code).startsWith(prefix)));
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
        const title = reason ? ` title="${escapeMyPortfolioHtml(reason)}"` : "";
        return `<span${title}>${myPortfolioStatus(label, tone, icon)}</span>`;
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
        const title = reason ? ` title="${escapeMyPortfolioHtml(reason)}"` : "";
        return `<span${title}>${myPortfolioStatus(label, tone, icon)}</span>`;
    }

    function myPortfolioConvictionCell(value, row) {
        const conviction = value ? String(value).toUpperCase() : null;
        const label = conviction || "-";
        const tone = conviction === "HIGH"
            ? "good"
            : conviction === "MEDIUM"
                ? "warning"
                : conviction === "LOW"
                    ? "danger"
                    : "neutral";
        const icon = conviction === "HIGH"
            ? "fa-signal"
            : conviction === "MEDIUM"
                ? "fa-gauge-high"
                : conviction === "LOW"
                    ? "fa-signal"
                    : "fa-minus";
        const reasonCode = myPortfolioFieldReason(row, ["CONVICTION_", "CONFIDENCE_"]);
        const detail = conviction
            ? `Decision confidence: ${conviction}. Conviction reflects ATHENA Decision confidence/reliability, not buy strength.`
            : (reasonCode ? myPortfolioReasonSummary(row) : "Decision confidence evidence is unavailable.");
        return `<span title="${escapeMyPortfolioHtml(detail)}">${myPortfolioStatus(label, tone, icon)}</span>`;
    }

    function myPortfolioTrendCell(value, row) {
        const raw = value ? String(value).toUpperCase() : "";
        const version = row?.provenance?.interpretation_version || "";
        const trend = raw.split("/")[0]?.trim() || "";
        const setup = raw.includes("/") ? raw.split("/")[1]?.trim() || "" : "";
        const legacy = raw && !raw.includes("/") && !["portfolio-interpretation-v3", "portfolio-interpretation-v4"].includes(version);
        const trendMeta = {
            UPTREND: ["Uptrend", "trend-up", "fa-arrow-trend-up"],
            DOWNTREND: ["Downtrend", "trend-down", "fa-arrow-trend-down"],
            MIXED: ["Mixed", "trend-mixed", "fa-shuffle"],
        }[trend] || [trend || "Trend unavailable", "trend-neutral", "fa-minus"];
        const setupMeta = {
            BREAKOUT: ["Breakout", "setup-breakout", "fa-arrow-up-right-dots"],
            BREAKDOWN: ["Breakdown", "setup-breakdown", "fa-arrow-down-short-wide"],
        }[setup] || [legacy ? "Legacy setup" : "No setup", "setup-neutral", legacy ? "fa-clock-rotate-left" : "fa-minus"];
        const detailCodes = (row?.provenance?.interpretation_reason_codes || [])
            .filter(code => String(code).startsWith("TREND_") || String(code).startsWith("SETUP_"));
        const detail = detailCodes.length
            ? myPortfolioReasonSummary({ provenance: { interpretation_reason_codes: detailCodes } })
            : "D1 Trend / Opening Range Setup evidence.";
        return `<span class="my-portfolio-trend-stack" title="${escapeMyPortfolioHtml(detail)}">
            <span class="my-portfolio-market-chip ${trendMeta[1]}"><i class="fa-solid ${trendMeta[2]}" aria-hidden="true"></i>${escapeMyPortfolioHtml(trendMeta[0])}</span>
            <span class="my-portfolio-market-chip ${setupMeta[1]}"><i class="fa-solid ${setupMeta[2]}" aria-hidden="true"></i>${escapeMyPortfolioHtml(setupMeta[0])}</span>
        </span>`;
    }

    function myPortfolioDailyReviewDetail(review) {
        if (!review) return "Daily Review evidence is unavailable on this snapshot.";
        const parts = [];
        if (review.supertrend_direction) {
            parts.push(`SuperTrend ${review.supertrend_direction}${review.supertrend_value ? ` @ ${formatMyPortfolioMoney(review.supertrend_value)}` : ""}`);
        }
        if (review.rsi14 != null) parts.push(`RSI14 ${formatMyPortfolioNumber(review.rsi14)}`);
        if (review.volume != null && review.volume_ma20 != null) {
            parts.push(`Volume ${formatMyPortfolioNumber(review.volume)} vs VMA20 ${formatMyPortfolioNumber(review.volume_ma20)}`);
        }
        if (review.latest_high_exceeds_prior_available_high === true) {
            parts.push("latest D1 high exceeded prior available-history high");
        }
        const limitations = "Support, invalidation, targets, EXIT_RISK, and numeric Review Conviction are deferred for v0.";
        return [...parts, limitations].join(". ");
    }

    function myPortfolioDailyReviewStatusCell(review) {
        const status = String(review?.review_status || "").toUpperCase();
        const map = {
            HOLD_STRONG: ["Hold Strong", "good", "fa-circle-check"],
            HOLD: ["Hold", "neutral", "fa-pause"],
            REVIEW_HOLD_TIGHT: ["Review / Hold Tight", "warning", "fa-triangle-exclamation"],
        };
        if (!status || !map[status]) {
            return `<span title="${escapeMyPortfolioHtml(myPortfolioDailyReviewDetail(review))}">${myPortfolioStatus("Unavailable", "neutral", "fa-circle-info")}</span>`;
        }
        const [label, tone, icon] = map[status];
        return `<span title="${escapeMyPortfolioHtml(myPortfolioDailyReviewDetail(review))}">${myPortfolioStatus(label, tone, icon)}</span>`;
    }

    // MY-PORTFOLIO-V1-FINAL-UX-CLOSURE: extract just the D1 Trend half of
    // the existing "TREND / SETUP" composite string (e.g. "UPTREND / -").
    // Presentation-only parsing of an already-computed field — no new
    // classification.
    function myPortfolioTrendLabelOnly(value) {
        if (!value) return null;
        const label = String(value).toUpperCase().split("/")[0].trim();
        return label && label !== "-" ? label : null;
    }

    // Short, presentation-only Daily Review summary composed from fields
    // already on the row (SuperTrend direction, D1 Trend label, and the
    // new-available-history-high flag). Never changes review_status.
    function myPortfolioDailyReviewSummary(review, trendLabel) {
        const status = String(review?.review_status || "").toUpperCase();
        const direction = review?.supertrend_direction ? String(review.supertrend_direction).toUpperCase() : null;
        const stPhrase = direction === "BULLISH" ? "Bullish ST" : direction === "BEARISH" ? "Bearish ST" : "ST unavailable";
        if (status === "HOLD_STRONG") {
            return `${stPhrase} · new available-history high`;
        }
        if (status === "HOLD" || status === "REVIEW_HOLD_TIGHT") {
            return trendLabel ? `${stPhrase} · D1 ${trendLabel.toLowerCase()}` : stPhrase;
        }
        const reason = review?.availability_reason;
        if (reason === "EVIDENCE_STALE_OR_SESSION_MISMATCH") return "D1 evidence stale";
        if (reason === "EVIDENCE_INCOHERENT") return "D1 evidence incoherent";
        return "D1 evidence unavailable";
    }

    // Combines the frozen Daily Review status pill with the concise summary
    // above into one main-table cell, replacing the old separate Daily
    // Guidance column. Full guidance text moves to the detail drawer.
    function myPortfolioDailyReviewCell(row) {
        const review = row?.daily_review;
        const pill = myPortfolioDailyReviewStatusCell(review);
        const trendLabel = myPortfolioTrendLabelOnly(row?.trend_or_setup);
        const summary = myPortfolioDailyReviewSummary(review, trendLabel);
        return `<span class="my-portfolio-daily-review-cell">${pill}<span class="my-portfolio-daily-review-summary">${escapeMyPortfolioHtml(summary)}</span></span>`;
    }

    const MY_PORTFOLIO_DAILY_REVIEW_REASON_LABELS = {
        EVIDENCE_INCOHERENT: "D1 evidence is not coherent for this holding.",
        EVIDENCE_STALE_OR_SESSION_MISMATCH: "D1 evidence is stale for the accepted Portfolio session.",
        EVIDENCE_UNAVAILABLE_OR_INSUFFICIENT_HISTORY: "Completed D1 evidence is unavailable or insufficient.",
        BULLISH_TRAILING_STRUCTURE_INTACT: "Bullish SuperTrend trailing structure remains intact.",
        NEW_AVAILABLE_HISTORY_HIGH: "Latest D1 high exceeded the prior available-history high.",
        BEARISH_TRAILING_STRUCTURE_REVIEW: "Price is below bearish SuperTrend evidence.",
        PROFIT_CUSHION_PROTECT_WINNER_CONTEXT: "Position is in profit — context only, does not change Review Status.",
        LOSS_CONTEXT_REVIEW_DISCIPLINE: "Position is at a loss — context only, does not change Review Status.",
        VOLUME_CONTEXT_ONLY: "Volume vs 20-day average is context only; no expansion/compression threshold.",
        SUPPORT_METHOD_DEFERRED: "Support 1 is intentionally unavailable in Portfolio v0.",
        TARGET_METHOD_DEFERRED: "Target 2/3 are intentionally unavailable in Portfolio v0.",
        EXIT_RISK_DEFERRED: "EXIT_RISK is intentionally unavailable in Portfolio v0.",
        REVIEW_CONVICTION_DEFERRED: "Numeric Review Conviction is intentionally unavailable in Portfolio v0.",
        UNADJUSTED_HISTORY_LIMITATION: "Available D1 history is not corporate-action adjusted.",
    };

    function myPortfolioDailyReviewReasonSummary(row) {
        const codes = row?.provenance?.daily_review_reason_codes || [];
        const messages = codes.map(code => MY_PORTFOLIO_DAILY_REVIEW_REASON_LABELS[code]).filter(Boolean);
        return [...new Set(messages)];
    }

    // Compact Plan Levels cell: only genuine TradePlan-derived values, one
    // per line, with truthful labels. Support 1/Target 2/Target 3 are never
    // referenced here (frozen PS-P10C.1 NO-GO) — a TradePlan stop is a plan
    // value, not the rejected structural-support methodology, so it is
    // never given that label (Owner Correction 2).
    function myPortfolioPlanLevelsCell(row) {
        const lines = [];
        if (row?.key_trigger != null && row.key_trigger !== "") {
            lines.push(`<span><i class="fa-solid fa-bolt" aria-hidden="true"></i>Plan Trigger ${escapeMyPortfolioHtml(formatMyPortfolioMoney(row.key_trigger))}</span>`);
        }
        if (row?.major_support_exit != null) {
            lines.push(`<span><i class="fa-solid fa-shield-halved" aria-hidden="true"></i>Plan Stop ${escapeMyPortfolioHtml(formatMyPortfolioMoney(row.major_support_exit))}</span>`);
        }
        if (row?.target_1 != null) {
            lines.push(`<span><i class="fa-solid fa-location-arrow" aria-hidden="true"></i>Plan T1 ${escapeMyPortfolioHtml(formatMyPortfolioMoney(row.target_1))}</span>`);
        }
        if (!lines.length) {
            return `<span class="my-portfolio-muted-dash">No plan levels</span>`;
        }
        return `<span class="my-portfolio-levels">${lines.join("")}</span>`;
    }

    // Compact Freshness cell: collapses Price As Of + Last Review into one
    // main-table affordance; the full freshness chain lives in the drawer.
    function myPortfolioFreshnessCell(row) {
        const priceAsOf = row?.price_as_of ? formatMyPortfolioTime(row.price_as_of) : null;
        const lastReview = row?.last_review ? formatMyPortfolioTime(row.last_review) : null;
        const label = priceAsOf || "Not available";
        const detailParts = [];
        if (priceAsOf) detailParts.push(`Price as of ${priceAsOf}`);
        if (lastReview) detailParts.push(`Last reviewed ${lastReview}`);
        const detail = detailParts.length ? detailParts.join(" · ") : "Freshness evidence unavailable.";
        return `<span class="my-portfolio-freshness-cell" title="${escapeMyPortfolioHtml(detail)}"><i class="fa-regular fa-clock" aria-hidden="true"></i>${escapeMyPortfolioHtml(label)}</span>`;
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
        // Confirming is best-effort per row, never all-or-nothing: a
        // structurally invalid row, an unresolved symbol (auto-onboarded if
        // possible), or a duplicate is excluded and reported rather than
        // blocking every other valid row — so the only client-side
        // precondition is that there's a real preview with at least one row
        // to try. The server is the sole source of truth for what actually
        // confirms; it refuses only if truly nothing in the file could be.
        return Boolean(preview) && preview.status === "PREVIEWED" && Number(preview.total_rows || 0) > 0;
    }

    function myPortfolioPreviewIssueSummary(preview) {
        const rows = preview?.rows || [];
        return rows
            .filter(row => (row.validation_errors || []).length || String(row.mapping_state || "").toUpperCase() !== "RESOLVED")
            .slice(0, 5)
            .map(row => {
                const reasons = [
                    ...(row.validation_errors || []),
                    String(row.mapping_state || "").toUpperCase() === "RESOLVED" ? "" : String(row.mapping_state || "UNRESOLVED").toUpperCase(),
                ].filter(Boolean);
                return `${row.raw_symbol || row.normalized_symbol || row.source_row_id}: ${reasons.join(", ")}`;
            });
    }

    function renderMyPortfolioInlinePreview(preview) {
        if (!myPortfolioInlinePreview) return;
        if (!preview) {
            myPortfolioInlinePreview.hidden = true;
            if (myPortfolioPreviewIssues) {
                myPortfolioPreviewIssues.hidden = true;
                myPortfolioPreviewIssues.innerHTML = "";
            }
            return;
        }
        const duplicates = countMyPortfolioDuplicateRows(preview);
        const skipped = Number(preview.rejected_rows || 0)
            + Number(preview.unresolved_rows || 0)
            + Number(preview.ambiguous_rows || 0)
            + duplicates;
        if (myPortfolioInlineTotal) myPortfolioInlineTotal.textContent = formatMyPortfolioNumber(preview.total_rows);
        if (myPortfolioInlineValid) myPortfolioInlineValid.textContent = formatMyPortfolioNumber(preview.accepted_rows);
        if (myPortfolioInlineSkipped) myPortfolioInlineSkipped.textContent = formatMyPortfolioNumber(skipped);
        if (myPortfolioInlineDuplicates) myPortfolioInlineDuplicates.textContent = formatMyPortfolioNumber(duplicates);
        myPortfolioInlinePreview.hidden = false;
        const issues = myPortfolioPreviewIssueSummary(preview);
        if (myPortfolioPreviewIssues) {
            if (issues.length) {
                myPortfolioPreviewIssues.hidden = false;
                myPortfolioPreviewIssues.innerHTML = issues
                    .map(issue => `<span>${escapeMyPortfolioHtml(issue)}</span>`)
                    .join("");
            } else {
                myPortfolioPreviewIssues.hidden = true;
                myPortfolioPreviewIssues.innerHTML = "";
            }
        }
    }

    function setMyPortfolioUploadStage(stage) {
        document.querySelectorAll("[data-upload-step]").forEach(stepEl => {
            const step = stepEl.getAttribute("data-upload-step");
            stepEl.classList.toggle("active", step === stage);
            stepEl.classList.toggle("done", (
                (stage === "preview" && step === "choose")
                || (stage === "confirm" && (step === "choose" || step === "preview"))
            ));
        });
    }

    function setMyPortfolioBusy(next = {}) {
        myPortfolioState.previewing = Boolean(next.previewing);
        myPortfolioState.confirming = Boolean(next.confirming);
        if (Object.prototype.hasOwnProperty.call(next, "syncing")) {
            myPortfolioState.syncing = Boolean(next.syncing);
        }
        const busy = myPortfolioState.previewing || myPortfolioState.confirming || myPortfolioState.syncing;
        if (myPortfolioFileInput) myPortfolioFileInput.disabled = busy;
        if (myPortfolioCancelPreview) {
            myPortfolioCancelPreview.disabled = busy || !myPortfolioState.preview;
        }
        if (myPortfolioConfirm) {
            myPortfolioConfirm.disabled = busy || !previewCanConfirm(myPortfolioState.preview);
            const label = myPortfolioConfirm.querySelector("span");
            if (label) label.textContent = myPortfolioState.confirming ? "Confirming & Syncing" : "Confirm & Sync Portfolio";
        }
        if (myPortfolioConfirmActions) {
            myPortfolioConfirmActions.hidden = !myPortfolioState.preview;
        }
        if (myPortfolioPreviewOpen) {
            myPortfolioPreviewOpen.disabled = busy || !myPortfolioState.preview;
        }
        if (myPortfolioSync) {
            myPortfolioSync.disabled = myPortfolioState.syncing;
            const label = myPortfolioSync.querySelector("span");
            if (label) label.textContent = myPortfolioState.syncing ? "Syncing Portfolio" : "Sync Portfolio";
        }
        if (myPortfolioResetOpen) {
            myPortfolioResetOpen.disabled = myPortfolioState.syncing || myPortfolioState.previewing || myPortfolioState.confirming;
        }
        if (myPortfolioState.confirming) {
            setMyPortfolioUploadStage("confirm");
        } else if (myPortfolioState.previewing) {
            setMyPortfolioUploadStage("preview");
        } else if (myPortfolioState.preview) {
            setMyPortfolioUploadStage("preview");
        } else {
            setMyPortfolioUploadStage("choose");
        }
    }

    function setMyPortfolioCancelLabel(label) {
        if (myPortfolioCancelPreview) myPortfolioCancelPreview.textContent = label;
    }

    async function loadMyPortfolioWorkspace() {
        if (!myPortfolioHoldingsRows) return;
        myPortfolioState.loading = true;
        clearMyPortfolioAlert();
        myPortfolioHoldingsRows.innerHTML = '<tr><td colspan="15" class="text-center text-muted">Loading holdings...</td></tr>';
        myPortfolioHistoryRows.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Loading import history...</td></tr>';
        try {
            const [holdingsRes, historyRes, notesRes] = await Promise.all([
                apiRequest("/api/v1/my-portfolio/holdings", { skipToast: true }),
                apiRequest("/api/v1/my-portfolio/imports", { skipToast: true }),
                apiRequest("/api/v1/my-portfolio/notes", { skipToast: true }).catch(() => ({ data: [] })),
            ]);
            myPortfolioState.holdings = holdingsRes?.data || [];
            myPortfolioState.imports = historyRes?.data?.imports || [];
            myPortfolioState.notes = myPortfolioNotesById(notesRes?.data || []);
            try {
                const snapshotRes = await apiRequest("/api/v1/my-portfolio/snapshot", { skipToast: true });
                myPortfolioState.snapshot = snapshotRes?.data || null;
            } catch (snapshotErr) {
                myPortfolioState.snapshot = null;
            }
            if (myPortfolioState.snapshot) {
                try {
                    const changesRes = await apiRequest("/api/v1/my-portfolio/snapshot/changes", { skipToast: true });
                    myPortfolioState.changes = changesRes?.data || null;
                } catch (changesErr) {
                    myPortfolioState.changes = null;
                }
            } else {
                myPortfolioState.changes = null;
            }
            renderMyPortfolioHoldings(myPortfolioState.holdings);
            renderMyPortfolioHistory(myPortfolioState.imports);
            renderMyPortfolioSummary();
        } catch (err) {
            console.error("Failed to load My Portfolio workspace", err);
            showMyPortfolioAlert("Could not load My Portfolio holdings or import history.", "danger");
            myPortfolioState.snapshot = null;
            myPortfolioState.changes = null;
            myPortfolioState.notes = {};
            renderMyPortfolioHoldings([]);
            renderMyPortfolioHistory([]);
            renderMyPortfolioSummary();
        } finally {
            myPortfolioState.loading = false;
            // The sticky header is inside a `display:none` tab-pane until this
            // tab is actually activated, so any earlier measurement of its
            // height (e.g. the one-time init call at page load, before this
            // tab was ever shown) measured a hidden, zero-height element.
            // --my-portfolio-section-nav-height stayed stuck at that stale
            // value (or its 56px CSS fallback) until an unrelated scroll/
            // resize event happened to refresh it -- so the first nav-target
            // click right after opening this tab always used a too-small
            // scroll-margin-top and undershot, leaving the tail of the
            // previous section visible above the now-visible sticky header.
            // Re-measure now that the tab-pane's real layout exists.
            scheduleMyPortfolioHoldingsScrollChrome();
        }
    }

    function renderMyPortfolioSummary() {
        const holdings = myPortfolioState.holdings || [];
        const imports = myPortfolioState.imports || [];
        const snapshot = myPortfolioState.snapshot;
        const summary = snapshot?.summary || null;
        const latestConfirmed = imports.find(item => item.status === "CONFIRMED");
        const hasLegacyAnalysis = Boolean(
            snapshot?.rows?.some(row =>
                row?.provenance?.interpretation_version
                && !["portfolio-interpretation-v3", "portfolio-interpretation-v4"].includes(row.provenance.interpretation_version)
            )
        );
        const totalInvestment = summary
            ? summary.total_investment
            : holdings.reduce((sum, holding) => {
                const investment = Number(holding.investment);
                return sum + (Number.isFinite(investment) ? investment : 0);
            }, 0);
        myPortfolioHoldingCount.textContent = formatMyPortfolioNumber(summary ? summary.holding_count : holdings.length);
        myPortfolioTotalInvestment.innerHTML = myPortfolioPrivateHtml(totalInvestment, formatMyPortfolioMoney, "Total investment masked");
        myPortfolioCurrentValue.innerHTML = summary && summary.total_current_value != null
            ? myPortfolioPrivateHtml(summary.total_current_value, formatMyPortfolioMoney, "Current value masked")
            : "—";
        if (myPortfolioMiniValue) {
            myPortfolioMiniValue.innerHTML = summary && summary.total_current_value != null
                ? myPortfolioPrivateHtml(summary.total_current_value, formatMyPortfolioMoney, "Current value masked")
                : "₹ —";
        }
        myPortfolioTotalPnl.innerHTML = summary && summary.total_pnl != null
            ? myPortfolioPrivateHtml(summary.total_pnl, formatMyPortfolioMoney, "Total P and L masked")
            : "—";
        if (myPortfolioMiniPnl) {
            myPortfolioMiniPnl.innerHTML = summary && summary.total_pnl != null
                ? myPortfolioPrivateHtml(summary.total_pnl, formatMyPortfolioMoney, "Total P and L masked")
                : "₹ —";
            setMyPortfolioToneClass(myPortfolioMiniPnl, summary?.total_pnl, "my-portfolio-mini-tone");
        }
        setMyPortfolioToneClass(myPortfolioTotalPnl, summary?.total_pnl, "my-portfolio-kpi-tone");
        myPortfolioTotalPnlDetail.textContent = summary && summary.total_pnl_pct != null
            ? `${formatMyPortfolioPrivatePct(summary.total_pnl_pct)} total return`
            : "Unavailable until all rows are priced";
        setMyPortfolioToneClass(myPortfolioTotalPnlDetail, summary?.total_pnl_pct, "my-portfolio-kpi-detail-tone");
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
        if (myPortfolioMiniSynced) {
            myPortfolioMiniSynced.textContent = summary?.last_synced_at
                ? formatMyPortfolioTime(summary.last_synced_at)
                : "—";
        }
        myPortfolioMarketDataThrough.textContent = myPortfolioMarketSessionLabel(snapshot);
        if (hasLegacyAnalysis) {
            showMyPortfolioAlert(
                "Portfolio analysis is from a legacy interpretation version. Sync Portfolio to regenerate current Trend, Setup, and Daily Review evidence.",
                "warning"
            );
        } else if (myPortfolioSnapshotIsStale(snapshot)) {
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

    function myPortfolioRowKey(row) {
        return String(row?.provenance?.instrument_id || row?.instrument_id || row?.symbol || "");
    }

    function myPortfolioNotesById(notes) {
        const byId = {};
        (Array.isArray(notes) ? notes : []).forEach(note => {
            const key = String(note?.instrument_id || "");
            if (key) byId[key] = note;
        });
        return byId;
    }

    function myPortfolioNoteForRow(row) {
        return myPortfolioState.notes[myPortfolioPinKey(row)] || myPortfolioState.notes[myPortfolioRowKey(row)] || null;
    }

    function myPortfolioNoteIsPresent(note) {
        if (!note || note.present === false) return false;
        return Boolean(
            note.follow_up
            || note.deferred
            || note.reviewed_today
            || note.reviewed_at
            || String(note.thesis || "").trim()
            || String(note.watch_condition || "").trim()
            || String(note.reminder || "").trim()
            || String(note.review_comment || "").trim()
        );
    }

    function myPortfolioNoteBadge(row) {
        const note = myPortfolioNoteForRow(row);
        const chips = [];
        if (note?.reviewed_today) {
            chips.push(`<span class="my-portfolio-note-badge is-reviewed" title="Owner reviewed today. This is your mark, not ATHENA guidance.">Reviewed</span>`);
        }
        if (note?.deferred) {
            chips.push(`<span class="my-portfolio-note-badge is-deferred" title="Owner deferred. This is your mark, not ATHENA ranking.">Deferred</span>`);
        }
        if (myPortfolioNoteIsPresent(note) && (note.follow_up || String(note.thesis || "").trim() || String(note.watch_condition || "").trim() || String(note.reminder || "").trim() || String(note.review_comment || "").trim())) {
            const label = note.follow_up ? "Follow-up" : "Note";
            const title = note.follow_up
                ? "Owner follow-up. This is your mark, not ATHENA guidance."
                : "Owner note. This is your judgment, not ATHENA evidence.";
            chips.push(`<span class="my-portfolio-note-badge${note.follow_up ? " is-follow-up" : ""}" title="${title}">${label}</span>`);
        }
        return chips.join("");
    }

    function myPortfolioPinBadge(row) {
        if (!myPortfolioIsPinned(myPortfolioPinKey(row))) return "";
        return `<span class="my-portfolio-pin-badge" title="Owner-pinned. This is your pin, not ATHENA conviction or ranking.">Pinned</span>`;
    }

    // Holdings edit/delete: one small, reused Actions cell. Buttons carry
    // data-action + rely on the row's own data-instrument-id (delegated
    // listener below) so no per-button symbol/id string escaping is needed
    // beyond the existing row-level attribute.
    // Compact icon buttons (Edit=neutral, Delete=btn-danger-outline — both
    // existing classes, reused as-is) rather than full-text pills, which
    // read as too heavy/blocky in a 110px column. Disabled + spinner while
    // a Portfolio Sync this action triggered is still recalculating —
    // editing/deleting another holding mid-sync would race the same full
    // resync, so every row's actions are held until it settles.
    function myPortfolioRowActionsCell(row) {
        const symbol = row?.symbol || bareMyPortfolioSymbol(row?.instrument_id);
        const key = myPortfolioPinKey(row);
        const pinned = myPortfolioIsPinned(key);
        const busy = Boolean(myPortfolioState.syncing);
        const safeSymbol = escapeMyPortfolioHtml(symbol);
        const disabledAttr = busy ? "disabled" : "";
        const editIcon = busy ? '<i class="fa-solid fa-spinner fa-spin"></i>' : '<i class="fa-solid fa-pen"></i>';
        const deleteIcon = busy ? '<i class="fa-solid fa-spinner fa-spin"></i>' : '<i class="fa-solid fa-trash-can"></i>';
        const pinIcon = '<i class="fa-solid fa-thumbtack"></i>';
        const title = busy ? "Portfolio Sync is recalculating — please wait" : null;
        const pinTitle = pinned ? `Unpin ${safeSymbol}` : `Pin ${safeSymbol} to keep it visible`;
        return `<td class="holdings-actions">
            <button type="button" class="inspect-btn my-portfolio-row-action${pinned ? " is-pinned" : ""}" data-action="pin" title="${pinTitle}" aria-label="${pinTitle}" aria-pressed="${pinned}">${pinIcon}</button>
            <button type="button" class="inspect-btn my-portfolio-row-action" data-action="edit" title="${title || `Edit ${safeSymbol}`}" aria-label="Edit ${safeSymbol}" ${disabledAttr}>${editIcon}</button>
            <button type="button" class="inspect-btn btn-danger-outline my-portfolio-row-action" data-action="delete" title="${title || `Delete ${safeSymbol}`}" aria-label="Delete ${safeSymbol}" ${disabledAttr}>${deleteIcon}</button>
        </td>`;
    }

    function renderMyPortfolioHoldings(holdings) {
        renderMyPortfolioRiskPanel();
        renderMyPortfolioHeatmap();
        if (myPortfolioState.snapshot?.rows?.length) {
            renderMyPortfolioSnapshotRows(myPortfolioState.snapshot.rows);
            return;
        }
        myPortfolioState.snapshotRowsByKey = {};
        const sourceRows = holdings || [];
        const visibleRows = myPortfolioVisibleRows(sourceRows);
        if (!sourceRows.length || !visibleRows.length) {
            myPortfolioHoldingsRows.innerHTML = `<tr><td colspan="15" class="text-center text-muted">${escapeMyPortfolioHtml(myPortfolioTriageEmptyMessage(sourceRows.length))}</td></tr>`;
            renderMyPortfolioSortControls();
            renderMyPortfolioDensityControls();
            renderMyPortfolioTriage(sourceRows.length, visibleRows.length);
            scheduleMyPortfolioHoldingsScrollChrome();
            return;
        }
        const rows = sortedMyPortfolioRows(visibleRows);
        myPortfolioHoldingsRows.innerHTML = rows.map((holding, index) => {
            const symbol = holding.symbol || bareMyPortfolioSymbol(holding.instrument_id);
            const pinKey = myPortfolioPinKey(holding);
            return `
            <tr class="my-portfolio-row-state state-muted${myPortfolioIsPinned(pinKey) ? " is-owner-pinned" : ""}" data-instrument-id="${escapeMyPortfolioHtml(pinKey)}">
                <td class="my-portfolio-row-index">${formatMyPortfolioNumber(index + 1)}</td>
                <td class="font-mono"><strong>${escapeMyPortfolioHtml(symbol)}</strong>${myPortfolioPinBadge(holding)}${myPortfolioNoteBadge(holding)}</td>
                <td>${myPortfolioPrivateNumberCell(holding.quantity)}</td>
                <td class="font-mono">${myPortfolioMoneyCell(holding.avg_price)}</td>
                <td>${myPortfolioDash()}</td>
                <td>${myPortfolioDash()}</td>
                <td>${myPortfolioDash()}</td>
                <td>${myPortfolioUnavailableChip()}</td>
                <td>${myPortfolioDash()}</td>
                <td>${myPortfolioUnavailableChip()}</td>
                <td class="text-muted">Not synced</td>
                <td>${myPortfolioUnavailableChip()}</td>
                <td>${myPortfolioDash()}</td>
                <td class="text-muted">Not synced</td>
                ${myPortfolioRowActionsCell(holding)}
            </tr>
        `;
        }).join("");
        renderMyPortfolioSortControls();
        renderMyPortfolioDensityControls();
        renderMyPortfolioTriage(sourceRows.length, rows.length);
        scheduleMyPortfolioHoldingsScrollChrome();
    }

    function renderMyPortfolioSnapshotRows(rows) {
        myPortfolioState.snapshotRowsByKey = {};
        rows.forEach(row => {
            myPortfolioState.snapshotRowsByKey[myPortfolioRowKey(row)] = row;
        });
        const visibleRows = myPortfolioVisibleRows(rows);
        if (!visibleRows.length) {
            myPortfolioHoldingsRows.innerHTML = `<tr><td colspan="15" class="text-center text-muted">${escapeMyPortfolioHtml(myPortfolioTriageEmptyMessage(rows.length))}</td></tr>`;
            renderMyPortfolioSortControls();
            renderMyPortfolioDensityControls();
            renderMyPortfolioTriage(rows.length, 0);
            scheduleMyPortfolioHoldingsScrollChrome();
            return;
        }
        const sortedRows = sortedMyPortfolioRows(visibleRows);
        myPortfolioHoldingsRows.innerHTML = sortedRows.map((row, index) => `
            <tr class="my-portfolio-row-state ${myPortfolioRowStateClass(row)}${myPortfolioIsPinned(myPortfolioRowKey(row)) ? " is-owner-pinned" : ""}" data-instrument-id="${escapeMyPortfolioHtml(myPortfolioRowKey(row))}" tabindex="0" role="button" aria-label="Open detail for ${escapeMyPortfolioHtml(row.symbol)}">
                <td class="my-portfolio-row-index">${formatMyPortfolioNumber(index + 1)}</td>
                <td class="font-mono"><strong>${escapeMyPortfolioHtml(row.symbol)}</strong>${myPortfolioPinBadge(row)}${myPortfolioNoteBadge(row)}${myPortfolioQueueReasonChips(row)}${myPortfolioChangeBadgeChips(row)}</td>
                <td>${myPortfolioPrivateNumberCell(row.qty ?? row.quantity)}</td>
                <td class="font-mono">${myPortfolioMoneyCell(row.avg_price)}</td>
                <td class="font-mono">${myPortfolioPriceToneCell(row.last_price, row.avg_price)}</td>
                <td class="font-mono">${row.pnl == null ? myPortfolioDash() : myPortfolioSignedCell(row.pnl, formatMyPortfolioMoney)}</td>
                <td>${row.pnl_pct == null ? myPortfolioDash() : myPortfolioSignedCell(row.pnl_pct, formatMyPortfolioPct)}</td>
                <td>${myPortfolioStatusPill(row.status, row)}</td>
                <td>${myPortfolioConvictionCell(row.conviction, row)}</td>
                <td>${myPortfolioTrendCell(row.trend_or_setup, row)}</td>
                <td>${myPortfolioDailyReviewCell(row)}</td>
                <td>${myPortfolioActionPill(row.next_action, row)}</td>
                <td>${myPortfolioPlanLevelsCell(row)}</td>
                <td>${myPortfolioFreshnessCell(row)}</td>
                ${myPortfolioRowActionsCell(row)}
            </tr>
        `).join("");
        renderMyPortfolioSortControls();
        renderMyPortfolioDensityControls();
        renderMyPortfolioTriage(rows.length, sortedRows.length);
        scheduleMyPortfolioHoldingsScrollChrome();
    }

    // MY-PORTFOLIO-V1-FINAL-UX-CLOSURE holding-detail drawer. Every value
    // below is already present on the snapshot row / daily_review /
    // provenance objects — no new fetch, no new evidence, no new
    // classification. Support 1/Target 2/Target 3 are never rendered as
    // blank rows here; the PLAN / LEVELS section states the v0 methodology
    // NO-GO once, in words.
    function myPortfolioDetailRow(label, value, options = {}) {
        return myPortfolioDetailRowHtml(label, escapeMyPortfolioHtml(value), options);
    }

    function myPortfolioDetailRowHtml(label, valueHtml, options = {}) {
        const tone = options.tone ? ` tone-${escapeMyPortfolioHtml(options.tone)}` : "";
        const wide = options.wide ? " my-portfolio-detail-row-wide" : "";
        const icon = options.icon
            ? `<i class="fa-solid ${escapeMyPortfolioHtml(options.icon)}" aria-hidden="true"></i>`
            : "";
        return `<div class="my-portfolio-detail-row${tone}${wide}">
            <span class="my-portfolio-detail-label">${icon}${escapeMyPortfolioHtml(label)}</span>
            <span class="my-portfolio-detail-value">${valueHtml}</span>
        </div>`;
    }

    function myPortfolioDetailSignedRow(label, value, formatter, icon) {
        const tone = myPortfolioToneFromNumber(value);
        if (value != null && myPortfolioState.valuesHidden) {
            return myPortfolioDetailRowHtml(label, myPortfolioMaskedValue(`${label} masked`), { icon, tone });
        }
        const valueText = value == null ? "Not available" : myPortfolioPrivateText(value, formatter);
        return myPortfolioDetailRow(label, valueText, { icon, tone });
    }

    function myPortfolioDetailMarketChip(label, tone, icon) {
        return `<span class="my-portfolio-detail-chip ${escapeMyPortfolioHtml(tone)}"><i class="fa-solid ${escapeMyPortfolioHtml(icon)}" aria-hidden="true"></i>${escapeMyPortfolioHtml(label)}</span>`;
    }

    function myPortfolioDetailTrendChip(value) {
        const label = value ? String(value).toUpperCase() : "";
        const map = {
            UPTREND: ["Uptrend", "good", "fa-arrow-trend-up"],
            DOWNTREND: ["Downtrend", "danger", "fa-arrow-trend-down"],
            MIXED: ["Mixed", "warning", "fa-shuffle"],
        };
        const [display, tone, icon] = map[label] || ["Not available", "neutral", "fa-minus"];
        return myPortfolioDetailMarketChip(display, tone, icon);
    }

    function myPortfolioDetailSetupChip(value) {
        const label = value ? String(value).toUpperCase() : "";
        const map = {
            BREAKOUT: ["Breakout", "good", "fa-arrow-up-right-dots"],
            BREAKDOWN: ["Breakdown", "danger", "fa-arrow-down-short-wide"],
        };
        const [display, tone, icon] = map[label] || ["Not available", "neutral", "fa-minus"];
        return myPortfolioDetailMarketChip(display, tone, icon);
    }

    function myPortfolioDetailDirectionChip(value) {
        const label = value ? String(value).toUpperCase() : "";
        const map = {
            BULLISH: ["Bullish", "good", "fa-arrow-trend-up"],
            BEARISH: ["Bearish", "danger", "fa-arrow-trend-down"],
        };
        const [display, tone, icon] = map[label] || ["Not available", "neutral", "fa-minus"];
        return myPortfolioDetailMarketChip(display, tone, icon);
    }

    function myPortfolioDetailPriceVsSupertrendTone(row, review) {
        const price = Number(row?.last_price);
        const st = Number(review?.supertrend_value);
        if (!Number.isFinite(price) || !Number.isFinite(st)) return "neutral";
        if (price > st) return "positive";
        if (price < st) return "negative";
        return "neutral";
    }

    function myPortfolioDetailHero(row, review, trendLabel) {
        const pnlTone = myPortfolioToneFromNumber(row?.pnl_pct);
        const priceTone = row?.last_price == null
            ? "neutral"
            : myPortfolioToneFromNumber(Number(row.last_price) - Number(row.avg_price));
        return `<div class="my-portfolio-detail-hero" aria-label="Holding quick summary">
            <div class="my-portfolio-detail-hero-grid">
                <span class="my-portfolio-detail-hero-metric tone-${escapeMyPortfolioHtml(priceTone)}">
                    <i class="fa-solid fa-indian-rupee-sign" aria-hidden="true"></i>
                    <span>Last</span>
                    <strong>${row?.last_price == null ? "Not available" : myPortfolioPrivateHtml(row.last_price, formatMyPortfolioMoney, "Last price masked")}</strong>
                </span>
                <span class="my-portfolio-detail-hero-metric tone-${escapeMyPortfolioHtml(pnlTone)}">
                    <i class="fa-solid fa-chart-line" aria-hidden="true"></i>
                    <span>P&L</span>
                    <strong>${row?.pnl_pct == null ? "Not available" : myPortfolioPrivateHtml(row.pnl_pct, formatMyPortfolioPct, "P and L percent masked")}</strong>
                </span>
                <span class="my-portfolio-detail-hero-chip">${myPortfolioStatusPill(row?.status, row)}</span>
                <span class="my-portfolio-detail-hero-chip">${myPortfolioActionPill(row?.next_action, row)}</span>
                <span class="my-portfolio-detail-hero-chip">${myPortfolioDetailTrendChip(trendLabel)}</span>
                <span class="my-portfolio-detail-hero-chip">${myPortfolioDetailDirectionChip(review?.supertrend_direction)}</span>
            </div>
        </div>`;
    }

    function myPortfolioPriceVsSupertrend(row, review) {
        const price = row?.last_price;
        const st = review?.supertrend_value;
        if (price == null || st == null) return "Not available";
        const priceNum = Number(price);
        const stNum = Number(st);
        if (!Number.isFinite(priceNum) || !Number.isFinite(stNum)) return "Not available";
        if (priceNum > stNum) return `Above SuperTrend (${formatMyPortfolioMoney(st)})`;
        if (priceNum < stNum) return `Below SuperTrend (${formatMyPortfolioMoney(st)})`;
        return `At SuperTrend (${formatMyPortfolioMoney(st)})`;
    }

    function myPortfolioAvailableHistoryHighText(review) {
        if (review?.latest_high_exceeds_prior_available_high === true) {
            return "Latest D1 high exceeded prior available-history high";
        }
        if (review?.latest_high_exceeds_prior_available_high === false) {
            return "Latest D1 high did not exceed prior available-history high";
        }
        return "Not available";
    }

    // Portfolio Intelligence V2 — Structural Review helpers. Additive only:
    // never redefines Status/Conviction/Trend/Setup/Daily Review/Next
    // Action/TradePlan/SuperTrend. "Plan Levels" (TradePlan-derived) and
    // "Structural Levels" (D1 swing-structure-derived) stay semantically
    // distinct and are never merged into one cell/label.
    function myPortfolioStructuralZoneText(zone) {
        if (!zone) return "Not available";
        const lower = Number(zone.lower);
        const upper = Number(zone.upper);
        if (!Number.isFinite(lower) || !Number.isFinite(upper)) return "Not available";
        return lower === upper
            ? formatMyPortfolioMoney(lower)
            : `${formatMyPortfolioMoney(lower)}-${formatMyPortfolioMoney(upper)}`;
    }

    const MY_PORTFOLIO_STRUCTURAL_REASON_LABELS = {
        STRUCTURAL_EVIDENCE_UNAVAILABLE: "Structural D1 evidence is unavailable.",
        STRUCTURAL_EVIDENCE_INCOHERENT: "Structural D1 evidence is not coherent for this holding.",
        STRUCTURAL_INSUFFICIENT_HISTORY: "Insufficient D1 history for structural analysis.",
        SUPPORT_1_SELECTED: "Support 1 selected from a confirmed recent reaction-low zone.",
        SUPPORT_1_UNAVAILABLE: "No structural support zone is currently active below price.",
        MAJOR_SUPPORT_FROM_SUPERTREND: "Major Support is anchored to the existing SuperTrend level.",
        MAJOR_SUPPORT_FROM_STRUCTURE: "Major Support is a deeper confirmed structural zone.",
        MAJOR_SUPPORT_UNAVAILABLE: "No deeper Major Support zone could be identified.",
        TARGET_1_SELECTED: "Target 1 selected from the nearest confirmed resistance zone.",
        TARGET_2_SELECTED: "Target 2 selected from the next distinct resistance zone.",
        TARGET_3_SELECTED: "Target 3 selected from the next distinct resistance zone.",
        NO_OVERHEAD_RESISTANCE: "No defensible overhead resistance exists — targets are intentionally null, never synthetic.",
        REVIEW_TRIGGER_RECLAIM: "Review Trigger is a reclaim of a recently lost structural level.",
        REVIEW_TRIGGER_BREAKOUT: "Review Trigger is a breakout of the nearest resistance zone.",
        REVIEW_TRIGGER_UNAVAILABLE: "No Review Trigger could be identified.",
        EXIT_RISK_STRUCTURAL_INVALIDATION: "Major structural support is currently breached while SuperTrend is bearish.",
        EXIT_RISK_NOT_TRIGGERED: "Structural invalidation has not been triggered.",
    };

    function myPortfolioStructuralReasonSummary(row) {
        const codes = row?.structural_review?.reason_codes || [];
        const messages = codes.map(code => MY_PORTFOLIO_STRUCTURAL_REASON_LABELS[code]).filter(Boolean);
        return [...new Set(messages)];
    }

    function renderMyPortfolioDetail(row) {
        const review = row?.daily_review || null;
        const trendLabel = myPortfolioTrendLabelOnly(row?.trend_or_setup);
        const setupLabel = (() => {
            const raw = row?.trend_or_setup ? String(row.trend_or_setup).toUpperCase() : "";
            const half = raw.split("/")[1];
            const label = half ? half.trim() : "";
            return label && label !== "-" ? label : "Not available";
        })();
        const reasonMessages = myPortfolioDailyReviewReasonSummary(row);

        const planLines = [];
        if (row?.key_trigger != null && row.key_trigger !== "") {
            planLines.push(myPortfolioDetailRow("Plan Trigger", formatMyPortfolioMoney(row.key_trigger), {
                icon: "fa-bolt",
                tone: "accent",
            }));
        }
        if (row?.major_support_exit != null) {
            planLines.push(myPortfolioDetailRow("Plan Stop", formatMyPortfolioMoney(row.major_support_exit), {
                icon: "fa-shield-halved",
                tone: "negative",
            }));
        }
        if (row?.target_1 != null) {
            planLines.push(myPortfolioDetailRow("Plan T1", formatMyPortfolioMoney(row.target_1), {
                icon: "fa-location-arrow",
                tone: "positive",
            }));
        }
        const planSection = planLines.length
            ? `<div class="my-portfolio-detail-grid">${planLines.join("")}</div>`
            : `<p class="my-portfolio-detail-guidance text-muted">No active TradePlan level currently available.</p>`;

        const sr = row?.structural_review || null;
        const structuralReasonMessages = myPortfolioStructuralReasonSummary(row);
        const structuralSection = sr && sr.is_coherent
            ? `
                <div class="my-portfolio-detail-grid">
                    ${myPortfolioDetailRow("Support 1", myPortfolioStructuralZoneText(sr.support_1), { icon: "fa-layer-group", tone: sr.support_1 ? "positive" : "neutral" })}
                    ${myPortfolioDetailRow("Major Support / Invalidation", myPortfolioStructuralZoneText(sr.major_support), { icon: "fa-shield-halved", tone: sr.major_support ? "negative" : "neutral" })}
                    ${myPortfolioDetailRow("Review Trigger", myPortfolioStructuralZoneText(sr.review_trigger), { icon: "fa-bolt", tone: sr.review_trigger ? "accent" : "neutral" })}
                    ${myPortfolioDetailRow("Target 1", myPortfolioStructuralZoneText(sr.target_1), { icon: "fa-location-arrow", tone: sr.target_1 ? "positive" : "neutral" })}
                    ${myPortfolioDetailRow("Target 2", myPortfolioStructuralZoneText(sr.target_2), { icon: "fa-location-dot", tone: sr.target_2 ? "positive" : "neutral" })}
                    ${myPortfolioDetailRow("Target 3", myPortfolioStructuralZoneText(sr.target_3), { icon: "fa-bullseye", tone: sr.target_3 ? "positive" : "neutral" })}
                    ${myPortfolioDetailRow("EXIT_RISK", sr.exit_risk ? "Elevated" : "Not triggered", { icon: sr.exit_risk ? "fa-triangle-exclamation" : "fa-circle-check", tone: sr.exit_risk ? "negative" : "positive" })}
                </div>
                ${sr.guidance ? `<p class="my-portfolio-detail-guidance structural"><i class="fa-solid fa-route" aria-hidden="true"></i><span><strong>Structural Guidance:</strong> ${escapeMyPortfolioHtml(sr.guidance)}</span></p>` : ""}
                ${structuralReasonMessages.length ? `<ul class="my-portfolio-detail-reasons">${structuralReasonMessages.map(msg => `<li>${escapeMyPortfolioHtml(msg)}</li>`).join("")}</ul>` : ""}
            `
            : `<p class="my-portfolio-detail-guidance text-muted">Structural Review is unavailable for this holding (insufficient or incoherent D1 history).</p>`;

        myPortfolioDetailBody.innerHTML = `
            ${myPortfolioDetailHero(row, review, trendLabel)}
            ${myPortfolioSinceLastSyncSection(row)}
            ${myPortfolioReviewTimelineSection()}
            <div class="my-portfolio-detail-section" data-detail-section="position">
                <h4>Position</h4>
                <div class="my-portfolio-detail-grid">
                    ${myPortfolioDetailRowHtml("Qty", myPortfolioPrivateHtml(row.qty ?? row.quantity, formatMyPortfolioNumber, "Quantity masked"), { icon: "fa-layer-group" })}
                    ${myPortfolioDetailRowHtml("Avg Price", myPortfolioPrivateHtml(row.avg_price, formatMyPortfolioMoney, "Average price masked"), { icon: "fa-scale-balanced" })}
                    ${myPortfolioDetailRowHtml("Last Price", row.last_price == null ? "Not available" : myPortfolioPrivateHtml(row.last_price, formatMyPortfolioMoney, "Last price masked"), { icon: "fa-indian-rupee-sign", tone: row.last_price == null ? "neutral" : myPortfolioToneFromNumber(Number(row.last_price) - Number(row.avg_price)) })}
                    ${myPortfolioDetailRowHtml("Investment", myPortfolioPrivateHtml(row.investment, formatMyPortfolioMoney, "Investment masked"), { icon: "fa-wallet" })}
                    ${myPortfolioDetailRowHtml("Current Value", row.current_value == null ? "Not available" : myPortfolioPrivateHtml(row.current_value, formatMyPortfolioMoney, "Current value masked"), { icon: "fa-chart-line", tone: "accent" })}
                    ${myPortfolioDetailSignedRow("P&L", row.pnl, formatMyPortfolioMoney, "fa-arrow-trend-up")}
                    ${myPortfolioDetailSignedRow("P&L %", row.pnl_pct, formatMyPortfolioPct, "fa-percent")}
                </div>
            </div>
            <div class="my-portfolio-detail-section" data-detail-section="technical">
                <h4>Technical State</h4>
                <div class="my-portfolio-detail-grid">
                    ${myPortfolioDetailRowHtml("D1 Trend", myPortfolioDetailTrendChip(trendLabel), { icon: "fa-chart-line" })}
                    ${myPortfolioDetailRowHtml("OR Setup", myPortfolioDetailSetupChip(setupLabel), { icon: "fa-border-top-left" })}
                    ${myPortfolioDetailRowHtml("SuperTrend direction", myPortfolioDetailDirectionChip(review?.supertrend_direction), { icon: "fa-route" })}
                    ${myPortfolioDetailRow("SuperTrend value", review?.supertrend_value == null ? "Not available" : formatMyPortfolioMoney(review.supertrend_value), { icon: "fa-wave-square", tone: "accent" })}
                    ${myPortfolioDetailRow("Price vs SuperTrend", myPortfolioPriceVsSupertrend(row, review), { icon: "fa-code-compare", tone: myPortfolioDetailPriceVsSupertrendTone(row, review) })}
                    ${myPortfolioDetailRow("RSI14 (context only)", review?.rsi14 == null ? "Not available" : formatMyPortfolioNumber(review.rsi14), { icon: "fa-gauge-high" })}
                    ${myPortfolioDetailRow("Volume", review?.volume == null ? "Not available" : formatMyPortfolioNumber(review.volume), { icon: "fa-chart-column" })}
                    ${myPortfolioDetailRow("Volume MA20", review?.volume_ma20 == null ? "Not available" : formatMyPortfolioNumber(review.volume_ma20), { icon: "fa-chart-simple" })}
                    ${myPortfolioDetailRow("Available-history high", myPortfolioAvailableHistoryHighText(review), { icon: "fa-mountain-sun", tone: review?.latest_high_exceeds_prior_available_high ? "positive" : "neutral" })}
                    ${myPortfolioDetailRow("Daily Review as of", review?.as_of ? formatMyPortfolioTime(review.as_of) : "Not available", { icon: "fa-calendar-check" })}
                    ${myPortfolioDetailRow("Evidence as of", review?.evidence_as_of ? formatMyPortfolioTime(review.evidence_as_of) : "Not available", { icon: "fa-clock" })}
                </div>
                <p class="my-portfolio-detail-guidance muted"><i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>RSI14 is raw context only — no overbought/oversold interpretation. Volume/VMA20 are raw context only — no expansion/compression interpretation.</span></p>
            </div>
            <div class="my-portfolio-detail-section" data-detail-section="review">
                <h4>ATHENA Review</h4>
                <div class="my-portfolio-detail-grid">
                    ${myPortfolioDetailRowHtml("Status", myPortfolioStatusPill(row.status, row), { icon: "fa-heart-pulse" })}
                    ${myPortfolioDetailRowHtml("Conviction", myPortfolioConvictionCell(row.conviction, row), { icon: "fa-signal" })}
                    ${myPortfolioDetailRowHtml("Next Action", myPortfolioActionPill(row.next_action, row), { icon: "fa-compass" })}
                </div>
                <p class="my-portfolio-detail-guidance review"><i class="fa-solid fa-bolt" aria-hidden="true"></i><span><strong>Daily Guidance:</strong> ${escapeMyPortfolioHtml(review?.guidance || "Daily Review unavailable.")}</span></p>
                ${reasonMessages.length ? `<ul class="my-portfolio-detail-reasons">${reasonMessages.map(msg => `<li>${escapeMyPortfolioHtml(msg)}</li>`).join("")}</ul>` : ""}
            </div>
            <div class="my-portfolio-detail-section" data-detail-section="plan">
                <h4>Plan / Levels</h4>
                ${planSection}
                <p class="my-portfolio-detail-notice">Plan Trigger/Stop/T1 reflect an active TradePlan only, distinct from the structural D1 levels below.</p>
            </div>
            <div class="my-portfolio-detail-section" data-detail-section="structural">
                <h4>Structural Review / Levels</h4>
                ${structuralSection}
            </div>
            ${myPortfolioOwnerNoteSection(row)}
        `;
        bindMyPortfolioNoteForm(myPortfolioPinKey(row) || myPortfolioRowKey(row));
    }

    function formatMyPortfolioNoteTime(value) {
        if (!value) return "";
        const dt = new Date(value);
        if (Number.isNaN(dt.getTime())) return "";
        return dt.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
    }

    function myPortfolioOwnerNoteSection(row) {
        const key = myPortfolioPinKey(row) || myPortfolioRowKey(row);
        const note = myPortfolioState.notes[key] || {};
        const present = myPortfolioNoteIsPresent(note);
        const updated = formatMyPortfolioNoteTime(note.updated_at);
        return `<div class="my-portfolio-detail-section my-portfolio-owner-note" data-detail-section="owner-note">
            <h4>Owner note</h4>
            <p class="metric-desc">Your judgment only. This never changes ATHENA Status, guidance, conviction, or scores.</p>
            <label for="my-portfolio-note-thesis">Thesis</label>
            <textarea id="my-portfolio-note-thesis" rows="3" maxlength="4000">${escapeMyPortfolioHtml(note.thesis || "")}</textarea>
            <label for="my-portfolio-note-watch">Watch condition</label>
            <textarea id="my-portfolio-note-watch" rows="2" maxlength="2000">${escapeMyPortfolioHtml(note.watch_condition || "")}</textarea>
            <label for="my-portfolio-note-reminder">Reminder</label>
            <textarea id="my-portfolio-note-reminder" rows="2" maxlength="2000">${escapeMyPortfolioHtml(note.reminder || "")}</textarea>
            <label for="my-portfolio-note-comment">Review comment</label>
            <textarea id="my-portfolio-note-comment" rows="2" maxlength="4000">${escapeMyPortfolioHtml(note.review_comment || "")}</textarea>
            <label class="my-portfolio-owner-note-check">
                <input id="my-portfolio-note-follow-up" type="checkbox"${note.follow_up ? " checked" : ""}>
                Needs manual follow-up
            </label>
            <div class="my-portfolio-owner-note-actions">
                <button id="my-portfolio-note-save" class="btn btn-primary" type="button">Save note</button>
                <button id="my-portfolio-note-clear" class="btn" type="button"${present ? "" : " disabled"}>Clear note</button>
            </div>
            <p id="my-portfolio-note-status" class="metric-desc">${present && updated ? `Last saved ${escapeMyPortfolioHtml(updated)}.` : "No owner note saved yet."}</p>
        </div>`;
    }

    function bindMyPortfolioNoteForm(instrumentId) {
        document.getElementById("my-portfolio-note-save")?.addEventListener("click", () => {
            saveMyPortfolioNote(instrumentId);
        });
        document.getElementById("my-portfolio-note-clear")?.addEventListener("click", () => {
            clearMyPortfolioNote(instrumentId);
        });
    }

    function rememberMyPortfolioNote(instrumentId, note) {
        if (note && note.present !== false && myPortfolioNoteIsPresent(note)) {
            myPortfolioState.notes[instrumentId] = note;
        } else {
            delete myPortfolioState.notes[instrumentId];
        }
        const openKey = myPortfolioState.detailOpenKey;
        const openRow = openKey ? myPortfolioState.snapshotRowsByKey[openKey] : null;
        renderMyPortfolioHoldings(myPortfolioSourceRows());
        if (openRow) renderMyPortfolioDetail(openRow);
        renderMyPortfolioReviewSessionChrome();
    }

    function myPortfolioNotePayload(instrumentId, extras = {}) {
        const existing = myPortfolioState.notes[instrumentId] || {};
        return {
            thesis: document.getElementById("my-portfolio-note-thesis")?.value || existing.thesis || "",
            watch_condition: document.getElementById("my-portfolio-note-watch")?.value || existing.watch_condition || "",
            reminder: document.getElementById("my-portfolio-note-reminder")?.value || existing.reminder || "",
            review_comment: document.getElementById("my-portfolio-note-comment")?.value || existing.review_comment || "",
            follow_up: document.getElementById("my-portfolio-note-follow-up")
                ? Boolean(document.getElementById("my-portfolio-note-follow-up").checked)
                : Boolean(existing.follow_up),
            deferred: extras.deferred !== undefined ? Boolean(extras.deferred) : Boolean(existing.deferred),
            ...(extras.reviewed === undefined ? {} : { reviewed: extras.reviewed }),
        };
    }

    async function saveMyPortfolioNote(instrumentId, extras = {}) {
        if (!instrumentId) return null;
        const status = document.getElementById("my-portfolio-note-status");
        const saveBtn = document.getElementById("my-portfolio-note-save");
        if (saveBtn) saveBtn.disabled = true;
        try {
            const response = await apiRequest(`/api/v1/my-portfolio/notes/${encodeURIComponent(instrumentId)}`, {
                method: "PUT",
                body: JSON.stringify(myPortfolioNotePayload(instrumentId, extras)),
                skipToast: true,
            });
            rememberMyPortfolioNote(instrumentId, response?.data);
            const nextStatus = document.getElementById("my-portfolio-note-status");
            if (nextStatus) nextStatus.textContent = response?.data?.present ? "Owner note saved." : "Owner note cleared.";
            return response?.data || null;
        } catch (err) {
            if (status) status.textContent = "Could not save the owner note.";
            showMyPortfolioAlert("Could not save the owner note.", "danger");
            return null;
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }

    async function clearMyPortfolioNote(instrumentId) {
        if (!instrumentId) return;
        const status = document.getElementById("my-portfolio-note-status");
        try {
            const response = await apiRequest(`/api/v1/my-portfolio/notes/${encodeURIComponent(instrumentId)}`, {
                method: "DELETE",
                skipToast: true,
            });
            rememberMyPortfolioNote(instrumentId, response?.data);
            const nextStatus = document.getElementById("my-portfolio-note-status");
            if (nextStatus) nextStatus.textContent = "Owner note cleared.";
        } catch (err) {
            if (status) status.textContent = "Could not clear the owner note.";
            showMyPortfolioAlert("Could not clear the owner note.", "danger");
        }
    }

    function myPortfolioReviewSessionRows() {
        return sortedMyPortfolioRows(myPortfolioVisibleRows(myPortfolioSourceRows()));
    }

    function renderMyPortfolioReviewSessionChrome() {
        const bar = document.getElementById("my-portfolio-review-session");
        const status = document.getElementById("my-portfolio-review-session-status");
        const session = myPortfolioState.reviewSession;
        if (!bar) return;
        if (!session.active || !session.keys.length) {
            bar.hidden = true;
            return;
        }
        bar.hidden = false;
        const position = session.index + 1;
        const currentKey = session.keys[session.index] || "";
        const note = myPortfolioState.notes[currentKey] || {};
        const marks = [
            note.reviewed_today ? "reviewed today" : null,
            note.deferred ? "deferred" : null,
        ].filter(Boolean);
        if (status) {
            status.textContent = `Review session ${position} of ${session.keys.length}${marks.length ? ` · ${marks.join(", ")}` : ""}. Owner marks only — this never changes ATHENA Status or guidance.`;
        }
        const prev = document.getElementById("my-portfolio-review-prev");
        const next = document.getElementById("my-portfolio-review-next");
        if (prev) prev.disabled = session.index <= 0;
        if (next) next.disabled = session.index >= session.keys.length - 1;
    }

    function endMyPortfolioReviewSession() {
        myPortfolioState.reviewSession = { active: false, keys: [], index: 0 };
        renderMyPortfolioReviewSessionChrome();
    }

    function openMyPortfolioReviewSessionAt(index) {
        const session = myPortfolioState.reviewSession;
        if (!session.active || !session.keys.length) return;
        const nextIndex = Math.max(0, Math.min(index, session.keys.length - 1));
        session.index = nextIndex;
        const key = session.keys[nextIndex];
        if (!key) return;
        openMyPortfolioDetail(key);
        renderMyPortfolioReviewSessionChrome();
    }

    function startMyPortfolioReviewSession() {
        const rows = myPortfolioReviewSessionRows();
        const keys = rows.map(row => myPortfolioPinKey(row) || myPortfolioRowKey(row)).filter(Boolean);
        if (!keys.length) {
            showMyPortfolioAlert("No holdings in the current Morning triage view to review.", "warning");
            return;
        }
        const firstUnreviewed = keys.findIndex(key => !myPortfolioState.notes[key]?.reviewed_today);
        myPortfolioState.reviewSession = {
            active: true,
            keys,
            index: firstUnreviewed >= 0 ? firstUnreviewed : 0,
        };
        openMyPortfolioReviewSessionAt(myPortfolioState.reviewSession.index);
        scrollMyPortfolioHoldingsIntoView();
    }

    function stepMyPortfolioReviewSession(delta) {
        if (!myPortfolioState.reviewSession.active) return;
        openMyPortfolioReviewSessionAt(myPortfolioState.reviewSession.index + delta);
    }

    async function markMyPortfolioReviewSession(kind) {
        const session = myPortfolioState.reviewSession;
        const key = session.keys[session.index];
        if (!session.active || !key) return;
        const extras = kind === "defer"
            ? { deferred: true }
            : { reviewed: true };
        const saved = await saveMyPortfolioNote(key, extras);
        if (!saved) return;
        const nextUnreviewed = session.keys.findIndex((item, index) => (
            index > session.index && !myPortfolioState.notes[item]?.reviewed_today
        ));
        if (nextUnreviewed >= 0) openMyPortfolioReviewSessionAt(nextUnreviewed);
        else if (session.index < session.keys.length - 1) stepMyPortfolioReviewSession(1);
        else renderMyPortfolioReviewSessionChrome();
    }

    function resetMyPortfolioDetailScroll() {
        if (myPortfolioDetailBody) myPortfolioDetailBody.scrollTop = 0;
        const container = myPortfolioDetailModal?.querySelector(".my-portfolio-detail-modal-container");
        if (container) container.scrollTop = 0;
    }

    function openMyPortfolioDetail(key) {
        const row = myPortfolioState.snapshotRowsByKey[key];
        if (!row || !myPortfolioDetailModal) return;
        if (myPortfolioDetailTitle) myPortfolioDetailTitle.textContent = row.symbol || key;
        if (myPortfolioDetailSubtitle) {
            myPortfolioDetailSubtitle.textContent = `Qty ${formatMyPortfolioPrivateNumber(row.qty ?? row.quantity)} @ ${formatMyPortfolioPrivateMoney(row.avg_price)} avg`;
        }
        myPortfolioState.detailOpenKey = key;
        if (myPortfolioState.reviewSession.active) {
            const sessionIndex = myPortfolioState.reviewSession.keys.indexOf(key);
            if (sessionIndex >= 0) myPortfolioState.reviewSession.index = sessionIndex;
        }
        myPortfolioState.timelineKey = key;
        myPortfolioState.timeline = null;
        myPortfolioState.timelineLoading = true;
        myPortfolioState.timelineError = false;
        renderMyPortfolioDetail(row);
        loadMyPortfolioReviewTimeline(key);
        resetMyPortfolioDetailScroll();
        openModal(myPortfolioDetailModal);
        window.requestAnimationFrame(resetMyPortfolioDetailScroll);
        renderMyPortfolioReviewSessionChrome();
    }

    myPortfolioHoldingsRows?.addEventListener("click", event => {
        if (event.target.closest(".my-portfolio-row-action")) return;
        const tr = event.target.closest("tr[data-instrument-id]");
        if (!tr) return;
        openMyPortfolioDetail(tr.getAttribute("data-instrument-id"));
    });
    myPortfolioHoldingsRows?.addEventListener("keydown", event => {
        if (event.key !== "Enter" && event.key !== " ") return;
        if (event.target.closest(".my-portfolio-row-action")) return;
        const tr = event.target.closest("tr[data-instrument-id]");
        if (!tr) return;
        event.preventDefault();
        openMyPortfolioDetail(tr.getAttribute("data-instrument-id"));
    });
    myPortfolioHoldingsRows?.addEventListener("click", event => {
        const btn = event.target.closest(".my-portfolio-row-action");
        if (!btn) return;
        const tr = btn.closest("tr[data-instrument-id]");
        if (!tr) return;
        const instrumentId = tr.getAttribute("data-instrument-id");
        if (btn.getAttribute("data-action") === "pin") {
            toggleMyPortfolioPin(instrumentId);
        } else if (btn.getAttribute("data-action") === "edit") {
            myPortfolioEditHolding(instrumentId);
        } else if (btn.getAttribute("data-action") === "delete") {
            myPortfolioDeleteHolding(instrumentId);
        }
    });
    myPortfolioDetailClose?.addEventListener("click", () => {
        endMyPortfolioReviewSession();
        closeModal(myPortfolioDetailModal);
    });
    window.addEventListener("click", event => {
        if (event.target === myPortfolioDetailModal) {
            endMyPortfolioReviewSession();
            closeModal(myPortfolioDetailModal);
        }
    });

    // Holdings edit/delete: owner-initiated corrections to one current
    // holding. Both reuse the existing Sync Portfolio pipeline (there is no
    // isolated single-holding recompute) so Status/Conviction/Trend/Daily
    // Review/Structural Review are recalculated with the updated holding,
    // then the list and page re-render via the same poller Sync already uses.
    function myPortfolioHoldingLookup(instrumentId) {
        const holding = (myPortfolioState.holdings || []).find(h => h.instrument_id === instrumentId);
        const snapshotRow = myPortfolioState.snapshotRowsByKey?.[instrumentId];
        return {
            symbol: holding?.symbol || snapshotRow?.symbol || bareMyPortfolioSymbol(instrumentId),
            quantity: holding?.quantity ?? snapshotRow?.qty ?? snapshotRow?.quantity ?? null,
            avgPrice: holding?.avg_price ?? snapshotRow?.avg_price ?? null,
        };
    }

    async function myPortfolioEditHolding(instrumentId) {
        if (!instrumentId) return;
        const { symbol, quantity, avgPrice } = myPortfolioHoldingLookup(instrumentId);

        const rawQty = window.prompt(`Quantity for ${symbol}?`, myPortfolioState.valuesHidden ? "" : quantity != null ? String(quantity) : "");
        if (rawQty === null || rawQty.trim() === "") return;
        const parsedQty = parseInt(rawQty, 10);
        if (!Number.isFinite(parsedQty) || parsedQty <= 0) {
            showMyPortfolioAlert("Quantity must be a positive whole number.", "danger");
            return;
        }

        const rawAvgPrice = window.prompt(`Average price for ${symbol}?`, myPortfolioState.valuesHidden ? "" : avgPrice != null ? String(avgPrice) : "");
        if (rawAvgPrice === null || rawAvgPrice.trim() === "") return;
        const parsedAvgPrice = parseFloat(rawAvgPrice);
        if (!Number.isFinite(parsedAvgPrice) || parsedAvgPrice <= 0) {
            showMyPortfolioAlert("Average price must be a positive number.", "danger");
            return;
        }

        // Blocking overlay from the instant the change is confirmed — bridges
        // the gap before Sync itself is running (tracked by `syncing`) so it
        // never flickers off between "saved" and "sync started".
        myPortfolioState.holdingActionPending = true;
        renderMyPortfolioSyncOverlay();
        try {
            await apiRequest(`/api/v1/my-portfolio/holdings/${encodeURIComponent(instrumentId)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ quantity: parsedQty, avg_price: String(parsedAvgPrice) }),
                skipToast: true,
            });
            showMyPortfolioAlert(`${symbol} updated. Syncing Portfolio to recalculate...`, "good");
            await loadMyPortfolioWorkspace();
            await startMyPortfolioSync();
            // startMyPortfolioSync only awaits the sync *starting*; render now so
            // the Actions column shows the busy/spinner state immediately rather
            // than waiting for the next poll tick. `syncing` is tracking the run
            // itself from here on, so the overlay stays up through it.
            renderMyPortfolioHoldings(myPortfolioState.holdings);
        } catch (err) {
            console.error("Failed to update My Portfolio holding", err);
            showMyPortfolioAlert(`Could not update ${symbol}. The existing holding is unchanged.`, "danger");
        } finally {
            myPortfolioState.holdingActionPending = false;
            renderMyPortfolioSyncOverlay();
        }
    }

    async function myPortfolioDeleteHolding(instrumentId) {
        if (!instrumentId) return;
        const { symbol, quantity, avgPrice } = myPortfolioHoldingLookup(instrumentId);
        const qtyText = quantity != null && !myPortfolioState.valuesHidden
            ? `${formatMyPortfolioNumber(quantity)} @ ${formatMyPortfolioMoney(avgPrice)} avg`
            : "";
        if (!window.confirm(`Delete ${symbol} ${qtyText} from My Portfolio? Re-import it to add it back.`)) return;

        myPortfolioState.holdingActionPending = true;
        renderMyPortfolioSyncOverlay();
        try {
            await apiRequest(`/api/v1/my-portfolio/holdings/${encodeURIComponent(instrumentId)}`, {
                method: "DELETE",
                skipToast: true,
            });
            showMyPortfolioAlert(`${symbol} removed. Syncing Portfolio to recalculate...`, "good");
            await loadMyPortfolioWorkspace();
            await startMyPortfolioSync();
            renderMyPortfolioHoldings(myPortfolioState.holdings);
        } catch (err) {
            console.error("Failed to delete My Portfolio holding", err);
            showMyPortfolioAlert(`Could not remove ${symbol}. The existing holding is unchanged.`, "danger");
        } finally {
            myPortfolioState.holdingActionPending = false;
            renderMyPortfolioSyncOverlay();
        }
    }

    function renderMyPortfolioHistory(imports) {
        if (!imports.length) {
            myPortfolioHistoryRows.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No import history yet.</td></tr>';
            renderMyPortfolioHistoryDisclosure();
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
        renderMyPortfolioHistoryDisclosure();
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
            if (myPortfolioPreview) closeModal(myPortfolioPreview);
            renderMyPortfolioInlinePreview(null);
            setMyPortfolioBusy();
            return;
        }
        renderMyPortfolioInlinePreview(preview);
        myPortfolioPreviewTotal.textContent = formatMyPortfolioNumber(preview.total_rows);
        myPortfolioPreviewValid.textContent = formatMyPortfolioNumber(preview.accepted_rows);
        myPortfolioPreviewInvalid.textContent = formatMyPortfolioNumber(preview.rejected_rows);
        myPortfolioPreviewUnresolved.textContent = formatMyPortfolioNumber(preview.unresolved_rows);
        myPortfolioPreviewAmbiguous.textContent = formatMyPortfolioNumber(preview.ambiguous_rows);
        myPortfolioPreviewDuplicates.textContent = formatMyPortfolioNumber(countMyPortfolioDuplicateRows(preview));

        const topMessages = [...(preview.errors || []), ...(preview.warnings || [])];
        const needsAttention = Number(preview.rejected_rows || 0)
            + Number(preview.unresolved_rows || 0)
            + Number(preview.ambiguous_rows || 0)
            + countMyPortfolioDuplicateRows(preview);
        if (preview.status === "FAILED") {
            showMyPortfolioAlert(topMessages.join(" ") || "The uploaded file could not be parsed. Review the required columns and upload again.", "danger");
        } else if (needsAttention === 0) {
            showMyPortfolioAlert("Preview is clean. Confirm & Sync Portfolio to replace holdings and refresh analysis.", "good");
        } else if (previewCanConfirm(preview)) {
            // Confirming is best-effort per row, never all-or-nothing: no
            // manual CSV edit needed. Any symbol unresolved only because
            // ATHENA hasn't tracked it yet is auto-onboarded on confirm;
            // whatever still can't be resolved, or is structurally invalid,
            // is simply excluded and reported — the rest still confirms.
            showMyPortfolioAlert(
                `${needsAttention} of ${preview.total_rows} row(s) need attention. Confirm & Sync will apply every row ATHENA can resolve and skip the rest.`,
                "warning"
            );
        } else {
            showMyPortfolioAlert("This preview has no rows to confirm. Upload a file with at least one holding.", "warning");
        }
        setMyPortfolioCancelLabel("Discard Upload");

        renderMyPortfolioPreviewRows(preview.rows || []);
        renderMyPortfolioReconciliation(preview.proposed_changes || []);
        myPortfolioUploadState.textContent = `Preview ready for ${preview.filename}. Confirm & Sync will replace holdings and refresh analysis in one step.`;
        setMyPortfolioBusy();
        openModal(myPortfolioPreview);
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
        if (!file || myPortfolioState.previewing || myPortfolioState.confirming || myPortfolioState.syncing) return;
        myPortfolioState.selectedFile = file;
        myPortfolioSelectedFile.textContent = file.name;
        myPortfolioUploadState.textContent = "Uploading and parsing on the server...";
        clearMyPortfolioAlert();
        renderMyPortfolioPreview(null);
        setMyPortfolioUploadStage("preview");
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
                renderMyPortfolioInlinePreview(null);
            }
        } finally {
            setMyPortfolioBusy();
        }
    }

    async function confirmMyPortfolioPreview() {
        const preview = myPortfolioState.preview;
        if (!previewCanConfirm(preview) || myPortfolioState.confirming) return;
        setMyPortfolioBusy({ confirming: true });
        myPortfolioUploadState.textContent = "Confirming holdings, then starting Portfolio Sync...";
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
            const skippedRows = result?.skipped_rows || [];
            const skippedText = skippedRows.length
                ? ` ${skippedRows.length} row(s) skipped: ${skippedRows.map(row => `${row.raw_symbol} (${row.reason})`).join(", ")}.`
                : "";
            const successMessage = `Portfolio update confirmed. Added ${counts.ADDED || 0}, updated ${counts.UPDATED || 0}, removed ${counts.REMOVED || 0}, unchanged ${counts.UNCHANGED || 0}.${skippedText}`;
            if (myPortfolioFileInput) myPortfolioFileInput.value = "";
            if (myPortfolioSelectedFile) myPortfolioSelectedFile.textContent = "No file selected";
            myPortfolioState.preview = null;
            myPortfolioState.selectedFile = null;
            if (myPortfolioPreview) closeModal(myPortfolioPreview);
            renderMyPortfolioInlinePreview(null);
            myPortfolioUploadState.textContent = "Holdings confirmed. Refreshing Portfolio analysis...";
            await loadMyPortfolioWorkspace();
            showMyPortfolioAlert(`${successMessage} Starting Portfolio Sync now...`, skippedRows.length ? "warning" : "good");
            await startMyPortfolioSync({
                source: "upload-confirm",
                successMessage: `${successMessage} Portfolio analysis refreshed.`,
                partialMessage: `${successMessage} Portfolio Sync finished partial — some holdings could not be analyzed.`,
            });
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
                setMyPortfolioCancelLabel("Discard Upload");
                myPortfolioUploadState.textContent = "Preview is stale. Discard it and choose the holdings file again.";
            } else {
                // Only reachable when literally every row in the file is
                // unconfirmable (see previewCanConfirm) — the server's own
                // detail message names exactly why, so surface it verbatim
                // rather than a generic "fix the file" that no longer applies.
                showMyPortfolioAlert(detail || "Confirmation failed. Review the preview and retry.", "danger");
            }
        } finally {
            setMyPortfolioBusy();
        }
    }

    function syncRunTerminal(status) {
        return ["SUCCESS", "PARTIAL", "FAILED", "CANCELLED"].includes(String(status || "").toUpperCase());
    }

    // Full blocking overlay, driven by the same `syncing`/`syncRun` state
    // the Sync Portfolio button and holdings table already track correctly
    // for the whole run — plus `holdingActionPending`, which covers the
    // brief window after an Edit/Delete is confirmed but before Sync has
    // actually started. Shows/hides for BOTH the manual Sync Portfolio
    // button and an Edit/Delete-triggered sync — one consistent "please
    // wait" experience for the one full-portfolio-recalculation operation
    // that exists, regardless of what triggered it.
    function renderMyPortfolioSyncOverlay() {
        if (!myPortfolioSyncOverlay) return;
        const active = Boolean(myPortfolioState.syncing || myPortfolioState.holdingActionPending);
        myPortfolioSyncOverlay.classList.toggle("active", active);
        document.body.classList.toggle("my-portfolio-sync-blocked", active);
        myPortfolioSyncOverlay.setAttribute("aria-hidden", active ? "false" : "true");
        if (!active || !myPortfolioSyncOverlayDetail) return;
        const run = myPortfolioState.syncRun;
        const processed = Number(run?.progress?.processed_holdings || 0);
        const total = Number(run?.total_holdings || 0);
        myPortfolioSyncOverlayDetail.textContent = total > 0
            ? `Recalculating ${processed} of ${total} holdings…`
            : myPortfolioState.holdingActionPending
                ? "Saving your change…"
                : "Starting Portfolio Sync…";
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
        setMyPortfolioBusy({ syncing: syncRunTerminal(status) ? myPortfolioState.syncing : true });
        renderMyPortfolioSyncOverlay();
    }

    async function startMyPortfolioSync(options = {}) {
        if (myPortfolioState.syncing) return;
        myPortfolioState.syncCompletion = options;
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
            myPortfolioState.syncCompletion = null;
            setMyPortfolioBusy({ syncing: false });
            renderMyPortfolioSyncOverlay();
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
                if (run.status === "SUCCESS" || run.status === "PARTIAL") {
                    const snapshotRes = await apiRequest("/api/v1/my-portfolio/snapshot", { skipToast: true });
                    myPortfolioState.snapshot = snapshotRes?.data || null;
                    renderMyPortfolioHoldings(myPortfolioState.holdings);
                    renderMyPortfolioSummary();
                    const completion = myPortfolioState.syncCompletion || {};
                    myPortfolioState.syncCompletion = null;
                    if (completion.source === "upload-confirm") {
                        myPortfolioUploadState.textContent = "Portfolio updated and synced. Choose another holdings file to update again.";
                    }
                    if (run.status === "PARTIAL") {
                        showMyPortfolioAlert(
                            completion.partialMessage
                                ? `${completion.partialMessage} ${run.succeeded_holdings} of ${run.total_holdings} holdings analyzed.${myPortfolioSyncFailureSummary(run)}`
                                : `Portfolio Sync partial — ${run.succeeded_holdings} of ${run.total_holdings} holdings analyzed.${myPortfolioSyncFailureSummary(run)} Failed rows remain visible in the table.`,
                            "warning"
                        );
                    } else {
                        showMyPortfolioAlert(completion.successMessage || "Portfolio Sync completed. Snapshot refreshed.", "good");
                    }
                } else {
                    myPortfolioState.syncCompletion = null;
                    showMyPortfolioAlert("Portfolio Sync failed. Previous completed snapshot remains unchanged.", "danger");
                    // Keep the row actions aligned with the terminal sync
                    // state before the full-page blocker is dismissed below.
                    renderMyPortfolioHoldings(myPortfolioState.holdings);
                }
                setMyPortfolioBusy({ syncing: false });
                renderMyPortfolioSyncOverlay();
                return;
            }
            myPortfolioState.syncPollTimer = setTimeout(() => pollMyPortfolioSync(syncRunId), 1500);
        } catch (err) {
            console.error("Failed to poll My Portfolio Sync", err);
            showMyPortfolioAlert("Could not read Portfolio Sync status. Previous completed snapshot remains unchanged.", "danger");
            setMyPortfolioBusy({ syncing: false });
            renderMyPortfolioHoldings(myPortfolioState.holdings);
            renderMyPortfolioSyncOverlay();
        }
    }

    function clearMyPortfolioPreview() {
        myPortfolioState.preview = null;
        myPortfolioState.selectedFile = null;
        if (myPortfolioFileInput) myPortfolioFileInput.value = "";
        if (myPortfolioSelectedFile) myPortfolioSelectedFile.textContent = "No file selected";
        if (myPortfolioPreview) closeModal(myPortfolioPreview);
        renderMyPortfolioInlinePreview(null);
        if (myPortfolioUploadState) myPortfolioUploadState.textContent = "Choose a holdings file to create a preview.";
        setMyPortfolioCancelLabel("Discard Upload");
        clearMyPortfolioAlert();
        setMyPortfolioBusy();
        myPortfolioFileInput?.focus();
    }

    function resetMyPortfolioGate() {
        const unlocked = myPortfolioResetConfirm?.value === "RESET";
        if (myPortfolioResetSubmit) myPortfolioResetSubmit.disabled = !unlocked;
        if (myPortfolioResetGateStatus) {
            myPortfolioResetGateStatus.textContent = unlocked
                ? "Unlocked. This will permanently clear My Portfolio state."
                : "Locked until RESET matches exactly.";
            myPortfolioResetGateStatus.classList.toggle("locked", !unlocked);
            myPortfolioResetGateStatus.classList.toggle("unlocked", unlocked);
        }
    }

    function openMyPortfolioResetModal() {
        if (!myPortfolioResetModal) return;
        if (myPortfolioResetConfirm) myPortfolioResetConfirm.value = "";
        resetMyPortfolioGate();
        openModal(myPortfolioResetModal);
        myPortfolioResetConfirm?.focus();
    }

    function closeMyPortfolioResetModal() {
        if (myPortfolioResetModal) closeModal(myPortfolioResetModal);
    }

    async function resetMyPortfolio() {
        if (myPortfolioResetConfirm?.value !== "RESET") {
            resetMyPortfolioGate();
            return;
        }
        if (myPortfolioResetSubmit) myPortfolioResetSubmit.disabled = true;
        try {
            const response = await apiRequest("/api/v1/my-portfolio", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ confirmation: "RESET" }),
                skipToast: true,
            });
            const counts = response?.data?.deleted_counts || {};
            const totalDeleted = Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0);
            closeMyPortfolioResetModal();
            myPortfolioState.preview = null;
            myPortfolioState.selectedFile = null;
            myPortfolioState.snapshot = null;
            myPortfolioState.holdings = [];
            myPortfolioState.imports = [];
            myPortfolioState.snapshotRowsByKey = {};
            resetMyPortfolioTriageState();
            if (myPortfolioFileInput) myPortfolioFileInput.value = "";
            if (myPortfolioSelectedFile) myPortfolioSelectedFile.textContent = "No file selected";
            if (myPortfolioPreview) closeModal(myPortfolioPreview);
            await loadMyPortfolioWorkspace();
            showMyPortfolioAlert(`My Portfolio reset complete. Deleted ${formatMyPortfolioNumber(totalDeleted)} My Portfolio record(s).`, "good");
        } catch (err) {
            console.error("Failed to reset My Portfolio", err);
            const detail = String(err?.data?.detail || "");
            showMyPortfolioAlert(detail || "Could not reset My Portfolio. Existing data is unchanged.", "danger");
            resetMyPortfolioGate();
        }
    }

    myPortfolioFileInput?.addEventListener("change", event => {
        const file = event.target.files && event.target.files[0];
        uploadMyPortfolioFile(file);
    });
    myPortfolioConfirm?.addEventListener("click", confirmMyPortfolioPreview);
    myPortfolioCancelPreview?.addEventListener("click", clearMyPortfolioPreview);
    myPortfolioPreviewOpen?.addEventListener("click", () => openModal(myPortfolioPreview));
    myPortfolioPreviewClose?.addEventListener("click", () => closeModal(myPortfolioPreview));
    myPortfolioSync?.addEventListener("click", () => startMyPortfolioSync());
    myPortfolioSortField?.addEventListener("change", event => {
        myPortfolioState.sort.key = event.target.value || "pnl_pct";
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    });
    myPortfolioSortDirection?.addEventListener("click", () => {
        myPortfolioState.sort.direction = myPortfolioState.sort.direction === "asc" ? "desc" : "asc";
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    });
    myPortfolioSortReset?.addEventListener("click", () => {
        const profile = currentMyPortfolioTableProfile();
        myPortfolioState.sort = { key: profile.sort.key, direction: profile.sort.direction };
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    });
    myPortfolioQueueAll?.addEventListener("click", () => setMyPortfolioQueueView(false));
    myPortfolioQueueOnly?.addEventListener("click", () => setMyPortfolioQueueView(true));
    myPortfolioTriageClear?.addEventListener("click", clearMyPortfolioTriage);
    document.getElementById("my-portfolio-view-holdings")?.addEventListener("click", scrollMyPortfolioHoldingsIntoView);
    document.getElementById("my-portfolio-triage-filters-toggle")?.addEventListener("click", () => {
        setMyPortfolioTriageFiltersExpanded(!myPortfolioState.triageFiltersExpanded);
    });
    myPortfolioUploadShortcut?.addEventListener("click", () => {
        setMyPortfolioUploadPanelOpen(!myPortfolioState.uploadPanelOpen);
    });
    myPortfolioUploadPanelClose?.addEventListener("click", () => setMyPortfolioUploadPanelOpen(false));
    document.getElementById("my-portfolio-review-start")?.addEventListener("click", startMyPortfolioReviewSession);
    document.getElementById("my-portfolio-review-prev")?.addEventListener("click", () => stepMyPortfolioReviewSession(-1));
    document.getElementById("my-portfolio-review-next")?.addEventListener("click", () => stepMyPortfolioReviewSession(1));
    document.getElementById("my-portfolio-review-mark")?.addEventListener("click", () => markMyPortfolioReviewSession("reviewed"));
    document.getElementById("my-portfolio-review-defer")?.addEventListener("click", () => markMyPortfolioReviewSession("defer"));
    document.getElementById("my-portfolio-review-exit")?.addEventListener("click", () => {
        endMyPortfolioReviewSession();
        closeModal(myPortfolioDetailModal);
    });
    document.addEventListener("keydown", event => {
        if (event.key === "Escape" && myPortfolioState.reviewSession.active) {
            endMyPortfolioReviewSession();
        }
    });
    myPortfolioCommandDashboard?.addEventListener("click", event => {
        const attentionChip = event.target.closest(".my-portfolio-triage-chip[data-triage-available='true']");
        if (attentionChip) {
            toggleMyPortfolioAttentionFilter(attentionChip.getAttribute("data-triage-filter"));
            return;
        }
        const smartChip = event.target.closest(".my-portfolio-smart-chip");
        if (smartChip) {
            toggleMyPortfolioSmartFilter(
                smartChip.getAttribute("data-smart-group"),
                smartChip.getAttribute("data-smart-value")
            );
        }
    });
    myPortfolioTableProfile?.addEventListener("change", event => {
        setMyPortfolioTableProfile(event.target.value);
    });
    myPortfolioHeatmapSize?.addEventListener("change", event => {
        setMyPortfolioHeatmapSize(event.target.value);
    });
    myPortfolioHeatmapColor?.addEventListener("change", event => {
        setMyPortfolioHeatmapColor(event.target.value);
    });
    myPortfolioRiskToggle?.addEventListener("click", () => {
        setMyPortfolioRiskExpanded(!myPortfolioState.riskExpanded);
    });
    myPortfolioHeatmapToggle?.addEventListener("click", () => {
        setMyPortfolioHeatmapExpanded(!myPortfolioState.heatmapExpanded);
    });
    myPortfolioHeatmapBody?.addEventListener("click", event => {
        const tile = event.target.closest(".my-portfolio-heatmap-tile[data-instrument-id]");
        if (!tile) return;
        openMyPortfolioDetail(tile.getAttribute("data-instrument-id"));
    });
    myPortfolioPrivacyToggle?.addEventListener("click", () => {
        setMyPortfolioValuesHidden(!myPortfolioState.valuesHidden);
    });
    myPortfolioExportToggle?.addEventListener("click", event => {
        event.stopPropagation();
        if (!myPortfolioExportPanel) return;
        myPortfolioExportPanel.hidden = !myPortfolioExportPanel.hidden;
        renderMyPortfolioExportPanel();
    });
    myPortfolioExportPanel?.addEventListener("click", event => {
        event.stopPropagation();
    });
    myPortfolioExportScope?.addEventListener("change", () => {
        renderMyPortfolioExportColumns();
        setMyPortfolioExportStatus("Choose a dataset, format, and optional column set.", "neutral");
    });
    myPortfolioExportFormat?.addEventListener("change", () => {
        setMyPortfolioExportStatus("Choose a dataset, format, and optional column set.", "neutral");
    });
    myPortfolioExportColumns?.addEventListener("change", updateMyPortfolioExportSelectionFromInputs);
    myPortfolioExportPresetEssential?.addEventListener("click", () => applyMyPortfolioExportPreset("essential"));
    myPortfolioExportPresetReview?.addEventListener("click", () => applyMyPortfolioExportPreset("review"));
    myPortfolioExportPresetDailyReview?.addEventListener("click", () => applyMyPortfolioExportPreset("daily_review"));
    myPortfolioExportPresetFullAudit?.addEventListener("click", () => applyMyPortfolioExportPreset("full_audit"));
    myPortfolioExportPresetPrivate?.addEventListener("click", () => applyMyPortfolioExportPreset("private_sharing"));
    myPortfolioExportSelectAll?.addEventListener("click", () => {
        myPortfolioState.exportColumnsByScope[currentMyPortfolioExportScope()] = null;
        renderMyPortfolioExportColumns();
    });
    myPortfolioExportClear?.addEventListener("click", () => {
        myPortfolioState.exportColumnsByScope[currentMyPortfolioExportScope()] = [];
        renderMyPortfolioExportColumns();
        setMyPortfolioExportStatus("Select at least one column to export.", "danger");
    });
    myPortfolioExportDownload?.addEventListener("click", downloadMyPortfolioExport);
    myPortfolioHistoryToggle?.addEventListener("click", () => {
        myPortfolioState.historyExpanded = !myPortfolioState.historyExpanded;
        renderMyPortfolioHistoryDisclosure();
    });
    myPortfolioHoldingsCard?.addEventListener("click", event => {
        const th = event.target.closest("th[data-sort-key]");
        if (!th) return;
        const key = th.getAttribute("data-sort-key");
        if (!key) return;
        if (myPortfolioState.sort.key === key) {
            myPortfolioState.sort.direction = myPortfolioState.sort.direction === "asc" ? "desc" : "asc";
        } else {
            myPortfolioState.sort.key = key;
            myPortfolioState.sort.direction = key === "symbol" ? "asc" : "desc";
        }
        renderMyPortfolioHoldings(myPortfolioSourceRows());
    });
    myPortfolioResetOpen?.addEventListener("click", openMyPortfolioResetModal);
    myPortfolioResetClose?.addEventListener("click", closeMyPortfolioResetModal);
    myPortfolioResetConfirm?.addEventListener("input", resetMyPortfolioGate);
    myPortfolioResetSubmit?.addEventListener("click", resetMyPortfolio);
    (function loadMyPortfolioLocalPreferences() {
        try {
            const savedProfile = window.localStorage.getItem("athena.myPortfolio.tableProfile");
            if (savedProfile && MY_PORTFOLIO_TABLE_PROFILES[savedProfile]) {
                myPortfolioState.tableProfile = savedProfile;
                myPortfolioState.density = MY_PORTFOLIO_TABLE_PROFILES[savedProfile].density;
                myPortfolioState.sort = {
                    key: MY_PORTFOLIO_TABLE_PROFILES[savedProfile].sort.key,
                    direction: MY_PORTFOLIO_TABLE_PROFILES[savedProfile].sort.direction,
                };
            }
            const savedPins = JSON.parse(window.localStorage.getItem("athena.myPortfolio.pinnedInstrumentIds") || "[]");
            if (Array.isArray(savedPins)) {
                myPortfolioState.pinnedInstrumentIds = savedPins.filter(id => typeof id === "string" && id);
            }
            const savedHeatmapSize = window.localStorage.getItem("athena.myPortfolio.heatmapSize");
            if (savedHeatmapSize && MY_PORTFOLIO_HEATMAP_SIZES[savedHeatmapSize]) {
                myPortfolioState.heatmap.size = savedHeatmapSize;
            }
            const savedHeatmapColor = window.localStorage.getItem("athena.myPortfolio.heatmapColor");
            if (savedHeatmapColor && MY_PORTFOLIO_HEATMAP_COLORS[savedHeatmapColor]) {
                myPortfolioState.heatmap.color = savedHeatmapColor;
            }
            const savedRiskExpanded = window.localStorage.getItem("athena.myPortfolio.riskExpanded");
            if (savedRiskExpanded === "false") myPortfolioState.riskExpanded = false;
            if (savedRiskExpanded === "true") myPortfolioState.riskExpanded = true;
            const savedHeatmapExpanded = window.localStorage.getItem("athena.myPortfolio.heatmapExpanded");
            if (savedHeatmapExpanded === "false") myPortfolioState.heatmapExpanded = false;
            if (savedHeatmapExpanded === "true") myPortfolioState.heatmapExpanded = true;
            const savedTriageFiltersExpanded = window.localStorage.getItem("athena.myPortfolio.triageFiltersExpanded");
            if (savedTriageFiltersExpanded === "false") myPortfolioState.triageFiltersExpanded = false;
            if (savedTriageFiltersExpanded === "true") myPortfolioState.triageFiltersExpanded = true;
        } catch (err) {
            // Browser privacy/storage restrictions should not break rendering.
        }
    })();
    renderMyPortfolioPrivacyToggle();
    renderMyPortfolioExportPanel();
    renderMyPortfolioDensityControls();
    renderMyPortfolioRiskDisclosure();
    renderMyPortfolioHeatmapDisclosure();
    renderMyPortfolioTriageFiltersDisclosure();
    renderMyPortfolioExportColumns();
    myPortfolioSectionNav?.querySelectorAll(".my-portfolio-section-nav-item").forEach(item => {
        item.addEventListener("click", () => {
            const key = item.dataset.navTarget;
            setMyPortfolioActiveNavItem(key);
            scrollMyPortfolioToSection(key);
        });
    });
    initMyPortfolioSectionNavObserver();
    scheduleMyPortfolioHoldingsScrollChrome();
    window.addEventListener("scroll", scheduleMyPortfolioHoldingsScrollChrome, { passive: true });
    window.addEventListener("resize", scheduleMyPortfolioHoldingsScrollChrome);
    myPortfolioWorkspaceViewport?.addEventListener("scroll", scheduleMyPortfolioHoldingsScrollChrome, { passive: true });
    myPortfolioHoldingsScroll?.addEventListener("scroll", syncMyPortfolioTheadDock, { passive: true });
    window.addEventListener("click", event => {
        if (myPortfolioExportPanel && !myPortfolioExportPanel.hidden) {
            myPortfolioExportPanel.hidden = true;
            renderMyPortfolioExportPanel();
        }
        if (event.target === myPortfolioResetModal) closeMyPortfolioResetModal();
        if (event.target === myPortfolioPreview) closeModal(myPortfolioPreview);
    });
