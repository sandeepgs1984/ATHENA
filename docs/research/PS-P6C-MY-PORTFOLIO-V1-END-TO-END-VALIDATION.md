# PS-P6C My Portfolio V1 End-to-End Validation

Status: Owner/Chief Architect approved and frozen
Date: 2026-09-03
Scope: Final My Portfolio V1 production-readiness validation
Boundary: No V2 features, no trading-methodology changes, no broker/execution,
no transaction ledger, no automatic trading, no new infrastructure

## 1. Executive Summary

PS-P6C validated the complete frozen My Portfolio V1 workflow end to end:
upload, preview, validation, symbol mapping, reconciliation, confirm, canonical
holdings, manual Sync Portfolio, persisted ATHENA evidence, portfolio
interpretation, immutable snapshot, currentness, and dashboard presentation.

No V1 correctness defect requiring a product-code fix was found. Six acceptance
tests were added to lock missing validation evidence around no-snapshot state,
legacy UNKNOWN currentness, stale-to-current resync, and representative
20/50/100 holding portfolios.

Verdict: Owner/Chief Architect approved PS-P6C on 2026-09-03. My Portfolio V1
is COMPLETE AND FROZEN.

## 2. V1 Scope Revalidated

V1 remains exactly owner-imported current holdings plus manual analysis sync.
Confirmed holdings provide only Symbol, Qty, and Avg Price. Sync does not mutate
holdings. Portfolio interpretation does not change ScoringEngine,
DecisionEngine, EntryQualification, TradePlan, indicator, provider, broker, or
order behavior.

Explicitly absent from V1: transactions, lots, inferred sells, realized P&L,
automatic portfolio management, REDUCE/ROTATE, allocation optimizer, broker
execution, scheduled sync, and portfolio scoring.

## 3. Environment/Test Dataset

Validation used deterministic pytest fixtures over temporary SQLite databases,
the real My Portfolio API/service/repository/orchestrator code path, and static
dashboard asset contracts. Representative portfolio-size validation generated
20, 50, and 100 canonical NSE holdings with persisted D1 candles and no network
or provider calls.

## 4. First Import Validation

Validated by API tests that upload a valid CSV, persist a preview, resolve
symbols, show ADDED reconciliation, and confirm into canonical holdings.
Holdings remain empty before confirmation, and confirmation stores canonical
instrument, quantity, average price, investment, source import, source row, and
audit reconciliation.

No trades, sell events, lots, broker executions, or realized P&L are fabricated.

## 5. Daily Sync Validation

Manual sync was validated through inline and background API paths. With current
persisted D1 data, sync reuses persisted state without refresh. With stale or
missing D1, sync scopes refresh through the existing validation runner, then
re-reads persisted data before creating snapshots.

The expected analysis session remains owned by `CalendarEngine`,
`resolve_validate_as_of`, `_index_instrument_needs_refresh`, and existing
validation/ingestion paths.

## 6. Holdings-Changed Validation

Quantity changes, average-price changes, added holdings, and removed holdings
all mark the latest previous snapshot `STALE_HOLDINGS_CHANGED` immediately.
The previous snapshot rows remain visible and unchanged; no hybrid of current
holdings and old valuation is created.

Added PS-P6C validation proves a successful resync creates a new snapshot whose
digest matches current holdings and restores `CURRENT`.

## 7. Identical Re-import Validation

Semantically identical holdings re-imports preserve the canonical holdings
digest and keep the existing snapshot `CURRENT`, even if import history advances.
Order-independent digest tests prove input ordering does not create a false
stale state.

## 8. PARTIAL Validation

A deterministic missing-D1 scenario validates `PARTIAL`: successful rows remain
usable, failed rows remain visible with failed components, and the summary keeps
Current Value/P&L null when valuation coverage is incomplete.

Currentness remains independent of `PARTIAL`: both `CURRENT + PARTIAL` and
`STALE_HOLDINGS_CHANGED + PARTIAL` are tested.

## 9. FAILED Validation

