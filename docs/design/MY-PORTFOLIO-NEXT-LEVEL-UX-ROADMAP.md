# My Portfolio Next-Level UX Roadmap

Date: 2026-09-07

Owner intent: take the existing My Portfolio workstation to a professional
trading-operations level without changing Portfolio methodology, evidence
semantics, interpretation versions, order placement, or advisory-only scope.

## Current Baseline

My Portfolio already supports:

- confirmed holdings import and reconciliation;
- Portfolio Sync over persisted market state;
- server-owned current value, investment, P&L, and currentness;
- Daily Review v0 and Portfolio Intelligence V2 structural review display;
- compact/full holdings table modes;
- symbol detail overlay;
- row numbering, sorting, privacy masking, reset, recent imports, and exports;
- advanced selected-column CSV/XLSX/JSON exports.

The next step is not more raw data. The next step is better decision workflow:
what needs attention, what changed, where risk is concentrated, and how the
owner completes a daily review session with less scanning.

## Complete UX Feature Inventory

This roadmap covers the full 14-item next-level UX inventory:

1. Portfolio Command Dashboard.
2. Action Queue View.
3. Column Profiles.
4. Portfolio Heatmap.
5. Symbol Detail Review Timeline.
6. Change Since Last Sync.
7. Risk Concentration Panel.
8. Watchlist / Opportunity Bridge.
9. Notes / Owner Override Layer.
10. Review Session Mode.
11. Pinned Rows.
12. Smart Filters.
13. Inline Mini Sparklines.
14. Export Profiles.

## Feature-to-Milestone Map

| Feature | Milestone | Notes |
|---|---|---|
| Portfolio Command Dashboard | MP-NX1 / MP-NX6C | Implemented 2026-09-07; MP-NX6C restacked the scan surface 2026-09-09 (four live metrics, collapsed Filters). |
| Action Queue View | MP-NX1 | Implemented 2026-09-07: dedicated actionable-holdings list scope over existing snapshot fields. |
| Smart Filters | MP-NX1 | Implemented 2026-09-07: filter chips for review, trend, status, P&L state, evidence availability, and currentness. |
| Change Since Last Sync | MP-NX2 | Owner/Chief Architect approved and closed 2026-09-07. |
| Risk Concentration Panel | MP-NX2 | Owner/Chief Architect approved and closed 2026-09-07. |
| Column Profiles | MP-NX3 | Owner/Chief Architect approved and closed 2026-09-08. |
| Pinned Rows | MP-NX3 | Owner/Chief Architect approved and closed 2026-09-08. |
| Export Profiles | MP-NX3 | Owner/Chief Architect approved and closed 2026-09-08. |
| Portfolio Heatmap | MP-NX4 | Owner/Chief Architect approved and closed 2026-09-08. |
| Inline Mini Sparklines | MP-NX4 | Not shipped: snapshot rows have no D1 close series; no new history fetch. |
| Symbol Detail Review Timeline | MP-NX5 | Implemented 2026-09-08: per-holding review timeline from recent snapshots. |
| Watchlist / Opportunity Bridge | MP-NX5 | Skipped: no stable My Portfolio opportunity contract; no new ranking authorized. |
| Notes / Owner Override Layer | MP-NX6 | Owner/Chief Architect approved and closed 2026-09-08. |
| Review Session Mode | MP-NX6B | Owner/Chief Architect approved and closed 2026-09-08. |

## Design Principles

- Preserve frozen portfolio methodology. UI may organize, filter, compare, or
  summarize existing computed fields unless a later milestone explicitly
  authorizes new domain evidence.
- Keep advisory-only boundaries. No order placement, broker-side mutation, or
  execution workflow.
- Prefer workflow surfaces over decorative cards. The screen should answer
  "what do I need to look at now?" first.
- Separate owner-authored state from ATHENA-generated state. Notes, pins,
  review marks, and preferences must never be confused with Portfolio
  Intelligence output.
- Every new view must degrade gracefully when a snapshot is missing, stale,
  partial, or has unavailable evidence.
- Each milestone must be independently reviewable, testable, and reversible.

## Proposed Milestone Sequence

### MP-NX1 — Action Queue and Smart Filters

Status: Implementation complete 2026-09-07 — ready for Owner / Chief Architect
review. Presentation-only over already loaded holdings/snapshot rows.

Objective: create a morning triage surface that shows holdings needing attention
without requiring the owner to scan the full table.

Scope completed:

- Added a non-sticky Portfolio Command Dashboard between the freshness strip
  and Current Holdings so sticky-header bleed cannot recur.
