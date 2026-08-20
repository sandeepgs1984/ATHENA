# ATHENA & DarvaX Advisory Dashboard UX Roadmap

**Status:** proposed — a menu for the owner to choose from, nothing here is
scheduled or approved. Each item still needs its own Design step before any
implementation, per the standard milestone workflow.  
**Scope:** the advisory experience across both surfaces — ATHENA's own
dashboard and the DarvaX satellite.  
**Owner ask (2026-08-19):** "come up with best trading experience improvements
needed in athena as well as darvax to make advisory dashboard world class and
best user experience, these improvements can be anything!"

## Owner-selected delivery sequence (2026-08-19)

The owner delegated prioritisation and approved the following sequence. This
table is the stable reference for the selected work; the remaining roadmap
ideas stay unscheduled. Only one milestone may be active at a time, and every
transition remains gated by owner review.

| Priority | Milestone | Selected roadmap item | Status |
|---:|---|---|---|
| 1 | **AUX-1a / AUX-1b** | Persistent data-freshness indicator — ATHENA first, then DarvaX | Approved 2026-08-19 |
| 2 | **AUX-2** | Visible last successful cycle and overdue warning | Approved 2026-08-20 |
| 3 | **AUX-3** | Confidence band visible in the Decisions list | Approved 2026-08-20; 2,028 tests pass |
| 4 | **DX-12b** | DarvaX trend badge on Advisor cards and Levels view | Approved 2026-08-20; 2,041 tests pass |
| 5 | **AUX-4a** | ATHENA daily near-miss digest (score-margin) | Approved 2026-08-20; 2,055 tests pass |
| 5b | **AUX-4b** | DarvaX's own near-miss digest | Approved 2026-08-20; 2,069 tests pass |
| 6 | **AUX-5** | ATHENA “My track record” panel | Approved 2026-08-20 |
| 7 | **AUX-4c** | Surface near-miss digests in the dashboard UI (both surfaces) | Ready for review 2026-08-20 |

The persistent-freshness idea is intentionally split. ATHENA consumes
intraday observations and scheduled cycles, while DarvaX presents a daily
sweep with its own `as_of` and completion timestamps. One browser-derived age
rule would mislabel at least one surface. `AUX-1a` and `AUX-1b` therefore share
wording and severity semantics but retain separate authoritative contracts.

Approved AUX-3 design record:
[`ATHENA-DECISION-LIST-CONFIDENCE-DESIGN.md`](ATHENA-DECISION-LIST-CONFIDENCE-DESIGN.md).

DX-12b is next. It must begin with the Design step and remain limited to
displaying already-persisted 50/100 EMA trend context on DarvaX Advisor cards
and the Levels view. It must not alter DarvaX eligibility, tier, action, or
ATHENA decision logic.

**Published, filterable version:** the same 29 ideas, filterable live by surface
and effort, are published as an interactive artifact
(`https://claude.ai/code/artifact/f7a4ed60-8da1-4dfa-b664-f9a11f9b0485`). This
document is the durable, in-repo copy — generated directly from the artifact's
own data so the two cannot drift apart; regenerate rather than hand-edit if the
list changes.

## Governing boundaries

Every idea below was screened against ATHENA's frozen invariants before being
listed. None of the following changes regardless of which ideas get built:

- No order-placement code, under any of these, ever.
- No invented profit targets, blended scores, or quality claims a validated
  method doesn't support.
- Every explanation stays computed and persisted by the engine that produced
  it (ADR-005) — none of these ideas re-derive a rationale in the browser.
- DarvaX keeps its `EXPERIMENTAL · UNVALIDATED` badge and its amber identity
  visually distinct from ATHENA's own surface, however far shared polish (a
  theme toggle, cross-linking) goes.

## How this list was built

