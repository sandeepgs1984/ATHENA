# My Portfolio Export Options

Date: 2026-09-07

## Objective

Add production-ready export options to the My Portfolio tab so the owner can
download ATHENA's server-owned portfolio state without manually copying table
data or reconstructing values from the browser.

## Scope

- Add a read-only My Portfolio export endpoint.
- Support CSV, XLSX, and JSON formats.
- Support Latest analyzed snapshot, Confirmed holdings, and Import history
  export scopes.
- Add a compact Export action to the My Portfolio command center.
- Add advanced selected-column export options with deterministic server-side
  column validation.
- Keep exports explicit that they include private portfolio values even when
  screen privacy masking is enabled.

## Decisions

- Exports are read-only projections over existing persisted My Portfolio state.
- Exports never run Portfolio Sync, never recalculate Portfolio Intelligence,
  and never mutate holdings, imports, sync runs, snapshots, or methodology.
- Latest analyzed snapshot export requires an existing completed Portfolio Sync
  snapshot. Confirmed holdings and Import history can export without a completed
  snapshot.
- CSV is for quick spreadsheet import, XLSX is for owner review workflows, and
  JSON is for machine-readable audit/detail.
- Export formatting is server-owned. The browser only requests a scope/format
  and downloads the returned artifact.
- Selected-column export uses stable column IDs. Unknown column IDs fail loudly;
  duplicate IDs collapse in request order; omitting `columns` preserves the full
  export.

## Implementation Notes

- `GET /api/v1/my-portfolio/export?scope=snapshot|holdings|imports&format=csv|xlsx|json`
  returns a downloadable file with explicit `Content-Disposition`.
- `columns=<comma-separated-column-ids>` optionally narrows CSV, XLSX, and JSON
  exports to the selected owner-visible columns.
- Snapshot CSV/XLSX flattens the current Portfolio Snapshot row contract plus
  Daily Review and Structural Review fields into owner-readable columns.
- Holdings CSV/XLSX exports canonical confirmed holdings only.
- Import-history CSV/XLSX/JSON exports the latest import audit summaries.
- Selected-column JSON returns a table-style payload with scope, column
  metadata, and row objects keyed by selected column ID; full JSON export remains
  the native source DTO payload.
- XLSX generation uses a minimal deterministic OpenXML workbook with a frozen
  header row and no external runtime dependency.
- The dashboard Export popover contains Dataset and Format selectors, a
  private-values notice, status feedback, advanced column checkboxes, Essential
  and Review presets, All/Clear actions, and one Download Export action.

## Methodology Boundary

No Portfolio methodology, evidence primitive, interpretation version, snapshot
schema, Daily Review logic, Structural Review logic, Status, Conviction, Trend,
Setup, Next Action, or TradePlan semantics changed.

## Validation

- `node --check src/athena/api/static/js/08b-my-portfolio.js`: PASS.
- `rtk pytest tests/api/v1/test_my_portfolio_import_api.py tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py`: PASS, 89 tests.
- `rtk uv run ruff check src/athena/api/v1/routers/my_portfolio.py src/athena/api/v1/services/my_portfolio_service.py tests/api/v1/test_my_portfolio_import_api.py tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py`: PASS.

## Status

Owner approved 2026-09-07. Export options and advanced selected-column exports
are closed for this milestone.
