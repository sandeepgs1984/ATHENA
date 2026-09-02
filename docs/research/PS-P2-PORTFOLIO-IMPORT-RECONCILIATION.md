# PS-P2 Portfolio Import Preview & Reconciliation

Status: Owner/Chief Architect approved 2026-09-02
Date: 2026-09-02
Scope: Backend import preview, symbol resolution, reconciliation, confirmation,
canonical holdings, and audit history
Boundary: No dashboard tab, no Sync Portfolio orchestration, no market-analysis
refresh, no portfolio interpretation methodology

## 1. Executive Summary

PS-P2 implements the backend My Portfolio import/reconciliation workflow over
the PS-P1 contracts:

```text
CSV/XLSX upload
-> parse
-> normalize
-> validate
-> resolve symbols
-> persist preview
-> show reconciliation diff
-> confirm
-> atomically update canonical holdings
-> preserve audit history
```

The implementation keeps My Portfolio isolated under the existing `portfolio`
capability and leaves `owner_positions`, ScoringEngine, DecisionEngine,
indicators, dashboard UX, and Sync Portfolio analysis untouched.

## 2. Implemented Scope

Implemented:

- Generic CSV parser.
- Lightweight generic XLSX parser using standard-library ZIP/XML parsing.
- Deterministic logical-column mapping for Symbol, Qty, and Avg Price.
- Row-level validation for symbols, quantities, and average prices.
- Symbol resolution through existing `symbol_master` / `instruments` records.
- Persistent import previews with stable import IDs.
- Duplicate canonical instrument detection as validation errors.
- Deterministic reconciliation actions: ADDED, UPDATED, REMOVED, UNCHANGED.
- Atomic confirmation transaction with rollback on failure.
- Idempotent confirmation retry.
- Stale-preview protection using a canonical holdings digest.
- API endpoints for preview, detail, confirmation, holdings, import history, and
  reconciliation history.

## 3. Import Pipeline

The parser produces provider-independent rows before symbol resolution:

```text
request body bytes + filename
-> parse_holdings_file()
-> ParsedHoldingRow
-> resolve_preview_rows()
-> persisted portfolio_imports / portfolio_import_rows
-> reconciliation proposal vs current portfolio_holdings
```

The parser and resolver are separate. No uploaded file is treated as persistent
portfolio storage; only metadata, digest, original row values, normalized facts,
mapping results, and audit data are persisted.

## 4. CSV Contract

CSV support expects a header row and UTF-8/UTF-8-sig text. Blank rows are
ignored. Required logical fields are Symbol, Qty, and Avg Price, with aliases
listed in §6.

File-level CSV failures:

- `EMPTY_FILE`
- `MISSING_HEADER_ROW`
- `MISSING_REQUIRED_COLUMN:<field>`
- `DUPLICATE_LOGICAL_COLUMN:<field>`
- `UNREADABLE_CSV`
- `NO_DATA_ROWS`
- `ROW_LIMIT_EXCEEDED`

## 5. XLSX Contract

XLSX support reads the first non-empty worksheet in deterministic sheet-file
order and does not combine sheets. It supports shared-string and inline-string
cells plus numeric cells, which is sufficient for generic holdings exports.

File-level XLSX failures:

- `EMPTY_FILE`
- `MALFORMED_XLSX`
- `XLSX_NO_USABLE_SHEET`
- the same logical-column/data-row failures as CSV once a sheet is selected

No heavy spreadsheet framework was introduced.

## 6. Logical Column Mapping

Supported aliases:

| Logical field | Accepted names |
|---|---|
| Symbol | `symbol`, `ticker`, `trading symbol`, `tradingsymbol` |
| Qty | `qty`, `quantity`, `shares` |
| Avg Price | `avg price`, `average price`, `avg_price`, `average_price`, `buy price`, `avg cost` |

Header comparison lowercases text, converts underscores to spaces, strips
outer whitespace, and collapses internal whitespace. If more than one source
column maps to the same logical field, preview fails with
`DUPLICATE_LOGICAL_COLUMN:<field>`.

## 7. Row Validation

Row validation is independent per row.

Symbol:

- trimmed and uppercased
- blank symbols produce `BLANK_SYMBOL`

Qty:

- must be a positive integer
- blank, non-numeric, zero, negative, fractional, NaN, or infinity values
  produce `INVALID_QTY`

Avg Price:

- stored as `Decimal`
- blank, non-numeric, zero, negative, NaN, or infinity values produce
  `INVALID_AVG_PRICE`