- Attention chips with counts: `Review / Hold Tight`, `Exit Risk`, `Stale Data`,
  `Unavailable Evidence`, and `Needs Review`.
- Deferred chips labeled unavailable (not invented): `Near Trigger`,
  `Near Support`, and `Fresh Breakout`.
- Smart Filters over existing fields only: Status, Daily Review, Next Action,
  Trend, Opening Range Setup, P&L state, currentness, and evidence
  availability.
- Action Queue list scope (`All Holdings` / `Action Queue`) reuses the existing
  row renderer and current sort/density/privacy/export/sync behavior.
- Client-side predicates only. No API, methodology, or interpretation-version
  change.

Frozen MP-NX1 predicates:

- `Review / Hold Tight`: `daily_review.review_status === REVIEW_HOLD_TIGHT`.
- `Exit Risk`: `structural_review.exit_risk === true`.
- `Stale Data`: snapshot currentness is `STALE_HOLDINGS_CHANGED` or `UNKNOWN`,
  or the row carries `STALE_*` interpretation provenance. No snapshot → 0.
- `Unavailable Evidence`: no snapshot, or missing Daily Review status, Status
  missing/`UNAVAILABLE`, missing Trend, or Structural Review missing/incoherent.
- `Needs Review` / Action Queue membership: snapshot row with Review / Hold
  Tight, Exit Risk, Next Action `EXIT`/`WATCH`/`ADD`, or Status `AT_RISK`/
  `CAUTION`. No snapshot → empty queue with a sync prompt.
- Smart Filters AND across groups and OR within a group. Attention chips OR.
  Action Queue ANDs with the actionable predicate. `Needs Review` toggles the
  Action Queue rather than adding a second overlapping filter.

Non-goals:

- No new Status, Conviction, Next Action, structural level, or Daily Review
  methodology.
- No new broker calls outside the existing sync path.
- No near-trigger, near-support, or fresh-breakout distance/recency thresholds.

Primary UX outcome:

- Owner can open My Portfolio and immediately know what deserves attention.

### MP-NX2 — Change Since Last Sync

Implemented 2026-09-07. Ready for Owner / Chief Architect review.

Objective: make daily syncs meaningful by showing what changed versus the
previous snapshot.

Scope:

- Add snapshot-to-snapshot diff derivation for display only.
- Highlight changed fields per row: Status, Daily Review Status, Next Action,
  Trend, Setup, P&L %, current value, key structural levels, guidance text, and
  currentness.
- Add badges such as `Status changed`, `Trend flipped`, `Action changed`,
  `P&L moved +4.2%`, `New support`, and `Target reached` only when backed by
  existing fields.
- Add detail-overlay "Since last sync" panel.
- Add a Risk Concentration Panel summarizing existing exposure by Status, Trend,
  Next Action, high-conviction positions, top holdings by capital, largest
  winners, and largest losers.

Non-goals:

- No persistence schema changes unless needed for efficient prior-snapshot
  lookup and approved in the milestone.
- No interpretation-version bump.
- No new risk scoring methodology; concentration summaries are factual
  aggregation of existing values only.

Primary UX outcome:

- Owner can see why today's portfolio view matters.

### MP-NX3 — Column Profiles

Implemented 2026-09-07. Ready for Owner / Chief Architect review.

Objective: turn table density into purposeful professional layouts.

Scope:

- Add saved table profiles:
  `Compact Scan`, `P&L Review`, `Technical Review`, `Risk Review`, `Full Audit`.
- Each profile controls visible columns, default sort, density, and quick
  context emphasis.
- Add Pinned Rows so owner-selected holdings can stay visible regardless of
  current sort/filter, clearly labeled as owner-pinned.
- Add Export Profiles using the approved selected-column export contract:
  `Daily Review`, `Full Audit`, `Private Sharing`, and future owner-defined
  presets if approved.
- Reuse the export selected-column catalog where practical, but keep table
  profile state separate from export state.
- Store preferences locally unless owner explicitly approves server persistence.

Non-goals:

- No data model or methodology change.
- No automatic profile switching without owner action.
- No server-persisted pins/export profiles unless owner approves persistence.

Primary UX outcome:

- Owner can switch from scanning to review to audit without fighting the table.

### MP-NX4 — Portfolio Heatmap

Owner/Chief Architect approved and closed 2026-09-08.

Implemented 2026-09-08. Ready for Owner / Chief Architect review.

Objective: add an at-a-glance concentration and performance surface.

Scope:

- Add heatmap modes:
  size by investment/current value;
  color by P&L %, Status, Daily Review, Trend, or Next Action.
- Clicking a tile opens the existing symbol detail overlay.
- Add optional Inline Mini Sparklines in the holdings table for compact D1
  visual context when the data and performance budget support it.
