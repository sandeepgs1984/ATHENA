# PS-P1 My Portfolio Contract Design

Status: Ready for Owner/Chief Architect review
Date: 2026-09-02
Scope: My Portfolio design, schema, domain contracts, DTO/API contracts
Boundary: Contract-first only; no dashboard workflow, no broker integration, no
portfolio interpretation methodology, no ScoringEngine/DecisionEngine changes

## 1. Frozen Owner Decisions

PS-P1 accepts the PS-P0 discovery report and the owner-approved decisions D1-D15
as frozen inputs. My Portfolio is an isolated subdomain inside ATHENA's existing
`portfolio` capability, persists to `db/athena.db`, owns its canonical current
holdings, uses hybrid snapshot-owned reconciliation, resolves uploaded symbols
through canonical ATHENA instrument identity, reuses ATHENA market/intelligence
infrastructure for Sync Portfolio, and leaves methodology-sensitive values
nullable where ATHENA does not yet produce an approved value.

Explicitly frozen:

- One canonical current holding per `instrument_id`, preferably `NSE:SYMBOL`.
- `owner_positions` remains the legacy/manual-fill ledger and is not migrated or
  repurposed.
- Import preview never mutates canonical holdings.
- Confirmed reconciliation retains an auditable before/after diff and never
  invents transactions, sale dates, sale prices, or realized P&L.
- Portfolio Snapshot has exactly the required 20 business fields, with nullable
  methodology-sensitive fields where needed.
- Sync Portfolio is a background job and supports partial success.
- No broker authentication, broker execution, automatic orders, lot accounting,
  transaction reconstruction, or cash/reserved-capital redesign is included.

## 2. Module Boundary

My Portfolio extends the existing `portfolio` boundary described by
`ATHENA-002-System-Blueprint.md`: portfolio intelligence consumes persisted
positions/holdings and upstream scores/decisions; it does not alter scoring,
confidence, risk, indicators, trade-plan generation, or decision methodology.

Dependency direction:

```text
ATHENA market data / candles / quotes
  -> existing validation and decision pipeline
  -> persisted Decision, DecisionTrace, run detail/report
  -> My Portfolio analysis snapshot
```

No ADR is required for PS-P1 because the implementation is additive inside the
existing portfolio module and the existing SQLite repository. An ADR would be
required if a later phase changes ATHENA's module graph, redefines
`owner_positions`, creates a second market-data store, or adds new trading
methodology.

## 3. Source of Truth

Canonical My Portfolio current holdings live in `portfolio_holdings`. Uploaded
CSV/XLSX files are evidence inputs only. Once the owner confirms a preview,
ATHENA writes the current-holdings representation to `portfolio_holdings` and
records the reconciliation audit.

Minimum canonical holding facts:

| Fact | Contract |
|---|---|
| Instrument | Canonical `instrument_id`, not raw ticker text |
| Quantity | Positive integer |
| Average price | Positive `Decimal` stored as text in SQLite |
| Provenance | Source import ID, source row ID, reconciliation ID, timestamps |

## 4. Persistence Model

PS-P1 introduces isolated `portfolio_*` tables and bumps ATHENA schema version
to 16. The tables are additive and do not modify `owner_positions`.

| Table | Responsibility |
|---|---|
| `portfolio_imports` | One upload/import batch with source, parser version, row counts, status, timestamps, provenance |
| `portfolio_import_rows` | Parsed source rows, original values, normalized fields, mapping state, errors/warnings |
| `portfolio_holdings` | Canonical current holdings; one row per canonical instrument |
| `portfolio_reconciliations` | Confirmed before/after diffs using ADDED/UPDATED/REMOVED/UNCHANGED |
| `portfolio_sync_runs` | Background Sync Portfolio run state, progress, per-symbol failures, provenance |
| `portfolio_analysis_snapshots` | Immutable derived rows for the 20-column Portfolio Snapshot |

Names follow the current repository convention of clear snake-case table names
grouped by domain prefix.

## 5. Entity Relationships

```text
portfolio_imports 1 -> many portfolio_import_rows
portfolio_imports 1 -> many portfolio_reconciliations
portfolio_imports 1 -> many portfolio_holdings via source_import_id
portfolio_sync_runs 1 -> many portfolio_analysis_snapshots
portfolio_holdings instrument_id -> existing instruments/symbol_master identity
portfolio_analysis_snapshots -> existing decisions/runs by stored references
```

The schema intentionally avoids foreign-keying every provenance reference to
upstream ATHENA artifacts because decision/run availability may vary by partial
sync outcome. Provenance columns retain references as data.

## 6. Import Contract

Normalized import contract:

- `ImportedHoldingRow.source_row_id`
- `ImportedHoldingRow.raw_symbol`
- `ImportedHoldingRow.quantity`
- `ImportedHoldingRow.avg_price`
- Optional `broker`, `source_metadata`, `holdings_as_of`

