# My Portfolio Post-Closure UI Refinements

Date: 2026-09-06

Owner request: improve My Portfolio usability after the Portfolio track closure without reopening Portfolio Intelligence methodology.

## Scope

- Add a `No.` column to Current Holdings for visible serial numbering.
- Add Excel-like sorting controls for Current Holdings.
- Add a complete My Portfolio reset action.
- Clarify the Upload / Update Holdings flow so preview, confirmation, and cancellation are visually distinct.
- Remove the post-upload confusion where the preview/confirm controls appeared below the fold and the owner had to manually run Sync Portfolio after confirming.

## Decisions

- Sorting is client-side presentation state only. It does not mutate holdings, snapshots, imports, or analysis output.
- Serial numbers follow the visible sorted order.
- Default sorting is P&L % high to low, matching the owner's prior spreadsheet review habit.
- Reset is destructive but isolated to the My Portfolio subdomain: holdings, import previews/history, reconciliation audit, sync runs, and analysis snapshots.
- Reset does not touch Decisions, owner candidates, journal/trade data, Kite configuration, or the legacy owner-position ledger.
- Reset is blocked while Portfolio Sync is active.
- Upload remains a three-step staged flow: choose file, review preview, confirm update.
- The upload panel is now the primary workflow block above summary metrics. Summary cards are read-only results, not the place where a pending upload is confirmed.
- Confirming an upload runs Portfolio Sync automatically after the holdings replacement succeeds. The header sync button remains available only as an explicit refresh for existing holdings.
- Detailed preview/reconciliation tables remain available, but they are collapsed behind `Preview Details` after the inline counts and issue chips identify whether attention is needed.

## Implementation Notes

- Current Holdings now has a sticky `No.` column before Symbol.
- The holdings toolbar supports sorting by P&L %, P&L, Conviction, Next Action, Status, Trend / Setup, Qty, Avg Price, Last Price, Symbol, and Daily Review.
- Column headers also show the active sort indicator and can be clicked to sort.
- The upload card now explicitly says that upload creates a preview first and holdings change only after confirmation.
- Cancel is labeled as `Discard Preview` to avoid confusion with page-level cancel semantics.
- Alerts are rendered inside the upload card, directly above the three-step flow, so row-quality warnings and confirm/sync completion messages stay attached to the action that produced them.
- The visible preview summary shows total rows, accepted rows, skipped rows, duplicate rows, and the first few row issues inline before the confirm action.
- `Confirm Portfolio Update` became `Confirm & Sync Portfolio`; the action confirms the import, reloads canonical holdings, and starts the existing Portfolio Sync pipeline in one user gesture.
- The manual header action was renamed from `Sync Portfolio` to `Sync Existing Holdings` to distinguish it from the upload confirmation flow.
- The duplicate header file-picker was removed. File selection now appears only inside `Update Holdings`; the header contains page-level actions only.
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
