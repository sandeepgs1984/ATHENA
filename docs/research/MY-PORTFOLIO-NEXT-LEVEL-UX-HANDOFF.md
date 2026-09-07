# My Portfolio Next-Level UX Handoff

Date: 2026-09-07

Purpose: give any future AI agent enough context to implement the next My
Portfolio UX milestones safely, in order, without reopening frozen methodology
or repeating prior UI mistakes.

## Read First

Before implementing anything in this track, read:

- `ATHENA_BRIEFING.md`
- `docs/MILESTONES.md`
- `docs/design/MY-PORTFOLIO-NEXT-LEVEL-UX-ROADMAP.md`
- `docs/research/MY-PORTFOLIO-POST-CLOSURE-UI-REFINEMENTS.md`
- `docs/research/MY-PORTFOLIO-EXPORTS.md`
- `docs/research/PS-P10D-DAILY-CHART-PORTFOLIO-REVIEW-IMPLEMENTATION.md`

The Portfolio track is closed. These next-level UX milestones are additive,
presentation/workflow improvements unless the owner explicitly approves a new
methodology milestone.

## Mandatory Guardrails

- Do not run git operations unless the owner explicitly asks in that turn.
- Do not add order placement, broker execution, or trading mutation flows.
- Do not change Portfolio Status, Conviction, D1 Trend, Opening Range Setup,
  Daily Review v0, Structural Review V2, Next Action, or TradePlan semantics.
- Do not bump interpretation versions for presentation-only work.
- Do not silently introduce new thresholds such as "near support" or "fresh
  breakout" without documenting whether they are pure UI heuristics or a new
  methodology requiring owner approval.
- Keep owner-authored data visually and contractually separate from
  ATHENA-generated evidence.
- Respect privacy masking for all investment, current value, P&L, and any value
  that reveals private position size.
- Use the existing static dashboard architecture unless a milestone explicitly
  authorizes a frontend architecture change.

## Current Implementation Surfaces

Likely files:

- `src/athena/api/v1/routers/my_portfolio.py`
- `src/athena/api/v1/services/my_portfolio_service.py`
- `src/athena/api/v1/dtos/portfolio.py`
- `src/athena/portfolio/my_portfolio_contracts.py`
- `src/athena/portfolio/sync.py`
- `src/athena/api/static/index.html`
- `src/athena/api/static/css/05b-my-portfolio.css`
- `src/athena/api/static/js/08b-my-portfolio.js`
- `tests/api/v1/test_my_portfolio_import_api.py`
- `tests/api/platform/test_dashboard_hosting.py`
- `tests/api/platform/test_decision_chart_release_gate.py`

Existing dashboard patterns to preserve:

- asset cache busting in `index.html` and release-gate tests;
- dashboard contract tests for HTML/CSS/JS controls;
- static JS concern split via `DASHBOARD_JS_PARTS`;
- My Portfolio privacy mode with non-text masks;
- compact/full holdings table modes;
- modal/detail overlay scroll reset;
- export popover with server-owned export behavior.

## Complete 14-Feature Coverage Checklist

The roadmap intentionally covers all 14 owner-discussed next-level UX ideas:

- Portfolio Command Dashboard: MP-NX1 — Owner/Chief Architect approved and closed 2026-09-07.
- Action Queue View: MP-NX1 — Owner/Chief Architect approved and closed 2026-09-07.
- Column Profiles: MP-NX3.
- Portfolio Heatmap: MP-NX4.
- Symbol Detail Review Timeline: MP-NX5.
- Change Since Last Sync: MP-NX2 — implemented 2026-09-07, pending owner review.
- Risk Concentration Panel: MP-NX2 — implemented 2026-09-07, pending owner review.
- Watchlist / Opportunity Bridge: MP-NX5.
- Notes / Owner Override Layer: MP-NX6.
- Review Session Mode: MP-NX6.
- Pinned Rows: MP-NX3.
- Smart Filters: MP-NX1 — Owner/Chief Architect approved and closed 2026-09-07.
- Inline Mini Sparklines: MP-NX4.
- Export Profiles: MP-NX3.

## Recommended Implementation Order

### 1. MP-NX1 Action Queue and Smart Filters

Owner/Chief Architect approved and closed 2026-09-07.

What shipped:

- Non-sticky `.my-portfolio-command-dashboard` between freshness and Current
  Holdings.
- Named JS predicates in `08b-my-portfolio.js`:
  `myPortfolioRowMatchesReviewHoldTight`, `myPortfolioRowMatchesExitRisk`,
  `myPortfolioRowMatchesStaleData`, `myPortfolioRowMatchesUnavailableEvidence`,
  `myPortfolioRowIsActionable`, plus smart-filter group matching.
- `Near Trigger` / `Near Support` / `Fresh Breakout` remain disabled
  unavailable chips. Opening Range Setup `BREAKOUT` is a Smart Filter only.
- Action Queue reuses the existing holdings renderer and adds reason chips
  next to the symbol. Sort, Compact/Full, privacy, export, and sync are
  unchanged.
- Dashboard asset version `9.184.0`. Screenshot correction: Action Queue
  badge and Clear filters now honor `[hidden]` so they do not stay visible
  on All Holdings.

Do not reopen MP-NX1 unless the owner asks for a correction.

### 2. MP-NX2 Change Since Last Sync

Implemented 2026-09-07. Ready for Owner / Chief Architect review.

