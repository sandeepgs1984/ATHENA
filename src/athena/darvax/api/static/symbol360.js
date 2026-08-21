/*
  AUX-7 "Symbol 360" — one search box, one page: ATHENA's Decision, DarvaX's
  screen result, saved-symbol status, and journal history for one instrument,
  side by side.

  DarvaX-owned (ADR-010 DX-4), same as every other file in this directory --
  this page's own JS fetches ATHENA's API directly, which is architecturally
  fine in this direction (DarvaX may read ATHENA; the reverse is what AUX-6
  proved is forbidden for any ATHENA-owned asset). Deliberately standalone,
  same convention as darvax.js/tab.js: duplicates the small token/request
  helpers rather than importing them, so this page has no load-order
  dependency on darvax.js.

  Pure presentation over data every engine already persists (ADR-005): every
  value shown here comes from an endpoint AUX-5, AUX-6, or ATHENA core
  already exposed -- no new backend route, no new domain computation.
*/
(function () {
  "use strict";

  var ATHENA_TOKEN_KEY = "athena.access_token";

  function token() {
    try {
      return sessionStorage.getItem(ATHENA_TOKEN_KEY) || "";
    } catch (err) {
      return "";
    }
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
      return response.json().then(function (payload) {
        if (!response.ok) {
          var detail = (payload && (payload.detail || payload.title)) || "";
          throw new Error(detail || "Request failed (" + response.status + ")");
        }
        return payload;
      });
    });
  }

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function num(raw, dp) {
    if (raw === null || raw === undefined || raw === "") return null;
    var v = Number(raw);
    return isFinite(v) ? (dp === undefined ? v : Number(v.toFixed(dp))) : null;
  }

  function money(raw) {
    var v = num(raw);
    return v === null ? "—" : "₹" + v.toLocaleString("en-IN");
  }

  // When embedded in ATHENA's DarvaX tab (same convention as darvax.js),
  // the "back to DarvaX" link must carry embedded=1 forward -- it navigates
  // only this iframe (no target on the <a>), and without these params the
  // main screener would load *not* embedded, showing its own redundant
  // "back to ATHENA" link instead of relying on ATHENA's own sidebar.
  if (window.location.search.indexOf("embedded=1") !== -1) {
    var backLink = document.querySelector("a.link[href='/darvax/']");
    if (backLink) backLink.setAttribute("href", "/darvax/?embedded=1&v=0.1.0-aux8b");
  }

  var els = {
    form: document.getElementById("s360-form"),
    input: document.getElementById("s360-input"),
    note: document.getElementById("s360-note"),
    result: document.getElementById("s360-result"),
    title: document.getElementById("s360-title"),
    athenaCard: document.getElementById("s360-athena-card"),
    darvaxCard: document.getElementById("s360-darvax-card"),
    saveToggle: document.getElementById("s360-save-toggle"),
    scanBtn: document.getElementById("s360-scan-btn"),
    scanNote: document.getElementById("s360-scan-note"),
    historySub: document.getElementById("s360-history-sub"),
    historyTbody: document.getElementById("s360-history-tbody")
  };

  var current = { instrumentId: null, bareSymbol: null, saved: false };

  // Bumped on every lookup() and every scanAndValidate() call so a stale
  // scan response (from a previous symbol, or superseded by a second click)
  // can never overwrite a card that has since moved on to something else --
  // same out-of-order-response guard convention tab.js's checkCrossLink uses.
  var scanRequestId = 0;

  function normalizeInstrumentId(raw) {
    var v = (raw || "").trim().toUpperCase();
    if (!v) return null;
    return v.indexOf(":") === -1 ? "NSE:" + v : v;
  }

  function bareSymbolOf(instrumentId) {
    return instrumentId.indexOf(":") === -1 ? instrumentId : instrumentId.split(":").pop();
  }

  function setNote(message, isError) {
    els.note.textContent = message || "";
    els.note.style.color = isError ? "var(--bad)" : "";
  }

  // Same convention ATHENA's own dashboard uses for every "As of" line
  // (05-utils.js's formatDecisionTime) -- duplicated per this file's own
  // no-cross-file-import rule rather than shared, so a raw ISO timestamp
  // never reaches this page any more literally than it reaches ATHENA's own.
  function formatDecisionTime(value) {
    var date = new Date(value);
    if (isNaN(date.getTime())) return "Unknown time";
    return date.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit"
    }) + " IST";
  }

  // -------------------------------------------------------- ATHENA decision

  function renderAthenaCard(decision) {
    if (!decision) {
      els.athenaCard.innerHTML = '<p class="dim">ATHENA has no decision for this instrument yet.</p>';
      return;
    }
    var meta = decision.metadata || {};
    var analysis = decision.analysis || {};
    var plan = decision.trade_plan;
    var lines =
      "<dt>Type</dt><dd>" + esc(meta.decision_type) + " &middot; " + esc(meta.direction) + "</dd>" +
      "<dt>As of</dt><dd>" + esc(formatDecisionTime(meta.ts)) + "</dd>" +
      "<dt>Confidence</dt><dd>" + esc(analysis.confidence_level || "—") + "</dd>";
    if (plan) {
      lines += "<dt>Entry zone</dt><dd>" + money(plan.entry_low) + " – " + money(plan.entry_high) + "</dd>" +
        "<dt>Stop loss</dt><dd>" + money(plan.stop_loss) + "</dd>" +
        "<dt>Targets</dt><dd>" + (plan.targets || []).map(money).join(", ") + "</dd>";
    }
    els.athenaCard.innerHTML =
      '<dl class="lines">' + lines + "</dl>" +
      (decision.explanation
        ? '<p class="why" style="margin-top:8px;">' + esc(decision.explanation) + "</p>"
        : "");
  }

  function loadAthenaDecision(instrumentId) {
    return request("/api/v1/decisions?instrument_id=" + encodeURIComponent(instrumentId) + "&page_size=1")
      .then(function (payload) {
        var items = (payload && payload.data) || [];
        renderAthenaCard(items[0] || null);
      })
      .catch(function () { renderAthenaCard(null); });
  }

  // ---------------------------------------------------------- DarvaX's read

  // Same labels darvax.js's own ACTION_LABEL uses (Advisor/Levels/Table) --
  // duplicated per this file's own established convention rather than
  // imported, so a raw DAR-CARD code (e.g. "ENTER_ON_RETEST") never reaches
  // this page any more literally than it reaches any other DarvaX view.
  var ACTION_LABEL = {
    ENTER: "Buy",
    ENTER_ON_RETEST: "Buy on retest",
    WAIT: "Wait",
    HOLD: "Hold",
    EXIT: "Sell",
    EXIT_IF_HELD: "Sell if held",
    NO_ENTRY: "Skip"
  };

  function actionLabel(row) {
    // Label only, deliberately no bracketed price: this card already shows
    // "Buy above"/"Stop loss" as their own dt/dd rows immediately below --
    // repeating the same number in the action line itself read as
    // confusing duplication, not extra clarity, once actually seen live.
    return esc(ACTION_LABEL[row.action] || row.action || "—");
  }

  // Owner-reported: "Buy on retest" alone doesn't say what price the retest
  // actually is. Reuses the same already-persisted action_reason_plain this
  // card already prints as its own "why" paragraph below (e.g. "Price broke
  // out and has dipped back to test ₹138, the level it cleared.") -- never
  // a new sentence, so a hover and the prose beneath it can never disagree.
  function actionTitleAttr(row) {
    var reason = row.action_reason_plain || row.action_reason || "";
    return reason ? ' title="' + esc(reason) + '"' : "";
  }

  function renderDarvaxCard(row, signal, freshlyScanned) {
    if (!row && !signal) {
      els.darvaxCard.innerHTML = '<p class="dim">DarvaX has no read on this instrument yet.</p>';
      return;
    }
    if (row) {
      // "Scan & Validate" (AUX-8) classifies its fresh signal with the exact
      // same screen_signal() a real sweep uses, so it renders through this
      // same branch as a sweep's ScreenResult -- identical shape, identical
      // fields. The only difference worth telling the owner about: it skips
      // the sweep-wide held-position/liquidity/trend context (screen_signal's
      // own documented optional inputs), so it's flagged, not silently
      // presented as equivalent to a completed universe sweep.
      var rowIntro = freshlyScanned
        ? "Freshly scanned just now — not the last completed universe sweep, " +
          "and doesn't know about any position you hold in this symbol."
        : "";
      var lines =
        "<dt>Tier</dt><dd>" + esc(row.tier) + "</dd>" +
        "<dt>Action</dt><dd" + actionTitleAttr(row) + ">" + actionLabel(row) + "</dd>" +
        "<dt>Close</dt><dd>" + money(row.close) + "</dd>" +
        "<dt>Buy above</dt><dd>" + money(row.trigger_price) + "</dd>" +
        "<dt>Stop loss</dt><dd>" + money(row.stop_price) + "</dd>" +
        "<dt>Box</dt><dd>" + money(row.box_bottom) + " – " + money(row.box_top) + "</dd>";
      els.darvaxCard.innerHTML =
        (rowIntro ? '<p class="dim">' + esc(rowIntro) + "</p>" : "") +
        '<dl class="lines">' + lines + "</dl>" +
        (row.action_reason_plain
          ? '<p class="why" style="margin-top:8px;">' + esc(row.action_reason_plain) + "</p>"
          : "");
      return;
    }
    // No current sweep row for this instrument, but a raw signal exists --
    // either an earlier ad hoc scan (passive lookup path) or the one this
    // page's own "Scan & Validate" button just triggered (freshlyScanned) --
    // show the lighter-weight reading rather than nothing, clearly labelled
    // as such (it carries no tier/action, only the box computation itself).
    var intro = freshlyScanned
      ? "Freshly scanned just now — not yet part of a saved universe sweep."
      : "No current sweep row for this instrument — showing its last scanned signal instead.";
    var lines2 =
      "<dt>Signal</dt><dd>" + esc(signal.signal_type) + "</dd>" +
      "<dt>Rule</dt><dd>" + esc(signal.darvas_rule) + "</dd>" +
      "<dt>Close</dt><dd>" + money(signal.close) + "</dd>" +
      "<dt>Box</dt><dd>" + money(signal.box_bottom) + " – " + money(signal.box_top) + "</dd>";
    els.darvaxCard.innerHTML =
      '<p class="dim">' + esc(intro) + "</p>" +
      '<dl class="lines">' + lines2 + "</dl>" +
      (signal.explanation
        ? '<p class="why" style="margin-top:8px;">' + esc(signal.explanation) + "</p>"
        : "");
  }

  function loadDarvaxRead(instrumentId) {
    return request("/darvax/api/screen/latest?limit=5000")
      .then(function (payload) {
        var rows = (payload && payload.data) || [];
        var row = null;
        for (var i = 0; i < rows.length; i++) {
          if (rows[i].instrument_id === instrumentId) { row = rows[i]; break; }
        }
        if (row) { renderDarvaxCard(row, null); return; }
        return request("/darvax/api/signals/" + encodeURIComponent(instrumentId))
          .then(function (sigPayload) { renderDarvaxCard(null, sigPayload.data); })
          .catch(function () { renderDarvaxCard(null, null); });
      })
      .catch(function () { renderDarvaxCard(null, null); });
  }

  // ---------------------------------------------------- Scan & Validate now

  // Owner-requested: "Look up" above only ever reads whatever each engine
  // has already persisted -- this is a second, explicit action that actually
  // re-runs both engines for the current symbol. Deliberately not folded
  // into "Look up" itself: ATHENA's half makes a real Kite ingest call and
  // both halves persist new data (a Decision, a DarvaxSignal), so neither
  // should fire on every search, only when the owner asks for it.
  //
  // The two engines run concurrently and update their own card independently
  // as each finishes -- ATHENA's live ingest is typically the slower of the
  // two -- and a failure in one (e.g. an expired Kite session) never blocks
  // or corrupts the other's result.

  function setScanNote(message, isError) {
    els.scanNote.textContent = message || "";
    els.scanNote.style.color = isError ? "var(--bad)" : "";
  }

  function athenaValidateNow(instrumentId, bareSymbol, requestId) {
    els.athenaCard.innerHTML = '<p class="dim">Scanning…</p>';
    // /market/validate requires the symbol to already be a known candidate;
    // upserting first (idempotent -- safe even if it already is one) is the
    // same two-call sequence ATHENA's own dashboard already uses for this
    // (09-market-intelligence.js's validateSymbolsNow), reused here rather
    // than invented fresh.
    return request("/api/v1/market/candidates", {
      method: "POST",
      body: { symbol: bareSymbol }
    }).then(function () {
      return request("/api/v1/market/validate", {
        method: "POST",
        body: { symbols: [bareSymbol] }
      });
    }).then(function () {
      // /validate returns run counts, not the decision itself -- the fresh
      // decision is picked up by re-running the exact same read lookup()
      // already uses, so the card can never render two different shapes of
      // "an ATHENA decision" depending on how it got there.
      if (requestId !== scanRequestId) return;
      return loadAthenaDecision(instrumentId);
    }).catch(function (err) {
      if (requestId !== scanRequestId) return;
      els.athenaCard.innerHTML = '<p class="dim" style="color:var(--bad);">' +
        "Could not run ATHENA validation: " + esc(err.message || "unknown error") + "</p>";
    });
  }

  function darvaxScanNow(instrumentId, requestId) {
    els.darvaxCard.innerHTML = '<p class="dim">Scanning…</p>';
    return request("/darvax/api/scan", {
      method: "POST",
      body: { instrument_ids: [instrumentId] }
    }).then(function (payload) {
      if (requestId !== scanRequestId) return;
      // The scan response's "screened" array carries the same
      // tier/action-classified shape a real sweep's ScreenResult does
      // (screen_signal applied server-side to the fresh signal) -- rendered
      // through the same row branch as "Look up", not the raw-signal
      // fallback, so the two actions can never show two different shapes of
      // "a DarvaX read" for one symbol. Falls back to the unclassified
      // signal only if, somehow, classification is missing from the
      // response (an older server, never this one).
      var screened = (payload && payload.screened) || [];
      if (screened.length) {
        renderDarvaxCard(screened[0], null, true);
        return;
      }
      var signals = (payload && payload.data) || [];
      renderDarvaxCard(null, signals[0] || null, true);
    }).catch(function (err) {
      if (requestId !== scanRequestId) return;
      els.darvaxCard.innerHTML = '<p class="dim" style="color:var(--bad);">' +
        "Could not run DarvaX scan: " + esc(err.message || "unknown error") + "</p>";
    });
  }

  function scanAndValidate() {
    if (!current.instrumentId) return;
    var requestId = ++scanRequestId;
    var instrumentId = current.instrumentId;
    var bareSymbol = current.bareSymbol;
    els.scanBtn.disabled = true;
    setScanNote("Scanning " + bareSymbol + " with both engines…");
    Promise.all([
      athenaValidateNow(instrumentId, bareSymbol, requestId),
      darvaxScanNow(instrumentId, requestId)
    ]).then(function () {
      if (requestId === scanRequestId) setScanNote("Scanned just now.");
    }).then(function () {
      if (requestId === scanRequestId) els.scanBtn.disabled = false;
    });
  }

  els.scanBtn.addEventListener("click", scanAndValidate);

  // ------------------------------------------------------- saved-symbol star

  function renderSaveToggle() {
    els.saveToggle.setAttribute("aria-pressed", String(current.saved));
    els.saveToggle.innerHTML = current.saved
      ? '<span class="s360-save-star">&#9733;</span> Saved'
      : '<span class="s360-save-star">&#9734;</span> Save symbol';
  }

  function loadSavedStatus(bare) {
    return request("/api/v1/saved-symbols")
      .then(function (payload) {
        var list = (payload && payload.data && payload.data.symbols) || [];
        current.saved = list.some(function (s) { return s.symbol === bare; });
        renderSaveToggle();
      })
      .catch(function () { current.saved = false; renderSaveToggle(); });
  }

  els.saveToggle.addEventListener("click", function () {
    if (!current.bareSymbol) return;
    els.saveToggle.disabled = true;
    var op = current.saved
      ? request("/api/v1/saved-symbols/" + encodeURIComponent(current.bareSymbol), { method: "DELETE" })
      : request("/api/v1/saved-symbols", { method: "POST", body: { symbol: current.bareSymbol } });
    op.then(function () {
      current.saved = !current.saved;
      renderSaveToggle();
    }).catch(function (err) {
      setNote(err.message || "Could not update saved symbols.", true);
    }).then(function () {
      els.saveToggle.disabled = false;
    });
  });

  // ------------------------------------------------------------ journal history

  function historyRow(entry) {
    var meta = entry.decision.metadata || {};
    var response = entry.journal ? esc(entry.journal.user_action) : "—";
    var outcome = entry.outcome
      ? (Number(entry.outcome.pnl) >= 0 ? "+" : "") + money(entry.outcome.pnl)
      : "—";
    return "<tr>" +
      "<td>" + esc(String(meta.ts || "").slice(0, 10)) + "</td>" +
      "<td>" + esc(meta.decision_type) + " " + esc(meta.direction) + "</td>" +
      "<td>" + response + "</td>" +
      "<td>" + outcome + "</td>" +
      "</tr>";
  }

  var HISTORY_LIMIT = 10;

  function loadJournalHistory(instrumentId) {
    return request("/api/v1/decisions?instrument_id=" + encodeURIComponent(instrumentId) + "&page_size=" + HISTORY_LIMIT)
      .then(function (payload) {
        var decisions = (payload && payload.data) || [];
        if (!decisions.length) {
          els.historySub.textContent = "no decisions recorded for this instrument yet";
          els.historyTbody.innerHTML = "";
          return;
        }
        els.historySub.textContent = decisions.length + " most recent decision(s)";
        return Promise.all(decisions.map(function (d) {
          var id = d.metadata.decision_id;
          return Promise.all([
            request("/api/v1/decisions/" + encodeURIComponent(id) + "/journal"),
            request("/api/v1/decisions/" + encodeURIComponent(id) + "/outcome")
          ]).then(function (results) {
            return {
              decision: d,
              journal: results[0] && results[0].data,
              outcome: results[1] && results[1].data
            };
          }).catch(function () {
            return { decision: d, journal: null, outcome: null };
          });
        })).then(function (rows) {
          els.historyTbody.innerHTML = rows.map(historyRow).join("");
        });
      })
      .catch(function () {
        els.historySub.textContent = "could not load history";
        els.historyTbody.innerHTML = "";
      });
  }

  // ------------------------------------------------------------------- search

  function lookup(raw) {
    var instrumentId = normalizeInstrumentId(raw);
    if (!instrumentId) {
      setNote("Enter a symbol first.", true);
      return;
    }
    var bare = bareSymbolOf(instrumentId);
    current.instrumentId = instrumentId;
    current.bareSymbol = bare;
    // Invalidate any scanAndValidate() still in flight for a previous
    // symbol, and reset its own UI -- otherwise a slow ATHENA validate call
    // for the OLD symbol could resolve after this new lookup and clobber
    // the card that now belongs to a different one.
    scanRequestId++;
    els.scanBtn.disabled = false;
    setScanNote("");
    setNote("");
    els.result.hidden = false;
    els.title.textContent = bare;
    els.athenaCard.innerHTML = '<p class="dim">Loading…</p>';
    els.darvaxCard.innerHTML = '<p class="dim">Loading…</p>';
    els.historyTbody.innerHTML = "";
    els.historySub.textContent = "";
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("symbol", bare);
      window.history.replaceState(null, "", url.pathname + url.search);
    } catch (err) {
      /* history is a nicety here, not a requirement */
    }
    loadAthenaDecision(instrumentId);
    loadDarvaxRead(instrumentId);
    loadSavedStatus(bare);
    loadJournalHistory(instrumentId);
  }

  els.form.addEventListener("submit", function (event) {
    event.preventDefault();
    lookup(els.input.value);
  });

  var initialSymbol = new URLSearchParams(window.location.search).get("symbol");
  if (initialSymbol) {
    els.input.value = initialSymbol;
    lookup(initialSymbol);
  }
})();