## 8. Symbol Resolution

Resolution indexes existing ATHENA `symbol_master` and `instruments` rows.

Outcomes:

- `RESOLVED`: exactly one canonical instrument.
- `UNRESOLVED`: no canonical instrument.
- `AMBIGUOUS`: multiple legitimate candidates.

Raw `NSE:SYMBOL`-style input is accepted when it matches an existing canonical
instrument ID. Bare symbols resolve only when exactly one canonical candidate
exists. Ambiguity is exposed in preview metadata; no arbitrary candidate is
selected.

## 9. Duplicate Handling

Duplicate uploaded rows resolving to the same canonical `instrument_id` are not
merged and no weighted average is inferred. PS-P2 represents this as a row
validation error:

```text
DUPLICATE_CANONICAL_INSTRUMENT
```

The PS-P1 persisted enum set is unchanged; duplicate is an explicit validation
error on resolved rows, not a new mapping state.

## 10. Import Status Lifecycle

PS-P2 uses the PS-P1 enum values:

- `PREVIEWED`: parsed and persisted, confirmation may be possible.
- `FAILED`: file-level parse/mapping failure, no confirmation allowed.
- `CONFIRMED`: applied exactly once.
- `REJECTED`: reserved by contract; not used by PS-P2.

Confirmation requires a clean preview: no rejected, unresolved, ambiguous, or
duplicate rows.

## 11. Preview Persistence

Preview persists:

- import ID
- filename and source
- upload timestamp
- parser version
- status and row counts
- file SHA-256
- base holdings digest
- parser warnings/errors
- original row values
- normalized symbol, quantity, average price
- mapping state, resolved instrument, candidates, errors, warnings

The original raw file is not stored permanently.

## 12. Reconciliation Algorithm

Reconciliation compares uploaded resolved holdings with current
`portfolio_holdings` by canonical `instrument_id`.

| Existing | Uploaded | Action |
|---|---|---|
| absent | present | `ADDED` |
| present | present with changed Qty and/or Avg Price | `UPDATED` |
| present | absent | `REMOVED` |
| present | present with same Qty and Avg Price | `UNCHANGED` |

`REMOVED` means only "not present in the latest confirmed current-holdings
snapshot." It does not imply sell, exit date, exit price, realized P&L, trade
outcome, or a DecisionEngine result.

## 13. Stale Preview Protection

Each preview stores `base_holdings_digest`, a deterministic SHA-256 digest of
current canonical holdings at preview time. Confirmation recomputes the digest
inside the SQLite transaction. If it differs, confirmation raises
`STALE_PREVIEW` and the caller must create a fresh preview.

This prevents Import A, previewed on Portfolio V1, from overwriting Portfolio V2
after Import B has already been confirmed.

## 14. Confirmation Transaction

`SqliteRepository.confirm_portfolio_import()` performs one SQLite transaction:

1. Read and validate import state.
2. Reject missing, failed, invalid, or stale imports.
3. Rebuild uploaded holdings from persisted preview rows.
4. Compute reconciliation deterministically.
5. Insert reconciliation audit rows.
6. Insert/update ADDED and UPDATED holdings.
7. Delete REMOVED holdings.
8. Leave UNCHANGED holdings untouched.
9. Mark the import `CONFIRMED`.

If any step fails, SQLite rolls back the entire transaction. A trigger-backed
test proves a failure during audit insert leaves the import `PREVIEWED`, creates
no holdings, and creates no reconciliation rows.

## 15. Idempotency

If the same import is confirmed again after success:

- holdings are not applied twice
- reconciliation rows are not duplicated
- confirmation timestamp is not rewritten
- response returns `already_confirmed=true`

## 16. Repository Changes

Added repository support for:

- saving import previews and rows
- reading import detail/history
- listing canonical My Portfolio holdings
- retrieving one holding by instrument
- deterministic holdings digest
- atomic import confirmation
- reconciliation audit retrieval

Enum-valued writes validate through PS-P1 enum classes before persistence.

## 17. API Endpoints