What shipped:

- Pure `src/athena/portfolio/snapshot_diff.py` over already-computed fields.
- `SqliteRepository.previous_portfolio_snapshot_sync_run()` using the same
  SUCCESS/PARTIAL + snapshot-exists rule as latest. No schema change.
- `GET /api/v1/my-portfolio/snapshot/changes`.
- Row badges, detail-overlay Since last sync, and a client-side Risk
  Concentration Panel. Privacy masks P&L-moved amounts and money ranks.
- Dashboard asset version `9.186.0`. Screenshot polish: High conviction
  preview (count + 5 names), table-matched labels, signed winner/loser
  tones, quieter no-previous-snapshot note.

Implementation approach:

- Compare latest snapshot rows against the immediately previous completed or
  partial snapshot.
- Keep diff output factual: old value, new value, field changed.
- Add row badges and a detail-overlay "Since last sync" panel.
- Add the Risk Concentration Panel as factual aggregation over existing
  investment/current value/P&L/status/trend/action fields.

Watch-outs:

- Snapshot currentness matters. If holdings changed since sync, distinguish
  "previous snapshot diff" from "current holdings diff."
- Avoid inventing qualitative labels beyond changed/not changed unless approved.
- Do not add new risk scoring; concentration is display aggregation only.

Suggested tests:

- service-level diff tests over synthetic snapshots;
- dashboard contract tests for changed-field badges;
- partial/stale/no-previous-snapshot cases.

### 3. MP-NX3 Column Profiles

Implementation approach:

- Define table profiles in JS first:
  `Compact Scan`, `P&L Review`, `Technical Review`, `Risk Review`, `Full Audit`.
- Each profile should specify visible columns, default sort, and density.
- Persist active profile in `localStorage` only unless owner approves server
  preference storage.
- Add Pinned Rows as owner-controlled priority, not ATHENA ranking.
- Add Export Profiles on top of the approved selected-column export endpoint.

Watch-outs:

- Do not confuse export column presets with table profiles. They may share
  labels/column IDs, but they serve different workflows.
- Keep pinned rows visually marked as owner-pinned so they are not mistaken for
  ATHENA conviction or ranking.
- Preserve keyboard and table scrolling ergonomics.

Suggested tests:

- dashboard contract for profile controls;
- CSS selectors for hidden low-priority columns;
- release-gate asset version bump.

### 4. MP-NX4 Portfolio Heatmap

Implementation approach:

- Add a secondary visualization panel below the KPI/freshness area or as a
  tab inside the holdings workbench.
- Use current loaded rows as data source.
- Tile click opens the existing detail overlay.
- Add Inline Mini Sparklines only if data loading and browser performance remain
  smooth for the full holdings list.

Watch-outs:

- Privacy mode: confirm whether tile area may encode private value. If not
  approved, use equal tile sizing while private values are hidden.
- Avoid one-note color palettes; use trading-specific green/red/yellow/neutral
  semantics consistently.
- Do not claim chart parity for mini sparklines.

Suggested tests:

- dashboard contract for heatmap container and modes;
- browser or screenshot validation if the panel uses canvas/SVG.

### 5. MP-NX5 Symbol Review Timeline

Implementation approach:

- Prefer service/API support if prior snapshots are not already available to the
  browser.
- Keep timeline event labels factual: status changed, trend changed, guidance
  changed, P&L moved.
- Add timeline to existing detail overlay rather than a separate modal.
- Add Watchlist / Opportunity Bridge only if stable watchlist/opportunity data
  contracts already exist or are explicitly authorized.

Watch-outs:

- Prior snapshots may contain stale or partial syncs. Present those states
  honestly.
- Avoid overloading the detail overlay; use collapsible sections if needed.
- Do not introduce a new opportunity ranking methodology inside this milestone.

Suggested tests:

- API/service tests for snapshot history query or diff contract;
- dashboard contract for timeline section and empty state.

### 6. MP-NX6 Owner Notes and Review Session Mode

Implementation approach:

- Design owner-authored persistence first. This is the first milestone in the
  sequence likely to require schema/API work.
- Notes should include provenance: created_at, updated_at, optional reviewed_at,
  and clear owner-authored markers.
- Review Session Mode should use existing filters/action queue as its input.

Watch-outs:

- Notes must never alter ATHENA evidence, scoring, or generated guidance.
- Do not auto-generate recommendations from owner notes.
- This milestone may need an ADR if persistent owner workflow state changes
  architecture boundaries.

Suggested tests:

- persistence migration/repository tests;
- API auth/validation tests;
- dashboard flow tests for create/update/delete notes and review marks.

## Milestone Definition of Done

For every milestone:

- implementation matches the approved milestone only;
- focused tests pass;
- no frozen methodology or interpretation semantics changed;
- `docs/MILESTONES.md` status updated;
- `ATHENA_BRIEFING.md` repo map updated when new docs/modules are added;
- `IMPLEMENTATION_SUMMARY.md` updated with files changed, tests, risks, and
  owner-review status;
- final response includes only a consolidated commit message for the owner to
  run, unless the owner explicitly requested git operations.

## Suggested Next Owner Decision

Review and approve MP-NX2.

If accepted, authorize MP-NX3 only: Column Profiles, Pinned Rows, and Export
Profiles. Do not start MP-NX3 until MP-NX2 is approved.