A deterministic failed-sync path validates that the failed run persists, does
not replace the previous usable snapshot, and does not alter currentness
semantics. The dashboard contract retains failed-sync messaging and keeps manual
retry available without adding auto-retry behavior.

## 10. UNKNOWN Currentness Validation

Legacy snapshot provenance without a holdings digest returns:

- `currentness = UNKNOWN`
- `portfolio_changed_since_sync = false`
- `currentness_reason = SNAPSHOT_HOLDINGS_DIGEST_UNAVAILABLE`

The dashboard contract includes a distinct UNKNOWN warning:

`Portfolio analysis currentness could not be verified. Sync Portfolio to generate a current verified snapshot.`

UNKNOWN is not represented as CURRENT, and it does not claim holdings changed.
A successful new sync regenerates holdings-digest provenance and resolves the
state to `CURRENT`.

## 11. Import-vs-Sync Concurrency Validation

Preview during `QUEUED`/`RUNNING` sync remains allowed and does not mutate
canonical holdings. Confirmation during active sync returns HTTP 409 and leaves
holdings and preview state unchanged. Sync start and import confirmation share
the process-local guard, so the active run lifecycle and holdings mutation
cannot overlap inside the current single-process dashboard runtime.

Accepted V1 constraint: the guard is process-local. Multi-process Portfolio
mutation would require a database-backed lease or transactional mutex.

## 12. No-Snapshot Validation

Confirmed holdings do not generate a snapshot automatically. The snapshot API
returns 404 until a successful or partial sync creates snapshot rows. Dashboard
static coverage preserves the no-snapshot guidance to Sync Portfolio to
generate ATHENA analysis.

## 13. Empty-State Validation

An empty portfolio sync completes with zero holdings and no snapshot. Empty or
blank imports do not clear holdings. Clear Portfolio remains deferred and was
not implemented for this validation.

## 14. Freshness/Session Validation

PS-P4.1 freshness behavior was revalidated through tests covering current D1,
missing D1, stale D1 refresh and re-read, forced refresh, weekend/holiday-like
prior-session handling using deterministic fixtures, and stale Decision
coherency. No Portfolio-owned freshness threshold was introduced.

## 15. Decision Coherency Validation

Current price plus stale Decision evidence does not produce current TradePlan
interpretation. Target 1, Key Trigger, Major Support / Exit, ADD, and EXIT are
blocked unless PS-P4.1/PS-P5B coherency rules accept the evidence. Stale
Decision identity can remain in provenance for audit.

## 16. EntryQualification/ADD Validation

ADD remains frozen: coherent active TradePlan plus coherent persisted
QUALIFIED EntryQualification produces ADD. Without coherent QUALIFIED
EntryQualification, an active plan remains HOLD. No price-chase constraint or
EntryQualification methodology change was added.

## 17. EXIT Boundary Validation

Inclusive invalidation remains frozen: `last_price <= stop_loss` yields
AT_RISK/EXIT. Runtime interpreter tests cover exact stop, below stop, and above
stop behavior.

## 18. Key Trigger Validation

Key Trigger remains `entry_low` only while `last_price < entry_low`. At or above
entry_low, the trigger is consumed/null. Entry high is not substituted.

## 19. Intentional Null Validation

Conviction, Trend / Setup, Support 1, Target 2, and Target 3 remain
intentionally nullable in V1. Their absence is represented by methodology
unavailable/deferred reason codes and unavailable fields, not runtime failure.

## 20. Portfolio Math Validation

Server-owned Decimal arithmetic remains authoritative:

- Investment = Qty x Avg Price
- Current Value = Qty x Last Price
- P&L = Current Value - Investment
- P&L % = P&L / Investment x 100

Dashboard JavaScript does not duplicate this authoritative row arithmetic.
Portfolio summary stays null for Current Value/P&L when any row lacks valuation.

## 21. Snapshot Immutability

Snapshots remain immutable when holdings change, currentness changes, dashboard
reloads, failed syncs occur, and new syncs complete. Currentness is read-time
relationship metadata between a snapshot run digest and current canonical
holdings digest.

## 22. Audit Traceability

