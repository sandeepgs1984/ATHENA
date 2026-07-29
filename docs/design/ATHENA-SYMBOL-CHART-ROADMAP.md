# ATHENA Symbol Chart Excellence Roadmap

**Status:** CH-0, CH-1, and CH-2 approved; CH-3 ready for owner review
**Date:** 2026-07-29
**Scope:** Decision Brief symbol chart presentation only
**Owner goal:** World-class, trading-grade chart presentation without adding
order placement, fabricated signals, or unreviewed architecture changes.

---

## Governing Constraints

This roadmap is implementation guidance under the frozen ATHENA architecture.
It must remain aligned with:

- `ATHENA-002-System-Blueprint.md`:
  - dashboard/reporting renders stored domain objects and read-only market data.
  - `TradePlan` carries entry zone, stop, targets, risk/reward, and validity
    window.
  - no order-placement behavior is allowed.
  - frozen module map, domain model, and contracts require ADR approval before
    architectural expansion.
- `docs/adr/ADR-004-static-html-first.md`:
  - static HTML, vanilla JavaScript, and Lightweight Charts are accepted for the
    workstation/dashboard surface.
- `docs/adr/ADR-005-explainability-as-data.md`:
  - explanations and overlays must be rendered from persisted or explicitly
    returned data.
  - the UI must not reconstruct, invent, or imply hidden strategy logic.

Any milestone that needs a new domain field, provider source, write behavior,
or non-read-only action is blocked until the correct ADR/DD/owner approval is
complete.

---

## Current Implementation Audit

### Backend Data Surface

- Existing endpoint:
  - `GET /api/v1/market/instruments/{instrument_id}/candles`
  - query params include `timeframe` and `limit`.
  - current UI uses `timeframe=5m&limit=120`.
- Chart controls expose only timeframes supported by the active provider and
  live ingestion configuration. Current controls use `5m` and `15m`; `1m` is
  not shown because the provider capability config does not declare it.
- `MarketHistoryService.recent_candles` returns persisted OHLCV candles,
  freshness information, ATR series, and SMA series.
- Trade plan levels and validity are loaded from the selected decision/depth
  payload, not calculated by the chart.

### Frontend Rendering

- Current renderer:
  - `src/athena/api/static/js/16-decision-brief-chart.js`
  - hand-rolled SVG chart.
- Current visual features:
  - candlesticks.
  - volume subplot.
  - SMA line.
  - ATR envelope.
  - TradePlan entry zone, stop, and target lines.
  - no-data and stale-data states.
  - modal chart reuses the same renderer.
  - limited native SVG hover titles.
- Current limitations:
  - no professional crosshair/legend interaction.
  - no zoom/pan/time scale controls.
  - no timeframe selector in the UI.
  - no current-price marker.
  - no session/day separators.
  - no persistent chart preferences.
  - fixed SVG dimensions constrain responsive quality.
  - visual inspection is harder than it should be during real money decisions.

### What Is Already Correct

- The chart is read-only.
- TradePlan overlays use real plan values.
- Stale/no-data warnings exist.
- The chart does not place orders or trigger broker actions.
- Existing data is enough for a professional foundation milestone.

---

## Target Experience

The chart should answer four questions within seconds:

1. **Where is price now?**
   - readable candles, current price marker, volume context, clean axes.
2. **Where is ATHENA's plan?**
   - entry zone, stop, targets, risk/reward, and validity shown directly on the
     price scale.
3. **How fresh is this plan and data?**
   - visible expiry/freshness state, source timestamp, stale warnings.
4. **What exactly am I inspecting?**
   - crosshair legend with candle OHLCV plus rendered indicators/plan levels.

The chart must feel professional, but correctness is more important than visual
drama. A beautiful chart that implies unsupported signals is unacceptable.

---

## Milestone Plan

### CH-0 — Design & Architecture Gate

**Objective:** Approve this roadmap before any chart implementation begins.

**Scope:**

- Capture current chart/data behavior.
- Confirm ADR-004 and ADR-005 alignment.
- Split work into independently reviewable milestones.
- Define explicit no-fabrication and no-order-placement boundaries.

**Deliverables:**

- This roadmap.
- `docs/MILESTONES.md` chart track entry.

**Acceptance criteria:**

- Owner confirms the roadmap.
- Owner confirms the dependency approach for Lightweight Charts:
  - preferred: vendored static asset under the existing dashboard static tree,
    with source/version documented; or
  - alternative: CDN load with a graceful unavailable-library state.

**Status:** Approved by owner on 2026-07-29.

---

### CH-1 — Professional Chart Foundation

**Objective:** Replace the hand-rolled SVG with a professional chart foundation
while preserving the same truthful data surface.

**Scope:**

- Introduce a small chart controller around the existing candles endpoint.
- Render candlesticks, volume, and existing SMA data.
- Preserve stale/no-data/error states.
- Keep the chart read-only.
- Make normal and modal chart views share one rendering path.
- Make the layout responsive across workstation and compact widths.

**No backend contract changes.**

**Acceptance criteria:**

- Existing Decision Brief tests pass.
- New/updated frontend hosting regression covers the chart asset wiring.
- Visual verification confirms nonblank chart rendering in normal and modal
  states.
- Chart displays the same OHLCV/SMA information as before, without invented
  overlays.

**Status:** Approved by owner on 2026-07-29.

---

### CH-2 — TradePlan Overlays & Validity Layer

