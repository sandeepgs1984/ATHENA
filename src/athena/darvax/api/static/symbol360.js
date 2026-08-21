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
    if (backLink) backLink.setAttribute("href", "/darvax/?embedded=1&v=0.1.0-aux7");
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
    historySub: document.getElementById("s360-history-sub"),
    historyTbody: document.getElementById("s360-history-tbody")
  };

  var current = { instrumentId: null, bareSymbol: null, saved: false };

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
      "<dt>As of</dt><dd>" + esc(meta.ts) + "</dd>" +
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

  function renderDarvaxCard(row, signal) {
    if (!row && !signal) {
      els.darvaxCard.innerHTML = '<p class="dim">DarvaX has no read on this instrument yet.</p>';
      return;
    }
    if (row) {
      var lines =
        "<dt>Tier</dt><dd>" + esc(row.tier) + "</dd>" +
        "<dt>Action</dt><dd>" + esc(row.action) + "</dd>" +
        "<dt>Close</dt><dd>" + money(row.close) + "</dd>" +
        "<dt>Buy above</dt><dd>" + money(row.trigger_price) + "</dd>" +
        "<dt>Stop loss</dt><dd>" + money(row.stop_price) + "</dd>" +
        "<dt>Box</dt><dd>" + money(row.box_bottom) + " – " + money(row.box_top) + "</dd>";
      els.darvaxCard.innerHTML =
        '<dl class="lines">' + lines + "</dl>" +
        (row.action_reason_plain
          ? '<p class="why" style="margin-top:8px;">' + esc(row.action_reason_plain) + "</p>"
          : "");
      return;
    }
    // No current sweep row for this instrument, but a raw signal exists from
    // an ad hoc scan -- show the lighter-weight reading rather than nothing,
    // clearly labelled as such (it carries no tier/action, only the box
    // computation itself).
    var lines2 =
      "<dt>Signal</dt><dd>" + esc(signal.signal_type) + "</dd>" +
      "<dt>Rule</dt><dd>" + esc(signal.darvas_rule) + "</dd>" +
      "<dt>Close</dt><dd>" + money(signal.close) + "</dd>" +
      "<dt>Box</dt><dd>" + money(signal.box_bottom) + " – " + money(signal.box_top) + "</dd>";
    els.darvaxCard.innerHTML =
      '<p class="dim">No current sweep row for this instrument — showing its last scanned signal instead.</p>' +
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
