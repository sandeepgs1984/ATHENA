# PS-P3 My Portfolio Dashboard + Upload UX

Status: Owner/Chief Architect approved 2026-09-02
Date: 2026-09-02
Scope: Owner-facing My Portfolio tab, upload preview UX, reconciliation review,
confirmation UX, current holdings table, and import history
Boundary: No Portfolio Sync orchestration, no market analysis, no P&L, no
portfolio methodology change, no order placement

## 1. Executive Summary

PS-P3 adds a first-class My Portfolio dashboard surface over the PS-P2 backend
contracts. The owner can upload a CSV/XLSX holdings file, review backend-parsed
rows, inspect reconciliation changes, confirm a clean preview, and view
canonical current holdings plus import history.

The existing Portfolio Overview / owner fill ledger remains separate. My
Portfolio is a current-holdings snapshot feature, not a trade journal and not a
replacement for the owner-entered fill ledger.

## 2. Implemented Scope

Implemented:

- Separate sidebar tab and route: `/dashboard/my-portfolio`.
- Upload / Update Holdings file control for CSV/XLSX files.
- Server-side preview call to `POST /api/v1/my-portfolio/imports`.
- Preview summary counts for total, valid, invalid, unresolved, ambiguous, and
  duplicate rows.
- Preview rows table with mapping state and validation details.
- Reconciliation diff table for ADDED, UPDATED, REMOVED, and UNCHANGED changes.
- Explicit Confirm Portfolio Update action.
- Stale-preview 409 messaging and Upload Again recovery.
- Canonical holdings table with Symbol, Qty, Avg Price, Investment, Imported At,
  and Source Import.
- Import history table with upload timestamp, filename, status, row counts, and
  confirmation timestamp.
- Static dashboard regression tests.

## 3. Out-of-Scope Items

Not implemented in PS-P3:

- Portfolio Sync analysis orchestration.
- Last price, current value, unrealized P&L, P&L %, conviction, setup, support,
  target, next action, or review status.
- Any ScoringEngine, DecisionEngine, indicator, or methodology changes.
- Any order-placement or broker execution code.
- A blank upload workaround to remove all holdings.

## 4. Dashboard Placement

My Portfolio is added as a sibling tab beside the existing Portfolio Overview,
Market, Strategies, Decisions, and Operations tabs. The tab uses its own
dashboard pane and JS module.

This preserves the older Portfolio Overview workflow for owner-entered fills,
reset fills, capital pools, NAV, and sector exposure.

## 5. Routing Contract

The SPA route whitelist now includes `my-portfolio`, so reloads and browser
back/forward navigation preserve `/dashboard/my-portfolio`.

Fresh login behavior remains unchanged: an explicit login still resets to
Portfolio Overview.

## 6. Static Assembly Contract

The dashboard JS assembly list now includes:

```text
08b-my-portfolio.js
```

The dashboard CSS manifest now imports:

```text
css/05b-my-portfolio.css
```

This follows the existing concern-split pattern without replacing the served
`/dashboard/dashboard.js` or `/dashboard/dashboard.css` routes.

## 7. API Usage

The UI calls only PS-P2 APIs:

- `GET /api/v1/my-portfolio/holdings`
- `GET /api/v1/my-portfolio/imports`
- `POST /api/v1/my-portfolio/imports?filename=...`
- `POST /api/v1/my-portfolio/imports/{import_id}/confirm`

There is no client-side CSV or XLSX parser. The browser uploads raw file bytes
and renders the backend preview contract.

## 8. Upload UX

The upload action uses the native file input for keyboard accessibility while
presenting an ATHENA-styled Upload / Update Holdings control. The selected
filename is shown next to the upload panel.

The panel states are:

- no file selected
- uploading/parsing on the server
- preview ready
- confirming
- success
- error

## 9. Required Columns

The UI explicitly names the required logical fields:

```text
Symbol, Qty, Avg Price
```

Alias resolution remains backend-owned per PS-P2. The browser does not inspect
headers or rows before upload.

## 10. Preview Summary

The preview summary renders:

- total rows
- valid rows
- invalid rows
- unresolved rows
- ambiguous rows
- duplicate rows

Duplicate count is derived from backend row validation errors containing
`DUPLICATE_CANONICAL_INSTRUMENT`; no new frontend-only duplicate rule is
introduced.

## 11. Preview Rows

Each preview row shows:

- source row ID
- raw symbol
- resolved instrument or candidates
- quantity
- average price
- mapping state
- validation state / error text

Status is represented with text and iconography, not color alone.

## 12. Mapping States

The UI distinguishes:

- `RESOLVED`
- `UNRESOLVED`
- `AMBIGUOUS`

Unresolved and ambiguous rows prevent confirmation through the backend contract
and through the disabled Confirm Portfolio Update button.

## 13. Validation States

Rows with validation errors are shown as Invalid or Duplicate, with backend
error strings preserved for auditability. Rows with warnings are shown as
Warning and still expose the backend warning text.

## 14. Confirmation Gate

Confirmation is available only when the preview is:

- status `PREVIEWED`
- zero rejected rows
- zero unresolved rows
- zero ambiguous rows
- zero duplicate rows
- no row-level validation errors

The button label is the explicit safety action:

```text
Confirm Portfolio Update
```

## 15. Confirmation Copy

The dashboard states that confirmation replaces ATHENA's current My Portfolio
holdings with the uploaded snapshot. It also states that no trades or realized
P&L are inferred.

This protects the semantic boundary between current-holdings snapshots and
trade outcomes.

## 16. Reconciliation Diff

The reconciliation table shows:

- action
- instrument
- previous quantity
- new quantity
- previous average price
- new average price
- meaning

For `REMOVED`, the meaning is explicit: the instrument is absent from the
uploaded current-holdings snapshot, and no sale is inferred.

## 17. Stale Preview Handling

On stale-preview confirmation failure, the UI shows:

```text
Portfolio holdings changed after this preview was generated. Please generate a fresh preview before confirming.
```

The stale state does not auto-apply. The recovery path is Upload Again or
re-selecting the file to create a fresh preview against the latest canonical
holdings.

## 18. Current Holdings Table

The holdings table shows only factual PS-P2 data:

- Symbol
- Qty
- Avg Price
- Investment
- Imported At
- Source Import

`Investment` is server-owned per holding (`quantity * avg_price`) and exposed in
the API DTO. The dashboard sums these server-provided values for the header
total investment.

## 19. Freshness Display

PS-P3 shows factual import metadata only:

- latest confirmed import timestamp
- holdings-as-of when supplied by the backend

It does not fabricate market-data-through, last-synced, or analysis freshness
before Portfolio Sync exists.

## 20. Future Snapshot Readiness

The PS-P1 20-column snapshot contract remains the future shape for Portfolio
Sync output. PS-P3 deliberately renders a narrower factual holdings table
because the analysis-backed columns do not exist yet.

The table uses horizontal scrolling and sticky leading columns so the later
wide snapshot can be introduced without changing the overall interaction
pattern.

## 21. Empty States

When no holdings exist, the dashboard shows:

```text
No holdings imported yet. Upload Portfolio to begin.
```

When no history exists, it shows a separate import-history empty state.

## 22. Blank Upload Limitation

PS-P2 rejects blank/zero-row uploads. PS-P3 does not work around that limitation
client-side and does not provide a hidden "remove all holdings" path.

A future Clear Portfolio feature should be explicit, confirmation-gated, and
implemented as its own milestone.

## 23. Accessibility Notes

PS-P3 uses:

- native file input semantics
- disabled button states for unavailable actions
- table headers for tabular data
- focus return to upload after clearing a preview
- non-color-only status labels

No modal or drawer was introduced, so no additional focus trap is required.

## 24. Test Evidence

Verified:

- dashboard static hosting and My Portfolio tab contract
- dashboard chart release-gate cache version
- PS-P1 contract/schema/DTO regressions
- PS-P2 parser/import/API regressions

Targeted command results:

```text
rtk pytest tests/api/platform/test_dashboard_hosting.py::test_my_portfolio_dashboard_tab_contract tests/api/platform/test_dashboard_hosting.py::test_dashboard_static_hosting_and_fallback tests/api/platform/test_decision_chart_release_gate.py
=> 7 passed

rtk pytest tests/runtime/test_my_portfolio_imports.py tests/runtime/test_my_portfolio_contracts.py tests/data_layer/test_my_portfolio_schema.py tests/api/v1/test_my_portfolio_dtos.py tests/api/v1/test_my_portfolio_import_api.py
=> 25 passed
```

## 25. Risks, Debt, and Recommended Next Milestone

Risks / debt:

- PS-P3 has static dashboard coverage but no browser screenshot or interaction
  automation yet.
- Import history remains intentionally minimal until deeper audit drill-down is
  requested.
- Clear Portfolio is intentionally absent.

Recommended next milestone:

```text
PS-P4 Portfolio Sync Orchestration
```

PS-P4 should analyze confirmed My Portfolio holdings through ATHENA's existing
data/advisory pipeline and populate the PS-P1 snapshot contract without
changing the existing scoring methodology.
