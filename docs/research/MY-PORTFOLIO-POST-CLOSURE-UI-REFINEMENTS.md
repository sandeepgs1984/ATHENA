# My Portfolio Post-Closure UI Refinements

Date: 2026-09-06

Owner request: improve My Portfolio usability after the Portfolio track closure without reopening Portfolio Intelligence methodology.

## Scope

- Add a `No.` column to Current Holdings for visible serial numbering.
- Add Excel-like sorting controls for Current Holdings.
- Add a complete My Portfolio reset action.
- Clarify the Upload / Update Holdings flow so preview, confirmation, and cancellation are visually distinct.
- Remove the post-upload confusion where the preview/confirm controls appeared below the fold and the owner had to manually run Sync Portfolio after confirming.
- Make the uploaded-file preview modal-first so row quality and reconciliation are immediately visible after parsing.
- Make manual `Sync Existing Holdings` feel like a full-portfolio recalculation by blocking the whole app until sync and snapshot refresh complete.
- Improve Current Holdings scan quality with trading-oriented, presentation-only indicators for P&L, price-vs-average, Conviction, Trend, Setup, Plan Levels, and Freshness.
- Correct the symbol detail overlay so each newly opened holding starts at the top rather than inheriting the previous modal scroll position.
- Correct the Sync Existing Holdings blocker so it is viewport-owned and visible even when Current Holdings is below the fold.
- Redesign the My Portfolio page into a trading-workstation hierarchy without changing any feature behavior: command center, status banner, KPI strip, holdings workbench, then secondary update/audit panels.
- Redesign the holding detail overlay with professional trading visual hierarchy: section accents, row icons, signed value tones, directional chips, and differentiated guidance callouts.
- Add the next professional workstation polish slice: integrated sticky holdings context, Current Holdings view controls, row-state rails, softer unavailable chips, collapsed Recent Imports audit panel, and an at-a-glance detail overlay summary band.
- Correct screenshot-review findings from 2026-09-07: quick-context backdrop bleed, cramped Recent Imports show/hide placement, shallow Compact scan / Full review behavior, and the floating quick-context strip visually fighting scrolled table rows.
- Add a screen-sharing privacy mode that hides private portfolio values on demand.
- Correct screenshot-review findings from 2026-09-07: privacy masks must not expose visible/searchable `Hidden` text, and the Current Holdings quick context must remain part of a refined sticky workbench header rather than scrolling like a loose table row.

## Decisions

- Sorting is client-side presentation state only. It does not mutate holdings, snapshots, imports, or analysis output.
- Serial numbers follow the visible sorted order.
- Default sorting is P&L % high to low, matching the owner's prior spreadsheet review habit.
- Reset is destructive but isolated to the My Portfolio subdomain: holdings, import previews/history, reconciliation audit, sync runs, and analysis snapshots.
- Reset does not touch Decisions, owner candidates, journal/trade data, Kite configuration, or the legacy owner-position ledger.
- Reset is blocked while Portfolio Sync is active.
- Upload remains a three-step staged flow: choose file, review preview, confirm update.
- The upload panel is now the primary workflow block above summary metrics. Summary cards are read-only results, not the place where a pending upload is confirmed.
- The detailed preview modal opens automatically after upload parsing finishes. The inline upload card remains a compact status/control strip.
- Confirming an upload runs Portfolio Sync automatically after the holdings replacement succeeds. The header sync button remains available only as an explicit refresh for existing holdings.
- Portfolio Sync uses a full-viewport blocker for manual sync, upload-confirm sync, and edit/delete-triggered sync. It is dismissed only after the sync reaches a terminal state and the visible snapshot refresh has completed.
- The sync blocker is mounted at top-level document scope, not inside Current Holdings, so it always covers the visible app.
- The holding detail overlay resets its internal scroll position on every open.
- Detailed preview/reconciliation tables remain available in an `Upload Preview` overlay after the inline counts and issue chips identify whether attention is needed.
- Table colors and icons are presentation-only affordances over existing values. They do not change Status, Conviction, D1 Trend, Opening Range Setup, Daily Review, Next Action, TradePlan, Structural Review, or any Portfolio snapshot semantics.
- The page hierarchy is presentation-only. The Current Holdings table is the primary daily-work surface; upload/import history are operational/audit surfaces and therefore sit below the trading workbench.
- Detail-overlay colors, icons, and chips are presentation-only. They describe the already-computed position, technical, daily-review, TradePlan, and structural-review values; they do not introduce new classifications or trading rules.
- View mode, sticky holdings context, row-state rails, and collapsed Recent Imports are browser presentation state only. They do not persist, reorder stored holdings, or change sync/import/audit semantics.
- Compact scan mode intentionally hides lower-priority audit columns (`Avg Price`, `Plan Levels`, and `Freshness`) from the main holdings grid so the daily trading scan path stays readable. Full review mode restores the complete table.
- Privacy mode is client-side presentation state only. It masks private exposure/performance values in the browser and never changes stored holdings, import records, snapshots, Portfolio Sync output, or API payloads.
- Privacy mode persists only as a local browser preference under `athena.myPortfolio.valuesHidden`.

