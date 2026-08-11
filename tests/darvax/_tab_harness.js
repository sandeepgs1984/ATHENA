/*
  Minimal DOM stub for exercising DarvaX's tab.js in Node (DX-4b).

  Grepping tab.js's source would only prove the code *mentions* injection. This
  harness actually runs it, so the tests can assert real behaviour: that exactly
  one nav item and one panel get appended in the normal case, and that a missing
  ATHENA hook produces a single warning and nothing else — no throw into the
  host page.

  Usage:  node _tab_harness.js <path-to-tab.js> <full|degraded|deeplink>
  Emits a single JSON line describing what happened.
*/
"use strict";

const fs = require("fs");

const source = fs.readFileSync(process.argv[2], "utf8");
const mode = process.argv[3] || "full";

const warnings = [];
const appended = { nav: [], panes: [], head: [] };

function element(tag) {
  const classes = new Set();
  return {
    tagName: String(tag).toUpperCase(),
    id: "",
    href: "",
    title: "",
    innerHTML: "",
    textContent: "",
    _attrs: {},
    _children: [],
    get className() { return Array.from(classes).join(" "); },
    set className(value) {
      classes.clear();
      String(value).split(/\s+/).filter(Boolean).forEach((c) => classes.add(c));
    },
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      contains: (c) => classes.has(c),
    },
    setAttribute(key, value) { this._attrs[key] = String(value); },
    getAttribute(key) {
      if (key === "class") return this.className;
      return Object.prototype.hasOwnProperty.call(this._attrs, key)
        ? this._attrs[key]
        : null;
    },
    appendChild(child) { this._children.push(child); return child; },
    addEventListener() {},
    removeEventListener() {},
    remove() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    _hasClass: (c) => classes.has(c),
  };
}

// Containers the script is expected to find in a healthy dashboard.
const nav = element("nav");
nav.className = "sidebar-nav";
nav.appendChild = function (child) { appended.nav.push(child); return child; };

const paneHost = element("div");
const existingPane = element("div");
existingPane.className = "tab-pane active";
existingPane.id = "tab-overview";
existingPane.parentElement = paneHost;
paneHost.appendChild = function (child) { appended.panes.push(child); return child; };

const pageTitle = element("h1");
pageTitle.id = "page-title";

const head = element("head");
head.appendChild = function (child) { appended.head.push(child); return child; };

const degraded = mode === "degraded";

global.document = {
  readyState: "complete",
  head,
  body: element("body"),
  createElement: element,
  getElementById(id) {
    if (degraded) return null;
    if (id === "page-title") return pageTitle;
    return null; // panel not yet present, which is what the script expects
  },
  querySelector(selector) {
    if (degraded) return null;
    if (selector === "nav.sidebar-nav") return nav;
    if (selector === ".tab-pane") return existingPane;
    return null;
  },
  querySelectorAll(selector) {
    if (degraded) return [];
    if (selector === ".tab-pane") return [existingPane];
    if (selector === ".nav-item") {
      const other = element("a");
      other.className = "nav-item";
      other.setAttribute("data-tab", "overview");
      return [other];
    }
    return [];
  },
  addEventListener() {},
};

global.window = {
  location: {
    pathname: mode === "deeplink" ? "/dashboard/darvax" : "/dashboard/overview",
    search: "",
  },
  history: { pushState() {} },
  addEventListener() {},
  console: { warn: (message) => warnings.push(String(message)) },
};
global.console = { warn: (message) => warnings.push(String(message)) };

let threw = null;
try {
  // eslint-disable-next-line no-new-func
  new Function(source)();
} catch (err) {
  threw = String((err && err.message) || err);
}

const panel = appended.panes[0];
const frame = panel && panel._children[0];

process.stdout.write(
  JSON.stringify({
    threw,
    warnings,
    navAppended: appended.nav.length,
    panesAppended: appended.panes.length,
    styleAppended: appended.head.length,
    navDataTab: appended.nav[0] ? appended.nav[0].getAttribute("data-tab") : null,
    navIsNavItem: appended.nav[0] ? appended.nav[0]._hasClass("nav-item") : false,
    navLabel: appended.nav[0] ? appended.nav[0].innerHTML : null,
    panelId: panel ? panel.id : null,
    panelIsTabPane: panel ? panel._hasClass("tab-pane") : false,
    panelActive: panel ? panel._hasClass("active") : false,
    frameTag: frame ? frame.tagName : null,
    frameDataSrc: frame ? frame.getAttribute("data-src") : null,
    frameSrc: frame ? frame.getAttribute("src") : null,
    pageTitle: pageTitle.textContent,
  }) + "\n"
);
