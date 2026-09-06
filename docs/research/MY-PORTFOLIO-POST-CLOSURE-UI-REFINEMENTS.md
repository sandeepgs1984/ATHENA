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
- Targeted mypy: not a clean gate because `my_portfolio_service.py` has pre-existing broad typing debt unrelated to this change.
