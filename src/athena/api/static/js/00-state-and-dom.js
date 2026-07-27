
    // ---------------------------------------------------------------------------
    // State Registry
    // ---------------------------------------------------------------------------
    const AUTH_ACCESS_KEY = "athena.access_token";
    const AUTH_REFRESH_KEY = "athena.refresh_token";

    const state = {
        activeTab: "overview",
        authRequired: false,
        authenticated: false,
        kiteRequired: false,
        kiteConnected: false,
        kiteBlocking: false,
        kiteUserId: null,
        telemetry: {
            requestId: "unknown",
            correlationId: "unknown",
            latencyMs: 0
        }
    };

    // ---------------------------------------------------------------------------
    // Selector Bindings
    // ---------------------------------------------------------------------------
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("page-title");
    const refreshTrigger = document.getElementById("refresh-trigger");
    const healthIndicator = document.getElementById("system-health-indicator");
    const appShell = document.getElementById("app");
    const unlockGate = document.getElementById("unlock-gate");
    const unlockForm = document.getElementById("unlock-form");
    const unlockUsername = document.getElementById("unlock-username");
    const unlockPassword = document.getElementById("unlock-password");
    const unlockError = document.getElementById("unlock-error");
    const unlockSubmit = document.getElementById("unlock-submit");
    const logoutBtn = document.getElementById("logout-btn");
    const profileName = document.getElementById("profile-name");
    const profileRole = document.getElementById("profile-role");
    const validateOverlay = document.getElementById("validate-overlay");
    const validateOverlaySymbols = document.getElementById("validate-overlay-symbols");
    const validateOverlayDetail = document.getElementById("validate-overlay-detail");
    const kiteGate = document.getElementById("kite-gate");
    const kiteGateDetail = document.getElementById("kite-gate-detail");
    const kiteGateTitle = document.getElementById("kite-gate-title");
    const kiteGateError = document.getElementById("kite-gate-error");
    const kiteGateClose = document.getElementById("kite-gate-close");
    const kiteStartAuth = document.getElementById("kite-start-auth");
    const kiteCompleteAuth = document.getElementById("kite-complete-auth");
    const kiteRecheck = document.getElementById("kite-recheck");
    const kiteDisconnect = document.getElementById("kite-disconnect");
    const kiteRequestToken = document.getElementById("kite-request-token");
    const kiteStatusBtn = document.getElementById("kite-status-btn");
    const kiteStatusLabel = document.getElementById("kite-status-label");
    
    // Telemetry DOM Bindings
    const reqIdElement = document.getElementById("header-req-id");
    const corrIdElement = document.getElementById("header-corr-id");
    const latencyElement = document.getElementById("header-latency");

    // Portfolio DOM Bindings
    const valTotalPortfolio = document.getElementById("val-total-portfolio");
    const valCashAvailable = document.getElementById("val-cash-available");
    const valCashReserved = document.getElementById("val-cash-reserved");
    const valActivePositions = document.getElementById("val-active-positions");
    const valTotalClosed = document.getElementById("val-total-closed");
    const valDayChange = document.getElementById("val-day-change");
    const valDayChangeText = document.getElementById("val-day-change-text");
    const poolAllocatedVal = document.getElementById("pool-allocated-val");
    const poolAllocatedBar = document.getElementById("pool-allocated-bar");
    const poolReserveVal = document.getElementById("pool-reserve-val");
    const poolReserveBar = document.getElementById("pool-reserve-bar");
    const holdingsTbody = document.getElementById("holdings-tbody");
    
    // Charts DOM Bindings
    const navChartCtx = document.getElementById("nav-chart")?.getContext("2d");
    const sectorChartCtx = document.getElementById("sector-chart")?.getContext("2d");
    const backtestComparisonChartCtx = document.getElementById("backtest-comparison-chart")?.getContext("2d");
    const opsTelemetryChartCtx = document.getElementById("ops-telemetry-chart")?.getContext("2d");
    let navChart = null;
    let sectorChart = null;
    let backtestComparisonChart = null;
    let opsTelemetryChart = null;
    let opsEventSource = null;