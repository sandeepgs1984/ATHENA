# PS-P6B Portfolio Experience Hardening Implementation

Status: Implementation complete; ready for Owner/Principal-Engineer review
Date: 2026-09-03
Scope: Portfolio currentness, concurrency, and operational UX hardening only
Boundary: No trading methodology, ScoringEngine, DecisionEngine, broker,
transaction ledger, scheduled sync, sorting/filtering, Clear Portfolio, or
future-phase behavior

## 1. Executive Summary

PS-P6B hardens My Portfolio's production-readiness around truthful state. The
latest snapshot response now reports server-owned currentness by comparing the
sync-run holdings digest against the current canonical holdings digest at read
time. Confirmed holdings changes no longer silently leave an old snapshot
looking current: the API marks it `STALE_HOLDINGS_CHANGED`, and the dashboard
keeps the previous snapshot visible with an explicit stale warning and manual
Sync prompt.

Import confirmation is now guarded while Portfolio Sync is `QUEUED` or
`RUNNING`. Preview remains allowed because it does not mutate canonical
holdings; confirmation receives a deterministic HTTP 409 conflict and leaves
the preview and holdings unchanged.

## 2. Architecture Compliance

The implementation stays within the approved PS-P6B scope. It reuses
`portfolio_holdings_digest()` and the sync-run provenance `holdings_digest`
without adding a duplicate snapshot digest column. Currentness is evaluated on
read and never mutates immutable `portfolio_analysis_snapshots`.

No portfolio interpretation rules changed. `CURRENT + PARTIAL` and
`STALE_HOLDINGS_CHANGED + PARTIAL` are represented independently: currentness
belongs to the snapshot-vs-current holdings relationship, while `PARTIAL`
remains the sync-run analysis result.

## 3. Server Currentness

`PortfolioSnapshotDTO` now includes:

- `currentness`
- `portfolio_changed_since_sync`
- `currentness_reason`
- `snapshot_holdings_digest`
- `current_holdings_digest`

`MyPortfolioService.latest_snapshot()` owns this calculation centrally. It
returns `CURRENT` when the stored sync-run digest equals the current holdings
digest, `STALE_HOLDINGS_CHANGED` when they differ, and `UNKNOWN` when an older
run lacks digest provenance. No browser-side digest computation was added.

## 4. Digest Verification

The existing digest semantics were verified and locked with tests. The digest
is stable, order-independent, and sensitive to instrument identity, quantity,
average price, additions, and removals. This confirms it is suitable as the
Portfolio Snapshot currentness boundary.

## 5. Concurrency Guard

`MyPortfolioService.confirm_import()` now shares the sync service's smallest
reliable in-process guard (`_SYNC_GUARD`) and checks for an active sync before
calling the repository mutation. If a live thread owns the active run,
confirmation raises `PortfolioSyncActiveConflictError`, mapped to HTTP 409.

Preview remains outside this guard because it persists only preview/audit data
and does not modify canonical holdings.

## 6. Dashboard UX

The My Portfolio dashboard now:

- shows the upload limits (`2 MB` and `2,000 rows`);
- renders stale-analysis warnings when holdings changed after the snapshot;
- keeps the previous snapshot visible instead of synthesizing hybrid rows;
- prompts manual Sync after confirmation when analysis is stale;
- distinguishes active-sync confirmation conflicts from stale-preview conflicts;
- surfaces concise failed-symbol details for failed/partial sync runs;
- adds status/action pills and short row-level explanation text from persisted
  PS-P5B reason/provenance codes.

The dashboard still does not reinterpret evidence or compute currentness; it
only translates server-owned codes into owner-readable text.

## 7. Tests Added

Added or extended coverage for:

- holdings digest stability/order-independence;
- digest sensitivity to quantity, average price, addition, and removal;
- current snapshot reports `CURRENT`;
- reimport with identical holdings remains `CURRENT`;
- quantity, average-price, added-holding, and removed-holding imports mark the
  prior snapshot stale while preserving its rows;
- `PARTIAL` snapshots can be current or stale independently;
- import confirmation is blocked during `QUEUED` and `RUNNING` syncs;
- preview remains allowed during active sync;
- confirmation is allowed after terminal sync states;
- failed sync preserves the previous good latest snapshot;
- dashboard static contract for stale UX, upload limits, row explanations, and
  failure summaries.

## 8. Verification

Verification results:

- `rtk ruff check ...` on touched Python files and tests
- `rtk pytest tests/api/v1/test_my_portfolio_import_api.py tests/data_layer/test_my_portfolio_schema.py tests/api/platform/test_dashboard_hosting.py tests/runtime/test_portfolio_interpretation.py`
  -> `57 passed`
- `rtk pytest` -> `3184 passed, 0 failed, 1 skipped`
- `rtk git diff --check` -> passed
- `rtk ruff check .` still reports broad pre-existing lint debt outside this
  change set (`290 issues in 90 files`)
- `rtk mypy` could not run because the active interpreter has no `mypy` module

Full-suite and whitespace verification are recorded in `IMPLEMENTATION_SUMMARY.md`.

## 9. Risks And Deferred Work

The active-sync guard is process-local, matching ATHENA's current dashboard
runtime model. A future multi-worker deployment would need a database-level run
lease or transactional mutex. That is outside PS-P6B and should be handled as a
separate operational architecture milestone if ATHENA moves beyond this runtime.

Deferred by owner scope: Clear Portfolio, sorting/filtering, richer history,
scheduled sync, broker integration, transaction ledger, REDUCE/ROTATE, and new
portfolio methodology.

## 10. Milestone Outcome

PS-P6B implementation is complete and ready for owner/principal-engineer
review. The next Portfolio Sync milestone remains blocked pending approval.
