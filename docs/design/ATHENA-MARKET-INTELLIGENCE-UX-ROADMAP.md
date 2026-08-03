# ATHENA Market Intelligence UX Roadmap

**Status:** MI-UX-0 approved (owner review, 2026-08-03); MI-UX-1 in progress
**Scope:** Correctness, information architecture, and visual-design quality of
the Market Intelligence dashboard screen (`/dashboard/market`) — the single
highest-density surface in ATHENA and the owner's daily entry point.
**Owner goal:** a screen that reads like a world-class market intelligence
product — scannable, honest about data gaps, and led by what's actionable —
without changing any analytical engine, score, or decision output.

## 1. Governing Boundaries

- This track is presentation and information-architecture only. It never
  changes regime, market health, sector health, evidence, scoring,
  confidence, risk, decision, or TradePlan values, and adds no broker write
  action.
- Where a fix touches backend data (e.g. a computed percentage that
  contradicts its own supporting counts), the fix corrects an existing
  calculation to be internally consistent — it does not invent a new metric,
  threshold, or policy. Any such fix follows ADR-005: the correction is
  computed and persisted by the engine that owns the number, not
  reconstructed by the dashboard.
- Where real data for a tile is structurally unavailable (e.g. Market Health
  missing `institutional_strength`), the fix is to stop giving unavailable
  data the same visual prominence as real data — never to fabricate a
  placeholder value.
- Copy stays plain and glanceable. No new jargon-only labels; abbreviations
  (e.g. "RS") get a spelled-out label or tooltip.

## 2. Origin — audit findings (2026-08-03)

A screenshot-driven audit of the live Market Intelligence screen surfaced 11
findings, grouped by severity:

**P0 — broken or actively misleading:**
1. Top Opportunities Today cards render mid-card clipped (cards show a header
   with no visible symbols) — a side effect of the MARKET_MAIN_MIN_HEIGHT
   layout fix (`css/06-market-intelligence.css`) giving Validation
   Pipeline/Universe a firm floor at the summary band's expense on shorter
   viewports.
2. The Breadth tile showed `0% · WEAK` next to `ADV 384 · DEC 124 · NEU 2` —
   internally contradictory; 384 advancers vs. 124 decliners is strongly
   positive breadth, not 0%/weak.
3. Market Health renders `Unavailable` with a full-width tile and a dedicated
   Evidence Attribution line explaining its own unavailability, apparently on
   every load — permanently-broken data is getting the same visual budget as
   working data.

**P1 — high-impact UX / information architecture:**
4. Timestamp sprawl: 5+ differently-phrased freshness labels on one screen
   (`As of`, `Observed`, `Updated`, `Last Updated`, `next live`) that don't
   agree with each other in a single screenshot.
5. The most actionable item on the page — a failed validation run with a
   named blocker — is rendered in the same small, muted register as routine
   metadata.
6. Three different visual idioms (sparkline, donut ring, dot row) across 8
   equally-weighted Market Summary tiles.
7. Universe table's default view surfaces mostly Excluded/noise rows ahead of
   Eligible/Watch/Trade rows.
8. Header is an ungrouped row of status pills (ticker, advisor-status pill,
   Kite pill, icon buttons, Healthy pill) with no visual priority.

**P2 — polish:**
9. "RS" (Relative Strength) is ambiguous at a glance — could read as Rupees.
10. Quick Actions card has a stray status line duplicating Recent Activity.
11. Evidence Attribution — the most decision-relevant sentence on the page —
    is a single dense line easy to skip past.

## 3. Target Experience

The owner should be able to answer these questions in a single glance, in
priority order:

1. Is anything on this screen broken or does something need my attention
   right now (failed run, blocker, contradictory data)?
2. What's the market doing today, at a glance, with one consistent visual
   language?
3. What's actionable today (qualified opportunities, eligible symbols) —
   without wading through excluded/noise rows to find it?
4. How fresh is what I'm looking at — using one mental model, not five?
5. If I want to go deeper (why a score/regime is what it is, which symbols
   were excluded and why), that detail is one click away, not fighting for
   first-fold space with the answers to 1–4.

## 4. Milestone Plan

### MI-UX-0 — Design & Audit Gate

**Goal:** Establish the audit findings above, prioritize them, and get owner
sign-off on tackling P0 first.

Acceptance: owner reviews the findings and approves starting with P0.

Status: ✅ Approved (owner review in chat, 2026-08-03).

### MI-UX-1 — P0 Correctness Fixes

**Goal:** Fix the three broken/misleading states before any broader redesign
conversation, since they actively erode trust in every other number on the
page.

Scope:
- Fix Top Opportunities Today's mid-card clipping so cards never render
  partially — either a card is fully visible or it isn't rendered in the
  visible band at all; internal scrolling, if kept, must clip between cards.
- Investigate and fix the Breadth tile's `0%`/`WEAK` vs. `ADV 384 · DEC 124`
  contradiction at its source.
- Change how Market Health's `Unavailable` state is presented when the
  required component is structurally missing, so it no longer competes for
  attention with working tiles at equal visual weight.

Acceptance:
- No opportunity card ever renders with a visible header and no visible
  symbol content.
- Breadth's percentage/label is always consistent with its own advance/
  decline counts, or the tile honestly says the percentage is unavailable
  rather than showing a contradictory number.
- Market Health's unavailable state is visually subordinate to working
  tiles.

### MI-UX-2 — Freshness & Alert Unification (P1)

**Goal:** One consistent freshness phrasing across the screen; failed
runs/blockers get real alert treatment.

Scope:
- Replace the 5+ bespoke timestamp phrasings with one shared pattern.
- Give the Validation Pipeline's failed-run/blocker state visual prominence
  proportional to how actionable it is.

Acceptance: a single freshness convention is used everywhere on the screen;
a failed run is visually unmissable without needing to read small print.

### MI-UX-3 — Visual Consistency & Information Architecture (P1)

**Goal:** One metric-tile idiom; actionable-first default views; a grouped,
prioritized header.

Scope:
- Consolidate Market Summary's three visual idioms (sparkline/ring/dots) into
  one consistent tile pattern.
- Change Universe's default view to lead with Eligible/Watch/Trade, with
  Excluded available as an explicit filter rather than the default noise.
- Group header status pills by priority/category instead of one undifferentiated row.

Acceptance: Market Summary tiles read as one repeated pattern; opening
Universe shows actionable symbols first; the header has a clear primary vs.
secondary status hierarchy.

### MI-UX-4 — Polish & Release Gate (P2 + QA)

**Goal:** Close out the remaining polish items and regression-test the whole
track.

Scope:
- Spell out or tooltip the "RS" label.
- Remove the duplicated status line from Quick Actions.
- Give Evidence Attribution more visual weight relative to the summary tiles.
- Screenshot/interaction QA across the full Market Intelligence screen.

Acceptance: no known P0–P2 finding from §2 remains open; regression coverage
locks in the fixed states.

**Implementation rule:** one MI-UX milestone at a time. MI-UX must never
create order placement, broker write actions, new signals, or changes to
ATHENA's analytical engines.

## 5. Non-Goals

- Auto-trading, broker order placement, or OMS integration.
- New scoring, confidence, risk, decision, or TradePlan rules.
- A full visual rebrand — this track fixes correctness and hierarchy, not
  ATHENA's design language.