Implemented:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/my-portfolio/imports?filename=...` | Upload CSV/XLSX bytes and create preview |
| `GET` | `/api/v1/my-portfolio/imports` | List import history |
| `GET` | `/api/v1/my-portfolio/imports/{import_id}` | Retrieve persisted preview/detail |
| `POST` | `/api/v1/my-portfolio/imports/{import_id}/confirm` | Confirm clean preview and apply holdings |
| `GET` | `/api/v1/my-portfolio/holdings` | Retrieve canonical holdings |
| `GET` | `/api/v1/my-portfolio/imports/{import_id}/reconciliations` | Retrieve reconciliation audit entries |

The upload endpoint accepts raw request bytes plus a `filename` query parameter
instead of requiring multipart form parsing. This avoids adding
`python-multipart` solely for PS-P2 while preserving CSV/XLSX upload semantics.

## 18. Error Semantics

API errors use ATHENA's existing Problem Details mapping:

- import not found: 404 `portfolio-import-not-found`
- stale preview: 409 `stale-portfolio-preview`
- invalid import/confirmation: 400 `portfolio-import-error`

Preview requests with file-level parse errors persist a `FAILED` import and
return a 400 response containing the preview payload and errors.

## 19. Auditability

After confirmation, ATHENA can reconstruct:

- which import changed holdings
- source filename and file digest
- upload and confirmation timestamps
- original row values
- normalized Symbol/Qty/Avg Price
- mapping state and resolved instrument
- prior canonical holding
- resulting canonical holding
- reconciliation action

Import rows and reconciliation entries are retained.

## 20. Test Coverage

Added coverage for:

- CSV canonical columns and aliases
- blank rows
- missing required columns
- unsupported extension
- invalid Qty and Avg Price values including NaN
- XLSX valid workbook and first usable sheet behavior
- malformed/empty XLSX
- resolved, unresolved, ambiguous, and duplicate symbol mappings
- preview persistence and no holdings mutation
- clean confirmation
- idempotent retry
- UPDATED/REMOVED/UNCHANGED reconciliation
- invalid preview rejection
- stale preview rejection
- rollback on audit-insert failure
- holdings retrieval
- reconciliation audit retrieval

## 21. Regression Results

Focused and regression tests:

- PS-P2/PS-P1 import, contract, schema, DTO, and API suites: included in the
  114-test run.
- Legacy owner portfolio API: included in the 114-test run.
- Existing indicators, ScoringEngine, and DecisionEngine tests: included in the
  114-test run.

Result: 121 passed.

`git diff HEAD --check`: clean.

Ruff:

- New/changed PS-P2 API/parser files: pass.
- `repository.py` passes I/E/F/UP/B/RUF checks introduced by PS-P2; full-file
  Ruff still reports pre-existing SIM117 nested-`with` style suggestions in
  older repository blocks, left untouched.

## 22. Deferred Scope

Deferred:

- Final My Portfolio dashboard tab.
- Polished upload UX.
- Sync Portfolio orchestration.
- Market ingestion triggered by portfolio import.
- OwnerValidationPipeline execution for holdings.
- Status, Conviction, Trend/Setup, Key Trigger, supports, targets, Next Action.
- 20-column analysis snapshot generation.
- Broker-specific adapters and broker authentication.
- Transactions, lots, sale inference, realized P&L reconstruction.
- Order placement or execution code.

## 23. Known Gaps

- XLSX support is intentionally generic and minimal; it does not evaluate
  formulas or support complex workbook features.
- Upload uses raw body bytes plus `filename` rather than multipart form data.
- Confirmation concurrency relies on local SQLite transaction serialization; no
  distributed locking is introduced.
- History endpoints are intentionally minimal and not dashboard-tailored.

## 24. Recommended PS-P3 Scope

Recommended PS-P3: My Portfolio Dashboard + Upload UX.

Rationale: the backend import/confirm/holdings/audit APIs now exist, while Sync
Portfolio analysis still depends on owner-visible workflow decisions: how the
owner reviews failed rows, confirms imports, and inspects reconciliation. A
thin dashboard tab for upload, preview table, diff review, confirm, holdings,
and audit history should come before market-analysis sync orchestration so the
source-of-truth workflow is usable and reviewable.

## 25. Files Changed

- `src/athena/portfolio/imports.py`
- `src/athena/api/v1/services/my_portfolio_service.py`
- `src/athena/api/v1/routers/my_portfolio.py`
- `src/athena/api/v1/router.py`
- `src/athena/api/dependencies.py`
- `src/athena/api/exceptions.py`
- `src/athena/api/errors.py`
- `src/athena/api/v1/dtos/portfolio.py`
- `src/athena/data/store/repository.py`
- `tests/runtime/test_my_portfolio_imports.py`
- `tests/api/v1/test_my_portfolio_import_api.py`
- `docs/research/PS-P2-PORTFOLIO-IMPORT-RECONCILIATION.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`
