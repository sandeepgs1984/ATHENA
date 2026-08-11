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

  els.scan.addEventListener("click", scan);
  els.refresh.addEventListener("click", load);
  els.symbols.addEventListener("keydown", function (event) {
    if (event.key === "Enter") scan();
  });

  load();
})();
