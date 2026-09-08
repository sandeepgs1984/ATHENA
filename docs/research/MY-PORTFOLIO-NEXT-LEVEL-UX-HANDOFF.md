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
- `src/athena/ops/symbol_validate.py`
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

## Operational note (2026-09-08) — session header and HFCL/BSE

Not an MP-NX milestone. One stale name was pinning the market-session
header and aborting Portfolio Sync refresh.

- Header copy is presentation-only: group `price_as_of` by IST date and
  name lagging holdings. `summary.market_data_through` remains the min.
- Refresh must not raise on a single Kite catalog miss. Skip the miss,
  ingest the rest.
- Kite `kite.json` stays `exchange: NSE`. If a holding is missing on NSE
  but present on BSE (HFCL), remap `NSE:SYMBOL` → `BSE:SYMBOL` and ingest
  BSE. Timeline/history will treat the two ids as different keys.
- Holdings upload preview: when the local index has exactly NSE + BSE for
  the same tradingsymbol, resolve to BSE (`BSE_EXCHANGE_FALLBACK`) instead
  of `AMBIGUOUS_SYMBOL`. Broker `RAJESHEXPO` maps to `NSE:RAJESHEXPO-BZ`
  (`SERIES_SUFFIX_FALLBACK`) when that is the only equity-series listing.
  Three-or-more listings stay ambiguous. Names that are not in the local
  index at all stay UNRESOLVED at preview and still use the BSE catalog
  fallback at confirm.
- Live LTP on this page still needs a separate ADR. Do not add it here.
- Dashboard assets: `9.202.0` after MP-NX6 Owner Notes (form at the bottom of the holding-detail overlay). Risk concentration and Portfolio heatmap start collapsed. Morning triage actions scroll Current Holdings into view.
- Current Holdings scroll: the table grows with every symbol. Update
  Holdings / Recent Imports come after the last row. No inner vertical
  scroller. Bind `#my-portfolio-holdings-table` for profile chrome.
  Column headers live in a sticky dock under the card header.
- Risk concentration: 4-column grid; rank values nowrap; long symbols
  ellipsize instead of wrapping into the next column.
- Same-symbol NSE→BSE remaps are `Listing remapped`, not REMOVED.
- Review timeline formats P&L % / money and stacks long guidance.

## Complete 14-Feature Coverage Checklist

The roadmap intentionally covers all 14 owner-discussed next-level UX ideas:

- Portfolio Command Dashboard: MP-NX1 — Owner/Chief Architect approved and closed 2026-09-07.
- Action Queue View: MP-NX1 — Owner/Chief Architect approved and closed 2026-09-07.
- Column Profiles: MP-NX3 — Owner/Chief Architect approved and closed 2026-09-08.
- Portfolio Heatmap: MP-NX4 — Owner/Chief Architect approved and closed 2026-09-08.
- Symbol Detail Review Timeline: MP-NX5 — Owner/Chief Architect approved and closed 2026-09-08.
- Change Since Last Sync: MP-NX2 — Owner/Chief Architect approved and closed 2026-09-07.
- Risk Concentration Panel: MP-NX2 — Owner/Chief Architect approved and closed 2026-09-07.
- Watchlist / Opportunity Bridge: MP-NX5 — skipped; no stable My Portfolio opportunity contract.
- Notes / Owner Override Layer: MP-NX6 — Owner Notes implemented 2026-09-08, pending owner review.
- Review Session Mode: later NX6 slice — not started.
- Pinned Rows: MP-NX3 — Owner/Chief Architect approved and closed 2026-09-08.
- Smart Filters: MP-NX1 — Owner/Chief Architect approved and closed 2026-09-07.
- Inline Mini Sparklines: MP-NX4 — not shipped; snapshot rows have no D1 close series.
- Export Profiles: MP-NX3 — Owner/Chief Architect approved and closed 2026-09-08.

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

Owner/Chief Architect approved and closed 2026-09-07.

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

Owner/Chief Architect approved and closed 2026-09-08.

What shipped:

- Table profiles in `08b-my-portfolio.js`: Compact Scan, P&L Review,
  Technical Review, Risk Review, Full Audit. Each sets columns, default
  sort, and density. Active profile is stored in
  `athena.myPortfolio.tableProfile`.
- Owner-pinned rows via the thumbtack in Actions. Pins stay visible
  across sort/filter and are labeled `Pinned` as owner-authored, not
  ATHENA conviction. Stored in `athena.myPortfolio.pinnedInstrumentIds`.
- Export profiles Daily Review, Full Audit, and Private Sharing on the
  existing selected-column export contract. Table profile state stays
  separate from export column state.
- Dashboard asset version `9.189.0`. Screenshot correction: each profile
  table is locked to visible-column widths, hidden columns collapse so
  they cannot sit under sticky Symbol, Technical/Risk snap padding is
  No.+Symbol only, switching profile resets horizontal scroll, and the
  Current Holdings header row stays pinned while scrolling.

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

Owner/Chief Architect approved and closed 2026-09-08.

What shipped:

- Heatmap panel between Risk Concentration and Current Holdings.
- Size by Current value or Investment over latest snapshot rows.
- Color by existing P&L %, Status, Daily Review, Trend, or Next Action.
- Tile click opens the existing detail overlay.
- Privacy: equal tile size, no money labels, P&L % color muted.
- Inline Mini Sparklines not shipped: snapshot rows have no D1 close series
  and this milestone does not authorize a new history fetch.
- Dashboard asset version `9.191.0`.
- Risk Concentration and Heatmap have Hide/Show toggles, default collapsed.

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

Owner/Chief Architect approved and closed 2026-09-08.

What shipped:

- Review timeline inside the existing holding detail overlay, after Since last sync.
- `GET /api/v1/my-portfolio/snapshot/timeline?instrument_id=…` over up to 8
  recent SUCCESS/PARTIAL snapshots that already have rows.
- Factual events from existing `snapshot_diff` fields plus timeline-only Last Price.
- Partial syncs labeled honestly; privacy masking reused for money fields.
- Watchlist / Opportunity Bridge skipped: `watchlist/` is strategy/scan
  membership, not a My Portfolio opportunity contract. No new ranking.
- Dashboard asset version `9.192.0`.

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

Owner Notes implemented 2026-09-08. Ready for Owner / Chief Architect review.
Review Session Mode is a later slice and is not started.

What shipped (Owner Notes only):

- `portfolio_holding_notes` (schema 19) + `OwnerHoldingNote`.
- Per-holding thesis / watch_condition / reminder / review_comment / follow_up.
- Provenance `{"source": "owner", "authored": true}`. Empty notes are deleted.
- Notes follow NSE→BSE remaps (dest note wins). Deleted with holding, confirm
  REMOVED, and My Portfolio reset.
- `GET /api/v1/my-portfolio/notes`, `GET/PUT/DELETE /notes/{instrument_id}`.
- Detail overlay Owner note form at the bottom, after Structural Review; Note / Follow-up list chips.
- Dashboard asset version `9.202.0`. No ADR — same My Portfolio SQLite store.

What did not ship:

- Review Session Mode (reviewed today / defer / one-holding-at-a-time).
- Notes on snapshot rows as ATHENA fields.
- Any change to Status, scores, guidance, conviction, or interpretation versions.

Watch-outs:

- Notes must never alter ATHENA evidence, scoring, or generated guidance.
- Do not auto-generate recommendations from owner notes.
- Do not start Review Session Mode until this Owner Notes slice is approved.

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

Review and approve MP-NX6 Owner Notes.

If accepted, authorize Review Session Mode as a later NX6 slice. Do not start
that slice until Owner Notes is approved.