## Implementation Notes

- Current Holdings now has a sticky `No.` column before Symbol.
- The holdings toolbar supports sorting by P&L %, P&L, Conviction, Next Action, Status, Trend / Setup, Qty, Avg Price, Last Price, Symbol, and Daily Review.
- Column headers also show the active sort indicator and can be clicked to sort.
- The upload card now explicitly says that upload creates a preview first and holdings change only after confirmation.
- The preview-open action is labeled `Upload Preview` and the discard action is labeled `Discard Upload`, matching the uploaded-file workflow rather than generic preview/cancel language.
- Alerts are rendered inside the upload card, directly above the three-step flow, so row-quality warnings and confirm/sync completion messages stay attached to the action that produced them.
- The visible preview summary shows total rows, accepted rows, skipped rows, duplicate rows, and the first few row issues inline before the confirm action.
- Full row-quality and reconciliation detail opens in a large modal overlay, so the owner can inspect the uploaded file without scrolling below the fold or losing the confirm/discard action context.
- The row-quality/reconciliation modal now opens immediately after a successful preview response, eliminating the hidden-below-the-fold discovery problem.
- `Confirm Portfolio Update` became `Confirm & Sync Portfolio`; the action confirms the import, reloads canonical holdings, and starts the existing Portfolio Sync pipeline in one user gesture.
- The manual header action was renamed from `Sync Portfolio` to `Sync Existing Holdings` to distinguish it from the upload confirmation flow.
- The duplicate header file-picker was removed. File selection now appears only inside `Update Holdings`; the header contains page-level actions only.
- `Sync Existing Holdings` now activates a full-app blocking overlay with progress text and scroll lock until the recalculation and snapshot refresh finish.
- The full-app blocker is outside the Current Holdings section in the DOM and also locks the workspace scroll container.
- The Current Holdings sort toolbar now has explicit header spacing and a wider selector so focus rings/buttons do not overlap the title or sort summary.
- Current Holdings now colors positive P&L/returns green and negative P&L/returns red, marks Last Price green/red relative to Avg Price, renders Conviction as a pill, renders Trend / Setup as directional chips, adds Plan Level icons, and adds a Freshness clock indicator.
- The tapped-holding detail overlay is wider and section-framed, with roomier grids, value spacing, guidance callouts, and reason-list line-height for easier scanning.
- Opening a different holding detail always resets the modal body and container scroll position to the top.
- The page now uses a professional trading-workstation layout: compact command center, global status banner, a four-card KPI strip led by Current Value and Total P&L, a compact freshness strip for Latest Import/Last Synced metadata, primary Current Holdings workbench, and a secondary two-column operations area for Update Holdings and Recent Imports.
- The detail overlay now uses section-level visual hierarchy: Position, Technical State, ATHENA Review, Plan / Levels, and Structural Review / Levels each get a subtle section accent; field labels get purpose-specific icons; positive P&L and favorable price context render green, negative values render red, warning/trigger fields render amber, and neutral unavailable fields stay muted.
- D1 Trend, Opening Range Setup, and SuperTrend direction now render as compact directional chips inside the detail overlay, matching the main table's trading scan language while remaining separate from methodology semantics.
- Daily Guidance, Structural Guidance, and raw-context notes are differentiated by callout tone so the user can scan recommendation, structural context, and caveat text without reading the whole modal linearly.
- The My Portfolio workstation now keeps the quick-context summary inside the sticky Current Holdings header, showing current value, total P&L, last synced time, and active sort while the user scrolls deeper into holdings without overlaying table rows.
- Current Holdings now supports separate Compact scan and Full review view modes. Compact scan hides `Avg Price`, `Plan Levels`, and `Freshness` columns and keeps secondary text one-line for a focused trading scan. Full review restores every column with wider table rhythm, roomier cells, and multi-line summaries. The toggle is never persisted into portfolio state.
- Holding rows now carry a thin left state rail derived from existing row values: positive/healthy rows, warning/watch rows, danger/exit/review rows, and muted unavailable rows.
- Unavailable table placeholders use muted chips instead of large repeated text, reducing noise while preserving truthfulness.
- Recent Imports is collapsed by default as a secondary audit surface and can be expanded on demand.
- The holding detail overlay now opens with an at-a-glance summary band containing the symbol, quantity/average, last price tone, P&L %, Status, Next Action, D1 Trend, and SuperTrend direction.
- The holdings context now has a stronger opaque blur/isolation layer and is anchored inside the Current Holdings sticky header so table rows do not visually bleed through while scrolling.
- Recent Imports now uses a dedicated header action lane with minimum button width, keeping Show/Hide separated from the title and audit description.
- Comfortable mode widens Daily Review, Trend / Setup, Plan Levels, and Freshness rhythm while Compact mode keeps the scan path tight.
- Update Holdings and Recent Imports now have more breathing room between section title and explanatory subtitle.
- Sort controls and view-mode controls are visually separated so `Default` reads as a sort reset, while Compact scan / Full review read as table view presets rather than extra filters.
- Screenshot-review follow-up: dashboard asset version advanced to `9.174.0`; dashboard contract tests assert the integrated sticky holdings context, separated Sort/View controls, Compact scan column hiding, and compact scroll-snap padding.
- The My Portfolio header now includes an eye / eye-slash privacy toggle. When active, it masks private quantity, average price, last price, investment, current value, total investment, total current value, P&L, and P&L % values across KPIs, the holdings grid, quick holdings context, edit/delete confirmations, and the holding detail overlay while preserving analysis signals and actions.
- Privacy-mode pass: dashboard asset version advanced to `9.175.0`; dashboard contract tests assert the privacy toggle, local browser preference key, masked-value rendering primitive, and private formatter helpers.
- Privacy/sticky-header correction pass: dashboard asset version advanced to `9.176.0`; masked private values now render as visual bars without visible `Hidden` text, text-only privacy slots use bullets, and the Current Holdings sticky header is a two-row workbench header with title/summary, separated Sort/View controls, and an integrated full-width context strip.
- Full reset is gated by a modal requiring the exact `RESET` token.