**Objective:** Make ATHENA's plan legible directly on the chart.

**Scope:**

- Render entry zone as a bounded band.
- Render stop and target levels as labeled price lines.
- Show stop/target percentage deltas from entry/current context where existing
  plan data supports it.
- Add risk/reward bracket labeling.
- Add validity and freshness affordance near the chart using existing
  `valid_from`, `valid_until`, and freshness data.

**No order actions. No invented plan levels.**

**Acceptance criteria:**

- Stop/target colors match the existing semantic good/bad design tokens.
- Expired/stale plan states are impossible to miss.
- If any plan value is unavailable, the chart degrades honestly rather than
  fabricating a substitute.
- Tests cover plan overlay rendering inputs and expired-plan wording.

**Status:** Approved by owner on 2026-07-29.

---

### CH-3 — Timeframe, Range, and Session Controls

**Objective:** Let the owner inspect the same symbol at useful intraday
resolutions without leaving the Decision Brief.

**Scope:**

- Add timeframe controls for configured supported intervals.
- Add bar-range controls within current API limits.
- Show requested-vs-returned bar counts when the ledger contains fewer bars
  than the selected range.
- Provide the same controls in the dedicated chart modal.
- Remember chart preference locally in browser storage.
- Add session/day separators when supported by candle timestamps.
- Clearly show the selected timeframe and last candle timestamp.
- Keep unavailable timeframe messages tied to the selected timeframe, never a
  hardcoded default.

**No new provider dependency.**

**Acceptance criteria:**

- Switching timeframe reloads only the selected symbol chart.
- Embedded and dedicated chart contexts expose the same timeframe/range
  controls.
- Invalid timeframe/range choices fail visibly and safely.
- Persisted-data shortages are visible and never backfilled with fabricated
  candles.
- All labels use the correct local trading-session interpretation.
- Tests cover query construction and fallback behavior.

**Status:** Implemented on 2026-07-29; ready for owner review.

---

### CH-4 — Interactive Inspection

**Objective:** Make chart reading precise enough for real decision review.

**Scope:**

- Crosshair with OHLCV legend.
- Indicator readout for rendered SMA/ATR values where present.
- Plan-level readout for entry, stop, and targets.
- Zoom/pan reset affordance.
- Keyboard-accessible focus and reset behavior where feasible in the static UI.

**Acceptance criteria:**

- Hover/crosshair never obscures critical plan warnings.
- Missing indicator values display as unavailable, not zero.
- Interaction works in normal and modal chart contexts.
- Visual QA covers desktop and compact widths.

---

### CH-5 — Decision & Event Markers

**Objective:** Connect price action with ATHENA's decision timeline without
manufacturing signals.

**Scope:**

- Render decision timestamp markers from persisted decision data.
- Render journal/outcome markers only when persisted journal/outcome records
  exist.
- Render revalidation markers only when a persisted run/decision timestamp
  supports them.

**Gate:**

- If existing endpoints do not expose enough persisted event data, add only an
  additive read-only DTO/endpoint after owner review.
- Any frozen contract/domain expansion remains ADR-gated.

**Acceptance criteria:**

- Every marker is traceable to a persisted record.
- Marker tooltip identifies source record type and timestamp.
- Empty history shows no markers rather than placeholder examples.

---

### CH-6 — Resilience, Visual QA, and Release Gate

**Objective:** Harden the chart before treating it as a trusted trading
decision surface.

**Scope:**

- Browser visual verification for normal, modal, mobile/compact, stale, and
  no-data states.
- Nonblank canvas/DOM checks for the chart area.
- Performance budget for supported candle limits.
- Accessibility pass for controls and readable contrast.
- Regression tests for asset loading and fallback states.

**Acceptance criteria:**

- Full relevant test suite passes.
- Visual QA evidence is recorded in the milestone review summary.
- No stale plan/data state can look fresh.
- No chart failure hides the rest of the Decision Brief.

---

## Risk Controls

| Risk | Control |
|---|---|
| A visual overlay implies a signal ATHENA did not compute | Render only persisted decision, plan, candle, and indicator data; otherwise show unavailable |
| Owner acts on stale plan/data | Prominent expiry/freshness state in CH-2 and CH-3 |
| Timeframe switch changes interpretation silently | Visible timeframe, bar count, and last candle timestamp |
| Chart library fails to load | Honest unavailable-library state; Decision Brief remains usable |
| Responsive chart hides price/plan labels | Browser visual QA across desktop and compact widths |
| Event markers become reconstructed history | CH-5 requires persisted source records for every marker |
| Implementation drifts into trading automation | No order placement, no broker write action, no buy/sell buttons |

---

## Explicitly Out of Scope

- Order placement, basket creation, broker execution, or pre-filled trade
  tickets.
- AI-drawn trendlines, support/resistance, patterns, or annotations unless
  backed by reviewed deterministic data.
- Streaming/WebSocket charting.
- New external data feeds.
- Options/F&O overlays.
- Strategy/scoring changes.

---

## Implementation Policy

- Implement exactly one chart milestone at a time.
- End every milestone with a Milestone Review Summary.
- Do not start the next milestone until owner approval is recorded.
- Update `IMPLEMENTATION_SUMMARY.md` after each completed milestone.
- Update `ATHENA_BRIEFING.md` only if the module map or track status materially
  changes.

Recommended next step after CH-0 approval: CH-1, because it improves the chart
foundation without changing backend contracts or trading logic.