Not brainstormed cold. A code survey (notifications, decision-compare, saved
symbols, search, responsive CSS coverage, personalization state, the Decision
Journal/outcome tracker, onboarding empty states, keyboard shortcuts, and
ATHENA↔DarvaX cross-linking) ran first, specifically so this list wouldn't
repropose what already exists. Two findings reshaped the result: **every alert
today is an ops-failure notice, never an owner-defined trading condition** (the
single biggest gap found), and **the Decision Journal and outcome tracker are
already fully built** — several ideas below are "roll up data that's already
captured" rather than "build new tracking," which is far cheaper than it reads.

**29 ideas across 12 categories** — 12 quick wins, 14 medium, 3 big bets.

| # | Category | Ideas |
|---|---|---|
| 1 | [Alerts that actually alert](#1-alerts-that-actually-alert) | 3 |
| 2 | [Unify the two advisory lanes](#2-unify-the-two-advisory-lanes) | 2 |
| 3 | [Findability & navigation](#3-findability-navigation) | 2 |
| 4 | [Performance & conviction analytics](#4-performance-conviction-analytics) | 3 |
| 5 | [Mobile & responsive parity](#5-mobile-responsive-parity) | 2 |
| 6 | [Personalization](#6-personalization) | 3 |
| 7 | [Guided onboarding](#7-guided-onboarding) | 2 |
| 8 | [Trust & explainability at a glance](#8-trust-explainability-at-a-glance) | 3 |
| 9 | [Risk & portfolio awareness](#9-risk-portfolio-awareness) | 2 |
| 10 | [Market context & depth](#10-market-context-depth) | 2 |
| 11 | [Visual & interaction polish](#11-visual-interaction-polish) | 3 |
| 12 | [Reliability & loading states](#12-reliability-loading-states) | 2 |

---

## 1. Alerts that actually alert

*The single biggest gap found: every alert today is an ops-failure notice, never a trading condition the owner defines.*

### Owner-authored price/level alerts

**Surface:** ATHENA + DarvaX  
**Effort:** Big bet

“Tell me when RELIANCE crosses ₹2,850” or “when DarvaX's buy level is hit” — no owner-configurable trading alert exists today at all.

> **Already there:** Reuses the existing webhook/file notifier infrastructure (DD-9) — needs a rules engine and an evaluation pass per cycle, not a new delivery channel.

### Daily “near-miss” digest

**Surface:** ATHENA + DarvaX  
**Effort:** Medium

Symbols sitting within 1–2% of their buy trigger, folded into the existing morning briefing — real value with no new alert engine.

> **Already there:** The DailyBriefing dispatcher already exists (notifications/dispatch.py); this is a new section inside it.

### Surface the outcome data that already exists

**Surface:** ATHENA  
**Effort:** Quick win

“3 TRADE calls last week — 2 accepted, 1 rejected; accepted trades are +4.1% so far” — built from data already captured per-decision but never summarized anywhere.

> **Already there:** TradeOutcome and DecisionJournalEntry are fully implemented (domain/decision.py) — this is a rollup, not new data capture.


## 2. Unify the two advisory lanes

*ATHENA and DarvaX are fully siloed today — not even a link between a symbol's two views.*

### “See the other view” cross-link

**Surface:** ATHENA + DarvaX  
**Effort:** Medium

A symbol's ATHENA Decision Brief gets a quiet “DarvaX also has a read on this →” affordance when one exists, and vice versa.

> **Already there:** Confirmed fully siloed today — tab.js has zero references to ATHENA's decision routes.

### One “Symbol 360” page

**Surface:** ATHENA + DarvaX  
**Effort:** Big bet

One search box, one page: ATHENA's Decision, DarvaX's screen result, saved-symbol status, and journal history for that instrument, side by side.

> **Already there:** Pure presentation over data every engine already persists — no new analytical logic, respects explainability-as-data throughout.


## 3. Findability & navigation

*Every search box today is scoped to its own tab — there is no way to jump straight to a symbol from anywhere.*

### Global command palette (⌘K)

**Surface:** ATHENA + DarvaX  
**Effort:** Medium

Jump to any symbol, any tab, any saved search from one keystroke, instead of navigating tab-by-tab.

> **Already there:** Three separate scoped search boxes exist (universe, decisions list, validation results) — none talk to each other.

### Tab-switch keyboard shortcuts

**Surface:** ATHENA  
**Effort:** Quick win

1–5 for the five main tabs. Escape already closes modals — nothing else is keyboard-reachable yet.


## 4. Performance & conviction analytics

*The hard part — capturing what actually happened — is already built on both sides. It just isn't rolled up.*

### “My track record” panel

**Surface:** ATHENA  
**Effort:** Medium

Win rate, average R-multiple, plan-adherence rate — aggregated from data that's already captured per decision but never summarized.

> **Already there:** TradeOutcome already computes PnL and adherence per decision (19-decision-brief-history.js) — this is a rollup view, not new tracking.

### DarvaX's own realized-performance view

**Surface:** DarvaX  
**Effort:** Medium

Win rate and realized R split by rule (B vs. retest) and by stop-placement (above vs. below breakout) over closed positions — this also starts feeding real evidence toward the DX-5 sufficiency gate.

> **Already there:** darvax_positions already records closed round-trips with a frozen stop — the raw data for this exists today.

### Equity curve / R-multiple distribution sparkline

**Surface:** ATHENA + DarvaX  
**Effort:** Quick win

A visual next to the track-record numbers — a shape communicates “consistent small wins” vs. “one lucky trade” faster than a table.


## 5. Mobile & responsive parity

*Coverage is real but uneven — and DarvaX is close to desktop-only.*

### Bring DarvaX up to ATHENA's responsive floor

**Surface:** DarvaX  
**Effort:** Medium

darvax.css carries 3 media queries total against ATHENA core's fuller (if uneven) coverage — a glance at the Advisor view from a phone during market hours barely works today.

### Close the four desktop-fixed panels

**Surface:** ATHENA  
**Effort:** Medium

The Decision Brief's chart, analysis breakdown, and context/history panels carry zero media queries — exactly the most-viewed screens in the app.

> **Already there:** Confirmed absent in 04-shared-components.css, 10-trade-plan-chart.css, 11-analysis-breakdown.css, 13-context-history.css.


## 6. Personalization

*There is exactly one visual theme and almost no persisted preference beyond sidebar state.*

### Light/dark theme toggle

**Surface:** ATHENA + DarvaX  
**Effort:** Medium

No theme handling exists anywhere today. Needs care on DarvaX specifically — its amber identity has to stay visually distinct from ATHENA's own surface in both themes, not just invert.

### Default tab + reorderable Saved Symbols

**Surface:** ATHENA  
**Effort:** Quick win

Saved Symbols is a flat, unordered bookmark list today — letting the owner pin their top few to the front costs little and is used constantly.

> **Already there:** Saved Symbols already exists (09-market-intelligence.js) — this extends it, doesn't replace it.

### A reason field when saving a symbol

**Surface:** ATHENA + DarvaX  
**Effort:** Quick win

“Why did I save this” has nowhere to live today on either side — saving is bookmark-only.


## 7. Guided onboarding

*Empty states exist but are handled ad hoc, screen by screen, not as one first-run path.*

### One first-run checklist

**Surface:** ATHENA  
**Effort:** Medium

Connect Kite → seed candidates → run first cycle → see the first Decision Brief, as one guided path instead of scattered “no decisions yet” messages across tabs.

> **Already there:** Confirmed scattered today: three separate ad hoc empty-state strings across 12-decisions-list.js alone.

### Point new visitors at the Guide

**Surface:** DarvaX  
**Effort:** Quick win

A first-time DarvaX visitor sees a blank screener with no signal that a full “How DarvaX works” guide is one click away.

> **Already there:** The DX-11 guide already exists and is comprehensive — this is purely a discoverability nudge.


## 8. Trust & explainability at a glance

*The engine already computes rationale for everything (ADR-005) — some of it just isn't visible until you dig in.*

### A persistent data-freshness indicator

**Surface:** ATHENA + DarvaX  
**Effort:** Quick win

“As of” timestamps exist in specific panels, but there's no single always-visible answer to “how stale is what I'm looking at” — the one question that matters most in a trading tool.

### Confidence band visible in the decisions list

**Surface:** ATHENA  
**Effort:** Medium

High/Medium/Low confidence is currently only visible after opening a Decision Brief — surfacing it as a small pill in the list itself saves a click on every single row.

### Make the EXPERIMENTAL badge answer its own question

**Surface:** DarvaX  
**Effort:** Quick win

One click from the badge straight to the live DX-5 numbers (closed trades and trading days measured so far, against the 200/500 bar) — turning a static warning into a current, numeric answer.

> **Already there:** The DX-5 sufficiency gate and its two constants already exist and are already tested (test_dx11_guide.py) — this just wires the badge to them.


## 9. Risk & portfolio awareness

*Risk limits live in config today; nothing shows how much of today's budget is already spent.*

### A live daily risk-budget gauge

**Surface:** ATHENA  
**Effort:** Big bet

How much of max_daily_loss_pct is already “spent” by open positions, visible on Overview at a glance — turns a config constraint into something the owner actually watches.

### Sector concentration warning

**Surface:** ATHENA + DarvaX  
**Effort:** Medium

Flag it when a new buy candidate (from either side) would pile into a sector the portfolio is already heavy in — using sector membership data that already exists.


## 10. Market context & depth

*Two ideas that reuse data already computed elsewhere in the pipeline, not new methodology.*

### Sector rotation heatmap

**Surface:** ATHENA  
**Effort:** Medium

A visual grid of sector_health scores on Market Intelligence — a classic professional-terminal view the module already has the numbers for.

### “Others in this sector” context on a DarvaX card

**Surface:** DarvaX  
**Effort:** Medium

“3 other stocks in this sector also broke out this week” — a conviction signal from data already on hand, not an invented indicator.


## 11. Visual & interaction polish

*Small, high-leverage extensions of patterns already proven out this session.*

### Trend badge on Advisor cards

**Surface:** DarvaX  
**Effort:** Quick win

The 50/100 EMA trend data now exists in every sweep (DX-12a) but only shows in the Table view — a small badge on the Advisor card is the next natural step.

> **Already there:** This is DX-12b, already scoped and pending review.

### Mini price sparkline per row

**Surface:** DarvaX  
**Effort:** Medium

A tiny 20–30-bar chart right in the Table/Advisor row — today the box shape is only visible in the dedicated Levels ladder.

### One-click copy of a symbol's levels

**Surface:** ATHENA + DarvaX  
**Effort:** Quick win

Entry / stop / target formatted for pasting straight into a broker's order ticket — the owner executes manually today with no shortcut for that step.


## 12. Reliability & loading states

*The DarvaX sweep already has a good progress bar — not every slow panel does.*

### Skeleton states instead of blank flashes

**Surface:** ATHENA + DarvaX  
**Effort:** Quick win

Extend DarvaX's existing sweep-progress pattern to ATHENA's slower panels, so a loading screen never reads as a broken one.

> **Already there:** The pattern to extend already exists and works well (DX-6b sweep progress).

### Visible “last successful cycle” + overdue warning

**Surface:** ATHENA  
**Effort:** Quick win

Surface this outside Live Operations too — an overdue cycle is exactly the kind of silent failure a trading tool can't afford to hide in one tab.


---

## Next step

This is a menu, not a plan. Pick what's worth a milestone, and it goes through
the normal Design → Implement → Test → Self-validate → Review → approval cycle
like everything else in `docs/MILESTONES.md` — nothing here skips that gate for
having already been written down.