## Methodology Boundary

No Portfolio interpretation, Daily Review, Structural Review, Status, Conviction, Trend, Setup, Next Action, EntryQualification, TradePlan, or evidence methodology changed.

## Review Status

Implementation complete and ready for Owner / Chief Architect review.

Focused validation:

- My Portfolio API tests: 68 passed.
- Dashboard hosting / release-gate tests: 13 passed.
- Combined focused pytest: 81 passed.
- `node --check src/athena/api/static/js/08b-my-portfolio.js`: passed.
- Ruff: passed on touched API/test Python files; `repository.py` passed with the repository's pre-existing SIM117 baseline ignored.
- Second-pass upload-first / confirm-and-sync validation: combined focused pytest 81 passed; JS syntax check passed; ruff passed.
- Detail-overlay visual hierarchy pass: dashboard asset version advanced to `9.170.0`; dashboard contract tests assert the detail chip/tone/callout primitives.
- Workstation polish pass: dashboard asset version advanced to `9.171.0`; dashboard contract tests assert sticky context, density controls, row rails, collapsed audit panel, unavailable chips, and detail hero primitives.
- Screenshot-review correction pass: dashboard asset version advanced to `9.172.0`; dashboard contract tests assert quick-context backdrop opacity/blur, Recent Imports action spacing, and distinct compact-vs-comfortable table behavior.
- Header-spacing polish: dashboard asset version advanced to `9.173.0`; dashboard contract tests assert scoped title/subtitle spacing for Update Holdings and Recent Imports.
- Compact scan correction pass: dashboard asset version advanced to `9.174.0`; dashboard contract tests assert the quick context is anchored in the sticky holdings header, Sort and View controls are separate, Compact scan hides lower-priority columns, and Full review keeps the complete table available.
- Privacy-mode pass: dashboard asset version advanced to `9.175.0`; dashboard contract tests assert the eye/eye-slash control, local preference key, masked-value primitive, and private value formatter helpers.
- Privacy/sticky-header correction pass: dashboard asset version advanced to `9.176.0`; dashboard contract tests assert no visible `Hidden` text in masked tokens and assert the refined sticky holdings header structure.
- Targeted mypy: not a clean gate because `my_portfolio_service.py` has pre-existing broad typing debt unrelated to this change.