- Support privacy masking by hiding money labels while preserving relative tile
  sizing only if this is acceptable to the owner; otherwise use equal tile size
  under privacy mode.

Non-goals:

- No sector/benchmark attribution unless already available in a stable contract.
- No new risk methodology.
- No TradingView/Kite visual parity claim for sparklines.

Primary UX outcome:

- Owner can see where capital, profit, loss, and attention are concentrated.

### MP-NX5 — Symbol Review Timeline

Implemented 2026-09-08. Ready for Owner / Chief Architect review.

Watchlist / Opportunity Bridge was skipped: no stable My Portfolio
opportunity contract exists, and no new ranking methodology was authorized.

Objective: make each holding's evolution inspectable.

Scope:

- Add a timeline inside the symbol detail overlay using prior snapshots.
- Show time-series events for price, P&L %, Status, Trend, Daily Review Status,
  Next Action, and guidance changes.
- Mark evidence staleness and partial-sync states.
- Add Watchlist / Opportunity Bridge only if stable watchlist/opportunity
  contracts exist: show relevant watchlist candidates, exited names, or better
  setups near weak holdings without changing ATHENA decisions.

Non-goals:

- No charting replacement for TradingView/Kite.
- No prediction layer.
- No new watchlist ranking methodology unless separately approved.

Primary UX outcome:

- Owner can answer "what changed in this holding over the last few syncs?"

### MP-NX6 — Owner Notes and Review Session Mode

Owner Notes (MP-NX6) and Review Session Mode (MP-NX6B) are Owner/Chief
Architect approved and closed 2026-09-08. The next-level UX sequence is
complete.

Objective: turn My Portfolio into a daily review workflow while preserving
separation between owner judgment and ATHENA-generated intelligence.

Scope:

- Add owner-authored notes per holding: thesis, watch condition, manual reminder,
  and review comment.
- Add review marks: reviewed today, defer, pinned, needs manual follow-up.
- Add Review Session mode:
  one holding at a time, mark reviewed, add note, defer, next.
- Keep owner-authored fields visually and contractually separate from ATHENA
  evidence and guidance.

Non-goals:

- No order placement.
- No automatic trading recommendations derived from owner notes.

Primary UX outcome:

- Owner can complete a disciplined daily portfolio review inside ATHENA.

## Suggested Priority

Recommended order:

1. MP-NX1 — Action Queue and Smart Filters.
2. MP-NX2 — Change Since Last Sync.
3. MP-NX3 — Column Profiles.
4. MP-NX4 — Portfolio Heatmap.
5. MP-NX5 — Symbol Review Timeline.
6. MP-NX6 — Owner Notes (closed) and MP-NX6B Review Session Mode.

Reasoning: MP-NX1 and MP-NX2 produce the highest workflow value with the lowest
methodology risk. MP-NX3 then makes the table scalable. Heatmap and timeline add
strong visual/contextual depth. Owner Notes and Review Session Mode are powerful
but introduce user-authored persistence and should come after the display layer
is stable.

Expanded inventory order:

1. Portfolio Command Dashboard.
2. Action Queue View.
3. Smart Filters.
4. Change Since Last Sync.
5. Risk Concentration Panel.
6. Column Profiles.
7. Pinned Rows.
8. Export Profiles.
9. Portfolio Heatmap.
10. Inline Mini Sparklines.
11. Symbol Detail Review Timeline.
12. Watchlist / Opportunity Bridge.
13. Notes / Owner Override Layer.
14. Review Session Mode.

## Acceptance Criteria for Each Milestone

- Clear owner-facing UX with no hidden workflow steps.
- Works with no holdings, holdings without sync, stale snapshot, partial sync,
  and complete sync.
- Respects privacy masking where private values appear.
- Does not change Portfolio Intelligence semantics unless explicitly approved.
- Has focused API/service tests when data contracts change.
- Has dashboard contract tests for new controls and cache-busted assets.
- Updates this roadmap, `docs/MILESTONES.md`, `ATHENA_BRIEFING.md`, and
  `IMPLEMENTATION_SUMMARY.md`.

## Open Questions for Owner Approval

- MP-NX1 decided: smart filters are pure client-side filters over the latest
  loaded snapshot/holdings. Revisit an API query layer only if holdings scale
  requires it.
- Should column profiles be local browser preferences or server-persisted owner
  preferences?
- In privacy mode, should heatmap tile size still encode private capital values?
- Should owner notes live inside ATHENA's database, or should they start as
  local-only browser annotations until the workflow is proven?
- Should Review Session Mode be daily-calendar aware or simply owner-triggered?
