/*
  DarvaX's own dashboard script (ADR-010 DX-4).

  Deliberately standalone: this file is NOT part of ATHENA's DASHBOARD_JS_PARTS
  and shares no state with dashboard.js. It renders only what the DarvaX API
  returns — every explanation shown was computed and persisted by the DarvaX
  engine (ADR-005's principle), so this script never recomputes, re-words, or
  infers a rationale.

  Auth: DarvaX delegates to ATHENA rather than running its own login. Same
  origin, so the dashboard's existing session token is reused from
  sessionStorage. Note sessionStorage is per browsing context: opening /darvax/
  in a brand-new tab has no token, which is reported honestly rather than
  silently failing.
*/
(function () {
  "use strict";

  // The key ATHENA's dashboard writes its access token under.
  var ATHENA_TOKEN_KEY = "athena.access_token";

  //: Rows requested for one screen. The API's own maximum — a universe larger
  //: than this truncates, which the meta line then says out loud rather than
  //: quietly reporting fewer instruments than were actually screened.
  var SCREEN_ROW_LIMIT = 5000;

  var els = {
    note: document.getElementById("note"),
    table: document.getElementById("table"),
    rows: document.getElementById("rows"),
    empty: document.getElementById("empty"),
    symbols: document.getElementById("symbols"),
    scan: document.getElementById("scan"),
    refresh: document.getElementById("refresh"),
    version: document.getElementById("version")
  };

  // States that read as constructive vs destructive vs neutral. Purely
  // presentational: the engine assigns meaning, this only picks a colour.
  var TONE = {
    BREAKOUT: "up",
    BREAKOUT_RETEST: "up",
    INSIDE_TOPMOST_BOX: "flat",
    NOT_IN_TOPMOST_BOX: "down",
    BELOW_BOX_BOTTOM: "down",
    NO_BOX: "flat"
  };

  function token() {
    try {
      return sessionStorage.getItem(ATHENA_TOKEN_KEY) || "";
    } catch (err) {
      return "";
    }
  }

  function say(message, isError) {
    els.note.textContent = message || "";
    els.note.className = isError ? "note err" : "note";
  }

  function request(path, options) {
    var opts = options || {};
    var headers = { "Content-Type": "application/json" };
    var bearer = token();
    if (bearer) headers.Authorization = "Bearer " + bearer;
    return fetch(path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (response) {
      if (response.status === 401 || response.status === 403) {
        throw new Error(
          "Not authenticated to ATHENA in this browser tab. Open the ATHENA " +
          "dashboard and unlock, then reload this page."
        );
      }
      return response.json().then(function (payload) {
        if (!response.ok) {
          throw new Error(payload.detail || payload.title || "Request failed");
        }
        return payload;
      });
    });
  }

  function text(value) {
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }

  function el(tag, className, content) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function boxLabel(signal) {
    if (!signal.box_top) return "—";
    return signal.box_bottom + " – " + signal.box_top;
  }

  function renderDetailRow(signal) {
    var row = el("tr", "detail");
    row.hidden = true;
    var cell = document.createElement("td");
    cell.colSpan = 7;

    cell.appendChild(el("p", "label", "Why DarvaX reads it this way"));
    cell.appendChild(el("p", "why", signal.explanation));

    if (signal.evidence && signal.evidence.length) {
      cell.appendChild(el("p", "label", "Evidence (persisted with the signal)"));
      var list = el("ul", "evidence");
      signal.evidence.forEach(function (item) {
        var li = document.createElement("li");
        li.appendChild(el("span", "k", item.name));
        li.appendChild(el("span", "v", item.value));
        li.appendChild(el("span", "d", item.detail));
        list.appendChild(li);
      });
      cell.appendChild(list);
    }

    if (signal.stop) {
      cell.appendChild(el("p", "label", "Stop derivation"));
      cell.appendChild(el("p", "why", signal.stop.detail));
    }

    cell.appendChild(
      el(
        "p",
        "trace",
        "signal " + signal.signal_id +
        "  ·  methodology " + signal.methodology_digest +
        "  ·  darvax " + signal.darvax_version +
        "  ·  " + signal.status
      )
    );

    row.appendChild(cell);
    return row;
  }

  function renderRow(signal) {
    var head = el("tr", "head-row");

    head.appendChild(el("td", "sym", signal.symbol));

    var stateCell = document.createElement("td");
    stateCell.appendChild(
      el("span", "state " + (TONE[signal.signal_type] || "flat"), signal.signal_type)
    );
    head.appendChild(stateCell);

    head.appendChild(el("td", "mono", text(signal.darvas_rule)));
    head.appendChild(el("td", "num mono", text(signal.close)));
    head.appendChild(el("td", "mono", boxLabel(signal)));
    head.appendChild(el("td", "num mono", signal.stop ? signal.stop.price : "—"));
    head.appendChild(el("td", "mono", signal.as_of.slice(0, 10)));

    var detail = renderDetailRow(signal);
    head.addEventListener("click", function () {
      detail.hidden = !detail.hidden;
    });

    return [head, detail];
  }

  function render(signals) {
    els.rows.textContent = "";
    var hasRows = signals.length > 0;
    els.table.hidden = !hasRows;
    els.empty.hidden = hasRows;
    signals.forEach(function (signal) {
      renderRow(signal).forEach(function (node) {
        els.rows.appendChild(node);
      });
    });
  }

  function load() {
    say("Loading DarvaX signals…");
    return request("/darvax/api/signals?limit=200")
      .then(function (payload) {
        render(payload.data || []);
        els.version.textContent = "v" + payload.darvax_version;
        say(
          (payload.count || 0) + " stored signal(s). Click a row for the " +
          "persisted explanation and evidence."
        );
      })
      .catch(function (err) {
        render([]);
        say(err.message, true);
      });
  }

  function parseSymbols(raw) {
    return raw
      .split(/[,\s]+/)
      .map(function (part) { return part.trim().toUpperCase(); })
      .filter(Boolean)
      .map(function (symbol) {
        // Accept bare symbols and fully-qualified ids alike.
        return symbol.indexOf(":") === -1 ? "NSE:" + symbol : symbol;
      });
  }

  function scan() {
    var ids = parseSymbols(els.symbols.value || "");
    if (!ids.length) {
      say("Enter at least one symbol to scan.", true);
      return;
    }
    els.scan.disabled = true;
    say("Scanning " + ids.length + " instrument(s)…");
    request("/darvax/api/scan", { method: "POST", body: { instrument_ids: ids } })
      .then(function (payload) {
        var skipped = payload.skipped || [];
        var message = "Evaluated " + payload.evaluated + " of " + payload.requested + ".";
        if (skipped.length) {
          // Skips are surfaced, never swallowed: a symbol DarvaX could not read
          // is information the owner needs.
          message += " Skipped: " + skipped.map(function (s) {
            return s.instrument_id + " (" + s.reason + ")";
          }).join("; ");
        }
        say(message, skipped.length > 0);
        return load().then(function () {
          if (skipped.length) say(message, true);
        });
      })
      .catch(function (err) {
        say(err.message, true);
      })
      .finally(function () {
        els.scan.disabled = false;
      });
  }

  // When embedded in ATHENA's DarvaX tab (ADR-010 Amendment 1), the "← ATHENA"
  // link is redundant chrome — you are already in ATHENA. The experimental
  // banner is deliberately NOT hidden here or anywhere else: it is a
  // correctness requirement, not decoration.
  if (window.location.search.indexOf("embedded=1") !== -1) {
    document.body.classList.add("embedded");
    var back = document.querySelector("a.link[href='/dashboard/']");
    if (back) back.remove();
  }

  els.scan.addEventListener("click", scan);
  els.refresh.addEventListener("click", load);
  els.symbols.addEventListener("keydown", function (event) {
    if (event.key === "Enter") scan();
  });

  // ======================================================================= //
  // Screener (DX-6c, ADR-010 Amendment 2)
  //
  // Renders what the screening engine persisted. It never classifies a tier,
  // re-measures a distance, or rewords an explanation — those are computed once
  // and stored, and this file only draws them (ADR-005).
  // ======================================================================= //

  var S = {
    note: document.getElementById("screen-note"),
    empty: document.getElementById("screen-empty"),
    tiers: document.getElementById("tiers"),
    meta: document.getElementById("sweep-meta"),
    filter: document.getElementById("filter"),
    toggleOther: document.getElementById("toggle-other"),
    sweepBtn: document.getElementById("sweep"),
    cancelBtn: document.getElementById("cancel-sweep"),
    progress: document.getElementById("progress"),
    pStage: document.getElementById("p-stage"),
    pDone: document.getElementById("p-done"),
    pTotal: document.getElementById("p-total"),
    pElapsed: document.getElementById("p-elapsed"),
    pBar: document.getElementById("p-bar"),
    skipped: document.getElementById("skipped"),
    skippedSummary: document.getElementById("skipped-summary"),
    skippedList: document.getElementById("skipped-list"),
    screener: document.getElementById("screener"),
    signalsView: document.getElementById("signals-view"),
    viewScreener: document.getElementById("view-screener"),
    viewSignals: document.getElementById("view-signals"),
    guideOpen: document.getElementById("guide-open"),
    guideClose: document.getElementById("guide-close"),
    guide: document.getElementById("guide"),
    guideBackdrop: document.getElementById("guide-backdrop"),
    // Advisor zones (DX-7c)
    posZone: document.getElementById("positions-zone"),
    posChips: document.getElementById("pos-chips"),
    posAddToggle: document.getElementById("pos-add-toggle"),
    posForm: document.getElementById("pos-form"),
    posNote: document.getElementById("pos-note"),
    posEmpty: document.getElementById("pos-empty"),
    pfSymbol: document.getElementById("pf-symbol"),
    pfQty: document.getElementById("pf-qty"),
    pfPrice: document.getElementById("pf-price"),
    pfDate: document.getElementById("pf-date"),
    pfStop: document.getElementById("pf-stop"),
    pfCancel: document.getElementById("pf-cancel"),
    // DX-8b advisor layout
    advisorView: document.getElementById("advisor-view"),
    levelsView: document.getElementById("levels-view"),
    detailedView: document.getElementById("detailed-view"),
    modeAdvisor: document.getElementById("mode-advisor"),
    modeLevels: document.getElementById("mode-levels"),
    modeTable: document.getElementById("mode-table"),
    lvPositions: document.getElementById("lv-positions"),
    lvPosSub: document.getElementById("lv-pos-sub"),
    lvPosLadders: document.getElementById("lv-pos-ladders"),
    lvBuy: document.getElementById("lv-buy"),
    lvBuySub: document.getElementById("lv-buy-sub"),
    lvBuyLadders: document.getElementById("lv-buy-ladders"),
    lvApproaching: document.getElementById("lv-approaching"),
    lvApprSub: document.getElementById("lv-appr-sub"),
    lvApprLadders: document.getElementById("lv-appr-ladders"),
    lvNote: document.getElementById("lv-note"),
    sellGroup: document.getElementById("sell-group"),
    sellTickets: document.getElementById("sell-tickets"),
    sellN: document.getElementById("sell-n"),
    holdGroup: document.getElementById("hold-group"),
    holdTickets: document.getElementById("hold-tickets"),
    holdN: document.getElementById("hold-n"),
    buyZone: document.getElementById("buy-zone"),
    buySub: document.getElementById("buy-sub"),
    buyTickets: document.getElementById("buy-tickets"),
    restLine: document.getElementById("rest-line"),
    // Conviction filters (DX-10b)
    fStop: document.getElementById("f-stop"),
    fLiq: document.getElementById("f-liq"),
    fBox: document.getElementById("f-box"),
    fClear: document.getElementById("f-clear"),
    filterNote: document.getElementById("filter-note")
  };

  /*
    DX-11 — the in-app methodology guide.

    A dialog, not a fourth mode alongside Advisor/Levels/Table: those three
    switch what live sweep data you are looking at, and the guide is reference
    material that applies regardless of which one is open. Folding it into the
    mode switch would make "how does this work" compete for a slot with "what
    should I do today", which are different questions asked at different times.

    Every fact in the panel is sourced from the code that computes it
    (DAR_CARD_TEXT, config.py, engine.py) rather than paraphrased — see
    test_dx11_guide.py, which cross-checks the rule quotes and thresholds
    against those same sources so the guide cannot silently drift from the
    methodology it describes.
  */
  var guideOpenerEl = null;

  function openGuide() {
    guideOpenerEl = document.activeElement;
    S.guideBackdrop.hidden = false;
    S.guide.hidden = false;
    S.guide.focus();
    document.addEventListener("keydown", onGuideKeydown);
  }

  function closeGuide() {
    S.guide.hidden = true;
    S.guideBackdrop.hidden = true;
    document.removeEventListener("keydown", onGuideKeydown);
    // Return focus to whatever opened it, not just to <body>: a keyboard user
    // who opened the guide from the header button should land back there,
    // not lose their place on the page.
    if (guideOpenerEl && typeof guideOpenerEl.focus === "function") {
      guideOpenerEl.focus();
    }
  }

  function onGuideKeydown(e) {
    if (e.key === "Escape") closeGuide();
  }

  S.guideOpen.addEventListener("click", openGuide);
  S.guideClose.addEventListener("click", closeGuide);
  S.guideBackdrop.addEventListener("click", closeGuide);

  var TIERS = [
    { key: "ACTIONABLE", cls: "t-actionable", title: "Actionable",
      rule: "Darvas rule B — buy above the topmost box" },
    { key: "WATCH", cls: "t-watch", title: "Watch",
      rule: "Darvas rule A — hold while in the topmost box" },
    { key: "EXIT_RELEVANT", cls: "t-exit", title: "Exit-relevant",
      rule: "Darvas rule C — sell below a new box bottom" },
    { key: "NOT_ELIGIBLE", cls: "t-other", title: "Not eligible",
      rule: "Darvas rule D — no reason to hold or buy" }
  ];

  var RULE_TEXT = {
    A: "A stock in its topmost box is a HOLD; intra-box fluctuation is ignored.",
    B: "A move above the topmost box top is a BUY, with a 10% stop on first breakout.",
    C: "A fall below a newly-formed higher box's bottom is a SELL.",
    D: "There is no reason to hold or buy a stock that is not in its topmost box."
  };

  var screen = {
    rows: [],
    sweep: null,
    currentDigest: null,
    filter: "",
    showOther: false,
    closed: {},
    sort: {},
    open: {},
    detail: {},
    polling: null,
    mode: "advisor",
    visible: []
  };

  function num(raw, dp) {
    if (raw === null || raw === undefined || raw === "") return null;
    var v = Number(raw);
    return isFinite(v) ? (dp === undefined ? v : Number(v.toFixed(dp))) : null;
  }

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tone(signalType) {
    return TONE[signalType] || "flat";
  }

  // The core visual: where price sits between the box floor and ceiling.
  function vizFor(row) {
    var lo = num(row.box_bottom), hi = num(row.box_top), close = num(row.close);
    if (lo === null || hi === null || close === null) {
      return '<div class="viz" title="No completed box"><div class="axis"></div></div>';
    }
    var trigger = num(row.trigger_price);
    var points = [lo, hi, close];
    if (trigger !== null) points.push(trigger);
    var min = Math.min.apply(null, points), max = Math.max.apply(null, points);
    var pad = (max - min) * 0.18 || 1;
    var a = min - pad, b = max + pad;
    function pos(v) { return ((v - a) / (b - a)) * 100; }

    var html = '<div class="viz vz-' + tone(row.signal_type) + '" title="box ' +
      esc(row.box_bottom) + " – " + esc(row.box_top) + " · close " +
      esc(row.close) + '"><div class="axis"></div>';
    html += '<div class="range" style="left:' + pos(lo).toFixed(2) + "%;width:" +
      (pos(hi) - pos(lo)).toFixed(2) + '%"></div>';
    if (trigger !== null) {
      html += '<div class="trig" style="left:' + pos(trigger).toFixed(2) + '%"></div>';
    }
    html += '<div class="now" style="left:' + pos(close).toFixed(2) + '%"></div></div>';
    return html;
  }

  function distanceCell(row) {
    var pct = num(row.distance_to_breakout_pct);
    if (pct === null) return '<td class="num">—</td>';
    var through = pct <= 0;
    var magnitude = Math.min(Math.abs(pct) / 5, 1) * 100;
    // The reference is shown because it differs by tier: DX-3 records a trigger
    // only alongside a stop, so most WATCH rows are measured to the box ceiling.
    var label = through ? "through" : "+" + pct.toFixed(2) + "%";
    return '<td class="num" title="measured to ' + esc(row.breakout_reference || "—") +
      '"><div class="dist"><span class="mb"><i style="width:' + magnitude.toFixed(0) +
      '%"></i></span><span class="val' + (through ? " through" : "") + '">' +
      label + "</span></div></td>";
  }

  /*
    Risk and liquidity are presentation arithmetic over persisted values
    (stop_price, close, liquidity_value) — not re-derived rationale, which
    ADR-005 reserves to the engine. They live here, once, because DX-9a puts
    the same two figures in the Table that DX-9d already put on the Levels
    card: two copies of this arithmetic would eventually disagree, and the
    owner would have no way to tell which view was lying.
  */
  function riskFromHere(row) {
    var stop = num(row.stop_price), now = num(row.close);
    if (stop === null || now === null || now <= stop) return null;
    return { abs: now - stop, pct: ((now - stop) / now) * 100 };
  }

  function liqCrore(row) {
    var v = num(row.liquidity_value);
    return v === null ? null : v / CRORE;
  }

  /*
    Rupees at a fixed two decimals.

    Deliberately NOT the existing money(): that helper omits fraction-digit
    options, so toLocaleString drops a trailing zero and a price becomes "₹6.7"
    — which riskLine already documents having been bitten by. It is also NOT a
    second function named money(): declaring one shadowed the existing helper's
    callers by declaration order, and every price on the Levels card rendered
    with a doubled "₹₹" because both the caller and the winning helper added
    the symbol. Distinct name, single responsibility.
  */
  function rupees(v) {
    var n = num(v);
    return n === null ? "—" : "\u20b9" + n.toLocaleString("en-IN", {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
  }

  /* --- DX-9a cells --------------------------------------------------------
     The Table used to be the only view WITHOUT the trade values: it showed
     state, rule and box geometry, so answering "what would I actually pay,
     and what would I lose" meant leaving it for the Advisor or Levels view.
     These four columns close that, and are grouped under one header so the
     tradeable figures read as a block rather than as more geometry. */

  function actionCell(row) {
    if (!row.action) {
      return '<td><span class="act a-none" ' +
        'title="No action recorded — this row predates DX-7a">—</span></td>';
    }
    // `a-<ACTION>` uppercase, matching the chip classes the Advisor view
    // already emits and darvax.css already styles. Inventing an `act-<lower>`
    // variant here rendered a correctly-labelled but completely unstyled chip.
    return '<td><span class="act a-' + esc(row.action) + '" title="' +
      esc(row.action_reason_plain || row.action_reason || "") + '">' +
      esc(ACTION_LABEL[row.action] || row.action) + "</span></td>";
  }

  function levelCell(value, extraClass, titleText) {
    var v = num(value);
    if (v === null) {
      // Absent, not zero. DX-3 persists a trigger only alongside a stop, so
      // most rows genuinely have neither and must not read as ₹0.
      return '<td class="num mono trade' + (extraClass ? " " + extraClass : "") +
        '"><span class="dim">—</span></td>';
    }
    return '<td class="num mono trade' + (extraClass ? " " + extraClass : "") + '"' +
      (titleText ? ' title="' + esc(titleText) + '"' : "") + ">" + esc(rupees(v)) + "</td>";
  }

  function riskCell(row) {
    var r = riskFromHere(row);
    if (r === null) {
      return '<td class="num mono trade"><span class="dim">—</span></td>';
    }
    // Risk from the CURRENT price, never from the trigger: risk-to-trigger is
    // 10% on every row by construction (the stop is defined 10% below it), so
    // it printed an identical, falsely reassuring figure everywhere.
    var hot = r.pct >= 15;
    return '<td class="num mono trade" title="From today\u2019s close of ' +
      esc(rupees(row.close)) + ' down to the stop at ' +
      esc(rupees(row.stop_price)) + ' \u2014 ' + esc(rupees(r.abs)) +
      ' per share">' + '<span class="risk' + (hot ? " hot" : "") + '">' +
      r.pct.toFixed(1) + "%</span></td>";
  }

  function liqCell(row) {
    var cr = liqCrore(row);
    if (cr === null) {
      return '<td class="num mono"><span class="dim" ' +
        'title="Not enough history to measure — not a claim of illiquidity">—</span></td>';
    }
    var thin = cr < 1;
    return '<td class="num mono" title="Median traded value over the last 20 ' +
      'sessions. Median, not average, so a single spike does not flatter it."><span' +
      (thin ? ' class="risk hot"' : "") + ">" +
      (cr >= 100 ? Math.round(cr).toLocaleString("en-IN") : cr.toFixed(cr < 10 ? 2 : 1)) +
      "</span></td>";
  }

  /*
    `group` drives the banded super-header. Columns carrying money you would
    act on sit in "the trade"; everything else is identity or context.
  */
  var COLUMNS = [
    { key: "symbol", label: "Symbol", group: "" },
    { key: "action", label: "Action", group: "" },
    { key: "close", label: "Now", num: true, group: "" },
    { key: "trigger_price", label: "Buy above", num: true, group: "the trade" },
    { key: "stop_price", label: "Stop-loss", num: true, group: "the trade" },
    { key: null, label: "Risk now", num: true, group: "the trade",
      sortKey: "risk_pct", hint: "% you lose from today\u2019s price if the stop hits" },
    { key: "distance_to_breakout_pct", label: "To buy level", num: true,
      group: "the trade",
      hint: "How far today\u2019s price is from the level you may buy above. "
          + "\u201cthrough\u201d means price is already past it" },
    { key: null, label: "Box range", group: "context" },
    { key: "box_height_pct", label: "Box height", num: true, group: "context",
      hint: "How tall the range is, floor to ceiling, as a % of the floor \u2014 "
          + "not a distance from your buy level" },
    { key: null, label: "\u20b9cr/day", num: true, group: "context",
      sortKey: "liquidity_value", hint: "Median traded value, last 20 sessions" },
    { key: "darvas_rule", label: "Rule", group: "context" },
    { key: "rank", label: "#", num: true, group: "context" }
  ];

  /* Sorting on a derived column needs the derived number, not a stored field. */
  var DERIVED_SORT = {
    risk_pct: function (r) { var v = riskFromHere(r); return v === null ? null : v.pct; },
    liquidity_value: function (r) { return num(r.liquidity_value); }
  };

  function sortedRows(tierKey) {
    var needle = screen.filter.trim().toUpperCase();
    var list = screen.visible.filter(function (r) {
      return r.tier === tierKey && (!needle || r.symbol.indexOf(needle) !== -1);
    });
    var sort = screen.sort[tierKey];
    if (!sort) return list;                       // persisted rank order
    var derive = DERIVED_SORT[sort.key];
    return list.slice().sort(function (x, y) {
      var a = derive ? derive(x) : x[sort.key];
      var b = derive ? derive(y) : y[sort.key];
      var na = num(a), nb = num(b);
      if (na !== null && nb !== null) return sort.dir * (na - nb);
      // Missing values sort last regardless of direction: they are absent, not
      // small, and floating them to the top would misrepresent them.
      if (a === null || a === undefined) return 1;
      if (b === null || b === undefined) return -1;
      return sort.dir * String(a).localeCompare(String(b));
    });
  }

  function renderTiers() {
    var html = "";
    TIERS.forEach(function (tier) {
      if (tier.key === "NOT_ELIGIBLE" && !screen.showOther) return;
      var list = sortedRows(tier.key);
      var total = screen.sweep && screen.sweep.tier_counts
        ? screen.sweep.tier_counts[tier.key] : list.length;
      var isOpen = screen.closed[tier.key] !== true;
      var sort = screen.sort[tier.key];

      html += '<section class="tier ' + tier.cls + '" data-open="' + isOpen + '">';
      html += '<header tabindex="0" role="button" aria-expanded="' + isOpen +
        '" data-tier="' + tier.key + '"><h3>' + tier.title + "</h3>";
      html += '<span class="count">' + (list.length === total ? total : list.length + " / " + total) + "</span>";
      html += '<span class="ruletext">' + tier.rule + "</span>";
      html += '<span class="chev">' + (isOpen ? "▾" : "▸") + "</span></header>";
      html += '<div class="tierbody"><div class="scroll"><table class="screen">';

      // A super-header, so twelve columns read as three ideas rather than as
      // one undifferentiated wall. Marked presentation-only for assistive
      // technology: the sortable row below is the real header.
      html += '<colgroup>';
      COLUMNS.forEach(function (col) {
        html += '<col' + (col.group === "the trade" ? ' class="cg-trade"' : "") + ">";
      });
      html += "</colgroup><thead><tr class=\"grouprow\" aria-hidden=\"true\">";
      var g = null, span = 0;
      COLUMNS.forEach(function (col, i) {
        if (col.group !== g) {
          if (g !== null) {
            html += '<th colspan="' + span + '" class="gh' +
              (g === "the trade" ? " gh-trade" : "") + '">' + esc(g) + "</th>";
          }
          g = col.group; span = 0;
        }
        span += 1;
        if (i === COLUMNS.length - 1) {
          html += '<th colspan="' + span + '" class="gh' +
            (g === "the trade" ? " gh-trade" : "") + '">' + esc(g) + "</th>";
        }
      });
      html += '</tr><tr>';
      COLUMNS.forEach(function (col) {
        // A derived column sorts on its computed value via sortKey; only
        // decorative columns (the box viz) have neither and stay unsortable.
        var key = col.key || col.sortKey || null;
        var active = sort && key && sort.key === key;
        html += "<th" + (col.num ? ' class="num"' : "") +
          (key ? ' data-sort="' + key + '" data-tier="' + tier.key + '"' : "") +
          (col.hint ? ' title="' + esc(col.hint) + '"' : "") +
          (active ? ' aria-sort="' + (sort.dir === 1 ? "ascending" : "descending") + '"' : "") +
          ">" + col.label + (active ? (sort.dir === 1 ? " ↑" : " ↓") : "") + "</th>";
      });
      html += "</tr></thead><tbody>";

      if (!list.length) {
        html += '<tr><td colspan="' + COLUMNS.length + '" class="dim" style="padding:14px 11px">' +
          (screen.filter
            ? "No symbol matches “" + esc(screen.filter) + "” in this tier."
            : "Nothing in this tier.") + "</td></tr>";
      }

      list.forEach(function (row) {
        var id = row.instrument_id;
        html += '<tr class="srow" data-id="' + esc(id) + '">';
        // The raw signal state moves under the symbol rather than taking a
        // column of its own: Action supersedes it for deciding anything, but
        // it is what the persisted explanation is phrased in terms of, so it
        // must stay visible somewhere.
        html += '<td class="sym">' + esc(row.symbol) +
          '<span class="substate ' + tone(row.signal_type) + '">' +
          esc(row.signal_type) + "</span></td>";
        html += actionCell(row);
        // Formatted like the price columns beside it. Rendering the raw decimal
        // put "1635.1" next to "₹66.99" — same kind of number, two notations,
        // one column apart, which makes the block harder to scan than it needs
        // to be. levelCell handles the ₹ and the two-decimal alignment.
        html += levelCell(row.close, "");
        html += levelCell(row.trigger_price, "", "Buy only above this price");
        html += levelCell(row.stop_price, "",
          row.stop_basis ? "Stop basis: " + row.stop_basis : "");
        html += riskCell(row);
        html += distanceCell(row);
        html += "<td>" + vizFor(row) + "</td>";
        var height = num(row.box_height_pct);
        html += '<td class="num mono">' + (height === null ? "—" : height.toFixed(2) + "%") + "</td>";
        html += liqCell(row);
        html += "<td>" + (row.darvas_rule
          ? '<span class="rulechip" title="' + esc(RULE_TEXT[row.darvas_rule] || "") + '">' +
            esc(row.darvas_rule) + "</span>"
          : '<span class="rulechip">—</span>') + "</td>";
        html += '<td class="num mono">' + esc(row.rank) + "</td>";
        html += "</tr>";
        html += '<tr class="sdetail" data-detail="' + esc(id) + '"' +
          (screen.open[id] ? "" : " hidden") + '><td colspan="' + COLUMNS.length + '">' +
          detailHtml(row) + "</td></tr>";
      });

      html += "</tbody></table></div>";
      if (tier.key === "NOT_ELIGIBLE" && list.length < total) {
        html += '<p class="dim" style="margin:0;padding:9px 13px;border-top:1px solid var(--line)">' +
          "Showing " + list.length + " of " + total + "." + "</p>";
      }
      html += "</section>";
    });
    S.tiers.innerHTML = html;
  }

  function detailHtml(row) {
    var loaded = screen.detail[row.instrument_id];
    var html = '<div class="sdetail-grid">';
    html += '<div><p class="lbl">Why DarvaX reads it this way</p>' +
      '<p class="why">' + esc(row.explanation) + "</p></div>";

    if (loaded === "loading") {
      html += '<p class="dim">Loading evidence…</p>';
    } else if (loaded && loaded.evidence && loaded.evidence.length) {
      html += '<div><p class="lbl">Evidence (persisted with the signal)</p><ul class="ev">';
      loaded.evidence.forEach(function (item) {
        html += "<li><span class=\"k\">" + esc(item.name) + "</span><span class=\"v\">" +
          esc(item.value) + "</span><span class=\"d\">" + esc(item.detail) + "</span></li>";
      });
      html += "</ul></div>";
      if (loaded.stop) {
        html += '<div><p class="lbl">Stop derivation</p><p class="why">' +
          esc(loaded.stop.detail) + "</p></div>";
      }
    }

    html += '<p class="trace">signal ' + esc(row.signal_id) + " · rank " +
      esc(row.rank) + " in " + esc(row.tier) +
      (row.breakout_reference ? " · ranked on " + esc(row.breakout_reference) : "") +
      " · " + esc(row.status) + "</p>";
    return html + "</div>";
  }

  function renderMeta() {
    var sweep = screen.sweep;
    if (!sweep) { S.meta.hidden = true; return; }
    var bits = [];
    bits.push('<span><span class="k">sweep</span> <span class="v">' + esc(sweep.sweep_id) + "</span></span>");
    if (sweep.as_of) {
      var asOf = sweep.as_of.slice(0, 10);
      bits.push('<span><span class="k">as of</span> <span class="v">' + esc(asOf) + "</span></span>");
    }
    bits.push('<span><span class="k">evaluated</span> <span class="v">' +
      esc(sweep.evaluated) + " / " + esc(sweep.requested) + "</span></span>");
    if (sweep.skipped && sweep.skipped.length) {
      bits.push('<span><span class="k">skipped</span> <span class="v">' +
        sweep.skipped.length + "</span></span>");
    }
    if (sweep.partial) {
      bits.push('<span class="flag warn">partial — sweep was cancelled</span>');
    }
    // Freshness stated as a fact, not as a session count: the trading calendar
    // is ATHENA's concern and this page must not guess at it.
    //
    // Compared against the *local* date, not toISOString(): as_of is an IST
    // trading date, and UTC is behind IST by 5h30m, so a UTC "today" reads as
    // yesterday for the first five and a half hours of every Indian day — long
    // enough to hide a stale screen every single morning.
    if (sweep.as_of) {
      var asOfDate = sweep.as_of.slice(0, 10);
      var now = new Date();
      var today = now.getFullYear() + "-" +
        String(now.getMonth() + 1).padStart(2, "0") + "-" +
        String(now.getDate()).padStart(2, "0");
      if (asOfDate < today) {
        bits.push('<span class="flag warn" title="The latest bar this screen saw is ' +
          esc(asOfDate) + '">not the latest session</span>');
      }
    }
    // A screen produced under different methodology settings than are in force
    // now is misleading unless the mismatch is stated.
    if (screen.currentDigest && sweep.methodology_digest &&
        screen.currentDigest !== sweep.methodology_digest) {
      bits.push('<span class="flag bad" title="sweep ' + esc(sweep.methodology_digest) +
        " · current " + esc(screen.currentDigest) +
        '">methodology changed since this sweep</span>');
    }
    S.meta.innerHTML = bits.join("");
    S.meta.hidden = false;
  }

  function renderSkipped() {
    var skipped = screen.sweep && screen.sweep.skipped ? screen.sweep.skipped : [];
    if (!skipped.length) { S.skipped.hidden = true; return; }
    S.skippedSummary.textContent = skipped.length + " instrument(s) skipped — reasons";
    S.skippedList.textContent = "";
    skipped.forEach(function (entry) {
      var li = document.createElement("li");
      li.textContent = entry.instrument_id + " — " + entry.reason;
      S.skippedList.appendChild(li);
    });
    S.skipped.hidden = false;
  }

  function renderScreen() {
    var hasSweep = !!screen.sweep;
    // Computed once and shared, so the three views can never disagree about
    // what is in scope. Positions are deliberately NOT filtered: what you hold
    // is not a discovery question, and hiding a holding because it failed a
    // liquidity threshold would hide advice you need.
    var outcome = applyFilters(screen.rows);
    screen.visible = outcome.kept;
    renderFilterNote(screen.rows.length, outcome.kept.length, outcome.unmeasured);
    S.empty.hidden = hasSweep;
    S.tiers.hidden = !hasSweep;
    renderMeta();
    renderSkipped();
    if (hasSweep) renderTiers(); else S.tiers.innerHTML = "";
    // The advisor zones read the same rows the table does, so they can never
    // show a different sweep than the screen beneath them (DX-7c).
    renderBuy();
    renderPositions();
    renderRest();
    if (screen.mode === "levels") renderLevels();
  }

  function screenSay(message, isError) {
    S.note.textContent = message || "";
    S.note.className = isError ? "note err" : "note";
  }

  function loadScreen() {
    // The API caps this at 5000. Requesting 2000 silently truncated a
    // 2,191-instrument sweep and the page then reported the truncated
    // number as the count screened — see the truncation warning below,
    // which exists because a cap that is invisible is worse than a low one.
    return request("/darvax/api/screen/latest?limit=" + SCREEN_ROW_LIMIT)
      .then(function (payload) {
        screen.rows = payload.data || [];
        screen.sweep = payload.sweep || null;
        screen.currentDigest = payload.current_methodology_digest || null;
        renderScreen();
        if (screen.sweep) {
          // Report what the SWEEP evaluated, not how many rows arrived: those
          // differ whenever the response is truncated, and quoting the smaller
          // number states a falsehood about coverage.
          var evaluated = screen.sweep.evaluated;
          var truncated = evaluated > screen.rows.length;
          // The mismatch can run the other way too, and the page used to state
          // the impossible when it did.
          //
          // Measured on the owner's live database: their most recent sweep has
          // all 2,191 result rows persisted, but its sweep record still reads
          // state="running", evaluated=0 — the runner saves results first and
          // the completion record second, so anything that stops the process
          // between those two writes (an auto-reload, a restart) leaves a
          // finished sweep looking unstarted. The process that ran it still had
          // the live figure in memory and displayed 2,191; only a fresh process
          // reads the record and reported "0 instrument(s) screened" above a
          // table of 2,191 rows.
          //
          // Whichever number is smaller, the page must not claim it as the
          // count and must say which of the two it cannot vouch for.
          var incomplete = evaluated < screen.rows.length;
          var count = incomplete ? screen.rows.length : evaluated;
          screenSay(
            count + " instrument(s) screened. Click a row for the " +
            "persisted explanation and evidence." +
            (truncated
              ? " Showing the first " + screen.rows.length + " — this view is " +
                "truncated, so the tiers and shortlist below are incomplete."
              : "") +
            (incomplete
              ? " The sweep record says it did not finish (" + evaluated +
                " recorded as evaluated), so treat this as a possibly partial " +
                "sweep and re-run it to be sure."
              : ""),
            truncated || incomplete
          );
        } else {
          screenSay("");
        }
      })
      .catch(function (err) { screenSay(err.message, true); });
  }

  function showProgress(on) {
    S.progress.hidden = !on;
    S.cancelBtn.hidden = !on;
    S.sweepBtn.disabled = on;
  }

  function pollProgress() {
    return request("/darvax/api/screen/progress")
      .then(function (payload) {
        var p = payload.data;
        var total = p.total || 0;
        S.pStage.textContent = p.stage === "scanning"
          ? "Evaluating universe" : (p.stage || "…");
        S.pDone.textContent = p.evaluated;
        S.pTotal.textContent = total;
        S.pElapsed.textContent = p.elapsed_seconds.toFixed(1) + "s";
        S.pBar.style.width = total ? ((p.evaluated / total) * 100).toFixed(1) + "%" : "0%";

        if (p.state !== "running") {
          stopPolling();
          showProgress(false);
          if (p.state === "failed") {
            screenSay("Sweep failed: " + (p.error || "unknown error"), true);
          }
          return loadScreen();
        }
        return null;
      })
      .catch(function (err) {
        stopPolling();
        showProgress(false);
        screenSay(err.message, true);
      });
  }

  function stopPolling() {
    if (screen.polling) { clearInterval(screen.polling); screen.polling = null; }
  }

  function startSweep() {
    screenSay("Starting sweep…");
    request("/darvax/api/screen", { method: "POST" })
      .then(function () {
        showProgress(true);
        screenSay("");
        stopPolling();
        screen.polling = setInterval(pollProgress, 900);
        return pollProgress();
      })
      .catch(function (err) { screenSay(err.message, true); });
  }

  function cancelSweep() {
    request("/darvax/api/screen", { method: "DELETE" })
      .then(function () {
        screenSay("Cancelling — results already evaluated are kept.");
      })
      .catch(function (err) { screenSay(err.message, true); });
  }

  function toggleDetail(instrumentId) {
    var isOpen = !screen.open[instrumentId];
    screen.open[instrumentId] = isOpen;
    if (isOpen && !screen.detail[instrumentId]) {
      // Fetched on expand rather than bundled into the screen payload: evidence
      // and stop derivation are per-signal and only wanted for the row actually
      // being read.
      screen.detail[instrumentId] = "loading";
      request("/darvax/api/signals/" + encodeURIComponent(instrumentId))
        .then(function (payload) {
          screen.detail[instrumentId] = payload.data || null;
          renderTiers();
        })
        .catch(function () {
          screen.detail[instrumentId] = null;
          renderTiers();
        });
    }
    renderTiers();
  }

  function switchView(which) {
    var screener = which === "screener";
    S.screener.hidden = !screener;
    S.signalsView.hidden = screener;
    S.viewScreener.setAttribute("aria-selected", String(screener));
    S.viewSignals.setAttribute("aria-selected", String(!screener));
    if (!screener) load();
  }

  S.sweepBtn.addEventListener("click", startSweep);
  S.cancelBtn.addEventListener("click", cancelSweep);
  S.filter.addEventListener("input", function () {
    screen.filter = this.value;
    renderTiers();
  });
  S.toggleOther.addEventListener("click", function () {
    screen.showOther = !screen.showOther;
    this.setAttribute("aria-pressed", String(screen.showOther));
    this.textContent = screen.showOther ? "Hide not eligible" : "Show not eligible";
    renderTiers();
  });
  S.viewScreener.addEventListener("click", function () { switchView("screener"); });
  S.viewSignals.addEventListener("click", function () { switchView("signals"); });

  S.tiers.addEventListener("click", function (event) {
    var header = event.target.closest("header[data-tier]");
    if (header) {
      var key = header.getAttribute("data-tier");
      screen.closed[key] = !screen.closed[key];
      renderTiers();
      return;
    }
    var th = event.target.closest("th[data-sort]");
    if (th) {
      var tierKey = th.getAttribute("data-tier"), sortKey = th.getAttribute("data-sort");
      var current = screen.sort[tierKey];
      screen.sort[tierKey] = current && current.key === sortKey
        ? { key: sortKey, dir: -current.dir }
        : { key: sortKey, dir: 1 };
      renderTiers();
      return;
    }
    var row = event.target.closest("tr.srow");
    if (row) toggleDetail(row.getAttribute("data-id"));
  });

  S.tiers.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" && event.key !== " ") return;
    var header = event.target.closest("header[data-tier]");
    if (header) { event.preventDefault(); header.click(); }
  });

  // ======================================================================
  // Advisor zones (DX-7c)
  //
  // Every action word and every justification below is READ from the payload.
  // Nothing here maps a signal state to an action or composes a sentence: the
  // engine did both and persisted them (ADR-005). A screen and this page can
  // therefore never disagree about what the advice was.
  // ======================================================================

  var positions = { list: [], loading: false };

  // Labels only. Deliberately NOT a state->action map: the action arrives from
  // the server, and this turns it into words a human reads.
  var ACTION_LABEL = {
    ENTER: "Buy",
    ENTER_ON_RETEST: "Buy on dip",
    WAIT: "Wait",
    HOLD: "Hold",
    EXIT: "Sell",
    EXIT_IF_HELD: "Sell if held",
    NO_ENTRY: "Skip"
  };

  function actionChip(row) {
    var action = row.action || "";
    var label = ACTION_LABEL[action] || action || "—";
    // `risk_bearing` is computed server-side from RISK_BEARING_ACTIONS so this
    // list cannot drift when an action is added (design decision 3b).
    var badge = row.risk_bearing
      ? '<abbr class="unval" title="Experimental and unvalidated. DX-5 attributes ' +
        'most of the measured edge to the exit rule and market drift rather than ' +
        'to box detection, and the detection increment is only marginally ' +
        'significant.">unvalidated</abbr>'
      : "";
    return '<span class="act a-' + esc(action) + '">' + esc(label) + badge + "</span>";
  }

  function money(raw) {
    var v = num(raw);
    return v === null ? "—" : "₹" + v.toLocaleString("en-IN");
  }

  // ------------------------------------------------------------ trade tickets

  // Distance in words. "through" was on the shipped screen and reads like an
  // error; it actually means the good news that price is already past the level.
  function distanceWords(row) {
    var pct = num(row.distance_to_breakout_pct);
    if (pct === null) return "";
    if (pct <= 0) return "already above the buy level";
    return pct.toFixed(2) + "% below the buy level";
  }

  function riskLine(row) {
    var buy = num(row.trigger_price), stop = num(row.stop_price);
    if (buy === null || stop === null || buy <= 0) return "";
    var risk = buy - stop;
    // Formatted directly rather than through money(): that helper re-parses to
    // a Number and toLocaleString drops the trailing zero, so a deliberate
    // two-decimal rupee value came out as "₹6.7".
    return '<span class="risk">risk ₹' +
      risk.toLocaleString("en-IN", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
      }) +
      "/share (" + ((risk / buy) * 100).toFixed(1) + "%)</span>";
  }

  // The methodology, one disclosure away rather than in the reader's face.
  // Renders the two strings the engine persisted; composes neither.
  function methodologyDetails(row) {
    var bits = "";
    if (row.action_reason) bits += "<p>" + esc(row.action_reason) + "</p>";
    if (row.explanation) bits += "<p>" + esc(row.explanation) + "</p>";
    if (row.stop_basis) {
      bits += '<p class="trace">stop basis ' + esc(row.stop_basis) +
        " · rule " + esc(row.darvas_rule || "—") +
        " · state " + esc(row.signal_type) + "</p>";
    }
    if (!bits) return "";
    return '<details class="method"><summary>Why, in method terms</summary>' +
      bits + "</details>";
  }

  function buyTicket(row, index) {
    var buy = num(row.trigger_price);
    return '' +
      '<article class="ticket buy">' +
        '<header><span class="pos">' + (index + 1) + "</span>" +
          '<span class="sym">' + esc(row.symbol) + "</span>" +
          actionChip(row) + "</header>" +
        '<dl class="lines">' +
          "<dt>Buy above</dt><dd class=\"key\">" +
            (buy === null ? "—" : money(row.trigger_price)) + "</dd>" +
          "<dt>Stop loss</dt><dd>" + money(row.stop_price) + " " +
            riskLine(row) + "</dd>" +
          "<dt>Now</dt><dd>" + money(row.close) +
            '<span class="dist"> ' + esc(distanceWords(row)) + "</span></dd>" +
        "</dl>" +
        vizFor(row) +
        '<p class="why">' + esc(row.action_reason_plain || row.action_reason) + "</p>" +
        methodologyDetails(row) +
      "</article>";
  }

  function holdingTicket(p, row) {
    var close = row ? num(row.close) : null;
    var entry = num(p.entry_price);
    var ret = (close !== null && entry) ? ((close - entry) / entry) * 100 : null;
    var why = row
      ? esc(row.action_reason_plain || row.action_reason)
      : "Run a screen to get advice for this holding.";
    return '' +
      '<article class="ticket">' +
        '<header><span class="sym">' + esc(p.instrument_id.split(":").pop()) +
          "</span>" +
          (row ? actionChip(row) : '<span class="act a-none">no reading</span>') +
          '<span class="spacer"></span>' +
          (ret === null ? "" : '<span class="ret ' + (ret >= 0 ? "up" : "down") +
            '">' + (ret >= 0 ? "+" : "") + ret.toFixed(2) + "%</span>") +
        "</header>" +
        '<dl class="lines">' +
          "<dt>You hold</dt><dd>" + esc(p.quantity) + " at " +
            money(p.entry_price) + "</dd>" +
          "<dt>Now</dt><dd>" + (close === null ? "—" : money(row.close)) + "</dd>" +
          "<dt>Your stop-loss</dt><dd>" + money(p.stop_price) + "</dd>" +
        "</dl>" +
        '<p class="why">' + why + "</p>" +
        (row ? methodologyDetails(row) : "") +
        '<div class="rowact">' +
          '<button type="button" class="ghost xs" data-close="' +
            esc(p.position_id) + '">Mark closed</button>' +
          '<button type="button" class="ghost xs danger" data-del="' +
            esc(p.position_id) + '">Delete</button>' +
        "</div>" +
      "</article>";
  }

  // ---------------------------------------------------------------- buy list

  function renderBuy() {
    if (!screen.rows.length) { S.buyZone.hidden = true; return; }
    // The engine already ordered these by distance to the buy level and
    // assigned rank; taking that order rather than re-sorting keeps the
    // shortlist and the detailed table telling the same story.
    var all = screen.visible.filter(function (r) { return r.risk_bearing; });
    // The cap exists so an unfiltered screen does not open with 117 cards. A
    // filtered list is already narrowed by intent, so it earns a bigger one —
    // and without this, filtering 117 down to 14 still showed exactly 10 cards,
    // which read as "the filter did nothing".
    var limit = anyFilterActive() ? BUY_SHORTLIST_FILTERED : BUY_SHORTLIST;
    var shortlist = all.slice().sort(function (a, b) {
      return (a.rank || 0) - (b.rank || 0);
    }).slice(0, limit);

    S.buyZone.hidden = false;
    if (!shortlist.length) {
      S.buySub.textContent = "nothing is near a buy level right now";
      S.buyTickets.innerHTML = '<p class="dim">No buy candidates in this screen.</p>';
      return;
    }
    S.buySub.textContent = "showing " + shortlist.length + " of " + all.length +
      " · closest to their buy level first";
    S.buyTickets.innerHTML = shortlist.map(buyTicket).join("");
  }

  // ------------------------------------------------------------- positions

  function posSay(message, isError) {
    S.posNote.textContent = message || "";
    S.posNote.classList.toggle("err", Boolean(isError));
  }

  function screenRowFor(instrumentId) {
    for (var i = 0; i < screen.rows.length; i++) {
      if (screen.rows[i].instrument_id === instrumentId) return screen.rows[i];
    }
    return null;
  }

  function renderPositions() {
    var open = positions.list;
    S.posEmpty.hidden = open.length > 0;

    var sell = [], hold = [];
    open.forEach(function (p) {
      var row = screenRowFor(p.instrument_id);
      // Grouped by the action the engine assigned, never by re-reading the
      // signal state here (ADR-005).
      if (row && (row.action === "EXIT" || row.action === "EXIT_IF_HELD")) {
        sell.push([p, row]);
      } else {
        hold.push([p, row]);
      }
    });

    S.sellGroup.hidden = sell.length === 0;
    S.sellN.textContent = sell.length ? sell.length : "";
    S.sellTickets.innerHTML = sell.map(function (pair) {
      return holdingTicket(pair[0], pair[1]);
    }).join("");

    S.holdGroup.hidden = hold.length === 0;
    S.holdN.textContent = hold.length ? hold.length : "";
    S.holdTickets.innerHTML = hold.map(function (pair) {
      return holdingTicket(pair[0], pair[1]);
    }).join("");

    var counts = {};
    open.forEach(function (p) {
      var row = screenRowFor(p.instrument_id);
      if (row && row.action) counts[row.action] = (counts[row.action] || 0) + 1;
    });
    S.posChips.innerHTML = Object.keys(counts).sort().map(function (a) {
      return '<span class="act a-' + esc(a) + '">' + esc(ACTION_LABEL[a] || a) +
        " " + counts[a] + "</span>";
    }).join("");
  }

  // The long tail, as one line rather than 2,000 rows.
  function renderRest() {
    if (!screen.rows.length) { S.restLine.hidden = true; return; }
    var quiet = screen.visible.filter(function (r) {
      return r.action === "NO_ENTRY" || r.action === "WAIT";
    }).length;
    S.restLine.hidden = quiet === 0;
    S.restLine.textContent = quiet.toLocaleString("en-IN") +
      " more instruments with nothing to act on today. " +
      "Open Detailed view to browse them.";
  }

  function loadPositions() {
    return request("/darvax/api/positions").then(function (body) {
      positions.list = (body && body.data) || [];
      renderPositions();
    }).catch(function (err) {
      posSay(err.message || String(err), true);
    });
  }


  // ====================================================================
  // Levels view (DX-9d) — the price ladder
  //
  // Darvas is a visual method: a box, a ceiling, a break above it. Rendered in
  // plain CSS on a per-card relative scale, because prices on one sweep span
  // ₹74 to ₹23,500 and a shared axis would flatten almost every ladder.
  //
  // Every level is a persisted field. The one sentence that carries insight —
  // where the stop lands relative to the breakout level — was compared and
  // worded by the engine (DX-9c), not assembled here.
  // ====================================================================

  //: Levels in descending display order, with how each is drawn. Data, so the
  //: legend and the ladder cannot disagree about what a line means.
  var LADDER_LEVELS = [
    // Hints only where the name does not already say it. "CEILING top of the
    // box" and "FLOOR bottom of the box" were pure restatement and pushed the
    // useful labels around; "Entry" genuinely needs to say *which* level it is.
    { key: "trigger_price", cls: "lv-entry",   label: "Entry",   hint: "prior day's high" },
    { key: "stop_price",    cls: "lv-stop",    label: "Stop-loss", hint: "" },
    { key: "box_top",       cls: "lv-ceiling", label: "Ceiling", hint: "" },
    { key: "box_bottom",    cls: "lv-floor",   label: "Floor",   hint: "" }
  ];

  // A narrow chart carrying the geometry, and a table carrying the numbers.
  //
  // The previous ladder put price labels ON the lines and nudged them apart when
  // levels sat close together — which detached a label from the line it named.
  // With five levels inside a few percent (BI: now ₹76.81, ceiling ₹75) it
  // became impossible to tell which label belonged to which line, which is
  // exactly what the owner reported. Table rows are in normal flow, so they
  // cannot collide, and each row's tick is colour-matched into the strip.
  function levelChart(row, position) {
    var items = [];
    LADDER_LEVELS.forEach(function (lv) {
      var v = num(row[lv.key]);
      if (v !== null) items.push({ v: v, cls: lv.cls, label: lv.label, note: lv.hint });
    });
    var now = num(row.close);
    if (now !== null) items.push({ v: now, cls: "lv-now", label: "Now", note: "" });
    if (position) {
      var pe = num(position.entry_price), ps = num(position.stop_price);
      if (pe !== null) items.push({ v: pe, cls: "lv-yourentry", label: "Your entry", note: "" });
      if (ps !== null) items.push({ v: ps, cls: "lv-yourstop", label: "Your stop-loss", note: "" });
    }
    if (items.length < 2) {
      return '<p class="dim">No levels recorded for this instrument.</p>';
    }

    // What a buyer today actually risks, which is the number that varies and
    // the number that applies. Risk measured to the trigger is a constant 10%
    // by construction — the stop is defined as 10% below it — so quoting that
    // as "of entry" printed the same figure on every card and understated the
    // real exposure whenever price had already run past the trigger.
    var stop = num(row.stop_price);
    var trigger = num(row.trigger_price);
    items.forEach(function (it) {
      if (it.cls === "lv-stop") {
        // Shared with the Table (DX-9a) so the two views cannot disagree about
        // what a buyer today risks.
        var risk = riskFromHere(row);
        if (risk !== null) {
          it.note = "risk from here " + rupees(risk.abs) +
            " (" + risk.pct.toFixed(1) + "%)";
        }
      }
      if (it.cls === "lv-entry" && trigger !== null && now !== null) {
        // Short: a longer caption wrapped and pushed the card from 328px to
        // 387px, which is the density problem this redesign was fixing.
        it.note = now > trigger ? "already passed" : "buy above this";
      }
      if (it.cls === "lv-now") {
        // Measured against the level itself, not against the current price.
        //
        // `distance_to_breakout_pct` is a percentage of *close* — it answers
        // "how far below price is the level", which rendered as "12.8% above
        // the buy level" for BI when price was really 14.7% above ₹66.99. "X%
        // above Y" has to mean (price − Y) / Y or the reader cannot check it,
        // and 14.7% is also the figure that explains the risk: a 10% stop taken
        // from an entry price already run past by 14.7% leaves 21.5% at risk.
        var ref = trigger !== null ? trigger : num(row.box_top);
        if (ref !== null && ref > 0 && now !== null) {
          var gap = ((now - ref) / ref) * 100;
          it.note = gap >= 0
            ? gap.toFixed(1) + "% above the buy level"
            : Math.abs(gap).toFixed(1) + "% below it";
        }
      }
    });

    items.sort(function (a, b) { return b.v - a.v; });
    var vals = items.map(function (i) { return i.v; });
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    var pad = (max - min) * 0.08 || 1;
    var lo = min - pad, hi = max + pad;
    function y(v) { return (1 - (v - lo) / (hi - lo)) * 100; }

    var top = num(row.box_top), bottom = num(row.box_bottom);
    var strip = '<div class="lstrip">';
    if (top !== null && bottom !== null) {
      strip += '<div class="lv-box" style="top:' + y(top).toFixed(2) +
        "%;height:" + (y(bottom) - y(top)).toFixed(2) + '%"></div>';
      // Only while the ceiling is still ahead of price: it is ground yet to be
      // taken, and shading it after a breakout filled the card with hatching
      // about a move that had already happened.
      if (now !== null && now < top) {
        strip += '<div class="lv-zone" style="top:' + y(top).toFixed(2) +
          "%;height:" + (y(now) - y(top)).toFixed(2) + '%"></div>';
      }
    }
    items.forEach(function (it) {
      strip += '<i class="ltick ' + it.cls + '" style="top:' + y(it.v).toFixed(2) + '%"></i>';
    });
    strip += "</div>";

    var rows = items.map(function (it) {
      return '<tr class="' + it.cls + '">' +
        '<td class="lt-tick"><i class="ltick ' + it.cls + '"></i></td>' +
        '<td class="lt-name">' + esc(it.label) + "</td>" +
        '<td class="lt-price">' + money(String(it.v)) + "</td>" +
        '<td class="lt-note">' + esc(it.note || "") + "</td>" +
      "</tr>";
    }).join("");

    return '<div class="lgrid">' + strip +
      '<table class="ltable"><tbody>' + rows + "</tbody></table></div>";
  }

  /*
    DX-10c — R-multiples, and why there is no target price.

    The owner asked for a target. The methodology has none: Darvas never took
    profit at a level, he trailed the stop until it was hit, and the DAR-CARD's
    only exit rules are the 10% stop (B) and the box floor (C). Inventing a
    target would be inventing methodology, which ADR-010 forbids — so DarvaX
    shows the one upside scale that is a fact rather than a forecast.

    R is the per-share risk the method itself defines: buy level minus stop.
    1R/2R/3R are simply that distance measured upwards. They predict nothing;
    they say "a move worth as much as you are risking would land here", which
    is what makes a trade's shape judgeable before entering it.

    Arithmetic over persisted values, like riskFromHere — not a rationale, so
    not something ADR-005 reserves to the engine.
  */
  function rMultiples(row) {
    var trigger = num(row.trigger_price), stop = num(row.stop_price);
    if (trigger === null || stop === null) return null;
    var r = trigger - stop;
    if (r <= 0) return null;              // stop at or above the buy level
    var now = num(row.close);
    return {
      r: r,
      levels: [1, 2, 3].map(function (k) { return { k: k, price: trigger + r * k }; }),
      // How far price has ALREADY travelled, in the same unit. This is the
      // number that says "you are late" — a candidate sitting at +1.8R has
      // spent most of a 2R move before you have paid anything for it.
      now: now === null ? null : (now - trigger) / r
    };
  }

  function rLine(row) {
    var m = rMultiples(row);
    if (m === null) return "";
    var parts = m.levels.map(function (l) {
      return '<span class="rk">' + l.k + "R</span> " + rupees(l.price);
    }).join('<span class="rsep">\u00b7</span>');
    var late = m.now !== null && m.now >= 1
      ? '<span class="rlate" title="Price has already covered this much of a ' +
        'move, before you have paid anything for it">already +' +
        m.now.toFixed(1) + "R</span>"
      : "";
    return '<div class="rrow">' +
      '<span class="rlbl" title="R is the risk the method defines: buy level ' +
      'minus stop. These are not targets — the method has no profit target, ' +
      'and rule C exits you when price falls below the box floor.">' +
      "R = " + rupees(m.r) + "</span>" + parts + late + "</div>";
  }

  function ladderCard(row, position) {
    // The stop-versus-ceiling sentence is read from the payload, never derived:
    // it is the one line on this card that says something non-obvious, and
    // ADR-005 keeps it with the engine that measured it.
    var vs = row.stop_vs_ceiling_note
      ? '<p class="lv-vs ' + (num(row.stop_vs_ceiling) >= 0 ? "ok" : "warn") + '">' +
        esc(row.stop_vs_ceiling_note) + "</p>"
      : "";
    var held = position
      ? '<div class="lv-held">You hold ' + esc(position.quantity) + " at " +
        money(position.entry_price) + " · your stop " + money(position.stop_price) +
        "</div>"
      : "";
    return '' +
      '<article class="lcard">' +
        '<header><span class="sym">' + esc(row.symbol) + "</span>" +
          actionChip(row) + "</header>" +
        levelChart(row, position) +
        rLine(row) +
        held +
        '<p class="why">' + esc(row.action_reason_plain || row.action_reason) + "</p>" +
        vs +
        methodologyDetails(row) +
      "</article>";
  }

  //: Watch candidates shown in the Levels view. A ladder per instrument is a
  //: lot of pixels, and 483 of them would bury the entries; these are the ones
  //: nearest their level, which is the same order the engine ranks by.
  var LEVELS_APPROACHING = 12;

  //: Buy ladders shown at once. A ladder is ~360px tall, so rendering all 116
  //: candidates was roughly 21,000px of scroll — the Advisor view already caps
  //: its shortlist at 10 for the same reason, and an uncapped list here made the
  //: view unusable for the studying it exists to support. The count says how
  //: many were held back.
  var LEVELS_BUY_MAX = 24;




  function renderLevels() {
    if (!screen.rows.length) {
      S.lvPositions.hidden = S.lvBuy.hidden = S.lvApproaching.hidden = true;
      S.lvNote.textContent = "Run a screen to see levels.";
      return;
    }
    // Positions look up against ALL rows, not the filtered set: a holding must
    // still show its advice even when a filter excludes it from discovery.
    var byId = {};
    screen.rows.forEach(function (r) { byId[r.instrument_id] = r; });

    var held = positions.list.filter(function (p) { return byId[p.instrument_id]; });
    S.lvPositions.hidden = held.length === 0;
    S.lvPosSub.textContent = held.length ? held.length + " with levels" : "";
    S.lvPosLadders.innerHTML = held.map(function (p) {
      return ladderCard(byId[p.instrument_id], p);
    }).join("");

    var buys = screen.visible.filter(function (r) { return r.risk_bearing; })
      .sort(function (a, b) { return (a.rank || 0) - (b.rank || 0); });
    var shown = buys.slice(0, LEVELS_BUY_MAX);
    S.lvBuy.hidden = buys.length === 0;
    S.lvBuySub.textContent = shown.length === buys.length
      ? buys.length + " with a full set of levels"
      : "nearest " + shown.length + " of " + buys.length +
        " · closest to their buy level first";
    S.lvBuyLadders.innerHTML = shown.map(function (r) {
      return ladderCard(r, null);
    }).join("");

    var waiting = screen.visible.filter(function (r) { return r.action === "WAIT"; })
      .sort(function (a, b) { return (a.rank || 0) - (b.rank || 0); })
      .slice(0, LEVELS_APPROACHING);
    S.lvApproaching.hidden = waiting.length === 0;
    S.lvApprSub.textContent = "nearest " + waiting.length +
      " of " + screen.rows.filter(function (r) { return r.action === "WAIT"; }).length +
      " · no entry or stop yet, so only the box is drawn";
    S.lvApprLadders.innerHTML = waiting.map(function (r) {
      return ladderCard(r, null);
    }).join("");

    var quiet = screen.visible.filter(function (r) { return r.action === "NO_ENTRY"; }).length;
    S.lvNote.textContent = quiet.toLocaleString("en-IN") +
      " instruments have no box to draw and are not shown here. " +
      "The Table view lists every row.";
  }


  // ====================================================================
  // Conviction filters (DX-10b)
  //
  // Every filter reads a persisted field. None invents a quality score, and
  // there is deliberately no market-cap filter: ATHENA holds no capitalisation
  // data, and a fabricated proxy labelled "market cap" would be worse than its
  // absence.
  //
  // A filter also reports what it could NOT evaluate. Silently dropping symbols
  // whose liquidity is unmeasured would make a new listing indistinguishable
  // from an illiquid one, which is the same "surface, never swallow" discipline
  // the sweep applies to skips.
  // ====================================================================

  var CRORE = 10000000;

  //: Cards in the Advisor shortlist. Larger once a filter is active, because the
  //: reader has already said what they want to see.
  var BUY_SHORTLIST = 10;
  var BUY_SHORTLIST_FILTERED = 24;

  function activeFilters() {
    return {
      stop: S.fStop.value,
      liq: S.fLiq.value ? Number(S.fLiq.value) : null,
      box: S.fBox.value ? Number(S.fBox.value) : null
    };
  }

  function anyFilterActive() {
    var f = activeFilters();
    return Boolean(f.stop || f.liq !== null || f.box !== null);
  }

  // Returns { kept, unmeasured } so the caller can say what it could not judge.
  function applyFilters(rows) {
    var f = activeFilters();
    var unmeasured = 0;
    var kept = rows.filter(function (r) {
      if (f.stop) {
        var d = num(r.stop_vs_ceiling);
        // A row with no stop has no answer to this question — it is not a
        // failure of the test, so it is excluded from the result without being
        // counted as unmeasured noise.
        if (d === null) return false;
        if (f.stop === "above" && d < 0) return false;
        if (f.stop === "below" && d >= 0) return false;
      }
      if (f.liq !== null) {
        var v = num(r.liquidity_value);
        if (v === null) { unmeasured++; return false; }
        if (v / CRORE < f.liq) return false;
      }
      if (f.box !== null) {
        var h = num(r.box_height_pct);
        if (h === null) return false;
        // A negative threshold reads as "wider than", so one control can express
        // both ends without a second widget.
        if (f.box > 0 ? h > f.box : h <= Math.abs(f.box)) return false;
      }
      return true;
    });
    return { kept: kept, unmeasured: unmeasured };
  }

  /*
    A filter that can only ever return nothing must say so instead of
    returning nothing.

    Measured on the owner's live database: all 17 sweeps recorded before
    DX-10a shipped carry no liquidity at all, because liquidity is computed at
    sweep time and their server had not restarted. Left alone, choosing any
    liquidity threshold on such a sweep empties the list and reports "0 of 2191
    match · 2191 excluded because their liquidity could not be measured" — which
    is true, unhelpful, and reads as a market with nothing in it.
  */
  function liquidityIsAbsentFromThisSweep() {
    return screen.rows.length > 0 && !screen.rows.some(function (r) {
      return num(r.liquidity_value) !== null;
    });
  }

  function syncLiquidityControl() {
    var absent = liquidityIsAbsentFromThisSweep();
    S.fLiq.disabled = absent;
    if (absent) {
      // Clear it too: a disabled control still submits its value, so a
      // threshold chosen on an earlier sweep would keep filtering invisibly.
      S.fLiq.value = "";
      S.fLiq.options[0].textContent = "Liquidity: not in this sweep";
      S.fLiq.title =
        "This sweep was run before DarvaX measured liquidity. Re-run " +
        "\u201cScreen universe\u201d to record it.";
    } else {
      S.fLiq.options[0].textContent = "Liquidity: any";
      S.fLiq.title = "";
    }
    return absent;
  }

  /*
    The stop filter's plain meaning, stated where there is room for it.

    An earlier version of this filter carried the explanation in the dropdown
    option itself ("Stop keeps part of the breakout"), which was less
    understandable than the geometry it replaced — an option is a label, and a
    label that has become a sentence is doing the wrong job. The option now
    states the fact; this states what it means for the trade.
  */
  var STOP_FILTER_PLAIN = {
    above:
      "Showing only entries whose stop-loss sits above the level price broke " +
      "out from \u2014 if the stop-loss is hit, price is still above its old " +
      "range, so part of the breakout is kept.",
    below:
      "Showing only entries whose stop-loss sits below the level price broke " +
      "out from \u2014 if the stop-loss is hit, price has fallen all the way " +
      "back into its old range and the whole breakout is given up."
  };

  /*
    Box height needed the same treatment, and for a sharper reason: the owner
    asked whether it was measured "above the buy level". It is not, and there is
    no fixed relationship to lean on — measured on a real sweep of 117 rows with
    both a box and a buy level, the buy level sits above the ceiling on 107
    (91%) but INSIDE the box on 10 (9%). So the explanation states what the
    number is and, explicitly, what it is not.
  */
  var BOX_FILTER_PLAIN =
    "Box height is how tall the price range itself is \u2014 from its floor up " +
    "to the ceiling that price broke out of, as a percentage of the floor. It " +
    "is not measured from your buy level. A tighter range keeps the floor, " +
    "which is the method's other exit, closer to the buy level.";

  function renderFilterNote(total, kept, unmeasured) {
    // Mark each control so an active filter is visible at a glance. A narrowed
    // list that looks unnarrowed reads as "nothing to trade today".
    [S.fStop, S.fLiq, S.fBox].forEach(function (el) {
      el.setAttribute("data-empty", String(el.value === ""));
    });
    S.fClear.hidden = !anyFilterActive();
    var liqAbsent = syncLiquidityControl();
    if (!anyFilterActive()) {
      if (liqAbsent) {
        S.filterNote.hidden = false;
        S.filterNote.textContent = "";
        var why = document.createElement("span");
        why.className = "fnwhat";
        why.textContent =
          "This sweep recorded no liquidity, so the liquidity filter is off. " +
          "Re-run “Screen universe” to measure it.";
        S.filterNote.appendChild(why);
        return;
      }
      S.filterNote.hidden = true;
      return;
    }
    // Meaning first, arithmetic second: a count is only useful once the reader
    // knows what was counted. Rendered as separate lines rather than joined
    // with "·" — two explanatory sentences and a count on one line is the wall
    // of text this whole rewording exists to avoid.
    var plain = [];
    if (STOP_FILTER_PLAIN[S.fStop.value]) plain.push(STOP_FILTER_PLAIN[S.fStop.value]);
    if (S.fBox.value) plain.push(BOX_FILTER_PLAIN);

    var counts = [kept + " of " + total + " match"];
    if (unmeasured) {
      counts.push(
        unmeasured + " excluded because their liquidity could not be measured " +
        "(too little history) — not because they are illiquid"
      );
    }

    // Built as elements with textContent rather than innerHTML: these strings
    // are constants today, and keeping the note free of markup assembly means a
    // future one carrying a symbol or a reason cannot become an injection.
    S.filterNote.textContent = "";
    plain.forEach(function (text) {
      var line = document.createElement("span");
      line.className = "fnwhat";
      line.textContent = text;
      S.filterNote.appendChild(line);
    });
    var tally = document.createElement("span");
    tally.className = "fncount";
    tally.textContent = counts.join(" · ");
    S.filterNote.appendChild(tally);
    S.filterNote.hidden = false;
  }

  function onFilterChange() {
    renderScreen();
  }

  S.fStop.addEventListener("change", onFilterChange);
  S.fLiq.addEventListener("change", onFilterChange);
  S.fBox.addEventListener("change", onFilterChange);
  S.fClear.addEventListener("click", function () {
    S.fStop.value = ""; S.fLiq.value = ""; S.fBox.value = "";
    onFilterChange();
  });

  // Three views, three questions: what do I do / where are the prices / show
  // me everything. Exactly one is visible, so they cannot render at once.
  function setMode(mode) {
    screen.mode = mode;
    S.advisorView.hidden = mode !== "advisor";
    S.levelsView.hidden = mode !== "levels";
    S.detailedView.hidden = mode !== "table";
    S.modeAdvisor.setAttribute("aria-selected", String(mode === "advisor"));
    S.modeLevels.setAttribute("aria-selected", String(mode === "levels"));
    S.modeTable.setAttribute("aria-selected", String(mode === "table"));
    if (mode === "levels") renderLevels();
  }

  S.modeAdvisor.addEventListener("click", function () { setMode("advisor"); });
  S.modeLevels.addEventListener("click", function () { setMode("levels"); });
  S.modeTable.addEventListener("click", function () { setMode("table"); });

  // ------------------------------------------------- position interactions
  //
  // Restored deliberately after the DX-8b restructure removed them along with
  // the markup they were bound to: the form and both row buttons rendered
  // perfectly and did nothing. Delegated from the two ticket lists rather than
  // bound per button, since tickets are re-rendered on every screen load.

  S.posAddToggle.addEventListener("click", function () {
    var show = S.posForm.hidden;
    S.posForm.hidden = !show;
    this.setAttribute("aria-expanded", String(show));
    if (show) {
      if (!S.pfDate.value) {
        // Local date, not toISOString: UTC is a day behind IST every morning,
        // which is the bug DX-6c hit on the freshness label.
        var d = new Date();
        S.pfDate.value = d.getFullYear() + "-" +
          String(d.getMonth() + 1).padStart(2, "0") + "-" +
          String(d.getDate()).padStart(2, "0");
      }
      S.pfSymbol.focus();
    }
  });

  S.pfCancel.addEventListener("click", function () {
    S.posForm.hidden = true;
    S.posAddToggle.setAttribute("aria-expanded", "false");
    posSay("");
  });

  S.posForm.addEventListener("submit", function (event) {
    event.preventDefault();
    var symbol = S.pfSymbol.value.trim().toUpperCase();
    if (!symbol) { posSay("A symbol is required.", true); return; }
    var body = {
      instrument_id: symbol.indexOf(":") === -1 ? "NSE:" + symbol : symbol,
      quantity: Number(S.pfQty.value),
      entry_price: S.pfPrice.value.trim(),
      entry_date: S.pfDate.value
    };
    if (S.pfStop.value.trim()) body.stop_price = S.pfStop.value.trim();

    posSay("Saving…");
    request("/darvax/api/positions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function () {
      S.posForm.reset();
      S.posForm.hidden = true;
      S.posAddToggle.setAttribute("aria-expanded", "false");
      posSay("");
      return loadPositions();
    }).catch(function (err) {
      posSay(err.message || String(err), true);
    });
  });

  function onTicketClick(event) {
    var closeBtn = event.target.closest("button[data-close]");
    var delBtn = event.target.closest("button[data-del]");
    if (closeBtn) {
      posSay("Closing…");
      request("/darvax/api/positions/" + encodeURIComponent(
        closeBtn.getAttribute("data-close")) + "/close", { method: "POST" })
        .then(loadPositions)
        .then(function () { posSay(""); })
        .catch(function (err) { posSay(err.message || String(err), true); });
      return;
    }
    if (delBtn) {
      // Delete erases a record; close keeps the completed trade. Only the
      // destructive one interrupts.
      if (!window.confirm(
        "Delete this position record? Use \"Mark closed\" instead if the trade " +
        "really happened — that keeps the history.")) return;
      posSay("Deleting…");
      request("/darvax/api/positions/" + encodeURIComponent(
        delBtn.getAttribute("data-del")), { method: "DELETE" })
        .then(loadPositions)
        .then(function () { posSay(""); })
        .catch(function (err) { posSay(err.message || String(err), true); });
    }
  }

  S.sellTickets.addEventListener("click", onTicketClick);
  S.holdTickets.addEventListener("click", onTicketClick);

  loadPositions();

  loadScreen();
})();
