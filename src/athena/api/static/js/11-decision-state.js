

    let activeTrace = null;
    let allTraceDecisionsList = [];
    let traceDecisionsList = [];
    // Owner-reported (2026-08-01): typing in the Validation Workbench search
    // box froze the UI. Root cause — currentOpenableDecisionForSymbol/
    // latestDecisionForSymbol each did a full .find() scan of
    // traceDecisionsList (thousands of decisions) for EVERY row on EVERY
    // render, i.e. O(rows × decisions) on every keystroke. traceDecisionsList
    // is already deduped to one decision per instrument, so a symbol->decision
    // Map (rebuilt once whenever the list itself is reassigned) turns every
    // lookup into O(1), and a render into O(rows + decisions) instead of
    // O(rows × decisions).
    let traceDecisionsBySymbol = new Map();
    function rebuildTraceDecisionsBySymbolIndex() {
        traceDecisionsBySymbol = new Map();
        for (const d of traceDecisionsList) {
            const instrument = String(d && d.metadata && d.metadata.instrument_id || "")
                .toUpperCase()
                .replace(/^NSE:|^BSE:/, "");
            if (instrument) traceDecisionsBySymbol.set(instrument, d);
        }
    }
    let activeDecisionId = null;
    let activeDecisionData = null;
    let activeDepth = null;
    let activeContextData = null;
    let activeJournalEntry = null;
    let activeTradeOutcome = null;
    let activeAnalogs = null;
    let activeCounterfactual = null;
    let activePlanFreshness = null;
    let activeChartSeries = null;
    let activeChartPlan = null;
    let activeBriefQuote = null;
    let selectedStageId = null;
    // Persists across decision switches on purpose — flipping through several
    // decisions to compare the same aspect (e.g. Analysis) should not keep
    // resetting back to Setup each time (graceful selection, UI overhaul).
    let activeBriefTab = "setup";

    function escapeDecisionHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function istDateKey() {
        const parts = new Intl.DateTimeFormat("en-GB", {
            timeZone: "Asia/Kolkata",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }).formatToParts(new Date());
        const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
        return `${values.year}-${values.month}-${values.day}`;
    }

    function dismissedDecisionStorageKey() {
        return `athena.dismissed-decisions.${istDateKey()}`;
    }

    function loadDismissedDecisionSymbols() {
        try {
            const raw = JSON.parse(localStorage.getItem(dismissedDecisionStorageKey()) || "[]");
            return new Set(Array.isArray(raw) ? raw.map(v => String(v).toUpperCase()) : []);
        } catch (_err) {
            return new Set();
        }
    }

    const dismissedDecisionSymbols = loadDismissedDecisionSymbols();

    function persistDismissedDecisionSymbols() {
        try {
            localStorage.setItem(
                dismissedDecisionStorageKey(),
                JSON.stringify(Array.from(dismissedDecisionSymbols).sort())
            );
        } catch (_err) {
            showToast("Could not persist dismissed decisions in this browser", "warning");
        }
    }

    function decisionInstrumentKey(decision) {
        const meta = decision && decision.metadata ? decision.metadata : {};
        return String(meta.instrument_id || meta.decision_id || "").toUpperCase();
    }
