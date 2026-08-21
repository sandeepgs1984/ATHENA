/*
  DarvaX dashboard-tab injector (ADR-010 Amendment 1, DX-4b).

  ATHENA's index.html contains exactly one DarvaX reference: a deferred script
  tag pointing here. That tag IS the flag guard — this asset is served only by
  the DarvaX sub-application, so when DarvaX is disabled or deleted the request
  404s, this code never runs, and the dashboard renders with its original tabs.
  No DarvaX markup, styling or logic lives in any ATHENA asset.

  Two constraints shape the implementation:

  1. ATHENA captures `navItems`/`tabPanes` via querySelectorAll at load, which
     returns a STATIC NodeList. A tab injected afterwards is therefore invisible
     to ATHENA's own switchTab(): it will not be activated, and ATHENA's tab
     switches will not deactivate it. So this script manages its own activation
     and listens for ATHENA tab clicks to stand down. This is the runtime
     coupling Amendment 1 records as an accepted, monitored risk.

  2. The panel embeds the existing /darvax/ page in a same-origin iframe rather
     than re-implementing the UI. One copy of the DarvaX interface, far less to
     break, and sessionStorage (where ATHENA's token lives) is shared with
     same-origin iframes in the same tab, so the session carries over.

  Degradation contract: if any expected ATHENA hook is missing, log once and do
  nothing. Never throw into ATHENA's page. A broken tab must never mean a broken
  dashboard, and /darvax/ stays independently reachable regardless.
*/
(function () {
  "use strict";

  var TAB_ID = "darvax";
  var LABEL = "DarvaX";
  var PANEL_ID = "tab-darvax";
  var ROUTE = "/dashboard/darvax";

  // Bumped with the DarvaX UI assets. The iframe src is a cache key of its own,
  // and it is set dynamically on tab activation — which does NOT inherit the
  // parent page's reload cache-bypass, so a hard reload of the dashboard leaves
  // a stale frame document in place. Changing this string changes the URL, and
  // a URL the browser has never seen cannot be served from cache.
  var UI_VERSION = "0.1.0-aux7c";

  function warn(reason) {
    // One line, once. DarvaX must not spam or destabilise ATHENA's console.
    if (window.console && console.warn) {
      console.warn(
        "[darvax] dashboard tab not injected (" + reason + "). " +
        "DarvaX remains available at /darvax/."
      );
    }
  }

  function build() {
    var nav = document.querySelector("nav.sidebar-nav");
    var anyPane = document.querySelector(".tab-pane");
    var pageTitle = document.getElementById("page-title");

    if (!nav) return warn("no nav.sidebar-nav");
    if (!anyPane || !anyPane.parentElement) return warn("no .tab-pane container");
    if (document.getElementById(PANEL_ID)) return; // already injected

    var paneHost = anyPane.parentElement;

    // --- styles: DarvaX's own, injected here, never in ATHENA's CSS ---------
    var style = document.createElement("style");
    style.id = "darvax-tab-style";
    style.textContent = [
      "#" + PANEL_ID + " { padding: 0; }",
      "#" + PANEL_ID + " .darvax-embed {",
      "  width: 100%; height: calc(100vh - 132px); min-height: 460px;",
      "  border: 0; display: block; background: transparent;",
      "}",
      ".nav-item[data-tab='" + TAB_ID + "'] .darvax-flag {",
      "  margin-left: auto; font-size: 9px; letter-spacing: .06em;",
      "  text-transform: uppercase; color: #d99a2b;",
      "  border: 1px solid #d99a2b; border-radius: 3px; padding: 0 4px;",
      "}"
    ].join("\n");
    document.head.appendChild(style);

    // --- nav item ----------------------------------------------------------
    // Uses ATHENA's own .nav-item class so it inherits sidebar styling, and
    // carries an EXP flag so the tab itself says the lane is experimental.
    var link = document.createElement("a");
    link.href = ROUTE;
    link.className = "nav-item";
    link.setAttribute("data-tab", TAB_ID);
    link.title = LABEL + " (experimental, unvalidated)";
    link.innerHTML =
      '<i class="fa-solid fa-box"></i><span>' + LABEL + "</span>" +
      '<span class="darvax-flag">Exp</span>';
    nav.appendChild(link);

    // --- panel with the embedded DarvaX page -------------------------------
    var panel = document.createElement("div");
    panel.id = PANEL_ID;
    panel.className = "tab-pane";
    var frame = document.createElement("iframe");
    frame.className = "darvax-embed";
    frame.title = "DarvaX (experimental)";
    // embedded=1 lets the page drop its redundant back-link inside the tab.
    // It never hides the experimental banner.
    // AUX-6: a cross-link from ATHENA's own Decision Brief lands on
    // /dashboard/darvax?symbol=&mode= (this file's own ROUTE, so the
    // outer page keeps ATHENA's sidebar rather than dropping to DarvaX's
    // bare standalone page) -- forward those same params into the iframe
    // so the embedded view opens pre-scoped instead of unfiltered. Read
    // once at build() time: this whole file only runs on a fresh page
    // load (a plain <a href> navigation, not an SPA route change), so
    // there is no later point where these params could change underneath
    // an already-built iframe.
    var outerParams = new URLSearchParams(window.location.search);
    var crosslinkSymbol = outerParams.get("symbol");
    var crosslinkMode = outerParams.get("mode");
    // AUX-7: view=symbol360 is the same idea one page over -- a
    // ?symbol=&view=symbol360 landing on this ROUTE means "open Symbol 360
    // inside ATHENA's own DarvaX tab", not the main screener. Without this
    // branch, showSymbol360Link()/symbol360Chip() below would have to link
    // straight at /darvax/symbol360, which is exactly the AUX-6 bug 4
    // pattern repeated: it drops ATHENA's sidebar/chrome entirely instead
    // of staying inside this tab's iframe.
    var frameSrc = outerParams.get("view") === "symbol360"
      ? "/darvax/symbol360?embedded=1&v=" + UI_VERSION
      : "/darvax/?embedded=1&v=" + UI_VERSION;
    if (crosslinkSymbol) frameSrc += "&symbol=" + encodeURIComponent(crosslinkSymbol);
    if (crosslinkMode) frameSrc += "&mode=" + encodeURIComponent(crosslinkMode);
    frame.setAttribute("data-src", frameSrc);
    frame.setAttribute("loading", "lazy");
    panel.appendChild(frame);
    paneHost.appendChild(panel);

    function deactivateAthena() {
      // Queried fresh each time, not snapshotted, so this stays correct even if
      // ATHENA's own tab set changes later.
      document.querySelectorAll(".tab-pane").forEach(function (pane) {
        if (pane.id !== PANEL_ID) pane.classList.remove("active");
      });
      document.querySelectorAll(".nav-item").forEach(function (item) {
        if (item.getAttribute("data-tab") !== TAB_ID) {
          item.classList.remove("active");
        }
      });
    }

    function activate(pushHistory) {
      deactivateAthena();
      panel.classList.add("active");
      link.classList.add("active");
      if (pageTitle) pageTitle.textContent = LABEL;
      // Load the frame only on first activation — DarvaX must not read ATHENA's
      // data or add page-load cost for someone who never opens the tab.
      if (!frame.getAttribute("src")) {
        frame.setAttribute("src", frame.getAttribute("data-src"));
      }
      if (pushHistory) {
        try {
          window.history.pushState({ tabId: TAB_ID }, "", ROUTE);
        } catch (err) {
          /* history is a nicety here, not a requirement */
        }
      }
    }

    function standDown() {
      panel.classList.remove("active");
      link.classList.remove("active");
    }

    link.addEventListener("click", function (event) {
      event.preventDefault();
      activate(true);
    });

    // ATHENA's switchTab reads navItems/tabPanes captured with
    // querySelectorAll -- but NOT at page-parse time as the name "snapshot"
    // suggests. ATHENA's own bootstrap (dashboard.js) defers that capture,
    // and its own routing, behind an async auth-status fetch that resolves
    // AFTER this deferred script has already run -- so by the time it
    // captures those NodeLists, this tab's nav item/pane already exist and
    // ARE included. A real, owner-caught bug proved this: on a deep link to
    // ROUTE, activate(false) below would win the race and set this tab
    // active, only for ATHENA's own switchTab("overview") to fire moments
    // later (unaware "darvax" isn't one of its own tab ids) and deactivate
    // it right back out from under the owner, landing on Overview instead
    // of DarvaX with no visible failure at all. Listening for ATHENA's own
    // clicks (below) is a completely different, NON-racy case -- a click
    // is synchronous and happens well after all of this has settled -- so
    // it is untouched by the fix beneath it.
    document.querySelectorAll(".nav-item").forEach(function (item) {
      if (item.getAttribute("data-tab") === TAB_ID) return;
      item.addEventListener("click", standDown, true);
    });

    window.addEventListener("popstate", function () {
      if (window.location.pathname === ROUTE) {
        activate(false);
      } else {
        standDown();
      }
    });

    // Deep link: /dashboard/darvax opens straight into the tab. Racy
    // against ATHENA's own async routing (see the comment above) --
    // activate now, but also watch for ATHENA's bootstrap clobbering it
    // and reassert exactly once, rather than guessing a delay long enough
    // to always run after a network round trip whose timing this file has
    // no way to know.
    if (window.location.pathname === ROUTE) {
      activate(false);
      var reassertOnce = new MutationObserver(function () {
        if (panel.classList.contains("active")) return;
        reassertOnce.disconnect();
        activate(false);
      });
      reassertOnce.observe(paneHost, { attributes: true, attributeFilter: ["class"], subtree: true });
      // Nothing to reassert against forever -- ATHENA's own routing settles
      // within one fetch round trip, not seconds. Stop watching well after
      // that so a page that never triggers it doesn't run an observer for
      // the rest of the session.
      setTimeout(function () { reassertOnce.disconnect(); }, 5000);
    }
  }

  // AUX-6 "See the other view" — a quiet link on ATHENA's Decision Brief when
  // DarvaX also has a persisted signal for the same instrument. Injected
  // entirely from here, never from any ATHENA asset: ATHENA's own dashboard
  // stays completely unaware DarvaX exists, the same constraint that governs
  // everything else in this file. A missing/removed ATHENA hook degrades to
  // silently doing nothing, per this file's own degradation contract.
  var ATHENA_TOKEN_KEY = "athena.access_token";
  var crosslinkEl = null;
  var crosslinkRequestId = 0;

  function crosslinkToken() {
    try {
      return sessionStorage.getItem(ATHENA_TOKEN_KEY) || "";
    } catch (err) {
      return "";
    }
  }

  function removeCrossLink() {
    if (crosslinkEl && crosslinkEl.parentElement) {
      crosslinkEl.parentElement.removeChild(crosslinkEl);
    }
    crosslinkEl = null;
  }

  function checkCrossLink(instrumentId, bareSymbol) {
    var requestId = ++crosslinkRequestId;
    removeCrossLink();
    if (!instrumentId) return;
    var headers = {};
    var bearer = crosslinkToken();
    if (bearer) headers.Authorization = "Bearer " + bearer;
    fetch("/darvax/api/signals/" + encodeURIComponent(instrumentId), { headers: headers })
      .then(function (res) {
        if (requestId !== crosslinkRequestId || !res.ok) return;
        var metaRow = document.getElementById("decision-brief-meta-row");
        if (!metaRow || !metaRow.parentElement) return;
        var link = document.createElement("a");
        link.className = "context-chip tone-neutral";
        // Same-tab navigation, deliberately -- a new tab (even without
        // rel="noopener") is not reliably guaranteed to inherit this tab's
        // sessionStorage across real browsers, and that is exactly where
        // the ATHENA auth token lives. Owner-verified real bug: a "_blank"
        // link opened to a login screen instead of the target page.
        // Same-tab navigation is the same top-level browsing context, so
        // there is nothing to inherit -- the token is simply already there.
        //
        // Links to THIS file's own ROUTE (/dashboard/darvax), not directly
        // to /darvax/ -- owner-caught real UX bug: a direct link dropped
        // the owner onto DarvaX's bare standalone page with ATHENA's own
        // sidebar/chrome gone entirely. build() above reads these same
        // ?symbol=/&mode= params back out of this exact URL and forwards
        // them into the embedded iframe's src, so the click instead opens
        // ATHENA's own DarvaX tab, pre-scoped to the right symbol, with
        // the rest of the dashboard still around it.
        link.href = ROUTE + "?symbol=" + encodeURIComponent(bareSymbol) + "&mode=table";
        // #decision-brief-header is a column flexbox; an unstyled child
        // stretches to its full width by default (flex's align-self:
        // stretch), which is why this first rendered as a wide banner
        // instead of a small chip. inline-flex + align-self: flex-start
        // makes it hug its own content, matching every other .context-chip
        // usage elsewhere on the page.
        link.style.display = "inline-flex";
        link.style.alignSelf = "flex-start";
        link.style.marginTop = "6px";
        // .context-chip is normally applied to a <span>; as an <a> it would
        // otherwise pick up the browser's default underline.
        link.style.textDecoration = "none";
        link.textContent = LABEL + " also has a read on this →";
        // showSymbol360Link runs synchronously just after this fetch starts,
        // so by the time this resolves it has usually already inserted its
        // own link right after metaRow -- anchor after it when present, so
        // the two links land in a deterministic order instead of racing.
        var anchor = symbol360El || metaRow;
        anchor.parentElement.insertBefore(link, anchor.nextSibling);
        crosslinkEl = link;
      })
      .catch(function () {
        // Unreachable, disabled, or a transient failure — no link, no noise.
      });
  }

  // AUX-7 "Symbol 360" — unlike the DarvaX-signal link above, this is shown
  // unconditionally: ATHENA's own decision, saved-symbol status, and journal
  // history are all useful on that page even when DarvaX has nothing for
  // the instrument, so there is no existence check to gate it on.
  var symbol360El = null;

  function removeSymbol360Link() {
    if (symbol360El && symbol360El.parentElement) {
      symbol360El.parentElement.removeChild(symbol360El);
    }
    symbol360El = null;
  }

  function showSymbol360Link(instrumentId, bareSymbol) {
    removeSymbol360Link();
    if (!instrumentId) return;
    var metaRow = document.getElementById("decision-brief-meta-row");
    if (!metaRow || !metaRow.parentElement) return;
    var link = document.createElement("a");
    link.className = "context-chip tone-neutral";
    // Same reasoning as checkCrossLink's link above: same-tab navigation,
    // no target, since tab.js only ever runs in ATHENA's own top-level page.
    // Links to THIS file's own ROUTE, not straight at /darvax/symbol360 --
    // an owner-caught bug identical to AUX-6's bug 4: a direct link dropped
    // ATHENA's own sidebar/chrome entirely. build() above reads view=symbol360
    // back out of this exact URL and points the embedded iframe at
    // /darvax/symbol360 instead of the main screener, so the click opens
    // Symbol 360 inside ATHENA's own DarvaX tab, sidebar intact.
    link.href = ROUTE + "?symbol=" + encodeURIComponent(bareSymbol) + "&view=symbol360";
    link.style.display = "inline-flex";
    link.style.alignSelf = "flex-start";
    link.style.marginTop = "6px";
    link.style.marginLeft = "6px";
    link.style.textDecoration = "none";
    link.textContent = "View Symbol 360 →";
    metaRow.parentElement.insertBefore(link, metaRow.nextSibling);
    symbol360El = link;
  }

  function watchDecisionBrief() {
    var titleEl = document.getElementById("decision-brief-title");
    if (!titleEl || typeof MutationObserver === "undefined") return;
    var lastInstrument = null;
    new MutationObserver(function () {
      var instrumentId = titleEl.getAttribute("title");
      if (instrumentId === lastInstrument) return;
      lastInstrument = instrumentId;
      checkCrossLink(instrumentId, titleEl.textContent || "");
      showSymbol360Link(instrumentId, titleEl.textContent || "");
    }).observe(titleEl, { attributes: true, attributeFilter: ["title"] });
  }

  try {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", build);
      document.addEventListener("DOMContentLoaded", watchDecisionBrief);
    } else {
      build();
      watchDecisionBrief();
    }
  } catch (err) {
    // Absolute last resort: DarvaX failing must never break ATHENA's dashboard.
    warn(String(err && err.message ? err.message : err));
  }
})();
