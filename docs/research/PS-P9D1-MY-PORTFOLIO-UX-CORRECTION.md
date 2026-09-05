# ATHENA — PS-P9D.1 My Portfolio UX Correction

Owner screenshot review date: 2026-09-05

## Scope

PS-P9D.1 fixes owner-visible My Portfolio dashboard issues observed after the
PS-P9D Opening Range Setup adapter freeze.

This is a presentation and workflow-state correction only. It does not change
Portfolio methodology, `PortfolioSetupAdapter`, `OpeningRangeEngine`, schema,
API contracts, interpretation rules, reason-code semantics, Decision,
EntryQualification, Scoring, TradePlan, broker behavior, or order placement.

## Screenshot Issues Found

1. Current Holdings table cells visually collided because the 20-column table
   had insufficient width, incomplete fixed sizing, and sticky-column offsets
   that did not match the actual sticky column widths.
2. Upload confirmation controls were visible even when no active import preview
   existed, causing the panel to show `No file selected` while also presenting
   `Cancel` and `Confirm Portfolio Update`.
3. Portfolio Sync progress text reused the upload-state line, mixing Sync
   lifecycle state into the upload workflow instead of using the alert/status
   surface.
4. Status and Next Action cells rendered full reason explanations inline,
   making rows tall and noisy and pushing neighboring table content out of
   alignment.
5. Legacy `portfolio-interpretation-v2` snapshots could still render as plain
   `UPTREND`, making the screen look like PS-P9D Setup had not been applied
   even though historical snapshots remain immutable by design.
6. Date/time values were allowed to wrap inside narrow cells, creating broken
   visual strings such as `pmIST` or multi-line timestamps.
7. Empty money cells rendered as `₹ —`, which looked like an amount rather than
   an unavailable value and added visual clutter to dense rows.
8. The unsynced holdings fallback row needed to preserve the exact 20-column
   contract so sticky-column alignment stays deterministic before the first
   successful Portfolio Sync snapshot.
9. First-pass fixed columns still over-compressed headers and values, causing
   `Conviction`, money, date, and Trend / Setup content to truncate.

## Fixes

1. Bumped the dashboard asset cache key to `9.151.0` so Chrome loads the fixed
   static assets instead of the previous cached My Portfolio bundle.
2. Added a dedicated `my-portfolio-confirm-actions` node that remains hidden
   until an actual preview exists.
3. Kept Sync progress on the alert/status surface and stopped mutating the
   upload-state line during Sync polling.
4. Widened the My Portfolio table to a fixed 3380px layout, added an explicit
   `colgroup`, aligned sticky offsets to the first three column widths, and
   gave dense numeric/date/action columns deterministic widths.
5. Removed global cell clipping so owner values are visible on the horizontal
   scroll surface instead of being forced into truncated viewport-width cells.
6. Made sticky table columns opaque so horizontally scrolled cells cannot bleed
   through the frozen Symbol/Qty/Avg Price area.
7. Moved long Status/Next Action reason prose into native tooltips while
   keeping compact owner-facing pills visible in the grid.
8. Added compact nowrap rendering for money, percentages, date values, and
   Trend / Setup.
9. Rendered unavailable money values as `-`/dash semantics instead of
   currency-prefixed unavailable values.
10. Added legacy snapshot handling: non-v3 rows display as `TREND / legacy` and
   the page asks the owner to Sync Portfolio to regenerate v3 Trend / Setup
   evidence, without mutating historical snapshots.

## Validation

- `node --check src/athena/api/static/js/08b-my-portfolio.js`
- `rtk pytest tests/api/platform/test_dashboard_hosting.py`
- `rtk uv run ruff check tests/api/platform/test_dashboard_hosting.py`
- `rtk git diff --check`

## Owner Review Boundary

PS-P9D remains frozen. PS-P9D.1 is ready for Owner/Chief Architect review as a
UI correction only. PS-P10 and future Portfolio Intelligence work still require
explicit Owner direction.