Import pipeline:

```text
CSV/XLSX
-> parser
-> normalized imported rows
-> validation
-> symbol resolution
-> preview
-> owner confirmation
-> reconciliation
-> canonical holdings
```

Parsing and symbol resolution remain separate concerns. The parser emits
normalized facts and row-level errors; the resolver converts valid rows into
canonical identity states.

## 7. Symbol Mapping Contract

Mapping states:

| State | Meaning | Canonical holding eligible? |
|---|---|---|
| `RESOLVED` | Exactly one ATHENA canonical instrument was found | Yes |
| `UNRESOLVED` | No canonical instrument was found | No |
| `AMBIGUOUS` | More than one plausible canonical instrument exists | No |

Resolution uses existing `symbol_master` / `instruments` infrastructure. A
future implementation may rank exact `NSE:SYMBOL` matches first, but ambiguity
must remain visible and owner-resolved; no silent guessing is allowed.

## 8. Import Preview Contract

Preview response must include:

- `import_id`
- `status=PREVIEWED`
- total/accepted/rejected/unresolved/ambiguous row counts
- row-level normalized data and mapping state
- warnings
- proposed reconciliation changes

Canonical holdings are unchanged until `POST confirm` succeeds. Tests protect
this by treating reconciliation preview as a pure diff over immutable holdings.

## 9. Reconciliation Contract

Deterministic reconciliation compares existing canonical holdings with the
resolved uploaded current-holdings snapshot by `instrument_id`.

| Existing | Uploaded | Action |
|---|---|---|
| absent | present | `ADDED` |
| present | present with different quantity or average price | `UPDATED` |
| present | absent | `REMOVED` |
| present | present with same quantity and average price | `UNCHANGED` |

`REMOVED` means "not present in the latest confirmed current-holdings snapshot."
It does not imply a sale, exit price, sale timestamp, or realized P&L.

## 10. Canonical Holdings Contract

`CanonicalPortfolioHolding` requires:

- canonical `instrument_id` containing the exchange prefix
- positive `quantity`
- positive `avg_price`
- timezone-aware `imported_at` and `updated_at`
- `source_import_id`
- `source_row_id`
- optional immutable provenance mapping

SQLite enforces one canonical current row per `instrument_id`.

## 11. Portfolio Math Contract

The server owns the Portfolio Snapshot math:

```text
investment = quantity * avg_price
current_value = quantity * last_price
pnl = current_value - investment
pnl_pct = pnl / investment * 100
```

If `last_price` is absent or investment is invalid/zero, `investment` remains
reported but `current_value`, `pnl`, and `pnl_pct` are `null`. The dashboard
must render these values; it must not become authoritative for them.

## 12. Sync Portfolio Contract

Conceptual flow:

1. Load canonical holdings.
2. Verify canonical instrument identities.
3. Inspect latest persisted D1 market data and quotes.
4. Reuse scoped ingestion if required.
5. Reuse `OwnerValidationPipeline` / validation infrastructure.
6. Read persisted decisions, traces, reports, and trade plans.
7. Build server-owned Portfolio Snapshot rows.
8. Persist immutable `portfolio_analysis_snapshots`.
9. Record per-holding success/failure.
10. Complete the sync as `SUCCESS`, `PARTIAL`, or `FAILED`.

Sync must not fetch every holding through a new provider, create another candle
store, duplicate indicator logic, or run a parallel decision methodology.

## 13. Background Job States

`SyncRunStatus`:

| State | Meaning |
|---|---|
| `QUEUED` | Accepted but not yet running |
| `RUNNING` | Background job active |
| `SUCCESS` | Every holding completed |
| `PARTIAL` | At least one holding succeeded and at least one failed |
| `FAILED` | No usable holding analysis completed, or setup failed |
| `CANCELLED` | Reserved for explicit future cancellation support |

`portfolio_sync_runs` stores total/succeeded/failed counts, progress JSON,
per-symbol JSON, error JSON, timestamps, `market_data_through`,
`validation_run_id`, and analysis version.

## 14. Analysis Snapshot Contract

`portfolio_analysis_snapshots` stores immutable row JSON for each holding plus
freshness, provenance, unavailable fields, and failures. It should prefer
references to persisted ATHENA artifacts over copied free-text analysis.

The row contract is produced by `PortfolioSnapshotRow` and serialized through
`PortfolioSnapshotRowDTO`.

## 15. Complete 20-Column DTO

The server-side DTO preserves all required fields:

| # | Display field | DTO field | Nullable? | Source |
|---|---|---|---|---|
| 1 | Symbol | `symbol` | No | Canonical instrument/symbol master |
| 2 | Qty | `qty` | No | Canonical holding |
| 3 | Avg Price | `avg_price` | No | Canonical holding |
| 4 | Last Price | `last_price` | Yes | Latest quote/mark |
| 5 | Price As Of | `price_as_of` | Yes | Quote timestamp |
| 6 | Investment | `investment` | No | Server math |
| 7 | Current Value | `current_value` | Yes | Server math, requires last price |
| 8 | P&L | `pnl` | Yes | Server math, requires last price |
| 9 | P&L % | `pnl_pct` | Yes | Server math, requires valid investment and last price |
| 10 | Status | `status` | Yes | Deferred portfolio interpretation |
| 11 | Conviction | `conviction` | Yes | Deferred mapping from existing ATHENA evidence |
| 12 | Trend / Setup | `trend_or_setup` | Yes | Existing decision/report evidence where valid |
| 13 | Key Trigger | `key_trigger` | Yes | Existing decision/report evidence where valid |
| 14 | Support 1 | `support_1` | Yes | Existing ATHENA evidence only if semantically valid |
| 15 | Major Support / Exit | `major_support_exit` | Yes | Stop/exit evidence where semantically valid |
| 16 | Target 1 | `target_1` | Yes | Existing `TradePlan.targets[0]` where available |
| 17 | Target 2 | `target_2` | Yes | Deferred methodology |
| 18 | Target 3 | `target_3` | Yes | Deferred methodology |
| 19 | Next Action | `next_action` | Yes | Deferred portfolio interpretation |
| 20 | Last Review | `last_review` | Yes | Analysis timestamp / sync review timestamp |

## 16. Null / Unavailable / Failure Semantics

`null` never means zero, false, sell, or "not loaded yet." It means the field
has no approved value in this specific analysis snapshot.

Examples:

- `target_2=null`: ATHENA has no approved Target 2 output for this holding at
  this snapshot.
- `status=null`: no approved portfolio status vocabulary/mapping is frozen.
- `last_price=null`: no usable mark was available; row provenance/failures must
  identify why.
- `support_1=null`: no approved support value was available or semantically
  valid.

Rows also carry `unavailable_fields` and `failed_components` so absence and
failure are distinguishable.

## 17. Freshness Contract

Freshness dimensions remain separate:

| Field | Meaning |
|---|---|
| `portfolio_imported_at` | When ATHENA imported/confirmed the holdings source |
| `holdings_as_of` | Date/time the owner/broker file claims holdings were current |
| `last_synced_at` | When ATHENA last ran Portfolio Sync |
| `market_data_through` | Latest market data included in the sync |
| `analysis_version` | My Portfolio analysis contract version |
| `decision_as_of` | Timestamp of the consumed Decision |
| `price_as_of` | Timestamp of the consumed price/quote |

Do not collapse these into one generic timestamp.

## 18. Provenance Contract

Each row must preserve:

- canonical `instrument_id`
- price source and timestamp
- candle reference where relevant
- consumed decision ID where available
- validation/run ID where available
- analyzed timestamp
- analysis contract version
- unavailable fields
- failed components

This satisfies ATHENA's explainability-as-data rule: UI renders provenance; it
does not reconstruct rationale.

## 19. Portfolio Summary Contract

`PortfolioSnapshotSummaryDTO` includes:

- holding count
- total investment
- total current value
- total P&L
- total P&L %
- imported-at
- holdings-as-of
- last-synced-at
- market-data-through
- sync status

This is not a portfolio risk engine. It is a server-owned arithmetic/freshness
summary for the eventual My Portfolio header.

## 20. API Surface

Minimal v1 endpoints for later phases:

| Method | Path | Contract |
|---|---|---|
| `POST` | `/api/v1/my-portfolio/imports` | Upload/parse holdings file and return `PortfolioImportPreviewDTO` |
| `POST` | `/api/v1/my-portfolio/imports/{import_id}/confirm` | Confirm preview, apply reconciliation, return canonical holdings/diff |
| `GET` | `/api/v1/my-portfolio/holdings` | Return current `MyPortfolioHoldingDTO` rows |
| `POST` | `/api/v1/my-portfolio/sync-runs` | Start background sync, return `PortfolioSyncRunDTO` |
| `GET` | `/api/v1/my-portfolio/sync-runs/{sync_run_id}` | Return sync progress/result |
| `GET` | `/api/v1/my-portfolio/snapshot` | Return latest complete `PortfolioSnapshotDTO` |
| `GET` | `/api/v1/my-portfolio/imports` | Minimal import/audit history |
| `GET` | `/api/v1/my-portfolio/sync-runs` | Minimal sync/audit history |

Endpoint names deliberately avoid overloading existing `/api/v1/portfolio`,
which remains the legacy/manual owner-fill ledger.

## 21. Error Contracts

Failure semantics:

| Failure | Contract |
|---|---|
| Malformed CSV/XLSX | Import status `FAILED`; no canonical mutation |
| Missing required logical columns | Preview row/import errors; no confirmation eligible |
| Invalid quantity / avg price | Row rejected with validation error |
| Duplicate symbol rows | Preview warning/error; confirmation must require deterministic duplicate policy |
| Zero/negative quantity | Rejected |
| Blank rows | Ignored or warned, but counted deterministically |
| Unsupported symbol | `UNRESOLVED`; not canonical-holding eligible |
| Ambiguous symbol | `AMBIGUOUS`; not canonical-holding eligible |
| Duplicate canonical mappings | Preview error until owner resolves |
| No candles / stale data | Per-symbol sync failure or unavailable fields |
| Ingestion failure | Sync `PARTIAL` or `FAILED` depending on per-symbol outcomes |
| Validation failure | Per-symbol failure with validation provenance |
| Missing Decision / TradePlan | Snapshot row may exist with nullable methodology fields |
| Database failure | Request/job fails loudly; no silent partial mutation |
| Concurrent sync | Existing run wins; new request returns current run/conflict |
| Zero holdings sync | `FAILED` or rejected with explicit zero-holdings error |

## 22. Concurrency / Idempotency

Frozen design:

- Only one import confirmation may mutate canonical holdings at a time.
- Only one Portfolio Sync job may run at a time.
- Sync requested while another sync is active should return the active run or a
  409 conflict; implementation must choose one behavior and test it.
- Import confirmation is idempotent by `import_id`; a confirmed import must not
  apply its reconciliation twice.
- Reconciliation records are immutable audit events.
- Duplicate upload is allowed as a new `import_id`, but duplicate confirmation
  of the same `import_id` is not a new mutation.

Reuse `CycleRunnerLock`/single-flight patterns where implementation reaches
background execution.

## 23. Tests Added / Required

Added in PS-P1:

- Schema creation and schema-version recording.
- Legacy `owner_positions` schema preservation.
- Canonical holding uniqueness by `instrument_id`.
- Normalized import-row validation.
- Symbol mapping states.
- Reconciliation `ADDED`, `UPDATED`, `REMOVED`, `UNCHANGED`.
- Preview diff does not mutate holdings.
- Server-owned portfolio math.
- Complete 20-column DTO serialization.
- Nullable methodology-sensitive fields.
- Freshness/provenance representation.
- Sync status and partial-success DTO contract.

Required in PS-P2/PS-P3 as implementation grows:

- Parser alias handling.
- Confirmation repository transaction semantics.
- Import confirmation idempotency.
- Background single-flight behavior.
- Per-symbol sync failure persistence.
- Regression checks proving existing ScoringEngine, DecisionEngine, indicators,
  and owner-position API behavior remain unchanged.

## 24. Deferred Scope

Deferred:

- Final My Portfolio dashboard tab.
- Polished upload UX.
- Full CSV/XLSX workflow implementation.
- Complete background Sync orchestration.
- Portfolio status vocabulary.
- Conviction mapping thresholds.
- Next Action methodology.
- Support/resistance methodology.
- Target 2/Target 3 methodology.
- Broker-specific adapters.
- Broker authentication and broker APIs.
- Trading/order execution.
- Transaction reconstruction, lot accounting, realized P&L reconstruction.
- Cash/reserved-capital redesign.

## 25. Files Changed

PS-P1 files:

- `src/athena/portfolio/my_portfolio_contracts.py`
- `src/athena/portfolio/__init__.py`
- `src/athena/data/store/schema.py`
- `src/athena/api/v1/dtos/portfolio.py`
- `tests/runtime/test_my_portfolio_contracts.py`
- `tests/data_layer/test_my_portfolio_schema.py`
- `tests/api/v1/test_my_portfolio_dtos.py`
- `docs/research/PS-P1-PORTFOLIO-CONTRACT-DESIGN.md`
- `docs/MILESTONES.md`
- `IMPLEMENTATION_SUMMARY.md`
- `ATHENA_BRIEFING.md`

## 26. PS-P2 Recommendation

Recommended PS-P2 scope:

Implement import preview and confirmation plumbing only:

- Generic CSV parser with explicit logical-field aliases.
- Symbol resolution through existing `symbol_master` / `instruments`.
- Repository methods for import batches, import rows, holdings, and
  reconciliation audit.
- Transactional confirmation that mutates `portfolio_holdings` only after a
  valid preview.
- Minimal API endpoints for upload preview, confirm, and current holdings.
- Tests for parser behavior, duplicate handling, unresolved/ambiguous symbols,
  confirmation idempotency, and no mutation during preview.

Do not start Sync Portfolio orchestration, dashboard UX, or interpretation
methodology in PS-P2 unless separately approved.
