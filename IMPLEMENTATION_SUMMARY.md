# ATHENA — Implementation Summary

Permanent implementation log. One section per completed phase, newest first,
in the 7-part format mandated by CLAUDE.md. Written before owner review;
status updated on approval.

---

## TP-4 — Intraday SOP surface (approved)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Give the owner a persistent, plain-language intraday operating guide that is reachable without selecting a symbol |
| Scope | Added a global-header `Intraday operating guide` icon; added a modal SOP surface covering before-market checks, work-queue review, before-entry checks, no-fill handling, after-entry stop/target handling, end-of-day handling, and manual broker boundaries; kept the guide non-symbol-specific and separate from the selected-symbol Trading Steps panel; reused existing modal helpers and close-all behavior; styled the guide as a compact operator manual; bumped dashboard cache-busters |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/index.html`, `src/athena/api/static/css/12-decision-cards-dag.css`, `src/athena/api/static/js/06-ui-helpers.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/06-ui-helpers.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 4 passed |
| Coverage | Dashboard hosting tests lock the SOP trigger/modal/close IDs, advisory-only copy, no-order/no-guarantee boundary, pre-open/live/no-fill/entry/exit/end-of-day sections, modal wiring, close-all integration, CSS shell, and `9.94.0` asset cache-busters |
| Architecture compliance | Static frontend guidance only. No provider, broker, order, scoring, confidence, risk, decision-policy, TradePlan value, schema, backend endpoint, or frozen domain contract changes |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS. ADR-005 preserved: the SOP explains how to use existing Decisions/TradePlans and does not fabricate signals, targets, exits, or recommendations |
| Risks discovered | Global guidance must not look like a broker workflow or promise a fixed outcome. The SOP should stay separate from sticky symbol detail content so it does not worsen the central-panel scroll experience |
| Technical debt introduced | None |
| Suggested improvements | Run a full visual QA pass on the complete intraday advisor workflow before treating the dashboard as day-to-day production advisory-ready |
| Remaining work | Full-suite validation after freeing disk space; any further TP work requires a new owner-approved milestone |
| Status | ✅ Approved (2026-07-30) — closes Intraday Advisor UX track |
| Branch | feature/live-dashboard |

---

## TP-3 — Top current setups (ready for review)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Give the owner a fast ranked review queue without mixing expired, stale, or no-plan rows into actionable setup discovery |
| Scope | Added a `Top Current Setups` section above the normal Decisions board groups; ranks up to 10 current setups using existing score, confidence, risk, expected-return, risk/reward, timestamp, and symbol data; admits only current-board TRADE rows with fresh or aging actionable TradePlans; excludes expired, stale, no-plan, historical, dismissed, and filtered-out rows; keeps normal Trade/Watch/No trade sections unchanged below; avoids double-counting the top section in visible-refresh outcome totals; adjusted duplicate active-row scrolling so selecting a setup does not jump between duplicated Top/Trade rows; compacted the left-list summary strip and moved explanatory board semantics into hover/title text; bumped dashboard cache-busters |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/index.html`, `src/athena/api/static/css/12-decision-cards-dag.css`, `src/athena/api/static/js/12-decisions-list.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/12-decisions-list.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 4 passed |
| Coverage | Dashboard hosting tests lock the top-10 limit, current/actionable/fresh-or-aging guardrails, ranking helper names, no expired/stale/no-plan admission path, section copy, duplicate active-row scroll handling, compact summary strip behavior, and `9.93.0` asset cache-busters |
| Architecture compliance | Frontend ranking/presentation only over already-rendered current Decisions data. No provider, broker, order, scoring, confidence, risk, decision-policy, TradePlan value, schema, or frozen domain contract changes |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS. ADR-005 preserved: the section reuses persisted Decision/TradePlan/freshness fields and does not invent new signals or alter recommendations |
| Risks discovered | A top section duplicates symbols already present under Trade, so selection scrolling must target the visible duplicate instead of scrolling both. The summary strip can materially reduce left-list scanability if it carries explanatory prose inline |
| Technical debt introduced | None |
| Suggested improvements | TP-4 should host the persistent intraday SOP/help surface outside the cramped left rail, with plain-language guidance for normal users |
| Remaining work | Owner review of TP-3; full-suite validation after freeing disk space |
| Status | 🔄 Ready for owner review |
| Branch | feature/live-dashboard |

---

## TP-2 — Current board controls (ready for review)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Let the owner refresh the current Decisions board without validating hidden historical rows |
| Scope | Added a left-rail `Re-validate visible` icon action; collected only on-screen current-board row symbols from the left list viewport; capped the quick action to the first 5 on-screen rows; reused the existing scoped validation workflow and dismissible validation overlay; added overlay elapsed timer and close control; refreshed the Decisions workspace after completion; added a result strip with validated count plus Trade/Watch/No trade/Excluded summary; cleared cooldown-only status messages when cooldown ends; added explicit failure copy using the backend error reason when available; added a proactive 60-second cooldown after every quick refresh; disabled the button during cooldown with an hourglass icon plus retry countdown tooltip/aria label; mapped Kite 429/rate-limit errors to plain action copy using the same cooldown; capped large validation symbol lists in the overlay/toast so visible-board batches stay readable; bumped dashboard cache-busters |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/index.html`, `src/athena/api/static/css/07-universe-modals.css`, `src/athena/api/static/css/12-decision-cards-dag.css`, `src/athena/api/static/js/09-market-intelligence.js`, `src/athena/api/static/js/12-decisions-list.js`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/09-market-intelligence.js` — passed; `rtk node --check src/athena/api/static/js/12-decisions-list.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 4 passed; `rtk git diff --check` — passed |
| Coverage | Dashboard hosting tests lock the button/status DOM, viewport-visible row collection, quick-action batch cap, proactive cooldown timer, disabled hourglass state, retry countdown tooltip, cooldown-only status cleanup, rate-limit cooldown copy, hidden-row skip guard, scoped validation reuse, workspace refresh, backend-error display, stale-on-failure fallback copy, result summary copy, status-strip tones, capped long validation overlay/toast copy, overlay elapsed timer, overlay close behavior, overlay viewport bounds, and `9.92.0` asset cache-busters |
| Architecture compliance | Frontend orchestration only. No provider, broker, order, scoring, confidence, risk, decision-policy, TradePlan value, schema, or frozen domain contract changes |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS. ADR-005 preserved: the control reuses existing persisted/current decision rows and the existing scoped validation endpoint rather than inventing signals or summaries |
| Risks discovered | The icon action must stay icon-only while the blocking overlay and status strip carry the progress text; putting validation text inside the 34px rail button would overflow. Large visible-board batches can contain 100+ symbols, so progress surfaces must summarize rather than print the entire symbol set. "Visible" must mean viewport-visible, not merely rendered inside the scroll container. Scoped validation is synchronous and can still take noticeable time, so the quick action must stay capped; larger refreshes need a dedicated/background flow. Users naturally repeat-tap refresh controls, so ATHENA must cool down proactively instead of waiting for Kite 429 |
| Technical debt introduced | None |
| Suggested improvements | TP-3 should add a ranked review queue above the normal groups, but only for current valid/aging TradePlans |
| Remaining work | Owner review of TP-2; full-suite validation after freeing disk space |
| Status | 🔄 Ready for owner review |
| Branch | feature/live-dashboard |

---

## TP-1 — Trade playbook foundation (ready for review)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Make the selected symbol's intraday manual-trading steps clear before the owner reads price levels |
| Scope | Added the Intraday Advisor UX roadmap; registered the TP track in `docs/MILESTONES.md`; moved symbol-specific Re-validate from the generic Decision Brief header into Advisor Status; added a plain-language Trading Steps panel before TradePlan levels; covered entry, stop, target, no-fill, end-of-day, and re-check rules; refreshed the playbook after authoritative plan-freshness data loads; added a scroll-aware compact cockpit so the sticky header frees reading space after the selected-symbol detail pane scrolls; bumped dashboard cache-busters |
| Files created | `docs/design/ATHENA-INTRADAY-ADVISOR-UX-ROADMAP.md` |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/index.html`, `src/athena/api/static/css/09-decision-brief-shell.css`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/js/14-decision-brief-analysis.js`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/14-decision-brief-analysis.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 4 passed |
| Coverage | Dashboard hosting tests lock the Advisor Status CTA location, removed header revalidate, Trading Steps renderer, playbook refresh after `/plan-freshness`, plain-language entry/no-fill/end-of-day rules, scroll-aware compact cockpit selectors/wiring, and `9.91.0` asset cache-busters |
| Architecture compliance | Presentation-only. No provider, broker, order, scoring, confidence, risk, decision-policy, TradePlan value, schema, or frozen domain contract changes |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS. ADR-005 preserved: the playbook renders guidance around existing Decision/TradePlan/freshness/session state and does not fabricate levels, signals, or rationale |
| Risks discovered | Trading instructions can become too technical if they mirror internal names. TP roadmap now requires normal-audience copy and avoids terms like pipeline, persisted artifact, validation cycle, and thesis in visible playbook/SOP text |
| Technical debt introduced | None |
| Suggested improvements | TP-2 should add current-board revalidation controls only after the selected-symbol playbook is owner-reviewed |
| Remaining work | Owner review of TP-1; full-suite validation after freeing disk space |
| Status | 🔄 Ready for owner review |
| Branch | feature/live-dashboard |

---

## AS-4 — Advisor status release gate (approved)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Lock the Advisor Status Layer into a safe release shape for live intraday use |
| Scope | Added a dedicated advisor-status release-gate regression test; hid expired historical TRADE decisions from the current Decisions board instead of treating them as restorable dismissals; added shared helpers for current-actionable versus historical TradePlans; made expired historical plans read as Not actionable / Plan not current / Historical TradePlan across cockpit, Quick Summary, eligibility, summary, and TradePlan presentation; surfaced scoped revalidation exclusions as no-current-TradePlan warnings; fixed expired duration copy to use `as_of - valid_until` rather than clamped remaining seconds |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/js/05-utils.js`, `src/athena/api/static/js/09-market-intelligence.js`, `src/athena/api/static/js/12-decisions-list.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/js/14-decision-brief-analysis.js`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/05-utils.js` — passed; `rtk node --check src/athena/api/static/js/09-market-intelligence.js` — passed; `rtk node --check src/athena/api/static/js/12-decisions-list.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/14-decision-brief-analysis.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py::test_advisor_status_release_gate -q` — 1 passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 4 passed |
| Coverage | AS-4 regression locks diagnostics privacy, reduced-motion static pulse behavior, expired/stale warning dominance over review-mode/valid copy, historical TradePlan removal from the current board, non-restorable handling for hidden historical rows, and detail-pane historical/not-actionable dominance |
| Architecture compliance | Presentation and test hardening only. No provider, broker, order, scoring, confidence, risk, decision-policy, TradePlan value, schema, or frozen domain contract changes |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS dashboard. ADR-005 preserved: the UI consumes persisted decisions, TradePlan freshness fields, selected quote/candle data, and latest validation detail; it does not fabricate signals, revalidation events, or new rationale |
| Risks discovered | A scoped revalidation can legitimately exclude a symbol after an older TRADE decision; without explicit presentation rules this looks like an active BUY. The left rail must remain a current action board, while audit/history preserves the old decision separately |
| Technical debt introduced | None |
| Suggested improvements | After local disk cleanup, rerun the full suite and consider a separate historical-decision browser/filter if the owner wants easy access to expired plans without polluting the current board |
| Remaining work | Full-suite validation after freeing disk space |
| Status | ✅ Approved (2026-07-30) — closes Advisor Status Layer track |
| Branch | feature/live-dashboard |

---

## AS-3 — Market closed review mode (implemented; validation blocked)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Make closed-market review mode explicit and show the next live session from ATHENA's calendar authority |
| Scope | Added a read-only dashboard session-status DTO and endpoint; computed current exchange phase and next live session from `CalendarEngine` plus configured NSE session times; wired the header advisor pulse to show market closed / next-live wording; added Decision Brief review-mode wording for selected plans when the market is closed; hardened owner-candidate list enrichment so optional repository context cannot block listing candidate symbols; bumped dashboard asset cache-busters |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/routers/dashboard.py`, `src/athena/api/v1/services/candidates_service.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/static/index.html`, `src/athena/api/static/js/00-state-and-dom.js`, `src/athena/api/static/js/03-app-shell.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `tests/api/v1/test_core_apis.py`, `tests/api/platform/test_dashboard_hosting.py`, `tests/api/platform/test_decision_chart_release_gate.py` |
| Public APIs added | `GET /api/v1/dashboard/session-status` returning exchange, timezone, current session phase, open/close timestamps, next live timestamps, and a display-safe message |
| Tests | `rtk python3 -m py_compile src/athena/api/v1/services/candidates_service.py src/athena/api/v1/dtos/dashboard.py src/athena/api/v1/services/dashboard_service.py src/athena/api/v1/routers/dashboard.py src/athena/api/v1/dtos/__init__.py` — passed; `rtk node --check src/athena/api/static/js/00-state-and-dom.js` — passed; `rtk node --check src/athena/api/static/js/03-app-shell.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk pytest tests/api/v1/test_saved_symbols.py::TestSavedSymbolsAPI::test_saved_symbols_independent_of_owner_candidates tests/api/v1/test_owner_candidates.py::TestOwnerCandidatesAPI::test_crud_normalize_and_list -q` — 2 passed; `rtk pytest tests/api/v1/test_core_apis.py::TestDashboardAPI tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py -q` — 10 passed; `rtk git diff --check` — passed; `rtk pytest -q` blocked by local disk capacity (`df -h`: only ~115 MiB free; `db/` is ~9.8 GiB), producing unrelated SQLite `disk I/O error` failures |
| Coverage | API test locks open and closed NSE session behavior with deterministic `as_of`; dashboard-hosting tests lock the endpoint wiring, review-mode copy, session state, and `9.89.0` static asset cache-busters |
| Architecture compliance | Additive read-only dashboard API plus static dashboard rendering. Candidate-list fallback only degrades optional UI enrichment when repository context is unavailable. No provider, broker, scoring, risk, decision-policy, TradePlan, analytical schema, or frozen domain contract changes |
| ADR compliance | ADR-004 preserved: dashboard remains static HTML/CSS/vanilla JS. ADR-005 preserved: market session status is sourced from `CalendarEngine` and config, not reconstructed from browser assumptions |
| Risks discovered | Session-status search is bounded to configured calendar coverage; if future-year calendar files are missing, the endpoint reports no next live session instead of guessing. Validation exposed that optional owner-candidate enrichment could 503 candidate listing when the live SQLite repo was unhealthy; AS-3 hardens that display path to return base candidate rows. Final full-suite validation needs local disk cleanup before it can be trusted |
| Technical debt introduced | None |
| Suggested improvements | AS-4 should add release-gate coverage for diagnostics privacy, actionability dominance, session-status review mode, and reduced-motion/readability regressions |
| Remaining work | Free local disk space, rerun full suite, then owner review of AS-3; AS-4 remains planned |
| Status | ⚠️ Implemented; full-suite validation blocked |
| Branch | feature/live-dashboard |

---

## AS-2 — Freshness propagation (approved)

| | |
|---|---|
| Completed | 2026-07-30 |
| Objective | Surface TradePlan freshness before and during brief review so expired/stale setups are visible earlier |
| Scope | Added shared dashboard freshness helpers; added compact TradePlan freshness chips to Decisions symbol rows; added a `Plan Status` row to Quick Summary; refreshed Quick Summary after the selected `/plan-freshness` DTO loads; bumped dashboard asset cache-busters |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/index.html`, `src/athena/api/static/js/05-utils.js`, `src/athena/api/static/js/12-decisions-list.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/js/14-decision-brief-analysis.js`, `src/athena/api/static/css/12-decision-cards-dag.css`, `src/athena/api/static/css/13-context-history.css`, `tests/api/platform/test_dashboard_hosting.py`, `tests/api/platform/test_decision_chart_release_gate.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/05-utils.js` — passed; `rtk node --check src/athena/api/static/js/12-decisions-list.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/14-decision-brief-analysis.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py -q` — 8 passed; `rtk git diff --check` — passed; `rtk pytest -q` — 1123 passed |
| Coverage | Hosting tests lock in the shared freshness helpers, configured freshness fractions, left-list freshness chips, Quick Summary `Plan Status`, selected DTO refresh, and `9.88.0` static asset cache-busters |
| Architecture compliance | Presentation-only. No backend, provider, broker, scoring, risk, decision-policy, frozen domain, or schema changes. Symbol-row freshness uses persisted TradePlan validity fields; the selected brief remains authoritative via the existing freshness DTO |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS. ADR-005 preserved: every displayed value comes from persisted TradePlan fields or the existing `/plan-freshness` explainability DTO; no new analytical rationale is reconstructed |
| Risks discovered | The static frontend mirrors the configured warn/stale fractions (`0.5` / `0.8`) for pre-open list hints; a future config change should update both the backend config and the dashboard mirror in one reviewed change |
| Technical debt introduced | None |
| Suggested improvements | AS-3 should replace generic market-ready wording with a true market-closed / next-session message sourced from ATHENA's calendar/session authority |
| Remaining work | AS-3 completed for review; AS-4 remains planned |
| Status | ✅ Approved (2026-07-30) |
| Branch | feature/live-dashboard |

---

## AS-1 — Header pulse and actionability foundation (approved)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Shift Decisions & Trace from visible engineering diagnostics toward a safer intraday advisor surface |
| Scope | Added the Advisor Status Layer track; replaced always-visible `REQ-ID` / `CORR-ID` / latency with a header advisor pulse plus diagnostics popover; added latency severity coloring inside diagnostics; added a selected-symbol Advisor Status banner that warns when a TradePlan is expired/stale and tells the owner to re-validate before considering manual action; tightened the screenshot-reviewed header/pulse/banner layout so it does not duplicate ticker data or read like loose body copy; wired TradePlan freshness DTO updates into the banner/pulse; bumped dashboard asset cache-busters |
| Files created | None |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`, `src/athena/api/static/index.html`, `src/athena/api/static/js/00-state-and-dom.js`, `src/athena/api/static/js/02-kite-gate.js`, `src/athena/api/static/js/03-app-shell.js`, `src/athena/api/static/js/04-api-client.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/js/14-decision-brief-analysis.js`, `src/athena/api/static/css/03-shell.css`, `src/athena/api/static/css/09-decision-brief-shell.css`, `tests/api/platform/test_dashboard_hosting.py`, `tests/api/platform/test_decision_chart_release_gate.py` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/00-state-and-dom.js` — passed; `rtk node --check src/athena/api/static/js/02-kite-gate.js` — passed; `rtk node --check src/athena/api/static/js/03-app-shell.js` — passed; `rtk node --check src/athena/api/static/js/04-api-client.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/14-decision-brief-analysis.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py -q` — 8 passed; `rtk git diff --check` — passed; `rtk pytest -q` — 1123 passed |
| Coverage | Hosting tests lock in the advisor pulse, diagnostics popover, actionability banner, expired-plan warning copy, release-gated `9.87.0` cache-busters, and the existing chart release gate |
| Architecture compliance | Presentation-only. No backend, provider, broker, scoring, risk, decision-policy, frozen domain, or schema changes. The banner does not alter ATHENA's recommendation; it only adds actionability wording over existing selected decision and TradePlan freshness data |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS. ADR-005 preserved: actionability wording consumes existing TradePlan/freshness fields and does not invent a next market session or new analytical rationale |
| Risks discovered | The owner-requested “market closed · next live date” message needs a real calendar/session payload; AS-1 deliberately defers that to AS-3 rather than guessing from browser time. Left-list and Quick Summary freshness propagation remain separate reviewable work in AS-2 |
| Technical debt introduced | None |
| Suggested improvements | AS-2 should surface plan validity directly in Quick Summary and symbol rows so expired setups are visible before opening each brief |
| Remaining work | AS-2 completed for review; AS-3/AS-4 remain planned |
| Status | ✅ Approved (2026-07-30) |
| Branch | feature/live-dashboard |

---

## CH-6 — Chart resilience and release gate (ready for owner review)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Harden the symbol chart before treating it as a trusted trading decision surface |
| Scope | Added chart release-gate regressions for nonblank SVG/DOM contracts, no-data and unavailable fallback states, stable tap/keyboard interaction wiring, no-scroll modal layout, compact viewport sizing, persisted-only event markers, and max 500-candle rendering budget contracts; hardened the dedicated chart modal to avoid internal vertical scrolling in fullscreen presentation |
| Files created | `tests/api/platform/test_decision_chart_release_gate.py` |
| Files modified | `src/athena/api/static/css/08-strategies-backtest.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py`, `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/16-decision-brief-chart.js` — passed; `rtk node --check src/athena/api/static/js/19-decision-brief-history.js` — passed; `rtk pytest tests/api/platform/test_decision_chart_release_gate.py tests/api/platform/test_dashboard_hosting.py -q` — 8 passed; `rtk git diff HEAD --check` — passed; `rtk pytest -q` — 1123 passed |
| Coverage | New release-gate test suite locks in nonblank chart rendering strings, empty/unavailable states, hit-area coordinate regression, pointer/tap fallback, bounded keyboard focus, modal overflow suppression, compact 96vw/88vh modal sizing, persisted-only marker sources, absence of marker placeholders/revalidation inference, and `9.86.0` asset cache-busters |
| Architecture compliance | No backend, provider, broker, scoring, risk, or domain contract changes. CH-6 adds tests and layout hardening only |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS only. ADR-005 preserved: tests enforce persisted-only marker sources and no fabricated placeholders |
| Risks discovered | Live authenticated visual QA remains owner-side because the workstation is behind the owner unlock gate; automated static release-gate tests now cover the no-scroll, no-blank, fallback, and interaction contracts that previously regressed |
| Technical debt introduced | None |
| Suggested improvements | If future chart work needs real revalidation markers, add a persisted read-only event source under owner review rather than deriving timestamps in the frontend |
| Remaining work | Owner review of CH-6; chart track can close after approval |
| Status | 🔄 Ready for owner review |
| Branch | feature/live-dashboard |

---

## CH-5 — Decision and event chart markers (approved)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Connect price action with ATHENA's persisted decision timeline without manufacturing signals |
| Scope | Added chart event markers for selected decision timestamp, owner journal response timestamp, and realized outcome close timestamp when those persisted records exist and fall on or near the rendered candle window; omitted markers for unavailable or out-of-window records; refreshed chart markers when journal/outcome data loads or changes |
| Files created | None |
| Files modified | `src/athena/api/static/js/16-decision-brief-chart.js`, `src/athena/api/static/js/19-decision-brief-history.js`, `src/athena/api/static/css/10-trade-plan-chart.css`, `src/athena/api/static/css/08-strategies-backtest.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py`, `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/16-decision-brief-chart.js` — passed; `rtk node --check src/athena/api/static/js/19-decision-brief-history.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 3 passed; `rtk git diff HEAD --check` — passed; `rtk pytest -q` — 1118 passed |
| Coverage | Static hosting regression locks in persisted event source functions, nearest-candle timestamp mapping, event marker classes, journal/outcome marker refresh, modal viewport sizing, and asset cache-busters through `9.86.0` |
| Architecture compliance | No backend, provider, broker, scoring, risk, or domain contract changes. CH-5 consumes only existing selected-decision, journal, outcome, and candle payload/state |
| ADR compliance | ADR-005 preserved: markers are created only from persisted record timestamps; no placeholder revalidation markers were added because the existing payload does not expose a distinct persisted revalidation timestamp |
| Risks discovered | Revalidation markers require an additive read-only persisted event source or DTO field in a future owner-reviewed milestone/ADR path; this milestone deliberately skips them rather than inferring them |
| Technical debt introduced | None |
| Suggested improvements | CH-6 should browser-verify normal/modal marker visibility and no-data/stale states across desktop and compact widths |
| Remaining work | None; CH-6 implemented after approval |
| Status | ✅ Approved by owner on 2026-07-29 |
| Branch | feature/live-dashboard |

---

## CH-4 — Interactive chart inspection (approved)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Make the Decision Brief chart precise enough for candle-by-candle decision review without adding new chart-derived signals |
| Scope | Added a persistent chart inspector row, pointer crosshair, OHLCV readout, SMA/ATR readout with unavailable handling for missing warmup values, TradePlan level readout, latest-candle reset affordance, stable pointer/tap and keyboard inspection controls for embedded and dedicated chart contexts, and enlarged the dedicated chart modal to roughly 80% of the viewport |
| Files created | None |
| Files modified | `src/athena/api/static/js/16-decision-brief-chart.js`, `src/athena/api/static/css/10-trade-plan-chart.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py`, `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/16-decision-brief-chart.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 3 passed; `rtk git diff HEAD --check` — passed; `rtk pytest -q` — 1118 passed |
| Coverage | Static hosting regression locks in the inspector helper functions, pointer inspection, delegated hit-area coordinate math, crosshair elements, reset control, keyboard arrow handling, unavailable indicator wording, dedicated modal viewport sizing, and asset cache-busters through `9.84.0` |
| Architecture compliance | No backend, provider, broker, scoring, risk, or domain contract changes. CH-4 reads only candle, indicator, and selected TradePlan values already present in the existing chart payload/state |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS only. ADR-005 preserved: missing indicator values render as `Unavailable`, never zero or inferred values |
| Risks discovered | Initial CH-4 pointer inspection used delegated document event coordinates instead of the SVG hit-area rectangle, which broke tap selection and made keyboard state inconsistent; fixed by mapping coordinates from the actual hit area and keeping focus on the chart shell. Authenticated visual inspection remains owner-side because the running workstation is behind the owner unlock gate; static regression and syntax checks cover the shipped shell and interaction wiring |
| Technical debt introduced | None |
| Suggested improvements | CH-5 should add decision/event markers only from persisted decision/revalidation/journal/outcome records, with an ADR if existing payloads are insufficient |
| Remaining work | None; CH-5 implemented after approval |
| Status | ✅ Approved by owner on 2026-07-29 |
| Branch | feature/live-dashboard |

---

## CH-3 — Timeframe, range, and session controls (ready for owner review)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Let the owner inspect a selected symbol across existing intraday resolutions and bar windows without leaving the Decision Brief |
| Scope | Added configured 5m/15m timeframe controls in embedded and dedicated chart contexts, enabled 15m live ingestion alongside existing 5m ingestion, added 60/120/300/500 bar-range controls, `localStorage` preference persistence, dynamic candles query construction, requested-vs-returned bar count labels, timeframe-specific no-data wording, a detail-pane fullscreen trigger, title/meta updates for selected timeframe and latest candle timestamp, and IST day/session separators when returned candles cross sessions |
| Files created | None |
| Files modified | `src/athena/api/static/js/16-decision-brief-chart.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/css/10-trade-plan-chart.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py`, `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/16-decision-brief-chart.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 3 passed; `rtk git diff HEAD --check` — passed; `rtk pytest -q` — 1118 passed |
| Coverage | Static hosting regression locks in configured 5m/15m timeframe controls, absence of unsupported 1m chart controls, range sets, preference key, dynamic query construction, embedded/modal control markup, fullscreen trigger, range-shortage label, timeframe-specific empty-state wording, session separator rendering, latest-candle wording, and `9.79.0` asset cache-busters |
| Architecture compliance | No backend, provider, broker, scoring, risk, or domain contract changes. CH-3 uses only the existing candles endpoint's supported `timeframe` and `limit` query parameters |
| ADR compliance | ADR-004 preserved: static HTML/CSS/vanilla JS only. ADR-005 preserved: all chart values remain rendered from returned candle/quote/TradePlan/freshness data; session separators are derived only from candle timestamps |
| Risks discovered | Local SQLite verification showed `NSE:TATACAP` currently has 56 persisted `5m` candles, 62 daily candles, and no persisted `15m` candles yet; 15m will populate after the next live ingestion cycle with the updated config. The active provider does not declare 1m capability, so unsupported 1m controls were removed. Range controls cannot display more bars than the ledger contains. Authenticated click-through visual verification remains owner-side because the running workstation is behind the owner unlock gate; TestClient verification confirmed the updated shell asset versions |
| Technical debt introduced | None |
| Suggested improvements | CH-4 should add crosshair/inspection behavior with OHLCV and rendered indicator readouts without adding new data sources |
| Remaining work | None; CH-4 implemented after approval |
| Status | ✅ Approved by owner on 2026-07-29 |
| Branch | feature/live-dashboard |

---

## CH-2 — TradePlan overlays & validity layer (approved)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Make ATHENA's TradePlan levels and validity state legible directly in the Decision Brief chart without adding new trading logic |
| Scope | Added chart-level TradePlan strip with entry, stop, T1, risk/reward, and expiry/freshness chips; added stop/target percentage deltas to SVG plan-line labels; re-rendered the chart after `/plan-freshness` returns so the chart validity chip uses the same DTO as the TradePlan card; fixed the price marker to use the same quote/LTP source as the header when available while still labeling the latest candle close separately; bumped dashboard CSS/JS asset versions |
| Files created | None |
| Files modified | `src/athena/api/static/js/16-decision-brief-chart.js`, `src/athena/api/static/js/14-decision-brief-analysis.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/js/11-decision-state.js`, `src/athena/api/static/css/10-trade-plan-chart.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py`, `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | `rtk node --check src/athena/api/static/js/11-decision-state.js` — passed; `rtk node --check src/athena/api/static/js/13-decision-brief-core.js` — passed; `rtk node --check src/athena/api/static/js/16-decision-brief-chart.js` — passed; `rtk node --check src/athena/api/static/js/14-decision-brief-analysis.js` — passed; `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 3 passed; `rtk git diff HEAD --check` — passed; `rtk pytest -q` — 1118 passed |
| Coverage | Static hosting regression now locks in chart-level plan delta calculations, plan strip rendering, validity chip classes, refresh-on-plan-freshness, quote-vs-candle price labeling, legend explanation, and `9.76.0` asset cache-busters |
| Architecture compliance | No backend, provider, broker, scoring, risk, or domain contract changes. The chart still renders only existing candles, indicators, selected decision TradePlan values, and the existing plan-freshness DTO |
| ADR compliance | ADR-005 preserved: stop/target percentages are pure arithmetic over persisted entry/level values and direction; expiry/freshness comes from the existing read-only DTO when available and otherwise degrades to plan timestamps |
| Risks discovered | Header price and chart marker previously used different real data sources: the header showed quote/LTP while the chart marker showed latest persisted candle close. Fixed by using the quote for the chart marker when available and labeling candle close separately. Authenticated visual review remains owner-side because the running workstation is protected by the owner unlock gate |
| Technical debt introduced | None |
| Suggested improvements | CH-3 should add timeframe/range/session controls, still using the existing candles endpoint and visible selected timeframe/last-candle timestamps |
| Remaining work | None; CH-3 implemented after approval |
| Status | ✅ Approved by owner on 2026-07-29 |
| Branch | feature/live-dashboard |

---

## CH-1 — Professional chart foundation (ready for owner review)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Improve the Decision Brief symbol chart foundation while preserving ATHENA's existing read-only candle and TradePlan data boundaries |
| Scope | Reworked the chart renderer into a reusable `DecisionChartController`; added a professional chart shell with distinct price and volume panels, richer axis/grid treatment, latest-price marker, high/low topline, and shared normal/modal rendering; bumped dashboard CSS/JS asset versions |
| Files created | None |
| Files modified | `src/athena/api/static/js/16-decision-brief-chart.js`, `src/athena/api/static/css/10-trade-plan-chart.css`, `src/athena/api/static/css/08-strategies-backtest.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py`, `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | `rtk pytest tests/api/platform/test_dashboard_hosting.py -q` — 3 passed; `rtk node --check src/athena/api/static/js/16-decision-brief-chart.js` — passed; `rtk git diff HEAD --check` — passed; `rtk pytest -q` — 1118 passed |
| Coverage | Static hosting regression now locks in the chart controller boundary, professional renderer, price/volume panels, latest-price marker, and aligned asset cache-busters |
| Architecture compliance | No backend, provider, broker, scoring, risk, or domain contract changes. Chart still consumes the existing candles endpoint and selected decision TradePlan data only |
| ADR compliance | ADR-004: remains static HTML/CSS/vanilla JS; no new library/dependency was added in CH-1. ADR-005: no fabricated overlays; existing candle, SMA/ATR, and TradePlan values remain the only rendered data sources |
| Risks discovered | Live visual chart inspection is blocked by the configured owner unlock gate without credentials; browser verification confirmed served asset versions and no pre-unlock console errors, while full authenticated chart review remains an owner-side review task |
| Technical debt introduced | None |
| Suggested improvements | CH-2 should move the existing plan overlays into clearer chart-level affordances for validity, stop/target deltas, and risk/reward without changing data sources |
| Remaining work | Owner review of CH-1; CH-2 blocked until approval |
| Status | ✅ Approved by owner on 2026-07-29 |
| Branch | feature/live-dashboard |

---

## CH-0 — Symbol Chart Excellence roadmap (ready for owner review)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Convert the owner request for world-class symbol chart presentation into a staged, review-gated implementation plan suitable for a money-sensitive decision surface |
| Scope | Documentation-only design milestone: current chart audit, governing constraints, target experience, CH-1 through CH-6 milestone sequence, explicit risk controls |
| Files created | `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md` |
| Files modified | `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md` |
| Public APIs added | None |
| Tests | Not run — documentation-only milestone. `rtk git diff --check` passed |
| Coverage | Not applicable |
| Architecture compliance | No architecture change. Roadmap keeps chart work inside the existing read-only dashboard/reporting boundary and does not alter scoring, risk, provider, broker, or domain contracts |
| ADR compliance | ADR-004 permits the static HTML/vanilla JS/Lightweight Charts surface; ADR-005 is carried forward as the rule that every chart overlay must come from persisted or explicitly returned data |
| Risks discovered | Chart polish can create false confidence if unsupported overlays are introduced; the roadmap blocks AI-drawn trendlines, invented support/resistance, hidden strategy annotations, and any order-placement behavior |
| Technical debt introduced | None |
| Suggested improvements | Owner should approve the chart-library dependency approach before CH-1: vendored static asset with documented source/version, or CDN with graceful unavailable-library handling |
| Remaining work | CH-1 Professional chart foundation after owner approval of CH-0 |
| Status | ✅ Approved by owner on 2026-07-29 |
| Branch | feature/live-dashboard |

---

## Fix pass: scoped re-validate inflated risk — two root causes (owner-reported, APPROVED)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Owner-reported: risk value showed as ~31.3 for most symbols in the decision list, and changed on re-validate (e.g. INFY → 42.8, ZENSARTECH → 38.8 vs its full-cycle 31.3). Audit + fix. Took 3 rounds: an initial fix, a follow-up when the owner reported it still broken after restart, and a second, deeper bug found while diagnosing the follow-up. |
| Scope | `src/athena/ops/owner_validation.py`, `tests/ops/test_owner_validation.py` |
| Public APIs added | None |
| Tests | 5 new regression tests across the 3 rounds. Full suite **1112 passed** |
| Coverage | Verified against real production `db/athena.db` after every round, including a final check with both fixes together: a full cycle and a scoped re-validate now produce identical values across all 6 risk dimensions (38.75 overall, both) |
| Architecture compliance | No architecture change — corrective wiring/resolution logic inside the already-frozen `OwnerValidationPipeline`/`RiskEngine` contract |
| ADR compliance | ADR-005: never fabricate — concentration is honestly `UNKNOWN` when no real full-cycle breadth exists yet; the regime benchmark index resolves to real configured index candles or is honestly absent, never another instrument's own candles standing in for it |
| Risks discovered | The kind of two-round miss here (a fix that works in a direct-call test but never fires against the real orchestrator's nested persistence shape) is worth remembering when testing any code that reads back its own previously-persisted `runs.detail_json` — the real caller may wrap it differently than a test calling the pipeline directly |
| Technical debt introduced | None — removed a near-duplicate copy of index-resolution logic between `_scan_eligible` and `_maybe_regime` |
| Suggested improvements | None beyond what's already tracked |
| Remaining work | None |
| Status | **✅ Fixed** (2026-07-29) |
| Branch | feature/live-dashboard |

### Root cause 1 (initial report): concentration_indicator distorted by scan scope

4 of the Risk Engine's 6 dimensions are inherently market-wide (identical for every symbol in one cycle by design) — only `liquidity_risk` genuinely varies per symbol. Separately, a real bug: a `symbols_filter`-scoped run (single-symbol Re-validate) narrows the universe scan to just that one instrument, so `concentration_indicator`'s "eligible instrument count" collapsed to 1, always tripping `concentrated_risk` (70, HIGH). Fix: `_last_full_universe_summary()` reuses the last real full-cycle's universe breadth for a scoped run instead of its own narrow scope.

### Root cause 1, follow-up: the fix never fired in production

`_last_full_universe_summary()` checked the top-level `detail_json`, but `DryRunCycleOrchestrator.run_cycle()` (the real code path behind both the scheduled cycle and "Run Full Validation") persists the pipeline's own dict nested under a `"pipeline"` key. Every real run's marker lived at `detail["pipeline"]["universe_scope"]`, never found by the original check — concentration stayed `UNKNOWN` in production even though the direct-call test passed. Fixed to check the nested shape first, flat as a fallback for direct callers.

### Root cause 2 (found while diagnosing the follow-up): index resolution used a random stock's own candles

Comparing a full cycle against a ZENSARTECH re-validate dimension-by-dimension (after root cause 1's fix) showed every dimension identical **except** `gap_risk` (20 vs 70). Traced to `index_id = next(iter(snapshot.indices.keys()))`: `MarketSnapshot.indices` keys are bare labels (`"NIFTY 50"`), while the `candles` table stores the full instrument_id (`"NSE:NIFTY 50"`) — so the DB lookup for index candles always returned zero rows, and the code fell through to `candles_by_id.get(included_ids[0], ())`, using **whichever stock happened to be first in that particular scan's own scope** as a stand-in for "the market index." A full 362-symbol cycle and a single-symbol re-validate pick a different "first" stock, so this silently fabricated a different market regime reading each time. Confirmed directly: one run's "index candles" were priced around ₹1,130, another's around ₹530 — neither is NIFTY 50 (~24,000).

Fix: new `_resolve_index_candles()`, shared by `_scan_eligible` and `_maybe_regime` (removing a near-duplicate copy of the same resolution logic), always tries the configured index instruments in order via the repo, requiring genuine candle history before accepting one — never substitutes an unrelated instrument's candles, honestly empty when no index data exists at all.

---

## SD-4 — Continuous scoring ramps (approved, 2026-07-29)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Replace coarse RSI / liquidity / ADX step functions with anchor-preserving linear ramps so per-symbol scores stop collapsing into a handful of identical buckets |
| Scope | `_linear_ramp` helper; continuous `_momentum`, `_liquidity`, ADX bonus inside `_trend`. New config: `adx.weak` (15.0), `liquidity.low_volume_floor_ratio` (0.5). RSI `mid_points` now validated as the honest mid-band ramp anchor. `technical_structure` left discrete (deferred — needs a normalizing band with no existing anchor) |
| Files modified | `src/athena/scoring/engine.py`, `src/athena/config/models.py`, `config/scoring.json`, `tests/decision/test_scoring.py` |
| Public APIs added | None (scoring behaviour change only; same `ScoringResult` contract) |

### Behaviour

| Component | Formula | Preserved anchors |
|---|---|---|
| momentum | linear RSI `weak→strong` → `weak_points→strong_points` | RSI 40→20, 50→50, 60→80 |
| liquidity | linear Volume MA `0.5×min→min` → `low_points→ok_points` | 250k→30, 500k→70 |
| ADX bonus | linear ADX `weak→strong` → `0→bonus` | ADX 15→0, 25→+10 |

Replay against the live 363-symbol book (pre-implementation model): distinct
composites 21 → 248; 34 symbols (9.4%) change TRADE/WATCH/NO_TRADE band,
correctly in both tails (e.g. NTPC RSI 40.02 drops out of TRADE; APLAPOLLO
0.5% under the volume floor rises from cliff-penalty to near-full liquidity).

### Tests added (6)

Anchor equivalence at every configured endpoint (including below/above band
clamps); mid-band ramp points for RSI 55 → 65 and ADX 20 → +5; near-floor
liquidity no longer cliffs. Full suite **1107 passed**, ruff clean on touched files.

### Remaining work

Existing decisions still carry pre-ramp scores — use "Clear all" + fresh
validation for a clean book, same migration path as SD-1. SD-2/SD-3
(sector_quality) remain blocked on the sector-health data decision.
Thresholds may need a final review once sector lands.

| Status | ✅ Completed / approved (2026-07-29) |

---

## SD-1 — Risk Engine: wire calendar context + universe result (owner-reported, 2026-07-29)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Activate `event_risk` and `concentration_indicator`, which had been permanently UNKNOWN on every decision ATHENA has ever produced |
| Root cause | `RiskEngine.assess()` accepts `calendar_context` and `universe`, but `OwnerValidationPipeline` never passed either. Both objects already existed in `run()` (the `CalendarEngine` at line 104, the `UniverseResult` at line 148) — they were simply out of scope inside `_scan_eligible()`, so risk was a weighted mean over 4 of 6 dimensions (completeness 0.75) for every symbol |
| Scope | `run()` now computes `calendar.context_for(as_of.date())` and threads it plus the universe result into `_scan_eligible()` → `risk_stage` → `RiskEngine.assess()`. Recalibrated `config/decision.json` `max_risk_for_trade` 60 → 50 (see below). No API, DTO, domain, or schema change |
| Files modified | `src/athena/ops/owner_validation.py` (+11 lines), `config/decision.json` (1 value), `tests/ops/test_owner_validation.py`, `tests/api/v1/test_core_apis.py` |
| Public APIs added | None |

### Threshold recalibration — why it shipped in the same change set

Risk is a weighted mean over *known* dimensions, so a 75-of-100 divisor
inflated every risk score. Completing the vector adds two genuinely
low-risk inputs (`event_risk` 20 on a normal day, `concentration_indicator`
30 for a diversified universe) and mechanically deflates the result:
liquid names move 45.67 → 40.25, illiquid names 61.67 → 52.25.

`max_risk_for_trade: 60` had therefore been implicitly calibrated against
the broken 4-dimension scale. Shipping the wiring alone would have
silently *loosened* the trade gate, flipping 6 symbols WATCH → TRADE
(AIIL, APLAPOLLO, CREDITACC, JSL, LALPATHLAB, MANKIND) — every one a name
whose volume sits just under the 500k liquidity floor. Owner chose the
strictness-preserving recalibration to 50.

### Verification

A simulator of the risk and decision logic was validated against the live
`db/athena.db` batch run of 363 decisions and reproduced every persisted
risk value and the exact 153 TRADE / 173 WATCH / 37 NO_TRADE split with
**0 mismatches**. Against that validated baseline, SD-1 plus
`max_risk_for_trade: 50` produces **0 per-symbol decision drift** across
all three calendar scenarios (normal day, expiry session, scheduled
events). One earlier simulation run was discarded as unsound: it keyed
off the persisted `trade_plan` field, which is null for every non-TRADE
decision by construction and therefore structurally concealed WATCH →
TRADE flips.

### Tests added (1 new, 1 updated)

`test_risk_scores_every_dimension_from_calendar_and_universe` asserts both
dimensions report `OK` with non-empty contributions, and that risk
completeness exceeds the old 0.75. It further asserts the calendar
contribution references the run's own trading date and the concentration
contribution reports the run's actual universe size, so passing
placeholder objects would not satisfy it. `test_counterfactual_quantifies_
confidence_and_risk_gap` updated for the new threshold (risk gap 65−50).
Full suite **1101 passed**, ruff clean.

### Remaining work / risks

`volatility_risk` still reports UNKNOWN under synthetic linear-price test
fixtures (a property of the fixture, not the wiring — production data
yields a real value). SD-1 adds **no per-symbol differentiation**: both
newly-activated dimensions are date-wide or universe-wide, so they raise
honesty and completeness only. The scoped re-validate inconsistency is
closed by the approved fix pass above. Remaining symbol differentiation
work is SD-3 sector quality after SD-2 selects a real data path.

| Status | ✅ Completed / approved (2026-07-29) |

---

## Decisions & Trace — header live price (owner request, 2026-07-29)

| | |
|---|---|
| Completed | 2026-07-29 |
| Objective | Show the selected symbol's current market price in the Decision Brief header, auto-refreshed every 10s, without heavy load |
| Scope | `GET /api/v1/market/instruments/{id}/quote`; lightweight Kite `/quote` (no instruments CSV); persisted-quote fallback; 10s client poll scoped to Decisions tab + visible document |
| Public APIs added | `InstrumentQuoteDTO`; `MarketHistoryService.instrument_quote`; `GET .../quote` |
| Tests | Service unit (live preferred / persisted fallback / empty) + auth endpoint + dashboard hosting markers. Full suite green |
| Architecture compliance | ADR-005: null fields when unavailable; never fabricate 0. Single-id `/quote` only — no catalog download per tick. Server 5s coalescing cache. Client in-flight guard + visibility/tab stop |
| Status | ✅ Built (owner request; not a numbered milestone) |
| Branch | feature/live-dashboard |

---

## MH-3 — Market Summary API + mock-faithful UI (APPROVED)

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | Expose persisted F-5 score / universe breadth / sparklines via a dedicated summary read model and render them honestly on Market Intelligence |
| Scope | `GET /api/v1/market/summary` + DTOs; `MarketSummaryService`; mock-aligned 8-cell hero with real NIFTY/VIX sparklines, universe-breadth ring, categorical indicators, and F-5 score ring |
| Public APIs added | `MarketSummaryDTO` (+ nested); `MarketSummaryService.market_summary()`; `GET /api/v1/market/summary` |
| Tests | `tests/api/v1/test_market_summary.py` + dashboard hosting MH-3 assertions. Full suite **1095 passed** |
| Coverage | Unit: empty → Unavailable; score+breadth+sparklines from seeded run detail; partial score null with reason. Hosting: summary fetch + ring/breadth/sparkline markup |
| Architecture compliance | F-5 §8; ADR-005 honesty (null ≠ 0); no client-side score reconstruction; label “Universe breadth” |
| ADR compliance | Consumes MH-1/MH-2 persisted artifacts only; no new providers |
| Risks discovered | Score often Unavailable until institutional + coverage + gap window are complete — UI caption surfaces `unavailable_reason` |
| Technical debt introduced | None intentional. Recent Activity still uses `/pipelines/runs` (acceptable; summary is separate) |
| Suggested improvements | Optional ticker chip when score present; collapse categorical Health into tooltip when score is live |
| Remaining work | None — Market Metrics Completion track closed on MH-3 approval |
| Status | ✅ Approved (2026-07-28) |
| Branch | feature/live-dashboard |
| Track outcome | Market Metrics Completion (MH-0…MH-3) closed |

### Scope completed

- Dedicated summary read model reads latest completed validation run’s `market_health_score`, `market_metric_inputs`, `regime_assessment`, plus D1 closes for sparklines and snapshot VIX.
- Market Summary UI: one mock-aligned 8-cell band (Regime, Volatility, Gap, Breadth, Momentum, Trend Quality, Volatility Quality, Market Health), with real persisted values or explicit Unavailable states.
- NIFTY and VIX daily-close sparklines live inside their relevant cells; breadth uses real ADV/DEC/NEU and advance %, while Market Health uses only persisted F-5 total.
- Repeated enum words are removed only at display time (`NORMAL_VOLATILITY` → `NORMAL`, `HEALTHY_MOMENTUM` → `HEALTHY`); categorical labels remain unchanged in data/evidence.
- Evidence Attribution is a compact read-only footer; the reference chevron was omitted because there is no hidden evidence body to disclose.
- Final visual pass places the title/timestamp on one line, gives all eight cells shared label/value/indicator rows, strengthens primary-value hierarchy, and left-aligns the Market Health ring with the same geometry as the other cells.
- Post-approval Universe polish matches the reference header: title/subtitle and Validate All/count share one row; search/status/sector/Add & validate share one responsive row. The search field is also the explicit add target, removing the redundant second symbol input without changing validation behavior. The six-column table now fits without horizontal scrolling, prioritizes full symbol/sector names, trims redundant eligibility/date display text, and adds a persisted Saved Symbols star toggle at the start of every symbol row. Tapping an eligibility metric opens the persisted per-rule pass/fail evidence and explanation; the UI never reconstructs rule outcomes.
- Fixed a live honesty bug in the Inspect Trace modal (ADR-005): it derived each rule's outcome by searching the explanation text for `(PASS)`, a marker only the in-memory demo fixture writes, so every real rule rendered FAIL — including for symbols that passed all six — and the detail line was filler text rather than the recorded explanation. It now renders the persisted `evidence` outcomes and explanations, and falls back to showing older `trace` lines verbatim rather than guessing a state.

---

## MH-2 — Exact F-5 `MarketHealthScore` (APPROVED)

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | Construct + persist the authoritative six-component F-5 `MarketHealthScore`, and cut scoring's `market_quality` over to `total` when present |
| Scope | Config point maps + weights; pure `market_health/score.py`; owner_validation persistence; ScoringEngine cutover with categorical compat shim |
| Public APIs added | `construct_market_health_score`, `MarketHealthScoreBuild`, `ComponentScoreDetail`. Run detail key `market_health_score`. Scoring `score(..., market_health_score=)` |
| Tests | `tests/market_intel/test_market_health_score.py`. Full suite **1091 passed** |
| Coverage | Unit: band mapping, coverage/staleness unavailable, weighted total, scoring prefer-score vs shim, weights-sum validation |
| Architecture compliance | F-5 §4 honesty (absent ≠ 50; no score if any component missing); config-driven weights/points; no UI fabrication (MH-3); categorical engine retained |
| ADR compliance | ADR-005: score + per-component diagnostics on run detail. ADR-008 / DD-11 inputs consumed. F-5 Accepted |
| Risks discovered | Live score often unavailable until institutional flow + full-window gap + coverage gates are met — UI must keep showing Unavailable until then (MH-3) |
| Technical debt introduced | Risk engine still averages categorical labels (F-5 §7 listed scoring cutover; risk left on shim intentionally). Calendar-day staleness for FII/DII (not trading-session count) |
| Suggested improvements | Trading-day age for institutional max_age; optional risk cutover to inverted score; NSDL finalization |
| Remaining work | Completed — MH-3 owns Market Summary API + UI |
| Status | ✅ Approved (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- F-5 component point maps + weights (sum 100) in `config/market_health.json` / `MarketHealthConfig`.
- Pure constructor maps trend/breadth/liquidity/volatility/institutional/gap → points or absent; emits domain `MarketHealthScore` only when all six present.
- Owner validation assesses categorical health once, builds score, persists `market_health_score` diagnostics on run detail, shares score into scan scoring.
- `ScoringEngine._market_quality` prefers `MarketHealthScore.total`; categorical label average remains the compat shim.

### Follow-up after MH-3 approval — pre-existing test-suite warnings (addressed)

Observed during MH-2 (warnings only; suite was green). Cleared in the post-approval chore change set:

1. `InsecureKeyLengthWarning` — default `jwt_secret` lengthened to ≥32 bytes; `create_app` fails loudly if the effective secret is under 32 UTF-8 bytes.
2. `StarletteDeprecationWarning` — `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT` in `app.py`.
3. `PytestUnraisableExceptionWarning` — no-op `close()` on the kite 429 test `_Body` stub.

---

## MH-1 — Canonical inputs + persistence (APPROVED)

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | First implementation milestone of Market Metrics Completion: persist real FII/DII flows, universe breadth (+ neutral), liquidity/gap aggregates, and snapshot history reads — without constructing `MarketHealthScore` yet |
| Scope | Domain `InstitutionalFlowSession` + `MarketSnapshot.breadth_neutral`; `InstitutionalFlowProvider` (file/nse); SCHEMA_VERSION 11 `institutional_flows`; `market_health/aggregates.py`; ingest + owner_validation wiring; config extensions |
| Public APIs added | Repository: `add_institutional_flow`, `get_latest_institutional_flow`, `list_institutional_flows_recent`, `list_snapshots_recent`. Providers: `build_institutional_flow_provider`. Run detail key `market_metric_inputs` |
| Tests | `tests/data_layer/test_institutional_flow.py` (+ SCHEMA_VERSION bumps). Full suite **1081 passed** |
| Coverage | Unit/integration self-verified. Live NSE optional via `ingestion.institutional_flow_provider=nse` (default `file`) |
| Architecture compliance | ADR-008 separate Protocol; no MarketDataProvider pollution; cycle continues on flow fetch failure; additive blueprint field only |
| ADR compliance | ADR-005: inputs persisted for MH-2 score construction; no fabricated Health ring. ADR-008 Accepted. DD-11 Accepted |
| Risks discovered | NSE HTML/cookie warm-up fragility — mitigated by file fallback + non-aborting ingest. Adding a config key while a host is already running makes every `extra="forbid"` reload fail: `/ops/kite/status` 500s and the dashboard shows a false "Connect Kite" blocker until the host restarts |
| Technical debt introduced | None intentional. Score construction explicitly deferred to MH-2 |
| Suggested improvements | Optional NSDL finalization adapter; cookie jar persistence for NSE; deferred by owner — make `checkKiteGate()` distinguish a 5xx status-check failure from a genuinely disconnected session so config/code skew is not reported as a Kite re-login |
| Remaining work | Completed — MH-2 owns score construction |
| Status | ✅ Approved (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- Institutional flow Protocol + file CSV + NSE JSON adapters; append-only SQLite table; best-effort ingest hook.
- Universe ADV/DEC/neutral overlay onto `MarketSnapshot` during owner validation; `breadth_neutral` round-trips in serialization.
- Liquidity median turnover + rolling gap-stability pure aggregates; thresholds in `config/market_health.json`.
- `list_snapshots_recent` for MH-3 sparklines / Recent Activity history.

---

## MI-4 — Universe table redesign + Sector ingestion fix

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | Fourth milestone of the Market Intelligence Redesign: redesign Stock List into the Universe table and surface Sector via the seed-CSV Industry ingestion fix |
| Scope | `src/athena/domain/market.py`, `src/athena/data/store/{schema,serialization,repository}.py`, `src/athena/ops/{constituents,candidate_seed}.py`, `src/athena/api/v1/{dtos/market.py,services/candidates_service.py}`, `src/athena/api/static/{index.html,js/09-market-intelligence.js,css/06-market-intelligence.css}`, tests listed below |
| Public APIs added | None new — `GET /api/v1/market/candidates` now optionally returns `sector`, `status`, `eligibility_summary`, `last_validated_ts` |
| Tests | Sector parse/migration/kite-preserve/seed backfill; candidates enrichment; scoped-validate verdict merge; Qualified Today dedupe (write + read path); dashboard hosting. Full suite **1055 passed** |
| Coverage | Self-verified. Live needs host restart + seed sector backfill (`./athena-daily` / candidate seed — Industry applied even on once-per-day skip) |
| Architecture compliance | No architecture change. Additive `Instrument.sector` (same class as DT-3 `name`). Sector sourced from NSE seed CSV only — Kite has none |
| ADR compliance | ADR-005: missing sector/status/last-validated render as `—`/Pending, never fabricated |
| Risks discovered | Sector stays null until instruments exist and seed runs with `instrument_repo` attached; once-per-day skip still refreshes sectors |
| Technical debt introduced | None |
| Suggested improvements | Optional client-side paging if Universe grows far past ~500; Inspect Trace FAIL-badge parsing honesty (pre-existing, flagged in MI-3) |
| Remaining work | None for this milestone |
| Status | **✅ Approved** (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- **Ingestion**: `parse_nifty_constituent_rows()` keeps Industry; `CandidateSeeder` backfills `instruments.sector` via `update_instrument_sector` even when candidate merge is skipped for the day; kite upserts use `COALESCE`-style preserve so catalog refresh cannot wipe seed-written sector.
- **Schema**: SCHEMA_VERSION 10 + idempotent `ALTER TABLE instruments ADD COLUMN sector TEXT`.
- **API enrichment**: `CandidatesService.list_candidates` joins sector map, per-symbol universe verdict (Eligible/Excluded/Pending + eligibility_summary), and last-validated timestamp.
- **UI**: Stock List → Universe table with search + status/sector filters; actions Validate / Inspect Trace / Remove.

### Owner-reported fixes (same milestone, before approval)

- **Universe status collapsed after every scoped validate**: the verdict lookup read a single run, but a scoped validate persists a run whose `universe_members` covers only the symbols it was asked about — so validating one symbol flipped all others back to Pending. `_universe_verdicts()` now merges newest-run-first across recent completed runs, first-wins per symbol, stopping early once every candidate is covered. Excluded symbols (which never produce a Decision) take Last Validated from the run that judged them, so the column is no longer blank for them.
- **Duplicate symbols under Qualified Today**: `_qualified_from_repo` listed every same-day Decision, so each re-validate of a symbol added another identical row. It now keeps each symbol's newest same-day verdict only, and reads WATCH/TRADE from that newest verdict — a name later downgraded to NO_TRADE no longer resurfaces from its earlier qualifying run.
- **Read path hardened for already-persisted runs**: the write-path fix only affects new runs, so `SqlitePipelineRunProvider._dedupe_qualified` collapses `qualified_today` to one row per symbol (newest first) when serving run detail. Run history recorded before the fix — e.g. today's runs holding 2 and 7 copies of one symbol — renders honestly without a re-validate.

---

## Fix pass — unlisted candidate symbols

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | A typo'd candidate (`INFSDFSD`) added through the dashboard aborted `./athena-daily` for the entire 507-symbol universe: stop storing symbols the exchange does not list, and stop one bad name from failing a whole cycle |
| Scope | `src/athena/data/providers/{kite_provider,factory}.py`, `src/athena/ops/{symbol_validate,owner_validation}.py`, `src/athena/api/v1/{dtos/market.py,services/candidates_service.py,providers/sqlite_providers.py}`, `src/athena/api/static/{index.html,js/09-market-intelligence.js,css/06-market-intelligence.css}`, tests below |
| Public APIs added | None. `POST /api/v1/market/candidates` can now return 422 for a symbol the exchange does not list; `OwnerCandidateDTO.status` gains `UNRESOLVED` |
| Tests | `tests/data_layer/test_kite_provider.py` (strict vs scope filter), `tests/ops/test_owner_validation.py` (reports-not-judges), `tests/api/v1/test_owner_candidates.py` (UNRESOLVED mapping, add-time rejection, offline fallback), `tests/api/platform/test_dashboard_hosting.py`. Full suite **1064 passed** |
| Coverage | Reproduced from the owner's own failing `./athena-daily` output; replayed against a copy of the live DB |
| Architecture compliance | No architecture change. Provider independence preserved: the pipeline decides "unresolved" from repo evidence (no catalog row, no ingested bar), never by consulting Kite |
| ADR compliance | ADR-005: an unresolvable symbol is reported as `UNRESOLVED` with the run's own reason, not dressed up as an eligibility verdict it never earned |
| Risks discovered | Add-time rejection is best effort — it cannot run when the catalog is unreachable, which is why the pipeline-side reporting exists as the second line of defence |
| Technical debt introduced | None |
| Suggested improvements | Offer a one-click remove from the Unresolved filter view once MI-5's Quick Actions land |
| Remaining work | None |
| Status | 🔄 Ready for review (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- **Provider**: `KiteProvider(strict_symbol_filter=True)` keeps `kite.json`'s own symbols failing loudly; the factory turns it off for caller-supplied scopes, which unblocks the resolve-and-warn code the CLI already had (it was unreachable because `_ensure_catalog` raised first) and lets `validate_symbols` return its own 422 instead of a 502.
- **Add time**: `resolve_against_catalog()` extracted from `validate_symbols` (one catalog fetch, no duplicate logic) and used by `upsert_candidate` to refuse an unlisted symbol before anything is stored.
- **Pipeline**: a candidate with no catalog row and no ingested bar is listed in `unresolved_candidates` instead of being judged as a synthesized instrument, which had reported it as "Excluded: failed rules".
- **UI**: `UNRESOLVED` status badge and filter option in the Universe table; failed adds surface the server's message instead of an unhandled rejection.

---

## Fix pass — Validation Pipeline shows the day, not the last run

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | Owner: "validation pipeline always lists only recent symbol and overrides previous one — I want the previous validation list as well" |
| Scope | `src/athena/ops/owner_validation.py`, `src/athena/api/v1/services/pipelines_service.py`, `src/athena/api/static/js/09-market-intelligence.js`, tests below |
| Public APIs added | None. `GET /api/v1/pipelines/validation-funnel` keeps its shape; its counts now cover the day rather than one run |
| Tests | `tests/api/v1/test_core_apis.py` (day merge, previous day excluded, re-validate replaces a verdict), `tests/ops/test_owner_validation.py` (Qualified Today keeps earlier runs, one row per symbol, same day only), `tests/api/platform/test_dashboard_hosting.py`. Full suite **1064 passed** |
| Coverage | Replayed against a copy of the live DB: Universe 1 / Eligible 1 → Universe 16 / Eligible 9 / Watch 5 / Trade 4 for the day, rebuilt from runs already persisted |
| Architecture compliance | No architecture change. Read-model aggregation only — no new scan, no mutation, no new endpoint |
| ADR compliance | ADR-005: counts are distinct real symbols, never summed per-run counts (which would count re-validations twice) and never carried across a day boundary |
| Risks discovered | The funnel is day-scoped while the Universe table keeps each symbol's latest known verdict regardless of day, so the two can legitimately differ — both are labelled |
| Technical debt introduced | None |
| Suggested improvements | Once MI-5's full-universe run exists, one run will cover the whole universe and the merge becomes a safety net rather than the main path |
| Remaining work | None |
| Status | 🔄 Ready for review (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- **Write path**: `_qualified_from_repo()` reports every WATCH/TRADE decision made today instead of only the current run's symbols, still keeping each symbol's newest verdict (a name downgraded to NO_TRADE drops out).
- **Funnel**: `validation_funnel()` merges the day's completed runs — each symbol keeps the verdict of the newest run that covered it, and its WATCH/TRADE is read from that same run, so a name re-validated without qualifying loses the decision it earned earlier. Runs that recorded counts without per-symbol members keep the previous summary-based reading.
- **Details modal**: the dashboard applies the same merge, so Eligible/Excluded and Qualified Today agree with the funnel instead of showing the last scoped symbol alone.

---

## MI-5 — Recent Activity + Quick Actions + Full Validation (ADR-007)

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | Final Market Intelligence redesign milestone: Quick Actions, Recent Activity, Saved Symbols relocation, and owner-triggered full-universe validation as a background host job (ADR-007 Accepted) |
| Scope | `src/athena/config/models.py`, `config/providers/kite.json`, `src/athena/data/providers/{kite_transport,kite_provider}.py`, `src/athena/ops/{serve_runtime,full_validation}.py`, `src/athena/api/{errors.py,v1/dtos/market.py,v1/services/candidates_service.py,v1/routers/market.py}`, `src/athena/api/static/{index.html,js/09-market-intelligence.js,css/06-market-intelligence.css}`, tests below |
| Public APIs added | `POST /api/v1/market/validate-all` (202) → start; `GET /api/v1/market/validate-all` → poll `FullValidationProgressDTO`. `CycleBusyError` → HTTP 409 |
| Tests | Pacing/429 transport; full-validation busy/lock; validate-all API; dashboard hosting. Full suite **1072 passed** |
| Coverage | Self-verified. Owner live-review density pass measured at 1920×1080: Universe occupies 62.7% of the main workspace with a 553px internal table viewport; Summary is 172px high and Pipeline 173px. Progress is process-local on ServeRuntime |
| Architecture compliance | No new execution model beyond ADR-007. Reuses `CycleRunnerLock` / `DryRunCycleOrchestrator` / `OwnerValidationPipeline`. No schema bump. Scoped validate contract unchanged |
| ADR compliance | ADR-007 Accepted. ADR-005: Recent Activity is real run history; Export omitted; Refresh Market View labelled honestly (reload view, not provider ingest) |
| Risks discovered | Progress mid-ingest cannot honestly report per-symbol completion without instrumenting `LiveIngestionEngine` — UI shows stage + total, completed jumps to total on success |
| Technical debt introduced | None intentional. Revisit ServeRuntime progress before multi-worker deploy (documented in ADR-007) |
| Suggested improvements | Optional per-symbol progress callbacks in ingestion; cancel-running-job control |
| Remaining work | None — Market Intelligence redesign track closed. Numeric Health Score + real breadth deferred to Market Metrics Completion (MH-0+) |
| Status | ✅ Approved (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- **Provider pacing**: configurable intervals + 429 retry with exponential backoff; injectable sleep/clock for tests; wired through `KiteProvider.from_config_dir`.
- **Background job**: single-flight via advisory lock; transient progress on `ServeRuntime`; durable outcome is the usual run record.
- **UI**: Mock-aligned Market Summary with one seven-cell row (Regime/Volatility/Gap + four real health dimensions) and a full-width Evidence footer; compact horizontal Validation KPI blocks; Universe at ~63% of the main workspace with sticky-header internal scrolling; utility rail reordered Recent Activity → Saved Symbols → Quick Actions; assets `v9.63.0`.

---

## MH-0 — FII/DII source + F-5 scoring design (APPROVED)

| | |
|---|---|
| Completed | 2026-07-28 (design only — no engine code) |
| Objective | First milestone of Market Metrics Completion: lock the institutional-flow data source, provider boundary, and exact F-5 six-component scoring/persistence/API contracts before any implementation |
| Scope | `docs/decisions/DD-11-institutional-flow-fii-dii.md`, `docs/adr/ADR-008-institutional-flow-provider.md` (Accepted), `docs/design/F5-MARKET-HEALTH-SCORE.md`, `docs/MILESTONES.md` track intro |
| Public APIs added | None (design) |
| Tests | N/A — design milestone |
| Coverage | Specs cover source criteria, FileProvider-first replay path, NSE official primary live source, NSDL finalization note, unknown-data policy, component formulas, single authoritative score vs scoring `market_quality`, snapshot field addition (`breadth_neutral`), and MH-1…MH-3 exit criteria |
| Architecture compliance | No code change at design time. Separates institutional flow from `MarketDataProvider` (ADR-002) via ADR-008. Breadth uses frozen `MarketSnapshot` fields + reviewed additive `breadth_neutral`. Score uses already-frozen `MarketHealthScore` |
| ADR compliance | ADR-005: score/rings only from persisted engine output. ADR-002: no broker Protocol pollution — new flow Protocol. ADR-007 unchanged |
| Risks discovered | NSE HTML/CSV scrape fragility; evening FII figures are provisional until custodian confirmation; third-party aggregators are convenience only, not canonical |
| Technical debt introduced | None |
| Suggested improvements | None |
| Remaining work | Completed — owner accepted; MH-1 authorized |
| Status | ✅ Approved (2026-07-28) |
| Branch | feature/live-dashboard |

---

## MI-3 — Validation Pipeline funnel (APPROVED)

| | |
|---|---|
| Completed | 2026-07-28 |
| Objective | Third milestone of the Market Intelligence Redesign: replace Today's Validation text strip with a horizontal Universe→Eligible→Filtered→Watch→Trade funnel backed by a typed READ endpoint over already-persisted validation counts |
| Scope | `src/athena/api/v1/dtos/pipelines.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/services/pipelines_service.py`, `src/athena/api/v1/routers/pipelines.py`, `src/athena/api/static/{index.html,js/09-market-intelligence.js,css/06-market-intelligence.css}`, `tests/api/v1/test_core_apis.py`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | `GET /api/v1/pipelines/validation-funnel` → `ValidationFunnelDTO` (READ). Stages always returned (stable UI contract); `available=false` when no owner_validation `validation_summary` exists |
| Tests | 3 new pipeline API tests + ~20 dashboard-hosting assertions. Full suite **1045 passed** |
| Coverage | API self-verified with real-shaped summary (Filtered = Eligible−Watch−Trade). Live-browser check needs server restart after this backend change |
| Architecture compliance | No architecture change. Priority-2 expose-already-computed pattern (same family as DT-2 ticker). No mutation, no new provider, no new scan |
| ADR compliance | ADR-005: Filtered is honest arithmetic over real counts, not a fabricated upstream stage; empty state is explicit (`available=false`), never invented percentages when Universe is 0 |
| Risks discovered | None new. Confirm live against production `db/athena.db` after restart — endpoint prefers newest non-failed run with a `validation_summary` |
| Technical debt introduced | None. Eligible/Excluded + Qualified remain under View Details until MI-4 (intentional bridge, not debt) |
| Suggested improvements | None beyond MI-4/MI-5 already tracked |
| Remaining work | None for this milestone |
| Status | **✅ Approved** (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- **Backend**: `PipelinesService.validation_funnel()` walks newest successful runs (same preference as the Market Intelligence tab), extracts `validation_summary`, maps Universe (`candidates`, falling back to `evaluated`), Eligible, Watch/Trade from `decision_counts`, and Filtered as `max(0, eligible − watch − trade)`. `% of Universe` to 1 decimal, or `None` when Universe is 0.
- **Frontend**: "Today's Validation" → "Validation Pipeline"; horizontal 5-stage funnel with Trade accent; as-of timestamp; empty guidance when `available=false`; View Details opens Eligible/Excluded + Qualified in a modal (kept out of the primary column so the Stock List remains the scroll region); Saved Symbols collapsed by default; Inspect Trace uses a stacked modal layer so it renders above the funnel details.
- **Fetch**: `loadMarketIntelligence` loads `/pipelines/validation-funnel` in parallel with `/pipelines/runs` (runs still needed for regime + universe members).
- **Polish (owner live review)**: funnel icons/chevrons/(TODAY)/Last Updated footer; column layout auto/1fr/auto with no outer column scroll; Market Summary height-to-content; `.modal-stacked` z-index for Trace-over-Details; Escape closes topmost stacked modal first.

---

## MI-2 — Market Summary Hero + Market Regime & Context (APPROVED)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | Second milestone of the Market Intelligence Redesign: replace "Volatility Regime & Health" with a larger-presentation "Market Summary" hero, and surface the real Market Health categorical breakdown instead of a fabricated numeric score |
| Scope | `src/athena/ops/owner_validation.py`, `src/athena/api/static/{index.html,js/09-market-intelligence.js,js/07-decision-format.js,css/06-market-intelligence.css}`, `tests/ops/test_owner_validation.py`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None — `_regime_to_payload()` signature change is internal; the same `/api/v1/pipelines/runs` endpoint the page already used now carries a real `market_health` dict instead of a hardcoded `0` |
| Tests | 1 new backend assertion locking in the real 4-dimension dict against the production repository shape. ~30 new/updated dashboard-hosting assertions. Full suite **1042 passed** |
| Coverage | Live-verified against real production data: ran `OwnerValidationPipeline.run()` directly against `db/athena.db` for a real symbol, confirmed `market_health` came back as a real dict; loaded that exact payload into the live-served frontend and confirmed correct tone-coloring on all 7 fields (3 regime + 4 health dimensions). Caught and fixed a real label-truncation bug via DOM measurement at realistic narrower workstation widths |
| Architecture compliance | No architecture change. Backend fix is corrective (surfacing an already-computed value that was being silently discarded), not new business logic |
| ADR compliance | ADR-005: the fabricated numeric gauge (`market_health: 0`, always) is replaced with real data; where no real numeric score exists (`MarketHealthScore` is never constructed anywhere in ATHENA), the honest categorical labels are shown instead of inventing a number |
| Risks discovered | None new. Confirmed `MarketHealthScore` (frozen domain type) has been entirely unimplemented since it was designed — worth flagging if a future milestone ever wants a real aggregate score, since it would need actual computation logic defined, not just wiring |
| Technical debt introduced | None — a small amount was removed (`formatVolatilityLabel()` dead code, parallel bull/bear/neutral tone logic unified into the single `contextChipTone()` system) |
| Suggested improvements | None identified beyond what's already tracked (`MarketHealthScore` real implementation, if ever wanted) |
| Remaining work | None — both scope items (hero redesign, real market health) complete |
| Status | **✅ Approved** (2026-07-28) |
| Branch | feature/live-dashboard |

### Scope completed

- **Backend fix, two parts (the second caught only by re-running tests after the first)**: `_regime_to_payload()` now accepts a `market_health` param and builds a real `{breadth, trend_quality, momentum, volatility}` dict from it instead of hardcoding `0`; `reg_stage` reordered so market health is computed before the payload captures it. That alone didn't reach the frontend — `run()`'s eager `_maybe_regime()` call (regime-only, no market health) was being preferred over the scan's own richer payload every time a scan had eligible symbols, because the fallback condition (`if regime_payload is None`) was almost never true. Flipped the precedence to prefer the scan's payload whenever a scan actually ran.
- **Frontend**: card renamed "Market Summary" with a real as-of timestamp (`regimeAsOf`, tracked from the winning pipeline run). Trend/Volatility/Gap rebuilt as `.brief-gauge`/`.hero-metric-band` tiles — the exact tile language Decisions & Trace's own hero gauges use, tone-colored via `contextChipTone()`/`friendlyLabel()` (the same functions, same RegimeLabel enum, already fixed for the descriptor-prefix bug earlier this session) instead of a parallel, duplicate bull/bear/neutral classifier. Market Health rebuilt as a `.context-metric-grid` — the exact cards the Decision Brief's own Market Context uses for the same `MarketHealthLabel` enum, via a new `renderMarketHealthGrid()` that reuses `contextMetricCard`/`contextChipTone`/`friendlyLabel` verbatim.
- **Honesty fix, found while unifying the tone logic**: each of Trend/Volatility/Gap previously defaulted an absent field to a *specific assessed state* (`"NEUTRAL"`, `"NORMAL_VOLATILITY"`, `"NO_GAP"`) rather than "unknown" — meaning a genuinely missing value could render as a plausible-looking real result. Changed all three fallbacks to their own `*_UNKNOWN` sentinel.
- **Dead code removed**: `formatVolatilityLabel()` (07-decision-format.js) — its only caller was this rendering block, now replaced; `.regime-badge`/`.regime-field`/`.health-gauge-container`/`.health-bar-fill`/`.health-score-value` CSS (06-market-intelligence.css) — all confirmed zero remaining references before deletion.
- **Truncation bug caught via DOM measurement, not eyeballing**: at realistic narrower workstation widths, even a single-word label ("Volatility") could truncate in the 3-column hero grid (`.brief-gauge-label` defaults to single-line ellipsis, tuned for the 4-column Decision Brief context's shorter labels). Fixed with shorter labels ("Market Regime" → "Regime", "Opening Gap" → "Gap") plus a scoped wrap override for this grid, then re-measured (`scrollWidth` vs `clientWidth`) to confirm zero truncation.

---

## MI-1 — Shared ticker strip + Trading Calendar relocation (APPROVED)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | First milestone of the new "ATHENA Market Intelligence Redesign" assignment (Market Intelligence → "Market Command Center", matching the Decisions & Trace workstation design language). Scope narrowed at Design time from the originally-proposed full 2-row grid down to the two independently well-defined, zero-placeholder pieces — see Scope completed below for why |
| Scope | `src/athena/api/static/js/03-app-shell.js`, `src/athena/api/static/index.html`, `src/athena/api/static/css/06-market-intelligence.css`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None — frontend-only, reuses the existing `GET /api/v1/market/ticker` endpoint and existing calendar-rendering functions verbatim |
| Tests | ~15 new/updated dashboard-hosting assertions. Full suite **1042 passed** |
| Coverage | Live-browser verified: ticker strip confirmed visible on Market Intelligence via a real nav click (not synthetic); 2-column grid renders correctly; calendar `<details>` panel collapsed by default, expands on click with chevron rotation, calendar content renders correctly once expanded; zero uncaught console errors beyond the expected unauthenticated-fetch logging already present in every prior milestone |
| Status | **✅ Approved** (2026-07-27) |
| Branch | feature/live-dashboard |

### Scope completed

Before proposing any milestone breakdown, a full data-source inventory (file:line level) was done across every element in the reference mock the owner supplied. Two findings materially changed what the redesign can show: **Market Health Score** ("84/100" ring in the mock) is hardcoded `0` upstream, and the numeric `MarketHealthScore` domain type has zero constructors anywhere in the codebase — never implemented, not just stale. **Breadth** ("72%"/"1458/526") is likewise hardcoded `0`/`0` in the live Kite provider, confirmed still true today. Both findings, plus four other gaps (Recent Activity synthesis, Universe table Sector, Run Full Validation wiring, Export Market Snapshot), were presented to the owner before any code was written; owner decisions are recorded in `docs/MILESTONES.md`'s track intro.

- **Shared ticker strip**: `03-app-shell.js` previously hardcoded `tabId !== "decisions"` in three separate places (visibility toggle, refresh start/stop, `loadTabData`'s dispatch). Replaced all three with a single `TICKER_TABS = new Set(["decisions", "market"])` set, and added a `loadMarketTicker()` call to the `"market"` branch of `loadTabData()` — one shared component/endpoint across both tabs, not a duplicated one.
- **Trading Calendar relocation**: moved out of the primary `.market-workstation` grid (3 columns → 2) into a `<details class="market-calendar-details">` panel below it, collapsed by default. Exact same ids (`calendar-month-year`/`calendar-grid-container`/`upcoming-events-container`) preserved, so `renderCalendar()`/`renderUpcomingEvents()` needed zero changes — purely a markup relocation plus new CSS for the collapsible summary/chevron (native `<details>`, no JS toggle logic).
- **Scope narrowing, disclosed before implementation**: the originally-proposed "2-row workstation grid" (Hero / Context+Pipeline+Actions / Universe+Activity+Saved) would have required empty placeholder cells for Quick Actions and Recent Activity, since their real content doesn't exist until MI-5 — conflicts with the project's "no speculative features, no placeholders" rule. Narrowed MI-1 to just the two pieces above; the grid will take its final shape incrementally as MI-2 through MI-5 land real content, the same way DT-1→DT-4 organically built up the Decisions & Trace layout rather than pre-building an empty shell.

---

## DT-4 — Reasoning Trace vertical pipeline list + Similar Trades sparkline (APPROVED)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | Fourth and final milestone of the owner's "ATHENA Workstation Refactor": replace the Reasoning Trace's auto-fit-grid + SVG-connector DAG with a cleaner vertical pipeline list, and add a last-5-trades sparkline to the Analogs (Similar Trades) panel — both per the scope agreed at the start of the assignment |
| Scope | `src/athena/api/static/js/{18-decision-brief-trace,19-decision-brief-history}.js`, `src/athena/api/static/css/{12-decision-cards-dag,13-context-history}.css`, `src/athena/api/static/index.html`, `tests/api/platform/test_dashboard_hosting.py` |
| Public APIs added | None — both changes are frontend-only, built from data already fetched by existing endpoints (`GET /decisions/{id}/trace`, `GET /decisions/{id}/analogs`) |
| Tests | ~15 new/updated dashboard-hosting assertions. Full suite **1042 passed** |
| Coverage | Live-browser verified via injected sample data (no owner credentials available for a real authenticated load, same constraint as prior milestones): pipeline list renders with a connecting rail between stages, click sets the active state (accent icon ring + glow + highlighted row), status badges render inline; sparkline renders bars scaled by return magnitude, colored green/red by sign, tooltip shows exact date/return. Zero uncaught console errors from the new code |
| Architecture compliance | No backend/business-logic change; no new provider; no new calculation — sparkline reuses `DecisionAnalogDTO.outcome_return_pct`/`outcome_closed_ts`, both already persisted and already fetched |
| ADR compliance | ADR-005 (explainability-as-data): no new numbers computed client-side beyond simple bar-height scaling of already-real values; ADR-004 (static HTML-first, no framework): both pieces are hand-rolled JS/CSS, no dependency added |
| Risks discovered | None new. Confirmed a stale-browser-cache quirk during verification (the outer `dashboard.css` link carries a cache-bust query param but its inner `@import`-ed files don't, so a long-lived tab can serve a stale inner CSS file until a hard reload) — not a code defect, just a verification-technique note for future sessions |
| Technical debt introduced | None |
| Suggested improvements | None identified |
| Remaining work | None — both scope items complete. This was the final milestone (DT-4 of 4) of the ATHENA Workstation Refactor assignment; the whole track is now closed |
| Status | **✅ Approved** (2026-07-27) |
| Branch | feature/live-dashboard |

### Scope completed

**Part 1 — Reasoning Trace vertical pipeline list.** Replaced the CSS grid (`grid-template-columns: repeat(auto-fit, minmax(130px, 1fr))`) of card-style stage nodes connected by JS-computed SVG `<line>` elements (`drawDAGLines()`, using a `ResizeObserver` + `getBoundingClientRect()` to redraw connector coordinates on resize — fragile once stages wrapped onto a second grid row) with a vertical flex-column list: each stage is a horizontal row (a circular icon-wrap + name/status body) connected by a pure-CSS rail (`.dag-node-rail::after`, a static `2px` line to the next node, no coordinate math, immune to wrapping). Same stage order, same click → `selectNode`/`showStageDetails` behavior, same status badge classes — only the connective visual layer changed. `drawDAGLines()` and its `ResizeObserver`/`setTimeout` callers removed entirely (dead code, zero remaining callers checked before deletion). The `<svg id="dag-svg-lines">` element removed from `index.html`.

**Part 2 — Similar Trades sparkline.** Added a compact inline SVG bar sparkline to the existing "Historical validation" card in the Analogs panel, showing the last 5 similar trades' realized returns. `analogSparklinePoints()` filters the already-fetched analogs (`activeAnalogs`, from `loadDecisionAnalogs`) to those with a realized outcome, sorts by close time descending, takes the 5 most recent, and reverses to oldest-first for a left-to-right trend read. `renderAnalogSparkline()` renders each as a `<rect>` whose height is proportional to `|outcome_return_pct|` (normalized against the max magnitude in the set) and whose color is `--tone-good-text`/`--tone-bad-text` by sign — the same tokens already used everywhere else in the app for pnl coloring, not a new palette. No new endpoint, no new backend field (`outcome_return_pct`/`outcome_closed_ts` already existed on `DecisionAnalogDTO` from an earlier milestone, simply unused until now) — a pure Priority-1 "reposition already-fetched data" change, per the owner's earlier "add the mini sparkline (Recommended)" decision.

### Verification notes

- Caught and fixed one test regression: an explanatory code comment containing the literal word "ResizeObserver" tripped the `assert "ResizeObserver" not in js` check meant to confirm the old coordinate-math approach was gone — narrowed to `"new ResizeObserver" not in js` (checking for actual instantiation, not any mention of the word).
- During live-browser verification, the sparkline bars initially rendered solid black instead of green/red. Root cause: the browser tab had cached the *inner* `css/13-context-history.css` file (reached via `@import` from the outer `dashboard.css`) from before this milestone's edit — the outer link's cache-bust query param doesn't propagate through `@import`, so a long-lived tab's HTTP cache can serve a stale inner file even after a fresh navigation. Confirmed via a cache-bypassing `fetch(..., {cache: "no-store"})` that the correct CSS rule was already on disk; this was a verification-technique artifact, not a code defect — a real hard-reload (or a fresh server restart, as already required for backend changes) picks up the new CSS normally.
- No backend restart was required for this milestone (frontend-only change) — cache-bust bumped in `index.html` (`9.53.0` for Part 1, `9.53.1` for Part 2) so the single concatenated `dashboard.js` and outer `dashboard.css` are re-fetched on next load.

---

## DT-3 — Tab restructuring: 5 tabs + spacing polish (APPROVED)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | Third milestone of the owner's "ATHENA Workstation Refactor": split the old single "Decision History" tab (which mixed logging a response with browsing history) into Response and History, per the scope agreed at the start of the assignment |
| Scope | `src/athena/api/static/index.html`, `src/athena/api/static/js/{13-decision-brief-core,14-decision-brief-analysis,18-decision-brief-trace,06-ui-helpers,07-decision-format}.js`, `src/athena/api/static/css/09-decision-brief-shell.css`, `src/athena/domain/market.py`, `src/athena/data/store/{schema,repository,serialization}.py`, `src/athena/data/providers/{kite_provider,file_provider}.py`, `src/athena/api/v1/dtos/decisions.py`, `src/athena/api/v1/services/decisions_service.py`, `src/athena/api/dependencies.py`, test files listed below |
| Tests | ~40 new/updated dashboard-hosting assertions across four rounds, plus 7 new backend tests (instruments.name migration/roundtrip, Kite-dump name parsing, DecisionMetadataDTO.instrument_name). Full suite **1042 passed** |
| Coverage | Live-browser verified: all 5 tabstrip buttons present, correctly ordered/labeled, click-wiring confirmed; structural source-slice test confirms Journal stays in Response while Timeline+Analogs move together into History; merged Recommendation+gauges tile and collapsed ATHENA Summary card visually confirmed via injected sample data, matching the reference mock; View Details modal opens/closes correctly (button, close button, and backdrop click all confirmed); identity row redesign visually confirmed (star toggle, company name, "NSE: DIXON" meta row, overflow menu open/close, ticker no longer truncates); star toggle's graceful 401 handling confirmed (no owner credentials for a real save); schema migration confirmed safe against the real production db (506 rows preserved); zero uncaught console errors |
| Status | **✅ Approved** (2026-07-27) |
| Branch | feature/live-dashboard |

### Scope completed

- **Tabstrip**: the single "Decision History" button (`data-brief-tab="response"`) split into two — "Response" (unchanged icon `fa-comment-dots`) and a new "History" (`fa-clock-rotate-left`).
- **Decision Timeline moved out of the always-visible hero.** It previously rendered inside `.decision-brief-hero` — visible on every tab regardless of which one was active, a real instance of the original assignment's "Remove Vertical Wasted Space" principle, not just a cosmetic complaint. Now it only renders inside the new History tabpane.
- **Similar past setups (Analogs) moved out of Response into History**, alongside the Timeline — reasoning: recording a response/outcome is a distinct action from browsing history, and the two didn't share a rendering timeline or data source. Response now holds only the Journal panel.
- `BRIEF_TAB_NAMES` (`18-decision-brief-trace.js`) extended `["setup", "analysis", "context", "response"]` → `[..., "history"]`; `BRIEF_TAB_LABELS.response` renamed `"Decision History"` → `"Response"`, new `history: "History"` entry added. `STAGE_TAB_MAP` left unchanged — no DAG stage currently jumps to response or history.
- No backend touched — this is presentation-only regrouping of already-rendered sections; no new fetch, no new calculation, no content removed or invented.

### Refinement from owner screenshot review (2026-07-27), before final approval

Owner shared the reference mock's hero hierarchy (Recommendation+gauges card → collapsed Summary card with "View Details" → tab strip) and asked for the same, since the Executive Summary bullet list was still always-visible on every tab (same class of issue this milestone had just fixed for Decision Timeline). Confirmed scope first: skip an "Expected Holding" gauge (same conclusion as DT-2's Quick Summary — no real forward-looking estimate exists), and leave the action bar's position unchanged.

- **Recommendation merged into the gauges row** as a new first tile — stance badge (`gauge-recommendation-stance`) set synchronously from `decisionStance()` (same data already used for the header chip); a qualifier band (`gauge-recommendation-band`, e.g. "Good Setup") set inside `renderCockpitGauges()` by reusing the Score tile's own already-computed band — never a second, independently-derived word.
- **Executive Summary collapsed into an "ATHENA Summary" card** (`#decision-summary-card`, reusing the existing `.decision-banner` stance-tone-colored classes) — shows the same real one-line headline previously rendered as the banner's reason text, plus a "View Details" button, positioned between the gauges row and the tab strip in the sticky header (moved out of the scrollable, always-visible hero).
- **New `#executive-summary-modal`** shows the full bullet breakdown on "View Details" — reuses the exact existing `openModal`/`closeModal` functions and the compare-modal's close-button/backdrop-click/Escape-key pattern verbatim; added to `closeAllModals()`. `renderExecutiveSummary()` is unchanged — its target container just moved from a per-render JS template into static HTML inside the modal.
- **`.decision-brief-hero` removed entirely** from `renderDecisionBrief()`'s per-decision template (it had already lost Decision Timeline earlier in this same milestone, and now the Banner moved out too — nothing was left to justify the wrapper), and the now-dead `.decision-brief-hero` CSS rule was deleted.

**Fix pass (same review):** the Recommendation tile initially shipped as a small `.stance-chip` pill inside a plain dark `.brief-gauge` tile — owner feedback: the reference mock treats it as a fully stance-tinted highlight card, not just another gauge tile with a badge inside. Fixed: `gaugeRecommendationTile.className` now applies the same `stance.cls` (`stance-buy`/`-sell`/`-hold`/`-pass`/`-wait`) already used by `.decision-banner`, and `.brief-gauge-recommendation.stance-*` gets the identical radial-gradient tint `.decision-banner.stance-*` uses (one tone system, not a second palette); the stance text switched from a small `.stance-chip` pill to `.hero-metric-band` (same large-bold sizing the Score/Confidence/Risk tiles already use for their band words), colored per stance via a scoped selector on the tile's own class.

### Identity row redesign (owner reference-mock screenshot, third review round)

Researched every new element in the mock before building anything, per the Data Source Priority rule — three of the four turned out to be data gaps, one of them fixable:

- **Company full name — fixable gap, owner approved the ingestion change.** Kite Connect's real instrument dump has always carried a `name` column; ATHENA's ingestion discarded it. Added `Instrument.name` (domain), bumped `SCHEMA_VERSION` 8→9, added an idempotent migration (`_migrate_instruments_name_column()` in `repository.py`, guarded by `PRAGMA table_info` so it safely reaches the *existing* `db/athena.db` — `CREATE TABLE IF NOT EXISTS` alone is a no-op against a table that already exists), updated `kite_provider.py`/`file_provider.py` to capture it, added `DecisionMetadataDTO.instrument_name`, and gave `DecisionsService` an optional `repo` (same optional-repo-alongside-primary-abstraction precedent as `MarketHistoryService`) to look it up via `repo.get_instrument()`. **Verified the migration already ran safely against the real production db** (via the test suite's own real-db wiring, a pre-existing characteristic): 506 existing instruments preserved, `name` column added, all correctly `NULL` — never fabricated — since no fresh Kite catalog sync has happened since. Real names will populate automatically on the next sync.
- **Sector and market-cap category — genuine gaps, no fix available.** Nothing in ATHENA's domain model, database, or Kite's own feed maps a symbol to either. **Owner decision: omit both, tracked as future scope.** The new meta row gracefully holds just the one real pill ("NSE: DIXON") today.
- **Star favorite toggle** — new UI surface for the existing "Saved Symbols" feature (UX-9b), reusing `GET/POST/DELETE /api/v1/saved-symbols` as-is (Priority-2, no new backend). A local `Set` cache avoids re-fetching the list on every symbol selection.
- **BUY/TRADE badges dropped** (owner-confirmed) — redundant with the Recommendation tile in the gauges row.
- **Secondary actions moved into a "more" (⋮) popover** (owner-confirmed which ones) — Dismiss today/Remove candidate/Export/News; Market Intelligence/Open Chart/Compare stay in the primary action bar. The moved buttons are the exact same elements relocated (ids/classes/click handlers unchanged), not rebuilt — same toggle/backdrop-click/Escape pattern as the symbols filter popover.
- **Fix pass (same round):** the ticker ("DIXON") rendered truncated to "DI…" once the company name sat beside it in the same flex row — neither element had an explicit `flex-shrink`, so flexbox shrank both by default. Fixed: `.decision-brief-symbol-lg` gets `flex-shrink: 0` (the primary identifier must never lose space to a secondary one), `.decision-brief-company-name` is the element that truncates.
- Dead code removed: `decisionBriefStanceChip`/`decisionBriefTypeChip` DOM refs and the now-unused `decisionTypeBadge()` function (its only caller was the removed BUY/TRADE row).

### Second fix pass (owner live-session screenshots, same day)

- **Confirmed company name works end-to-end**: owner added a new symbol ("ETERNAL") and its real name ("ETERNAL - ZOMATO") rendered correctly immediately. Investigated why *existing* symbols still showed nothing: a pre-existing (not introduced this session) invalid candidate symbol `INFSDFSD` in `owner_candidates` (added 2026-07-26) has been failing every scheduled cycle tick at the exact point the instrument catalog rebuilds — `KiteProvider._ensure_catalog()` raises `ProviderError` before any `upsert_instrument` call can run, so the scheduled catalog refresh (and name backfill) never completes. New/re-validated symbols go through a different, unblocked path. Flagged to the owner as a separate pre-existing issue, not fixed here.
- **Market Intelligence button removed** from the identity row's actions (redundant with the sidebar nav item — both just call `switchTab("market")`); its click handler deleted.
- **Open Chart/Compare relocated as icon-only buttons** in the header-actions row, next to Re-validate — same ids/click handlers moved, only the markup/label changed (owner: "icons are also sufficient"). With no buttons left in it, `.decision-brief-actionbar` was removed entirely — HTML element, the `decisionBriefActionbar` JS ref and its two hidden-toggle lines, and the CSS rules (including its entry in the `[hidden]` display-override list).
- **Fix pass: Expected R:R tile truncation.** 5 tiles in a 4-column grid wrap the last one (Expected R:R) onto its own row with only 1/4 the width — "reward per ₹1 risked" was truncating next to empty space. `.decision-brief-gauges .brief-gauge:last-child { grid-column: 1 / -1; }` lets it span the full row.

### Third fix pass (owner live-session screenshot, same day)

- **Company name truncation on the identity row itself** ("SANDHA…") — too many competing elements (star, ticker, as-of, icon buttons) in the center column's narrower width. Moved `#decision-brief-company-name` into the meta row instead, next to "NSE: SANDHAR" — verified via `scrollWidth === clientWidth` (no overflow) that long real names ("Sandhar Technologies Limited") now render in full.
- **Re-confirmed sector/market-cap are genuine gaps** — re-checked `Instrument`, config, and Kite's exact dump columns a second time on direct owner follow-up; nothing new found. **Owner decision reconfirmed: leave omitted, track as future scope.**

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html` — tabstrip button split; Recommendation tile added to the gauges row; new `#decision-summary-card` + `#executive-summary-modal`; `#decision-executive-summary` moved into the modal as static HTML; identity row redesigned (favorite toggle, company name, meta row, overflow menu with the 4 moved action buttons; BUY/TRADE chip spans removed); cache-bust `9.49.4` → `9.51.1`.
- `src/athena/api/static/js/13-decision-brief-core.js` — Decision Timeline section removed from the hero template; Response tabpane split into Response (Journal only) + new History tabpane (Timeline + Analogs); Recommendation tile + Summary card populated synchronously in `renderDecisionBrief()`; `renderDecisionBriefEmpty()` resets both; `.decision-brief-hero`/`.decision-banner` removed from the template entirely; View Details/modal-close/backdrop-click wiring added; favorite-toggle wiring (`loadSavedSymbolsCache`/`applyFavoriteToggleState`) + overflow-menu toggle/close wiring added; company-name/exchange-symbol population added; stance-chip/type-chip population removed.
- `src/athena/api/static/js/14-decision-brief-analysis.js` — `renderCockpitGauges()`/`resetCockpitGauges()` also populate/reset the Recommendation tile's qualifier band, reusing the Score tile's own computed value.
- `src/athena/api/static/js/18-decision-brief-trace.js` — `BRIEF_TAB_NAMES`/`BRIEF_TAB_LABELS` updated for the 5th tab.
- `src/athena/api/static/js/06-ui-helpers.js` — `closeAllModals()` now also closes `#executive-summary-modal`.
- `src/athena/api/static/js/07-decision-format.js` — dead `decisionTypeBadge()` removed (its only caller, the removed type-chip span, is gone).
- `src/athena/api/static/css/09-decision-brief-shell.css` — `.decision-summary-icon` tone coloring, `.decision-summary-details-btn` right-alignment, `.brief-gauge-recommendation` spacing + stance-tinted background/text; dead `.decision-brief-hero` rule removed; `.favorite-toggle-btn`/`.decision-brief-company-name`/`.decision-brief-meta-row`/`.decision-brief-exchange-symbol`/`.decision-brief-overflow-*`/`.overflow-menu-item*` added; `.decision-brief-symbol-lg` gained `flex-shrink: 0` (fix pass).
- `src/athena/domain/market.py` — `Instrument.name: str | None = None`.
- `src/athena/data/store/schema.py` — `SCHEMA_VERSION` 8→9; `instruments` DDL gained `name TEXT` (fresh dbs).
- `src/athena/data/store/repository.py` — `_migrate_instruments_name_column()` (idempotent `ALTER TABLE`, reaches existing dbs); `upsert_instrument`/`get_instrument`/`list_instruments` SQL updated for the new column.
- `src/athena/data/store/serialization.py` — `instrument_to_row`/`row_to_instrument` updated for `name`.
- `src/athena/data/providers/kite_provider.py` — reads Kite's real `name` column (previously discarded).
- `src/athena/data/providers/file_provider.py` — reads an optional `name` CSV column, for offline/test parity.
- `src/athena/api/v1/dtos/decisions.py` — `DecisionMetadataDTO.instrument_name`.
- `src/athena/api/v1/services/decisions_service.py` — optional `repo` constructor param; `_lookup_instrument_name()`.
- `src/athena/api/dependencies.py` — `get_decisions_service` passes `repo=app.state.sqlite_repo`.
- `tests/api/platform/test_dashboard_hosting.py` — ~35 new/updated assertions total (tab count/order/labels, Response/History content-placement structural check, hero/banner-removed-from-template check, Recommendation tile, Summary card, View Details modal wiring, identity-row redesign, overflow menu, action-bar decluttering).
- `tests/data_layer/test_repository.py` — 3 new tests (`name` roundtrip, absent-reads-as-None, pre-existing-db migration).
- `tests/data_layer/test_kite_provider.py` — 1 new test (`name` captured from the Kite dump fixture).
- `tests/api/v1/test_decisions_instrument_name.py` — new file, 3 tests (`instrument_name` populated/None/no-repo).
- `tests/data_layer/test_decision_journal.py`, `tests/runtime/test_dry_run_schedule.py` — `SCHEMA_VERSION == 8` → `9` (legitimate bump, not a regression).
- This log; `docs/MILESTONES.md`.

### Public APIs

- No new endpoints. `GET /api/v1/decisions/{id}` and `GET /api/v1/decisions` response shape gained `metadata.instrument_name` (additive-only, nothing removed/renamed).

### Validation and architecture

- Full regression: **1042 passed** (1035 + 7 new backend tests). Ruff clean (pre-existing, unrelated issues only: `SIM117` in `repository.py` predates this change, confirmed via diff).
- JS syntax verified (`node --check` on the reassembled script). HTML div-balance re-verified after every edit.
- Schema migration verified safe two ways: (1) a dedicated test that builds a pre-migration db (old column set, a real row) and confirms `initialize()` adds the column in place without touching existing data; (2) direct inspection of the real `db/athena.db` after the test suite's own real-db wiring exercised it live — 506 rows preserved, `name` column present, all `NULL` as expected.
- No ADR required: the schema/ingestion change is a normal additive column for a real field Kite already provides — not a new architectural pattern, provider, or business-logic addition. Everything else (identity row) is presentation-only, reusing the existing Saved Symbols service as-is.

### Risks and technical debt

- Could not exercise the full tabpane content (Response/History) against a real, authenticated decision selection end-to-end — verified via a structural source-slice test plus live tabstrip click-wiring, same constraint as every prior milestone (no owner credentials available to the AI).
- "Spacing polish" (the other half of this milestone's name) was intentionally limited to the concrete win here (removing Decision Timeline from the always-visible hero) rather than speculative CSS tweaking across Trade Plan/Analysis/Market Context with no concrete target — matches the pattern established this session (DT-1/DT-2 polish was always owner-screenshot-driven, not guessed at).
- Existing instruments (all 506 in the real db) will show no company name in the dashboard until the next Kite instrument-catalog refresh runs and re-upserts them — not a bug, just a natural consequence of the migration being additive rather than a backfill. The UI gracefully shows nothing (no name span rendered) rather than a placeholder.
- Restarted the live `athena-serve --with-cycles` process to load the new backend code (same as the earlier Holding Period feature this session) — a scheduled cycle tick was interrupted, consistent with prior restarts this session.

### Remaining work

- **Owner review** on the live dashboard: click through all 5 tabs on a real decision, confirm Response shows only the journal/outcome form and History shows Timeline + Similar past setups together; confirm the merged Recommendation+gauges tile, the ATHENA Summary card with "View Details", and the redesigned identity row (star toggle, company name once a catalog refresh populates it, "NSE: SYMBOL" meta row, overflow menu) all render as expected; flag any specific spacing/hierarchy issue for a targeted follow-up (rather than the AI guessing at "polish").
- Then proceed to DT-4 (Reasoning Trace redesign + Similar Trades sparkline) once approved.

### Commit message

```text
feat(dashboard): DT-3 — split Decision History into Response + History
tabs

- Split the tabstrip's single "Decision History" button into "Response"
  (Journal/Outcome only) and a new "History" (Decision Timeline +
  Similar past setups) — matches the milestone scope agreed at the
  start of the workstation refactor assignment.
- Move Decision Timeline out of the always-visible hero section (it
  rendered on every tab regardless of which was active) into the new
  History tab — a real fix for the assignment's "Remove Vertical
  Wasted Space" principle, not just a relabeling.
- Move Similar past setups (Analogs) out of Response into History,
  alongside the Timeline — recording a response is a distinct action
  from browsing history; Response now holds only the Journal panel.
- Extend BRIEF_TAB_NAMES/BRIEF_TAB_LABELS for the 5th tab; no backend
  change, no content removed or invented, purely a regroup of already-
  rendered sections.
- Merge ATHENA Recommendation into the gauges row as its own tile
  (stance badge + a qualifier band reusing the Score tile's own
  computed word, e.g. "Good Setup") — matches the reference mock's
  hero hierarchy, requested after reviewing the live build.
- Collapse the always-visible Executive Summary bullet list into an
  "ATHENA Summary" card (same real one-line headline, now positioned
  between the gauges and the tab strip) with a "View Details" button
  that opens the full breakdown in a modal — reuses the existing
  openModal/closeModal pattern (Compare/Chart/Backtest), no new modal
  architecture. Fixes the same always-repeats-on-every-tab issue this
  milestone had just fixed for Decision Timeline.
- Remove the now-empty .decision-brief-hero wrapper and its dead CSS
  rule; no backend change, no content invented — same real headline
  and bullet computations, only repositioned and collapsed.
- Redesign the identity row to match the reference mock: star favorite
  toggle (reuses the existing Saved Symbols GET/POST/DELETE endpoints,
  Priority-2, no new backend), real company name + "EXCHANGE: SYMBOL"
  meta row, BUY/TRADE badges dropped (redundant with the Recommendation
  tile), secondary actions (Dismiss today/Remove candidate/Export/News)
  moved into a "more" overflow popover — same buttons relocated, not
  rebuilt.
- Add Instrument.name: Kite's real instrument dump has always carried a
  company-name column that ingestion discarded. Bump SCHEMA_VERSION
  8->9 with an idempotent ALTER TABLE migration (reaches the existing
  production db safely, verified against a simulated pre-migration db
  and against the real db/athena.db — 506 rows preserved, name column
  added, all NULL until the next Kite catalog sync populates them, never
  fabricated). Sector and market-cap category are genuine gaps with no
  fix available in Kite's feed — omitted, tracked as future scope.
- Fix pass: the ticker truncated to "DI..." once the company name sat
  next to it (flexbox shrinking both siblings by default) —
  .decision-brief-symbol-lg now has flex-shrink: 0 so the primary
  identifier never loses space to the secondary one.
- Remove the Market Intelligence button (redundant with the sidebar nav
  item of the same name); relocate Open Chart/Compare as icon-only
  buttons next to Re-validate (owner: "icons are also sufficient").
  With no buttons left in it, remove decision-brief-actionbar entirely
  (HTML/JS/CSS) — a further real vertical-space win.
- Fix pass: "reward per ₹1 risked" was truncating on the Expected R:R
  tile, which only got 1 of 4 grid columns' width when it wrapped alone
  onto row 2 — .brief-gauge:last-child now spans the full row.
- Fix pass: company name was still truncating on the identity row
  itself once cramped next to the star/ticker/as-of/icon buttons — move
  it into the meta row (alongside "NSE: SYMBOL") where it has far more
  room; verified no overflow via scrollWidth === clientWidth.
- Re-confirm sector/market-cap category are genuine gaps (re-checked
  Instrument, config, and Kite's exact dump columns a second time) —
  owner reconfirmed: leave omitted, track as future scope.
- Give the symbols panel a single, calibrated color system across
  three iterations. (1) Section headers (Trade/Watch/No trade/...) had
  no background — flush with the rows below. (2) First attempt reused
  each section's raw alert-style dot color as a color-mix() full-block
  tint — pure yellow (Watch) overpowered green (Trade) at the same
  opacity. (3) Balanced the hues, but 3-4 stacked solid blocks still
  read as "too much color" overall. Final: thin left-border accent +
  barely-there wash (same restrained pattern as the Recommendation
  tile/ATHENA Summary card), and the exact same accent applied to
  individual .symbol-row rows (decisionCardStanceColor()), which had
  the identical fully-opaque-3px-border problem, loud across a dozen+
  stacked rows. Hover uses filter: brightness(1.25).
```

---

## DT-2 — Hero header + Quick Summary + ticker strip (APPROVED)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | Second milestone of the owner's "ATHENA Workstation Refactor": rearrange the hero header hierarchy, build a "Quick Summary" card from existing data only, and add a market ticker strip — per an explicit data-source priority (reuse ATHENA's existing pipeline first; stop and present any gap rather than fabricate or silently add a new external integration) |
| Scope | `src/athena/api/v1/dtos/market.py`, `src/athena/api/v1/services/market_history_service.py`, `src/athena/api/v1/routers/market.py`, `src/athena/api/dependencies.py`, `src/athena/api/static/index.html`, `src/athena/api/static/js/03-app-shell.js`, `src/athena/api/static/js/13-decision-brief-core.js`, `src/athena/api/static/js/19-decision-brief-history.js`, `src/athena/api/static/css/03-shell.css`, `src/athena/api/static/css/09-decision-brief-shell.css`, `src/athena/api/static/css/13-context-history.css` |
| Tests | 4 new backend tests + 2 existing analog-aggregate tests extended with real min/max holding-day assertions + ~35 new dashboard-hosting assertions. Full suite **1035 passed** |
| Coverage | Live-browser verified: ticker shows/hides correctly per active tab via real nav clicks; graceful all-`None`/"—" fallback confirmed when the endpoint 401s (no owner credentials for a real fetch); Quick Summary card visually confirmed via injected sample data |
| Status | **✅ Approved** (2026-07-27) |
| Branch | feature/live-dashboard |

### Research phase: what does ATHENA already have?

Before writing any ticker code, dispatched research (not implementation) to verify the owner's stated priority — reuse existing data, only propose new infrastructure for a genuine gap:

- **NIFTY 50 / BANK NIFTY / India VIX**: all three have a real live level (`KiteMarketDataProvider.market_snapshot()` already fetches all three into `MarketSnapshot.indices`/`.india_vix`) **and** real persisted daily candles (`index_instruments`/`india_vix_instrument` are always included in the ingestion catalog, confirmed directly against the live DB: `NSE:NIFTY 50`, `NSE:NIFTY BANK`, `NSE:INDIA VIX` all have candle rows). Neither the level nor a day-change % required any new provider — only a small new endpoint to expose what already exists (Priority 2 per the owner's own rule) plus simple derived arithmetic over already-persisted values.
- **Market breadth (ADV/DEC)**: genuine gap. `MarketSnapshot.breadth_advances`/`breadth_declines` exist as domain fields, but the live Kite provider hardcodes both to `0` — Kite Connect's quote API has no advancers/decliners concept at all. **Decision (owner): omit from the ticker, track as future scope** rather than propose a new external feed as part of this milestone.
- **Overall Market Health score**: the Market Intelligence tab's existing "Market Health" gauge has silently shown a hardcoded `0/100` forever — `_regime_to_payload()` (`src/athena/ops/owner_validation.py`) never merges in the real `MarketHealthEngine.assess()` result. Investigating *what that real result actually is* revealed it's not a fixable wiring bug the way it first looked: `MarketHealthAssessment` has no scalar 0-100 field at all, only 4 categorical dimension labels (Breadth/Trend Quality/Momentum/Volatility). Synthesizing a single score from those labels would be new business logic, not a data-exposure fix. **Decision (owner): omit from the ticker, drop the fake gauge for now, track as future scope.**

### Scope completed

- **Backend (Priority-2 exception — small, additive, no new provider/architecture)**:
  - `MarketIndexTickerDTO` (label/level/change_pct, all `Optional`) and `MarketTickerDTO` (nifty/bank_nifty/india_vix/as_of) in `dtos/market.py` — docstrings explicitly record why breadth and an overall health score are excluded, so a future reader doesn't mistake the omission for an oversight.
  - `MarketHistoryService.market_ticker()`: reads `repo.get_latest_snapshot()` for each index's live level, then `repo.list_candles_recent(instrument_id, Timeframe.D1, limit=5)` filtered to the most recent candle strictly before the snapshot's own trading day, as the prior-close baseline for `change_pct = (level - baseline) / baseline * 100`. Returns `None` for any field whose underlying data isn't available — never a fabricated 0.
  - `GET /api/v1/market/ticker` (`routers/market.py`, `Permission.READ`) — thin, delegates entirely to the service.
  - `MarketHistoryService` gained an optional `repo: SqliteRepository | None` constructor param (mirrors the existing `CandidatesService`/`DecisionsService` precedent of accepting a raw repo alongside a primary provider abstraction for secondary read needs); wired from `app.state.sqlite_repo` in `get_market_history_service`.
- **Frontend — header ticker**: `#header-market-ticker` in the shared `.console-header` (outside any tab-pane), hidden by default; `switchTab()` shows it only when `tabId === "decisions"`; `loadTabData()`'s "decisions" branch calls the new `loadMarketTicker()` — the one new fetch approved for this page, never triggered by any other tab.
- **Frontend — Quick Summary**: `renderSidebarQuickSummary()` (UX-6's sidebar score/confidence/risk strip) expanded — not duplicated alongside a second new section — with R:R Potential (`decision.trade_plan.risk_reward`, same `formatDecisionRatio` already used on the Trade Plan tab), Expected Return (same `computeExpectedReturnPct` already used there too — never a second, independently-derived calculation), and Historical Analogs' Win Rate/Avg Holding, both explicitly labeled "(Historical)" since no forward-looking per-decision holding-period field exists anywhere in ATHENA — this is honestly a real average across similar past trades, not a guarantee for the current one. `loadDecisionAnalogs()` now also calls `renderSidebarQuickSummary()` after it resolves, since Win Rate/Avg Holding depend on that data and nothing previously re-rendered the sidebar for it.
- **Hero header polish**: `.decision-brief-header`/`-row1` gaps widened, `.decision-brief-symbol-lg` font-size increased (`--text-1-2` → `--text-1-4`), a top border/padding added above `.decision-brief-gauges` as a clear visual divider between the identity row and the score/confidence/risk/R:R row — same elements, same data, only spacing/sizing/grouping changed.

### Refinements from owner screenshot review (2026-07-27), before final approval

- **Quick Summary → standalone card.** The owner shared a reference-mock screenshot showing Quick Summary as its own distinct bordered card (own header + stance badge), not inline at the top of the Reasoning Trace card the way it was originally built. Restructured: `#quick-summary-card` is now a sibling `.card` above the Reasoning Trace card inside `.dag-column`; the header (icon + "Quick Summary" title + `#quick-summary-stance` badge) lives in static HTML, and `renderSidebarQuickSummary()` now only toggles the card's visibility, sets the badge's text/class, and fills the metrics rows — it no longer builds a header or symbol line itself. `.dag-column` gained explicit flex sizing (`.quick-summary-card { flex: 0 0 auto }`, the Reasoning Trace card `{ flex: 1 1 auto; min-height: 0 }`) since it now holds two stacked cards instead of one. One deliberate deviation from the mock: it showed "Holding Period: 2-5 Days", but no such range field exists anywhere in ATHENA — only a real historical *average* (`DecisionAnalogsDTO.avg_holding_days`). Kept the honest "Avg Holding (Historical)" label rather than inventing a range to match the mock exactly.
- **Ticker auto-refresh.** Owner asked how often the ticker refreshes; the honest answer was "never automatically" — no `setInterval` exists anywhere in this dashboard, every tab (this one included) only reloads on tab-switch or a manual refresh click. Owner asked for a timer. Added `startTickerRefresh()`/`stopTickerRefresh()` (60s interval via `TICKER_REFRESH_INTERVAL_MS`), started when `switchTab` activates Decisions & Trace and stopped when leaving it — mirrors the existing `stopOpsStream()` start/stop lifecycle already used for the Operations tab's live stream. Deliberately scoped to the ticker only, not the decisions list/briefing (re-fetching those every tick would reset scroll position/selection, which wasn't asked for).
- **Quick Summary value formatting/coloring** (owner reference-mock screenshot, second review pass). Score/Confidence were rendering the same band words the hero gauges already show ("Strong"/"HIGH") — changed to raw numbers, `${scoreView.valueLabel}/100` and `${confidenceView.valueLabel}%`, so this card reads as at-a-glance data rather than repeating the gauge chips. Risk was band-only — changed to `${band} (${valueLabel})` (e.g. "Medium (42.9)"), colored via the shared `.tone-good-text`/`.tone-warn-text`/`.tone-bad-text` utility classes (the same tokens the header ticker's `.positive`/`.negative` colors use). R:R Potential was using the shared `formatDecisionRatio()` (2 decimals, `2.00 : 1`) — switched to `rr.toFixed(1)` to match the hero cockpit gauge's own "EXPECTED R:R" formatting (`2.0 : 1`) instead of introducing a third ratio format. Expected Return gained the same sign-based `tone-good-text`/`tone-bad-text` coloring. Every value still comes from the exact same `analysisPresentation`/`riskBand` computations the hero gauges already use (`depth.score`/`depth.confidence`/`depth.risk`) — this was purely a presentation change, no new number computed anywhere.
- **Holding Period (real range, replacing the fabricated one in the mock).** Owner asked whether ATHENA can provide a real "Holding Period" in days like the mock's "2 - 5 Days". Checked: each returned analog already carries its own real `outcome_holding_days` (from a persisted trade's actual entry-to-exit time), and `DecisionsService._aggregate_analog_outcomes` already collects all of them in memory to compute the average — the min/max across that exact same list was simply never exposed. Added `min_holding_days`/`max_holding_days` to `DecisionAnalogsDTO`, computed alongside the existing average (same method, same input list — no new provider, no new business logic, Priority 1/2). Quick Summary's "Avg Holding (Historical)" row replaced with "Holding Period (Historical): 3 - 7 Days" — a real historical range across similar past trades (collapses to a single number when every analog held for the same length of time), not a fabricated estimate.

### Files created

- None.

### Files modified

- `src/athena/api/v1/dtos/market.py` — `MarketIndexTickerDTO`, `MarketTickerDTO`.
- `src/athena/api/v1/services/market_history_service.py` — `market_ticker()`, `_index_ticker()`, `_prior_close()`; optional `repo` constructor param.
- `src/athena/api/v1/routers/market.py` — `GET /market/ticker`.
- `src/athena/api/dependencies.py` — `get_market_history_service` passes `repo=app.state.sqlite_repo`.
- `src/athena/api/v1/dtos/decisions.py` — `DecisionAnalogsDTO` gained `min_holding_days`/`max_holding_days`.
- `src/athena/api/v1/services/decisions_service.py` — `_aggregate_analog_outcomes()` now also returns min/max holding days from the same collected list.
- `src/athena/api/static/index.html` — header ticker markup; Quick Summary restructured into a standalone card; cache-bust `9.48.0` → `9.49.4`.
- `src/athena/api/static/js/03-app-shell.js` — ticker show/hide in `switchTab`, `loadMarketTicker()`/`renderTickerIndex()`, fetch wired into `loadTabData`'s "decisions" branch; `startTickerRefresh()`/`stopTickerRefresh()` 60s auto-refresh lifecycle.
- `src/athena/api/static/js/13-decision-brief-core.js` — `renderSidebarQuickSummary()` expanded, then restructured to target the standalone card's header badge + body separately, then reworked per-row formatting/coloring and the Holding Period range.
- `src/athena/api/static/js/19-decision-brief-history.js` — `loadDecisionAnalogs()` now also refreshes the sidebar.
- `src/athena/api/static/css/03-shell.css` — `.header-market-ticker`/`.ticker-*` styles.
- `src/athena/api/static/css/09-decision-brief-shell.css` — hero header spacing/hierarchy polish; `.dag-column` flex sizing for two stacked cards; `.quick-summary-card-header`/`.card-header-title`.
- `src/athena/api/static/css/13-context-history.css` — `.dag-quick-summary` restructured for the richer card, then simplified once the header moved to static HTML (dropped `.quick-summary-header`/`.dag-quick-symbol`/`.quick-summary-grid`, dropped the sticky-positioning/margin-bleed hack since it's no longer visually merged into the DAG canvas); removed the now-unused `.dag-quick-metric`.
- `tests/api/v1/test_market_history.py` — 4 new tests (`TestMarketTicker`).
- `tests/api/v1/test_core_apis.py` — 2 existing analog-aggregate tests extended with real min/max holding-day assertions (one exact single-outcome equality, one deterministic 3-day/7-day spread via explicit `closed_ts`).
- `tests/api/platform/test_dashboard_hosting.py` — ~35 new assertions; 1 updated (`.dag-quick-metric` no longer exists).
- This log; `docs/MILESTONES.md`.

### Public APIs

- `GET /api/v1/market/ticker` (READ) — new.
- `GET /api/v1/decisions/{decision_id}/analogs` — response shape additive-only change: `min_holding_days`/`max_holding_days` added alongside the existing `avg_holding_days`, no fields removed or renamed.

### Validation and architecture

- Full regression: **1035 passed** (1031 + 4 new backend tests). Ruff clean.
- Discovered mid-implementation that `create_app()`'s test client always wires the real local `db/athena.db` (no `ATHENA_DB_PATH` override exists in the test fixtures) — a pre-existing characteristic of this test suite, not introduced here. Adjusted the endpoint-level test to assert response *shape* only, not specific values, and did the real value-level testing directly against `MarketHistoryService` with an isolated `tmp_path` `SqliteRepository` instead.
- Two backend test failures along the way, both fixed and re-verified: a foreign-key violation (candles reference `instruments`, so indices need a real `instruments` row too, same as any equity) and the DB-wiring discovery above.
- JS syntax verified (`node --check` on the reassembled script). HTML/CSS balance re-verified after every edit.
- No ADR required: the ticker's backend addition is the Priority-2 exception the owner's own rule pre-approved (expose already-computed data via a small read endpoint — no new provider, no new architecture, no new business logic); everything else is presentation-only.

### Risks and technical debt

- Could not exercise the ticker's real authenticated fetch end-to-end (no owner credentials) — verified via live DOM injection of sample data (exercises the same render path) plus the backend tests' real-repository coverage of the actual arithmetic.
- Market breadth and an overall Market Health score are explicitly tracked as future scope, not fixed here — see the two "Decision (owner)" notes above.
- No new technical debt otherwise.

### Remaining work

- None — owner reviewed on the live dashboard (including restarting the server to pick up the Holding Period backend change, and confirming the field renders correctly with real logged-outcome data) and approved. Proceeding to DT-3.

### Commit message

```text
feat(dashboard): DT-2 — hero header polish, standalone Quick Summary
card, auto-refreshing market ticker

- Add GET /api/v1/market/ticker (NIFTY 50/BANK NIFTY/INDIA VIX, real
  level + real day-change % derived from already-persisted Kite
  snapshot + daily candle data — no new provider, no new calculations
  beyond simple arithmetic). Shown/fetched only on Decisions & Trace,
  auto-refreshed every 60s while that tab is active (owner-requested;
  mirrors the existing Operations-tab stream start/stop lifecycle).
- Explicitly omit market breadth (Kite has no adv/dec data — hardcoded
  0/0 in the live provider, a genuine gap) and an overall Market Health
  score (no scalar aggregate exists anywhere in ATHENA, only 4
  categorical dimension labels — synthesizing one would be new business
  logic) from the ticker; both tracked as future scope instead of
  fabricated.
- Expand renderSidebarQuickSummary (UX-6) with R:R Potential, Expected
  Return, and historical-analogs Win Rate/Holding Period (all
  explicitly labeled "(Historical)") rather than adding a second,
  duplicate section — reuses values already computed/rendered
  elsewhere on the brief, no new fetch or calculation. Restructured as
  its own standalone card (owner reference-mock refinement) rather
  than inline at the top of the Reasoning Trace card.
- Score/Confidence as raw numbers instead of band words, Risk as
  "band (value)" colored by band, R:R at one decimal (matching the
  hero gauge's own formatting), Expected Return colored by sign — all
  from the exact same analysisPresentation/riskBand computations the
  hero gauges already use.
- Add min_holding_days/max_holding_days to DecisionAnalogsDTO, computed
  from the same per-analog outcome_holding_days list
  _aggregate_analog_outcomes already collects for the average — a real
  historical Holding Period range (e.g. "3 - 7 Days"), replacing the
  single-average row, never a fabricated estimate.
- Hero header spacing/hierarchy polish (larger symbol text, clearer
  divider above the gauges row) — same elements, same data.
```

---

## Fix pass — reload-resets-tab regression + collapsible global sidebar (BUILT, awaiting owner confirmation)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | Two owner requests before starting DT-2: (1) a plain browser reload (Cmd+R) was jumping back to Portfolio Overview every time instead of staying on the current tab — a regression from the earlier "tab restored on login" fix, which had been made too broad; (2) a collapsible global sidebar (icon-only when minimized, smooth animation, main content reflows) |
| Scope | `src/athena/api/static/js/03-app-shell.js`, `src/athena/api/static/js/01-auth.js`, `src/athena/api/static/index.html`, `src/athena/api/static/css/03-shell.css` |
| Tests | 6 new dashboard-hosting assertions. Full suite **1031 passed** |
| Coverage | Live-browser verified: sidebar collapse/expand (smooth width transition, main content reflow, icon flip, localStorage persistence across reload). The reload-preserves-tab fix could not be driven through the real end-to-end scenario myself — this deployment requires real owner credentials (the unlock gate stayed visible when I navigated directly to `/dashboard/decisions` without logging in) — verified via direct code review instead, plus a test that explicitly checks `initializeRoute`'s function body no longer contains the force-reset call |
| Status | **BUILT** — sidebar collapse live-verified; reload-tab-persistence awaiting owner confirmation on the real authenticated session |
| Branch | feature/live-dashboard |

### Root cause: reload-resets-tab regression

Earlier this session, the owner reported "sometimes previously selected tab appears after user logins" and asked for every session to always start on Portfolio Overview. The fix changed `initializeRoute()` — called from 3 places — to unconditionally force Overview:

```js
function initializeRoute() {
    window.history.replaceState({ tabId: "overview" }, "", "/dashboard/overview");
    switchTab("overview");
}
```

This was correct for the actual login-form-submit call site, but `initializeRoute()` is *also* called from both branches of `bootstrapSession()` — the silent-restore paths that run on every single page load (auth not required, or an already-valid stored token) — not just on an explicit login. Since a plain reload re-runs `bootstrapSession()`, it now *always* reset to Overview too, which the owner flagged as "very annoying." The original bug and this over-fix are two sides of the same coin: the shared function needed to behave differently depending on *which* of its 3 callers invoked it, and the first fix picked the wrong one to change.

### Fix

- `initializeRoute()` reverted to its original, URL-preserving behavior (parses `window.location.pathname`, defaults to Overview only if the path doesn't match a known tab) — used by both `bootstrapSession()` silent-restore branches.
- A new, separate `resetToOverviewTab()` (the force-to-Overview logic) is called only from the login-form submit handler (`01-auth.js`) — the one call site that represents an actual new login, not a continuation of an existing session.

### Feature: collapsible global sidebar

- New `#sidebar-collapse-toggle` button in `.sidebar-brand`, toggling a `.collapsed` class on `.sidebar`.
- `.sidebar` gains `width: 260px` → `72px` on collapse, with `transition: width var(--transition-speed) ease` — the existing `.console-main { flex-grow: 1 }` reflows into the freed space automatically via normal flexbox layout, no JS recalculation needed for any page's content (Decisions & Trace's 3-column grid included, since its `grid-template-columns` are relative to its own container's width).
- Nav item labels, the "Soon" badges, brand text, and profile info all hidden when collapsed (icons centered); each nav item already had visible text so gained a matching `title="..."` attribute for a hover tooltip once collapsed.
- Preference persisted to `localStorage` (`athena.sidebar-collapsed`), restored on load — same pattern already used for dismissed-decision symbols elsewhere in this file.

### Files created

- None.

### Files modified

- `src/athena/api/static/js/03-app-shell.js` — `initializeRoute()` reverted to URL-preserving; new `resetToOverviewTab()`; new sidebar-collapse toggle logic + localStorage persistence.
- `src/athena/api/static/js/01-auth.js` — login-form submit now calls `resetToOverviewTab()` instead of `initializeRoute()`.
- `src/athena/api/static/index.html` — `#sidebar-collapse-toggle` button; `title="..."` on each nav item; cache-bust `9.47.3` → `9.48.0`.
- `src/athena/api/static/css/03-shell.css` — `.sidebar` width transition + `.collapsed` state and all its descendant overrides (brand text, nav-item labels, footer/profile).
- `tests/api/platform/test_dashboard_hosting.py` — 6 new assertions, including one that inspects `initializeRoute`'s own function body to lock in the corrected (non-forcing) behavior.
- This log; `docs/MILESTONES.md`.

### Public APIs

- None — frontend-only.

### Validation and architecture

- Full regression: **1031 passed**. Ruff clean. JS syntax verified (`node --check` on the reassembled script). HTML/CSS balance re-verified.
- Live-browser verification for the sidebar: expand → collapse → confirm smooth width transition, main content reflow, icon flip, `localStorage` write; reload → confirm collapsed state restored.
- No ADR required: both are small, presentation/behavior-only changes — no domain/contract/schema impact.

### Risks and technical debt

- Could not drive the real reload-preserves-tab scenario end-to-end (no owner credentials for this deployment, which does require real auth) — mitigated by a test that inspects the actual function body rather than just checking the function exists, plus the fact both functions are small and unconditional (no branching to get wrong).
- No new technical debt.

### Remaining work

- **Owner confirmation**: reload while on a non-Overview tab (e.g. Decisions & Trace) and confirm it stays there; confirm logging out and back in still resets to Overview as expected.

### Commit message

```text
fix(dashboard): stop reload from resetting the active tab; add
collapsible sidebar

- initializeRoute() was made to always force Portfolio Overview by an
  earlier fix, but it's shared by 3 callers — bootstrapSession's two
  silent session-restore paths (which also run on every plain reload)
  and the login-form submit. Only the login path should force Overview;
  a reload of an already-active session should stay where it was.
  Revert initializeRoute() to URL-preserving and add a separate
  resetToOverviewTab(), called only from the login-form submit handler.
- Add a collapsible global sidebar (icon-only when minimized, smooth
  width transition, main content reflows automatically via existing
  flex-grow, preference persisted in localStorage).
```

---

## DT-1 — Layout shell: 3-pane workstation (BUILT, awaiting owner confirmation)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | First milestone of the owner's "ATHENA Workstation Refactor" assignment (presentation-layer only, matching a reference trading-workstation mock): replace Decisions & Trace's horizontal outcome carousels + toolbar-above-the-fold layout — which the owner measured as wasting ~300px of vertical space before the selected symbol's details became visible — with a permanent 3-pane layout: left Symbols panel (always visible), center detail (immediately visible, zero scroll), right Reasoning Trace (unchanged this milestone) |
| Scope | `index.html`, `12-decisions-list.js`, `13-decision-brief-core.js`, `09-decision-brief-shell.css`, `12-decision-cards-dag.css`, `03-shell.css` (nav placeholders) |
| Tests | New structural assertions (markup/CSS/JS presence) plus a real div-nesting-depth check for the filter popover (see bug below). Full suite **1031 passed** |
| Coverage | Live-browser verified end to end: 3-pane layout, sample-data row/group rendering, selected-row highlight, collapse toggle, filter popover open/close/click-outside, responsive single-column collapse below 1400px, zero console errors |
| Status | **BUILT** — awaiting owner confirmation on the live dashboard |
| Branch | feature/live-dashboard |

### Scope completed

- **Layout shell**: `.trace-workstation` (2-column grid: brief + trace) became `.decisions-workstation` (3-column grid: `minmax(240px,280px) minmax(0,1.7fr) minmax(280px,1fr)`), with a single responsive breakpoint at 1400px collapsing to one stacked column (each pane capped at `max-height: 70vh`). Header, left panel, and right panel all sticky/full-height via `overflow: hidden` on the grid + independent `overflow-y: auto` inside each pane's own scrollable content — only the center brief body and the left symbol list actually scroll.
- **Left Symbols panel**: new `.symbols-panel` replacing the old `.decisions-toolbar-card` + `#decisions-carousel-groups`. Search stays pinned in a fixed header row; stance/type/sort filters + "Clear all" moved behind a small icon-triggered popover (`#symbols-filter-popover`) so they never consume vertical space above the detail panel — same `<select>`/`<button>` elements and change-listeners as before, only their visibility changed. The summary strip and outcome groups sit below, in the only scrollable region of the panel.
- **Row/group rendering**: `renderDecisionCarousels` (unchanged grouping/priority logic — Trade → Watch → No trade → Insufficient data → anything else, never by timestamp) now appends vertical rows directly into each group instead of a horizontal `scroll-snap` track; the nav-arrow buttons and their `wireCarouselOverflow` edge-fade logic were deleted entirely (dead code once nothing scrolls horizontally). `renderDeckCard` renamed `renderSymbolRow` — identical fields (symbol, score, time, gate-summary note, dismiss button), just a full-width row layout instead of a 156px-wide card.
- **Selected-state strength** (owner: "current selected state is too weak"): `.symbol-row.active` gets a full-row accent gradient wash, a thicker accent-colored left border, `box-shadow` glow, and the symbol text switches to accent color at a slightly larger size — unambiguous at a glance.
- **Scroll-position discipline** (owner requirements): the left panel's `scrollTop` is captured before every `innerHTML` rebuild (search/filter/sort changes trigger a full re-render) and restored after, so typing in search no longer resets the list to the top. `selectBriefing` now also resets only `decisionBriefBody.scrollTop` to 0 on a new selection — the left and right panels keep whatever scroll position they already had.
- **Nav placeholders**: "Reports & Analytics" / "Settings" added to the global sidebar as `.nav-item-disabled` (deliberately not `.nav-item`, so `app-shell.js`'s click-wiring and active-state loops — which only ever query `.nav-item` — never see them at all; no guard needed at any call site), each with a "Soon" badge.

### Bug found and fixed during live verification

The filter popover initially rendered far off-screen (`top: 758px` instead of anchored just below the toggle button). Root cause: `#symbols-filter-popover` was authored as a DOM **sibling** of `.symbols-panel-header` rather than a **child** — since the popover uses `position: absolute`, it resolved against the nearest *other* positioned ancestor up the tree instead of the header. Fixed by nesting the popover inside the header element in the HTML. Added a regression test that checks actual div-nesting depth between the header and the popover (not just that both elements' class/id strings appear somewhere on the page) — a plain substring check would have passed even with the bug present, since both elements still existed in the DOM, just in the wrong place.

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html` — 3-pane layout, left Symbols panel, nav placeholders; cache-bust `9.46.1` → `9.47.0`.
- `src/athena/api/static/js/12-decisions-list.js` — `renderDecisionCarousels` rewritten for vertical rows; `renderDeckCard` → `renderSymbolRow`; `wireCarouselOverflow` deleted; filter-popover toggle wiring added; scroll-position preservation added.
- `src/athena/api/static/js/13-decision-brief-core.js` — `selectBriefing`: `.deck-card` → `.symbol-row` selector update; center-panel-only scroll reset added.
- `src/athena/api/static/css/09-decision-brief-shell.css` — `.trace-workstation` → `.decisions-workstation` (3 columns), `.symbols-panel` sizing rules.
- `src/athena/api/static/css/12-decision-cards-dag.css` — carousel/deck-card CSS replaced with symbols-panel/symbol-row CSS (everything below the DAG/context section, out of DT-1's scope, untouched).
- `src/athena/api/static/css/03-shell.css` — `.nav-item-disabled`/`.nav-item-soon` styles.
- `tests/api/platform/test_dashboard_hosting.py` — updated 3 stale assertions (old class/function names), added new DT-1 structural assertions + the popover-nesting regression test.
- This log; `docs/MILESTONES.md`.

### Public APIs

- None — frontend-only, no backend/API changes.

### Validation and architecture

- Full regression: **1031 passed**.
- Ruff clean. HTML `<div>`/`</div>` count balanced (250/250) before and after every edit. CSS brace balance verified per file. JS reassembled-script syntax verified with `node --check`.
- Live-browser verification (see Coverage above) — this milestone's scale (a full layout restructure) warranted more live checking than the smaller fixes earlier this session, including catching and fixing a real bug (the popover mis-anchoring) before considering it done.
- No ADR required: pure frontend reorganization, no domain/contract/schema change, no architecture drift. Confirmed via the earlier structural research pass that this milestone's scope (layout shell only) doesn't touch the Reasoning Trace's DAG rendering, tab content, or any data/selection logic — those are DT-3/DT-4.

### Risks and technical debt

- Could not exercise a real authenticated end-to-end flow (no owner credentials) — verified via live DOM injection of sample data instead, which exercises the same render functions the real data path uses.
- No new technical debt. The nav placeholders are intentionally inert until DT-2+ (or a future milestone) gives them real destinations.

### Remaining work

- **Owner confirmation** on the live dashboard, then proceed to DT-2 (Hero header + Quick Summary + ticker strip) once approved.

### Commit message

```text
feat(dashboard): DT-1 — 3-pane workstation layout for Decisions & Trace

- Replace the horizontal outcome carousels + toolbar-above-the-fold
  layout with a permanent left Symbols panel (search always visible,
  collapsible BUY/WATCH/PASS-equivalent groups, strong selected-row
  highlight) beside the center detail (now immediately visible, zero
  scroll) and the existing right Reasoning Trace — first milestone of
  the owner's workstation-refactor assignment, matching a reference
  mock. Same data/selection/filter/sort/dismiss logic throughout; only
  DOM position and row/group markup shape changed.
- Move stance/type/sort filters + Clear all behind a small popover so
  they never consume vertical space above the detail panel.
- Preserve left-panel scroll position across re-renders; reset only the
  center panel's scroll to top on a new symbol selection.
- Add two disabled "Reports & Analytics"/"Settings" nav placeholders
  (future implementation, no backing route yet).
- Fix a popover mis-anchoring bug found during live verification (was a
  DOM sibling instead of a child of its position:relative anchor); add
  a regression test that checks actual nesting depth.
```

### Fix pass (owner live screenshots, 2026-07-27)

Once the owner tried the filter popover against real data, four refinements came back:

1. **Excessive vertical gaps between Stance/Type/Sort.** Root cause: each `<label class="decisions-filter-label">` inherited `flex: 1 1 100px` from an unrelated shared rule in `05-portfolio.css` (written for the *old horizontal* toolbar row, where growing to fill available width made sense). Inside the *new vertical* flex popover, that same `flex-grow: 1` stretched every label to fill a third of the popover's total height, producing large empty gaps. Fixed with `flex: none` on `.symbols-filter-popover .decisions-filter-label`. Verified in a live browser: all three labels now measure a consistent 54px tall with ~11px gaps, and the whole popover is 260px tall instead of stretching to fill its container.
2. **"Clear all" read as "clear the filters."** A destructive data-wipe button sitting inside a view-only filter popover was genuinely ambiguous. Moved it to its own separate, danger-red-styled icon button in the panel header, next to (not inside) the filter toggle — same `#decisions-clear-all-btn` id and click handler as before, purely a DOM relocation.
3. **No way to reset filters, and no discoverable way to close the popover.** Added a small popover header row: "FILTERS" title, a "Reset" link (stance/type/sort back to `all`/`all`/`newest`, re-runs `applyDecisionsView()` — distinct from "Clear all," which deletes data), and an explicit close (×) button. Click-outside and Escape already worked; this adds a third, visible way that doesn't require already knowing about the other two. Owner follow-up: Reset should also dismiss the popover afterward (a completed action, not a mid-adjustment) — added.
4. **No visual differentiation, and the list stayed clickable underneath.** Added `#symbols-filter-backdrop`, scoped to the list area only (wrapped `.symbols-summary-strip` + `.symbols-groups` in a new `.symbols-panel-body` container as its positioning/z-index context — the header with search/filter/clear-all stays outside it and always interactive). Shown/hidden in lockstep with the popover. Verified in a live browser via `document.elementFromPoint()` at a coordinate within the backdrop's rect but below the popover's own footprint: the backdrop element itself is what receives the click, not the symbol row underneath — confirming rows are genuinely non-interactive while filtering, not just visually dimmed.

11 new dashboard-hosting assertions (flex-none rule present, danger-icon-button class present, reset/close ids and JS wiring present, backdrop id/CSS/JS present, Reset's click handler contains a call to close the popover). Full suite **1031 passed**. Ruff clean. JS/CSS/HTML balance re-verified after every edit.

**Files modified in this fix pass**: `src/athena/api/static/index.html` (popover header row, separate Clear-all button, `.symbols-panel-body` wrapper, backdrop element; cache-bust `9.47.0` → `9.47.3` across the round), `src/athena/api/static/js/12-decisions-list.js` (`closeSymbolsFilterPopover()` helper, reset/close/backdrop wiring), `src/athena/api/static/css/12-decision-cards-dag.css` (`flex: none` fix, danger-icon-button, popover-head/reset/close, `.symbols-panel-body`, `.symbols-filter-backdrop`), `tests/api/platform/test_dashboard_hosting.py` (11 new assertions).

---

## Fix pass — stale Reasoning Trace sidebar after Clear all + tab restored on login (BUILT, awaiting owner confirmation)

| | |
|---|---|
| Completed | 2026-07-27 |
| Objective | Two bugs the owner found via a live screenshot right after the dashboard.js split shipped: (1) after "Clear all," the Reasoning Trace sidebar kept showing the previously selected symbol's score/confidence/risk chips and a stale DAG stage-detail card ("Regime / COMPLETED / regime-NIFTY 50-2026-07-24T15:30:00+05:30"); (2) login sometimes reopened whatever tab was active before instead of always landing on Portfolio Overview |
| Scope | `src/athena/api/static/js/13-decision-brief-core.js` (`renderDecisionBriefEmpty`), `src/athena/api/static/js/03-app-shell.js` (`initializeRoute`) |
| Tests | 4 new dashboard-hosting assertions. Full suite **1031 passed** |
| Coverage | Both fixes verified correct by direct code inspection (each is a small, unconditional function with no branching) plus a live in-browser check confirming `history.replaceState` behaves as expected in this exact browser. Could not drive a real authenticated login or a real Clear all end to end myself — this deployment requires real owner credentials, unlike the earlier no-auth dev assumption this session had been testing against |
| Status | **BUILT** — awaiting owner confirmation on the live dashboard (trigger a real Clear all and confirm the sidebar goes empty; log out/in and confirm Overview always opens) |
| Branch | feature/live-dashboard |

### Root cause: Bug 1 (stale Reasoning Trace sidebar)

`renderSidebarQuickSummary()` already had correct logic to hide itself
when there's no active decision (`if (!decision || !decision.metadata) {
dagQuickSummary.style.display = "none"; ... return; }`) — but nothing ever
called it again after "Clear all" nulled `activeDecisionData`, so the DOM
just kept showing whatever it had last rendered. The DAG stage-detail
panel (`dagDetailsPanel`, populated by `showStageDetails` when a trader
clicks a DAG node) had no reset path at all — it defaults to
`display: none` in the HTML but nothing ever set it back once a stage had
been shown.

Rather than patch the three call sites that can lead to an empty brief
(Clear all, zero-filter-results in `applyDecisionsView`, and a failed
decision-detail fetch in `loadDecisionDetail`) individually, the fix
centralizes the reset inside `renderDecisionBriefEmpty()` — the one
function whose entire purpose is "there is no decision to show" — so any
future caller gets this for free too:

```js
activeDecisionData = null;
selectedStageId = null;
renderSidebarQuickSummary();
if (dagDetailsPanel) dagDetailsPanel.style.display = "none";
```

### Root cause: Bug 2 (tab restored on login)

`initializeRoute()` (called once, at the end of `bootstrapSession()` or
after a successful login) used to read `window.location.pathname` to
decide which tab to open:

```js
function initializeRoute() {
    const pathParts = window.location.pathname.split("/");
    const pathTab = pathParts[pathParts.length - 1];
    if ([...].includes(pathTab)) switchTab(pathTab);
    else switchTab("overview");
}
```

If the browser's address bar still pointed at, say, `/dashboard/decisions`
(left over from a session that expired while on that tab, or simply
because the browser was closed there), this would reopen that same tab
after the next login — even though the existing logout handler already
explicitly resets navigation to Overview
(`window.history.replaceState({tabId: "overview"}, "", "/dashboard/overview")`)
specifically so "the next session always lands on Portfolio Overview,
never wherever the previous session happened to be." `initializeRoute()`
just never got the same treatment. Confirmed via `grep` that
`initializeRoute` has exactly 3 call sites, all inside the post-auth
bootstrap flow — never used for normal in-session tab navigation (that
goes through `switchTab` directly via nav clicks and the `popstate`
handler) — so it's safe to make it unconditional:

```js
function initializeRoute() {
    window.history.replaceState({ tabId: "overview" }, "", "/dashboard/overview");
    switchTab("overview");
}
```

### Files created

- None.

### Files modified

- `src/athena/api/static/js/13-decision-brief-core.js` — `renderDecisionBriefEmpty` now clears `activeDecisionData`/`selectedStageId`, re-invokes `renderSidebarQuickSummary()`, and hides `dagDetailsPanel`.
- `src/athena/api/static/js/03-app-shell.js` — `initializeRoute()` always resets to Overview instead of reading the current URL.
- `src/athena/api/static/index.html` — cache-bust `9.46.0` → `9.46.1`.
- `tests/api/platform/test_dashboard_hosting.py` — 4 new assertions.
- This log; `docs/MILESTONES.md`.

### Public APIs

- None — frontend-only.

### Validation and architecture

- Full regression: **1031 passed**.
- JS syntax validated (`node --check`) on the full reassembled script after the edit.
- Live-server check: served `/dashboard/dashboard.js` confirmed to contain the fix; zero console errors on a fresh load.
- Live-browser check: loading `/dashboard/decisions` directly and confirming `window.history.replaceState` itself behaves as expected in this browser (updates `window.location.pathname` immediately) — could not complete the actual authenticated login flow myself, since this deployment (unlike the earlier no-auth dev assumption this session had been testing against) requires real owner credentials. Both fixes are small, unconditional functions with no branching, so direct code inspection carries most of the confidence here.
- No ADR required: two small, targeted bug fixes, no architecture/contract change.

### Risks and technical debt

- Neither fix could be exercised through a real authenticated session (no owner credentials) — the owner should confirm both live: trigger a real "Clear all" and confirm the Reasoning Trace sidebar goes fully empty (no stale chips or stage-detail card); log out and back in (or let a session expire) and confirm Portfolio Overview always opens regardless of which tab was open before.
- No new technical debt.

### Remaining work

- **Owner confirmation**: both fixes, live.

### Commit message

```text
fix(dashboard): clear stale Reasoning Trace sidebar and always reset to
Overview on login

- renderDecisionBriefEmpty() now nulls activeDecisionData/selectedStageId,
  re-invokes renderSidebarQuickSummary(), and hides the DAG stage-detail
  panel — previously nothing re-ran these after Clear all (or a
  zero-filter-results state, or a failed decision-detail fetch), so the
  sidebar kept showing the last-selected symbol's score/confidence/risk
  chips and a stale "Regime / COMPLETED" detail card.
- initializeRoute() now always resets to /dashboard/overview instead of
  reading window.location.pathname — a stale URL left over from a prior
  session (e.g. one that expired while on /dashboard/decisions) could
  reopen that same tab on the next login instead of Portfolio Overview,
  the one guarantee the logout handler already made but login didn't.
```

---

## Refactor — dashboard.js concern-based split (BUILT, verified)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Owner flagged `dashboard.js` at 6,108 lines in one file and asked whether that's maintainable — same complaint that drove UX-7's `dashboard.css` split into 14 `css/*.css` files. Owner then explicitly asked to refactor it properly and verify properly, mirroring that precedent |
| Scope | Split the single-closure script (everything lived inside one `document.addEventListener("DOMContentLoaded", () => {...})`) into 22 concern-based files under `src/athena/api/static/js/`, reassembled server-side into the exact original script via a new FastAPI route |
| Tests | New `test_dashboard_js_assembled_losslessly_from_concern_split` (re-derives the expected assembly from the live files every run, spot-checks functions across the concern spread, confirms the wrapper closure and final `bootstrapSession()` ordering survive). Full suite **1031 passed** |
| Coverage | A standalone verification script (not part of the shipped app) parsed the original file's AST, proved 100% statement coverage across the 22-file partition (no gap, no duplicate), and did a full content-equality check — every one of 372 original top-level statements confirmed byte-identical at its new position. The live server's actual response was then diffed against that verified reference and found byte-identical |
| Status | **BUILT** — verified via a mechanical content-equality proof (stronger than a visual diff) plus a live browser smoke test (zero console errors, all 5 tabs exercised via real click handlers). Old monolithic `dashboard.js` deleted (fully superseded) |
| Branch | feature/live-dashboard |

### Why this needed a different approach than the CSS split

UX-7's CSS split was purely mechanical and losslessly verified because CSS
has no scoping or circular-dependency concerns — cutting `dashboard.css`
into 14 files and loading them via `@import` changes nothing about how the
cascade resolves. `dashboard.js` is not like that: the whole file lives
inside one JS closure, and a structural analysis (via a dedicated research
pass reading the entire 6,108-line file) surfaced real coupling that a naive
split into genuine ES modules (`<script type="module">`, real
`export`/`import`) would have had to resolve with actual code changes, not
just code moves:

- Shared mutable `let` state (`activeDecisionId`, `activeDepth`,
  `activeContextData`, etc.) gets reassigned directly from `selectBriefing`
  and various `load*` functions across what would become module boundaries —
  ES module imports are read-only live bindings, so this would need setter
  functions at ~10 call sites, not a bare move.
- A genuine 3-way cycle: the DAG/trace renderer reads `activeDepth` (owned
  by the analysis renderer) and `activeContextData` (owned by the context
  renderer) to paint each node's live status, while both of those call back
  into the DAG renderer to refresh it after their own async loads resolve.
- `ui-helpers.js`'s `closeAllModals()` hardcodes four different modals' DOM
  ids spanning three unrelated feature areas.
- A real `auth.js` ↔ `api-client.js` cycle (`apiRequest` needs auth's token
  helpers; `auth.js`'s `bootstrapSession`/`fetchMe` call `apiRequest`).

None of this is unsafe today — it's one shared closure, so it all just
works — but real ES modules would require fixing all four points with
actual behavioral changes, verifiable only by manual testing (this app has
no JS test framework, and I have no owner credentials to drive a full
authenticated smoke test). The owner was given this trade-off explicitly and
chose the lower-risk option: **reorganize the source into concern-based
files but keep the exact original runtime structure** (one closure, same
statement order semantics), reassembled server-side rather than via
`<script type="module">` — verified with a mechanical proof strictly
stronger than "looks the same," rather than relying on manual smoke-testing
alone.

### How the split was built (mechanical, not hand-transcribed)

1. Installed Node 26 (via Homebrew — the pre-existing Node in this
   environment was v8.9.0 from 2017 and couldn't even parse the file's
   optional-chaining syntax) and the `acorn` JS parser, used only as an
   authoring-time tool for this refactor — not a new runtime or build
   dependency; the shipped app remains vanilla JS with zero build step.
2. Parsed the original file's AST to get the exact character range of every
   one of its 372 top-level statements inside the `DOMContentLoaded`
   callback — avoids any risk of a hand-counted line range being wrong
   around a template literal's `${...}` braces.
3. Authored a partition table assigning contiguous ranges of statement
   indices to 22 target files (by concern: auth, kite-gate, app-shell,
   api-client, utils, ui-helpers, decision-format, portfolio,
   market-intelligence, strategies-backtests, decision-state,
   decisions-list, decision-brief-core/analysis/context/chart/trace/history,
   decision-compare, operations, plus a tiny final `bootstrap.js` holding
   only the very last two statements — the Escape-key listener and the
   final `bootstrapSession();` call, which must stay last).
4. A script verified the partition covers all 372 indices exactly once,
   then **sliced the original source directly** (no retyping) into each
   target file.
5. Reassembled the 22 files (+ `_header.js`/`_footer.js`, also sliced
   directly from the original, never hand-typed) in the new file order and
   proved equivalence: re-parsed the reassembled output, and for every one
   of the 372 original statements, confirmed its exact source text appears,
   unaltered, at the position implied by the new file order. Also confirmed
   the total non-whitespace character count matches exactly end to end.

### Files created

- `src/athena/api/static/js/00-state-and-dom.js` through `21-bootstrap.js`
  (22 files) + `_header.js` / `_footer.js`.
- `tests/api/platform/test_dashboard_hosting.py`'s new test (see below).

### Files modified

- `src/athena/api/app.py` — `DASHBOARD_JS_PARTS` tuple, `assemble_dashboard_js()`,
  and a `GET /dashboard/dashboard.js` route registered ahead of the
  `StaticFiles` mount so this one path is served by concatenation instead of
  a (now nonexistent) single static file.
- `tests/api/platform/test_dashboard_hosting.py` — new
  `test_dashboard_js_assembled_losslessly_from_concern_split`.
- `src/athena/api/static/index.html` — cache-bust `9.45.0` → `9.46.0`.

### Files deleted

- `src/athena/api/static/dashboard.js` (the 6,108-line monolith — fully
  superseded by `static/js/*.js` + the new route; confirmed nothing else in
  the codebase referenced its raw file path before deleting).

### Public APIs

- None — the served `/dashboard/dashboard.js` URL and its content are
  unchanged from the trader's/browser's perspective. No backend/domain API
  touched.

### Validation and architecture

- Full regression: **1031 passed**.
- Ruff clean on `app.py` and the modified test file.
- Live-server verification: restarted the API, fetched the real
  `/dashboard/dashboard.js` response, and diffed it byte-for-byte against
  the independently-verified reassembly — identical. Repeated after
  deleting the old monolith to confirm the route has zero dependency on the
  now-deleted file.
- Live browser verification: zero console errors on a fresh, uncached page
  load (confirmed in a brand-new browser tab to rule out a stale
  console-log buffer from an earlier tab); all 5 sidebar tabs successfully
  switched via their real, wired click handlers (not synthetic CSS-class
  pokes), each correctly triggering its own `load*` function; the only
  logged errors were the pre-existing, expected `console.error` calls for
  unauthenticated API calls (since I have no owner credentials to complete
  a real login) — no `ReferenceError`/`TypeError`/`SyntaxError` anywhere,
  which is exactly the failure signature a broken split would produce.
- No ADR required: purely additive/organizational — no domain, contract, or
  schema change; the frozen ATHENA-002 architecture is untouched. The one
  backend change (a route ahead of the `StaticFiles` mount) is a serving
  mechanism, not an architectural boundary.

### Risks and technical debt

- The server now reads and concatenates 22 files on every request to
  `/dashboard/dashboard.js` instead of serving one static file — negligible
  cost for a single-owner localhost app (~280KB total, no measurable
  latency change observed), but noted for completeness.
- If a future edit adds a new top-level statement, it must go into the
  right concern file and — if it's an immediately-executing statement that
  isn't inside a function/event-handler body — the author should keep the
  same discipline: everything up to the final `bootstrap.js` still executes
  before `bootstrapSession()` runs, which must stay the last statement.
  `DASHBOARD_JS_PARTS` in `app.py` is the single source of truth for the
  concatenation order.
- I could not exercise a real authenticated session (no owner credentials) —
  verified via the mechanical content-equality proof (which does not depend
  on authentication at all) plus everything reachable pre-login/via a
  client-side gate bypass for visual/wiring checks only.

### Remaining work

- **Owner confirmation**: use the live dashboard as normal for a while
  (all tabs, Decision Brief, journal, chart, compare, saved symbols,
  validate) and confirm nothing behaves differently than before — the
  content-equality proof means it shouldn't, but only real day-to-day use
  can confirm.

### Commit message

```text
refactor(dashboard): split dashboard.js into 22 concern-based files

- dashboard.js had grown to 6,108 lines in one closure (owner-flagged,
  same complaint that drove the UX-7 dashboard.css split). Real ES
  modules would have required behavioral changes at 4 real coupling
  points (shared mutable state reassigned across module boundaries, a
  3-way DAG/analysis/context cycle, a hardcoded multi-modal registry, an
  auth/api-client cycle) with no way to verify equivalence by diff, so
  the split instead preserves the exact original single-closure runtime
  structure, reorganizing only where the source lives on disk.
- Split via a mechanical, Acorn-AST-driven script: every one of the
  original file's 372 top-level statements was sliced directly from the
  source (never retyped) into 22 new concern-based files under
  static/js/, then verified byte-for-byte unaltered at its new
  (relocated) position via a full content-equality check.
- Add a GET /dashboard/dashboard.js route (ahead of the StaticFiles
  mount) that concatenates the 22 files in order, read fresh per
  request; delete the now-superseded monolithic dashboard.js.
- Add a test that re-derives the expected assembly from the live files
  on every run and locks in the closure/statement-ordering invariants.
```

---

## UX-9b — Add Watchlist (Saved Symbols) (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Second half of the final UX Overhaul milestone: a minimal owner-curated "Saved Symbols" personal watch list, deliberately independent of two unrelated existing concepts — `owner_candidates` (the Market Intelligence "Stock List," which seeds the ingest/scoring pipeline) and the automated M4.3 `watchlist` package (config-driven, no owner input). Research confirmed `owner_candidates` is a closer structural analog than the milestone doc's original M-X0 (DecisionJournalEntry/TradeOutcome) reference — no FK relationship to decisions, same flat symbol+timestamp+notes shape — so the implementation mirrors it end-to-end |
| Scope | New `saved_symbols` SQLite table (schema bumped 7→8); `SqliteSavedSymbolStore`/`InMemorySavedSymbolStore` (Protocol-based, mirrors `CandidateStore`); `SavedSymbolsService`; `GET/POST/DELETE /api/v1/saved-symbols` (List=READ, Add/Remove=EXECUTE, matching the `owner_candidates` permission precedent); new "Saved Symbols" card in the Market Intelligence tab (add input + list + per-row remove), reusing the existing `.candidate-*` CSS classes as-is — zero new CSS needed |
| Tests | 6 new API tests (`tests/api/v1/test_saved_symbols.py`) — CRUD, symbol normalization, re-add-updates-in-place (not a duplicate), 404 on missing delete, EXECUTE-permission gating, unauthenticated rejection, and explicit independence from `owner_candidates` (saving/removing one list never touches the other). 2 existing schema-version assertions updated (7→8). 9 new dashboard-hosting assertions. Full suite **1030 passed** |
| Coverage | Backend: new repository methods, service, router, DI wiring, schema migration — all exercised via a real `TestClient`+in-memory store round trip. Frontend: markup/function/endpoint presence locked in; visually verified live (see below) |
| Status | **APPROVED** (2026-07-26) — schema migrated cleanly on the live DB (verified via direct read: `schema_version` now 8, `saved_symbols` table present with the expected columns, zero data loss since it's an additive `CREATE TABLE IF NOT EXISTS`), server restarted, live console check + visual DOM verification done |
| Branch | feature/live-dashboard |

### Scope completed

- **Domain/store** (`src/athena/ops/saved_symbols.py`, new): `SavedSymbol` frozen dataclass (`symbol`, `added_ts`, `notes`), `normalize_saved_symbol()` (strips `NSE:`/`BSE:` prefixes, uppercases — same convention as `owner_candidates`), `SavedSymbolStore` Protocol, `SqliteSavedSymbolStore`, `InMemorySavedSymbolStore`.
- **Schema** (`src/athena/data/store/schema.py`): `saved_symbols` table (`symbol TEXT PRIMARY KEY`, `added_ts`, `notes`) + index on `added_ts`; `SCHEMA_VERSION` 7 → 8. No `active` flag (unlike `owner_candidates`) — a personal watch list has no soft-delete/reactivation use case, so removal is a hard delete; kept deliberately simpler than the pipeline-list precedent rather than copying unneeded complexity.
- **Repository** (`src/athena/data/store/repository.py`): `add_saved_symbol()` (upsert — re-saving an existing symbol refreshes its timestamp/notes rather than duplicating), `remove_saved_symbol()`, `list_saved_symbols()` (ordered newest-first by `added_ts`, not alphabetically — a watch list's natural read order is "what did I just save," unlike the pipeline list's alphabetical order). `saved_symbols` added to `record_counts()` for backup/restore integrity checks.
- **DTOs** (`src/athena/api/v1/dtos/saved_symbols.py`, new): `SavedSymbolDTO`, `SavedSymbolListDTO`, `AddSavedSymbolRequest`, `RemoveSavedSymbolResultDTO`.
- **Service** (`src/athena/api/v1/services/saved_symbols_service.py`, new): `SavedSymbolsService` + `SavedSymbolNotFoundError(ResourceNotFoundError)` (maps to 404 automatically via the existing generic `ResourceNotFoundError` exception mapping — no new entry needed in `errors.py`).
- **Router** (`src/athena/api/v1/routers/saved_symbols.py`, new): `GET /api/v1/saved-symbols` (READ), `POST /api/v1/saved-symbols` (EXECUTE, add/upsert), `DELETE /api/v1/saved-symbols/{symbol}` (EXECUTE). Registered in `src/athena/api/v1/router.py`.
- **DI wiring** (`src/athena/api/dependencies.py`): module-level `InMemorySavedSymbolStore()` default + `SqliteSavedSymbolStore` attached to `app.state` inside `wire_sqlite_providers`, `get_saved_symbol_store()`/`get_saved_symbols_service()` factories — mirrors the `candidate_store` wiring exactly.
- **Frontend** (`index.html`, `dashboard.js`): new "Saved Symbols" card in the Market Intelligence tab, placed directly below the existing "Stock List" card, with an explanatory HTML comment distinguishing it from that list. `loadSavedSymbols()`, `removeSavedSymbolNow()`, and the add-button/Enter-key wiring closely mirror `loadCandidateList()`/`removeCandidateNow()` but simpler (no search bar, no per-row "Validate" action — a personal list has no pipeline action to trigger). Hooked into `loadMarketIntelligence()` so it loads whenever that tab is opened.

### Files created

- `src/athena/ops/saved_symbols.py`
- `src/athena/api/v1/dtos/saved_symbols.py`
- `src/athena/api/v1/services/saved_symbols_service.py`
- `src/athena/api/v1/routers/saved_symbols.py`
- `tests/api/v1/test_saved_symbols.py`

### Files modified

- `src/athena/data/store/schema.py` — new `saved_symbols` table; `SCHEMA_VERSION` 7 → 8.
- `src/athena/data/store/repository.py` — `add_saved_symbol`/`remove_saved_symbol`/`list_saved_symbols`; `saved_symbols` added to `record_counts()`.
- `src/athena/api/v1/router.py` — registers the new router.
- `src/athena/api/dependencies.py` — store singleton, `wire_sqlite_providers` wiring, `get_saved_symbol_store`/`get_saved_symbols_service`.
- `tests/api/conftest.py` — `client` fixture now resets `saved_symbol_store` between tests (mirrors the existing `candidate_store` reset).
- `tests/data_layer/test_decision_journal.py`, `tests/runtime/test_dry_run_schedule.py` — hardcoded `SCHEMA_VERSION == 7` assertions updated to `8`.
- `src/athena/api/static/index.html` — new Saved Symbols card; cache-bust `9.44.4` → `9.45.0`.
- `src/athena/api/static/dashboard.js` — `loadSavedSymbols`/`removeSavedSymbolNow` + wiring, hooked into `loadMarketIntelligence()`.
- `tests/api/platform/test_dashboard_hosting.py` — 9 new assertions.
- This log; `docs/MILESTONES.md`.

### Public APIs

- `GET /api/v1/saved-symbols` (READ)
- `POST /api/v1/saved-symbols` (EXECUTE) — add/upsert
- `DELETE /api/v1/saved-symbols/{symbol}` (EXECUTE)

### Validation and architecture

- Full regression: **1030 passed** (1024 + 6 new).
- Ruff clean on all changed/new `.py` files (2 pre-existing, unrelated `I001` import-order issues introduced by my own new imports were auto-fixed and re-verified; 3 pre-existing `SIM117` nested-`with` warnings in `repository.py` confirmed unrelated, left untouched per established practice this session).
- Live-DB schema migration verified directly (not just in tests): `schema_version` row now reads `8`, `saved_symbols` table exists with the expected columns, via a read-only `sqlite3` inspection of the actual `db/athena.db` — confirms the idempotent `CREATE TABLE IF NOT EXISTS` + version-bump path is safe for an existing production database with no downtime or data loss.
- Server restarted (backend Python changes require this, unlike the static-asset-only overlay feature); isolated-browser console check: zero errors on load.
- Visual verification: since I have no owner credentials to authenticate, I bypassed only the client-side unlock-gate `hidden` attribute via DOM manipulation (not a real auth bypass — no data was fetched, no protected action taken) purely to screenshot the new card's layout/styling; confirmed it renders identically in visual language to the adjacent "Stock List" card, reusing its CSS with zero new rules.
- No ADR required: additive table + additive endpoints, no change to any frozen contract, no architecture drift. Confirmed via research that this deliberately does NOT reuse or modify `owner_candidates` or `watchlist` — avoids concept collision the milestone doc explicitly flagged.

### Risks and technical debt

- I could not exercise the real end-to-end add/remove flow through an authenticated session myself (no owner credentials) — verified via the automated test suite (real `TestClient` round trip) and a live DOM/CSS visual check instead.
- No new technical debt. The design deliberately omitted features not in scope (search/filter within Saved Symbols, bulk clear, any pipeline-triggering action) to keep the milestone small and reviewable — can be added later if the owner wants them, but nothing here blocks that.

### Remaining work

- **Owner confirmation**: on the live dashboard, save a real symbol from the new Market Intelligence card, confirm it appears in the list, refresh the page and confirm it persists (SQLite-backed), then remove it and confirm it's gone.

### Commit message

```text
feat(market): add owner-curated Saved Symbols watch list (UX-9b)

- Add a minimal "Saved Symbols" domain — a passive personal watch list,
  deliberately independent of owner_candidates (the Stock List, which
  seeds ingest/scoring) and the automated M4.3 watchlist package
  (config-driven, no owner input) — to avoid conflating three different
  concepts that all happen to be "a list of symbols."
- New saved_symbols SQLite table (schema v7 -> v8), SqliteSavedSymbolStore/
  InMemorySavedSymbolStore mirroring the existing CandidateStore shape,
  SavedSymbolsService, and GET/POST/DELETE /api/v1/saved-symbols
  (List=READ, Add/Remove=EXECUTE, matching the owner_candidates
  permission precedent).
- New "Saved Symbols" card in the Market Intelligence tab (add/list/
  remove), reusing the existing .candidate-* CSS classes as-is.
- Add 6 new API tests plus 9 dashboard-hosting assertions; update 2
  existing tests that hardcoded the old schema version.
```

---

## Feature — Blocking validate overlay for Decisions & Trace / Market Intelligence (BUILT, awaiting owner confirmation)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Owner-reported: while "Re-validate" (Decision Brief) or "Validate"/"Add & validate" (Market Intelligence) was in flight, the rest of the dashboard stayed fully interactive — the trader could click other candidates or decisions mid-run and act on stale or half-updated state. Not just cosmetic: a correctness risk given the run_id-collision history above. Requested as a "beautiful ATHENA theme loading blocker/indicator" |
| Scope | A full-viewport, non-dismissible overlay shown for the duration of any `validateSymbolsNow` call, covering all 4 existing call sites (Portfolio holdings row, Market Intelligence candidate row, "Add & validate" button, Decision Brief "Re-validate" header button) automatically since it's centralized in the one shared function rather than duplicated per call site. No cancel affordance — the backend call itself can't be aborted once started |
| Frontend | `index.html`: `#validate-overlay` markup (ATHENA `fa-circle-nodes` brand mark, title, dynamic symbol list, detail line), `role="alertdialog"`/`aria-modal`, placed as a body-level sibling after the Kite gate. `css/07-universe-modals.css`: `.validate-overlay`/`.validate-overlay-panel`/`.validate-overlay-mark` (rotating-ring `validate-spin` animation, `prefers-reduced-motion` respected), z-index 9000 (above modals at 2000, below the unlock/Kite gates at 10000/11000, since a validate can only start once already past those). `dashboard.js`: `showValidateOverlay(symbols)`/`hideValidateOverlay()` helpers, wired into `validateSymbolsNow`'s existing try/finally so every caller gets it for free |
| Tests | 15 new dashboard-hosting assertions locking in the markup/CSS/JS. Full suite **1024 passed** |
| Coverage | No backend changes — pure frontend. Verified via a live isolated-browser check: zero console errors, overlay DOM resolves to the intended fixed/flex/z-index-9000 styling, and a manual reveal confirms the intended visual (brand mark, spin, symbol list, detail copy) |
| Status | **BUILT** — server serves static assets live (no restart needed to pick up changes), cache-bust bumped to `9.44.4`, visually verified via browser DOM inspection. Awaiting owner confirmation of the real end-to-end trigger (an authenticated Re-validate/Validate click) on the live dashboard, since I have no owner credentials to drive that myself |
| Branch | feature/live-dashboard |

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html` — `#validate-overlay` markup added; cache-bust `9.44.3` → `9.44.4`.
- `src/athena/api/static/css/07-universe-modals.css` — `.validate-overlay*` rules + `validate-spin` keyframes + reduced-motion override, inserted before the existing Kite-gate block.
- `src/athena/api/static/dashboard.js` — `showValidateOverlay`/`hideValidateOverlay` helpers; wired into `validateSymbolsNow`'s show/finally logic.
- `tests/api/platform/test_dashboard_hosting.py` — 15 new assertions.
- This log; `docs/MILESTONES.md`.

### Public APIs

- None — no backend/API changes.

### Validation and architecture

- Full regression: **1024 passed**.
- JS braces balanced (1614/1614), CSS braces balanced (769/769).
- Static files are served directly from disk, so the live dev server
  already reflects the change without a restart; confirmed via `curl`
  that `/dashboard/` and `/dashboard/dashboard.js` return the `9.44.4`
  cache-bust and the new markup/functions.
- Isolated-browser console check: zero errors. DOM inspection confirms
  `#validate-overlay` resolves to `position: fixed`, `display: flex`,
  `z-index: 9000` and reverts cleanly to `hidden` — matches the intended
  stacking order relative to modals (2000) and the unlock/Kite gates
  (10000/11000).
- No ADR required: additive UI-only change, no domain/contract/schema
  impact, no architecture drift.

### Risks and technical debt

- I could not trigger a real authenticated validate call end-to-end
  myself (no owner credentials) — verified the overlay's markup, CSS
  resolution, and wiring instead, plus a manual DOM-level reveal to
  confirm the visual. Owner should confirm the real trigger path (click
  "Re-validate" or "Add & validate" and see the overlay appear/disappear
  around the actual network call) on the live dashboard.
- No new technical debt.

### Remaining work

- **Owner confirmation**: trigger a real "Re-validate" (Decision Brief)
  and a real "Add & validate" (Market Intelligence) on the live
  dashboard and confirm the overlay blocks other UI interaction for the
  duration of the call and clears cleanly afterward either way (success
  or failure).

### Commit message

```text
feat(dashboard): add blocking ATHENA-themed overlay during validate calls

- Re-validate (Decision Brief) and Validate/Add & validate (Market
  Intelligence) left the rest of the dashboard fully interactive while
  the backend ingest+score call was in flight, letting the trader click
  other candidates/decisions and act on stale or half-updated state.
- Add a full-viewport, non-dismissible #validate-overlay (ATHENA brand
  mark, rotating ring, dynamic symbol list) wired into the one shared
  validateSymbolsNow function so all 4 existing call sites get it
  automatically, with no per-call-site duplication.
- Lock in the new markup/CSS/JS with 15 dashboard-hosting assertions;
  bump cache-bust to 9.44.4.
```

---

## Data-integrity fix — correction: run_id never actually reached the saved Decision (FIXED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | The earlier "REFRESH run_id collision" fix was incomplete — the owner reported still seeing "Unknown" Score/Confidence/Risk after successfully re-authenticating Kite and re-validating multiple times. This entry is the real, complete fix, found by directly querying the live SQLite database rather than assuming the first fix was sufficient |
| Scope | `src/athena/scheduling/dry_run.py` (`DryRunPipeline` Protocol, `run_cycle`), `src/athena/ops/owner_validation.py` (`OwnerValidationPipeline.run` signature) — plus a related frontend fix (see below) for the specific visual confusion the owner flagged |
| Tests | 1 new regression test (`test_repeat_validate_with_same_as_of_does_not_orphan_earlier_decision`) + 1 existing test extended with a direct assertion; 2 new dashboard-hosting assertions for the frontend fix. Full suite **1023 passed** |
| Coverage | The new backend test exercises the exact real code path (`OwnerValidationPipeline.run()` called twice with a shared `as_of`, different `run_id`s) that produced the owner's reported symptom |
| Status | **FIXED** — root-caused via direct database inspection (twice), verified via a regression test that reproduces the exact scenario, server restarted |
| Branch | feature/live-dashboard |

### Root cause (found by re-inspecting the live database, not assumed)

After the first run_id fix, the owner re-authenticated Kite, re-validated
several times, and still saw "Unknown" for BIOCON. Rather than assume the
first fix was sufficient, I queried `db/athena.db` directly again and
found something specific: **11 new-format run rows now existed**
(`run-refresh-20260724T153000-<8 hex chars>`, confirming the first fix's
uuid suffix *was* being generated), each `COMPLETED` with a correct,
intact `decision_reports` entry for whichever symbol had been
re-validated — including 3 separate successful runs for BIOCON. But the
`decisions` table's BIOCON row still pointed at the *original*,
un-suffixed `run-refresh-20260724T153000` — none of those 3 successful
re-validates had updated it, despite `SqliteRepository.save_decision`'s
upsert (`ON CONFLICT(decision_id) DO UPDATE SET run_id=excluded.run_id`,
verified correct in isolation with a standalone repro script) being
perfectly capable of doing so.

Traced why: `OwnerValidationPipeline.run()` (called by the orchestrator
as the pipeline stage inside `DryRunCycleOrchestrator.run_cycle()`)
**recomputed its own local `run_id`** at
`f"run-{trigger.value.lower()}-{as_of.strftime('%Y%m%dT%H%M%S')}"` —
line-for-line the same old, collision-prone formula the first fix had
already corrected *for the orchestrator's own `RunRecord`* — completely
independent of and disconnected from the orchestrator's actual,
now-unique `run_id`. This local variable is what gets threaded into
`decision_engine.decide(..., run_id=run_id, ...)` and ultimately saved
onto the `Decision` domain object. The `DryRunPipeline` Protocol's
`run()` signature never had a parameter to receive the orchestrator's
real run_id in the first place, so `OwnerValidationPipeline` had no
choice but to invent its own — and that invented one collided every
time, exactly as before the first fix, just one layer deeper.

### Fix

- `DryRunPipeline` Protocol (`src/athena/scheduling/dry_run.py`) gains a
  required `run_id: str` parameter.
- `DryRunCycleOrchestrator.run_cycle()` now passes its own already-unique
  `run_id` through: `self._pipeline.run(trigger, as_of=as_of,
  ingestion=ingestion, run_id=run_id)`.
- `OwnerValidationPipeline.run()` accepts `run_id: str` and uses it
  directly — the local recomputation is deleted entirely.
- Updated the one other implementation (`RecordingPipeline` in
  `tests/runtime/test_dry_run_schedule.py`) and the two existing callers
  in `tests/ops/test_owner_validation.py` to match the new required
  parameter.

### Related frontend fix (owner-flagged, same investigation)

The owner separately pointed out that even when this *is* a genuine data
problem (e.g. stale Kite quotes), the UI showing "0.0/100" next to
"Unknown" looks exactly like a real, computed zero score rather than an
honest error/absent state — confusing regardless of the backend cause.
Traced to the classic `Number(null) === 0` JavaScript trap (the same
class of bug fixed once before for the chart's `numericOrNull`, but
never re-checked here): `analysisPercent`, `analysisMeterWidth`, and the
completeness calculation inside `analysisPresentation` all did
`Number(value)` without first checking for `null`/`undefined` — so a
genuinely-absent `AnalysisBlockDTO.value`/`.completeness` (JSON `null`
when `status != "OK"`) silently became a plausible-looking `"0.0"`/`"0%
complete"` instead of the honest `"—"`/`"Completeness unknown"` the code
already used elsewhere for real absence. Fixed by adding an explicit
`value === null || value === undefined` check before coercion in all
three places.

### Files created

- None.

### Files modified

- `src/athena/scheduling/dry_run.py` — `DryRunPipeline.run()` gains `run_id`; `run_cycle()` passes it through.
- `src/athena/ops/owner_validation.py` — `OwnerValidationPipeline.run()` accepts and uses the passed-in `run_id`; local recomputation removed.
- `tests/runtime/test_dry_run_schedule.py` — `RecordingPipeline.run()` updated to match the new signature.
- `tests/ops/test_owner_validation.py` — both existing `pipe.run(...)` calls updated with `run_id=`; new `test_repeat_validate_with_same_as_of_does_not_orphan_earlier_decision`; existing test extended with a `run_id` assertion.
- `src/athena/api/static/dashboard.js` — `analysisPercent`, `analysisMeterWidth`, and `analysisPresentation`'s completeness calculation all gained an explicit null/undefined check before `Number()` coercion.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions for the frontend fix.
- `docs/MILESTONES.md` — the original "Data-integrity fix" entry updated in place with a "Correction (same day)" row rather than a new, separate section, since it's the same bug, more completely fixed.
- This log.

### Public APIs

- None — internal pipeline wiring only.

### Validation and architecture

- Full regression: **1023 passed** (1022 + 1 new).
- Ruff clean on all changed `.py` files. mypy remains unavailable in
  this environment (pre-existing, unrelated).
- JS braces balanced (1611/1611).
- Live server restarted; isolated-browser console check on the
  pre-login page: zero errors.
- No ADR required: internal signature threading + a null-check
  correctness fix, no domain/contract change.
- ADR-005 reinforced, not weakened: the frontend fix makes the "never
  fabricate a value" principle actually visible to the trader (a
  genuinely-absent value now *reads* as absent) rather than silently
  looking like a real zero.

### Risks and technical debt

- This was found by re-querying the live database a second time after
  the owner reported the first fix hadn't resolved their symptom —
  worth internalizing as a pattern: for data-integrity bugs, verify the
  *complete* data flow end-to-end (here: orchestrator run_id → pipeline
  callback → decision_engine → saved Decision row) rather than stopping
  at the first plausible-looking fix.
- Existing decisions from between the first (incomplete) fix and this
  correction may still have inconsistent run_id references — the "Clear
  all" feature gives a clean-slate path if needed.
- I could not exercise this against the live authenticated dashboard
  myself (no owner credentials) — verified via a regression test that
  reproduces the exact reported scenario end-to-end at the code level.
- No new technical debt beyond the above.

### Remaining work

- **Owner confirmation**: re-validate a symbol on the live dashboard and
  confirm Score/Confidence/Risk populate with real values (not
  "Unknown"), and that re-validating a *different* symbol afterward
  doesn't blank out the first one again.

### Commit message

```text
fix(scheduling): thread the real run_id through to OwnerValidationPipeline
so saved decisions stop pointing at a colliding, recomputed one

- The earlier run_id-uniqueness fix only fixed the orchestrator's own
  RunRecord identity. OwnerValidationPipeline.run() independently
  recomputed its own local run_id from (trigger, as_of) using the same
  old collision-prone formula, and that's what actually got attached to
  each saved Decision — so decisions kept pointing at a run whose
  detail_json had since been overwritten by a different symbol's
  validation, still showing "Unknown" Score/Confidence/Risk even after a
  successful re-validate.
- Add run_id to the DryRunPipeline Protocol and thread the orchestrator's
  actual run_id through to OwnerValidationPipeline.run(), removing the
  local recomputation entirely.
- Add a regression test validating two different symbols back-to-back
  with the same as_of and asserting each keeps its own distinct run_id.
- Fix analysisPercent/analysisMeterWidth/completeness calculation:
  Number(null) is 0 in JS, not NaN — a genuinely-absent score/confidence/
  risk value was rendering as a plausible "0.0/100" instead of an honest
  "—", which is exactly the confusion the owner flagged regardless of the
  underlying data cause.
```

---

## Feature — "Clear all" for Decisions & Trace (BUILT, awaiting owner confirmation)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Owner-requested admin utility: wipe the Decisions & Trace domain so it can be "cleared properly in the DB and added again," instead of repairing/re-validating each decision individually (especially useful after the run_id-collision bug above orphaned some test decisions) |
| Scope | `decisions`, `decision_traces`, `decision_journal`, `trade_outcomes` tables — built as a close mirror of the existing "Reset fills" (Portfolio) feature: same CONFIRM-token gate, same automatic pre-delete backup pattern, same ADMIN-only permission requirement |
| Tests | 2 new backend tests (`test_reset_decisions_requires_confirmation_and_admin`, `test_reset_decisions_clears_domain_after_confirmation`) + 6 new dashboard-hosting assertions. Full suite **1022 passed** |
| Coverage | Backend: repository + provider + service + router, all exercised by the new tests. Frontend: presentation-only, no computed values |
| Status | **BUILT** — implemented, tested, server restarted. Awaiting owner confirmation on the live dashboard |
| Branch | feature/live-dashboard |

### Scope completed

- **Backend**, following the exact established `PortfolioService.
  reset_positions` pattern:
  - `SqliteRepository.delete_decisions_data()` (`src/athena/data/store/
    repository.py`) — deletes all rows from `decisions`,
    `decision_traces`, `decision_journal`, `trade_outcomes`, returns
    per-table deleted counts. Deliberately does **not** touch `runs`
    (shared with Market Intelligence's universe/regime history —
    clearing it could have side effects beyond "Decisions & Trace"),
    portfolio positions, or owner candidates.
  - `SqliteDecisionProvider.reset_decisions_data()` /
    `InMemoryDecisionProvider.reset_decisions_data()` (same interface
    on both, `DecisionProvider` Protocol updated to match) — so the
    in-memory test fixture and the real SQLite path behave identically.
  - `DecisionsService.reset_decisions(confirmation)` — refuses unless
    `confirmation == "CONFIRM"` (raises the new
    `DecisionsResetConfirmationError`, mapped to HTTP 400 in
    `errors.py`, same shape as the existing
    `PortfolioResetConfirmationError`); creates a best-effort automatic
    backup first via the same `create_backup` helper Portfolio reset
    uses, saved as `db/backups/athena-pre-decisions-reset-<UTC
    timestamp>.db`; backup failure is non-fatal (the reset still
    proceeds — a `backup_path: null` in the response signals it wasn't
    created).
  - `POST /api/v1/decisions/reset` (new `ResetDecisionsRequest`/
    `ResetDecisionsResultDTO`), gated by `Permission.ADMIN` (same
    requirement as Portfolio reset).
- **Frontend**: a "Clear all" button in the Decisions & Trace toolbar
  opens a confirmation modal (following the existing trace-modal/
  chart-modal/compare-modal pattern) containing the exact same "type
  CONFIRM to unlock" gate UX as Portfolio's "Reset fills" card — reused
  the existing `.ops-restore-gate`/`.ops-restore-gate-status` CSS
  classes directly, no new styling needed. On success: clears the
  active decision brief and Reasoning Trace panel back to their empty
  states, reloads the (now-empty) decisions list.

### Files created

- None.

### Files modified

- `src/athena/data/store/repository.py` — `delete_decisions_data()`.
- `src/athena/api/v1/providers/sqlite_providers.py` — `SqliteDecisionProvider.reset_decisions_data()`.
- `src/athena/api/v1/providers/in_memory.py` — `InMemoryDecisionProvider.reset_decisions_data()`.
- `src/athena/api/v1/providers/base.py` — `DecisionProvider` Protocol gains `reset_decisions_data()`.
- `src/athena/api/exceptions.py` — `DecisionsResetConfirmationError`.
- `src/athena/api/errors.py` — exception → HTTP 400 mapping.
- `src/athena/api/v1/dtos/decisions.py` + `dtos/__init__.py` — `ResetDecisionsRequest`, `ResetDecisionsResultDTO`.
- `src/athena/api/v1/services/decisions_service.py` — `db_path`/`backup_dir` constructor params (mirroring `PortfolioService`), `reset_decisions()`.
- `src/athena/api/dependencies.py` — `get_decisions_service` wires `ops_db_path`/`ops_backup_dir` from app state, same as `get_portfolio_service`.
- `src/athena/api/v1/routers/decisions.py` — `POST /reset` endpoint.
- `src/athena/api/static/index.html` — "Clear all" toolbar button + confirmation modal; cache-bust bumped to `9.44.0`.
- `src/athena/api/static/dashboard.js` — gate-sync logic, modal wiring, submit handler.
- `tests/api/v1/test_core_apis.py` — 2 new tests, `DecisionTrace`/`TraceStage` imports added.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — new "Clear all" feature section.
- This log.

### Public APIs

- New: `POST /api/v1/decisions/reset` (ADMIN-only), `ResetDecisionsRequest`, `ResetDecisionsResultDTO`. Additive — no existing endpoint or DTO changed.

### Validation and architecture

- Full regression: **1022 passed** (1020 + 2 new).
- Ruff clean on all changed `.py` files (fixed 2 incidental lint issues
  surfaced by `ruff check --fix` while touching these files: an
  `__all__` sort order in `dtos/__init__.py` and an import-order issue
  in `test_core_apis.py` — both mechanical, auto-fixed, verified with a
  full test re-run afterward). 3 pre-existing `SIM117` (nested-`with`)
  warnings in `repository.py` at unrelated lines were left untouched —
  out of scope for this change. mypy remains unavailable in this
  environment (pre-existing, unrelated).
- JS braces balanced (1611/1611); parens off by the same pre-existing
  +1 baseline quirk.
- Live server restarted on `9.44.0`; isolated-browser console check on
  the pre-login page: zero errors.
- No ADR required: purely additive (new domain-scoped delete capability
  behind a confirmation + permission gate), no frozen contract or
  domain model changed, follows an already-approved precedent
  (Portfolio reset) exactly in shape and safety mechanism.

### Risks and technical debt

- I could not exercise the modal/gate/delete flow against the live
  authenticated dashboard myself (no owner credentials) — the backend
  is covered by real HTTP-level tests (confirmation refusal, role
  refusal, actual deletion + empty subsequent listing), which is the
  strongest verification available without live access; the frontend
  gate-sync logic directly mirrors the already-working Portfolio reset
  gate's exact code shape.
- Deliberately did not clear the `runs` table — a "Clear all" that also
  wiped scheduled premarket/closing run history would affect Market
  Intelligence surfaces (universe/regime history) beyond what "Decisions
  & Trace" implies. If the owner wants a fuller reset later, that's a
  separate, explicit scope decision, not something to fold in silently.
- No new technical debt beyond the above.

### Fix pass (owner live test, 2026-07-26)

Owner clicked "Clear all" on the live dashboard and got "delete decisions
data failed: FOREIGN KEY constraint failed." Root cause: `decision_traces`,
`decision_journal`, and `trade_outcomes` each `REFERENCES
decisions(decision_id)` — my original `delete_decisions_data()` deleted
`decisions` (the parent) **first**, then the child tables, which SQLite's
foreign-key enforcement (`PRAGMA foreign_keys=ON`) correctly rejects. This
passed my original tests because those used the **in-memory** decision
provider (no real FK enforcement), never the real `SqliteRepository` —
a real gap in test coverage for this feature. Fixed the delete order
(children first, `decisions` last) and added
`test_reset_decisions_data_respects_foreign_keys` in
`tests/api/v1/test_owner_portfolio.py`, using a real `SqliteRepository`
with `foreign_keys=ON` specifically to exercise this constraint — verified
it fails against the old order and passes against the fixed one before
finalizing. Version bumped to `9.44.3`.

### Remaining work

- **Owner confirmation**: open Decisions & Trace, click "Clear all,"
  confirm the gate stays locked until "CONFIRM" is typed exactly, then
  confirm a real clear empties the carousels and resets the brief/trace
  panel to their empty states, and that a backup file appears under
  `db/backups/`.

### Commit message

```text
feat(decisions): add CONFIRM-gated "Clear all" reset for Decisions &
Trace, mirroring the existing Portfolio reset pattern

- Add SqliteRepository.delete_decisions_data() (decisions, traces,
  journal entries, trade outcomes — not runs/positions/candidates).
- Add DecisionsService.reset_decisions(confirmation), gated on the
  exact token "CONFIRM" (DecisionsResetConfirmationError -> HTTP 400),
  with a best-effort automatic pre-delete backup via the same
  create_backup helper Portfolio reset already uses.
- Add POST /api/v1/decisions/reset (ADMIN-only), ResetDecisionsRequest/
  ResetDecisionsResultDTO.
- Add a "Clear all" button + confirmation modal to the Decisions &
  Trace toolbar, reusing the existing Portfolio reset gate's exact UX
  (type CONFIRM to unlock) and CSS classes — no new styling needed.
- Add 2 backend tests (confirmation/role gating, real clear + empty
  listing) and dashboard-hosting assertions. Bump cache-bust to 9.44.0.
```

---

## Data-integrity fix — REFRESH run_id collision (FIXED, awaiting owner confirmation)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Owner-reported, tracked separately from the UX Overhaul per explicit instruction: fix the root cause of Score/Confidence/Risk showing "Unknown"/0.0 for a decision until it's re-validated — and the same thing then happening to whichever *other* decision had been re-validated most recently |
| Scope | `_default_run_id` in `src/athena/scheduling/dry_run.py` — append a `uuid4` disambiguator for `RunTrigger.REFRESH` only, so every ad-hoc symbol validation gets a genuinely unique run_id even when `as_of` collapses to the same value (which it always does outside live trading hours) |
| Tests | Full suite **1020 passed** (2 new regression tests: REFRESH run_id uniqueness under a shared `as_of`, PREMARKET run_id format unchanged) |
| Coverage | `tests/runtime/test_dry_run_schedule.py` exercises the real default `run_id_factory` (no override) for the first time on this exact path |
| Status | **FIXED** — root cause confirmed via direct inspection of the live `db/athena.db`, code fix applied, tested, server restarted. Awaiting owner confirmation that re-validating a symbol no longer breaks a previously-fresh one |
| Branch | feature/live-dashboard |

### Root cause (confirmed via direct SQLite inspection, not guessed)

The owner's screenshot showed decision "PERSISTENT" (HOLD/WATCH) with
Score/Confidence/Risk all "Unknown"/0.0, despite its own explanation text
correctly quoting a real score (62.75/100) — meaning the base decision
record was fine, but its *depth* (score/confidence/risk breakdown) wasn't
resolving. Traced the exact chain:

1. `GET /decisions/{id}/depth` → `decisions_service.get_decision_depth`
   resolves score/confidence/risk from `get_run_detail(decision.run_id)`
   — a SQLite lookup of `runs.detail_json` by `run_id`.
2. Queried `db/athena.db` directly: `decision-NSE:DIXON-...`,
   `decision-NSE:TCS-...`, and `decision-NSE:HFCL-...` — all three, from
   the same day — shared the identical `run_id`
   `run-refresh-20260724T153000`. Loaded that run's `detail_json` and
   found `pipeline.decision_reports` contained an entry for **only
   DIXON** — TCS and HFCL were simply absent, so their depth fetch
   correctly (but unhelpfully) fell back to "Unknown" for every block —
   ADR-005 behaving as designed (no fabricated number), just fed by
   already-corrupted upstream data.
3. Traced why three decisions share one run_id: `resolve_validate_as_of`
   (`src/athena/calendar/resolve_as_of.py`) returns the exact session
   *close* time whenever validation happens outside live trading
   hours — a fixed value, identical for every call made later that same
   day. `_default_run_id(trigger, as_of)`
   (`src/athena/scheduling/dry_run.py:189-191`, before this fix) derives
   the run_id purely from `(trigger, as_of)` with no per-invocation
   disambiguator, so every off-hours "Re-validate" click that day
   computed the *same* run_id string.
4. `SqliteRepository.save_run` (`src/athena/data/store/repository.py:
   290-313`) persists runs via `INSERT ... ON CONFLICT(run_id) DO UPDATE
   SET ... detail_json=excluded.detail_json` — a genuine upsert. So
   validating DIXON, then later TCS, then later HFCL (all colliding on
   the same run_id) meant each subsequent call's `detail_json`
   (containing only *that* call's requested symbol's report, since
   `validateSymbolsNow` sends one symbol at a time) completely
   overwrote the previous call's — silently orphaning whichever
   decision had been "fresh" a moment before. This is fully
   deterministic and reproducible, not intermittent: it happens on
   *every* off-hours re-validation of more than one symbol on the same
   calendar day.

### Fix

`_default_run_id` now appends `-{uuid4().hex[:8]}` to the run_id **only**
for `RunTrigger.REFRESH` (the ad-hoc, owner-triggered validation path —
`PREMARKET`/`CLOSING` are scheduled, at-most-once-per-day cycles left
untouched, since a stable id there may be relied on for idempotent
retries of the same logical run). This is a bookkeeping-identifier
concern, not an analytical-determinism one: no score/confidence/risk/
regime computation is affected, and `uuid4()` for identifier generation
is already an established pattern elsewhere in this codebase (request-id
middleware, ops service, security service) — it is not being introduced
into any analytical engine, which remain fully deterministic.

### Files created

- None.

### Files modified

- `src/athena/scheduling/dry_run.py` — `_default_run_id` gains a
  `uuid4`-based disambiguator for `RunTrigger.REFRESH`; `import uuid`.
- `tests/runtime/test_dry_run_schedule.py` —
  `test_refresh_run_id_unique_per_call_even_with_same_as_of` (regression
  test for the exact bug, using the real default `run_id_factory`),
  `test_premarket_run_id_still_deterministic_for_same_as_of` (confirms
  no change to the untouched trigger types).
- `docs/MILESTONES.md` — new "Data-integrity fix" section, tracked
  separately from the UX Overhaul per owner instruction; also fixed a
  markdown table formatting bug (two rows missing their leading `|`)
  noticed while editing.
- This log.

### Public APIs

- None — internal run_id generation only; `run_id` was always an opaque
  string to API consumers, no contract change.

### Validation and architecture

- Full regression: **1020 passed** (1018 + 2 new).
- Ruff clean on both changed files. mypy remains unavailable in this
  environment (pre-existing, unrelated).
- No architecture change, no ADR required: this is a bug fix to an
  identifier-generation function's collision behavior, not a domain
  model, contract, or module-boundary change.
- Live server restarted; isolated-browser console check on the
  pre-login page: zero errors.

### Risks and technical debt

- **Not retroactively repaired**: decisions already orphaned by a past
  collision in this session's live database (TCS, HFCL, and possibly
  others sharing `run-refresh-20260724T153000` or any other collided
  run_id from before this fix) will continue to show "Unknown" until
  each is individually re-validated once more. I deliberately did not
  hand-edit the live `db/athena.db` to backfill/repair this — that would
  be an out-of-band data mutation on the owner's real working database
  without being asked, and the safe path is simply: re-validate the
  affected symbols once, going forward each will get its own unique
  run_id and never be silently clobbered by another symbol's refresh.
- `cycle_id` has a structurally similar (lower-severity) non-uniqueness
  issue: it's built from a `self._cycle_counter` that resets to zero
  every time a new `DryRunCycleOrchestrator` is constructed (which
  happens on every API call), so it can also collide across separate
  validate calls — but `cycle_id` is not the `runs` table's primary key
  (`run_id` is), so it does not cause data loss. Not fixed here since it
  wasn't the reported symptom and fixing it isn't needed to resolve the
  actual bug — flagging for awareness, not silently expanding scope.
- I could not exercise the fix against the live authenticated dashboard
  myself (no owner credentials) — the regression tests exercise the
  exact code path (`DryRunCycleOrchestrator.run_cycle` with the real
  default `run_id_factory`), which is the strongest verification
  available without live access.

### Remaining work

- **Owner confirmation**: re-validate two different symbols back-to-back
  on the live dashboard (ideally outside live trading hours, to
  reproduce the exact conditions that triggered the original bug) and
  confirm the first symbol's Score/Confidence/Risk stay populated after
  the second is validated.
- Optional follow-up (not blocking, not requested): decide whether to
  also fix `cycle_id`'s reset-per-orchestrator-instance behavior, and/or
  whether to write a one-off script to repair already-orphaned
  decisions in the live database by re-associating them with their
  original (still-correct-at-the-time) run detail, if any of that detail
  is recoverable from earlier backup snapshots in `db/backups/`.

### Commit message

```text
fix(scheduling): prevent REFRESH run_id collisions from clobbering
persisted decision analysis

- _default_run_id derived run_id purely from (trigger, as_of); outside
  live trading hours, resolve_validate_as_of always returns the same
  fixed session-close as_of, so every ad-hoc "Re-validate" call on the
  same day computed an identical run_id.
- SqliteRepository.save_run's upsert (ON CONFLICT(run_id) DO UPDATE ...
  detail_json=excluded.detail_json) then silently overwrote the
  previous call's persisted decision_reports with the new call's —
  orphaning the earlier decision from its own score/confidence/risk,
  which rendered as "Unknown" until re-validated again (which just
  moved the same bug onto whichever symbol was validated before it).
  Root-caused via direct inspection of the live SQLite database.
- Fix: append a uuid4-based disambiguator to the run_id for
  RunTrigger.REFRESH only. PREMARKET/CLOSING (scheduled, at-most-once-
  per-day cycles) are untouched.
- Add 2 regression tests exercising the real default run_id_factory:
  two REFRESH calls sharing an as_of now get distinct run_ids and both
  persist their detail intact; PREMARKET's id format is unchanged.
- Not retroactively repaired: decisions already orphaned by a prior
  collision need one more re-validate each; the fix only prevents new
  collisions going forward.
```

---

## UX-9a — Open Chart / Compare / News / Portfolio Impact quick actions (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | First half of the final UX Overhaul milestone: four owner-approved quick actions and a portfolio-context strip, all built without new backend routes by composing existing endpoints. Scope for "Compare" (symbol-vs-symbol) and "Open Chart" (enlarge in a modal) was resolved with the owner beforehand — both were originally open questions in the milestone plan |
| Scope | `openChartModal` (reuses `renderCandlestickSvg` in a larger modal, no new fetch); `openCompareModal`/`runSymbolCompare` (fetches a second symbol's latest decision + depth via existing endpoints, renders side-by-side using the same `analysisPresentation`/`decisionStance` helpers the current decision uses); `loadPortfolioImpact`/`renderPortfolioImpact` (aggregates open positions for the instrument from the existing full portfolio list, computes gain % against a real latest close); "News" quick action jumps to the already-implemented Market Context tab |
| Tests | Full suite **1018 passed**; new dashboard-hosting assertions; no backend files touched |
| Coverage | Frontend-only; no Python coverage impact |
| Status | **APPROVED** (2026-07-26) — smoke-tested live by owner, plus the later bug-fix pass above (Compare NSE-prefix + case-sensitivity fixes) |
| Branch | feature/live-dashboard |

### Scope completed

- **Open Chart**: `renderCandlestickSvg` gained an optional `hostId`
  parameter (default unchanged, so the existing Trade Plan tab call site
  is untouched) so the exact same chart-rendering code — and the
  already-loaded candle series, stashed in new `activeChartSeries`/
  `activeChartPlan` globals — can render into a larger `#chart-modal`
  without a second fetch. The SVG's `viewBox` already scales to its
  container, so "enlarge" is purely a bigger CSS box around the same
  render call, not a second chart implementation.
- **Compare** (symbol vs. symbol, per owner decision): a new
  `#compare-modal` with a symbol input. `fetchLatestDecisionForSymbol`
  reuses the already-supported `instrument_id` filter on
  `GET /api/v1/decisions` plus the existing `/depth` endpoint — the
  exact same two calls already made for the *current* decision — and
  `compareColumn`/`compareMetricRow` render both sides through the same
  `decisionStance`/`analysisPresentation` helpers, so the compared
  symbol is never a different, lower-fidelity code path. A symbol with
  no decision history shows "No decision found for this symbol," not a
  silent blank.
- **News**: the "External research" panel (owner-curated
  `config/external_links.json` links) was already fully implemented but
  reachable only via a sub-tab click; the new button just calls the
  existing `switchBriefTab("context")`.
- **Portfolio Impact** ("you own N shares, avg price, gain %"): reuses
  the existing full `GET /api/v1/portfolio` positions list (already
  fetched for the Portfolio Overview workstation) — filtered to this
  instrument's *open* positions (`closed_ts` null), aggregated into a
  total share count and a cost-weighted average price. Gain % is exact
  arithmetic against a real latest close fetched via the same candles
  endpoint the chart uses (`fetchLatestClose`, deliberately independent
  of the chart's own load so the two async fetches can't race each
  other or leave a stale price). Shows "You don't currently own any
  shares of this symbol" — never a fabricated 0-share row — when there's
  no open position.
- **Excluded, as always**: no "Place Order" action anywhere — verified
  by a dedicated test assertion (`"Place Order" not in html/js`), per
  the constitution's absolute prohibition on order-placement code.

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html` — 3 new actionbar buttons (Open
  Chart, Compare, News); 2 new modals (`#chart-modal`, `#compare-modal`)
  following the existing trace-modal/backtest-modal pattern; cache-bust
  bumped to `9.43.0`.
- `src/athena/api/static/dashboard.js` — `renderCandlestickSvg` gained
  an optional `hostId` param; new `activeChartSeries`/`activeChartPlan`
  globals (reset in `selectBriefing`, alongside the other per-decision
  caches); `openChartModal`, `openCompareModal`, `runSymbolCompare`,
  `fetchLatestDecisionForSymbol`, `compareColumn`, `compareMetricRow`,
  `loadPortfolioImpact`, `renderPortfolioImpact`,
  `portfolioInstrumentMatches`, `fetchLatestClose`; `closeAllModals`
  extended for the 2 new modals; a Portfolio Impact section added to the
  Trade Plan tab template, loaded alongside the existing chart/analogs/
  journal loads in `renderDecisionBrief`.
- `src/athena/api/static/css/08-strategies-backtest.css` — modal/compare
  styling (`.chart-modal-container`, `.compare-grid`, `.compare-column`,
  `.compare-metric`, etc.).
- `src/athena/api/static/css/10-trade-plan-chart.css` —
  `.portfolio-impact-grid`.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-9 split into 9a (this milestone) and 9b
  (Add Watchlist, needs new backend); 9a → Ready for review.
- This log.

### Fix pass (owner screenshots, 2026-07-26)

Owner screenshot showed Compare always returning "No decision found for
this symbol" for a valid symbol (HFCL). Root cause: `instrument_id` is
stored with an exchange prefix (e.g. `NSE:HFCL`) and the backend's
`GET /decisions?instrument_id=` filter is an exact string match
(`sqlite_providers.py:133`) — a bare symbol typed into Compare (e.g.
"HFCL") never matched anything. Fixed `fetchLatestDecisionForSymbol` to
probe `NSE:{symbol}` before the bare symbol, the same candidate-id
pattern `loadDecisionChart` already uses successfully. Version bumped to
`9.43.1`; cache-bust-only fix, no other changes in this pass.

The owner also reported a second, separate issue: selecting an older
decision from a carousel sometimes shows Score/Confidence/Risk as
"Unknown" with 0.0/100 until "Re-validate" is clicked — and the same
thing then happening to whichever *other* decision had been re-validated
most recently. Initial code tracing correctly identified this as a
backend data-lookup issue unrelated to any UX-9a frontend change, not a
regression — and per owner instruction, this was tracked and fixed as
its own separate item rather than folded into the UX milestone. See the
dedicated **"Data-integrity fix — REFRESH run_id collision"** entry above
this one for the full root cause (confirmed via direct SQLite inspection)
and fix.

### Second fix pass (owner screenshots, 2026-07-26)

Owner reported Compare returning "No decision found for this symbol" for
DIXON specifically, even though DIXON has real decisions (confirmed
working elsewhere in the same session). Root cause: `fetchLatestDecisionForSymbol`
never uppercased the typed symbol before building the `NSE:{symbol}`/
`{symbol}` candidates. The Compare input's all-caps *look* is CSS
`text-transform: uppercase` only — it doesn't change the underlying
`.value`, so a symbol typed in lowercase or mixed case (e.g. "dixon")
silently failed the backend's case-sensitive `instrument_id` match, while
an all-caps-typed symbol (e.g. "HFCL", typed that way by chance) worked.
Fixed by uppercasing the input before building candidates. Version bumped
to `9.44.1`.

Also re-confirmed via direct database inspection: the owner's "even after
re-validate, I'm getting 0 values for HFCL" report is a **separate,
expected** condition, not a remaining bug in the run_id fix above. Every
`RunTrigger.REFRESH` attempt that day was failing outright with
`ingest rejected dataset 'quotes': FRESHNESS: quotes are 2716.2 min
behind as_of (threshold 20 min)` — a live Kite quote-freshness gate
correctly refusing stale market data, unrelated to run_id generation.
Since the validate call never completes, no new decision is ever created
for HFCL, so it correctly keeps showing its old, already-orphaned data.
This is expected, intentional data-quality enforcement (ADR-005-adjacent:
never analyze on stale data) — not something to relax.

### Public APIs

- None — every new feature composes existing endpoints
  (`GET /decisions?instrument_id=`, `GET /decisions/{id}/depth`,
  `GET /portfolio`, `GET /market/instruments/{id}/candles`); no new
  routes, no schema changes.

### Validation and architecture

- Full regression: **1018 passed** (unchanged — no backend files touched).
- Ruff clean on the one changed test file. mypy remains unavailable in
  this environment (pre-existing, unrelated).
- JS braces balanced (1594/1594); parens off by the same pre-existing +1
  baseline quirk. CSS braces balanced (757/757).
- Live server restarted on `9.43.0`; isolated-browser console check on
  the pre-login page: zero errors.
- ADR-005 preserved: every number in Compare and Portfolio Impact is
  exact arithmetic over already-real, already-persisted data (positions,
  candle closes, existing decision depth) — nothing generated or
  predicted. No ADR required: no schema change, no new architectural
  surface, purely frontend composition of existing read endpoints.
- Constitution preserved: no order-placement code anywhere — verified
  by an explicit test assertion, not just manual review.

### Risks and technical debt

- `fetchLatestClose` duplicates ~10 lines of the NSE-prefix candidate
  probing logic already in `loadDecisionChart`, kept deliberately
  separate rather than shared/refactored to avoid touching an
  already-approved, working function for this milestone — flagged as a
  minor, acceptable duplication rather than silently "fixed" by
  refactoring code outside this milestone's scope.
- `Portfolio Impact` and `Compare`'s depth fetch both add real (small)
  network calls per decision view — acceptable for a localhost,
  single-user app, but worth knowing if either ever needs to be
  debounced or cached across quick re-selection of the same decision.
- I could not exercise any of these four features end-to-end myself (no
  owner credentials, and each depends on real portfolio/decision data
  existing) — needs an owner click-through, ideally with at least one
  owned position and one comparable symbol to exercise the non-empty
  paths of each feature, not just the empty states.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: open a decision and (a) click "Open Chart",
  confirm the enlarged chart matches the inline one; (b) click
  "Compare", enter a symbol you have a decision for, confirm both
  columns populate correctly (and try a symbol with no history to see
  the empty state); (c) click "News", confirm it jumps to Market
  Context; (d) check the new "Portfolio impact" block on a symbol you
  own vs. one you don't.
- Next: **UX-9b** (Add Watchlist / Saved Symbols — new backend domain,
  its own milestone for a focused review) — not yet started, awaiting
  approval of this part first.
- Documented, deferred future enhancement (owner decision): deep-link/
  share for a specific decision (a `?decision=<id>` URL param + "Copy
  link" action) — no existing infrastructure for this today; scoped as
  its own future milestone if the owner wants it later.

### Commit message

```text
feat(dashboard): add Open Chart, Compare, News, and Portfolio Impact
quick actions (UX-9a)

- Add openChartModal, reusing renderCandlestickSvg (now with an optional
  hostId param) and the already-loaded candle series in a larger modal —
  no second fetch, no separate chart implementation.
- Add openCompareModal/runSymbolCompare (symbol-vs-symbol, per owner
  decision): fetches the entered symbol's latest decision + depth via
  the existing instrument_id filter and /depth endpoint, renders both
  sides through the same analysisPresentation/decisionStance helpers
  already used for the current decision.
- Add a "News" quick action that jumps to the existing Market Context
  tab (External research links were already implemented, just gated
  behind a sub-tab).
- Add loadPortfolioImpact/renderPortfolioImpact: "you own N shares, avg
  price, gain %" derived from the existing full portfolio positions
  list and a real latest close price — no new backend, "—" (never
  fabricated) when there's no open position or no price.
- No new backend routes; add dashboard-hosting test coverage including
  an explicit assertion that no "Place Order" text exists anywhere.
  Bump cache-bust to 9.43.0.
```

---

## UX-8 — Copy pass (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Eighth milestone of the owner's UX audit: replace engineering vocabulary leaking into trader-facing text, improve unhelpful empty states, and fix a couple of narrative-parity gaps — the last purely-cosmetic milestone before UX-9 |
| Scope | Friendly labels for raw ALL_CAPS enums shown in chips/sentences (decision type, eligibility status); plain-English rewrites of five dense tab-intro paragraphs; a handful of empty-state message fixes; a real (not fabricated) market-health explanation sentence for parity with the regime block; one label-consistency fix ("Composite score" → "Score") |
| Tests | Full suite **1018 passed**; new dashboard-hosting assertions for the rewritten copy; no backend files touched |
| Coverage | Frontend-only, pure copy/text change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26) |
| Branch | feature/live-dashboard |

### Scope completed

- **Raw enum leakage fixed** — several spots showed an internal ALL_CAPS
  value directly, often right next to an already-friendly label for the
  same concept:
  - `decisionTypeBadge()` and the "qualified names" row (dashboard.js)
    showed the raw `decision_type` (`TRADE`/`WATCH`/`NO_TRADE`/
    `INSUFFICIENT_DATA`) as a second chip sitting beside the
    already-friendly stance chip (`BUY`/`HOLD`/`PASS`/`WAIT`) — two
    badges for one idea, one polished and one raw, with a literal
    underscore visible in two of the four values. Both now reuse the
    existing `friendlyAnalysisName()` helper (already used elsewhere in
    the file for exactly this purpose).
  - The Trade Plan "no plan authorized" sentence used to interpolate the
    raw uppercase type directly into a sentence (e.g. "...for a
    **NO_TRADE** decision"); now reads "...for a **No Trade** decision."
  - `renderEligibilityDepth()`'s status badge showed the raw
    `INCLUDED`/`EXCLUDED`/`UNKNOWN` instead of the "Eligible"/"Excluded"
    wording the Universe table already established — added
    `friendlyEligibilityLabel()` so both surfaces agree.
  - The Decision Timeline's decision-type fallback and the regime/
    volatility/gap badge fallback (no-payload case) both showed raw
    `"UNKNOWN"`; now "Unknown", consistent with the friendly-cased
    fallback the main (non-fallback) rendering path already used.
  - `analysisPercent()` returned the literal string `"UNKNOWN"` as a
    score value (rendering as "UNKNOWN / 100"); now returns "—", matching
    the app's own established em-dash convention for missing numbers,
    and the "/ 100" suffix is hidden entirely when there's no value.
- **Dense engineering paragraphs rewritten in plain English** (same
  underlying meaning — "this is exact math over saved data, nothing
  invented" — just without the jargon): the "Why not a trade?", "Session
  & market context", "Analytical provenance" (renamed **"Data sources"**),
  "Your response", and "Similar past setups" tab intros no longer say
  "persisted", "config thresholds", "recomputed", "ingestion", "generated
  rationale", "deterministic nearest-neighbor retrieval", "fingerprint",
  or name the internal "AI Playbook Diagnostics" module directly.
- **Empty-state fixes**: "No comparable historical decisions yet (needs a
  persisted score/confidence/risk fingerprint)" → explains the real
  requirement in plain terms; "No provenance references captured"/"No
  analytical references persisted" → "No source references recorded";
  "Trace empty — decision has no persisted DecisionTrace stages" (leaked
  an internal class name) → "This decision has no recorded reasoning
  stages to show"; "No step-by-step trace logs stored for this member" →
  "...for this symbol" ("member" is internal universe-membership
  terminology); "No WATCH/TRADE names for the latest validation day" →
  "No Watch or Trade candidates from the latest validation run."
- **Market-health narrative parity** (real fix, not fabricated): the
  regime block in Market Context already rendered its persisted
  `explanation` sentence under the metric cards; the market-health block
  sat right next to it with no equivalent sentence, even though
  `MarketHealthContextDTO.explanation` is a real, already-computed field
  that simply wasn't being rendered. Now both blocks show their own
  explanation sentence — no new backend work, just surfacing data that
  already existed.
- **Label consistency**: the hero gauge's static label read "Composite
  score" while the rest of the app (including a code comment explicitly
  stripping the word "composite" from rendered text elsewhere) has
  standardized on plain "Score" — fixed the one outlier.
- **Deliberately left unchanged** (a real scoping decision, not an
  oversight): CLI-command instructions in a few empty/error states (e.g.
  "Re-run `./athena-daily smoke`") and HTTP-status/technical error text
  on the unlock screen. ATHENA is a single owner-operator tool — the same
  person reading these messages is the one who runs those exact commands
  — so this is accurate operational guidance for its one user, not
  jargon leaking to a separate non-technical audience the way the other
  fixes above were.

### Files created

- None.

### Files modified

- `src/athena/api/static/dashboard.js` — `decisionTypeBadge`,
  the qualified-names type chip, `renderTradePlan`'s no-plan sentence,
  `friendlyEligibilityLabel` (new) + `renderEligibilityDepth`,
  `analysisPercent`, the analysis-summary-card status badge, the regime/
  volatility/gap no-payload fallback, `renderDecisionContext`'s regime/
  market-health blocks (added the market-health explanation sentence),
  five tab-intro paragraphs, four empty-state messages, the Decision
  Timeline's decision-type fallback.
- `src/athena/api/static/index.html` — hero gauge label "Composite
  score" → "Score"; cache-bust bumped to `9.42.0`.
- `tests/api/platform/test_dashboard_hosting.py` — updated two
  assertions whose underlying text changed, added new assertions for the
  UX-8 copy fixes.
- `docs/MILESTONES.md` — UX-7 → Approved, UX-8 → Ready for review.
- This log.

### Public APIs

- None — pure frontend copy change, no backend files touched.

### Validation and architecture

- Full regression: **1018 passed** (unchanged — no backend files touched).
- Ruff clean on the one changed test file. mypy remains unavailable in
  this environment (pre-existing, unrelated).
- JS braces balanced (1524/1524); parens off by the same pre-existing +1
  baseline quirk.
- Live server restarted on `9.42.0`; isolated-browser console check on
  the pre-login page: zero errors.
- ADR-005 preserved: every rewritten sentence describes the same
  already-real computation/data it always did — nothing was invented,
  and the one new sentence added (market-health explanation) surfaces an
  existing, already-computed backend field that simply wasn't rendered
  before. No ADR required.

### Risks and technical debt

- This was a representative pass over the clearest, highest-value jargon
  leaks identified by an audit of both `index.html` and `dashboard.js`
  (~30 candidate findings), not an exhaustive line-by-line rewrite of
  every string in a ~6,400-line frontend — some lower-visibility spots
  may remain. Flagging this rather than claiming full coverage.
- I could not exercise the rewritten copy end-to-end myself (no owner
  credentials) — needs an owner read-through, especially of the five
  rewritten tab-intro paragraphs, to confirm the plain-English versions
  still read naturally in context.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: read through the Decision Brief's four tabs
  (especially the intro paragraph under each section heading) and
  confirm the plain-English rewrites read naturally; open a decision
  with no trade plan / no analog matches / no reasoning trace to see the
  updated empty states; check the hero gauge now reads "Score" instead
  of "Composite score."
- Next in the UX Overhaul program: **UX-9** (Quick actions + Portfolio
  Context + export/deep-link/share — needs a small backend
  portfolio-position-lookup addition, and "Compare"/"Portfolio Impact"
  still need a precise scope definition before implementation).

### Commit message

```text
refactor(dashboard): plain-English copy pass, fix jargon leaks (UX-8)

- Replace raw ALL_CAPS enum leakage (decision type, eligibility status)
  in chips and sentences with the friendly labels already established
  elsewhere in the app (friendlyAnalysisName, new
  friendlyEligibilityLabel matching the Universe table's wording).
- Rewrite five dense tab-intro paragraphs in plain English — same
  meaning (exact math over saved data, nothing invented), no more
  "persisted"/"config thresholds"/"ingestion"/"generated rationale"/
  "deterministic nearest-neighbor retrieval"/"fingerprint", and no
  internal module name ("AI Playbook Diagnostics") in trader-facing text.
- Fix several empty-state messages that leaked internal terminology
  ("member", raw "DecisionTrace", "provenance") or read as unhelpful
  dead ends.
- Surface MarketHealthContextDTO.explanation (a real, already-computed
  field) in the Market Context tab's market-health block, matching the
  explanation sentence the regime block already showed — parity fix,
  not new data.
- Rename hero gauge label "Composite score" to "Score", matching the
  app's own established convention (already stripped elsewhere).
- Deliberately leave CLI-command/HTTP-status operational text as-is —
  accurate guidance for ATHENA's single owner-operator, not jargon
  leaking to a separate audience.
- Update dashboard hosting tests for the rewritten copy; bump cache-bust
  to 9.42.0.
```

---

## UX-7 — Typography/spacing/elevation/color/animation/accessibility polish + CSS refactor (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Seventh (and, per plan, deliberately last) milestone of the owner's UX audit: a cross-cutting visual-consistency and accessibility pass. Owner additionally asked to fix the underlying maintainability problem — a single 4,903-line `dashboard.css` — with a proper refactor, and for genuine design-token normalization, not just a cosmetic pass |
| Scope | (1) Lossless split of `dashboard.css` into 14 `css/*.css` files by concern, loaded via an `@import` manifest; (2) ~85 new spacing/typography/elevation/color design tokens, substituted across all 14 files; (3) accessibility: global keyboard focus ring, dashboard-wide reduced-motion coverage, missing aria-labels, decorative-SVG aria-hidden, keyboard-operable decision cards |
| Tests | Full suite **1018 passed**; new dashboard-hosting assertions (tokens + accessibility); the token substitution itself was additionally verified via a full resolved-value diff against the pre-refactor stylesheet (688 changed lines, 0 real mismatches) — a stronger check than the usual manual screenshot review, run because this pass touches nearly every CSS line in the app |
| Coverage | Frontend-only change; no Python coverage impact; one test file touched, Ruff clean |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26) |
| Branch | feature/live-dashboard |

### Scope completed

- **CSS file split** (owner: "4900 lines of code in a single file... not maintainable"): the original `dashboard.css` was sliced at its own existing section-comment boundaries into 14 files under `css/`, grouped by concern —
  `00-tokens.css` (root design tokens), `01-base.css` (reset + new global
  a11y/motion rules), `02-auth.css` (unlock gate), `03-shell.css` (sidebar
  nav + header + workspace), `04-shared-components.css` (cards, tables,
  toast, progress bars), `05-portfolio.css`, `06-market-intelligence.css`,
  `07-universe-modals.css`, `08-strategies-backtest.css`,
  `09-decision-brief-shell.css` (cockpit header/banner/tabs),
  `10-trade-plan-chart.css`, `11-analysis-breakdown.css`,
  `12-decision-cards-dag.css` (Today's Decisions + Reasoning Trace),
  `13-context-history.css`. `dashboard.css` itself is now a 15-line
  `@import` manifest — the external contract (`/dashboard/dashboard.css`)
  is unchanged, so `index.html` needed only its usual cache-bust bump.
  Verified **byte-for-byte identical** to the original before any token
  substitution was applied (concatenated the 14 files in import order and
  diffed against a pre-split backup — empty diff). `StaticFiles` already
  mounts the whole static directory, so no route changes were needed;
  confirmed live via network-request inspection that all 14 files load
  in the correct cascade order with zero console errors.
- **Design tokens** (owner: "full design-token normalization"): rather
  than inventing a smaller "ideal" scale and accepting unverifiable
  visual drift, every token was named **after an exact value already in
  use** — e.g. `--space-8: 8px` for the existing `8px`, `--text-0-85:
  0.85rem` for the existing `0.85rem` — so every substitution is
  value-for-value identical to what it replaced. This is still a real
  maintainability win (one named source of truth instead of the same
  literal scattered across 100+ call sites) without gambling on visual
  regressions I can't see myself. Delivered:
  - **Spacing scale** — 20 tokens (`--space-1` … `--space-32`) covering
    every distinct padding/gap/margin px length found; substituted at
    365 declaration sites. A handful of true one-offs (a single `36px`,
    negative offsets, one `1.5rem`) were deliberately left as plain
    literals rather than given a token no one else would reference.
  - **Typography scale** — 38 tokens covering all 39 distinct font-size
    values (`inherit` excluded, not a length). The two former bare-px
    sizes (`9px`/`10px`) were folded into the rem scale as their exact
    equivalent at a 16px root (`0.5625rem`/`0.625rem`) so every
    font-size in the app now shares one unit — verified mathematically
    equivalent, not just visually similar.
  - **Elevation/shadow scale** — 14 tokens: `--shadow-xs` through
    `--shadow-xl` for the 5 distinct panel/overlay depths, plus
    `--ring-*`/`--glow-*` tokens standardizing the focus-ring and
    colored-glow patterns that were each hand-rolled slightly
    differently per component (17 of 21 `box-shadow` declarations
    substituted; the 3 pulse-keyframe-internal shadows and `none` were
    left as-is — they're intrinsic animation steps, not reusable values).
  - **Color consolidation** — 5 raw hex literals that were exact
    duplicates of an *existing* root variable (`#0b0f19`→`--bg-primary`,
    `#0f1626`→`--bg-sidebar`, `#64748b`→`--text-muted`,
    `#94a3b8`→`--text-secondary`, `#00f2fe`→`--accent`) now reference
    that variable instead. 12 new semantic `--tone-*` tokens were added
    for the shades that recur 2+ times with a clear, consistent
    good/bad/warn/info role across components (e.g. `--tone-good-text:
    #86efac`, the lighter/more-readable-on-dark green used for status
    text, distinct from the more saturated `--success: #00e676` used for
    solid fills — a deliberate existing distinction, not accidental
    duplication, so it was preserved rather than collapsed). 12
    genuinely one-off hex values (single occurrence, no reuse) were left
    as literals with no new token — consolidating those would have meant
    inventing abstraction for something used exactly once.
- **Accessibility fixes** (real, verifiable gaps, not the token-scale
  cosmetic work):
  - Global `:focus-visible` ring (`css/01-base.css`) — before this, only
    5 hand-picked `<input>`s anywhere in the app had *any* focus style;
    every button, nav link, tab, and modal control had zero visible
    keyboard-focus feedback. Verified live: tabbing to the pre-login
    "Unlock" button (previously no indicator at all) now shows a clear
    cyan ring.
  - Dashboard-wide `prefers-reduced-motion: reduce` handling — previously
    only the UX-5 Reasoning Trace flow-line animation was gated; now
    every `animation`/`transition` on the page (the persistent pulse dot,
    modal scale-in, toast slide-in, fade-ins) collapses to near-zero
    duration for users who've asked for reduced motion, via the standard
    "near-zero duration, !important" pattern.
  - `aria-label` added to the 3 icon-only header buttons that previously
    relied only on `title` (not reliably exposed as an accessible name
    to screen readers): logout, force-refresh, and the ops backup-list
    refresh button. Each icon inside also got `aria-hidden="true"`.
  - `aria-hidden="true"` on `#dag-svg-lines`, the decorative Reasoning
    Trace connector-line SVG overlay (no content of its own, purely
    visual).
  - "Today's Decisions" carousel cards (`renderDecisionCard` in
    `dashboard.js`) were previously a plain `<div>` with a click
    listener only — unreachable and unactivatable by keyboard. Added
    `tabindex="0"`, `role="button"`, an `aria-label`, and a keydown
    handler (Enter/Space triggers the same action as a click), without
    disturbing the existing nested dismiss-button's own click handling.
- **Deliberately deferred** (documented, not silently skipped): a
  systemic `aria-hidden` sweep across every decorative `<i class="fa...">`
  icon in the app (dozens of occurrences in `index.html` plus JS-rendered
  markup). Font Awesome icon glyphs are Private-Use-Area codepoints that
  modern screen readers don't expose by default, so this is a defensive
  best practice rather than an active bug fix for a severe gap — lower
  value relative to the effort of touching every icon in the codebase.
  Flagging it here rather than doing a low-confidence blanket sweep I
  can't fully verify.

### Files created

- `src/athena/api/static/css/00-tokens.css` through `13-context-history.css`
  (14 files, sliced from the original `dashboard.css`).

### Files modified

- `src/athena/api/static/dashboard.css` — replaced with a 15-line
  `@import` manifest (was the 4,903-line monolith).
- `src/athena/api/static/css/00-tokens.css` — ~85 new design tokens added
  to the existing `:root` block (spacing/typography/shadow/tone scales).
- `src/athena/api/static/css/01-base.css` — global `:focus-visible` rule;
  dashboard-wide `prefers-reduced-motion: reduce` rule.
- All 14 `css/*.css` files — font-size/padding/gap/margin/box-shadow
  literals substituted with the new tokens where a token exists; 5
  hex-literal-duplicate-of-existing-var occurrences deduplicated.
- `src/athena/api/static/index.html` — `aria-label`/`aria-hidden` on the
  3 icon-only header buttons and the DAG SVG overlay; cache-bust bumped
  9.38.0 → 9.39.0 (CSS split) → 9.40.0 (design tokens) → 9.41.0
  (accessibility).
- `src/athena/api/static/dashboard.js` — `renderDeckCard` gained
  tabindex/role/aria-label/keydown for keyboard operability.
- `tests/api/platform/test_dashboard_hosting.py` — added `_fetch_full_css`
  helper (resolves and concatenates the `@import` chain so existing CSS
  content assertions keep working against the split file), new
  assertions for tokens and accessibility.
- `docs/MILESTONES.md` — UX-6 → Approved, UX-7 → Ready for review.
- This log.

### Public APIs

- None — pure frontend refactor. `GET /dashboard/dashboard.css` still
  returns 200 (now an `@import` manifest instead of the full stylesheet);
  each `css/*.css` module is independently servable under
  `/dashboard/css/`.

### Validation and architecture

- Full regression: **1018 passed** (unchanged — no backend files touched).
- Ruff clean on the one changed `.py` test file. mypy remains unavailable
  in this environment (pre-existing, unrelated).
- **CSS split**: verified byte-for-byte identical to the pre-split
  monolith via direct concatenation + diff (empty diff) *before* any
  token substitution was applied.
- **Token substitution**: verified via a custom resolver that expands
  every `var(--token)` back to its literal value (following fallback
  chains) and diffs the result, line-by-line, against the pre-refactor
  file for every one of the 688 changed lines. Result: 0 unexplained
  mismatches; the only 2 differences are the intentional `9px`/`10px` →
  rem conversions, confirmed mathematically exact at a 16px root. One
  script-introduced defect was caught and fixed during this process (a
  hex-literal `var()` fallback got doubly-wrapped into
  `var(--bg-sidebar, var(--bg-sidebar))` — simplified to
  `var(--bg-sidebar)`).
- JS braces balanced (1520/1520); parens off by the same pre-existing +1
  baseline quirk. CSS braces balanced across all 14 files (742/742).
- Live server restarted on `9.41.0`; isolated-browser console check on
  the pre-login page: zero errors, all 14 `css/*.css` imports load
  (200 OK) in the correct cascade order, screenshot pixel-identical to
  pre-refactor, and the new focus-visible ring visually confirmed live
  on a keyboard tab to the "Unlock" button.
- ADR-005 not implicated — no data/explainability change, pure
  presentation-layer refactor. No ADR required: `@import`-based
  multi-file CSS is a standard technique, doesn't touch ADR-004's
  "no frontend framework" constraint (still hand-rolled CSS, just
  organized across files instead of one), and the `StaticFiles` mount
  already served the whole directory so no backend routing changed.

### Risks and technical debt

- `@import` adds one extra round-trip per file versus a single request,
  but this is a localhost-only, single-user app (ADR: FastAPI
  localhost-only) — the latency is unmeasurable in practice, confirmed
  live (all 14 imports resolved instantly alongside the main page load).
- The 12 genuinely one-off hex colors and the systemic decorative-icon
  `aria-hidden` sweep were deliberately deferred (documented above) —
  not technical debt so much as a scoped-out lower-priority tail.
- I could not exercise the refreshed dashboard end-to-end myself (no
  owner credentials) — the pre-login page and a resolved-value diff give
  strong confidence of zero visual regression, but only an owner
  click-through across the actual authenticated workstations (Portfolio,
  Market Intelligence, Strategies, Decisions & Trace, Live Operations)
  can fully confirm nothing shifted pixel-wise in practice.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: click through each workstation tab (Portfolio
  Overview, Market Intelligence, Strategies & Scans, Decisions & Trace,
  Live Operations) and confirm nothing looks different from before;
  specifically check hover/focus states on buttons and the Today's
  Decisions cards; try tabbing to a decision card and pressing
  Enter/Space to confirm it opens the same as a click; if your OS/browser
  has "reduce motion" enabled, confirm the pulse dot and modals no longer
  animate.
- This was planned as the **last** UX Overhaul milestone (typography/
  spacing/color polish makes most sense once the structure it's polishing
  is final). Remaining: **UX-8** (copy/vocabulary pass) and **UX-9**
  (quick actions + Portfolio Context + export/deep-link/share — still has
  open scope questions on "Compare"/"Portfolio Impact" from the original
  audit).

### Commit message

```text
refactor(dashboard): split monolithic CSS into 14 files, add design
tokens, fix accessibility gaps (UX-7)

- Split the 4,903-line dashboard.css into 14 css/*.css files by concern,
  loaded via an @import manifest from a slim dashboard.css entry point —
  verified byte-for-byte identical to the original before any value
  changed. External URL contract and index.html are unaffected.
- Add ~85 design tokens (20 spacing, 38 typography, 14 elevation/shadow,
  13 color) named after every distinct value already in use, and
  substitute them across all 14 files — zero visual drift, verified by
  resolving every token back to its literal and diffing against the
  pre-refactor file (688 changed lines, 0 unexplained mismatches).
- Add a global :focus-visible keyboard focus ring and dashboard-wide
  prefers-reduced-motion: reduce coverage (previously only 5 inputs and
  1 animation were handled respectively).
- Add aria-label to 3 icon-only header buttons, aria-hidden to the
  decorative DAG connector SVG, and make "Today's Decisions" cards
  keyboard-operable (tabindex/role/keydown) — previously click-only.
- Update test_dashboard_hosting.py to resolve the CSS @import chain for
  content assertions; add token + accessibility coverage. Bump
  cache-bust to 9.41.0.
```

---

## UX-6 — Sidebar summary + Historical Validation + Decision Timeline narrative + Decision History polish (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Sixth milestone of the owner's UX audit: keep symbol/stance/score/confidence/risk visible while scrolling the Reasoning Trace panel; show how similar past setups actually played out (win-rate/avg-return/avg-holding), not just their similarity %; make the Decision Timeline read as a narrative of what changed, not a bare list of timestamps; and show a friendly outcome-accuracy read in Decision History |
| Scope | Backend: `outcome_return_pct`/`outcome_holding_days` added to `DecisionAnalogDTO`, `win_rate_pct`/`avg_return_pct`/`avg_holding_days`/`outcomes_sample_size` added to `DecisionAnalogsDTO`, computed in `decisions_service.py` from the `TradeOutcome` already fetched per analog (no new queries). Frontend: `renderSidebarQuickSummary` (sticky Reasoning Trace strip), `renderHistoricalValidation` (analogs panel), `timelineNarrative` (Decision Timeline), `decisionAccuracyLabel` (Decision History outcome) |
| Tests | Full suite **1018 passed** (1 new backend test — mixed win/loss aggregate); new dashboard-hosting assertions; Ruff clean on all changed `.py` files |
| Coverage | New service math covered by 3 analog tests (single-outcome, mixed win/loss, empty); frontend is presentation-only |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26) |
| Branch | feature/live-dashboard |

### Scope completed

- **Sticky Reasoning Trace quick summary** (`renderSidebarQuickSummary`,
  `#dag-quick-summary`): a compact strip — symbol, stance chip, and
  score/confidence/risk bands — pinned to the top of the Reasoning Trace
  panel (`position: sticky` inside `.trace-dag-canvas-wrapper`'s own
  scroll region), so the trader doesn't lose the core facts while
  scrolling through DAG nodes and stage detail. Reuses `activeDecisionData`
  and `activeDepth` already loaded for the brief — no new fetch. Renders
  immediately with symbol/stance when a decision is selected; score/
  confidence/risk fill in ("—" until then) once `activeDepth` resolves,
  via the same `refreshDagNodeMeanings()` hook UX-5 added.
- **Historical Validation** (`renderHistoricalValidation`, backend
  aggregate fields): the "Similar past setups" panel now leads with a
  win-rate/avg-return/avg-holding-days summary computed from whichever
  shown analogs have a realized `TradeOutcome`. All exact arithmetic over
  already-persisted values — `return_pct = pnl / (entry_price * quantity)
  * 100` (reusing the existing direction-aware `pnl`, never a second
  computation of it) and `holding_days = holding_seconds / 86400` — both
  computed once per analog in `_outcome_return_and_holding` and aggregated
  in `_aggregate_analog_outcomes`. Shows an honest "no realized outcomes
  logged yet" message when the sample is empty, never a fabricated 0%/—.
- **Decision Timeline as narrative** (`timelineNarrative`): each entry now
  shows a factual one-line delta versus the prior entry — stance held or
  moved, and (when both entries have a parseable composite score, via the
  existing `decisionScoreValue`/`extractScoreFromText` technique already
  trusted for timeline sorting) whether score rose or fell and by how
  much. The earliest entry shown reads "Earliest tracked assessment."
  No new data source — same explanation text already rendered elsewhere.
- **Decision History outcome accuracy** (`decisionAccuracyLabel`): the
  realized-outcome card now leads with a friendly badge — e.g. "BUY call
  paid off" / "HOLD call didn't pay off" / "SELL call — broke even" —
  derived entirely from the same pnl sign already shown in the grid below
  it (cosmetic phrasing over an already-real value, same convention as
  `qualityBand`/`riskBand`), never a second, independent judgment of the
  decision.

### Files created

- None.

### Files modified

- `src/athena/api/v1/dtos/decisions.py` — `DecisionAnalogDTO` gained
  `outcome_return_pct`/`outcome_holding_days`; `DecisionAnalogsDTO` gained
  `win_rate_pct`/`avg_return_pct`/`avg_holding_days`/
  `outcomes_sample_size`.
- `src/athena/api/v1/services/decisions_service.py` —
  `_outcome_return_and_holding` and `_aggregate_analog_outcomes` static
  helpers; `get_decision_analogs` wires both into the DTOs it returns.
- `tests/api/v1/test_core_apis.py` — extended
  `test_decision_analogs_ranking` with the new per-analog/aggregate field
  assertions; added `test_decision_analogs_aggregate_mixed_win_loss`.
- `src/athena/api/static/index.html` — `#dag-quick-summary` container
  added to the Reasoning Trace panel; cache-bust bumped to `9.38.0`.
- `src/athena/api/static/dashboard.js` — `renderSidebarQuickSummary`
  (+ call sites in `renderDecisionBrief` and `refreshDagNodeMeanings`),
  `renderHistoricalValidation` (wired into `renderAnalogsPanel`),
  `timelineNarrative` (wired into `renderDecisionTimeline`),
  `decisionAccuracyLabel` (wired into `renderOutcomeResult`).
- `src/athena/api/static/dashboard.css` — `.dag-quick-summary` (+
  `-symbol`/`-metric`), `.historical-validation` (+ `-title`/`-stats`
  and tone variants), `.outcome-accuracy-badge` (+ tone variants),
  `.decision-timeline-narrative`.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-2/UX-5 reconciled to Approved (owner had
  already approved both in chat; the doc had drifted), UX-6 → Ready for
  review.
- This log.

### Public APIs

- `DecisionAnalogDTO` and `DecisionAnalogsDTO` gained additive optional
  fields (`outcome_return_pct`, `outcome_holding_days`, `win_rate_pct`,
  `avg_return_pct`, `avg_holding_days`, `outcomes_sample_size`) — no
  existing field removed or retyped, `GET /decisions/{id}/analogs`
  response shape is backward compatible.

### Validation and architecture

- Full regression: **1018 passed** (1 new backend test).
- Ruff clean on all changed `.py` files. mypy remains unavailable in this
  environment (pre-existing, unrelated).
- JS braces balanced (1517/1517); parens off by the same pre-existing +1
  baseline quirk. CSS braces balanced (739/739).
- Live server restarted on `9.38.0`; isolated-browser console check on
  the pre-login page: zero errors. Authenticated-app verification
  depends on an owner screenshot/click-through, as with every prior UX
  milestone — I have no login credentials for the live dashboard.
- ADR-005 preserved: `outcome_return_pct` and `outcome_holding_days` are
  exact arithmetic over already-persisted `pnl`/`entry_price`/`quantity`/
  `holding_seconds` (never a second computation of `pnl` itself, which
  stays owned by `record_trade_outcome`'s existing `_compute_pnl`); the
  aggregate fields are `None` (not 0/—) when no analog in the returned set
  has a realized outcome. No ADR required — additive DTO fields, no
  schema break, no new query pattern (the `TradeOutcome` lookup per
  analog already existed).

### Risks and technical debt

- The Historical Validation aggregate is computed only over the analogs
  actually *returned* (top-N by similarity, default 5), not the full
  `compared_count` pool — this is intentional (matches what the trader
  can see and click into) but worth knowing if the owner expects it to
  reflect a larger sample.
- `timelineNarrative`'s score comparison depends on `decisionScoreValue`'s
  text-extraction from the `explanation` string (pre-existing technique,
  reused, not new) — if a decision's explanation text doesn't mention a
  parseable score, the narrative silently omits the score delta and shows
  only the stance line, which is correct behavior but worth confirming
  reads well across a variety of real decisions.
- I could not exercise the new UI end-to-end myself (no owner
  credentials) — needs an owner click-through, ideally on a decision with
  logged analog outcomes (to see Historical Validation with real
  numbers) and one without (to confirm the honest empty state).
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: (a) open a decision's Reasoning Trace, scroll the
  panel, confirm the quick-summary strip stays pinned and shows real
  symbol/stance/score/confidence/risk; (b) open Decision History for a
  decision with analogs that have logged outcomes and confirm Historical
  Validation shows sensible win-rate/avg-return/avg-holding numbers (and
  the honest empty state for one with none); (c) confirm the Decision
  Timeline reads naturally as a narrative across a few entries; (d) log
  or view a realized outcome and confirm the new accuracy badge reads
  correctly for both a win and a loss.
- Next in the UX Overhaul program: **UX-7** (Typography, spacing,
  elevation, color-language, micro-animations, accessibility — the
  cross-cutting polish pass, deliberately done last).

### Commit message

```text
feat(dashboard): add Historical Validation, timeline narrative, sidebar
summary, and outcome accuracy to Decision History (UX-6)

- Add outcome_return_pct/outcome_holding_days to DecisionAnalogDTO and
  win_rate_pct/avg_return_pct/avg_holding_days/outcomes_sample_size to
  DecisionAnalogsDTO, computed in decisions_service from the TradeOutcome
  already fetched per analog — exact arithmetic over persisted pnl/entry/
  quantity/holding_seconds, None (not 0) when the sample is empty.
- Add renderHistoricalValidation to the analogs panel showing that
  aggregate, per owner UX audit — trader sees how similar setups actually
  played out, not just their similarity %.
- Add renderSidebarQuickSummary: a sticky symbol/stance/score/confidence/
  risk strip pinned to the top of the Reasoning Trace panel so the trader
  keeps context while scrolling DAG detail.
- Add timelineNarrative so the Decision Timeline reads as a factual
  stance/score delta per entry instead of a bare timestamp list.
- Add decisionAccuracyLabel: a friendly "call paid off/didn't pay off"
  badge over the same real pnl sign already shown in Decision History.
- Bump dashboard cache-bust to 9.38.0; add backend + dashboard-hosting
  test coverage; reconcile UX-2/UX-5 to Approved in docs/MILESTONES.md
  (owner had already approved both in chat, the doc had drifted).
```

---

## UX-5 — Reasoning Trace redesign (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Fifth milestone of the owner's UX audit: make the Reasoning Trace DAG feel like a flow rather than a static pipeline diagram, and replace each stage's generic lifecycle badge ("COMPLETED") with that stage's own real computed state, without ever inventing a value a stage doesn't actually have |
| Scope | `stageMeaning(stageId)` resolver reusing already-loaded `activeContextData`/`activeDepth`/`activeDecisionData`; DAG node badges now show the real state when available, falling back to the existing lifecycle badge otherwise; `refreshDagNodeMeanings()` upgrades already-rendered nodes once that async data arrives, without re-selecting or jumping tabs; connector lines get a subtle animated dash-flow (brighter/faster on edges touching the selected node), gated behind `prefers-reduced-motion` |
| Tests | Full suite **1017 passed**; new assertions; no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26; one fix pass applied — stale "Setup"/"Response" tab-name text) |
| Branch | feature/live-dashboard |

### Scope completed

- **`stageMeaning(stageId)`** (owner audit #14/#19 — "each node should show
  what actually happened, not just 'Completed'"): maps a stage id to a
  `{label, tone}` pair drawn from data already loaded elsewhere on the
  page — never a second fetch, never a fabricated value:
  - `regime` → the Trend-category regime label (e.g. "Bull Trend"), tone
    from the existing `contextChipTone` convention.
  - `market_health` → the `momentum` dimension label (or the first
    available dimension), same tone convention.
  - `score` / `confidence` / `risk` → the real `displayBand` each already
    shows in its Analysis card (`analysisPresentation`), toned
    good/warn/bad by band meaning (risk inverted: LOW is good, HIGH is
    bad).
  - `decision` → the real stance (`decisionStance` — BUY/SELL/HOLD/
    PASS/WAIT), toned by stance.
  - `trade_plan` → "Authorized" if a trade plan was persisted for this
    decision, "Not authorized" otherwise.
  - `evidence` → "Sufficient"/"Insufficient" from the persisted EVIDENCE
    gate result.
  - Any other/unmapped stage id (or a mapped one whose data hasn't
    loaded/isn't `OK` yet) returns `null` — `dagStatusBadgeHtml` then
    falls back to the pre-existing generic lifecycle badge. Nothing is
    ever guessed.
- **`refreshDagNodeMeanings()`**: the DAG renders before `activeDepth`/
  `activeContextData` finish loading (separate async calls), so it's
  called again from `loadDecisionDepth`'s and `loadDecisionContext`'s
  success paths to upgrade already-rendered badges in place. Deliberately
  does **not** call `selectNode`/`switchBriefTab` — this is a passive
  badge refresh, not a navigation event, avoiding a repeat of the
  previously-fixed "automatic highlight silently jumps the trader's tab"
  bug.
- **Animated connector flow** (owner audit #14 — "the trace should feel
  like a flow, not a diagram"): `drawDAGLines` now tags every SVG line
  `dag-flow-line`, and `dag-flow-line-active` for lines adjacent to the
  selected node. CSS drives a dashed-stroke animation
  (`stroke-dashoffset`) at two speeds — this is purely decorative, no new
  data is introduced — wrapped in `@media (prefers-reduced-motion:
  no-preference)` so trader accessibility settings are respected.

### Deferred (scope note, not a gap)

- **Per-stage completion/data-quality percentage** (part of the original
  audit point) was researched and explicitly **not** implemented for this
  milestone: only the `score`/`confidence`/`risk` blocks persist a
  `completeness` field, and that's already surfaced in their existing
  Analysis detail cards (`completenessLabel`). `regime`, `market_health`,
  `decision`, `trade_plan`, and `evidence` have no equivalent persisted
  field — adding one would mean inventing a number, which ADR-005
  forbids. If the owner wants this for those stages, it needs a backend
  addition first (a genuine, small one), not a client-side guess.

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html` — cache-bust bumped to `9.37.0`, then
  `9.37.1` for the fix pass below.
- `src/athena/api/static/dashboard.js` — `stageMeaning`,
  `stageToneColor` (folded into `stageMeaning`'s return), `dagStatusBadgeHtml`,
  `refreshDagNodeMeanings`; `renderTraceDAG`'s node-building loop now
  calls `dagStatusBadgeHtml` instead of always rendering the raw lifecycle
  status; `loadDecisionDepth`/`loadDecisionContext` call
  `refreshDagNodeMeanings()` after their data lands; `drawDAGLines` tags
  connector lines with `dag-flow-line`/`dag-flow-line-active`; fix pass
  added `BRIEF_TAB_LABELS` and used it in `showStageDetails`.
- `src/athena/api/static/dashboard.css` — `.dag-node-status.meaning-good/
  -bad/-warn/-neutral`; `.dag-flow-line`/`.dag-flow-line-active` +
  `@keyframes dag-flow-dash`, gated behind `prefers-reduced-motion`.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions,
  including the `BRIEF_TAB_LABELS` fix-pass assertions.
- `docs/MILESTONES.md` — UX-5 → Ready for review.
- This log.

### Fix pass (owner screenshots, 2026-07-26)

Two live screenshots (TCS/HOLD and DIXON/BUY) confirmed the core feature —
DAG nodes correctly showing real state (`SIDEWAYS`, `HEALTHY MOMENTUM`,
`SUFFICIENT`, `GOOD`, `HIGH`, `MEDIUM`, `HOLD`/`BUY`, `AUTHORIZED`) instead
of generic `COMPLETED` badges — but also surfaced a stale-copy bug in the
stage-detail panel underneath: clicking a node showed "Full detail lives
in the **Setup** tab" / "**Response** tab" instead of the actual renamed
visible labels "Trade Plan" / "Decision History". Root cause: UX-4
deliberately kept the internal `data-brief-tab` keys unchanged
(`setup`/`response`) while renaming only the visible tab text — but
`showStageDetails` was reconstructing the tab name via a raw
`friendlyLabel()` capitalization of that internal key, so it silently went
stale the moment the visible label diverged from the key. Fixed by adding
a single `BRIEF_TAB_LABELS` map (the one place this key→visible-label
association now lives) and using it in `showStageDetails` instead of
re-deriving the name from the key.

### Public APIs

- None — pure frontend change, no backend files touched.

### Validation and architecture

- Full regression: **1017 passed** (unchanged — no backend files touched).
- No Ruff/mypy scope on `.py` (only the one test file changed; `ruff check`
  on it is clean). mypy remains unavailable in this environment
  (pre-existing, unrelated).
- JS braces balanced (1468/1468); parens off by the same pre-existing
  +1 baseline quirk confirmed harmless in prior milestones. CSS braces
  balanced (722/722).
- Live server restarted; isolated-browser console check on the
  pre-login page: zero errors. Authenticated-app verification depends on
  an owner screenshot/click-through, as with every prior UX milestone —
  I have no login credentials for the live dashboard.
- ADR-005 preserved: every per-stage label rendered by `stageMeaning`
  traces to a value already computed and persisted elsewhere on the page;
  no new computation, no invented numbers. No ADR required.

### Risks and technical debt

- `stageMeaning`'s per-stage mapping is hand-written per stage id; a
  future new stage type would silently fall back to the generic lifecycle
  badge rather than error — acceptable, matches the existing
  `STAGE_ICONS`/`STAGE_TAB_MAP` fallback pattern, and is easy to extend.
- I could not exercise the redesigned DAG end-to-end myself (no owner
  credentials, and the effect depends on real trace/analysis data loading
  asynchronously) — needs an owner click-through across a few different
  decisions (including one with a stage that's genuinely `UNKNOWN`/not
  `OK`, to confirm the fallback badge still renders correctly).
- No new technical debt beyond the above.

### Remaining work

- Owner screenshots (TCS/HOLD, DIXON/BUY) already confirmed part (a): DAG
  nodes correctly show real per-stage state (`SIDEWAYS`, `HEALTHY
  MOMENTUM`, `SUFFICIENT`, `GOOD`, `HIGH`, `MEDIUM`, `HOLD`/`BUY`,
  `AUTHORIZED`) instead of the generic `COMPLETED` badge, and surfaced the
  `BRIEF_TAB_LABELS` bug fixed above.
- **Owner smoke test still needed**: (b) a decision with an
  `UNKNOWN`/not-`OK` stage still shows a sensible fallback badge, not a
  blank or broken one; (c) the connector lines show a subtle
  flowing-dash animation, brighter along the path to the selected node;
  (d) clicking a node still navigates to the right tab, the automatic
  first-node highlight on load still does **not** jump tabs, and the
  stage-detail panel's "Full detail lives in the X tab" text now reads
  the correct trader-facing tab name.
- Next in the UX Overhaul program: **UX-6** (Sidebar summary + Historical
  Validation + Decision Timeline narrative + Decision History polish —
  needs a small backend win-rate/avg-return aggregation addition).

### Commit message

```text
feat(dashboard): show real per-stage state in the Reasoning Trace DAG

- Add stageMeaning() resolving each DAG stage to its own already-loaded
  computed state (regime trend, market-health momentum, score/confidence/
  risk band, decision stance, trade-plan authorization, evidence
  sufficiency) instead of the generic "Completed" lifecycle badge, per
  owner UX audit #14/#19 — falls back to the lifecycle badge when no
  mapping applies or the underlying data isn't OK yet, never fabricated.
- Add refreshDagNodeMeanings() to upgrade already-rendered DAG badges once
  activeDepth/activeContextData resolve asynchronously, called from
  loadDecisionDepth/loadDecisionContext without triggering a tab jump.
- Add an animated dash-flow effect to DAG connector lines (brighter/faster
  toward the selected node), gated behind prefers-reduced-motion, per
  owner UX audit #14.
- Fix showStageDetails's "Full detail lives in the X tab" text reading
  "Setup"/"Response" instead of the actual renamed visible tab labels
  "Trade Plan"/"Decision History" (owner screenshot caught it live) — add
  BRIEF_TAB_LABELS as the single source for that key-to-label mapping.
- Bump dashboard cache-bust to 9.37.0, then 9.37.1 for the fix pass, and
  extend dashboard hosting test assertions for the new functions/CSS
  classes and the fix.
```

---

## UX-4 — Tab renaming + progressive disclosure + Market Context cards (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Fourth milestone of the owner's UX audit: replace engineering tab names with trader-facing ones, make the Analysis tab's component breakdown a deliberate second step rather than everything visible at once, and present regime/market-health as labeled cards instead of a flat row of chips |
| Scope | Tab labels renamed (internal `data-brief-tab` keys unchanged); Score/Confidence/Risk component breakdown moved behind a "View detailed breakdown" toggle; `renderDecisionContext`'s regime/market-health blocks rebuilt as metric-card grids |
| Tests | Full suite **1017 passed**; new assertions; no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26) |
| Branch | feature/live-dashboard |

### Scope completed

- **Tab renaming**: Setup → **Trade Plan**, Context → **Market Context**,
  Response → **Decision History** (Analysis unchanged, matching the
  owner's exact suggested naming). Only the visible `<span>` text changed
  — `data-brief-tab="setup"/"context"/"response"` internal keys are
  untouched, so `STAGE_TAB_MAP`, `switchBriefTab`, and every existing test
  keep working without modification.
- **Progressive disclosure in Analysis** (`renderDecisionDepth`): the full
  Score/Confidence/Risk component stack (star ratings, trust checklist,
  risk summary — all from earlier UX-2 work) now sits behind a "View
  detailed breakdown" `<details>` toggle, closed by default. The first
  thing a trader sees on opening Analysis is just the three overview cards
  — the same drill-down the owner's audit described (Overview → category →
  expand → component → expand → raw values), now with one more explicit
  step at the top instead of the full component stack rendering
  immediately below the overview.
- **Market Context as cards, not labels** (`contextMetricCard`,
  `regimeLabelCategory`): regime labels (e.g. `BULL_TREND`,
  `NORMAL_VOLATILITY`, `GAP_DOWN`) and market-health dimensions (already a
  clean `{name: label}` mapping) now render as small labeled metric cards
  (category caption + value, colored by the same `contextChipTone`
  convention already used for chips) instead of an undifferentiated row of
  pills. `regimeLabelCategory` derives a category from the label text
  itself (VOLATILITY/GAP/BREADTH/TREND, falling back to a generic caption)
  — a display grouping over already-real data, not a fabricated dimension.
  Session/expiry/holiday flags are left as chips (they're boolean flags,
  not label+value dimension pairs, so the "cards" treatment doesn't apply
  there).

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html` — tab label text; cache-bust bumped
  to `9.36.0`.
- `src/athena/api/static/dashboard.js` — `contextMetricCard`,
  `regimeLabelCategory`; `renderDecisionDepth`'s detail-toggle wrapper;
  `renderDecisionContext`'s regime/market-health block rebuild.
- `src/athena/api/static/dashboard.css` — `.analysis-detail-toggle` (+
  chevron), `.context-metric-grid` (+ `-label`/`-value`), `.tone-unknown-text`.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-3b flipped to Approved, UX-4 → Ready for review.
- This log.

### Public APIs

- None — pure frontend change.

### Validation and architecture

- Full regression: **1017 passed** (unchanged — no backend files touched).
- No Ruff/mypy scope (no `.py` files changed).
- JS brace/paren balance checked against the pre-edit baseline; live
  server restart + isolated-browser console check: zero errors on load.
- ADR-005 preserved: metric cards and category labels render already-real
  persisted label strings, nothing generated. No ADR required.

### Risks and technical debt

- `regimeLabelCategory`'s pattern matching covers the known regime label
  families (trend/volatility/gap/breadth); any genuinely new label family
  added to the regime engine in the future would fall back to a generic
  "Regime" caption rather than a specific one — not incorrect, just less
  specific, and easy to extend if it comes up.
- I could not exercise the redesigned tabs/cards end-to-end myself (no
  owner credentials) — needs an owner click-through.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: confirm the renamed tabs read naturally; open
  Analysis and confirm the overview cards show first with the component
  breakdown behind one click; open Market Context and confirm regime/
  market-health render as clean labeled cards rather than a chip wall.
- Next in the UX Overhaul program: **UX-5** (Reasoning Trace redesign —
  animated flow, meaningful per-stage labels instead of generic
  "Completed," completion/data-quality percentage per stage).

### Commit message

```text
feat(dashboard): rename tabs, add progressive disclosure, redesign Market Context as cards (UX-4)

- Rename Decision Brief tabs to trader-facing labels (Trade Plan/Analysis/Market Context/Decision History); internal data-brief-tab keys unchanged so STAGE_TAB_MAP and existing tests keep working
- Move the Analysis tab's Score/Confidence/Risk component breakdown behind a "View detailed breakdown" toggle, closed by default, so the overview cards are the first thing shown
- Rebuild Market Context's regime/market-health blocks as labeled metric cards (category + value, same tone coloring as the existing chips) instead of a flat row of chips
```

---

## UX-3b — Chart ATR/moving-average/volume overlay (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | "Professional mini-TradingView style" chart (owner UX audit #11): the intraday chart gains a moving-average line, an ATR volatility envelope, and a volume subplot |
| Scope | New `atr_series`/`sma_series` pure functions in `indicators/calculations.py` (existing scalar `atr()`/`sma()` now delegate to them — byte-identical output); `CandleDTO` gains optional `atr`/`moving_average` fields, populated by `MarketHistoryService.recent_candles` using the same config-driven periods (`config/indicators.json`) already used elsewhere; frontend chart renders the MA line, ATR band, and volume bars; also fixed Entry Zone showing "₹X – ₹X" when low==high |
| Tests | Full suite **1017 passed** (+1 backend test verifying the service's per-candle output matches the pure functions exactly); Ruff clean; mypy currently unavailable in this environment (missing since earlier in the session, unrelated to this change) — types manually reviewed |
| Coverage | Existing project coverage retained |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26 — Y-axis fix pass verified against live screenshots) |
| Branch | feature/live-dashboard |

### Scope completed

- **`atr_series`/`sma_series`** (`indicators/calculations.py`): full per-bar
  series versions of the existing scalar `atr()`/`sma()`, retaining every
  intermediate Wilder-smoothed/rolling-window value instead of discarding
  all but the last. The scalar functions now **delegate** to the series
  functions (`series[-1]`) rather than duplicating the math — guarantees
  the chart's ATR/MA line and the TradePlan's D1-based sizing can never
  silently diverge from the same underlying computation. Verified
  byte-identical against the pre-existing `tests/decision/test_indicators.py`
  suite (26 tests, all still pass unchanged).
- **`align_trailing_series`**: pads a trailing series (which starts partway
  through the candle history, once enough bars exist) with `None` for the
  warmup prefix — honest "not yet computable," never an invented early
  value.
- **`CandleDTO.atr`/`.moving_average`** (both `Decimal | None`, default
  `None`): additive fields, no existing consumer breaks.
  `MarketHistoryService.recent_candles` computes both using the exact same
  periods already configured in `config/indicators.json` (`atr.period=14`,
  `sma.period=20`) — no new config, no duplicated thresholds.
- **Chart rendering** (`renderCandlestickSvg`): a moving-average polyline,
  a semi-transparent ATR envelope (MA ± ATR, filled only across indices
  where both values are actually known — never interpolated across a
  gap), and a volume bar subplot beneath the price chart (up/down colored
  to match the candle bodies above it). Y-axis scaling now also accounts
  for the ATR band's price range so it's never clipped. Legend gained
  "Moving average," "ATR band," and "Volume" entries.
- **Entry Zone display fix** (owner-reported): when `entry_low ==
  entry_high`, the Trade Plan card now shows the single price instead of
  "₹13,781.00 – ₹13,781.00," which read as a rendering glitch.

### Files created

- None.

### Files modified

- `src/athena/indicators/calculations.py` — `sma_series`, `atr_series`,
  `align_trailing_series`; `sma`/`atr` now delegate to their series.
- `src/athena/api/v1/dtos/market.py` — `CandleDTO.atr`/`.moving_average`.
- `src/athena/api/v1/services/market_history_service.py` — `config_dir`
  constructor param; computes/attaches the aligned series per candle.
- `src/athena/api/dependencies.py` — `get_market_history_service` passes
  `config_dir`.
- `tests/api/v1/test_market_history.py` — new test verifying per-candle
  output matches `atr_series`/`sma_series` exactly, warmup is honestly
  `None`.
- `src/athena/api/static/dashboard.js` — `renderCandlestickSvg` gains the
  MA/ATR/volume rendering; chart legend entries; `renderTradePlan`'s
  entry-zone single-value fix.
- `src/athena/api/static/dashboard.css` — `.decision-chart-ma-line`,
  `.decision-chart-atr-band`, `.decision-chart-volume-bar` (+ legend
  swatches).
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-3a flipped to Approved, UX-3b → Ready for review.
- Cache-bust: `9.34.0` → `9.35.0` → `9.35.1` (fix pass, below).
- This log.

### Fix pass (2026-07-26, owner live screenshot)

Owner-reported: the chart's Y-axis showed an absurd range (-907 to 16,026)
for a stock trading around ₹13,000-15,000, squeezing the Entry Zone/Stop/
Target lines and their labels together at the very top. Root cause: a
classic JavaScript gotcha — `Number(null)` evaluates to `0`, not `NaN`.
With only 11 candles in this chart (below both the 14-period ATR and
20-period SMA warmup), every candle's `atr`/`moving_average` is genuinely
`null` from the API — correct, honest behavior — but `numericOrNull`
coerced each `null` into a fake reading of exactly `0` instead of treating
it as "not available." That silently injected a price of `0` into both the
rendered MA line/ATR band (a spurious flat line/band at the bottom of the
plot) and the Y-axis autoscale (forcing the range down to include `0`).
Fixed by checking for `null`/`undefined` explicitly before the `Number()`
coercion. Cache-bust `9.35.1`. Full suite still **1017 passed** (this is a
pure frontend logic fix, not something a Python test could have caught);
live server restart + browser console check: zero errors.

### Public APIs

- `CandleDTO` gains two additive, optional fields (`atr`, `moving_average`)
  — backward compatible, no existing consumer breaks. No other API surface
  changed.

### Validation and architecture

- Full regression: **1017 passed** (was 1016; +1 new backend test).
- Ruff clean on every touched file. mypy unavailable in this environment
  (disappeared from the toolchain since earlier in this session, unrelated
  to this change) — reviewed all touched signatures/types manually;
  existing `tests/decision/test_indicators.py` (26 tests) confirms the
  scalar/series delegation produces identical output.
- JS brace/paren balance checked against the pre-edit baseline; live
  server restart (clean startup — confirms the new config-loading path
  works) + isolated-browser console check: zero errors on load.
- No order-placement path touched. ADR-005 preserved: ATR/MA are pure,
  deterministic, already-existing-formula computations over persisted
  candle history — never generated, never a second independently-derived
  number (the scalar TradePlan-sizing ATR and the chart's ATR line share
  one function). No ADR required — additive DTO fields, not a domain
  object change.

### Risks and technical debt

- I could not exercise the redesigned chart end-to-end myself (no owner
  credentials) — needs an owner click-through, especially to confirm the
  ATR band/MA line/volume subplot read clearly rather than adding clutter.
- mypy being unavailable in this environment is a pre-existing
  environment issue, not something this change introduced or can fix —
  flagging for awareness, not treating as this milestone's technical debt.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: open a decision with enough candle history (≥21
  bars) to clear both the ATR (14) and SMA (20) warmup periods; confirm
  the moving-average line and ATR band render sensibly against price;
  confirm the volume subplot reads clearly; confirm a short-history
  decision (< 21 bars) shows the chart with no MA/ATR line rather than an
  error. Confirm the Entry Zone single-value fix reads correctly for a
  zero-width entry.
- This closes out **UX-3** (both 3a and 3b). Next in the UX Overhaul
  program: **UX-4** (tab renaming + progressive disclosure + Market
  Context cards).

### Commit message

```text
feat(indicators,dashboard): add ATR/moving-average/volume chart overlay (UX-3b)

- Add atr_series/sma_series pure functions to indicators/calculations.py; existing scalar atr()/sma() now delegate to them (byte-identical output, verified by the existing 26-test indicator suite) so the chart and TradePlan sizing can never silently diverge
- Add CandleDTO.atr/.moving_average (additive, optional) and align_trailing_series for honest None-padding during warmup, never an invented early value
- Wire MarketHistoryService.recent_candles to compute both using the same config/indicators.json periods already used elsewhere (atr=14, sma=20), no new config
- Add moving-average line, ATR envelope, and volume subplot to renderCandlestickSvg; fix Entry Zone showing "X - X" when entry_low equals entry_high
```

---

## UX-3a — Trade Plan visual redesign (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Third milestone of the owner's UX audit: "huge numbers, professional" — the Trade Plan's entry/stop/target/R:R deserve the same visual weight as the cockpit gauges, not small dense text |
| Scope | `renderTradePlan` restructured into a hero-metric grid; new **Expected Return %** figure computed from the plan's own persisted `entry_low`/`entry_high`/`targets[0]` (pure arithmetic, never invented) |
| Tests | Full suite **1016 passed**; new assertions; no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26 — math verified against the live screenshot) |
| Branch | feature/live-dashboard |

### Scope completed

- **Trade Plan hero grid**: Entry zone, Stop, Target(s), Expected Return,
  Risk:Reward each get their own bordered metric card with a large
  (1.15rem mono) value — the same visual language as the cockpit gauges —
  replacing the old dense 2-column grid of small text. Model units/risk
  amount moved to a smaller secondary row underneath (still shown, just
  de-emphasized relative to the tradeable levels).
- **Expected Return %** (`computeExpectedReturnPct`): `((target - entryMid)
  / entryMid) * 100`, using the nearest target (`targets[0]`) since that's
  the one most likely to be hit; sign-flipped for SHORT decisions. When a
  plan has more than one target, the caption reads "to T1" so it's never
  ambiguous which target the percentage refers to. Pure arithmetic over
  already-persisted `TradePlan` fields — no new backend field, nothing
  invented, per ADR-005.
- Removed the now-dead `.trade-plan-grid`/`.trade-plan-metric` CSS (only
  consumer was the old template, and the DAG-panel duplicate that rendered
  it was already removed in an earlier milestone).

### Files created

- None.

### Files modified

- `src/athena/api/static/dashboard.js` — `computeExpectedReturnPct`;
  `renderTradePlan` signature gains `direction`; call site updated.
- `src/athena/api/static/dashboard.css` — `.trade-plan-hero-grid` (+
  `-metric`/`-label`/`-value`/`-caption`), `.trade-plan-secondary-row`;
  removed dead `.trade-plan-grid`/`.trade-plan-metric` rules.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-3 split into UX-3a (this) and UX-3b (chart
  ATR/MA/volume overlay, researched but not yet implemented).
- Cache-bust: `9.33.2` → `9.34.0`.
- This log.

### Public APIs

- None — pure frontend change.

### Validation and architecture

- Full regression: **1016 passed**. No Ruff/mypy scope.
- JS brace/paren balance checked against baseline; live server restart +
  isolated-browser console check: zero errors on load.
- ADR-005 preserved: Expected Return % is arithmetic over already-persisted
  fields, never generated or invented. No ADR required.

### Risks and technical debt

- None beyond needing an owner click-through (no login credentials).

### Remaining work

- **Owner smoke test**: open a TRADE decision, confirm Entry/Stop/Target/
  Expected Return/R:R all read clearly at the new size; confirm Expected
  Return's sign and "to T1" caption make sense for both LONG and SHORT
  decisions if you have one of each.
- **UX-3b** (chart ATR/moving-average/volume overlay) is scoped but not yet
  implemented — see `docs/MILESTONES.md` for the research summary. Owner
  go-ahead already given; will implement as its own change set given the
  backend work involved (new indicator series functions + DTO extension).

### Commit message

```text
feat(dashboard): redesign Trade Plan with hero-sized numbers and Expected Return % (UX-3a)

- Restructure renderTradePlan into a hero-metric grid (Entry/Stop/Target/Expected Return/R:R), matching the cockpit gauges' visual weight instead of small dense text
- Add computeExpectedReturnPct: pure arithmetic over the plan's own persisted entry/target values, sign-aware for SHORT decisions, captioned "to T1" when there's more than one target
- Remove dead .trade-plan-grid/.trade-plan-metric CSS (no longer referenced after the Decisions & Trace redesign removed the DAG-panel duplicate)
```

---

## UX-2 — Score/Confidence/Risk storytelling (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | Second milestone of the owner's UX audit: replace the raw dimension bars in the Analysis tab with storytelling that matches each tone — star-rated contributors for Score, a trust checklist for Confidence, a categorized hazard summary for Risk — plus a reassuring safety-gate headline and a Decision Quality Meter ladder |
| Scope | `renderAnalysisSummaryCard`/`renderAnalysisBlock` restructured to dispatch by tone; every band/percentage/star sourced from already-persisted `AnalysisDimensionDTO` fields (`value`, `level`, `weight`, `weighted`) — no client-side re-derivation of config thresholds |
| Tests | Full suite **1016 passed**; new assertions for every new function/class; no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner confirmed live, approved starting UX-3) |
| Branch | feature/live-dashboard |

### Scope completed

- **Score contributors as storytelling** (`renderScoreContributors`, `starRating`,
  `starGlyphs`, `dimensionContributionPct`): dimensions ranked by actual
  value (highest first), each shown as a 1-5 star rating plus its *real*
  contribution percentage — computed from the already-persisted `weight`/
  `weighted` fields on `AnalysisDimensionDTO` (`weighted / sum(weighted)`),
  never a client-side copy of `config/scoring.json`'s weight table that
  could silently drift out of sync with the real config.
- **Confidence as "why ATHENA trusts this"** (`renderConfidenceChecklist`,
  `CONFIDENCE_TRUST_LABELS`): the six raw dimension names (evidence
  completeness, data freshness, indicator availability, cross-engine
  agreement, unknown ratio, consistency) become a ✔/✘ checklist with plain
  labels ("Evidence is complete," "Engines agree with each other"). Trust
  vs. flag comes entirely from the backend's own persisted `level`
  (anything not `LOW` counts as trusted) — no new numeric threshold
  invented client-side.
- **Risk as a categorized "Major Risks" summary** (`renderRiskSummary`):
  the six raw dimensions (volatility/liquidity/gap/event/market-environment/
  concentration risk) sorted by severity (highest first), each banded
  Low/Medium/High via the same `riskBand` helper the Hero cockpit gauge
  already uses — one hazard scale throughout, never two disagreeing ones.
- **Decision Quality Meter** (`qualityLadder`, `QUALITY_LADDER_BANDS`): a
  5-segment ladder (Weak→Excellent) under the Score summary card, marking
  the same band word already shown above it — Score has no backend-computed
  level (`scoring.json` carries no levels block), so `analysisPresentation`
  now derives a `displayBand` per tone: Score uses the client `qualityBand`
  (same one from UX-1's Hero gauge); Confidence/Risk keep showing their
  real backend level, never overridden by a client approximation.
- **Safety checklist summary** ("All safety checks passed" / "Blocked on N
  of M safety checks") — a reassuring headline over the exact same gate
  results already listed below it, not a separate computation.
- **Fix pass, same turn** (owner live screenshots, cache-bust `9.32.1`):
  found two bugs while reviewing the screenshots closely before starting
  UX-2 — (1) the Hero cockpit gauges banded a fabricated "Weak"/"0.0" for a
  block whose depth status wasn't `"OK"` (Decision Banner correctly said
  "score 66.92," gauge said "Weak 0.0" for the same decision) — fixed by
  gating the band/value/bar entirely on `status === "OK"`, showing
  "Unknown"/"—" otherwise, matching what the Executive Summary already did
  correctly; (2) the Reasoning Trace's automatic "highlight stage 0 on
  load" was calling the same tab-jump logic as a real click, silently
  overriding whichever tab the trader had chosen every time they picked a
  new decision — fixed via `selectNode(stageId, { userInitiated })`, which
  only jumps tabs when `userInitiated` is true.

### Files created

- None (all additive/restructuring within existing files).

### Files modified

- `src/athena/api/static/dashboard.js` — `dimensionContributionPct`,
  `dimensionExplanationBody`, `starRating`, `starGlyphs`,
  `renderScoreContributors`, `CONFIDENCE_TRUST_LABELS`,
  `renderConfidenceChecklist`, `renderRiskSummary`, `qualityLadder`,
  `QUALITY_LADDER_BANDS`; `analysisPresentation` extended with
  `displayBand`; `renderAnalysisSummaryCard`/`renderAnalysisBlock`
  restructured; safety-checklist summary line in `renderDecisionBrief`;
  `renderCockpitGauges` status-gating fix; `selectNode` `userInitiated` fix.
- `src/athena/api/static/dashboard.css` — `.analysis-summary-band`,
  `.quality-ladder`, `.score-contributor-row`, `.trust-checklist-row`,
  `.risk-summary-row`, `.risk-band-chip`, `.safety-checklist-summary`.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions.
- `docs/MILESTONES.md` — UX-1 flipped to Approved, UX-2 → Ready for review.
- Cache-bust: `9.32.0` → `9.32.1` (fix pass) → `9.33.0` (UX-2) → `9.33.1`
  (second fix pass, below).
- This log.

### Second fix pass (2026-07-26, owner live screenshots of UX-2)

Owner-reviewed the live Score/Confidence/Risk breakdowns closely; one real
issue found and fixed:

- **Score contributors were sorted by star rating, not by actual
  contribution.** A dimension with 4 stars but only 12% of the score
  (Liquidity) was listed above one with 3 stars but 21% (Market Quality) —
  since the whole point of the list is "what actually drove the score,"
  ranking by raw value instead of the real weight-derived contribution
  produced a confusing order. Fixed: `renderScoreContributors` now sorts by
  `contributionPct` (falling back to raw value only when a dimension has no
  persisted `weighted` figure to rank by).
- Also bumped the Decision Quality Meter ladder's visual weight slightly
  (4px → 6px, added a subtle highlight ring on the active segment) since it
  was hard to confirm from a screenshot whether it was rendering at all.

### Third fix pass (2026-07-26) — Decision Timeline moved out of the Context tab

Owner-reported: the Decision Timeline's entries aren't just a history
display — clicking one actually switches the entire brief to that other
decision (`renderDecisionTimeline`'s rows already called `selectBriefing`),
but it was buried inside the Context tab where that significance wasn't
obvious. Moved it into `.decision-brief-hero` — the section that already
renders once per decision, outside all four tab panes, right below the
Decision Banner/Executive Summary — so it's now visible regardless of which
tab is active, with an explicit hint ("Click an entry to view ATHENA's
assessment at that point in time") for discoverability. No function
changed, no new element ids — same `renderDecisionTimeline`/
`#decision-history-timeline`, only relocated in the template. Cache-bust
`9.33.2`. Full suite still **1016 passed**; live server restart + browser
console check: zero errors.

### Public APIs

- None — pure frontend restructuring, no backend/API surface touched.

### Validation and architecture

- Full regression: **1016 passed** (unchanged — no backend files touched).
- No Ruff/mypy scope (no `.py` files changed).
- JS brace/paren balance checked against the pre-edit baseline after every
  edit in this turn; live server restart + isolated-browser console-error
  check after both the fix pass and UX-2: zero errors on load.
- ADR-005 preserved: every star/percentage/checklist tick is arithmetic or
  a direct read of an already-persisted field (`value`, `level`, `weight`,
  `weighted`), never generated or client-invented. No ADR required.

### Risks and technical debt

- I could not exercise the redesigned Analysis tab end-to-end myself (no
  owner credentials) — needs an owner click-through.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: expand Score/Confidence/Risk breakdowns on a few
  decisions; confirm star ratings and contribution % look sensible against
  the raw values; confirm the confidence checklist's ✔/✘ matches what you'd
  expect from each dimension's level; confirm risk dimensions are sorted
  worst-first with sensible Low/Medium/High bands; confirm the safety
  checklist headline matches the gate list below it.
- Next in the UX Overhaul program: **UX-3** (Trade Plan visual redesign +
  chart ATR/MA overlay — needs your go-ahead on the chart backend addition
  first).

### Commit message

```text
feat(dashboard): add score/confidence/risk storytelling (UX-2); fix gauge and DAG-tab bugs

- Add renderScoreContributors: star-rated score dimensions ranked by value, with real contribution % from persisted weight/weighted fields, never a re-derived config-weight table
- Add renderConfidenceChecklist: "why ATHENA trusts this" checklist driven entirely by each dimension's real backend level
- Add renderRiskSummary: Major Risks categorized Low/Medium/High, worst first, same riskBand scale as the Hero gauge
- Add a Decision Quality Meter ladder for Score (no backend level exists for it) and a safety-checklist reassurance headline over the existing gate list
- Fix: cockpit gauges no longer band a fabricated "Weak"/"0.0" when the underlying block's status isn't OK
- Fix: Reasoning Trace's automatic first-node highlight no longer force-switches the brief's active tab — only a real click does
```

---

## UX-1 — Hero Decision Card + Executive Summary + Decision Banner (APPROVED)

| | |
|---|---|
| Completed | 2026-07-26 |
| Objective | First milestone of the owner's 40-point "ATHENA UX Overhaul" audit (`docs/MILESTONES.md`): make the top of the Decision Brief answer "what happened / why / what should I do" in under 5 seconds — meaning over decimals, an executive-briefing feel over a metrics strip |
| Scope | Sticky cockpit gauges gain band words (Strong/Good/Weak, Low/Medium/High) alongside the raw numbers; a 4th "Expected R:R" card; the old plain thesis paragraph becomes a colored Decision Banner ("ATHENA Recommendation: BUY") plus a 5-line Executive Summary composed from already-persisted engine explanations |
| Tests | Full suite **1016 passed** (new assertions for every new element); no backend files touched |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **APPROVED** (owner smoke confirmed live 2026-07-26; two bugs found and fixed in the same turn — see UX-2's fix-pass note above) |
| Branch | feature/live-dashboard |

### Scope completed

- **Band words, not just decimals** (`qualityBand`, `riskBand`): Composite
  score and Confidence get a 5-band quality word (Weak → Excellent, 40/55/
  70/85 breakpoints); Risk gets its own 3-band hazard word (Low/Medium/
  High, since "Weak risk" reads as nonsense) — both purely cosmetic
  client-side bands over the same already-computed 0-100 value, colored via
  the existing `gaugeToneColor`. The raw number moves to a smaller
  secondary caption underneath.
- **Expected R:R joins the cockpit** as a 4th gauge card, read straight from
  `decision.trade_plan.risk_reward` (no computation, `—` when there's no
  trade plan) — synchronous, no async load needed.
- **Decision Banner** replaces the plain thesis paragraph: a colored strip
  (reusing the *exact* `stance-buy`/`stance-sell`/`stance-hold`/`stance-pass`
  /`stance-wait` palette already used for the header chip — one color
  meaning throughout, never remapped) headed "ATHENA Recommendation" with
  the stance and the same reused `formatDecisionSummary().headline`
  sentence as the reason.
- **Executive Summary** (`buildExecutiveSummaryLines`, `renderExecutiveSummary`):
  up to 5 lines — gates pass/fail count, then the score/confidence/risk
  engines' own persisted `.explanation` strings verbatim (sanitized for
  numeric formatting), then a decision-type suitability line. Every line is
  either a deterministic count or a string an engine already wrote — never
  generated, per ADR-005. Gates + suitability render immediately (synchronous
  data); the three explanation lines fill in once `loadDecisionDepth`
  resolves (progressive fill, same pattern as the rest of the brief).
- **Two fields from the owner's example deliberately omitted**: "Holding:
  2-5 Days" and "Strategy: Momentum Breakout." Researched first (2026-07-26)
  — confirmed neither exists prospectively anywhere in the domain model,
  config, or DTOs (`TradeOutcome.holding_seconds` is retrospective-only,
  computed after a trade closes; the Strategy Framework can classify
  *already-completed* decisions against a strategy but never writes that
  classification back onto the `Decision`). Showing either would mean
  inventing a value — flagged instead as a possible small backend addition
  for a future milestone, not fabricated client-side.

### Fix pass (2026-07-26, owner live screenshots)

Owner approved the milestone live, but two real bugs surfaced from close-reading
the screenshots, both fixed (cache-bust `9.32.1`):

- **Gauges fabricated a "Weak"/"0.0" band for an unavailable block.** A HOLD/
  WATCH decision's Decision Banner correctly said "score 66.92/100" while
  the gauge above it showed Composite Score "Weak 0.0/100" — the Executive
  Summary correctly detected the depth report's status wasn't `"OK"` and
  omitted its lines, but `renderCockpitGauges` banded the raw value without
  checking status first. Fixed: gauges now show "Unknown"/"—" whenever the
  underlying block's status isn't `"OK"`, matching what the Executive
  Summary already did correctly.
- **Reasoning Trace's auto-highlighted first node silently overrode the
  user's chosen tab.** `selectNode()` was called both by an actual click
  and by the automatic "highlight stage 0 on load" — both paths triggered
  the same tab-jump, so picking a new decision would silently yank the
  brief back to whichever tab the first stage mapped to (usually Context),
  contradicting the stated "tab persists across decision switches" design.
  Fixed: `selectNode(stageId, { userInitiated })` only jumps tabs when
  `userInitiated` is true — the automatic initial highlight passes `false`.

### Files created

- None (all additive/restructuring within existing files).

### Files modified

- `src/athena/api/static/index.html` — gauges row expanded to 4 cards with
  band-word elements; cache-bust bumped to `9.32.0`.
- `src/athena/api/static/dashboard.js` — `qualityBand`, `riskBand`,
  `buildExecutiveSummaryLines`, `renderExecutiveSummary`; extended
  `renderCockpitGauges`/`resetCockpitGauges`; `renderDecisionBrief`'s hero
  section rebuilt as Decision Banner + Executive Summary.
- `src/athena/api/static/dashboard.css` — `.decision-banner` (+ stance
  variants), `.executive-summary-list`, `.hero-metric-band`, 4-column
  gauge grid; removed the now-dead `.decision-brief-thesis` rule.
- `tests/api/platform/test_dashboard_hosting.py` — new assertions for every
  new element/function.
- `docs/MILESTONES.md` — new "ATHENA UX Overhaul" tracked section (UX-1
  through UX-9); this log.

### Public APIs

- None — pure frontend restructuring, no backend/API surface touched.

### Validation and architecture

- Full regression: **1016 passed** (unchanged — no backend files touched).
- No Ruff/mypy scope (no `.py` files changed).
- JS brace/paren balance checked against the pre-edit baseline (added code
  perfectly balanced; the single pre-existing off-by-one paren count
  unchanged). Live server restart + isolated-browser console-error check:
  zero errors on load.
- ADR-005 preserved: Executive Summary lines are either exact counts or
  engine-authored explanation strings, never generated. No ADR required —
  no domain object, contract, or backend behavior changed.

### Risks and technical debt

- I could not exercise the redesigned cockpit end-to-end myself (no owner
  credentials) — needs an owner click-through.
- Holding-period and strategy-name gaps are now documented (not silently
  missing) — worth a decision on whether to scope small backend additions
  for them in a future UX milestone.
- No new technical debt beyond the above.

### Remaining work

- **Owner smoke test**: select a TRADE, WATCH, and NO_TRADE decision each;
  confirm the band words (score/confidence quality word, risk hazard word)
  look sensible against the raw numbers; confirm the Decision Banner's
  color/border matches the stance; confirm the Executive Summary's 5 lines
  read naturally and match what's shown elsewhere on the same brief;
  confirm Expected R:R shows `—` for a non-TRADE decision with no trade plan.
- Next in the UX Overhaul program: **UX-2** (score/confidence/risk
  storytelling — star-rated contributors, "why ATHENA trusts this"
  checklist, risk category summary, safety-gate checklist, "Why?" button).

### Commit message

```text
feat(dashboard): add Hero Decision Card, Executive Summary, Decision Banner

- Add qualityBand/riskBand: band composite score, confidence, and risk into words (Weak-Excellent / Low-Medium-High) alongside the existing raw numbers, colored via the existing gauge tone logic
- Add a 4th cockpit gauge for Expected R:R, read directly from trade_plan.risk_reward
- Replace the plain thesis paragraph with a colored Decision Banner (reusing the existing stance palette) and a 5-line Executive Summary composed entirely from already-persisted engine explanations, never generated
- Research-confirm holding-period and strategy-name (from the owner's UX audit example) don't exist prospectively anywhere in the backend; omit rather than fabricate, flagged for a future milestone
```

---

## Decisions & Trace UI overhaul (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Owner-reported: the Decisions & Trace tab was overcrowded (13 sections stacked in one scroll), had redundant gate chips (list card vs. brief), and a Reasoning Trace DAG that duplicated the brief's own analysis in a side panel. Also fixed: logging out left the browser URL on the previous tab, so the next login reopened it instead of defaulting to Portfolio Overview. |
| Scope | Full frontend redesign: outcome-grouped horizontal carousels for Today's Decisions, a sticky cockpit header with live score/confidence/risk gauges, a four-tab Decision Brief (Setup/Analysis/Context/Response), and a Reasoning Trace that navigates to the matching tab instead of duplicating it. Plus the logout navigation fix. No backend/API changes. |
| Tests | Full suite **1016 passed** (2 stale dashboard-hosting assertions updated to match the new static markup, plus new assertions for every redesigned element); no backend files touched, so no Ruff/mypy scope. No JS test runner in this repo — verified via full-suite substring assertions, a JS brace/paren balance check against the pre-edit baseline, and a live browser console-error check (zero errors on load) |
| Coverage | Frontend-only change; no Python coverage impact |
| Status | **READY FOR REVIEW** — first-pass redesign smoke-tested live by owner (2026-07-26), four issues found and fixed in a follow-up pass (below); needs a second owner click-through |
| Branch | feature/live-dashboard |

### Fix pass (2026-07-26, owner screenshots)

Owner smoke-tested the first pass live and reported four issues, all fixed:

- **Empty state didn't actually hide** — filtering to zero matching
  decisions left the cockpit gauges (`0.0`/`0.0`/`0.0`), all four tabs, and
  the action buttons visibly rendered and interactive, with the title
  ellipsis-truncated to "Instrument Decisio…". Root cause: the browser's
  built-in `[hidden] { display: none }` default is author-overridable, and
  `.decision-brief-gauges`/`.decision-brief-tabstrip`/`.decision-brief-actionbar`
  each had their own unconditional `display: grid`/`flex` rule, which wins
  the cascade over the UA default even with the `hidden` attribute present.
  Fixed with explicit `[hidden] { display: none; }` overrides for all
  three, a short "Select a symbol" placeholder that fits without
  truncating, and `resetCockpitGauges()` now also runs in the empty state
  for defense-in-depth.
- **Carousel nav arrows/fade showed even with nothing to scroll** — Trade's
  single-card row still showed both chevrons and a hard-clipped right edge.
  Added `wireCarouselOverflow()`: measures actual overflow per row via
  `ResizeObserver` + a scroll listener, toggling `.scrollable`/`.at-start`/
  `.at-end` classes so each arrow only appears when there's somewhere to
  scroll *in that direction*, and a `mask-image` edge fade (instead of the
  earlier gradient-on-button approach, which read as a hard clip) shows
  only on the side that actually has more content.
- **Repetitive, undifferentiated gate notes** — many Watch/No-trade cards
  showed the identical muted-gray "N of M gates open" with no at-a-glance
  severity cue (only a hover tooltip). Added a `tone-good-text`/
  `tone-warn-text`/`tone-bad-text` color cue (0 / 1-2 / 3+ failed gates)
  reusing the existing tone-text convention, so severity reads at a glance
  across a row of cards without hovering each one.
- **Possible stray character before a card's score digits** — traced the
  render path (`decisionScoreValue` → `extractScoreFromText` →
  `renderDeckCard`); no currency symbol or prefix is ever added to the raw
  `.toFixed(1)` score string, so this is almost certainly a screenshot
  compression artifact on a thin-serif numeral, not a real bug — flagged to
  the owner to double-check live rather than "fixed" speculatively.

### Scope completed

- **Logout navigation fix**: `logoutBtn`'s click handler never reset the
  browser URL, so it stayed at e.g. `/dashboard/decisions`; the next login's
  `initializeRoute()` read that stale path and reopened the same tab instead
  of defaulting to Portfolio Overview. Fixed with one
  `window.history.replaceState({tabId: "overview"}, "", "/dashboard/overview")`
  call before the reload/unlock-gate branch.
- **Outcome-grouped carousels** (`renderDecisionCarousels`, `renderDeckCard`,
  `DECISION_CAROUSEL_SECTIONS`): Today's Decisions is grouped into
  Trade → Watch → No trade → Insufficient data (any other `decision_type`
  gets its own carousel too, so nothing is ever silently hidden), always in
  that priority order regardless of timestamp (owner-confirmed). Each
  section is an independently scrollable horizontal row with prev/next
  buttons, expanded by default (owner-confirmed), collapsible via its
  header. Cards are compact (symbol, score, time, a single "N of M gates
  open" note whose tooltip lists the specific failing gates — the full
  breakdown lives in the Analysis tab, so nothing shown before is now
  unreachable). `decisionTypePriority()` drives both the display order and
  the default-selected decision on load/filter-change, replacing the old
  "newest first" fallback.
- **Sticky cockpit header**: symbol, stance chip, decision-type chip,
  as-of time, and Re-validate button, plus three live gauges (composite
  score / confidence / risk) that read the exact same
  `analysisPresentation()`-derived value/level already computed for the
  Analysis tab's summary cards (`renderCockpitGauges`) — never a second,
  independently-derived number. Always visible regardless of scroll
  position or active tab.
- **Four-tab Decision Brief** (`switchBriefTab`, `activeBriefTab`) replaces
  the old 13-section stacked scroll: **Setup** (eligibility, TradePlan,
  intraday chart), **Analysis** (score/confidence/risk depth, "why not a
  trade", safety & quality gates), **Context** (decision timeline, session/
  market context, analytical provenance), **Response** (your response/
  outcome, similar past setups). Every one of the original sections is
  preserved — none dropped, only regrouped — and every existing loader
  (`loadDecisionDepth`, `loadDecisionContext`, `loadDecisionChart`,
  `loadJournalPanel`, `loadDecisionAnalogs`, `loadDecisionCounterfactual`,
  `loadDecisionPlanFreshness`) is unchanged, since each still targets the
  same element ids, now nested inside a tab pane instead of a flat section.
  `activeBriefTab` deliberately persists across decision switches — flipping
  through several decisions to compare the same aspect keeps you on that
  aspect instead of resetting to Setup each time (graceful selection).
- **Action bar and tab strip are static, wired once**: the header
  previously rebuilt and rebound its action buttons on every
  `renderDecisionBrief` call; since it's now a fixed part of the sticky
  header (not rebuilt per decision), the buttons are wired exactly once at
  load and read `activeDecisionData`/`activeDecisionId` at click time — this
  needed a new `resetActionButtons()` so a "Removed" state from a previous
  symbol can't leak onto the next one.
- **Reasoning Trace navigates instead of duplicating**: clicking a DAG node
  now looks up its tab via a new `STAGE_TAB_MAP` and calls `switchBriefTab`,
  so the brief opens exactly where that value lives. The side panel
  (`showStageDetails`) now shows only what isn't duplicated elsewhere — the
  stage's status and provenance references — instead of re-rendering the
  same score/confidence/risk/regime/trade-plan content a second time.
  Removed the now-dead `renderStageDetailBody`, `renderContextStageBody`,
  `renderTradePlanStageBody`, and `refreshSelectedStageDetail` (their output
  is fully covered by the brief tabs, which have no async-refresh problem
  since they're rebuilt fresh on every `renderDecisionBrief`).
- **Text truncation handled throughout**: long symbols/labels get
  `text-overflow: ellipsis` plus a `title` tooltip with the full value
  (deck card symbol, cockpit symbol, gauge labels, carousel hint text,
  decision-note tooltips, DAG node names) — nothing silently clips without
  a way to read the full value.

### Files created

- None (all additive/restructuring within existing files).

### Files modified

- `src/athena/api/static/index.html` — replaced the 3-column
  `.trace-workstation` with a toolbar card, outcome-carousel container, and
  a 2-column workstation (Decision Brief | Reasoning Trace); new static
  cockpit header (identity, gauges, tab strip, action bar); cache-bust
  bumped to `9.30.0`.
- `src/athena/api/static/dashboard.js` — see Scope completed above for the
  full list of new/changed functions; `logoutBtn` click handler.
- `src/athena/api/static/dashboard.css` — new carousel/cockpit/tab-strip/
  gauge styles; removed dead `.briefing-*` and DAG-panel-duplication rules.
- `tests/api/platform/test_dashboard_hosting.py` — replaced stale
  DAG-duplication assertions with new ones for the redesigned elements;
  fixed two assertions that checked `js` for id attributes now emitted only
  in static `html`.
- This log.

### Public APIs

- None — pure frontend restructuring, no backend/API surface touched.

### Validation and architecture

- Full regression: **1016 passed** (unchanged count — no backend files
  touched, no new backend tests needed).
- No Ruff/mypy scope (no `.py` files changed).
- JS has no linter/test runner in this repo; verified via (1) full-suite
  substring assertions against the new markup/functions, (2) a brace/paren
  balance check of the whole file against the pre-edit baseline (added code
  is perfectly balanced; the single pre-existing off-by-one paren count is
  unchanged, confirmed not something this change introduced), (3) a live
  server restart + isolated-browser console-error check (zero errors on
  load, both `dashboard.css`/`dashboard.js` served 200).
- No order-placement path touched. ADR-005 preserved: gauges/tabs render
  already-computed values, nothing generated. No ADR required — no domain
  object, contract, or backend behavior changed.

### Risks and technical debt

- I could not exercise the redesigned Decisions & Trace tab end-to-end
  myself (no owner credentials) — the live console-error check only covers
  the pre-login page. **This milestone needs an owner click-through in the
  real dashboard before being marked approved.**
- No new technical debt beyond the above; dead code from the old DAG-panel
  duplication was removed rather than left in place.

### Remaining work

- **Owner smoke test round 2** (see chat for step-by-step): re-check the
  empty state (filter to zero matches) now cleanly shows just "Select a
  symbol" with no gauges/tabs/actions visible; confirm the Trade row (or
  any single-card row) shows no nav arrows and no clipped edge; confirm
  Watch/No-trade cards now show a color-coded gate note; confirm the
  ADANIENSOL-like score glyph looks correct live. Beyond the fix pass: the
  original round-1 smoke test items (carousel order, gauges, all four tabs,
  DAG node jumps, logout landing on Portfolio Overview) plus the owner's
  own list of further refinements are still pending.

### Commit message

```text
refactor(dashboard): overhaul Decisions & Trace UI; fix logout tab reset

- Replace the flat, chronological Today's Decisions list with outcome-grouped horizontal carousels (Trade/Watch/No trade/Insufficient data), always in that priority order regardless of timestamp
- Add a sticky cockpit header with live score/confidence/risk gauges, replacing the 13-section stacked scroll with a four-tab brief (Setup/Analysis/Context/Response) — every original section preserved, just regrouped
- Make Reasoning Trace nodes navigate to the matching brief tab instead of duplicating its content in a side panel; remove the now-dead duplicate renderers
- Fix logout leaving the browser URL on the previous tab, which made the next login reopen it instead of defaulting to Portfolio Overview
- Fix empty-state gauges/tabstrip/actionbar not actually hiding ([hidden] was overridden by an unconditional display rule); hide carousel nav arrows/fade when a row doesn't overflow; add a quick-glance severity color to repetitive gate notes
```

---

## M-X3 — Confidence-decay clock (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Replace the dashboard's ad-hoc client-side Active/Expired TradePlan badge (computed from an un-quantified `new Date()` comparison) with a real, quantified, backend-computed decay percentage and band (FRESH/AGING/STALE/EXPIRED) over the plan's validity window |
| Scope | New read-only `/plan-freshness` endpoint + a decay badge next to the existing TradePlan validity row |
| Tests | Full suite **1016 passed** (+3 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25) |
| Branch | feature/live-dashboard |

### Scope completed

- Added `DecisionsService.get_trade_plan_freshness(decision_id, as_of=None)`:
  pure arithmetic over the decision's already-persisted
  `TradePlan.valid_from`/`valid_until` and an `as_of` instant (defaults to
  wall-clock `datetime.now(tz=timezone.utc)` at the API boundary — the same
  "genuine wall-clock read for a real-time question, not an analytical
  computation" precedent already used by `record_trade_outcome`'s
  `closed_ts`). No domain object, engine, or persisted report touched.
- Added two new config thresholds to `config/decision.json`'s `plan` block:
  `freshness_warn_fraction` (0.5) and `freshness_stale_fraction` (0.8) —
  the elapsed-fraction bands that separate FRESH → AGING → STALE, with
  `EXPIRED` once `as_of >= valid_until`. Validated ordered (`warn <
  stale`) via a `model_validator`, matching the existing
  `DecisionThresholdsCfg._ordered` pattern.
- Added `TradePlanFreshnessDTO` (frozen, `Decimal` decay_fraction) and
  `GET /api/v1/decisions/{id}/plan-freshness?as_of=<optional ISO8601>` —
  the optional query param lets a caller ask "what would freshness look
  like at time X", defaulting to right now.
- Added a small `plan-freshness-badge` next to the pre-existing
  `.plan-status` (Active/Expired/Pending) badge in the TradePlan card,
  filled in asynchronously once the endpoint resolves (e.g. "62% decayed"),
  color-banded FRESH→green, AGING→blue, STALE→amber, EXPIRED→red. The
  pre-existing client-side Active/Expired/Pending badge is left untouched —
  this milestone adds the quantified decay signal alongside it rather than
  replacing already-working, already-tested behavior. Cache-busted
  dashboard assets to `9.29.0`.
- No architecture change: pure read-only arithmetic over already-persisted
  `TradePlan` fields and new (additive) config thresholds — no domain
  object, contract, or frozen model touched; no new Protocol method needed.

### Files created

- None (all additive to existing files).

### Files modified

- `config/decision.json`, `src/athena/config/models.py`
  (`DecisionPlanCfg.freshness_warn_fraction`/`freshness_stale_fraction` +
  ordering validator)
- `src/athena/api/v1/dtos/{decisions,__init__}.py` (`TradePlanFreshnessDTO`)
- `src/athena/api/v1/services/decisions_service.py`
  (`get_trade_plan_freshness`, `_freshness_summary` helper)
- `src/athena/api/v1/routers/decisions.py` (`GET .../plan-freshness`)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`;
  this log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/plan-freshness`.
- Added two new required config fields to `config/decision.json`'s `plan`
  block (backward-incompatible for hand-edited config files missing them —
  acceptable since `config/decision.json` is the single owner-controlled
  instance, already updated in this change set).
- No frozen domain object, calculation, risk policy, or order boundary
  changed.

### Validation and architecture

- Full regression: **1016 passed** (was 1013; +3 net new — no-trade-plan,
  four-band decay-via-as_of, and not-found tests).
- Ruff clean on every touched file (one pre-existing, unrelated F811 —
  duplicate `SizingConfig` class in `config/models.py` — spotted while
  running the check; flagged separately as out-of-scope cleanup, not
  touched here).
- mypy clean on all touched modules.
- ADR-005 preserved: the decay badge and summary are arithmetic/template
  composition over persisted values and config, never generated text.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required — additive config fields + a
  read-only endpoint over existing persisted fields.

### Risks and technical debt

- The endpoint reads live `config/decision.json` thresholds at request
  time, same intentional trade-off as M-X2's counterfactual: answers "what
  would it take right now," not "what it looked like at scoring time."
- The pre-existing client-side Active/Expired/Pending badge and the new
  backend-computed decay badge are two independent, not-necessarily-in-sync
  signals (one reads the browser's clock, one reads the server's). Both are
  derived from the same `valid_from`/`valid_until`, so they should agree in
  practice, but a large client/server clock skew could show a mismatch.
  Acceptable for v1; worth consolidating onto the backend signal only in a
  future pass if it ever causes confusion.
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: open a decision with a trade plan, confirm the new decay
  badge shows a sensible percentage next to the existing status badge, and
  that it transitions through FRESH → AGING → STALE color bands as time
  passes (or via a shortened `validity_hours` in config for faster manual
  testing).
- Next in the Intraday Edge Program: **M-X8** (synthetic canary decision),
  **M-X9** (config-change impact preview), or **M-X10** (outcome-tagged
  setups) are all clean, no-gate candidates. **ADR-006** (circuit-limit
  risk signal) still awaits owner sign-off before M-X4 can start.

### Commit message

```text
feat(api): add deterministic TradePlan decay clock (M-X3)

- Add get_trade_plan_freshness: quantifies elapsed/remaining/decay_fraction over the plan's persisted valid_from/valid_until window against an as_of instant (defaults to wall-clock now)
- Add freshness_warn_fraction/freshness_stale_fraction config thresholds to config/decision.json, ordered-validated like existing DecisionThresholdsCfg
- Add GET /api/v1/decisions/{id}/plan-freshness and a decay-percentage badge next to the existing TradePlan status badge, replacing nothing — purely additive alongside the already-working client-side Active/Expired indicator
```

---

## M-X2 — "Why not" counterfactual (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | For every non-TRADE decision, quantify the exact score/confidence/risk/evidence/market gap to the TRADE gate — pure arithmetic over already-persisted values and current config thresholds, never a recomputed decision |
| Scope | New read-only `/counterfactual` endpoint + Decision Brief "Why not a trade?" section |
| Tests | Full suite **1013 passed** (+3 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25) |
| Branch | feature/live-dashboard |

### Scope completed

- Added `DecisionsService.get_decision_counterfactual(decision_id)`: for a
  TRADE decision, returns a trivial "already cleared" result. For any other
  decision type, reads the decision's own persisted `gate_results` (never
  recomputed) plus its persisted score/confidence/risk report (via the
  existing `_fetch_report` helper) and the live `config/decision.json`
  thresholds, then computes, per failing gate, `current`, `required`, and
  `gap = max(0, required - current)` (or `current - required` for RISK,
  since risk is a ceiling not a floor). Composite score gap is computed the
  same way against `min_composite_for_trade`.
- Handles the two non-numeric blockers that are not expressed as a
  `QualityGate` at all — `Direction.NONE` (no trend direction) and a missing
  `trade_plan` (ATR/SMA indicators unavailable) — by checking the decision's
  own persisted `direction`/`trade_plan` fields directly, only when no
  numeric gate/score gap remains, so a decision is never told to "close a
  gap" that isn't actually the reason it wasn't a TRADE.
- Added `CounterfactualGapDTO`/`DecisionCounterfactualDTO` (frozen, `Decimal`
  fields) and a deterministic `summary` string (e.g. `"To become a TRADE:
  score +4.20, confidence +10.00."`) built from simple template composition
  over the computed gaps — no generated rationale, per ADR-005.
- Added `GET /api/v1/decisions/{id}/counterfactual`.
- Added a "Why not a trade?" Decision Brief section (after "Score ·
  confidence · risk", before "Safety & quality gates"): an "all gates
  cleared" chip for TRADE decisions, or a row per gap (current vs. required,
  with a gap chip) plus the summary sentence for everything else. Cache-
  busted dashboard assets to `9.28.0`.
- No architecture change: pure read-only arithmetic over already-persisted
  data and existing config thresholds — no domain object, contract, or
  frozen model touched; no new Protocol method needed (reuses
  `get_decision`/`_fetch_report`).

### Files created

- None (all additive to existing files).

### Files modified

- `src/athena/api/v1/dtos/{decisions,__init__}.py` (`CounterfactualGapDTO`,
  `DecisionCounterfactualDTO`)
- `src/athena/api/v1/services/decisions_service.py`
  (`get_decision_counterfactual`, `_decimal_or_none`, `_market_quality_value`,
  `_counterfactual_summary` helpers)
- `src/athena/api/v1/routers/decisions.py` (`GET .../counterfactual`)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`;
  this log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/counterfactual`.
- No frozen domain object, calculation, risk policy, or order boundary
  changed.

### Validation and architecture

- Full regression: **1013 passed** (was 1010; +3 net new — already-TRADE,
  confidence/risk gap quantification, and non-numeric direction-blocker
  tests).
- Ruff clean on every touched file. mypy clean on all touched modules.
- ADR-005 preserved: summary is template composition over persisted/
  computed numbers, never generated text.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required — read-only arithmetic over
  existing persisted fields and existing config thresholds.

### Risks and technical debt

- Thresholds are read live from `config/decision.json` at request time; if
  the owner changes a threshold between when a decision was scored and when
  its counterfactual is viewed, the gap reflects the *current* threshold,
  not the one in force at scoring time. This is intentional (answers "what
  would it take right now"), but worth stating explicitly since it's the one
  place this milestone reads live config rather than only persisted data.
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: open a WATCH/NO_TRADE decision, confirm the gap numbers and
  summary sentence match the persisted score/confidence/risk shown
  elsewhere on the same Decision Brief; open a TRADE decision, confirm the
  "all gates cleared" state.
- Next in the Intraday Edge Program: **M-X3 confidence-decay clock** (clean,
  no gate) is the natural follow-on. **ADR-006** (circuit-limit risk signal)
  still awaits owner sign-off.

### Commit message

```text
feat(api): add "why not a trade" counterfactual gap for decisions

- Add get_decision_counterfactual: quantifies exact score/confidence/risk/evidence/market gap to the TRADE gate from already-persisted gate_results and report values, plus live config thresholds
- Handle non-numeric blockers (no direction, no trade plan) only when no numeric gate/score gap remains, so a decision is never told to close a gap that isn't the real reason
- Add GET /api/v1/decisions/{id}/counterfactual and a "Why not a trade?" Decision Brief section with per-gate gap rows and a deterministic summary sentence
```

---

## M-X1 — Historical analog matcher (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Deterministic nearest-neighbor retrieval of past decisions with a similar score/confidence/risk fingerprint, each with its logged human response and realized outcome (now real, thanks to M-X0) |
| Scope | New read-only `/analogs` endpoint + Decision Brief "Similar past setups" section |
| Tests | Full suite **1010 passed** (+2 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25) |
| Branch | feature/live-dashboard |

### Scope completed

- Added `DecisionProvider.list_recent_decisions(limit)` — a raw, unfiltered
  read (newest first) for analytical queries that need a candidate pool
  rather than a paginated/filtered API listing. Implemented in both
  `SqliteDecisionProvider` (delegates to `repo.list_decisions`) and
  `InMemoryDecisionProvider`.
- Added `DecisionsService.get_decision_analogs(decision_id, limit=5)`:
  extracts the target decision's (score composite, confidence overall, risk
  overall) fingerprint from its persisted report — refactored the existing
  report-lookup logic out of `get_decision_depth`/`get_decision_context`
  into a shared `_fetch_report` helper rather than duplicating it a third
  time — then computes Euclidean distance against every other persisted
  decision with a comparable (status `OK`) fingerprint, grouping by
  `run_id` to fetch each run's detail once rather than once per decision.
  Decisions with an `UNKNOWN` score/confidence/risk (including the target
  itself, if unassessed) are excluded from comparison entirely — never
  compared against a fabricated or defaulted value.
- Each returned match carries its logged `DecisionJournalEntry.user_action`
  and `TradeOutcome.pnl`/`closed_ts` if present (via M-X0's `get_journal_entry`/
  `get_trade_outcome`) — `null` when never recorded, never inferred.
- Added `GET /api/v1/decisions/{id}/analogs?limit=1..20`.
- Added a "Similar past setups" Decision Brief section: each match shows
  symbol, stance chip, an intuitive similarity % (derived client-side from
  distance for display only — never persisted or compared), a response
  chip, and a pnl chip (color-coded) or "no outcome logged". Rows are
  clickable and jump to that decision, matching the existing Decision
  Timeline row pattern. Cache-busted dashboard assets to `9.27.0`.
- No architecture change: pure read-only composition over already-persisted
  data (Decision, DecisionReport.machine, DecisionJournalEntry, TradeOutcome)
  via one small additive Protocol method — no domain object, contract, or
  frozen model touched.

### Files created

- None (all additive to existing files).

### Files modified

- `src/athena/api/v1/providers/{base,sqlite_providers,in_memory}.py`
  (`list_recent_decisions`)
- `src/athena/api/v1/dtos/{decisions,__init__}.py` (`DecisionAnalogDTO`,
  `DecisionAnalogsDTO`)
- `src/athena/api/v1/services/decisions_service.py` (`get_decision_analogs`,
  shared `_fetch_report`/`_fingerprint` helpers, refactored
  `get_decision_depth`/`get_decision_context` to reuse `_fetch_report`)
- `src/athena/api/v1/routers/decisions.py` (`GET .../analogs`)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`;
  this log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/analogs`.
- No frozen domain object, calculation, risk policy, or order boundary
  changed.

### Validation and architecture

- Full regression: **1010 passed** (was 1008; +2 net new — ranking/exclusion
  test and an unknown-fingerprint-target test).
- Ruff clean on every touched file (one import-sort auto-fix applied,
  verified no behavior change via full suite re-run).
- mypy clean on all touched modules.
- ADR-005 preserved: analog matches are factual retrieval from persisted
  data, no generated text, no recomputed comparison.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required — additive Protocol method only.

### Risks and technical debt

- Candidate pool is capped at the 500 most recent decisions (matching the
  existing `SqliteDecisionProvider` windowing convention) — a very long
  history could miss older analogs. Acceptable for v1; revisit if the
  journal grows large enough for this to matter in practice.
- Similarity % is a display-only derived value (linear map from Euclidean
  distance over a fixed 0–173.2 range) — not a statistically calibrated
  confidence measure. Documented as such in the UI copy ("factual retrieval
  only, nothing generated").
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: select a decision with several historical siblings, confirm
  the ranking looks sensible, confirm decisions without a persisted
  fingerprint (or with UNKNOWN score/confidence/risk) are excluded, confirm
  clicking a row navigates to that decision's brief.
- Next in the Intraday Edge Program: **M-X2 "Why not" counterfactual** or
  **M-X3 confidence-decay clock** (both clean, no gate). **ADR-006**
  (circuit-limit risk signal) still awaits owner sign-off.

### Commit message

```text
feat(api): add historical analog matcher for decisions

- Add DecisionProvider.list_recent_decisions for raw candidate-pool reads, implemented in both Sqlite and InMemory providers
- Add get_decision_analogs: deterministic nearest-neighbor retrieval by score/confidence/risk fingerprint, excluding any decision without a comparable persisted assessment
- Refactor report-lookup logic shared across depth/context/analogs into one _fetch_report helper instead of duplicating it a third time
- Add GET /api/v1/decisions/{id}/analogs and a "Similar past setups" Decision Brief section showing each match's logged response and realized outcome
```

---

## M-X0 — Decision Journal & Outcome capture (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Close a foundational gap discovered while designing the Intraday Edge Program: `DecisionJournalEntry` and `TradeOutcome` are fully modeled, persisted, and already consumed by M10.4 AI Playbook Diagnostics — but nothing in the codebase ever called `save_journal_entry`. The feedback loop has been silently empty since M10.4 shipped. |
| Scope | Owner accept/reject/ignore response + realized-outcome logging, server-computed pnl/holding-time/TradePlan-adherence, new Decision Brief section |
| Tests | Full suite **1008 passed** (+19 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner smoke confirmed 2026-07-25 — response recording, persistence across reload, outcome pnl/adherence computation all verified) |
| Branch | feature/live-dashboard |

### Scope completed

- Discovered via `git grep`-level tracing (no code written yet) that
  `save_journal_entry` — the repository method that persists the owner's
  response to a decision — is called nowhere in `src/`. `TradeOutcome` had
  no persistence path at all (no repository methods, no table). M10.4's
  `PlaybookDiagnosticsAnalyzer.analyze(journal=...)` has therefore always
  received an empty sequence in production. This is the first milestone of
  the AI-proposed "Intraday Edge Program" (`docs/MILESTONES.md`), reordered
  ahead of the originally-planned Historical Analog Matcher (M-X1) once
  discovered, since analog matching over always-empty outcomes would have
  been hollow.
- Added `trade_outcomes` SQLite table (schema v6→v7) and repository methods
  `save_trade_outcome`/`get_trade_outcome`/`list_trade_outcomes`, plus
  `get_journal_entry` (single-decision lookup; only `list_journal` existed).
  Additive only — no existing table/method changed.
- Extended `DecisionProvider` Protocol (P8.3 API-layer abstraction, not an
  ATHENA-002 §7 analytical contract) with
  `save_journal_entry`/`get_journal_entry`/`save_trade_outcome`/
  `get_trade_outcome`; implemented in both `SqliteDecisionProvider` and
  `InMemoryDecisionProvider`.
- Added `POST/GET /api/v1/decisions/{id}/journal` and
  `POST/GET /api/v1/decisions/{id}/outcome`. PnL (`entry`/`exit` vs.
  `Decision.direction`), holding time (`closed_ts - decision.ts`), and
  TradePlan adherence (`entered_within_zone`, `hit_stop`, `hit_target`) are
  computed server-side from the persisted `TradePlan` — never client-
  supplied, so every outcome is deterministic and explainable (ADR-005).
  Write endpoints require `Permission.EXECUTE`; reads require `READ`.
- Added a "Your response" section to the Decision Brief: Accept/Reject/
  Ignore buttons with optional notes, and — once accepted — an outcome-
  logging form (entry/exit/quantity only; everything else computed) that
  becomes a read-only result card (PnL, adherence chips, holding time) once
  logged. Cache-busted dashboard assets to `9.26.0`.
- No architecture change: `DecisionJournalEntry`/`TradeOutcome` were already
  frozen domain objects; `journal` is already a named contract row in
  ATHENA-002 §7's module table (consumes `decisions`, produces "persisted
  journal rows") — this milestone completes what the blueprint already
  specified, per the R6 anti-scope-creep guardrail checked before starting.

### Files created

- None (all additive to existing files).

### Files modified

- `src/athena/data/store/{schema,serialization,repository}.py` (trade_outcomes
  table + methods, `get_journal_entry`)
- `src/athena/api/v1/providers/{base,sqlite_providers,in_memory}.py` (Protocol
  extension + two implementations)
- `src/athena/api/v1/dtos/{decisions,__init__}.py` (4 new DTOs)
- `src/athena/api/v1/services/decisions_service.py` (record/get journal +
  outcome, server-side pnl/adherence computation)
- `src/athena/api/v1/routers/decisions.py` (4 new endpoints)
- dashboard CSS/JS/HTML; `tests/api/v1/test_core_apis.py`,
  `tests/data_layer/test_decision_journal.py`,
  `tests/runtime/test_dry_run_schedule.py` (schema-version bump fix),
  `tests/api/platform/test_dashboard_hosting.py`; `docs/MILESTONES.md`; this log.

### Public APIs

- Added `POST/GET /api/v1/decisions/{decision_id}/journal`,
  `POST/GET /api/v1/decisions/{decision_id}/outcome`.
- No frozen domain object, calculation, risk policy, or order boundary
  changed — `DecisionJournalEntry`/`TradeOutcome` were already defined;
  this milestone only adds their persistence and a real entry point.

### Validation and architecture

- Full regression: **1008 passed** (was 1004; +19 net new: 2 API tests +
  4 repository round-trip tests + updated 2 stale schema-version assertions
  + assorted dashboard-hosting assertions).
- Ruff clean on every touched file; 3 pre-existing `SIM117` findings in
  `repository.py` (nested `with` in unrelated pre-existing methods) left
  untouched per scope discipline.
- mypy clean on all touched modules.
- ADR-005 preserved: pnl/holding-time/adherence are computed once, server-
  side, from persisted data — never entered by the owner, never
  recalculated by the UI.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR required (confirmed against ATHENA-002
  §19/§7 before starting — see Scope completed).

### Risks and technical debt

- Outcome logging currently supports one outcome per decision (upsert by
  `decision_ref:closed_ts`); partial exits across multiple fills are not
  modeled. Acceptable for v1 — no existing UI/data assumed multiple
  outcomes either.
- `adherence` is a fixed 2-key computed dict (`entered_within_zone`,
  `hit_stop`, `hit_target`) when a TradePlan exists, empty otherwise (e.g.
  outcome logged against a non-TRADE decision). Documented, not silently
  defaulted.
- No new technical debt beyond the above.

### Remaining work

- Owner smoke: unlock the live workstation, select an ACCEPTED-worthy
  decision, record Accept/Reject/Ignore, confirm it persists across a
  reload, log a realized outcome and confirm pnl/adherence compute
  correctly, confirm a REJECTED/IGNORED decision does not show the outcome
  form.
- Next in the Intraday Edge Program: **M-X1 Historical analog matcher**,
  now genuinely valuable once real journal/outcome data accumulates.
  **ADR-006** (circuit-limit risk signal) still awaits owner sign-off.

### Commit message

```text
feat(data): wire Decision Journal and Trade Outcome to a real owner action

- Add trade_outcomes table (schema v7) and repository persistence — TradeOutcome existed in the frozen domain model with zero persistence path until now
- Extend DecisionProvider with journal/outcome save+get, implemented in both Sqlite and InMemory providers
- Add POST/GET journal and outcome endpoints; pnl, holding time, and TradePlan adherence are computed server-side, never client-supplied (ADR-005)
- Add a "Your response" Decision Brief section: accept/reject/ignore + outcome logging, closing the gap where M10.4 AI Playbook Diagnostics ran against an always-empty journal since it shipped
```

---

## M-D4 — Context lane (APPROVED)

| | |
|---|---|
| Completed | 2026-07-25 |
| Objective | Ground each selected decision in session/calendar awareness, persisted regime/market-health context, and owner-curated external research links; add a deterministic Decision Brief export |
| Scope | Session/calendar context, persisted regime/market-health surfacing, deterministic brief export, approved external links |
| Tests | Full suite **1004 passed** (+15 new); changed-file Ruff clean; mypy clean on touched modules |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner approved 2026-07-25, after live smoke-test review and fixes) |
| Branch | feature/live-dashboard |

### Scope completed

- Extended `ScanCapture` and `DecisionReportingEngine.report()` with optional
  `regime`/`market_health` fields, persisting them into `DecisionReport.machine`
  the same additive way M-D3 persisted score/confidence/risk — no frozen
  domain object changed, no new architecture. Wired both call sites
  (`scanner.py`, `owner_validation.py`) so future scans/re-validates persist
  real regime/market-health context instead of leaving it unrecorded.
- Added a new owner-maintained `config/external_links.json` (+ pydantic model
  + loader), mirroring the existing `calendar/events.json` convention:
  static, provenance-tagged link metadata only (title/url/source/added_by/
  date_added), keyed by instrument id or `GLOBAL`. No fetching, no scraping,
  no news ingestion.
- Added authenticated, read-only `GET /api/v1/decisions/{decision_id}/context`
  combining a live-computed `CalendarContext` (session type, hours, holiday,
  weekly/monthly expiry, scheduled events) with the persisted regime/
  market-health snapshot and matching external links (GLOBAL, exact
  instrument id, or bare-symbol fallback).
- Added a deterministic `DECISION_BRIEF` export artifact type, composing
  already-persisted Decision + Depth + Context DTOs into one JSON/Markdown/
  Text artifact via the existing Export & Presentation pipeline (P6.6/P8.4).
  No new export dependency; no recomputation.
- Added a "Session & market context" section to the Instrument Decision Brief
  dashboard pane: session/expiry/holiday chips, regime labels, market-health
  dimensions, curated external links, and an "Export Brief" action that
  downloads the artifact client-side.
- **Owner smoke UI fixes** (post-review): redesigned the Session & market
  context card with semantic color-coded chips (good/bad/warn/neutral/unknown
  by label meaning), block-card styling, and icons per section; dropped the
  redundant raw prose duplicating the market-health dimension chips. Fixed
  `risk_reward` bypassing `formatDecisionPrice` in the TradePlan card (now a
  proper `formatDecisionRatio` helper, 2dp). Fixed the Decision Trace DAG's
  Trade Plan node showing full, un-rounded `Decimal` tails (e.g.
  `2.0000000000000000001`) in its human-readable trace summary — root cause
  was `DecisionEngine._trace()` interpolating raw `Decimal` values into the
  `trade_plan` stage summary string; fixed by reusing the engine's existing
  `_fmt_score` quantize-to-2dp helper (presentation-only; no `TradePlan`
  value, gate, or contract changed). Also fixed the DAG detail panel
  mislabeling every `ref_ids` reference list as "N rules checked" regardless
  of stage type.
- **Reasoning Trace DAG complete redesign** (post-review, systemic): the same
  overflowing-Decimal complaint applied to every node, not just Trade Plan —
  `scoring/engine.py`, `confidence/engine.py`, and `risk/engine.py` each
  interpolated raw division-derived `Decimal`s (composite/overall scores,
  dimension averages, cross-engine spread, contradiction deltas) straight
  into their `explanation=` strings; `regime/engine.py` and
  `sector_health/engine.py` interpolated raw SMA averages into their trend
  explanations. Added a local 2dp quantize helper to each of the first three
  (mirroring `decision/engine.py`'s existing `_fmt_score`) and inline `:.2f`
  specifiers to the latter two — presentation-only, no stored value, gate,
  or contract changed. Separately, redesigned the DAG node detail cards to
  stop rendering raw trace prose at all for Regime/Market Health/Score/
  Confidence/Risk/Trade Plan: they now reuse the *same* already-fetched,
  already-formatted structured data the Decision Brief panel uses
  (`/depth` and `/context` responses, cached client-side as `activeDepth`/
  `activeContextData`/`activeDecisionData`) — color-coded chips for Regime/
  Market Health, the existing `renderAnalysisSummaryCard` for Score/
  Confidence/Risk, and the existing TradePlan formatters for Trade Plan.
  Handles the load-order race (trace loads independently of depth/context)
  by re-rendering the currently-selected node once the richer data arrives.
  Also fixed the provenance grid's misleading "N rules checked" label
  (applied to every stage regardless of type — those are reference IDs, not
  rules) to "N reference(s)". Evidence/Decision/Sector Health nodes without
  a structured secondary source still show prose, now from the corrected
  backend explanation strings. Cache-busted dashboard assets to `9.24.0`.
- **Re-validate moved to the Decision Brief header** (owner feedback: "no
  idea of where it exists"): added `#decision-brief-revalidate-header`
  next to the "as of" timestamp in the static header (always visible
  regardless of scroll position), removed the old button buried at the
  bottom of the "Human next step" actions row. Wired once at page load
  (not per-render, since the header markup is static) referencing the
  cached `activeDecisionData` at click time so it always targets the
  currently-selected instrument. Enabled/disabled alongside brief load/
  empty state. Added `.btn-sm` and made `.decision-brief-header` an
  explicit flex container (previously relied on `align-items`/
  `justify-content` with no `display: flex` — dead CSS, now fixed).
  Cache-busted dashboard assets to `9.25.0`.
- **Owner smoke fix**: found and fixed a pre-existing latent bug in the P8.4
  Export layer, surfaced for the first time by repeated Decision Brief
  exports in one browser session. `ExportsService` was constructed fresh per
  HTTP request, so its `ExportPresentationEngine`'s id counter reset to zero
  every time — every export got id `exp-0001`, and the in-memory artifact
  store's oldest-first lookup silently kept returning the *first* export
  ever created that session regardless of which decision was actually
  exported. Fixed by injecting one long-lived `ExportPresentationEngine`
  singleton (`dependencies._export_engine`) instead of constructing a new
  one per request; added a regression test exporting two different
  decisions in sequence and asserting distinct ids/payloads.

### Files created

- `config/external_links.json`
- `src/athena/api/v1/services/decision_brief.py`
- `tests/api/v1/test_decision_context_service.py`

### Files modified

- `src/athena/scanner/models.py`, `src/athena/reporting/engine.py`,
  `src/athena/scanner/scanner.py`, `src/athena/ops/owner_validation.py`
  (regime/market-health persistence);
- `src/athena/config/models.py`, `src/athena/config/loader.py` (external
  links config);
- `src/athena/api/v1/dtos/{decisions,base,__init__}.py`,
  `src/athena/api/v1/services/decisions_service.py`,
  `src/athena/api/v1/routers/decisions.py`, `src/athena/api/dependencies.py`
  (context endpoint);
- `src/athena/export/{models,engine}.py`,
  `src/athena/api/v1/services/exports_service.py` (Decision Brief export);
- dashboard CSS/JS/HTML; reporting/config/API/dashboard tests; milestone
  roadmap; this implementation log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/context`. Response contains
  `calendar`, `regime`, `market_health`, and `external_links` blocks; regime/
  market-health render `UNKNOWN` explicitly when not yet persisted for a
  decision (pre-M-D4 decisions, until re-validated).
- Added `SourceArtifactType.DECISION_BRIEF` to the export request contract;
  `POST /api/v1/exports` now accepts it and composes a deterministic brief
  from already-persisted data only.
- No frozen domain object, calculation, risk policy, or order boundary
  changed. `DecisionReportingEngine.report()` and `ScanCapture` gained
  optional, backward-compatible parameters only.

### Validation and architecture

- Full regression: **1003 passed** (was 989 at M-D3; +14 net new tests).
- Ruff clean on every touched file; pre-existing unrelated lint debt in
  `config/models.py`, `export/engine.py`, `reporting/engine.py`, and
  `test_reports_analytics_export.py` (outside this milestone's diff) was left
  untouched per scope discipline.
- mypy clean on all touched modules.
- ADR-004 preserved: no new dashboard dependency/framework.
- ADR-005 preserved: context/regime/market-health render only persisted data;
  the export composes persisted DTOs verbatim, never recomputes.
- CalendarEngine remains the sole trading-day authority (R-3); no new
  calendar logic was added, only surfaced.
- No order-placement path touched. Determinism, replayability, provider
  independence preserved. No ADR or schema migration required.

### Risks and technical debt

- Decisions created before this milestone show `regime`/`market_health` as
  `UNKNOWN` until re-validated — identical, already-accepted precedent from
  M-D3's score/confidence/risk backfill behavior.
- `load_external_links_file` treats a missing `external_links.json` as an
  empty list rather than failing loudly, since the file is new and owner-
  optional; every other config loader in this project fails loudly on a
  missing file. This one deliberate exception should be called out in
  owner review.
- No new technical debt beyond the above.

### Remaining work

- None. Owner smoke completed live (Session & market context, regime/
  market-health persistence via re-validate, `config/external_links.json`
  entry surfacing, Export Brief download, Reasoning Trace DAG node cards,
  header Re-validate placement) — every issue found during smoke testing
  was fixed and re-verified in this milestone (see additional entries
  above). Approved 2026-07-25.
- **Instrument decision brief track closed.** M-D5 (News Evidence) remains
  deferred until DD-5/provider approval; no successor milestone is queued.

### Commit message

```text
feat(dashboard): add M-D4 context lane, regime persistence, and brief export

- Persist regime/market-health into ScanCapture and DecisionReport.machine, mirroring M-D3's score/confidence/risk pattern
- Add owner-curated config/external_links.json with GLOBAL/instrument/bare-symbol matching, no fetching or news ingestion
- Add GET /api/v1/decisions/{id}/context combining live calendar context, persisted regime/market-health, and curated links
- Add deterministic DECISION_BRIEF export artifact composing Decision + Depth + Context DTOs via the existing export pipeline
- Add dashboard Session & market context section and Export Brief download action, cache-busted to 9.22.0
```

---

## M-D3 — ATHENA analytical depth (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Explain eligibility and analytical depth for each selected decision |
| Scope | Eligibility, score/confidence/risk detail, timeline, safe candidate removal |
| Tests | Full suite **989 passed**; focused M-D3 **36 passed**; changed-file Ruff; browser JS compile |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** (owner approved, 2026-07-25) |
| Branch | develop |

### Scope completed

- Persisted each scanner-produced `DecisionReport.machine` in the originating
  run detail, retaining score, confidence, risk, evidence, indicator, and trace
  provenance without adding analytical computation to the API or dashboard.
- Closed the owner-validate analytical gap: confidence, risk, evidence, and
  market-health stages now run before DecisionEngine so re-validate persists
  real depth instead of UNKNOWN confidence/risk refs.
- Extended report serialization with source-created explanations and
  contributions for score, confidence, and risk dimensions per ADR-005.
- Added authenticated, read-only
  `GET /api/v1/decisions/{decision_id}/depth`, backed by the provider protocol
  and deterministic in-memory/SQLite implementations.
- Added typed depth DTOs for the originating universe eligibility assessment
  and persisted score/confidence/risk artifacts; unavailable historical depth
  is reported explicitly as `UNKNOWN`.
- Added Decision Brief sections for universe eligibility/rules, collapsible
  score-confidence-risk components, and the latest eight persisted decisions
  for the selected instrument.
- Redesigned score/confidence/risk as progressive disclosure: recognizable
  summary cards with 0–100 meters, followed by full-width category and component
  drill-downs with aligned values and recorded inputs.
- Added confirmed candidate removal from both Decision Brief and Market
  Intelligence. Removal stops future validation only; decisions, traces, and
  replay evidence remain untouched.
- Retained after-hours Re-validate behavior from M-D2 and cache-busted
  dashboard assets to `9.21.0`.

### Files created

- None.

### Files modified

- Decision report/run-detail persistence; decision DTO/provider/service/router;
  dashboard CSS/JS/HTML; API, reporting, owner-validation, and hosting tests;
  milestone roadmap; this implementation log.

### Public APIs

- Added `GET /api/v1/decisions/{decision_id}/depth`.
- Response contains `eligibility`, `score`, `confidence`, and `risk` blocks
  sourced exclusively from persisted artifacts.
- No frozen domain object, calculation, risk policy, or order boundary changed.

### Validation and architecture

- Full regression: **989 passed**.
- Focused reporting/owner-validation/decision/dashboard/trace tests:
  **36 passed**.
- Changed Python files pass Ruff; the modern browser runtime compiled
  `dashboard.js` (`9.20.0`) successfully.
- ATHENA-002 report boundary preserved: API and dashboard render only.
- ADR-005 preserved: explanations/contributions originate in analytical
  modules and are persisted, never reconstructed by UI.
- Candidate deletion does not cascade to immutable decision/run history.
- Determinism, replayability, provider independence, and no-order boundary
  preserved. No ADR or schema migration required.

### Risks and technical debt

- Decisions created before M-D3 have no persisted report payload and therefore
  show `UNKNOWN` analytical depth until the symbol is re-validated.
- Timeline is bounded to the API's existing 5,000-decision retrieval window and
  displays the latest eight entries per instrument.
- No new technical debt introduced.

### Remaining work

- Owner smoke: unlock after host restart, re-validate one symbol, inspect
  eligibility/components/timeline, and optionally verify confirmed removal.
- M-D4 (Context lane) design started 2026-07-25 against existing calendar,
  export, and regime/market-health contracts.

### Commit message

```text
feat(dashboard): expose persisted decision depth

- Persist score, confidence, risk, and eligibility rationale for faithful rendering
- Add decision depth API, analytical drill-down, and per-symbol decision timeline
- Preserve decision history when removing candidates from future validation
```

---

## M-D2 follow-up — After-hours validate as_of (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Make Validate / Re-validate usable overnight without pretending stale quotes are live |
| Scope | Calendar-aware `as_of` clamp + explicit session-close UI messaging |
| Tests | Targeted resolve/dashboard/candidates **15 passed** |
| Status | **APPROVED** — owner smoke confirmed after-hours session-close validation |
| Branch | develop |

### Scope completed

- Added pure `resolve_validate_as_of`: during known session → live `now`;
  after close / premarket / weekend / holiday / Muhurat-without-timings → last
  completed session close from CalendarEngine (R-3).
- Wired into `POST /api/v1/market/validate` and CLI `validate-symbols` when
  `--as-of` is omitted; explicit CLI `--as-of` remains an override.
- Response now includes `as_of` + `as_of_mode` (`live` | `session_close`).
- Dashboard Validate / Re-validate toasts explain session-close analysis and
  replace raw FRESHNESS ingest-reject text with an actionable message.
- Unattended cycle worker `as_of` is unchanged (separate concern).

### Files created

- `src/athena/calendar/resolve_as_of.py`
- `tests/unit/test_resolve_validate_as_of.py`

### Files modified

- Calendar package export, candidates service/DTO, symbol_validate result,
  CLI validate-symbols, dashboard JS/HTML assets `9.19.3`, hosting regression,
  milestone roadmap, this log.

### Validation

- Targeted: **15 passed**.
- Architecture: CalendarEngine remains sole trading-day authority; no silent
  live pretence after hours; no order-placement path touched.

---

## M-D2 — Intraday chart + TradePlan overlays (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Ground each Decision Brief in persisted intraday price context without prediction |
| Scope | Provider-independent candles API, SVG candlesticks, TradePlan overlays, explicit freshness |
| Tests | Full suite **980 passed**; targeted M-D2 **20 passed**; changed-file Ruff; HTML parse |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED** — owner smoke confirmed charts and session-close validation |
| Branch | develop |

### Scope completed

- Added authenticated read-only
  `GET /api/v1/market/instruments/{instrument_id}/candles` for persisted
  `1m`/`5m`/`15m` OHLCV, chronological ordering, bounded `limit`, and explicit
  `FRESH`/`STALE`/`NO_DATA` status.
- Added `CandleHistoryProvider` with deterministic in-memory and live SQLite
  implementations; the service maps canonical `Candle` objects without
  coupling the API to Kite/FileProvider.
- Freshness uses `validation.json`’s
  `freshness.intraday_max_minutes_behind`; service clock is injectable and the
  threshold boundary is unit-tested.
- Added a dependency-free responsive SVG candlestick chart in the selected
  Instrument Decision Brief using the most recent 120 persisted 5-minute bars.
- Overlaid the persisted TradePlan entry zone, invalidation/stop, and targets;
  no chart-derived or invented price level is created.
- Added explicit stale-data warning (“Re-validate before using the TradePlan”),
  no-data and unavailable states, OHLCV hover tooltips, price/time axes, source,
  latest timestamp, and bar count.
- Added bare-symbol → `NSE:` fallback for older decisions while preserving
  canonical instrument IDs when present.
- Dashboard assets cache-busted to `9.19.0`.

### Files created

- `src/athena/api/v1/services/market_history_service.py`
- `tests/api/v1/test_market_history.py`

### Files modified

- API app/dependencies, market DTO/router, provider protocols and in-memory/
  SQLite providers, dashboard HTML/CSS/JS, API test fixture, hosting regression,
  milestone roadmap, and this implementation log.

### Public APIs

- Added `GET /api/v1/market/instruments/{instrument_id}/candles`.
- Query: `timeframe=1m|5m|15m`, `limit=1..500`.
- Response is read-only and includes candles plus freshness metadata.
- No frozen domain object or analytical contract changed.

### Validation and architecture

- Full regression: **980 passed**.
- Targeted market-history/core/dashboard tests: **20 passed**.
- All changed Python files pass Ruff; dashboard HTML parses successfully.
- Modern browser loaded `9.19.0` assets; authenticated owner chart interaction
  remains the final manual smoke step.
- ADR-004 preserved: no new chart dependency/framework; SVG is static vanilla
  JS over the localhost API.
- ADR-005 preserved: chart renders persisted price/TradePlan data only.
- Determinism, replayability, provider independence, explainability, and
  no-order boundary are preserved. No ADR required.

### Risks and technical debt

- The chart is historical context from the latest persisted ingest, not a
  streaming quote chart; freshness state makes this explicit.
- Bare-symbol fallback assumes NSE for legacy decisions; current canonical IDs
  bypass the fallback.
- Full analytical score/confidence/risk payloads remain M-D3 scope.
- No technical debt introduced.

### Suggested improvements and remaining work

- Owner smoke: select a symbol with ingested 5m candles; verify bars, tooltip,
  freshness badge, and exact TradePlan overlay values.
- M-D3 only after approval: eligibility narrative, symbol decision timeline,
  and resolvable analytical depth.
- News remains deferred to M-D5/DD-5.

### Commit message

`feat(dashboard): add freshness-aware intraday decision chart`

---

## M-D1 — Instrument Decision Brief foundation (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Turn a selected Today’s Decision into a disciplined, explainable stock brief |
| Scope | Full decision detail, TradePlan strip, safety gates, provenance, daily dismiss, re-validate/MI actions |
| Tests | Full suite **976 passed**; targeted dashboard/API **17 passed**; HTML parse; changed-test Ruff |
| Coverage | Existing project coverage retained; no separate percentage collected |
| Status | **APPROVED 2026-07-24** — owner smoke verified |
| Branch | develop |

### Scope completed

- Added a responsive three-pane Decisions workstation: Today’s Decisions,
  selected Instrument Decision Brief, and existing Reasoning Trace DAG.
- Selecting a card now calls the existing `GET /api/v1/decisions/{id}` endpoint
  as well as the trace endpoint, with stale-response guards for rapid selection.
- Renders persisted explanation, stance/type/score chips, all gate rationales,
  score/confidence/risk provenance references, and exact as-of time in IST.
- Renders persisted `TradePlan` entry zone, invalidation/stop, targets, R:R,
  model sizing/risk, validity interval, and active/pending/expired state.
- WATCH/PASS/INSUFFICIENT decisions explicitly show that no actionable plan is
  authorized; the UI never invents entry/exit values.
- Added non-destructive **Dismiss today** per instrument using an IST-day
  browser key, visible hidden count, and Restore action. Decisions, traces,
  journal, and replay evidence are never deleted.
- Added Re-validate and Market Intelligence actions using existing paths.

### Files created

- None.

### Files modified

- `src/athena/api/static/index.html`
- `src/athena/api/static/dashboard.css`
- `src/athena/api/static/dashboard.js`
- `tests/api/platform/test_dashboard_hosting.py`
- `tests/api/v1/test_core_apis.py`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`

### Public APIs

- No new API or frozen domain contract. M-D1 reuses the existing decision
  detail/trace and market validate APIs.

### Validation and architecture

- Full regression: **976 passed**.
- Targeted dashboard hosting + core API: **17 passed**.
- Changed Python tests pass Ruff; dashboard HTML parses successfully.
- Modern browser loaded the `9.18.0` assets and exposed the new brief landmark;
  interactive owner-data verification remains an owner smoke step after unlock.
- ADR-004 preserved: static HTML/CSS/vanilla JS and localhost FastAPI only.
- ADR-005 preserved: the UI renders stored rationale and never reconstructs or
  generates post-hoc explanations.
- Determinism, replayability, provider independence, and no-order boundary
  remain unchanged. No ADR required.

### Risks and technical debt

- Daily dismiss is intentionally local to one browser profile; it is not a
  cross-device preference and does not affect future candidate validation.
- Score/confidence/risk are provenance references only because rich analytical
  payloads are not yet persisted/resolvable. M-D3 owns that depth.
- The local Node executable is too old to parse pre-existing optional chaining;
  browser execution plus hosting assertions cover this milestone.
- No technical debt introduced beyond the approved phased limits.

### Suggested improvements and remaining work

- Owner smoke: unlock, select TRADE/WATCH/PASS cards, verify plan/no-plan,
  dismiss/restore, re-validate, and responsive layout.
- M-D2 subsequently delivered the read-only candles endpoint and chart overlays.
- News remains deferred to M-D5/DD-5 and is not represented as available data.

### Commit message

`feat(dashboard): add explainable instrument decision brief`

---

## Decisions pagination / latest-per-instrument fix (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Stop Today’s Decisions from silently truncating after the first API page |
| Scope | Walk all `/api/v1/decisions` pages before client dedupe; enlarge SQLite list window |
| Tests | `tests/api/platform/test_dashboard_hosting.py` asserts page-walk helpers; decisions paging suite unchanged |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Dashboard previously called `/api/v1/decisions` with the default `page_size=20`, then
  deduped only that page — large validate/seed runs hid most symbols.
- `fetchAllDecisionPages()` now requests `page_size=100`, `sort_by=ts`, and follows
  `pagination.has_next` (capped at 50 pages) before `latestDecisionPerInstrument()`.
- SQLite decision provider window raised from 2000 → 5000 so page walking can surface
  Nifty-scale candidate sets.
- Cache-bust dashboard assets `?v=9.17.0`. Hard-refresh after deploy.

---

## Live Entry M-E5 — hardening & ops polish (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Objective | Harden the approved Dock/URL → unlock → Kite → LIVE workstation path |
| Scope | Login throttling; production JWT secret resolution; localhost/TLS controls; final runbook and roadmap |
| Tests | Owner QA: **976 passed, 127 warnings in 9.53s**; auth/serve **33 passed**; R1 smoke **3 passed** |
| Coverage | Existing project coverage gate retained; no separate percentage collected |
| Status | **APPROVED 2026-07-24** — professional live-entry track complete |
| Branch | develop |

### Scope completed

- Added deterministic, thread-safe login throttling per normalized
  username/client IP: five failures in ten minutes trigger a fifteen-minute
  lockout, HTTP 429, and `Retry-After`.
- Replaced the known development JWT signing key for owner-configured runtime:
  explicit `ATHENA_JWT_SECRET` wins; otherwise a stable SHA-256 key is derived
  from the bcrypt owner hash without exposing that hash as the signing key.
- Changed the transport default to `127.0.0.1`; added paired
  `--ssl-certfile`/`--ssl-keyfile` serve options and an optional mkcert recipe.
- Preserved the existing AuthService audit sink, `/auth/me` profile,
  read-only Kite boundary, cycle-runner advisory lock, and launchd role for
  unattended scheduling.
- Added `docs/ops/LIVE_ENTRY.md`, `.env.example` security controls, README
  linkage, and M-E1–M-E5 roadmap entries.
- Isolated the R1 file-backed smoke from live Nifty seeding by disabling the
  network seed in its temporary config and adding only fixture candidates
  `AAA`/`BBB`.
- Added `docs/ops/QA_VERIFICATION.md` as the canonical regression, targeted
  suite, warning-triage, manual acceptance, and evidence procedure.

### Files created

- `src/athena/api/security/login_limiter.py`
- `tests/api/v1/test_login_limiter.py`
- `docs/ops/LIVE_ENTRY.md`
- `docs/ops/QA_VERIFICATION.md`

### Files modified

- API configuration, app wiring, security exceptions/exports/error mapping,
  auth router, serve CLI, auth route tests, `.env.example`, README,
  `scripts/smoke_file_backed_day.sh`, `docs/MILESTONES.md`, and this
  implementation log.

### Public APIs and compatibility

- No frozen analytical/domain contract changed.
- Existing `/api/v1/auth/login` now additionally returns RFC-style HTTP 429
  while locked; successful response and token contracts are unchanged.
- `athena serve` adds optional TLS flags; HTTP localhost remains the default.

### Validation and architecture

- Determinism/replayability: analytical execution paths are untouched; limiter
  clock is injectable and unit-tested.
- ADR compliance: no ADR required. The in-process worker remains interactive;
  launchd remains the unattended scheduler. No embedded UI framework added.
- Provider independence and no-order boundary: unchanged.
- Owner full regression on macOS Darwin 25.2.0 / Python 3.14.6:
  **976 passed, 127 warnings in 9.53s**.
- Known warning categories are Starlette/httpx TestClient deprecation, PyJWT's
  short test-only signing key, and Starlette's HTTP 422 constant rename; new
  categories/count increases require investigation.
- R1 file-backed smoke: **3 passed** after fixture isolation.
- Changed-file Ruff: passed. Repository-wide Ruff still reports 243 pre-existing
  findings outside this milestone; no new changed-file finding remains.
- Shell launchers parse successfully; macOS `Info.plist` validates.

### Risks, debt, and remaining work

- Login counters are intentionally process-local; restarting the localhost
  workstation clears a lockout. This is proportionate for a single-user,
  localhost-only app and avoids introducing persistent auth state.
- Optional TLS is a terminal power-user mode; the Dock launcher intentionally
  keeps the default trusted localhost HTTP path.
- No technical debt or architecture drift introduced by M-E5.
- Remaining work: none; owner approved M-E5 on 2026-07-24.

### Consolidated commit message

`feat(ops): deliver professional live-entry workstation`

QA follow-up: `test(ops): isolate smoke and document QA verification`

---

## Live Entry M-E4 — macOS Dock launcher (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Thin native `.app` wrapper; one-command installer; health-aware server start and browser open |
| Tests | App plist/executable, shell syntax, temporary signed app installation; full suite **970 passed** |
| Status | **APPROVED** |
| Branch | develop |

- `./install-athena-app` installs an ad-hoc-signed `~/Applications/ATHENA.app`.
- Dock click opens an already-running workstation or starts `./athena-serve --with-cycles`, waits for `/health/live`, then opens the dashboard.
- Finder-safe PATH includes Apple Silicon / Intel Homebrew; failures show a native alert and point to `artifacts/logs/athena-serve.log`.
- The app contains no secrets—only the repository path—and remains a shell app bundle per ADR-004 (no Tauri/Qt/Electron).
- Documentation: README quick entry and `HOST_SCHEDULE.md` install/Dock/reinstall instructions.

---

## Live Entry M-E3 — in-UI Kite morning gate (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Verify Kite session after unlock; browser login URL; request-token exchange and live reinjection |
| Tests | Full suite: **966 passed**; Kite service/API tests; HTML parse; Python lint |
| Status | **APPROVED** |
| Branch | develop |

- Routes: `GET /api/v1/ops/kite/status`, `POST /kite/start-auth`, `POST /kite/complete-auth`.
- Gate verifies read-only Kite `/user/profile`; missing/expired sessions block the LIVE state.
- Owner opens Kite in a new tab, pastes redirect URL/request token, then ATHENA exchanges, persists, re-injects, and verifies the token.
- API secret and access token never return to the browser; start/complete require ADMIN.
- CLI `./kite-auth` remains the fallback. Dashboard assets `?v=9.15.0`.
- File-backed smoke now forces its intended `file` provider instead of inheriting the owner's live Kite config.
- Header **KITE** button shows live session state; opens reconnect panel; **Clear Session** drops the access token via `POST /api/v1/ops/kite/disconnect` (assets `?v=9.16.0`).

---

## Live Entry M-E2 — athena serve supervisor (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | One-command localhost host: API + optional due-cycle worker; health serve fields; cycle lock |
| Tests | `tests/ops/test_serve_runtime.py`; `tests/api` health compatibility |
| Status | **APPROVED** |
| Branch | develop |

- CLI: `athena serve [--host] [--port] [--with-cycles] [--cycle-interval] [--open]`.
- Wrappers: `./athena-serve`, `./athena-daily serve`.
- Worker reuses `_execute_run_due` / `HostDueRunner` (same path as `run-due`).
- Advisory lock `artifacts/locks/cycle-runner.lock` shared with `run-due`.
- Health: `kite_token_status`, `cycles_enabled`, `last_cycle`, `serve_error`.
- Dashboard badge reflects cycles / kite presence (`?v=9.14.0`).

---

## Live Entry M-E1 — Auth surface + unlock screen (APPROVED)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Wire AuthService to HTTP; owner seed from `.env`; unlock gate; Bearer + refresh in dashboard |
| Tests | `tests/api/v1/test_auth_routes.py` + `tests/api` (120 passed) |
| Status | **APPROVED** |
| Branch | develop |

- Routes: `GET/POST /api/v1/auth/status|login|refresh|logout|me`.
- Owner seed: `ATHENA_OWNER_USER` + `ATHENA_OWNER_PASSWORD_HASH`; CLI `athena set-owner-password`.
- When owner hash is set, `ATHENA_SINGLE_USER` bypass is disabled; unlock is required.
- Dashboard: unlock overlay, sessionStorage JWTs, Bearer on `apiRequest`, refresh on 401, SSE `access_token` query, profile from `/me`.
- `/` redirects to `/dashboard/`. Assets `?v=9.13.0`.

---

## Dashboard workspace usability improvements (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Balanced Portfolio layout; dedicated searchable/scrollable MI stock list; Add & validate; known VIX regime selection; Decisions filters |
| Tests | HTML parse; `tests/api/v1/test_owner_candidates.py` (5 passed); browser layout/filter/scroll verification |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Overview: holdings and charts now share the left stack while log-fill/pools/reset stay on the right, removing the empty center gap; holdings retain a sticky, independently scrolling table and per-row **Add & validate**.
- MI candidate list: dedicated Stock List card with a 561-symbol independently scrolling region, live search/count, and per-row **Validate/Remove**; validation results scroll separately.
- MI dashboard picks the newest regime and prefers non-UNKNOWN volatility when merging runs.
- Decisions: Stance / Type / Sort controls (newest, symbol, score, stance) plus search.
- Assets `?v=9.12.0`. Hard-refresh after deploy. Validation card scrolls as one panel; stock-list search uses transparent dark styling.

---

## Regime VIX snapshot + decision UX clarity (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Persist India VIX market snapshot on ingest (fixes VOLATILITY_UNKNOWN); human-friendly decision copy + chip UI |
| Tests | `tests/data_layer/test_ingestion.py` (snapshot persist); decision/ops suites |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Live ingest now writes `market_snapshot()` (includes India VIX) into the ledger when the provider supports it.
- Owner validation fills VIX from INDIA VIX candles when snapshot VIX is missing.
- DecisionEngine explanations use plain language (Buy/Hold/Pass) with rounded scores and named safety checks.
- Decisions + Qualified Today: stance chips (BUY/HOLD/PASS), score chip, “Needs Risk/Data/…” gate chips; MI volatility badge shows High/Low/Normal/Unknown.
- Dashboard assets `?v=9.9.0`. Re-run validate/smoke after upgrade so new explanations and VIX appear.

---

## On-demand symbol validate + Decisions UI fix (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | After MI Add, run scoped kite ingest+score so the symbol appears in Eligible/Excluded and Decisions; fix Decisions search-icon overlap; dedupe latest decision per symbol |
| Tests | `tests/api/v1/test_owner_candidates.py` (validate empty body 422) |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- `POST /api/v1/market/validate` + `CandidatesService.validate_candidates` → `ops/symbol_validate.validate_symbols`.
- MI **Add & validate** button: upsert candidate then validate; refreshes Market Intelligence panels.
- CLI: `athena validate-symbols SYM…` / `./athena-daily validate SYM`.
- Decisions: flex search bar (no absolute icon overlap); list shows latest decision per instrument.
- Cache bust dashboard assets `?v=9.8.0`.

---

## Nifty 500 daily candidate seed (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Once-per-day merge-unique seed of `owner_candidates` from official Nifty 500 constituents CSV |
| Tests | `tests/ops/test_candidate_seed.py`; schema v6 (`ops_meta`) |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Config: `config/candidate_seed.json` (`source: NIFTY500`, merge_unique, once_per_day).
- Fetch: NSE archives CSV (+ niftyindices fallback); optional `local_file` for offline/tests.
- Merge: inserts missing symbols only; never wipes manual adds or overwrites existing notes.
- Wired into `athena cycle`, `./athena-run-due`, and `athena seed-candidates`.
- SCHEMA_VERSION 6: `ops_meta` tracks last seed date. Seed failure warns and continues with existing list.

---

## Portfolio reset + owner validation list (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | D-P1 portfolio fill reset (open\|all + CONFIRM); D-V1–D-V3 owner candidate list with two-layer daily qualify (UniverseEngine → WATCH/TRADE) |
| Tests | `tests/api/v1/test_owner_portfolio.py`, `test_owner_candidates.py`, `tests/ops/test_owner_validation.py`; schema v5 asserts updated |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- **D-P1:** `delete_owner_positions(scope=open|all)`; `POST /api/v1/portfolio/positions/reset` (ADMIN + typed `CONFIRM`); Overview UI gate; best-effort auto-backup before wipe.
- **D-V1:** SCHEMA_VERSION 5 `owner_candidates`; CRUD `/api/v1/market/candidates`; MI list editor; shared `SqliteCandidateStore` for API + CLI.
- **D-V2:** `OwnerValidationPipeline` on `athena cycle` / `./athena-run-due` runs `UniverseEngine` on candidates; ingest scoped to candidate symbols (kite catalog override when needed); MI shows real Eligible/Excluded; kite.json no longer faked as Eligible.
- **D-V3:** Eligible names scanned via `DailyMarketScanner` + DecisionEngine; decisions/traces persisted; MI “Qualified Today” = WATCH/TRADE for cycle day (same rows as Decisions tab).

Files created: `ops/owner_candidates.py`, `ops/owner_validation.py`, `api/v1/{dtos/market,routers/market,services/candidates_service}.py`, candidate/validation tests. Files modified: schema/repository, CLI + HostDueRunner, sqlite pipeline provider, dashboard static assets, dependencies/router, this log + milestones. No ADR; no order placement; journal/runs untouched by portfolio reset.

---

## Dashboard live data + owner fill ledger (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Remove dashboard seed/demo data; serve Decisions + Market Intelligence from SQLite; owner-entered Kite/Groww fill ledger for Portfolio Overview |
| Tests | API + data_layer green; new `tests/api/v1/test_owner_portfolio.py`; decision-trace + dashboard-summary updated for empty/real data |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Dropped `seed_sample_data` from API startup; live app wires `SqliteDecisionProvider`, `SqlitePortfolioProvider`, `SqlitePipelineRunProvider` via `wire_sqlite_providers`.
- Decision traces return **stored** `DecisionTrace` stages only (no synthetic 7-stage DAG).
- SCHEMA_VERSION 4: `owner_positions` table; `POST /api/v1/portfolio/positions` + `.../close` for manual fills (symbol/qty/entry/exit); cash from `config/portfolio.json` `initial_cash` (`PortfolioConfig`).
- Market Intelligence: latest SQLite run context; falls back to `kite.json` symbols when run has no universe payload; honest empty copy when neither exists.
- Dashboard Overview form to log/close owner fills; no Kite holdings API (still blocked).
- **Hotfix:** `SqliteRepository` uses `check_same_thread=False` + `RLock` so FastAPI request threads can reuse the startup connection (fixes “Log fill” / tab query thread errors).
- **Hotfix:** Market Intelligence toast on empty runs — removed TDZ reference to `evidenceText` before declaration in `dashboard.js`.

Files created: `src/athena/api/v1/providers/sqlite_providers.py`, `config/portfolio.json`, `tests/api/v1/test_owner_portfolio.py`. Files modified: schema/serialization/repository, dependencies/app, decisions/portfolio/dashboard services + routers/DTOs, dashboard static assets, tests, this log. No ADR; no order placement; frozen Position/TradeOutcome contracts reused.

---

## Production readiness -- R6 Closing / Day-Summary Cycle (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Post-close `CLOSING` cadence + dry-run cycle; briefing day roll-up + journal prompts (Blueprint §8). |
| Tests | Cadence closing cases; briefing day_summary + journal prompt clear when journaled |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- `RunTrigger.CLOSING`; `scheduling.closing` (`run_at` default 15:45); `is_closing_due` / `due_triggers`.
- Dry-run + `run-due` / CLI `cycle --trigger closing` support CLOSING.
- Briefings include `day_summary` + `journal_prompts` for decisions lacking journal rows.

Files created: (none new top-level). Files modified: `config/scheduling.json`, `src/athena/domain/enums.py`, `src/athena/config/models.py`, `src/athena/scheduling/{cadence,dry_run,__init__}.py`, `src/athena/notifications/{models,builder,__init__}.py`, `src/athena/ops/scheduled_run.py`, `src/athena/cli.py`, `docs/*`, tests. Public APIs: `is_closing_due`, `BriefingJournalPrompt`, extended `DailyBriefing`. No ADR; no order methods.

---

## Production readiness -- R5 Host Schedule + Failure Alerts (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | External launchd/cron invokes due cycles + brief; hard failures alert via file + webhook (DD-9). No embedded cron. |
| Tests | `tests/ops/test_host_ops.py` (file alert, webhook mock, idle path, failure alert, brief-after-cycle) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- CLI `athena run-due` + root `./athena-run-due` (sources `.env` for launchd).
- `HostDueRunner` evaluates cadence, runs due PREMARKET/REFRESH, optional brief, alerts on `AthenaError`.
- `FailureAlertDispatcher`: `artifacts/alerts/` + `ATHENA_ALERT_WEBHOOK_URL` (fallback `ATHENA_WEBHOOK_URL`).
- Docs: `docs/ops/HOST_SCHEDULE.md` + launchd plist example; email SMTP still deferred.

Files created: `config/host_ops.json`, `src/athena/ops/{failure_alerts,scheduled_run}.py`, `athena-run-due`, `docs/ops/HOST_SCHEDULE.md`, `docs/ops/launchd/com.athena.run-due.plist.example`, `tests/ops/test_host_ops.py`. Files modified: `src/athena/config/{models,loader,__init__}.py`, `src/athena/cli.py`, `src/athena/ops/__init__.py`, `.env.example`, `docs/*`, `README.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `HostDueRunner`, `FailureAlertDispatcher`, `load_host_ops_config`, `athena run-due`. No ADR; localhost/secrets policy preserved; no order methods.

---

## Production readiness -- R4 Kite Live Provider Adapter (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Read-only Zerodha Kite `MarketDataProvider`; config-selected bind; FileProvider remains default; secrets in `.env` only. |
| Tests | Contract suite green via fake transport; unit tests for quotes/candles/snapshot/allowlist; owner live smoke: INFY ingest OK |
| Status | **APPROVED** — Owner approved 2026-07-23 (live smoke + runbook) |
| Branch | develop |

- `KiteProvider` + allowlisted GET-only `UrllibKiteTransport` (`/instruments*`, `/quote*` only — no order paths, no kiteconnect SDK).
- Config: `config/providers/kite.json`; `ingestion.provider` accepts `file` \| `kite` (default `file`).
- Factory `build_market_data_provider`; CLI ingest/cycle loads `.env` then resolves provider.
- Ops: `docs/ops/KITE_LIVE_DATA.md` (token refresh, enable steps, limits); root `./kite-auth` interactive helper.
- Instrument ids: `NSE:SYMBOL`. Snapshot: index LTPs + India VIX; breadth left 0.

Files created: `src/athena/data/providers/{kite_provider,kite_transport,factory}.py`, `src/athena/config/env.py`, `config/providers/kite.json`, `docs/ops/KITE_LIVE_DATA.md`, `tests/data_layer/test_kite_provider.py`, `tests/contract/test_kite_provider_contract.py`. Files modified: `src/athena/config/{models,loader,__init__}.py`, `src/athena/cli.py`, `src/athena/api/app.py`, `config/ingestion.json`, `.env.example`, `docs/*`, `IMPLEMENTATION_SUMMARY.md`, `README.md`. Public APIs: `KiteProvider`, `build_market_data_provider`, `load_kite_provider_config`, `load_dotenv`. No ADR; frozen Protocol unchanged; no order methods.

---

## Production readiness -- R3 DD-1 Live Vendor Decision (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Written DD-1 decision record: criteria matrix, candidate vendors, **Zerodha Kite Connect** accepted; **no adapter code**. |
| Tests | N/A (documentation milestone) |
| Status | **APPROVED** — Owner approved 2026-07-23 (existing Kite account; Groww for manual execution only) |
| Branch | develop |

- Created `docs/decisions/DD-1-broker-live-data-vendor.md` against ATHENA-002 §15 and ADR-002.
- Recommendation: **Zerodha Kite Connect** as first live provider for R4; FileProvider remains default/fallback; C2 deep history deferred to DD-10/accumulation.
- Explicit non-goals: no R4 code, no orders, no websocket (DD-2).

Files created: `docs/decisions/DD-1-broker-live-data-vendor.md`. Files modified: `docs/MILESTONES.md`, `docs/PRODUCTION_READINESS_ROADMAP.md`, `README.md`, `IMPLEMENTATION_SUMMARY.md`.

---

## Production readiness -- R2 Decision Journal Persistence (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Persist Decision/Trace/Journal in SQLite (schema v3); SqliteDecisionSummarySource for `athena brief`; smoke seeds decision → briefing OK. |
| Tests | Full suite green; new `tests/data_layer/test_decision_journal.py`; smoke asserts briefing status OK |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- SCHEMA_VERSION 3: `decisions`, `decision_traces`, `decision_journal` tables.
- Repository: `save_decision`, `get_decision`, `get_trace`, `list_decisions`, `save_journal_entry`, `list_journal`.
- `SqliteDecisionSummarySource` wired into CLI brief; briefings reach OK when runs + decisions exist.
- Smoke seeds a fixture WATCH after cycle until live cycle emits decisions.

Files created: `src/athena/notifications/decision_source.py`, `tests/data_layer/test_decision_journal.py`. Files modified: `schema.py`, `serialization.py`, `repository.py`, `notifications/__init__.py`, `cli.py`, smoke script, ops SOP, MILESTONES, roadmap, IMPLEMENTATION_SUMMARY. No ADR; frozen Decision contracts unchanged; no order APIs.

---

## Production readiness -- R1 File-backed Daily Ops SOP (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Written SOP for file-backed daily advisory use; executable mock-day smoke on fixtures; fix CLI AthenaConfig nesting for due/cycle/brief/diagnose. |
| Tests | smoke script PASS + `tests/ops/test_file_backed_daily_smoke.py` |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- Added `docs/ops/FILE_BACKED_DAILY_OPS.md` (prereqs, refresh CSVs, premarket/refresh CLI sequence, failure playbook, smoke checklist).
- Added `scripts/smoke_file_backed_day.sh` (temp config/DB, fixture FileProvider, health → due → cycle → brief → diagnose).
- Fixed Phase 10 CLI to read `cfg.base.*` / `cfg.market.*` correctly on `AthenaConfig`.

Files created: `docs/ops/FILE_BACKED_DAILY_OPS.md`, `scripts/smoke_file_backed_day.sh`, `tests/ops/test_file_backed_daily_smoke.py`. Files modified: `src/athena/cli.py`, `docs/MILESTONES.md`, `docs/PRODUCTION_READINESS_ROADMAP.md`, `IMPLEMENTATION_SUMMARY.md`, `README.md`. No ADR; R2+ still unauthorized.

---

## Phase 10 -- Live Dry-Run Operations & AI Playbook Learning (COMPLETE — owner closed 2026-07-23)

Phase outcome: M10.1–M10.4 owner-approved. FileProvider-backed dry-run ops, briefings, and propose-only playbook diagnostics delivered. Broker binding (DD-1) deferred. No order-placement code. Next: production-readiness tracks R1–R6 in `docs/PRODUCTION_READINESS_ROADMAP.md` (unauthorized until gated).

### M10.4 -- AI Playbook Diagnostics

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Rules-based playbook diagnostics over run ledger + injectable decisions/journal; TuningProposal artifacts only; `athena diagnose`; never auto-applies config. |
| Tests | 870 passed / 0 failed (11 new diagnostics tests) |
| Status | **APPROVED** — Owner approved 2026-07-23; closes M10.4 and Phase 10 |
| Branch | develop |

Implemented propose-only diagnostics (no LLM; no R2 journal schema; no config mutation).
- `PlaybookDiagnosticsAnalyzer`: ops failure rate, insufficient-data share, gate concentration, adherence → threshold/weight proposals with `min_sample_size` gate (`blocked=True` when under-sampled).
- Paired scoring weight proposals keep sum-100 invariant in the proposed snapshot.
- `PlaybookDiagnosticsService` + `DiagnosticReportWriter` → `artifacts/diagnostics/diag-<date>.{json,txt}`.
- CLI: `athena diagnose [--as-of] [--dry-run]` (dry-run accepted; apply path does not exist).

Files created: `config/diagnostics.json`, `src/athena/diagnostics/{__init__.py,models.py,analyzer.py,writer.py,service.py}`, `tests/runtime/test_diagnostics.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/errors.py`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `DiagnosticReport`, `TuningProposal`, `PlaybookDiagnosticsService`, `load_diagnostics_config`, `athena diagnose`. No ADR; human approval required for any config change; R1–R6 still unauthorized.

### M10.3 -- Daily Briefing Notifications

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Assemble immutable DailyBriefing from SQLite run ledger (+ optional injected decisions); dispatch via FileNotifier / optional WebhookNotifier; CLI `athena brief`. |
| Tests | 859 passed / 0 failed (8 new briefing tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented assemble→notify path (no decision-pipeline rebuild; no P8.9 alert center).
- `DailyBriefingBuilder`: runs for `as_of.date()` from ledger; missing runs → `BriefingError`; no decisions → `DEGRADED` with explicit reason; failed runs degrade.
- Notifiers: `FileNotifier` (JSON+txt), `WebhookNotifier` (`ATHENA_WEBHOOK_URL` from `.env`), `EmailNotifier` refuses loudly if enabled (SMTP deferred).
- `BriefingDispatcher` + config `notifications.json`; `--dry-run` forces file-only delivery.
- CLI: `athena brief [--as-of] [--dry-run]`.

Files created: `config/notifications.json`, `src/athena/notifications/{__init__.py,models.py,builder.py,notifiers.py,dispatch.py}`, `tests/runtime/test_daily_briefing.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/errors.py`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `DailyBriefing`, `BriefingDispatcher`, notifiers, `load_notifications_config`, `athena brief`. No ADR; secrets stay in `.env`; M10.4 AI deferred.

### M10.2 -- Scheduled Dry-Run Operations

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Premarket + intraday refresh cadence; dry-run cycle = ingest → optional paper pipeline hook → SQLite run ledger; CLI `athena due` / `athena cycle`. |
| Tests | 851 passed / 0 failed (12 new dry-run/cadence tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented schedule cadence and dry-run cycle orchestration (no embedded cron; external launcher may call CLI).
- Extended `SchedulingConfig` / `scheduling.json` with `premarket.run_at` and `refresh.interval_minutes` (null → `base.refresh_interval_minutes`).
- Pure cadence helpers: `is_premarket_due`, `is_refresh_due`, `due_triggers` (injected `as_of` + last-run markers).
- `DryRunCycleOrchestrator.run_cycle(trigger, as_of=…)`: `LiveIngestionEngine` → optional `DryRunPipeline` → persist `RunRecord` (FAILED runs saved before re-raise).
- SQLite schema v2: append-only `runs` table; `save_run` / `get_run` / `list_runs` / `latest_run`; `initialize` upgrades version.
- CLI: `athena due [--as-of]`, `athena cycle --trigger premarket|refresh [--as-of]`.

Files created: `src/athena/scheduling/{cadence.py,dry_run.py}`, `tests/runtime/test_dry_run_schedule.py`. Files modified: `config/scheduling.json`, `src/athena/config/models.py`, `src/athena/scheduling/__init__.py`, `src/athena/data/store/{schema.py,repository.py,serialization.py}`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: cadence helpers, `DryRunCycleOrchestrator`, `DryRunCycleResult`, run ledger methods, `athena due`/`cycle`. No ADR; no broker SDK; no order placement; M10.3 notifications / M10.4 AI deferred.

### M10.1 -- Live Data Ingestion

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Callable live ingest cycle: MarketDataProvider quotes/candles → duplicate/freshness validation → SQLite persist; FileProvider only; `athena ingest` CLI. |
| Tests | 839 passed / 0 failed (9 new ingestion tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented `LiveIngestionEngine.run_cycle(as_of=…)` as a deterministic poll→validate→persist step (scheduler deferred to M10.2).
- Config: `config/ingestion.json` + `IngestionConfig` / `load_ingestion_config` (provider=`file` only until DD-1).
- Reuses `DatasetValidator` (OHLC/duplicates/freshness; gaps off by default for live lookback) and `QuarantineRegistry`; adds `validate_quotes` for quote price/freshness/dupes.
- Empty candle fetches skip (provider contract); failed validation quarantines and raises `DataStaleError` / `DataValidationError` with no writes for that cycle’s failed path.
- `skip_existing` filters already-persisted candles/quotes for idempotent re-runs.
- CLI: `athena ingest [--as-of ISO]` wires FileProvider + calendar + SQLite (`ATHENA_DB_PATH` override).

Files created: `config/ingestion.json`, `src/athena/data/ingestion/{__init__.py,engine.py,models.py}`, `tests/data_layer/test_ingestion.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/data/validation/{validators.py,__init__.py}`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `LiveIngestionEngine`, `IngestionResult`, `build_ingest_validator`, `validate_quotes`, `load_ingestion_config`, `athena ingest`. No ADR; frozen `MarketDataProvider` unchanged; no broker SDK; no order methods.

---

## Phase 9 -- Dashboard & Operations Console (COMPLETE — owner closed 2026-07-23)

Phase outcome: single-user workstation console delivered and approved (P9.1–P9.7), including console reliability hotfixes and Overview capital correctness. Architecture frozen; no order-placement code; Phase 10 authorized after Phase 9 close.

### P9.7 -- Live Monitoring & Admin

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Replace Live Operations placeholder with SSE warning stream, stage telemetry Chart.js bars, and CONFIRM-gated SQLite backup/restore admin controls. |
| Tests | 830 passed / 0 failed (11 new ops + hosting update) |
| Status | **APPROVED** — closes P9.7 and Phase 9 (Owner approved) |
| Branch | develop |

Implemented Live Operations workstation APIs and UI on `#tab-operations`.
- Added `GET /api/v1/ops/stream` (SSE heartbeats + derived health/metrics/stage/database warnings).
- Added `GET /api/v1/ops/telemetry` aggregating latest pipeline stage statuses for charts.
- Added `GET/POST /api/v1/ops/backups` and `POST /api/v1/ops/backups/{id}/restore` reusing `create_backup` / `restore_backup`; restore requires exact token `CONFIRM`.
- Built Operations UI: EventSource warning feed, horizontal stage telemetry chart, backup list + create/restore admin panel.
- Clarified restore UX (CONFIRM unlocks buttons; explicit row click required; toast + last-restore feedback).
- Paths configurable via `ATHENA_DB_PATH` / `ATHENA_BACKUP_DIR` and `app.state.ops_*` for tests; missing live DB fails loudly (503).

Files created: `src/athena/api/v1/dtos/ops.py`, `src/athena/api/v1/services/ops_service.py`, `src/athena/api/v1/routers/ops.py`, `tests/api/v1/test_ops.py`. Files modified: `src/athena/api/v1/router.py`, `src/athena/api/dependencies.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/static/{index.html,dashboard.js,dashboard.css}`, `tests/api/platform/test_dashboard_hosting.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs added: ops stream/telemetry/backups/restore. No ADR; frozen contracts preserved; Phase 9 closed before Phase 10 authorization.

---

### Hotfix -- Console modal leak & loader failure UX (2026-07-23)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Repair workstation console defects observed in live screenshots: inactive modals leaking into page flow, silent loader failures leaving permanent "Loading..." states, and a fake Live Operations loader ahead of P9.7. |
| Tests | 819 passed / 0 failed (hosting suite extended +1) |
| Status | **OWNER VERIFIED** — not a new milestone; hardening of P9.1–P9.6 console |
| Branch | develop |

Root cause: `.modal-overlay` previously used `display: flex` while inactive (opacity-only hide), so trace/backtest modal chrome rendered inside the document flow across every tab. Concurrently, auth/env startup gaps caused API failures; strategies/decisions loaders swallowed errors and never cleared placeholder text.
- Moved trace and backtest modals outside `#app`, marked `hidden` + `aria-hidden` at rest, and forced inactive overlays to `display: none !important`.
- Added `openModal` / `closeModal` / Escape-to-dismiss helpers; cache-busted static assets to `?v=9.6.2`.
- Hardened Market / Strategies / Decisions loaders to always replace Loading placeholders on empty, error, or missing context (with nested `final_context` fallback).
- Replaced Live Operations fake loader with an explicit P9.7 placeholder (milestone not started — no speculative ops UI).
- Extended `tests/api/platform/test_dashboard_hosting.py` to lock modal inertness and placeholder contracts.

Files modified: `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.css`, `src/athena/api/static/dashboard.js`, `tests/api/platform/test_dashboard_hosting.py`, `IMPLEMENTATION_SUMMARY.md`.

---

### Correctness patch -- Overview exposure & day-change (2026-07-23)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Fix capital-screen correctness: sector donut was 100% fake cash because summary omitted `exposure_by_sector`; day-% was a hardcoded HTML placeholder. |
| Tests | 819 passed / 0 failed |
| Status | **OWNER VERIFIED** |
| Branch | develop |

- Extended `DashboardSummaryDTO` with `exposure_by_sector` and `day_change_pct`.
- `DashboardService` now maps portfolio sector exposure + cash into absolute ₹ slices and computes day-change from the two most recent NAV snapshots.
- Seeded prior-day + current NAV snapshots aligned to live portfolio value (₹1,25,050) so Overview chart and % are deterministic.
- Wired Overview UI for day-change (+/− classes) and sector tooltips; title-cased strategy profile names.
- Updated summary + analytics list tests; cache-bust `?v=9.6.3`.

Files modified: `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/static/{index.html,dashboard.js}`, `tests/api/platform/test_dashboard_summary.py`, `tests/api/v1/test_reports_analytics_export.py`, `IMPLEMENTATION_SUMMARY.md`, `docs/MILESTONES.md`.

---

### P9.6 -- Decision Trace DAG Viewer

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Implement backend REST trace endpoint, briefing document browser list, and interactive 7-node DAG flowchart rendering connection lines using SVG overlay layers. |
| Tests | 818 passed / 0 failed (3 new) |
| Status | **APPROVED** — closes P9.6 (Owner approved) |
| Branch | develop |

Implemented backend services and interactive visual workstation features to explore decision rationales.
- Created `GET /api/v1/decisions/{id}/trace` resolving execution logs and mapping variables to 7 sequential pipeline stages.
- Developed search-enabled Briefing Documents browser card listing past recommendation entries.
- Designed node flow diagram representing Universe Ingest, Indicators, Scoring, Confidence, Risk, Quality Gates, and Recommendation outputs.
- Programmed dynamic connector line drawing inside absolute SVG viewport, wired to window resize triggers.
- Wired click-to-open node parameter details card rendering composite scores, indicators thresholds, and gate checklists.

Files created: `tests/api/v1/test_decision_trace.py`. Files modified: `src/athena/api/v1/dtos/decisions.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/services/decisions_service.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `docs/MILESTONES.md`. Public APIs added: `GET /api/v1/decisions/{id}/trace`. 3 new integration tests validating trace node schemas and exception parameters. All quality checks pass; 818 total suite tests run successfully.

---

### P9.5 -- Strategy & Backtest Workspace

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Implement backend APIs, seed mock runs, and build front-end workstation widgets under the Strategies & Scans tab (`#tab-strategies`) to display active strategy profiles and historical backtest runs. |
| Tests | 815 passed / 0 failed (6 new) |
| Status | **APPROVED** — closes P9.5 (Owner approved) |
| Branch | main |

Implemented backend services, mock seeding, and interactive workstation UI components for strategy configuration and backtest execution.
- Created `GET /api/v1/strategies/profiles` returning active strategy profiles and selection rules.
- Created `GET /api/v1/backtests/runs` and `GET /api/v1/backtests/runs/{run_id}` exposing backtest replays and performance metrics.
- Seeded a 10-step mock backtest session spanning all 5 reference strategies inside `in_memory.py`.
- Developed a two-column UI grid displaying Strategy Profiles Matrix and Backtest Replays.
- Integrated a Chart.js comparison bar chart showing completed vs failed steps for each run.
- Implemented a detailed modal drawer showing chronological timelines and horizontal strategy match performance bars.

Files created: `src/athena/api/v1/dtos/strategies.py`, `src/athena/api/v1/dtos/backtests.py`, `src/athena/api/v1/services/strategies_service.py`, `src/athena/api/v1/services/backtests_service.py`, `src/athena/api/v1/routers/strategies.py`, `src/athena/api/v1/routers/backtests.py`, `tests/api/v1/test_strategies_backtests.py`. Files modified: `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/router.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `docs/MILESTONES.md`. Public APIs added: `GET /api/v1/strategies/profiles`, `GET /api/v1/backtests/runs`, `GET /api/v1/backtests/runs/{id}`. 6 new integration tests validating payload formats, authentication guards, and details lookup. All quality checks pass; 815 total suite tests run successfully.

---

### P9.4 -- Market & Universe Dashboard

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Build the Swing Trading Workstation's Market Intelligence and Universe Dashboard containing Volatility regime badges, interactive trading calendar session grid, and search-enabled Universe inclusion traces. |
| Tests | 809 passed / 0 failed (1 new) |
| Status | **APPROVED** — closes P9.4 (Owner approved) |
| Branch | main |

Implemented visual market and universe dashboard workstation panels under `src/athena/api/static/`.
- Created `GET /api/v1/dashboard/calendar` returning NSE segment holidays, expiries, special timings, and macro events.
- Extended dashboard service to resolve and load calendar configuration files dynamically.
- Seeded sample pipeline runs with volatility regime evaluations and eligibility traces in `in_memory.py`.
- Designed three-column grid workstation layout displaying Trend/Volatility/Gap badges, health gauge, interactive calendar cells with dots indicators, and search-enabled universe list.
- Implemented step-by-step eligibility trace inspector modals detailing rule checks outcomes (PASS/FAIL).

Files created: None. Files modified: `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/v1/routers/dashboard.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `tests/api/v1/test_core_apis.py`. Public APIs added: `GET /api/v1/dashboard/calendar`. 1 new integration test validating calendar structure. All quality checks pass; 809 total suite tests run successfully.

---

### P9.3 -- Portfolio & Capital Allocation Dashboard

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Build visual dashboard components showing exposure breakdowns, asset balances, and portfolio charts including NAV area line chart, Sector Exposure donut chart, and open holdings table detail. |
| Tests | 818 passed / 0 failed (0 new) |
| Status | **APPROVED** — closes P9.3 (Owner approved) |
| Branch | main |

Implemented visual portfolio dashboard components under `src/athena/api/static/` utilizing Chart.js CDN hosting.
- Integrated canvas configurations for `#nav-chart` and `#sector-chart` inside `index.html`.
- Implemented `renderNavChart(snapshots)` and `renderSectorChart(exposure)` functions in `dashboard.js` with responsive configurations, tooltips, currency formatting, and fallback points.
- Wired charts rendering to load portfolio performance snapshots data asynchronously from `/api/v1/analytics/performance/snapshots`.
- Introduced environment-controlled single-user mode authentication bypass when `ATHENA_SINGLE_USER=true` is set.

Files created: None. Files modified: `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/security/dependencies.py`, `task.md`. Public APIs added: None. All quality checks pass; 818 total suite tests run successfully.

---

## Phase 8 -- Application Platform (completed)

### P8.5 -- API Platform Completion & Production Readiness

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Finalize the API platform infrastructure and establish a production-grade API foundation with health, versioning, metadata, feature/capability discovery, standard headers, request context middleware, unified RFC 9457 error mappings, and OpenAPI contract completeness. |
| Tests | 806 passed / 0 failed (7 new) |
| Status | **APPROVED** — closes P8.5 (Owner approved) |
| Branch | main |

Finalized REST API platform infrastructure.
- Established a dedicated `platform` module defining extensible `BuildInfoProvider` and `MetadataProvider` protocols.
- Implemented `/health`, `/health/live`, and `/health/ready` check diagnostics.
- Implemented `/api/version` and `/api/info` consolidated startup metadata endpoints for desktop/UI clients.
- Introduced `PlatformMiddleware` combining request ID, correlation ID, logging, execution timing, standard headers injection, and unhandled exception-to-ProblemDetails mapping.
- Standardized error handling, migrating all mappings to use unified RFC 9457 `ProblemDetail` schemas.
- Audited all routes to confirm OpenAPI tags, operation IDs, summaries, descriptions, and pagination metadata schemas are 100% complete and consistent.

Files created: `src/athena/api/platform/health.py`, `src/athena/api/platform/version.py`, `src/athena/api/platform/metadata.py`, `src/athena/api/platform/info.py`, `src/athena/api/platform/headers.py`, `src/athena/api/platform/problem_details.py`, `src/athena/api/platform/middleware.py`, `src/athena/api/platform/providers/build_info_provider.py`, `src/athena/api/platform/providers/metadata_provider.py`, `tests/api/platform/test_platform.py`, `docs/API_PLATFORM_GUIDE.md`. Files modified: `src/athena/api/app.py`, `src/athena/api/errors.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/routers/health.py`, `src/athena/api/v1/routers/metrics.py`. Public APIs added: `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /api/version`, `GET /api/meta`, `GET /api/features`, `GET /api/capabilities`, `GET /api/info`. 7 new integration tests validating process liveness/readiness, headers propagation, timing, unhandled panic mappings, contract schemas, and pagination consistency. All quality checks pass; 806 total suite tests run successfully.

---

### P8.4 -- Reports, Analytics & Export APIs

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Expose Generic Reports, Portfolio Performance Analytics, and Presentation Format Export generation endpoints under versioned REST paths, backed by CQRS-aligned query and command providers. |
| Tests | 799 passed / 0 failed (14 new) |
| Status | **APPROVED** -- closes P8.4 (Principal Engineer review passed) |
| Branch | main |

Implemented reports, analytics, and exports API endpoints under versioned REST paths `/api/v1/`.
- Domain exceptions (`ReportNotFoundError`, `PerformanceSnapshotNotFoundError`, `ExportSnapshotNotFoundError`, `ExportArtifactNotFoundError`, `ExportGenerationError`) registered and mapped to HTTP Problem Details.
- Composed, nested DTOs (including `ArtifactMetadataDTO`, `ReportMetadataDTO`, `AnalyticsProvenanceDTO`, `SourceReferenceDTO`, `ExportOptionsDTO`, `ExportRequestDTO`, `ExportJobDTO`) decouple the transport interface from internal structures.
- Structured export requests and job status wrappers model export generation as a job abstraction, maintaining forward-compatibility for future asynchronous workers.
- CQRS-aligned provider separation decouples query interfaces from command mutation.
- Verified lease privilege and RBAC permission checks across all endpoints.

Files created: `src/athena/api/v1/dtos/reports.py`, `src/athena/api/v1/dtos/analytics.py`, `src/athena/api/v1/dtos/exports.py`, `src/athena/api/v1/services/reports_service.py`, `src/athena/api/v1/services/analytics_service.py`, `src/athena/api/v1/services/exports_service.py`, `src/athena/api/v1/routers/reports.py`, `src/athena/api/v1/routers/analytics.py`, `src/athena/api/v1/routers/exports.py`, `tests/api/v1/test_reports_analytics_export.py`. Files modified: `src/athena/api/v1/dtos/base.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/services/__init__.py`, `src/athena/api/v1/routers/__init__.py`, `src/athena/api/v1/router.py`. Public APIs added: `GET /api/v1/reports`, `GET /api/v1/reports/{id}`, `GET /api/v1/analytics/performance/snapshots`, `GET /api/v1/analytics/performance/snapshots/{id}`, `GET /api/v1/exports/snapshots`, `GET /api/v1/exports/snapshots/{id}`, `GET /api/v1/exports/artifacts/{id}`, `POST /api/v1/exports`. 14 new integration tests covering listing summaries, detail specs, provenance tracking, dynamic export generation jobs, and header/permission guards. All 10 validation checklist items passed; 799 total suite tests pass clean.

---

### P8.3 -- Core Platform APIs

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Expose trading decisions, portfolios, execution run logs, scheduling history, and workspace snapshots under secure, authenticated, role-based controls. |
| Tests | 785 passed / 0 failed (14 new) |
| Status | **APPROVED** -- closes P8.3 (Principal Engineer review passed) |
| Branch | main |

Implemented core intelligence and operational API resources under versioned REST paths `/api/v1/`.
- Domain lookup exceptions mapped to RFC 9457 HTTP Problem Details via `AthenaExceptionMapper` (e.g. `DecisionNotFoundError`, `PortfolioUnavailableError`).
- Composed, generic DTO structures defined under `athena.api.v1.dtos.base` (including `CollectionResult`, `QuerySpecification`, `ResourceReference`).
- Decisions, Portfolios, Pipelines, Scheduler, and Workspace services map internal domain objects to clean public DTOs.
- Secured all routes with `RequirePermission(Permission.READ)` dependency.
- Collection list endpoints support query-based specification parsing for pagination, sorting, and filtering.
- Consolidated DTO optimization ensures workspace snapshots list returns lightweight metadata summaries while GET details returns full entries.

Files created: `tests/api/v1/test_core_apis.py`. Files modified: `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/v1/routers/portfolio.py`, `src/athena/api/v1/routers/pipelines.py`, `src/athena/api/v1/routers/scheduler.py`, `src/athena/api/v1/routers/workspace.py`, `src/athena/api/v1/services/decisions_service.py`. Public APIs added: `GET /api/v1/decisions`, `GET /api/v1/decisions/{id}`, `GET /api/v1/portfolio`, `GET /api/v1/pipelines/runs`, `GET /api/v1/pipelines/runs/{id}`, `GET /api/v1/scheduler/history`, `GET /api/v1/scheduler/history/{id}`, `GET /api/v1/workspace/snapshots`, `GET /api/v1/workspace/snapshots/{id}`. 14 new integration tests covering listing pagination, specs, filtering, details lookup, error status, and permission/RBAC bounds. All 10 validation checklist items passed; 785 total suite tests pass clean.

---

### P8.2 -- Authentication & RBAC

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Introduce production-grade authentication and authorization: Users, Roles, Permissions, JWT, API Keys, Sessions, RBAC, Password hashing, Permission middleware, Token refresh, Audit logging |
| Tests | 771 passed / 0 failed (16 new) |
| Status | **APPROVED** -- closes P8.2 (Principal Engineer review passed) |
| Branch | main |

Implemented the production authentication and authorization layer. `SecurityConfig` isolates cryptographic parameters (secret keys, algorithms, expiries, rounds) into `APISettings`. `AuthenticatedPrincipal` defines the immutable, runtime security context carrying pre-resolved user ID, role, and fine-grained permissions. `PasswordHasher` protocol abstraction uses `BcryptPasswordHasher` for password validation, shielding high-level components from raw password schemas. `TokenSigner` and `TokenClaimsFactory` divide signature verification from JWT claim generation. API Key persistence is split between `APIKeyMetadata` (hashes and active flags) and `APIKeySecret` (one-time returned key plain-text `key_id.raw_secret`). `SessionStore` protocol abstracts session status and token rotation tracking, using an `InMemorySessionStore` implementation that revokes session trees upon detecting refresh token reuse. `AuthenticationProvider` and `AuthorizationProvider` coordinate credential verification and permission validation. Security exceptions are mapped inside `AthenaExceptionMapper` to generate RFC 9457 Problem Details. FastAPI dependencies `get_current_user` and `RequirePermission` guard controller routes, integrating natively with OpenAPI schemas. `LoggingAuditSink` writes structured audit events to stdout log lines.

Files created: `src/athena/api/security/exceptions.py`, `src/athena/api/security/models.py`, `src/athena/api/security/hashing.py`, `src/athena/api/security/token.py`, `src/athena/api/security/repos.py`, `src/athena/api/security/providers.py`, `src/athena/api/security/dependencies.py`, `src/athena/api/security/audit.py`, `src/athena/api/security/__init__.py`, `tests/api/v1/test_security.py`. Files modified: `src/athena/api/config.py` (SecurityConfig), `src/athena/api/errors.py` (mappings), `src/athena/api/app.py` (app state initialization). Public APIs added: None (dependencies and exceptions only). 16 security integration tests covering hashing, claim parsing, token rotation, API key hashing checks, RBAC route bounds, and custom security exceptions. All 10 validation checklist items passed; 771 total suite tests pass clean.

---

### P8.1 -- Platform API Foundation

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Design and implement ATHENA's production REST API infrastructure: FastAPI app factory, ASGI/Lifespan lifecycle, API versioning (`/api/v1/`), unified response envelope `AthenaResponse[T]`, generic filtering (`FilterParams`), pagination/sorting params, `HealthProvider`/`MetricsProvider` protocols, `AthenaExceptionMapper` (RFC 9457 Problem Details) |
| Tests | 755 passed / 0 failed (24 new) |
| Status | **APPROVED** -- closes P8.1 (Principal Engineer review passed) |
| Branch | main |

Implemented the production FastAPI REST API platform foundation. `APISettings` separates TransportConfig (deployment) from AppMetadataConfig (application identity) with secure-by-default empty CORS origin list. `create_app()` uses a lifespan context manager (`@asynccontextmanager lifespan`) to manage startup and shutdown events cleanly. `AthenaResponse[T]` is the single, unified response envelope used across all endpoints, carrying optional pagination and links metadata. `PaginationMeta` and `PaginationParams` are future-ready, reserving cursor fields next to standard offset page parameters. `FilterParams` and `SortParams` establish consistent collection query interfaces. `AthenaExceptionMapper` functions as a central registry mapping domain errors to HTTP status codes and RFC 9457 `ProblemDetail` structures. Service components (`HealthService` and `MetricsService`) depend entirely on abstract `HealthProvider` and `MetricsProvider` protocols, with default implementations reading from system health checks and returning scaffold telemetry metrics. Middlewares inject unique `X-Request-ID` headers to all responses and format structured request logs. OpenAPI 3.1 is auto-generated with interactive documentation at `/api/docs`.

Files created: `src/athena/api/config.py`, `src/athena/api/errors.py`, `src/athena/api/middleware.py`, `src/athena/api/dependencies.py`, `src/athena/api/app.py`, `src/athena/api/v1/router.py`, `src/athena/api/v1/dtos/base.py`, `src/athena/api/v1/dtos/common.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/observability.py`, `src/athena/api/v1/routers/health.py`, `src/athena/api/v1/routers/metrics.py`, `src/athena/api/v1/services/health_service.py`, `src/athena/api/v1/services/metrics_service.py`, `tests/api/conftest.py`, `tests/api/v1/test_health.py`, `tests/api/v1/test_metrics.py`, `tests/api/v1/test_error_handling.py`. Files modified: `pyproject.toml` (dependencies). Public APIs added: `GET /api/v1/health`, `GET /api/v1/metrics`, `/api/docs`. 24 new integration tests covering endpoint payloads, headers, CORS behavior, validation errors, and custom exception mappings. All 10 validation checklist items passed; 755 total suite tests pass clean.

---

## Phase 7 -- Production Orchestration & Scheduling (complete)

### P7.5 -- Pipeline Scheduler Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Introduce scheduling-domain bridge adapter: `ScheduleRunRequest`, `PipelineScheduleRun`, `PipelineScheduleHistory`, `SystemScheduleAdapter` |
| Tests | 731 passed / 0 failed (26 new) |
| Status | **APPROVED** -- closes Phase 7 (Principal Engineer review passed) |
| Branch | main |

Introduced ATHENA's scheduling-domain bridge. `ScheduleRunRequest` is a stable, versioned input contract bundling `ScheduledJob`, `decisions`, `current_prices`, and `as_of`; validation fires at construction, establishing the request-rejected lifecycle boundary before execution begins. `PipelineScheduleRun` is a thin, immutable scheduling envelope holding only the scheduling-domain metadata (`schedule_run_id`, `job_id`, `definition_id`, `duration_seconds`) backed by `SystemPipelineResult` as the authoritative execution record -- no fields duplicated. `PipelineScheduleHistory` is an immutable append-only history exposed as a read-only property; the adapter holds the current instance and replaces it via `record()` with no mutable state leakage. `SystemScheduleAdapter` coordinates the four-step lifecycle: validate-and-build context (via private `_ScheduleContextBuilder`), measure duration, delegate to `SystemPipelineRunner`, wrap result, record history. Failure recording policy is lifecycle-based: request-rejected failures produce no history record; execution-started failures (pipeline failure, contract failure, workspace failure) always produce a `PipelineScheduleRun` and are always recorded. The scheduling domain never touches `PipelineDefinition`, artifact keys, or stage topology.

Files created: `src/athena/orchestration/schedule_models.py`, `src/athena/orchestration/schedule_adapter.py`, `tests/runtime/test_pipeline_scheduler.py`. Files modified: `src/athena/orchestration/__init__.py` (exported four new APIs). Public APIs added: `ScheduleRunRequest`, `PipelineScheduleRun`, `PipelineScheduleHistory`, `SystemScheduleAdapter`. Private (not exported): `_ScheduleContextBuilder`. 26 new tests across four test classes covering request validation, thin-envelope design, append-only history semantics, adapter execution lifecycle, failure recording policy, and scheduler-pipeline isolation. No ADR required; no architecture drift; zero technical debt. All 10 validation checklist items passed; 731 total suite tests pass clean.

---

### P7.4 -- Pipeline Runner Integration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Implement integrated runtime orchestration layer: `PipelineContract`, `validate_contract`, `PipelineCoordinator`, `WorkspaceAssembler`, `SystemPipelineRunner`, `SystemPipelineResult` |
| Tests | 705 passed / 0 failed (12 new) |
| Status | **APPROVED** — closes P7.4 (Principal Engineer review passed) |
| Branch | main |

Implemented ATHENA's integrated production runtime. `PipelineContract` declares symmetric input/output requirements per pipeline; `validate_contract()` is a pure validation function that raises `OrchestrationError` on missing required inputs. `PipelineCoordinator` executes an ordered sequence of `(PipelineDefinition, PipelineContract)` pairs generically — enforcing contracts between runs and threading functional context — with no knowledge of specific artifact keys. `WorkspaceAssembler` is a standalone post-processing adapter that extracts intelligence artifacts from the final `PipelineContext` and delegates construction to `UnifiedIntelligenceWorkspace`, fully isolating workspace assembly from the orchestration layer. `SystemPipelineRunner` is the high-level system entry point, composing coordinator and assembler with explicit four-boundary failure handling: execution failure → immediate termination; contract validation failure → raises `OrchestrationError`; intelligence failure → skips workspace; workspace failure → exception caught, pipelines preserved, `overall_status=FAILED`. `SystemPipelineResult` is an immutable generic container holding `pipeline_runs: tuple[PipelineResult, ...]` to scale beyond two pipelines.

Files created: `src/athena/orchestration/contract.py`, `src/athena/orchestration/coordinator.py`, `src/athena/orchestration/workspace_adapter.py`, `src/athena/orchestration/system_runner.py`, `tests/runtime/test_pipeline_runner_integration.py`. Files modified: `src/athena/orchestration/models.py` (added `SystemPipelineResult`), `src/athena/orchestration/__init__.py` (exported all P7.4 APIs). Public APIs added: `PipelineContract`, `validate_contract`, `EXECUTION_PIPELINE_CONTRACT`, `INTELLIGENCE_PIPELINE_CONTRACT`, `PipelineCoordinator`, `WorkspaceAssembler`, `SystemPipelineRunner`, `SystemPipelineResult`. 12 new tests covering: contract construction and validation, coordinator sequence execution, coordinator contract failure boundary, workspace assembler extraction, end-to-end system cycle success, execution failure early exit, workspace assembly failure handling, deterministic replayability, and `FrozenInstanceError` immutability. No ADR required; no architecture drift; zero technical debt. All 10 validation checklist items passed; 705 total suite tests pass clean.

---

### P7.3 — Intelligence Pipeline Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Wire six presentation/intelligence stage adapters into a validated, declarative `PipelineDefinition`; model topology as four independent producer roots, Timeline as intermediate aggregator, and Export as terminal aggregator |
| Tests | 693 passed / 0 failed (21 new) |
| Status | **APPROVED** — closes P7.3 (Owner approved) |
| Branch | main |

Built ATHENA's second production pipeline. `create_intelligence_pipeline()` returns an immutable `PipelineDefinition` with six stages: four independent roots (`ReportingStage`, `ExplainabilityStage`, `DashboardStage`, `MonitoringStage`), one intermediate aggregator (`TimelineStage` depending on the four roots), and one terminal aggregator (`ExportStage` depending on all five upstream stages). `validate_intelligence_pipeline()` enforces the correct topological shape, stage count (6), and expected stage IDs. The explicit execution-artifact input contract is defined by `INTELLIGENCE_PIPELINE_REQUIRED_INPUTS` and `INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS` to prevent implicit runtime assumptions. `IntelligenceArtifactKey` and `IntelligenceStageId` enums eliminate all raw string keys in context propagation. Each stage adapter wraps its engine internally with no concrete engine injection at builder level.

Files created: `src/athena/orchestration/pipelines/intelligence.py`, `src/athena/orchestration/stages/{reporting,explainability,dashboard,monitoring,timeline,export}.py`, `tests/runtime/test_intelligence_pipeline.py`. Files modified: `src/athena/orchestration/pipelines/keys.py`, `src/athena/orchestration/pipelines/__init__.py`, `src/athena/orchestration/stages/__init__.py`, `src/athena/orchestration/__init__.py`. Public APIs added: `IntelligenceArtifactKey`, `IntelligenceStageId`, `INTELLIGENCE_PIPELINE_REQUIRED_INPUTS`, `INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS`, `create_intelligence_pipeline`, `validate_intelligence_pipeline`, and all six stage classes. 21 new tests: registration, topology validation, stage count, roots, validators, stage execution, failure isolation, and deterministic replayability. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 693 suite tests pass.

---

### P7.2 — Execution Pipeline Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Wire all eight execution-domain stage adapters into a validated, declarative `PipelineDefinition` using the P7.1 generic orchestration framework; typed artifact key model replaces all string-based context access |
| Tests | 672 passed / 0 failed (7 new) |
| Status | **APPROVED** — closes P7.2 (Principal Engineer review passed) |
| Branch | main |

Built ATHENA's first production pipeline. `create_execution_pipeline()` returns an immutable `PipelineDefinition` (not a live executor) with eight `PipelineStage` adapters wired in correct topological order: two independent root stages (`PortfolioSnapshotStage`, `DecisionsLoadStage`) followed by `AllocationStage → SizingStage → OrderPlanningStage → BrokerTranslationStage → OrderLifecycleStage → PortfolioAnalyticsStage`. Each stage adapter owns its own engine dependencies and writes a typed `ExecutionArtifactKey` value into the context; no concrete engines are injected at the builder level. `validate_pipeline_definition()` asserts stage count, dependency integrity, key-to-stage consistency, and dual-root topology. `ExecutionArtifactKey` and `ExecutionStageId` enums replace all string-based context access, satisfying the typed key model requirement from the architecture review. Pipeline topology is immutable in code; operational parameters (timeout, retries) remain configurable via `PipelineConfig`. The dual-root design preserves future parallel execution of the two root stages without any structural change.

Files created: `src/athena/orchestration/pipelines/{__init__,keys,execution}.py`, `src/athena/orchestration/stages/{__init__,portfolio_snapshot,decisions,allocation,sizing,order_planning,broker_translation,lifecycle,analytics}.py`, `tests/runtime/test_execution_pipeline.py`. Files modified: `src/athena/orchestration/__init__.py` (exported new APIs). Public APIs added: `ExecutionArtifactKey`, `ExecutionStageId`, `create_execution_pipeline`, `validate_pipeline_definition`, and all eight stage classes. 7 new tests: definition type, stage count, dual independent roots, validator passes, stage execution artifact, failure isolation, deterministic replayability. Fixed 4 E501 linter warnings in stage success-message strings. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 672 suite tests pass.

---

### P7.1 — Generic Pipeline Infrastructure

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Domain-agnostic pipeline execution framework: stage-based orchestration, typed execution context, composable retry/fallback/timeout policies, deterministic structured execution record |
| Tests | 665 passed / 0 failed (10 new) |
| Status | **APPROVED** — closes P7.1 (Principal Engineer review passed) |
| Branch | main |

Built the Generic Pipeline Infrastructure (`src/athena/orchestration/`). `PipelineExecutor` performs topological sort of `PipelineStage` dependencies, gates downstream stages on upstream success (propagates `SKIPPED` through dependents of failed stages), evaluates configurable `RetryPolicy` (max attempts + delay), invokes an optional `fallback_handler` on exhaustion, enforces `timeout_seconds` per stage, and accumulates all outcomes into an immutable `PipelineResult`. All data types are `frozen=True, slots=True`. The framework is entirely domain-independent — zero imports from any ATHENA business module.

**Phase 6 engine bug fixes (identified during P7.1 full-suite self-validation):** Seventeen stale field-name references in Phase 6 presentation/analytics engines (dashboard, explainability, timeline, monitoring, reporting, analytics/portfolio) were corrected against the actual `PortfolioSnapshot` and `AllocationPlanSummary` contracts. NAV formula in `analytics/portfolio/engine.py` corrected from `total_cash + gross_exp` (double-counted) to `available_cash + reserved_cash + gross_exp`. Two test files corrected (`test_portfolio_analytics.py` — wrong kwarg names and monotonic timestamp; `test_workspace.py` — fixture omitted `schedule_execution`/`workflow` sentinels). No domain models, frozen contracts, or business logic were changed.

Files created: `src/athena/orchestration/{__init__,models,engine}.py`, `config/pipeline.json`, `tests/runtime/test_orchestration.py`. Files modified (bug fixes only): `src/athena/reporting/engine.py`, `src/athena/dashboard/engine.py`, `src/athena/explainability/engine.py`, `src/athena/timeline/engine.py`, `src/athena/monitoring/engine.py`, `src/athena/analytics/portfolio/engine.py`, `tests/runtime/test_portfolio_analytics.py`, `tests/runtime/test_workspace.py`. Public APIs added: `PipelineStage`, `PipelineContext`, `StageResult`, `PipelineResult`, `RetryPolicy`, `PipelineExecutor`. 10 new tests: single-stage execution, dependency ordering, skip propagation, retry with success, retry exhaustion + fallback, timeout enforcement, deterministic independent ordering, deterministic replay, immutable outputs, config validation. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 665 suite tests pass.

---

## Phase 1 — Data Foundation (complete)

### M1.6 — Backup & Restore  (completes Phase 1)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic backup + restore with integrity verification, schema-compat enforcement, recovery validation |
| Tests | 182 passed / 0 failed (11 new) |
| Status | **APPROVED** — closes Phase 1 (Principal Engineer review passed) |
| Branch | main |

Built the backup/restore layer. `create_backup` integrity-verifies the source, snapshots it via SQLite's online backup API written atomically (temp + `os.replace`, so a backup file is always complete), and writes a JSON metadata sidecar (schema version, per-table counts, provenance). `restore_backup` validates the backup first (integrity + schema-version compatibility — no silent repair, no automatic migration), replaces the target atomically, clears stale WAL sidecars, then re-verifies the restored repository (integrity, foreign keys, schema version, record counts vs metadata) and reports the outcome. Every failure mode raises `RepositoryError` with an actionable message and never leaves the target inconsistent. Repository-focused; no business/provider/intelligence logic.

Files created: `src/athena/data/store/backup.py`, `tests/data_layer/test_backup_restore.py`. Files modified: `src/athena/data/store/{__init__,repository}.py` (exports; repo `path`/`connection`/`record_counts` accessors). Public APIs added: `create_backup`, `restore_backup`, `BackupResult`, `RestoreResult`. 11 new tests: successful backup/restore, overwrite behavior, read-only destination, recovery of every entity, restored==original, deterministic repeated cycles, missing/corrupted backup, incompatible schema refusal (+ target untouched), unhealthy-source refusal.

**Codebase-wide quality pass (this milestone):** ran `ruff` for the first time (not previously available in the sandbox). Applied safe modernizations tree-wide — `typing.List/Dict/Tuple/Optional/Union` → builtin generics and `X | None` (verified against the 3.10 floor; all tests green), raw-string regex patterns in tests, and minor nits. Set ruff `target-version = py310` and `line-length = 120` (a deliberate project-standard width suited to this explainability-heavy code, avoiding low-value wrapping churn). `ruff check src tests` now passes clean. `mypy` could not run — v2.3.0 in the sandbox crashes with an INTERNAL ERROR on any input (tooling bug); strict typing remains configured for `domain`/`config` and should be verified on the owner's machine.

Validation checklist 1–10 passed; frozen contracts unchanged; no ADR; no drift; no tech debt.

---

## Phase 6 — Reporting, Dashboards & User Intelligence (in progress)

### P6.7 — Unified Intelligence Workspace

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Read-only unified intelligence composition workspace orchestrating query lookups, artifact filtering, and consolidated snapshots across all Phase 6 intelligence artifacts |
| Tests | 669 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — Phase 6 completed; Phase 7 blocked until approved |
| Branch | main |

Built the Unified Intelligence Workspace (`src/athena/workspace/`), which answers one question: "How can all immutable ATHENA intelligence artifacts be accessed through a single, unified, read-only interface?" `UnifiedIntelligenceWorkspace` provides a consolidated view across 6 canonical workspace views (`REPORT`, `DASHBOARD`, `EXPLAINABILITY`, `TIMELINE`, `MONITORING`, `EXPORT`) into `WorkspaceSnapshot`s. It **aggregates and organizes information only**: it performs no state mutation, no user authentication, no REST APIs, no Web/Desktop/Mobile UI rendering, and no market analysis.

Workspace features: `assemble_workspace(reports=None, dashboard_snapshot=None, explanation_snapshot=None, timeline_snapshot=None, monitoring_snapshot=None, export_snapshot=None, *, as_of)` aggregates all Phase 6 intelligence artifacts into cataloged `WorkspaceEntry` records, provides deterministic filtering (`filter_by_type()`), identifier lookup (`find_by_id()`), and a high-level `WorkspaceSummary`. All outputs (`WorkspaceEntry`, `WorkspaceSummary`, `WorkspaceSnapshot`, `WorkspaceHistory`) are immutable and preserve full `WorkspaceReferences` back to originating platform artifacts (`report_id`, `dashboard_snapshot_id`, `explanation_snapshot_id`, `timeline_snapshot_id`, `monitoring_snapshot_id`, `export_snapshot_id`).

Files created: `src/athena/workspace/{__init__,models,engine}.py`, `config/workspace.json`, `tests/runtime/test_workspace.py`. Files modified: `src/athena/errors.py` (+`WorkspaceError`), `src/athena/config/{models,loader,__init__}.py` (+`WorkspaceConfig`, `load_workspace_config`, exports). No analytical engine, export engine, monitoring engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `UnifiedIntelligenceWorkspace`, `WorkspaceEntry`, `WorkspaceSummary`, `WorkspaceSnapshot`, `WorkspaceHistory`, `WorkspaceReferences`, `WorkspaceConfig`, `load_workspace_config`. 12 new tests: workspace assembly across all 6 Phase 6 artifact types, filtering by artifact type, lookup by ID, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming all Phase 6 intelligence artifacts. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.6 — Export & Presentation Layer

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Presentation format transformation (JSON, Markdown, Text, CSV) for immutable platform artifacts; pure presentation adapter |
| Tests | 657 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Export & Presentation Layer (`src/athena/export/`), which answers one question: "How can immutable ATHENA artifacts be exported and presented in standardized formats without changing their meaning or contents?" `ExportPresentationEngine` transforms immutable platform artifacts into 4 canonical presentation formats (`ExportFormat`: `JSON`, `MARKDOWN`, `TEXT`, `CSV`). It **transforms representations only**: it performs no state mutation, no PDF rendering, no REST endpoints, no file upload services, and no market analysis.

Export features: `export_report()`, `export_dashboard()`, `export_explanation()`, `export_timeline()`, `export_monitoring()`, and `create_snapshot(exports, *, as_of)`. Standardized format rendering ensures deterministic payloads, content-type mapping (`application/json`, `text/markdown`, `text/plain`, `text/csv`), and standardized extension generation (`.json`, `.md`, `.txt`, `.csv`). All outputs (`ExportRequest`, `ExportArtifact`, `ExportSummary`, `ExportSnapshot`, `ExportHistory`) are immutable and preserve full `ExportReferences` back to originating platform artifacts (`report_id`, `dashboard_snapshot_id`, `explanation_snapshot_id`, `timeline_snapshot_id`, `monitoring_snapshot_id`).

Files created: `src/athena/export/{__init__,models,engine}.py`, `config/export.json`, `tests/runtime/test_export.py`. Files modified: `src/athena/errors.py` (+`ExportError`), `src/athena/config/{models,loader,__init__}.py` (+`ExportConfig`, `ExportFormat`, `load_export_config`, exports). No analytical engine, monitoring engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ExportPresentationEngine`, `ExportRequest`, `ExportArtifact`, `ExportSummary`, `ExportSnapshot`, `ExportHistory`, `ExportReferences`, `ExportFormat`, `ExportConfig`, `load_export_config`. 12 new tests: export generation across all 4 canonical formats, format-specific content-type verification, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming Reporting, Dashboard, Explainability, Timeline, and Monitoring artifacts across all 4 formats. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.5 — Operational Monitoring

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Operational health snapshot generation and component monitoring across 10 platform domains; read-only health observation only |
| Tests | 645 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Operational Monitoring Engine (`src/athena/monitoring/`), which answers one question: "What is the current operational health of ATHENA and are all platform components functioning correctly?" `OperationalMonitoringEngine` evaluates platform health across 10 canonical domains (`MonitoringDomain`: `SCHEDULER`, `WORKFLOW`, `PORTFOLIO`, `EXECUTION`, `ANALYTICS`, `REPORTING`, `DASHBOARD`, `EXPLAINABILITY`, `TIMELINE`, `OVERALL`). It **observes operational health only**: it performs no state mutation, no live polling, no alert delivery, no Prometheus/Grafana integration, and no market analysis.

Monitoring features: `evaluate_health(schedule_execution=None, workflow=None, portfolio_snapshot=None, execution_state=None, performance_snapshot=None, reports=None, dashboard_snapshot=None, explanation_snapshot=None, timeline_snapshot=None, *, as_of)` aggregates component status, detects missing/stale artifacts, and computes overall platform health (`HEALTHY`, `DEGRADED`, `CRITICAL`). All outputs (`MonitoringCheck`, `MonitoringSummary`, `MonitoringSnapshot`, `MonitoringHistory`) are immutable and preserve full `MonitoringReferences` back to originating platform artifacts across every layer.

Files created: `src/athena/monitoring/{__init__,models,engine}.py`, `config/monitoring.json`, `tests/runtime/test_monitoring.py`. Files modified: `src/athena/errors.py` (+`MonitoringError`), `src/athena/config/{models,loader,__init__}.py` (+`MonitoringConfig`, `MonitoringDomain`, `load_monitoring_config`, exports). No analytical engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OperationalMonitoringEngine`, `MonitoringCheck`, `MonitoringSummary`, `MonitoringSnapshot`, `MonitoringHistory`, `MonitoringReferences`, `MonitoringDomain`, `MonitoringConfig`, `load_monitoring_config`. 12 new tests: component health check aggregation across 10 domains, missing artifact detection, overall status calculation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting, Dashboard, Explainability, and Timeline engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.4 — Timeline & Audit Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Chronological timeline reconstruction and audit stream generation across 11 platform domains; read-only reconstruction only |
| Tests | 633 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Timeline & Audit Engine (`src/athena/timeline/`), which answers one question: "What happened across the complete ATHENA pipeline, in what order, and how can every platform event be reconstructed?" `TimelineAuditEngine` reconstructs chronological timelines across 11 canonical domains (`TimelineDomain`: `DECISION`, `PORTFOLIO`, `ALLOCATION`, `SIZING`, `ORDER_PLANNING`, `BROKER_TRANSLATION`, `LIFECYCLE`, `ANALYTICS`, `REPORTING`, `DASHBOARD`, `EXPLAINABILITY`). It **reconstructs immutable history only**: it performs no state mutation, no live streaming, no distributed tracing, and no market analysis.

Timeline features: `build_timeline(decisions=None, portfolio_snapshot=None, allocation_plan=None, sizing_plan=None, execution_plan=None, broker_plan=None, execution_state=None, performance_snapshot=None, reports=None, dashboard_snapshot=None, explanation_snapshot=None, *, as_of)` extracts, sorts, and sequence-numbers platform events into causally ordered `AuditEntry` records inside a `TimelineSnapshot`. All outputs (`TimelineEvent`, `AuditEntry`, `TimelineSummary`, `TimelineSnapshot`, `TimelineHistory`) are immutable and preserve full `TimelineReferences` back to all originating platform artifacts across every layer.

Files created: `src/athena/timeline/{__init__,models,engine}.py`, `config/timeline.json`, `tests/runtime/test_timeline.py`. Files modified: `src/athena/errors.py` (+`TimelineAuditError`), `src/athena/config/{models,loader,__init__}.py` (+`TimelineConfig`, `TimelineDomain`, `load_timeline_config`, exports). No analytical engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `TimelineAuditEngine`, `TimelineEvent`, `AuditEntry`, `TimelineSummary`, `TimelineSnapshot`, `TimelineHistory`, `TimelineReferences`, `TimelineDomain`, `TimelineConfig`, `load_timeline_config`. 12 new tests: timeline building across 11 domains, strict 1-indexed sequence numbering, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting, Dashboard, and Explainability engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.3 — Explainability Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic human-readable explanation generator explaining why decisions, allocations, sizing, execution plans, lifecycle outcomes, and analytics were produced; rationale only |
| Tests | 621 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Explainability Engine (`src/athena/explainability/`), which answers one question: "Why did ATHENA produce this decision, allocation, position size, execution plan, lifecycle outcome, or analytical result?" `ExplainabilityEngine` generates deterministic, human-readable explanations across 9 canonical domains (`ExplanationDomain`: `DECISION`, `PORTFOLIO`, `ALLOCATION`, `SIZING`, `ORDER_PLANNING`, `BROKER_TRANSLATION`, `LIFECYCLE`, `ANALYTICS`, `REPORTING`). It **explains existing platform outcomes only**: it performs no state mutation, no decision altering, no LLM generation, and no market analysis.

Explainability features: `explain_decision()`, `explain_portfolio()`, `explain_allocation()`, `explain_sizing()`, `explain_order_planning()`, `explain_broker_translation()`, `explain_lifecycle()`, `explain_analytics()`, `explain_reporting()`, and `create_snapshot(explanations, *, as_of)`. All outputs (`ExplanationSection`, `Explanation`, `ExplanationSnapshot`, `ExplanationHistory`) are immutable and preserve full `ExplanationReferences` back to `decision_id`, `portfolio_snapshot_id`, `allocation_plan_id`, `position_sizing_plan_id`, `execution_plan_id`, `broker_execution_plan_id`, `execution_state_id`, `performance_snapshot_id`, `report_id`, and `schedule_execution_id`.

Files created: `src/athena/explainability/{__init__,models,engine}.py`, `config/explainability.json`, `tests/runtime/test_explainability.py`. Files modified: `src/athena/errors.py` (+`ExplainabilityError`), `src/athena/config/{models,loader,__init__}.py` (+`ExplainabilityConfig`, `ExplanationDomain`, `load_explainability_config`, exports). No analytical engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ExplainabilityEngine`, `ExplanationSection`, `Explanation`, `ExplanationSnapshot`, `ExplanationHistory`, `ExplanationReferences`, `ExplanationDomain`, `ExplainabilityConfig`, `load_explainability_config`. 12 new tests: explanation generation across all 9 canonical domains, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting and Dashboard engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.2 — Dashboard & Snapshot Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Derived, read-only operational dashboard snapshots aggregating platform status, portfolio health, execution progress, and analytics; presentation layer only |
| Tests | 609 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Dashboard & Snapshot Engine (`src/athena/dashboard/`), which answers one question: "Given the current immutable platform artifacts, what is the current operational view of ATHENA?" `DashboardEngine` aggregates platform status across 9 canonical sections (`Portfolio Overview`, `Capital Allocation Overview`, `Active Positions`, `Execution Status`, `Order Lifecycle Summary`, `Portfolio Performance`, `Risk & Exposure Summary`, `Reporting Status`, `Platform Health`) into `DashboardSnapshot`s. It **presents derived operational views only**: it performs no state mutation, no UI rendering, no live polling, and no market analysis.

Dashboard features: `create_snapshot(portfolio_snapshot=None, allocation_plan=None, execution_state=None, performance_snapshot=None, reports=None, *, as_of)` aggregates available platform artifacts into modular `DashboardSection`s and a high-level `DashboardSummary`. All outputs (`DashboardSection`, `DashboardSummary`, `DashboardSnapshot`, `DashboardHistory`) are immutable and preserve full `DashboardReferences` back to `portfolio_snapshot_id`, `performance_snapshot_id`, `execution_state_id`, `allocation_plan_id`, `report_id`, and `schedule_execution_id`.

Files created: `src/athena/dashboard/{__init__,models,engine}.py`, `config/dashboard.json`, `tests/runtime/test_dashboard.py`. Files modified: `src/athena/errors.py` (+`DashboardError`), `src/athena/config/{models,loader,__init__}.py` (+`DashboardConfig`, `load_dashboard_config`, exports). No analytical engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `DashboardEngine`, `DashboardSection`, `DashboardSummary`, `DashboardSnapshot`, `DashboardHistory`, `DashboardReferences`, `DashboardConfig`, `load_dashboard_config`. 12 new tests: dashboard snapshot creation with all sections, partial artifact handling, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming real artifacts from Phase 5 execution pipeline and Reporting Framework. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.1 — Reporting Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Generic operational reporting engine generating immutable, structured machine-readable and human-readable reports from platform artifacts; read-only |
| Tests | 597 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Reporting Framework (`src/athena/reporting/`), which answers one question: "Given ATHENA's completed artifacts from Phases 1–5, how can we produce generic, immutable, human-readable and structured operational reports?" `ReportingEngine` consumes immutable platform artifacts (`PortfolioSnapshot`, `ExecutionState`, `AllocationPlan`, `PerformanceSnapshot`, audit events) to produce `GenericReport`s. It **presents and formats information only**: it performs no state mutation, no order execution, no analytical calculation, and no market analysis.

Supported report types: `ReportType` (`PORTFOLIO`, `EXECUTION`, `ALLOCATION`, `ANALYTICS`, `AUDIT`). Report generation operations: `generate_portfolio_report(portfolio_snapshot, *, as_of)`, `generate_execution_report(execution_state, *, as_of)`, `generate_allocation_report(allocation_plan, *, as_of)`, `generate_analytics_report(performance_snapshot, *, as_of)`, `generate_audit_report(run_id, events, *, as_of)`. All reports provide dual presentation views (`to_dict()` machine-readable view and `to_text()` human-readable summary view). All outputs (`GenericReport`, `ReportingReferences`, `ReportingHistory`) are immutable and preserve full `ReportingReferences` back to `portfolio_snapshot_id`, `execution_state_id`, `allocation_plan_id`, `performance_snapshot_id`, `audit_id`, and `schedule_execution_id`.

Files modified: `src/athena/reporting/{__init__,models,engine}.py` (added `ReportingEngine`, `GenericReport`, `ReportingReferences`, `ReportingHistory` while preserving M3.7 `DecisionReportingEngine` & `DecisionReport` intact), `config/reporting.json`, `tests/runtime/test_reporting_framework.py`. Files modified: `src/athena/errors.py` (+`ReportingError`), `src/athena/config/{models,loader,__init__}.py` (+`ReportingFrameworkConfig`, `ReportType`, `load_reporting_framework_config`, exports). No analytical engine, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ReportingEngine`, `GenericReport`, `ReportingReferences`, `ReportingHistory`, `ReportType`, `ReportingFrameworkConfig`, `load_reporting_framework_config`. 12 new tests: portfolio report generation, execution report generation, allocation report generation, analytics report generation, audit report generation, machine/text rendering verification, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming real artifacts across all Phases 1–5. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

---

## Phase 5 — Portfolio & Execution Platform (COMPLETED)

### P5.7 — Portfolio Analytics & Performance

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Computes portfolio returns, realized/unrealized P&L, exposures, win/loss stats, and drawdowns; performance calculation only |
| Tests | 585 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Portfolio Analytics Engine (`src/athena/analytics/portfolio/`), which answers one question: "Given completed portfolio activity and execution history, how has the portfolio performed?" `PortfolioAnalyticsEngine` consumes `PortfolioSnapshot`s and `ExecutionState`s to compute comprehensive performance metrics (`PortfolioPerformance`, `TradePerformance`, `AnalyticsSummary`, `PerformanceSnapshot`). It **computes performance metrics and analytics only**: it performs no investment decision making, no capital allocation, no position sizing, no order planning, no broker communication, and no execution state modification.

Core performance metrics & analytics: Realized P&L, unrealized P&L, total P&L, total return %, portfolio valuation, peak portfolio value, drawdown, drawdown %, max drawdown %, gross exposure, net exposure, cash utilization %, trade-level win/loss classification, win rate %, average gain, average loss, win/loss ratio, and average holding period (days). Analytics operations: `analyze(portfolio_snapshot, execution_state=None, current_prices=None, *, as_of)` processes portfolio state deterministically. All outputs (`TradePerformance`, `PortfolioPerformance`, `AnalyticsSummary`, `PerformanceSnapshot`, `PortfolioAnalyticsHistory`) are immutable and preserve full `PortfolioAnalyticsReferences` back to `execution_state_id`, `broker_execution_plan_id`, `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/analytics/portfolio/{__init__,models,engine}.py`, `config/portfolio_analytics.json`, `tests/runtime/test_portfolio_analytics.py`. Files modified: `src/athena/errors.py` (+`PortfolioAnalyticsError`), `src/athena/config/{models,loader,__init__}.py` (+`PortfolioAnalyticsConfig`, `load_portfolio_analytics_config`, exports). No analytical engine, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PortfolioAnalyticsEngine`, `TradePerformance`, `PortfolioPerformance`, `AnalyticsSummary`, `PerformanceSnapshot`, `PortfolioAnalyticsHistory`, `PortfolioAnalyticsReferences`, `PortfolioAnalyticsConfig`, `load_portfolio_analytics_config`. 12 new tests: unrealized P&L & valuation, win/loss accounting & realized P&L, drawdown calculation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative initial capital rejection, production config loading), and an **end-to-end integration test** consuming real outputs from the entire Phase 5 pipeline (`PortfolioEngine` → `CapitalAllocationEngine` → `PositionSizingEngine` → `OrderPlanningEngine` → `BrokerManager` → `OrderLifecycleEngine` → `PortfolioAnalyticsEngine`). ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.6 — Order Lifecycle Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Tracks order lifecycle states, validates legal state transitions, and records execution history; execution state model only |
| Tests | 573 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Order Lifecycle Engine (`src/athena/execution/`), which answers one question: "What is the current lifecycle state of every planned order from creation until completion or cancellation?" `OrderLifecycleEngine` consumes `BrokerExecutionPlan`s and tracks order state transitions (`OrderLifecycleState`: `CREATED`, `ACCEPTED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELLED`, `REJECTED`, `EXPIRED`). It **tracks execution state transitions only**: it performs no live broker polling, no WebSockets/REST communication, no exchange connectivity, and no market analysis.

State machine & transition features: Enforces strict legal state transition graph (e.g. `CREATED` → `SUBMITTED` → `PARTIALLY_FILLED` → `FILLED`); illegal transitions (e.g. `CREATED` → `FILLED`, or transitioning out of terminal states `FILLED`/`CANCELLED`/`REJECTED`/`EXPIRED`) fail loudly with `LifecycleError`. Accumulates fill quantities and calculates weighted average fill price (`avg_fill_price`). Auto-promotes `PARTIALLY_FILLED` to `FILLED` when 100% of target quantity is filled. All outputs (`ExecutionEvent`, `OrderLifecycle`, `LifecycleSummary`, `ExecutionState`, `LifecycleHistory`) are immutable and preserve full `ExecutionReferences` back to `broker_execution_plan_id`, `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/execution/{__init__,models,engine}.py`, `config/execution.json`, `tests/runtime/test_execution.py`. Files modified: `src/athena/errors.py` (+`LifecycleError`), `src/athena/config/{models,loader,__init__}.py` (+`ExecutionConfig`, `OrderLifecycleState`, `load_execution_config`, exports). No analytical engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OrderLifecycleEngine`, `OrderLifecycle`, `ExecutionEvent`, `ExecutionState`, `LifecycleSummary`, `LifecycleHistory`, `ExecutionReferences`, `OrderLifecycleState`, `ExecutionConfig`, `load_execution_config`. 12 new tests: legal state transitions, illegal transition rejection, terminal state protection, partial fills & weighted average price, cancellation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming a real `BrokerExecutionPlan` from `BrokerManager`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.5 — Broker Abstraction Layer

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Canonical broker contracts, capability validation, and translation from broker-neutral execution plans into broker requests; contract definition only |
| Tests | 561 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Broker Abstraction Layer (`src/athena/brokers/`), which answers one question: "How can ATHENA communicate with different brokers through a single canonical interface?" `BrokerManager` registers broker contract definitions (`BrokerDefinition`, `BrokerCapabilities`) and translates broker-neutral `ExecutionPlan`s into canonical `BrokerExecutionPlan`s containing `BrokerRequest`s. It **defines contracts and validates capabilities only**: it performs no network communication, no OAuth flows, no REST/WebSocket clients, and no live order submission.

Capability validation & contract features: `BrokerCapabilities` enforces supported order types (`OrderType`), fractional trading support (`supports_fractional`), shorting support (`supports_shorting`), and supported time-in-force policies (`TimeInForce`: `DAY`, `IOC`, `FOK`, `GTC`). Translation operations: `translate_plan(execution_plan, broker_id=None, *, as_of, time_in_force=None)` validates broker availability and capabilities, mapping planned orders into canonical `BrokerRequest`s (`ACCEPTED`, `REJECTED_UNSUPPORTED_ORDER_TYPE`, `REJECTED_UNSUPPORTED_FRACTIONAL`, `SKIPPED_HOLD`); `create_mock_response` generates abstract `BrokerResponse` artifacts for contract testing. All outputs (`BrokerDefinition`, `BrokerCapabilities`, `BrokerRequest`, `BrokerResponse`, `BrokerExecutionPlan`, `BrokerSummary`, `BrokerHistory`) are immutable and preserve full `BrokerReferences` back to `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/brokers/{__init__,models,engine}.py`, `config/brokers.json`, `tests/runtime/test_brokers.py`. Files modified: `src/athena/errors.py` (+`BrokerError`), `src/athena/config/{models,loader,__init__}.py` (+`BrokerConfig`, `TimeInForce`, `load_broker_config`, exports). No analytical engine, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `BrokerManager`, `BrokerDefinition`, `BrokerCapabilities`, `BrokerRequest`, `BrokerResponse`, `BrokerExecutionPlan`, `BrokerSummary`, `BrokerHistory`, `BrokerReferences`, `TimeInForce`, `BrokerConfig`, `load_broker_config`. 12 new tests: canonical translation, unsupported order type rejection, unsupported fractional quantity rejection, unsupported time-in-force error, mock response creation, unregistered & disabled broker handling, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming a real `ExecutionPlan` from `OrderPlanningEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.4 — Order Planning Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Transforms position sizes into broker-neutral execution instructions and batches; execution plan generation only |
| Tests | 549 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Order Planning Engine (`src/athena/orders/`), which answers one question: "Given approved position sizes, what broker-neutral execution instructions should ATHENA prepare?" `OrderPlanningEngine` converts `PositionSizingPlan` outputs into broker-neutral `ExecutionPlan`s composed of `PlannedOrder`s grouped into `ExecutionBatch`es. It **prepares execution instructions only**: it performs no broker communication, no live order placement, no order fill tracking, and no market analysis.

Supported order actions & instruction types: `OrderAction` (`BUY`, `SELL`, `HOLD`) and `OrderType` (`MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`). Planning operations: `plan_execution(sizing_plan, *, as_of, decisions=None, order_type=None)` processes all position sizes in deterministic sorted order; `create_order(instrument_id, action, quantity, *, as_of, order_type=None, limit_price=None, stop_price=None)` creates a single explicit instruction. Batching policy (`batch_by_action`, `max_orders_per_batch`) groups planned orders into deterministic action batches (e.g. `BUY` batch, `SELL` batch) and chunks larger sets. Zero-quantity or `ZERO_ALLOCATION` items automatically generate `OrderAction.HOLD` instructions. All outputs (`PlannedOrder`, `OrderInstruction`, `ExecutionBatch`, `ExecutionPlan`, `OrderPlanningSummary`, `OrderPlanningHistory`) are immutable and preserve full `OrderReferences` back to `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/orders/{__init__,models,engine}.py`, `config/orders.json`, `tests/runtime/test_orders.py`. Files modified: `src/athena/errors.py` (+`OrderPlanningError`), `src/athena/config/{models,loader,__init__}.py` (+`OrderPlanningConfig`, `OrderAction`, `OrderType`, `load_order_planning_config`, exports). No analytical engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OrderPlanningEngine`, `PlannedOrder`, `OrderInstruction`, `ExecutionBatch`, `ExecutionPlan`, `OrderPlanningSummary`, `OrderPlanningHistory`, `OrderReferences`, `OrderAction`, `OrderType`, `OrderPlanningConfig`, `load_order_planning_config`. 12 new tests: BUY planning, SELL planning, HOLD handling, MARKET & LIMIT order types, action batching & chunking, single order creation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (positive batch size enforcement, production config loading), and an **end-to-end integration test** consuming a real `PositionSizingPlan` from `PositionSizingEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.3 — Position Sizing Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Converts approved capital allocations into executable share/unit quantities with rounding & precision policy; quantity calculation only |
| Tests | 537 passed / 0 failed (13 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Position Sizing Engine (`src/athena/sizing/`), which answers one question: "Given an approved capital allocation, how many units of the instrument should ATHENA purchase or sell?" `PositionSizingEngine` converts allocated capital amounts from an `AllocationPlan` into executable unit quantities based on instrument prices. It **calculates unit quantities only**: it performs no market analysis, no capital allocation policy decisions, no risk limit checks, and no order placement.

Supported sizing models & rounding policies: `WHOLE_SHARE` (integer share quantities via `int(raw_qty)`) and `FRACTIONAL` (decimal unit quantities up to configured `decimal_precision`, default 4 decimal places), combined with `ROUND_DOWN` (floor / conservative sizing ensuring cost <= allocation) or `ROUND_UP` (ceiling sizing). Sizing operations: `size_plan(allocation_plan, prices, *, as_of, model=None, rounding=None)` processes all allocations in deterministic sorted order; `size_amount(allocated_amount, unit_price, instrument_id, *, as_of)` calculates single-opportunity quantity. Zero-allocation items get `status="ZERO_ALLOCATION"`, `quantity=0`; missing or non-positive price items get `status="REJECTED_ZERO_PRICE"`, `quantity=0`. All outputs (`PositionSize`, `PositionSizingPlan`, `PositionSizingSummary`, `PositionSizingHistory`) are immutable and preserve full `SizingReferences` back to `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/sizing/{__init__,models,engine}.py`, `config/sizing.json`, `tests/runtime/test_sizing.py`. Files modified: `src/athena/errors.py` (+`SizingError`), `src/athena/config/{models,loader,__init__}.py` (+`SizingConfig`, `SizingModel`, `RoundingMode`, `load_sizing_config`, exports). No analytical engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PositionSizingEngine`, `PositionSize`, `PositionSizingDecision`, `PositionSizingPlan`, `PositionSizingSummary`, `PositionSizingHistory`, `SizingReferences`, `SizingModel`, `RoundingMode`, `SizingConfig`, `load_sizing_config`. 13 new tests: whole-share sizing with round down & round up, fractional unit sizing with precision, zero-allocation handling, missing price handling, single-amount sizing, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative precision rejection, production config loading), and an **end-to-end integration test** consuming a real `AllocationPlan` from `CapitalAllocationEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.2 — Capital Allocation Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Policy-driven capital allocation per approved opportunity; enforces reserve floors and allocation models without position sizing or order execution |
| Tests | 524 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Capital Allocation Engine (`src/athena/allocation/`), which answers one question: "How much capital should be reserved for each approved investment opportunity?" `CapitalAllocationEngine` evaluates available portfolio capital from a `PortfolioSnapshot` and allocates capital to candidate opportunities according to policy. It **determines capital allocation policy only**: it performs no market analysis, no position sizing (shares calculation), no risk limit checks, and no order execution.

Supported allocation models: `FIXED_AMOUNT` (configured fixed INR amount per opportunity), `FIXED_PERCENTAGE` (configured percentage of total portfolio cash), and `EQUAL_WEIGHT` (equal division of the allocatable pool among active candidates up to `max_opportunities`). Minimum cash reserve floor (`min_cash_reserve_pct`, default 20%) is strictly enforced before any allocation occurs (`allocatable_pool = max(0, available_cash - min_reserve_floor)`). Candidate opportunities (filtered for `TRADE` / `INCREASE_POSITION` decision types) are processed in deterministic sorted order. If remaining allocatable cash is less than target, a `status="PARTIAL"` allocation is issued; if pool is exhausted, `status="REJECTED_INSUFFICIENT_CASH"` or `REJECTED_RESERVE_FLOOR` is returned. Opportunities beyond `max_opportunities` are rejected as `REJECTED_MAX_OPPORTUNITIES`. `allocate_amount` provides explicit single-opportunity allocation. All outputs (`CapitalAllocation`, `AllocationPlan`, `AllocationSummary`, `AllocationHistory`) are immutable and preserve full `AllocationReferences` back to `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/allocation/{__init__,models,engine}.py`, `config/allocation.json`, `tests/runtime/test_allocation.py`. Files modified: `src/athena/errors.py` (+`AllocationError`), `src/athena/config/{models,loader,__init__}.py` (+`AllocationConfig`, `AllocationModel`, `load_allocation_config`, exports). No analytical engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `CapitalAllocationEngine`, `CapitalAllocation`, `AllocationDecision`, `AllocationPlan`, `AllocationSummary`, `AllocationHistory`, `AllocationReferences`, `AllocationModel`, `AllocationConfig`, `load_allocation_config`. 12 new tests: fixed percentage allocation, fixed amount allocation, equal weight allocation, cash reserve threshold enforcement, max opportunities limit, partial & rejected statuses, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative values rejection, production config loading), and an **end-to-end integration test** consuming a real `PortfolioSnapshot` from `PortfolioEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.1 — Portfolio Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic portfolio state management, holdings, cash allocation, reserved capital, closed positions, and append-only history; state tracking only |
| Tests | 512 passed / 0 failed (18 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Portfolio Engine (`src/athena/portfolio/`), which answers one question: "Given ATHENA's completed investment decisions, what should the portfolio currently own?" `PortfolioEngine` manages portfolio state, active holdings, available cash, reserved capital, realized/closed positions, and append-only history. It **records state only**: it performs no market analysis, no position sizing calculations, no risk limit checks, and no order execution; it consumes completed `Decision` artifacts produced by the operational pipeline and maintains deterministic portfolio ledger state.

State operations: `open_position` (creates holding, allocates cash), `increase_position` (recomputes quantity & average price), `reduce_position` (reduces holding quantity, releases cost & records proceeds), `close_position` (removes holding, records immutable `ClosedPosition`, releases cash), `hold_position` (updates last-seen timestamp), `reserve_capital` / `release_capital` (allocates/frees reserved cash), and `apply_decision` (convenience mapper dispatching `open`, `increase`, `reduce`, `close`, or `hold` based on `DecisionType` and existing holdings). All operations return immutable `PortfolioSnapshot` objects referencing originating `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`. `PortfolioHistory` is **append-only** (`record()` returns a new history). Cash accounting enforces strict invariants (`total_cash == available + allocated + reserved`). Backdated operations, duplicate holdings on open, over-reduction, and cash deficits fail loudly with `PortfolioError`.

Files created: `src/athena/portfolio/{__init__,models,engine}.py`, `config/portfolio.json`, `tests/runtime/test_portfolio.py`. Files modified: `src/athena/errors.py` (+`PortfolioError`), `src/athena/config/{models,loader,__init__}.py` (+`PortfolioConfig`, `load_portfolio_config`, exports). No analytical engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PortfolioEngine`, `Portfolio`, `PortfolioSnapshot`, `Holding`, `ClosedPosition`, `CashBalance`, `ReservedCapital`, `PortfolioReferences`, `PortfolioSummary`, `PortfolioHistory`, `PortfolioConfig`, `load_portfolio_config`. 18 new tests: open/increase/reduce/close/hold operations, capital reservation & release, `apply_decision` with TRADE & FULL_EXIT decisions, duplicate holding protection, insufficient cash handling, backdated timestamp rejection, deterministic replay (`to_dict` and `to_json` equality), immutable snapshots (`FrozenInstanceError`), append-only history, config validation (negative cash rejection, production config loading), and an **end-to-end integration test** consuming the completed operational pipeline via `SchedulingFramework`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

---

## Phase 4 — Orchestration & Operational Intelligence (APPROVED)

### M4.7 — Scheduling Framework (completes Phase 4)

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic execution coordination over the completed pipeline; schedules and records when ATHENA runs without changing how ATHENA analyzes markets |
| Tests | 494 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed (completes Phase 4) |
| Branch | main |

Built the Scheduling Framework (`src/athena/scheduling/`), which answers one question: "When should ATHENA execute its existing operational pipeline?" `SchedulingFramework` coordinates the execution of existing operational components — the M4.1 `WorkflowEngine`, M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, M4.4 `StrategyFramework`, M4.5 `BacktestingEngine`, and M4.6 `ReportingAnalyticsEngine`. It **coordinates execution only**: it invokes no analytical engine directly, evaluates no strategy rules, derives no market intelligence, and modifies no completed decision.

Two execution paths: `execute(definition, *, as_of, pipeline_builder, universe, previous_watchlist=None)` runs the full daily pipeline (scanner → watchlist → strategy → analytics), returning an immutable `ScheduleExecution` referencing every upstream artifact (`scan_id`, `watchlist_snapshot_id`, `strategy_execution_id`, `analytics_report_id`); `execute_replay(definition, *, as_of, replay_points)` runs the replay pipeline (backtester → analytics), returning a `ScheduleExecution` referencing `backtest_run_id` and `analytics_report_id`. Five deterministic scheduling modes supported: `MANUAL`, `DAILY`, `WEEKLY`, `REPLAY`, `ONE_TIME`. Scheduling policies are configuration-driven (`config/scheduling.json`, `record_history` toggle). `ScheduleHistory` is **append-only** (`record()` returns a new history). **Failure isolation**: any pipeline or replay exception is caught, recorded as `ExecutionStatus.FAILED` with a diagnostic note, and never crashes the framework. Determinism: with `as_of` injected and no clock read for business decisions (monotonic clock used for duration measurement only), identical inputs produce identical execution records (verified). Disabled definitions are rejected loudly before execution.

Files created: `src/athena/scheduling/{__init__,models,engine}.py`, `config/scheduling.json`, `tests/runtime/test_scheduling.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `SchedulingConfig`, `load_scheduling_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `SchedulingFramework`, `ScheduleDefinition`, `ScheduledJob`, `ScheduleExecution`, `ExecutionReferences`, `ScheduleHistory`, `ScheduleSummary`, `ScheduleMode`, `SchedulingConfig`, `load_scheduling_config`. 21 new tests: full pipeline manual execution (all artifact references preserved), recurring schedules (daily/weekly/one-time modes), replay schedule execution (backtest + analytics references, execute() rejection of REPLAY mode), chronological execution ordering in history, deterministic rerun (`to_dict` equality), immutable outputs (`FrozenInstanceError` on execution and history), history filtering by definition and mode, summary generation, record_history disabled toggle, disabled definition rejection, failure isolation (BrokenScanner recorded as FAILED), config validation (unknown-key rejection, production config loads, missing fails loudly), and a **real end-to-end scheduled execution** through the full M4.1→M4.6 operational pipeline across three instruments. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### M4.6 — Reporting & Analytics

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic operational summaries and analytical statistics aggregated from completed artifacts; presentation + aggregation only |
| Tests | 473 passed / 0 failed (14 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Reporting & Analytics layer (`src/athena/analytics/`), which answers operational questions — "What happened today?", "How many instruments matched each strategy?", "How did decisions distribute across the universe?", "What activity occurred during replay?" — purely by aggregating completed artifacts from the M4.2 scanner, M4.3 watchlist manager, M4.4 strategy framework, and M4.5 backtester. `ReportingAnalyticsEngine` is **presentation + aggregation only**: it invokes no analytical engine, derives no new market intelligence, and modifies no completed decision. Every metric is a count or roll-up of an existing immutable artifact, and every report preserves references back to its sources.

Two entry points: `daily_report(scan_report, *, as_of, watchlist=None, strategy_execution=None)` produces a `kind="daily"` `AnalyticsReport` embedding `DailyAnalytics` (decision distribution taken from the scan's own summary; scan success/fail/skip counts; confidence and risk **level distributions** aggregated from completed decision reports; optional `WatchlistAnalytics` and `StrategyAnalytics`); `backtest_report(run, *, as_of)` produces a `kind="replay"` report embedding `BacktestAnalytics` (step counts, replay coverage, decision distribution summed across every replayed scan, and per-strategy match/instrument roll-ups from the run's performance). Confidence/risk distributions honour config: `confidence_levels`/`risk_levels` fix display order and `include_unknown` toggles the UNKNOWN bucket. Determinism: all inputs are immutable, no clock is read (`as_of` injected), distributions are built in fixed config-driven order, and `to_json()` emits sorted-key output — identical inputs yield an identical report (verified). Empty inputs produce empty distributions, not errors.

Files created: `src/athena/analytics/{__init__,models,engine}.py`, `config/analytics.json`, `tests/runtime/test_analytics.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `AnalyticsConfig`, `load_analytics_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, backtesting engine, workflow engine, or frozen-domain type touched. Public APIs added: `ReportingAnalyticsEngine`, `AnalyticsReport`, `DailyAnalytics`, `WatchlistAnalytics`, `StrategyAnalytics`, `BacktestAnalytics`, `AnalyticsSummary`, `AnalyticsConfig`, `load_analytics_config`. 14 new tests: decision/confidence/risk distributions, embedded watchlist+strategy analytics, skipped-count aggregation, include_unknown toggle, empty scan, deterministic replay, immutable report, sorted-JSON serialization, config validation (unknown-key rejection, lowercase-level rejection, production config loads, missing fails loudly), and a real **BacktestRun end-to-end** produced by the M4.5 chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, strategy framework, backtesting engine, workflow engine, and analytical engines all unchanged.

### M4.5 — Backtesting Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic chronological replay of the existing operational pipeline across historical points, with no alternate analytical logic |
| Tests | 459 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Backtesting Engine (`src/athena/backtest/`), which answers one question: "How would ATHENA's completed analytical pipeline and strategy framework have behaved across historical market snapshots?" `BacktestingEngine.run(points, *, run_id=None)` replays a chronological sequence of caller-supplied `ReplayPoint`s (each a timezone-aware `as_of`, a universe, and the per-instrument pipeline builder for that date — identical in shape to what the live scanner consumes) through the **existing** operational components: the M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, and M4.4 `StrategyFramework` (which in turn run the M4.1 `WorkflowEngine` and the analytical core). It **orchestrates only** — it introduces no alternate analytical logic, computes no market values, and replays the same deterministic pipeline used live; the analytical core stays the single source of truth. Out-of-scope items (portfolio valuation, P&L, sizing, brokerage/slippage/cost simulation, order execution) are deliberately absent.

Each replay point produces an immutable `BacktestStep` referencing the artifacts the real pipeline emitted — scan id, watchlist snapshot id, strategy execution id, replay date, and execution timestamp — and retaining the full `DailyScanReport`, `WatchlistSnapshot`, and `StrategyExecution` for complete history preservation. Watchlist state **threads forward** chronologically (per `carry_watchlist` config) so trend-based watchlists and strategies observe prior scans exactly as they would live. Steps run in strict chronological order (sorted by `as_of`; duplicate timestamps fail loudly). **Failure isolation**: any step whose scan/apply/execute raises is recorded `FAILED` with a diagnostic note; with `continue_on_error` the replay proceeds (and a failed step does not advance carried state), otherwise it stops. Results aggregate into a `BacktestRun` (run identity + period + `BacktestSession`) carrying a `BacktestSummary` with sum-checked step counts and per-strategy `StrategyPerformance` (total matches, steps with matches, distinct instruments) across the whole period. Determinism verified: with `as_of` injected and no clock read, the same dataset yields an identical `to_dict()` on rerun (internal per-stage timings are excluded from serialization).

Files created: `src/athena/backtest/{__init__,models,engine}.py`, `config/backtest.json`, `tests/runtime/test_backtest.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `BacktestConfig`, `load_backtest_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, workflow engine, or frozen-domain type touched. Public APIs added: `BacktestingEngine`, `ReplayPoint`, `BacktestStep`, `BacktestSession`, `BacktestRun`, `BacktestSummary`, `StrategyPerformance`, `BacktestConfig`, `load_backtest_config`. 19 new tests: chronological ordering (incl. out-of-order input), all-steps-completed, step references, watchlist carry-forward (and disabled), multi-strategy performance aggregation, partial-failure isolation, stop-on-error, failed-step-doesn't-advance-state, deterministic rerun, empty dataset, immutable run, duplicate-replay-point rejection, history preservation, config validation (defaults, unknown-key rejection, production config loads, missing fails loudly), and a three-day **end-to-end replay** through the real workflow → scanner → watchlist → strategy chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; workflow engine, scanner, watchlist manager, strategy framework, and analytical engines all unchanged.

### M4.4 — Strategy Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic framework for multiple strategies to select completed decision artifacts by policy, without any analytical calculation |
| Tests | 440 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Strategy Framework (`src/athena/strategy/`), which answers one question: "Which completed ATHENA decisions satisfy each strategy's deterministic selection policy?" `StrategyFramework.execute(scan_report, watchlist, *, as_of)` runs every registered strategy over the immutable outputs of the M4.2 scanner (`DailyScanReport` → `DecisionReport`) and M4.3 watchlist manager (`WatchlistSnapshot`), producing an immutable `StrategyExecution`. It **coordinates strategy evaluation only** — it parses completed decision artifacts into read-only views, invokes each strategy, and aggregates; it never invokes an analytical engine, computes an indicator, or reinterprets a decision. Strategies express *selection*, not intelligence.

The `Strategy` contract (`base.py`) is a small ABC declaring `name`, `version`, `description`, and a pure `select(views) -> tuple[MatchProposal, ...]`. Each strategy sees only `InstrumentView`s — a pre-parsed, read-only lens bundling one instrument's completed decision facts (type, direction, and the score/confidence/risk values *already produced* by the core, read as-is, UNKNOWN preserved as `None`) with its current watchlist memberships. Five reference strategies (Momentum, Swing, Breakout, Mean Reversion, Sector Rotation) share a `ConfigurableStrategy` base that applies declarative `StrategyRuleCfg` filters (decision set, direction, watchlist overlap, min score, min confidence, max risk). A threshold set against an UNKNOWN value never matches — missing analytical values exclude an instrument rather than being defaulted (no fabrication). Multiple strategies may select the same instrument; overlaps are surfaced in the summary.

Determinism: instruments are viewed in stable sorted order, strategies run in registration order (and `from_config` registers enabled reference strategies in id-sorted order), and matches are ordered by instrument — with `as_of` injected and no clock read, identical inputs yield an identical `StrategyExecution` (verified via `to_dict` replay equality). Each `StrategyMatch` records the instrument, originating decision id, originating watchlist memberships, a strategy-specific explanation, and supporting references (decision id, scan id, watchlist snapshot id, and the score/confidence/risk refs lifted faithfully from the decision report). Duplicate strategy registration and unknown reference-strategy ids fail loudly; failed/skipped scan results are ignored.

Files created: `src/athena/strategy/{__init__,models,base,strategies,framework}.py`, `config/strategy.json`, `tests/runtime/test_strategy.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `StrategyConfig` + `StrategyRuleCfg`, `load_strategy_config`, exports). No analytical engine, scanner, watchlist manager, workflow engine, or frozen-domain type touched. Public APIs added: `StrategyFramework`, `Strategy`, `InstrumentView`, `MatchProposal`, `StrategyMatch`, `StrategyResult`, `StrategySummary`, `StrategyExecution`, the five reference strategies + `ConfigurableStrategy` + `REFERENCE_STRATEGIES`, `StrategyConfig`, `load_strategy_config`. 19 new tests: multiple strategies, overlapping matches, no matches, UNKNOWN-value exclusion, failed-results ignored, explanation + references preservation, registration, duplicate-registration rejection, `from_config` enabled-only + unknown-id rejection, deterministic replay, immutable output, empty universe, config validation (unknown decision, unknown direction, empty strategies, production config loads, missing config fails loudly), and a **real chain** consuming a scanner-produced `DailyScanReport` and a watchlist-manager-produced `WatchlistSnapshot`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, workflow engine, and analytical engines all unchanged.

### M4.3 — Watchlist Manager

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Maintain deterministic, explainable named watchlists derived exclusively from completed scan/decision artifacts |
| Tests | 421 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Watchlist Manager (`src/athena/watchlist/`), which answers one question: "Which instruments deserve ongoing attention based on ATHENA's completed decisions?" `WatchlistManager.apply(scan_report, *, as_of, previous=None)` folds an immutable `DailyScanReport` (M4.2) into a new immutable `WatchlistSnapshot`. It **coordinates state only** — it never executes an analytical engine, never recalculates a decision, and never invents a conclusion; it reads only the completed decision outcomes already produced by the pipeline and scanner, and organises them into named watchlists.

Classification is entirely **configuration-driven** (`config/watchlist.json`, validated by `WatchlistConfig`). Two rule kinds cover the initial five watchlists: a `decision_in` rule (membership when the instrument's current decision type is in a configured set — **High Conviction** ← TRADE/INCREASE_POSITION, **Watch** ← WATCH/WAIT, **Rejected** ← NO_TRADE/AVOID_SECTOR) and a `trend` rule (membership by change in decision *strength* versus the previous scan, using a configurable `decision_rank` map — **Improving** when the rank rose, **Weakening** when it fell). An instrument may belong to several watchlists at once (e.g. both High Conviction and Improving).

`apply` is a **pure function** of `(config, previous, scan_report, as_of)`: no hidden state, no clock read (`as_of` injected), instruments processed in stable sorted order — so replaying the same scan sequence yields bit-identical snapshots (verified). Every membership change is recorded as an explained `WatchlistChange` (ADDED / RETAINED / REMOVED) stating *why the instrument entered, why it remained, or why it exited* (rule no longer satisfied, or absent from the current scan). `entered_as_of` is preserved across retentions so an entry's original entry time is never lost. `WatchlistHistory` is **append-only** — `record()` returns a new, extended history and never overwrites prior state. Failed/skipped scan results are ignored (only completed decisions classify); a scan report containing a duplicate instrument fails loudly.

Files created: `src/athena/watchlist/{__init__,models,manager}.py`, `config/watchlist.json`, `tests/runtime/test_watchlist.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `WatchlistConfig` + rule models, `load_watchlist_config`, exports). No analytical engine, scanner, workflow engine, or frozen-domain type touched. Public APIs added: `WatchlistManager`, `WatchlistSnapshot`, `WatchlistEntry`, `WatchlistChange`, `WatchlistChangeType`, `WatchlistHistory`, `WatchlistSummary`, `WatchlistConfig`, `load_watchlist_config`. 21 new tests: decision-in classification, multi-watchlist membership, additions/retention/removal (rule-lapse and absence), improving/weakening trends, no-trend-without-prior, append-only history + entry/exit explanation, deterministic replay, immutable snapshots, empty scan (and empty-scan removals), duplicate-instrument protection, failed/skipped results ignored, config validation (duplicate names, unknown decision, production config loads, missing config fails loudly), and a **real DailyScanReport** produced by the M4.2 scanner classified across two cycles. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, workflow engine, and analytical engines all unchanged.

### M4.2 — Daily Market Scanner

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Coordinate ATHENA's full analytical workflow across the approved universe into one immutable daily scan report |
| Tests | 400 passed / 0 failed (10 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Daily Market Scanner (`src/athena/scanner/`), which answers a single question: "What does ATHENA conclude today for every eligible instrument?" `DailyMarketScanner.scan(universe, *, as_of, pipeline_builder)` iterates the universe in **stable sorted order** (`sorted(set(universe))` — deterministic, deduplicated), asks the caller-supplied `pipeline_builder` for a per-instrument `InstrumentPlan`, executes that plan's `WorkflowDefinition` through the shared `WorkflowEngine`, and — after the workflow completes — reads the captured `ScanCapture` and renders a `DecisionReport` via the existing `DecisionReportingEngine`. It **coordinates only**: it reuses M4.1's engine and M3.7's reporting engine, invokes analytical engines exclusively inside workflow stages defined by the caller, and recalculates nothing.

The design challenge was that M4.1's `WorkflowExecution` (frozen, approved) does not surface the `DecisionOutcome`. Rather than modify the approved engine (which would need an ADR), the scanner uses a **capture pattern**: `InstrumentPlan` pairs the workflow definition with a `collect()` callable; workflow stages populate a closure, and the scanner calls `collect()` after `execute()` to retrieve the outcome. No M4.1 change, no frozen-domain change.

**Failure isolation** is total — every per-instrument step (build, execute, collect, report) is wrapped so one instrument's failure produces a `FAILED` result with a diagnostic note and never aborts the scan; a builder returning `None` yields `SKIPPED`. Results aggregate into an immutable `DailyScanReport` with `ScanStatistics` (sum-checked total/successful/failed/skipped) and a `ScanSummary` (decision-type distribution, frozen via `MappingProxyType`), plus `result_for()` lookup and a JSON-safe `to_dict()`. Determinism verified: two scanners under fixed clocks produce bit-identical `to_dict()`.

Files created: `src/athena/scanner/{__init__,models,scanner.py}`, `tests/runtime/test_scanner.py`. Files modified: none (pure addition; no engine or contract touched). Public APIs added: `DailyMarketScanner`, `DailyScanReport`, `InstrumentPlan`, `InstrumentScanResult`, `ScanCapture`, `ScanStatistics`, `ScanSummary`, `PipelineBuilder`. 10 new tests: multi-instrument scan, deterministic ordering, empty universe, partial-failure isolation, skipped instrument, failed result carries no report, replay determinism, immutability, `to_dict` shape, and a **real multi-instrument pipeline** wiring indicator → regime → scoring → decision engines through workflows. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed.

### M4.1 — Workflow Orchestration Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic central orchestrator that runs analytical engines as coordinated pipeline stages |
| Tests | 390 passed / 0 failed (17 new) |
| Status | **APPROVED** — orchestration foundation for Phase 4 |
| Branch | main |

Built the runtime orchestration layer (`src/athena/runtime/`, realizing the blueprint's reserved §2 `runtime` module — building the plan, not a new module). `WorkflowEngine` executes a `WorkflowDefinition` (a validated DAG of `WorkflowStage`s) in a deterministic topological order, passing a read-only `WorkflowContext` accumulator through the stages; each stage's callable invokes an existing analytical engine and returns named outputs the engine merges (collisions rejected). It **coordinates only** — performs no analysis, duplicates no engine logic, modifies no engine. Dependency validation rejects missing dependencies, cycles, and duplicate stage names up front (`WorkflowError`). Failure isolation: a failed stage is recorded with its error and its downstream dependents are SKIPPED, while independent branches still run. Timing is captured per stage (offset + duration) via an **injected clock**, so under a fixed clock an execution is bit-identical — replay determinism verified. Produces an immutable `WorkflowExecution` (the execution report) plus a presentation-only `WorkflowReport` (`to_dict`/`to_json`/`to_text`). Verified end-to-end by wiring the real indicator → regime → scoring → decision engines as stages — the orchestrator ran the full pipeline without duplicating any engine.

Runtime types live in `src/athena/runtime/` — the blueprint's planned orchestration module — no ADR, no frozen-domain change, no analytical engine touched. Files created: `src/athena/runtime/{__init__,models,workflow,report}.py`, `tests/runtime/test_workflow.py`. Files modified: `src/athena/errors.py` (+WorkflowError). Public APIs added: `WorkflowEngine`, `WorkflowDefinition`, `WorkflowStage`, `WorkflowContext`, `WorkflowExecution`, `WorkflowReport`, `StageResult`, `ExecutionStatus`, `build_definition`. ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence (COMPLETE — pending formal review)

### M3.7 — Decision Trace & Reporting  (completes Phase 3)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Presentation-only human- and machine-readable decision reports from immutable artifacts |
| Tests | 373 passed / 0 failed (11 new) |
| Status | **Awaiting owner approval** — closes Phase 3; Phase 4 blocked pending full Phase-3 review |
| Branch | main |

Built `DecisionReportingEngine` (`src/athena/reporting/`), completing Phase 3. It consumes a `DecisionOutcome` plus the source artifacts (scoring, confidence, risk, evidence bundle, indicators) and produces an immutable `DecisionReport` offering two views derived from the same source: `to_dict()`/`to_json()` (machine-readable, JSON-safe, sorted-key deterministic) and `to_text()` (human-readable, sectioned). The report faithfully mirrors the decision — decision summary/outcome/status/direction, trade-plan summary, all six gate results, score summary with component breakdown, confidence dimensions, risk dimensions, evidence summary (provenance + missing sources), indicator summary, full reasoning-stage trace, and referenced artifact ids. Presentation only: it never modifies, reinterprets, or recalculates any artifact, and adds no new conclusions. UNKNOWN is displayed explicitly for every absent artifact (verified on the INSUFFICIENT_DATA path). Pure and deterministic: no I/O, clock, or randomness; both views reproducible.

Report types live in `src/athena/reporting/` (not frozen domain §4) — no ADR. Files created: `src/athena/reporting/{__init__,models,engine}.py`, `tests/decision/test_reporting.py`. No config needed. Public APIs added: `DecisionReportingEngine.report`, `DecisionReport` (`to_dict`, `to_json`, `to_text`). Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence: COMPLETE (pending formal review)

All seven milestones implemented and individually reviewed: M3.1 Evidence Aggregation, M3.2 Indicator Engine, M3.3 Scoring, M3.4 Confidence, M3.5 Risk, M3.6 Decision, M3.7 Reporting. ATHENA now runs a complete, end-to-end, evidence-first decision pipeline: canonical data → market intelligence → aggregated evidence → objective indicators → transparent scores → confidence → risk → gated, auditable decisions → faithful human/machine reports. Every decision is deterministic, replayable, and traceable back to explicit evidence, measurements, and configuration; the frozen-domain TRADE invariant is enforced at construction. 373 tests, ruff-clean, zero technical debt. Ready for full Phase-3 review before Phase 4 is authorized.

---

### M3.6 — Decision Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First deterministic, auditable decisions combining scores + confidence + risk via config-driven gates |
| Tests | 362 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — M3.7 (Decision Trace & Reporting) blocked until approved |
| Branch | main |

Built `DecisionEngine` (`src/athena/decision/`), the capstone that combines the analytical pipeline into the first explainable decisions. It consumes approved artifacts only (ScoringResult, ConfidenceAssessment, RiskAssessment, EvidenceBundle, RegimeResult, indicators, optional market/sector health) and produces the **frozen-domain** `Decision` + `DecisionTrace` wrapped in a `DecisionOutcome`. It evaluates all six §8.5 quality gates (DATA, EVIDENCE, RISK, EXPLAINABILITY, CONFIDENCE, MARKET) as `GateResult`s, then applies config-driven policy: TRADE (all gates pass + composite ≥ trade threshold + directional regime + buildable plan), WATCH (composite in watch band), NO_TRADE (below watch), or INSUFFICIENT_DATA (no composite). Every frozen invariant is honored — a TRADE always carries a `TradePlan`, a direction, and zero failed gates (verified end-to-end: a strong-bull pipeline yields TRADE with all six gates green). Trade plans use analytical levels only (last close ± ATR multiples for stop/target, constant risk-reward); `position_size` is a provisional unit — **no capital-based sizing** (deferred to the capital layer). The `DecisionTrace` records the full reasoning path (regime → market/sector health → evidence → score → confidence → risk → decision → trade_plan) with references. Pure and replayable: injected `as_of`, Decimal math, thresholds from `decision.json`; consumes approved artifacts, never recalculates lower layers or touches providers/repositories.

Engine + `DecisionOutcome` live in `src/athena/decision/` (the frozen `Decision`/`DecisionTrace` come from `athena.domain.decision` — no §4 change) — no ADR. Files created: `src/athena/decision/{__init__,models,engine}.py`, `config/decision.json`, `tests/decision/test_decision.py`. Files modified: `config/models.py` (+DecisionConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_decision_config). Public APIs added: `DecisionEngine.decide`, `DecisionOutcome`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.5 — Risk Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic descriptive exposure assessment across six independent risk dimensions |
| Tests | 350 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M3.6 (Decision Engine) blocked until approved |
| Branch | main |

Built `RiskEngine` (`src/athena/risk/`). It consumes approved artifacts only and produces an immutable `RiskAssessment` of six independently explainable dimensions (higher value = more risk), each degrading to explicit `UNKNOWN`: volatility risk (regime volatility label), liquidity risk (Volume MA vs configured minimum), gap risk (regime gap label), event risk (CalendarContext expiries/scheduled events), market-environment risk (market-health labels mapped to risk points, averaged), and a concentration indicator (investable-universe breadth). Each dimension carries `RiskContribution` traces and a LOW/MEDIUM/HIGH level; the overall risk is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Risk measures exposure only — independent of opportunity, and never a recommendation or position size. Missing artifacts produce transparent UNKNOWN; nothing is fabricated. Pure and replayable: injected `as_of`, Decimal math, all point maps from `risk_assessment.json` (a new file, kept separate from the F-4 no-trade rules in `risk.json`). Consumes approved artifacts, never providers/repositories.

Result types in `src/athena/risk/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/risk/{__init__,models,engine}.py`, `config/risk_assessment.json`, `tests/decision/test_risk.py`. Files modified: `config/models.py` (+RiskAssessmentConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_risk_assessment_config). Public APIs added: `RiskEngine.assess`, `RiskAssessment`, `RiskDimension`, `RiskContribution`, `RiskLevel`, `RiskStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.4 — Confidence Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic evaluation-reliability assessment across six independent confidence dimensions |
| Tests | 334 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M3.5 (Risk Engine) blocked until approved |
| Branch | main |

Built `ConfidenceEngine` (`src/athena/confidence/`). It consumes approved artifacts only — EvidenceBundle, ScoringResult, IndicatorResults — and produces an immutable `ConfidenceAssessment` of six independently explainable dimensions, each degrading to explicit `UNKNOWN`: evidence completeness (present vs required sources), data freshness (validation reports passed vs total), indicator availability (OK vs total), cross-engine agreement (dispersion of known component scores), unknown ratio (share of known artifacts), and consistency (absence of contradictory signals among known scores, config divergence gap). Each dimension carries `ConfidenceContribution` traces and a LOW/MEDIUM/HIGH level; the overall confidence is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Confidence measures evaluation reliability only — never market direction, attractiveness, or risk. Missing artifacts transparently reduce confidence; nothing is fabricated or inferred. Pure and replayable: injected `as_of`, Decimal math, thresholds/weights from `confidence.json`; consumes approved artifacts, never providers/repositories.

Result types in `src/athena/confidence/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/confidence/{__init__,models,engine}.py`, `config/confidence.json`, `tests/decision/test_confidence.py`. Files modified: `config/models.py` (+ConfidenceConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_confidence_config). Public APIs added: `ConfidenceEngine.assess`, `ConfidenceAssessment`, `ConfidenceDimension`, `ConfidenceContribution`, `ConfidenceLevel`, `ConfidenceStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.3 — Scoring Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Transparent, config-driven component + composite scores from approved evidence and indicators |
| Tests | 317 passed / 0 failed (18 new) |
| Status | **Awaiting owner approval** — M3.4 (Confidence Engine) blocked until approved |
| Branch | main |

Built `ScoringEngine` (`src/athena/scoring/`). It consumes approved artifacts only — regime, market-health, sector-health assessments and `IndicatorResult`s — and produces six independent `ComponentScore`s (trend, momentum, market quality, sector quality, liquidity, technical structure), each 0–100 with a full `Contribution` trace referencing the exact regime/health dimension, indicator, and configured point value behind it, plus a plain-language explanation. A `CompositeScore` weights the known components (config weights sum to 100) and retains a complete `CompositeBreakdownItem` breakdown including each component's weight, value, and weighted contribution, with a `completeness` ratio. UNKNOWN propagation is strict: any missing evidence/indicator yields an explicit UNKNOWN component (no value, no fabricated default), unscoreable dimensions are excluded from averages, and the composite is UNKNOWN only when nothing is scoreable. Scores are intermediate artifacts — no buy/sell/hold, sizing, risk, or portfolio logic. Pure and replayable: injected `as_of`, Decimal math, all point maps from `scoring.json`; consumes approved artifacts, never raw providers/repositories.

Result types in `src/athena/scoring/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/scoring/{__init__,models,engine}.py`, `config/scoring.json`, `tests/decision/test_scoring.py`. Files modified: `config/models.py` (+ScoringConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_scoring_config). Public APIs added: `ScoringEngine.score`, `ScoringResult`, `ComponentScore`, `CompositeScore`, `CompositeBreakdownItem`, `Contribution`, `ScoreStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.2 — Indicator Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic technical-indicator measurement layer over canonical candles |
| Tests | 299 passed / 0 failed (26 new) |
| Status | **Awaiting owner approval** — M3.3 (Scoring Engine) blocked until approved |
| Branch | main |

Built `IndicatorEngine` (`src/athena/indicators/`) computing SMA, EMA, RSI (Wilder), ATR (Wilder), MACD, ADX (Wilder), and Volume MA from canonical candle data. Parameters are configuration-driven (`indicators.json`, extended with sma/macd/adx/volume_ma); calculations are pure Decimal functions in `calculations.py`; each result is an immutable `IndicatorResult` carrying name, status, parameters, window used, value(s), `IndicatorEvidence` (formula + inputs + explanation), and tz-aware ts. Insufficient history yields an explicit `UNKNOWN` result with no values (never a fabricated number). Strictly measurement-only — no signals, crossovers-as-events, composites, scoring, or interpretation; results never imply bullish/bearish/strength/weakness. Pure and replayable: injected `as_of`, deterministic Decimal math (fixed 28-digit context), candles sorted; provider/repository/intelligence-independent.

Result types in `src/athena/indicators/models.py` (measurement types, not frozen domain §4) — no ADR. Files created: `src/athena/indicators/{__init__,models,calculations,engine}.py`, `tests/decision/test_indicators.py`. Files modified: `config/indicators.json` (added sma/macd/adx/volume_ma params + versions; ema now single-period). Public APIs added: `IndicatorEngine.compute` / `compute_all`, `IndicatorName`, `IndicatorStatus`, `IndicatorResult`, `IndicatorEvidence`. Tests validate exact SMA/Volume-MA values, RSI boundaries (all-gains→100, all-losses→0, alternating≈50), ATR/MACD zero on flat/constant series, ADX range, Decimal precision, UNKNOWN handling, determinism, and immutability. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.1 — Evidence Aggregation Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Gather all approved intelligence into a single immutable, provenance-tagged evidence graph |
| Tests | 273 passed / 0 failed (10 new) |
| Status | **Awaiting owner approval** — M3.2 (Indicator Engine) blocked until approved |
| Branch | main |

Built `EvidenceAggregationEngine` (`src/athena/evidence/`), the first Decision Intelligence module. It gathers approved intelligence — regime, market health, sector health, universe, corporate-action evidence, and validation reports — into a single immutable `EvidenceBundle` of provenance-tagged `EvidenceItem`s. Each item records its `source`, `kind`, `reference_id`, timezone-aware `ts`, explanation, and the original (frozen) intelligence object as `payload` — so nothing is transformed or lost; provenance is preserved verbatim. The engine detects missing required sources (`required_sources` → `missing_sources`, `is_complete`) and publishes a per-source provenance count. Aggregation only — no scoring, signals, decisions, or transformation. Pure and replayable: injected `as_of`, deterministic fixed source ordering (sectors sorted), no I/O/clock/randomness; `EvidenceBundle` exposes `by_source`, `has_source`, `present_sources`.

Result types in `src/athena/evidence/models.py` (decision-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/evidence/{__init__,models,engine}.py`, `tests/decision/test_evidence_aggregation.py`. Public APIs added: `EvidenceAggregationEngine.aggregate`, `EvidenceBundle`, `EvidenceItem`, `EvidenceSource`. All prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence (COMPLETE — pending formal review)

### M2.4 — Universe Engine  (completes Phase 2)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic investable-universe construction via config-driven eligibility rules + constituent-breadth export |
| Tests | 263 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — closes Phase 2; Phase 3 blocked pending full Phase-2 review |
| Branch | main |

Built `UniverseEngine` (`src/athena/universe/`). It evaluates each instrument independently against configuration-driven eligibility rules — active status, supported series, eligible exchange, data present, minimum trading history, minimum liquidity, and (when a calendar + window are supplied) data completeness — producing an immutable per-instrument `UniverseAssessment` (inclusion status, exclusion reasons, per-rule `RuleEvidence`, eligibility summary) and the frozen-domain `Universe` of included members (each with a full inclusion trace). Missing datasets produce explicit evidence, never silent exclusion. It also publishes **constituent advances/declines per sector** as a canonical output (`constituent_breadth`), completing the data dependency anticipated by Sector Health (M2.3) — computed from included instruments' latest vs prior close, and never by calling the Sector Health Engine. `max_universe_size` is advisory only (a hard cap would require ranking, which is out of scope) — all eligible instruments are included and the cap is surfaced in the summary. Pure and replayable (injected `as_of`, Decimal math, thresholds from `universe.json`); eligibility-focused, no ranking/scoring/selection.

Result types in `src/athena/universe/models.py` + `UniverseResult` in engine (not frozen domain §4; the canonical included set uses the frozen `Universe`/`UniverseMember`) — no ADR. Files created: `src/athena/universe/{__init__,models,engine}.py`, `tests/market_intel/test_universe.py`. Files modified: `config/models.py` (UniverseConfig +eligibility fields), `config/universe.json`. Public APIs added: `UniverseEngine.build`, `UniverseResult`, `UniverseAssessment`, `RuleEvidence`. Regime, Market Health, Sector Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence: COMPLETE (pending formal review)

All four milestones implemented and individually reviewed: M2.1 Regime Engine, M2.2 Market Health, M2.3 Sector Health, M2.4 Universe Engine. The Market Intelligence layer now describes market conditions (regime, market health), sector conditions (sector health), and constructs a trustworthy investable universe — all deterministic, explainable, replayable, and strictly descriptive/eligibility-focused (no scoring, ranking, or decisions). Engines consume canonical data + approved intelligence and are aware-but-not-dependent on one another. 263 tests, ruff-clean, zero technical debt. Ready for full Phase-2 review before Phase 3 (Decision Intelligence) is authorized.

---

### M2.3 — Sector Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive per-sector condition across four independently explainable dimensions |
| Tests | 246 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M2.4 (Universe Engine) blocked until approved |
| Branch | main |

Built `SectorHealthEngine` (`src/athena/sector_health/`). Per sector it consumes canonical sector-index `Candle` history (plus optional constituent breadth) and produces an immutable `SectorHealthAssessment` of four independently explainable dimensions, each degrading to explicit `*_UNKNOWN`: **trend** (fast/slow SMA → UPTREND/DOWNTREND/SIDEWAYS), **breadth** (constituent participation — reported `SECTOR_BREADTH_UNKNOWN` unless constituent advances/declines are supplied; never inferred, since constituent data arrives with M2.4), **momentum** (period ROC), and **volatility** (realized volatility = stdev of returns, a sector-specific context that complements — not duplicates — Market Health). `assess_many` evaluates multiple sectors deterministically. Every dimension emits `SectorHealthEvidence` with inputs, thresholds, outcome, and explanation. Pure and replayable (injected `as_of`, Decimal math incl. `Decimal.sqrt`, thresholds from `sector_health.json`); descriptive only — no ranking, rotation, selection, or signals. Regime-aware and Market-Health-aware but dependent on neither (optional, explanation-only).

Result types in `src/athena/sector_health/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/sector_health/{__init__,models,engine}.py`, `config/sector_health.json`, `tests/market_intel/test_sector_health.py`. Files modified: `config/models.py` (+SectorHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_sector_health_config). Public APIs added: `SectorHealthEngine.assess` / `assess_many`, `SectorHealthResult`, `SectorHealthAssessment`, `SectorHealthEvidence`, `SectorHealthLabel`, `SectorHealthConfig`, `load_sector_health_config`. Regime, Market Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.2 — Market Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive assessment of overall market condition across four independently explainable dimensions |
| Tests | 223 passed / 0 failed (24 new) |
| Status | **Awaiting owner approval** — M2.3 (Sector Health) blocked until approved |
| Branch | main |

Built `MarketHealthEngine` (`src/athena/market_health/`). It consumes canonical `Candle` history + optional `MarketSnapshot`, and produces an immutable `MarketHealthAssessment` composed of four independently explainable dimensions, each always labelled (explicit `*_UNKNOWN` on insufficient data): **breadth** (advance ratio from snapshot advances/declines), **trend quality** (one-directional consistency of recent index returns — complements the Regime Engine's direction, does not replace it), **momentum** (period rate-of-change of the index), and **volatility** (contextual read of India VIX on market stability, framed as health not re-classification). Every dimension emits `HealthEvidence` carrying inputs, the thresholds that produced the label (owner suggestion #3), the outcome, and a human explanation. Pure and replayable (injected `as_of`, Decimal math, thresholds from `market_health.json`); descriptive only — no scores, rankings, or recommendations. Regime-aware but not regime-dependent: an optional `RegimeResult` enriches the trend-quality explanation only; labels are identical with or without it (verified by test).

Result types live in `src/athena/market_health/models.py` (market-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/market_health/{__init__,models,engine}.py`, `config/market_health.json`, `tests/market_intel/test_market_health.py`. Files modified: `config/models.py` (+MarketHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_market_health_config). Public APIs added: `MarketHealthEngine.assess`, `MarketHealthResult`, `MarketHealthAssessment`, `HealthEvidence`, `MarketHealthLabel`, `MarketHealthConfig`, `load_market_health_config`. Regime Engine and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.1 — Regime Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic market-regime classification from canonical market data; descriptive, not prescriptive |
| Tests | 199 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M2.2 (Market Health) blocked until approved |
| Branch | main |

Built `RegimeEngine` (`src/athena/regime/`), the first Market Intelligence module. It consumes canonical `Candle` history (an index) plus an optional `MarketSnapshot` (India VIX) and produces the frozen-domain `RegimeAssessment` plus a supporting `RegimeEvidence` chain. Three orthogonal, deterministic dimensions, each always labelled (explicit `*_UNKNOWN` when data is insufficient — never a silent omission): **trend** (BULL/BEAR/SIDEWAYS via fast-vs-slow SMA and last close), **volatility** (HIGH/LOW/NORMAL via India VIX against configured bands), and **gap** (UP/DOWN/NONE via latest open vs prior close against the gap threshold). Pure and replayable: no I/O, no clock reads (time injected as `as_of`), no randomness; Decimal math throughout; thresholds from the existing `regime.json`. Output is strictly descriptive — labels, evidence, and explanation only; no scoring, ranking, or recommendation.

Regime result types live in `src/athena/regime/models.py` (market-intelligence types, not additions to frozen domain §4, which already provides `RegimeAssessment`) — no ADR required. Files created: `src/athena/regime/{__init__,models,engine}.py`, `tests/market_intel/test_regime.py`. Public APIs added: `RegimeEngine.assess`, `RegimeResult`, `RegimeEvidence`, `RegimeLabel`. Validation checklist passed; frozen contracts unchanged; ruff clean; no drift; no tech debt.

---

## Phase 1 — Data Foundation: COMPLETE ✅ (approved 2026-07-20)

All six milestones implemented and individually reviewed: M1.1 provider contracts, M1.2 FileProvider, M1.3 validation layer, M1.4 corporate actions, M1.5 SQLite repository, M1.6 backup & restore. The data foundation now ingests (via an abstract, order-incapable provider), validates, historically adjusts, persists, and recovers canonical market data — deterministically, explainably, and replayably. 182 tests, ruff-clean. **Phase 1 approved; Phase 2 (Market Intelligence) authorized.**

---

### M1.5 — SQLite Repository

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Persistent storage layer: schema, repository, WAL/FK config, integrity verification, quarantine + corporate-action persistence |
| Tests | 171 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M1.6 (backup & restore) blocked until approved |
| Branch | main |

Built `SqliteRepository`, ATHENA's persistent ledger. Deterministic schema (ATHENA-002 §5) with a single `candles` table keyed by (instrument_id, timeframe, ts_open) serving both daily and intraday, plus `instruments`, `quotes`, `market_snapshots`, `corporate_actions`, `quarantine_records`, and a `schema_version` table for future migrations. Explicit primary keys, foreign keys, and a range index; all decimals/timestamps stored as TEXT (ISO-8601, tz-aware) to preserve exact precision. SQLite configured with WAL mode and enforced foreign keys per connection; writes wrapped in transactions with a public `transaction()` context manager (commit on success, rollback on exception). Repository returns canonical domain objects, never rows — no provider, validation, or intelligence logic lives here. Append-only history (duplicate primary keys rejected as `RepositoryError`); instruments and quarantine support idempotent upsert. `verify_integrity()` runs `PRAGMA integrity_check` + `PRAGMA foreign_key_check` + schema-version check and returns an immutable `IntegrityReport`; corrupt/non-SQLite files fail loudly. Quarantine persistence serializes/restores `QuarantineRecord`s with full validation evidence, timestamps, types, severities, and explanations.

Storage types live in `src/athena/data/store/` — §5 schema is not among the §19-frozen items, and the milestone checklist confirms no ADR — so schema evolution is allowed within the data module. Files created: `src/athena/data/store/{__init__,schema,serialization,repository}.py`, `tests/data_layer/test_repository.py`. Files modified: `src/athena/errors.py` (+RepositoryError), `.gitignore` (WAL sidecars + db/). Public APIs added: `SqliteRepository` (initialize, upsert_instrument, get_instrument, list_instruments, add_candles, get_candles, add_quotes, get_quotes, add_snapshot, get_latest_snapshot, add_corporate_action, get_corporate_actions, save_quarantine, get_quarantine, list_quarantine, verify_integrity, transaction, close), `IntegrityReport`, `SCHEMA_VERSION`. Validation checklist 1–10 passed; provider contract, Validation Layer, and Corporate Actions Engine untouched; no drift; no tech debt.

### M1.4 — Corporate Actions Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider/storage-independent modeling + deterministic back-adjustment for splits, bonuses, dividends, renames |
| Tests | 148 passed / 0 failed (19 new) |
| Status | **Awaiting owner approval** — M1.5 (SQLite repository) blocked until approved |
| Branch | main |

Built a Corporate Actions Engine that interprets the canonical (frozen) `CorporateAction` domain object into validated typed actions (`Split`, `Bonus`, `Dividend`, `Rename`) and applies deterministic back-adjustment to candle datasets, producing **adjusted copies** with full evidence — originals are never mutated (and `Candle` is frozen regardless). Standard model: an action with ex_date D adjusts only candles strictly before D; split from→to scales price by from/to and volume by to/from; bonus b:h scales price by h/(h+b); dividend scales price by (prev_close − amount)/prev_close using the raw close before D; factors are cumulative across sequential actions; renames map identifiers (with chain resolution A→B→C) and never touch candle values. Four explicit, traceable strategies (RAW, SPLIT_ADJUSTED, SPLIT_BONUS_ADJUSTED, FULLY_ADJUSTED) — no hidden behavior. Every adjustment emits immutable `AdjustmentEvidence` (action, ex_date, price/volume factor, affected record count, explanation, metadata); the whole run returns an immutable `AdjustmentResult`. Deterministic Decimal math (fixed context) and injected `as_of` make it fully replayable. Optional Calendar Engine only annotates whether an ex_date is a trading session — effective dates are never inferred. No fetching, no persistence, no provider/file/SQLite awareness.

Engine types live in `src/athena/data/corporate_actions/` — not additions to the frozen domain §4 — so no ADR was required. Files created: `src/athena/data/corporate_actions/{__init__,models,evidence,engine}.py`, `tests/data_layer/test_corporate_actions.py`. Files modified: `src/athena/errors.py` (+CorporateActionError). Public APIs added: `CorporateActionsEngine` (`adjust`, `build_symbol_map`, `resolve_symbol`), `parse_action`, `Split`/`Bonus`/`Dividend`/`Rename`, `CorporateActionType`, `AdjustmentStrategy`, `AdjustmentEvidence`, `AdjustmentResult`. Validation checklist 1–10 passed; provider contract and Validation Layer untouched; no drift; no tech debt.

### M1.3 — Validation Layer

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider-independent data-quality framework: freshness, OHLC, duplicate, gap validation; immutable reports; quarantine |
| Tests | 129 passed / 0 failed (25 new) |
| Status | **Awaiting owner approval** — M1.4 (corporate actions) blocked until approved |
| Branch | main |

Built a reusable validation framework that operates exclusively on canonical `Candle` objects and the Phase-0 Calendar Engine — no file/SQLite/broker/provider awareness. Validators are pure functions with an injected `as_of` (no clock reads → deterministic and replayable). Freshness compares daily data against the calendar's expected latest trading day and intraday data against the reference time, with configurable thresholds. OHLC validation checks the one business rule the Candle contract does NOT guarantee — strictly positive prices — and explicitly does not re-check H/L ordering (structurally enforced by the domain object) to avoid duplicating provider responsibility. Duplicate detection targets cross-dataset/ingestion-boundary duplicates (provider within-request dedup untouched). Gap detection uses the Calendar Engine for both missing trading sessions (weekends/holidays never counted) and missing intraday intervals; sessions are never inferred manually. Every check produces an immutable `ValidationReport` (type, result, severity, explanation, evidence, statistics, tz-aware timestamp); `DatasetValidator` aggregates into an immutable `ValidationSummary`; `QuarantineRegistry` records invalid datasets with preserved failure evidence and never auto-repairs.

Validation types live in `src/athena/data/validation/` — data-layer result types, NOT additions to the frozen canonical domain model (§4) — so no ADR was required. Files created: `src/athena/data/validation/{__init__,reports,validators,dataset_validator,quarantine,calendar_expectations}.py`, `config/validation.json`, `tests/data_layer/test_validation.py`. Files modified: `config/models.py` (+ValidationConfig/FreshnessConfig/GapConfig), `config/loader.py` + `config/__init__.py` (+load_validation_config). Public APIs added: `DatasetValidator`, `ValidationReport`, `ValidationSummary`, `ValidationType`, `ValidationResult`, `Severity`, `QuarantineRegistry`, `QuarantineRecord`, the five `validate_*` functions, `load_validation_config`, `ValidationConfig`. Validation checklist 1–10 passed; provider contract untouched; no drift; no tech debt.

### M1.2 — FileProvider

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First production `MarketDataProvider`, backed by local CSV/JSON files; reference implementation for all future providers |
| Tests | 104 passed / 0 failed (37 new) |
| Status | **Awaiting owner approval** — M1.3 (validation layer) blocked until approved |
| Branch | main |

Implemented `FileProvider` conforming 100% to the frozen contract (passes the M1.1 suite unchanged). Loads daily candles, intraday candles, instrument metadata, market snapshots, and quotes from configurable file locations (`config/providers/file.json`, loaded via a new `load_file_provider_config` + `FileProviderConfig` model — `AthenaConfig` untouched, so config compatibility is preserved). Deterministic: no caching, no mutable global state, no clock reads, no concurrency; candles sorted ascending and deduplicated to honor the contract. Decimal precision and tz-aware timestamps preserved end to end. Error taxonomy differentiates missing files, invalid format (wrong header), unsupported instrument/timeframe/capability, and corrupted data (non-numeric values, impossible OHLC, naive timestamps, duplicate timestamps) — all `ProviderError` with file:line context. Validation is limited to what loading correctness requires; freshness/gap/cross-dataset validation deferred to M1.3 as instructed.

Files created: `src/athena/data/__init__.py`, `src/athena/data/providers/__init__.py`, `src/athena/data/providers/file_provider.py`, `config/providers/file.json`, two deterministic fixture datasets (`tests/data/fileprovider/` synthetic, `tests/data/fileprovider_sample/` sanitized-realistic with real symbols/ISINs but fictional prices), `tests/contract/test_file_provider_contract.py`, `tests/data_layer/test_file_provider.py`, dataset READMEs. Files modified: `config/models.py` (+FileProviderConfig, ProviderCapabilitiesConfig), `config/loader.py` + `config/__init__.py` (+loader). Public APIs added: `FileProvider`, `FileProvider.from_config_dir`, `load_file_provider_config`, `FileProviderConfig`. Validation checklist 1–10 passed; contract unchanged; no ADR; no drift; no tech debt.

### M1.1 — MarketDataProvider Contracts

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider Protocol behavioral contract, ProviderCapabilities/ProviderHealth invariants, reusable contract test suite |
| Tests | 67 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M1.2 (FileProvider) blocked until approved |
| Branch | main |

Frozen Protocol signatures untouched (contract compatibility preserved). Added: constructor invariants on `ProviderCapabilities` (non-empty unique timeframes, history ≥ 1 day) and `ProviderHealth` (mandatory detail, tz-aware timestamps); a documented behavioral contract on the Protocol (capability honesty, candle ordering/uniqueness/range, emptiness-is-not-error, determinism, unknown-id failures, structurally-forbidden order methods); `tests/contract/provider_contract.py` — the conformance suite every provider (M1.2 FileProvider, future broker adapters per DD-1) must pass unchanged, including a `test_no_order_methods_exist` structural-safety check; proven against a deterministic in-memory `StubProvider` (test infrastructure only, arithmetic data, no randomness/clock reads) plus negative tests showing the suite catches rogue order methods and invalid capabilities. Validation checklist 1–10 passed; no ADR needed; no config changes.

---

## Phase 0 — Foundations

| | |
|---|---|
| Completed | 2026-07-20 |
| Blueprint scope | ATHENA-002 §14, Phase 0 |
| Tests | 51 passed / 0 failed |
| Status | **APPROVED** (owner + principal engineer review passed, 2026-07-20) |
| Branch | main |
| Lessons learned | Phase-sized batches are too large to review well — milestone-based workflow adopted from Phase 1 (see CLAUDE.md, docs/MILESTONES.md) |

### 1. Summary of completed work

Project scaffolding (`pyproject.toml`, `justfile`, `.env.example`); complete canonical domain model; layered configuration framework with strategy profiles, feature flags, and cross-file invariants; JSONL logging with secret redaction and run/cycle correlation; observability skeleton (metric timers, performance-budget violations, system-health pre-flight); Trading Calendar Engine loaded with the real NSE 2026 holiday calendar (16 weekday holidays + Muhurat on 2026-11-08); CLI commands `athena today`, `athena health`, `athena version`.

### 2. Architectural compliance review

All Phase 0 exit criteria pass: CalendarContext correct for the 10 acceptance dates including Republic Day (holiday) and Muhurat (special session overriding a Sunday, timings honestly "TBD" until NSE notifies); config invariant violations fail with readable errors naming field and rule; full suite green. Contracts match the blueprint exactly: PipelineContext enforces consumes/produces discipline (re-producing a key raises, F-1/ADR-003); `MarketDataProvider` Protocol contains no order methods (ADR-002); explanations are constructor-mandatory — a TRADE decision without a TradePlan, without a direction, or with a failed quality gate cannot be instantiated (F-12, ADR-005); prices are Decimal; timestamps are timezone-aware; clocks are injected. No architectural deviations; no ADR was needed.

### 3. Files created

- `src/athena/domain/` — enums, market, evidence, decision, run, health, context, interfaces (8 files)
- `src/athena/config/` — models (pydantic), loader + snapshot hashing (2 files)
- `src/athena/observability/` — logging, metrics, health (3 files)
- `src/athena/calendar/engine.py`, `src/athena/cli.py`, `src/athena/errors.py`
- `config/` — base, market.nse, risk, capital, regime, universe, indicators, profiles/intraday-momentum, calendar/{holidays,expiries,events} (10 files)
- `tests/` — conftest + 5 test modules + golden-dataset skeleton README
- Scaffolding: `pyproject.toml`, `justfile`, `.env.example`

### 4. Tests added (51)

Calendar acceptance (10 parametrized dates, timings, trading-session semantics, budget event, fail-loud on uncovered year, determinism); config (11 cases: invariants, typo rejection, missing file, unknown profile, unversioned indicator, out-of-session trading window, snapshot hash determinism and change-sensitivity); domain invariants (immutability, impossible OHLC, naive timestamps, mandatory explanations, score-breakdown sum, decision contract, context discipline, read-only context data); observability (JSON-line shape, run/cycle correlation, secret redaction, budget violation detection, health pre-flight honest WARNs, calendar-coverage BLOCKED); CLI (5 commands/paths).

### 5. Remaining work

Phase 1 (Data): `MarketDataProvider` contract test suite, FileProvider (EOD bhavcopy + intraday files), validation layer (freshness, OHLC sanity, gaps, duplicates), corporate-actions handling, SQLite store with backup/restore. Owner actions before relying on calendar-aware features: verify `config/calendar/holidays.json` against the NSE circular and set `verified_by_owner: true`; populate `config/calendar/expiries.json` from the current derivatives circular (left empty by design — expiry weekdays change by circular and were not guessed).

### 6. Risks discovered

The AI sandbox cannot delete files, so `athena health` reports storage/logs BLOCKED when run there — the check is working as designed and passes on the owner's machine. The blueprint pins Python ≥ 3.12 but verification ran on 3.10; `pyproject.toml` currently declares ≥ 3.10 — tighten to 3.12 once the production interpreter is confirmed.

### 7. Suggested improvements (implementation-only)

A `just verify-calendar` target that diffs `holidays.json` against the NSE circular each January; a minimal GitHub Actions workflow (ruff + mypy + pytest) once the owner wants CI on pushes.
