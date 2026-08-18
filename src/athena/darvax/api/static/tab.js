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
  var UI_VERSION = "0.1.0-dx9d2";

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
    frame.setAttribute("data-src", "/darvax/?embedded=1&v=" + UI_VERSION);
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

    // ATHENA's switchTab only knows its own snapshotted nav items, so it cannot
    // deactivate this tab. Listen in the capture phase and stand down ourselves
    // whenever the user picks one of ATHENA's tabs.
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

    // Deep link: /dashboard/darvax opens straight into the tab.
    if (window.location.pathname === ROUTE) activate(false);
  }

  try {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", build);
    } else {
      build();
    }
  } catch (err) {
    // Absolute last resort: DarvaX failing must never break ATHENA's dashboard.
    warn(String(err && err.message ? err.message : err));
  }
})();
