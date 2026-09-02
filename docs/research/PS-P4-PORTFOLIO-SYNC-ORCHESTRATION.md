# PS-P4 Portfolio Sync Orchestration

Status: Ready for Owner/Chief Architect review
Date: 2026-09-02
Scope: Background My Portfolio Sync runs, persisted analysis snapshots,
server-owned valuation math, latest-snapshot API, and dashboard sync wiring
Boundary: No new trading methodology, no portfolio-specific action vocabulary,
no alternate indicator/scoring/decision engine, no order placement

## 1. Executive Summary

PS-P4 implements Portfolio Sync as a persisted background workflow over the
PS-P1/PS-P2/PS-P3 My Portfolio foundation. Sync reads confirmed
`portfolio_holdings`, composes them with ATHENA's persisted D1 candles and
latest persisted decisions, calculates server-owned valuation math, writes
immutable snapshot rows, exposes sync status/results, and upgrades the My
Portfolio dashboard to a 20-column Portfolio Snapshot table.

## 2. Scope

Implemented:

- `POST /api/v1/my-portfolio/sync`
- `GET /api/v1/my-portfolio/sync`
- `GET /api/v1/my-portfolio/sync/{sync_run_id}`
- `GET /api/v1/my-portfolio/snapshot`
- persisted `portfolio_sync_runs` lifecycle updates
- persisted `portfolio_analysis_snapshots` rows
- background single-flight execution
- deterministic inline sync helper for tests
- dashboard sync start, polling, status, and snapshot refresh

## 3. Frozen Architecture

My Portfolio remains inside ATHENA's existing `portfolio` capability. Sync
does not modify `portfolio_holdings`, quantity, average price, import
provenance, `owner_positions`, ScoringEngine, DecisionEngine, indicators, or
market-data storage. It consumes existing persisted ATHENA facts and artifacts.

## 4. Sync Semantics

Upload / Confirm changes what the owner currently holds. Sync Portfolio
refreshes ATHENA's derived view of those holdings.

Sync never infers transactions and never creates order/execution behavior.

## 5. Background Job Model

The start endpoint returns HTTP 202 with a sync run ID and initial status.
Execution occurs in a daemon worker thread owned by the API process. Progress
and final state are persisted in `portfolio_sync_runs`, not only process memory.

## 6. Single-Flight Behavior

The service keeps one local sync worker at a time. If a persisted QUEUED/RUNNING
sync exists and the local worker is alive, start returns the active run rather
than launching a duplicate. If a QUEUED/RUNNING row exists without a live local
worker, it is marked FAILED as interrupted before a new run starts.

## 7. Market Data Reuse

Each holding reads the latest persisted D1 candle using
`SqliteRepository.list_candles_recent(..., Timeframe.D1, limit=1)`.

`last_price` is the candle close and `price_as_of` is that candle's timestamp.
Run-level `market_data_through` is the minimum successful row price timestamp,
so the aggregate never claims to be fresher than its least-fresh priced holding.

## 8. Scoped Ingestion Behavior

When the API service has config/repo-root context and a holding has no persisted
D1 candle, PS-P4 can invoke the existing `validate_symbols()` adapter for the
missing holdings. My Portfolio does not talk to providers directly and does not
own a separate ingestion path.

Deterministic direct-service tests instantiate `MyPortfolioService(repo)`
without config context; those runs consume persisted ATHENA data only.

## 9. Validation/Decision Reuse

Sync reads latest persisted `Decision` objects by canonical `instrument_id`.
When a decision exists, provenance records `decision_id` and `validation_run_id`
from that decision. Sync does not create portfolio-only ephemeral decisions.

## 10. Analysis Evidence Adapter

`src/athena/portfolio/sync.py` is the narrow PS-P4 adapter. It gathers:

- canonical holding facts
- canonical instrument identity
- latest persisted D1 candle
- latest persisted decision
- TradePlan target 1 when present
- provenance and unavailable/failure metadata

## 11. 20-Column Mapping

Implemented columns:

1. Symbol
2. Qty
3. Avg Price
4. Last Price
5. Price As Of
6. Investment
7. Current Value
8. P&L
9. P&L %
10. Status
11. Conviction
12. Trend / Setup
13. Key Trigger
14. Support 1
15. Major Support / Exit
16. Target 1
17. Target 2
18. Target 3
19. Next Action
20. Last Review

## 12. Server-Owned Math

The existing PS-P1 `calculate_portfolio_row_math()` contract computes:

- investment = qty × avg price
- current value = qty × last price
- P&L = current value − investment
- P&L % = P&L / investment × 100

If price is unavailable, valuation/P&L fields remain null.

## 13. Target Mapping

`target_1` is populated only from an existing persisted `TradePlan.targets[0]`.
If no TradePlan exists, it remains null. `target_2` and `target_3` remain null.

## 14. Support Mapping

`support_1` remains null. No support algorithm was introduced.

`major_support_exit` remains null. PS-P4 does not relabel TradePlan stop-loss as
Major Support / Exit.

## 15. Methodology-Sensitive Null Fields

These remain null in PS-P4:

- Status
- Conviction
- Trend / Setup
- Key Trigger
- Support 1
- Major Support / Exit
- Target 2
- Target 3
- Next Action

The row provenance records why fields are unavailable.

## 16. Freshness

Rows preserve:

- portfolio imported at
- last synced at
- decision as of
- price as of
- market data through
- analysis version

The dashboard displays Portfolio imported, Holdings as of, Last synced, and
Market data through as distinct concepts.

## 17. Provenance

Each row records:

- instrument ID
- candle ref
- price source
- decision ID when present
- validation/run ID when present
- analyzed timestamp
- unavailable fields
- failed components

## 18. Snapshot Persistence

Each analyzed holding writes one immutable row in
`portfolio_analysis_snapshots`. A later sync writes new rows with a new
`sync_run_id`; previous snapshot rows are not overwritten.

## 19. Partial Success

A run with some successful rows and some per-holding failures finishes as
`PARTIAL`. Successful rows are persisted. Failed rows are also persisted with
null valuation fields and explicit failure provenance.

This differs from import confirmation, which remains atomic by design.

## 20. Error Semantics

Per-holding failures include:

- `INVALID_CANONICAL_INSTRUMENT`
- `NO_PERSISTED_D1_CANDLE`

All-holding failure marks the sync run `FAILED`. Worker-level exceptions mark
the run `FAILED` with `SYNC_WORKER_FAILED`.

## 21. Latest Snapshot Semantics

Latest snapshot selects the most recent sync run with status `SUCCESS` or
`PARTIAL` and persisted snapshot rows.

Queued/running runs do not replace a previous good snapshot. Failed runs do not
replace a previous good snapshot.

## 22. Portfolio Summary

The latest snapshot endpoint returns the PS-P1 summary contract:

- holding count
- total investment
- total current value
- total P&L
- total P&L %
- imported at
- holdings as of
- last synced at
- market data through
- sync status

If any row lacks price/P&L, aggregate current value and P&L fields are null.

## 23. Dashboard Integration

The PS-P3 disabled Sync button is now active. The dashboard:

- starts sync
- disables repeated starts while syncing
- polls status
- displays progress
- fetches latest snapshot on SUCCESS/PARTIAL
- renders all 20 columns
- keeps previous completed snapshot on FAILED

## 24. Restart/Recovery

On start/status/history/snapshot operations, stale persisted QUEUED/RUNNING
syncs without a live local worker are marked FAILED with an interruption error.
No distributed job infrastructure was introduced.

## 25. Test Coverage

Added/updated tests cover:

- zero holdings sync
- all-success snapshot math
- TradePlan target 1 mapping
- methodology-sensitive null fields
- partial success with missing candle
- failed run preserving previous good snapshot
- API background start/status/snapshot
- 20-column API serialization
- dashboard active sync contract

## 26. Regression Results

Targeted verification:

```text
rtk pytest tests/api/v1/test_my_portfolio_import_api.py tests/api/platform/test_dashboard_hosting.py::test_my_portfolio_dashboard_tab_contract tests/api/platform/test_dashboard_hosting.py::test_dashboard_static_hosting_and_fallback tests/api/platform/test_decision_chart_release_gate.py
=> 17 passed

rtk pytest tests/runtime/test_my_portfolio_imports.py tests/runtime/test_my_portfolio_contracts.py tests/data_layer/test_my_portfolio_schema.py tests/api/v1/test_my_portfolio_dtos.py tests/api/v1/test_my_portfolio_import_api.py tests/api/platform/test_dashboard_hosting.py tests/api/platform/test_decision_chart_release_gate.py tests/api/v1/test_owner_portfolio.py tests/decision/test_indicators.py tests/decision/test_scoring.py tests/decision/test_decision.py tests/api/platform/test_platform.py
=> 138 passed

rtk pytest
=> 2987 passed, 0 failed, 1 skipped
```

## 27. Known Gaps

- No browser screenshot/interaction automation was added.
- Scoped refresh is limited to the existing `validate_symbols()` path when API
  config context is available.
- No new support/conviction/status/next-action methodology was introduced.
- Sync cancellation UI is not implemented.

## 28. Deferred Methodology

Deferred beyond PS-P4:

- final portfolio Status vocabulary
- Conviction mapping
- portfolio-specific Next Action
- Support 1
- Major Support / Exit
- Target 2 / Target 3
- ADD/REDUCE/EXIT/ROTATE portfolio interpretation

## 29. Files Changed

Created:

- `src/athena/portfolio/sync.py`
- `docs/research/PS-P4-PORTFOLIO-SYNC-ORCHESTRATION.md`

Modified:

- repository sync/snapshot persistence
- My Portfolio service and router
- API dependency/error mapping
- My Portfolio dashboard HTML/CSS/JS
- dashboard release gates
- My Portfolio API tests
- status and briefing docs

## 30. Recommended PS-P5

Recommended PS-P5 is Portfolio Interpretation Methodology only if the owner
wants ATHENA to deliberately define portfolio-facing meanings for Status,
Conviction, Trend / Setup, Key Trigger, Support, Major Support / Exit, Target
2/3, and Next Action.

Do not begin PS-P5 without Owner/Chief Architect approval.