The audit chain is traceable through persisted import metadata and parser
digest, preview rows, reconciliation rows, confirmed canonical holdings,
holdings digest, sync run provenance, expected analysis session, persisted D1
market evidence, Decision/EntryQualification references, interpretation version
and reason codes, and snapshot row/freshness/provenance JSON.

No new audit UI was required.

## 23. Dashboard UX Acceptance

Static dashboard contracts validate upload limits, preview state, errors,
unresolved/ambiguous/duplicate rows, reconciliation, confirmation, active-sync
confirmation conflict, holdings table, Sync button/polling hooks, stale warning,
UNKNOWN warning, no-snapshot guidance, PARTIAL and FAILED summaries, failed
symbols, status/action visual priority, row explanations, horizontal scrolling,
sticky leading columns, and the 20-column layout.

No redesign was performed.

## 24. API/Error Contract Audit

The API validation covers import preview/detail/confirm, holdings, import
history, sync start/status/latest-snapshot behavior, missing snapshot 404,
stale preview 409, active sync 409, malformed/invalid import 400, and failed
sync preservation. Errors remain structured and do not expose stack traces.

## 25. Upload/Input Hardening

Existing import tests and parser contracts cover malformed/invalid previews,
duplicate canonical instruments, unresolved symbols, ambiguous symbols, stale
previews, empty/zero-holdings rejection, and the frozen limits of 2 MB and
2,000 rows. Blank/empty upload does not clear the portfolio.

## 26. Restart/Recovery

Existing recovery logic marks stale `QUEUED`/`RUNNING` syncs failed when no
live worker owns them. Browser refresh/page reload behavior is covered through
dashboard reload contracts and snapshot read tests. PS-P6C added a new
service-instance read test proving legacy UNKNOWN currentness recomputes from
persisted state and resolves to CURRENT after a new sync.

## 27. 20/50/100 Holdings Performance Sanity

Representative 20, 50, and 100 holding portfolios were imported, synced, and
read through the real workflow. All completed SUCCESS, preserved holdings
digest, produced one snapshot row per holding, and stayed CURRENT. No obvious
N+1 blocker, repeated digest pathology, or unreasonable payload behavior was
observed in this lightweight sanity validation.

## 28. Corrective Fixes, If Any

No PS-P6C product-code corrective fix was required. Added tests only.

## 29. Full Regression Evidence

Validation commands:

- `rtk ruff check ...` on touched Python files/tests -> passed
- `rtk pytest tests/api/v1/test_my_portfolio_import_api.py` -> `36 passed`
- `rtk pytest tests/api/v1/test_my_portfolio_import_api.py tests/data_layer/test_my_portfolio_schema.py tests/api/platform/test_dashboard_hosting.py tests/runtime/test_portfolio_interpretation.py tests/runtime/test_my_portfolio_contracts.py` -> `70 passed`
- `rtk pytest` -> `3190 passed, 0 failed, 1 skipped`

Full Ruff remains blocked by known unrelated lint debt outside this change set.
`rtk mypy` is unavailable in the active interpreter (`No module named mypy`).

## 30. Known V1 Constraints

- Portfolio Sync remains manual.
- Import confirmation vs Sync guard is process-local and approved for the
  current single-process dashboard runtime.
- UNKNOWN currentness can occur for legacy snapshots without digest provenance
  and requires a new sync to become verified CURRENT.
- Clear Portfolio is not available in V1.
- No snapshot history UI or reconciliation detail UI beyond the current import
  history and preview/reconciliation flow.

## 31. Deferred V2 Work

Deferred work includes Conviction, Trend / Setup, validated Support 1, Target 2,
Target 3, richer portfolio analytics/history, comparative holding strength,
REDUCE, ROTATE, capital allocation/opportunity ranking, database-backed
multi-worker leases, scheduled sync, broker integration, transaction ledger,
lots, and realized P&L.

## 32. Final Production-Readiness Verdict

All PS-P6C completion criteria are satisfied by existing tests plus the new
acceptance coverage. Owner/Chief Architect approved PS-P6C on 2026-09-03. My
Portfolio V1 is COMPLETE AND FROZEN.
