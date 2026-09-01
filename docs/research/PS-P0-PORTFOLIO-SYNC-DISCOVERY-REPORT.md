# PS-P0 Portfolio Sync Discovery Report

Status: Discovery only  
Date: 2026-09-01  
Scope: New independent Dashboard feature/module, "My Portfolio"  
Boundary: No production implementation, no ScoringEngine/DecisionEngine/market-methodology changes

## 1. Executive Summary

ATHENA already has three portfolio-adjacent implementations, but none is the
complete "My Portfolio" source of truth requested for Portfolio Sync:

- `src/athena/portfolio/` is an in-memory, decision-driven Portfolio Engine with
  immutable snapshots/history. It models holdings, cash, closed positions, and
  reservations, but it is not the live dashboard's persisted source of truth.
- `owner_positions` in `db/athena.db`, exposed by
  `GET/POST /api/v1/portfolio`, is the current live dashboard ledger. It stores
  owner-entered fills, not uploaded/reconciled holdings. It stores raw
  `instrument_id` text that is often just an uppercased symbol.
- `src/athena/analytics/portfolio/` can compute realized/unrealized P&L and
  portfolio performance from a PortfolioSnapshot plus supplied prices, but it
  does not own holdings, imports, reconciliation, symbol mapping, or analysis
  snapshots.

The clean architecture direction is to add a separate My Portfolio module that
owns uploaded-holdings import, symbol mapping, reconciliation, canonical
holdings persistence, and portfolio-analysis snapshots, while consuming existing
ATHENA market data and persisted Decision/Decision Brief outputs. The dependency
direction should remain:

Existing ATHENA intelligence -> My Portfolio

PS-P1 is not ready as a coding milestone until the owner/chief architect decides
the source-of-truth model, reconciliation semantics, and whether a new isolated
portfolio schema is an ADR-level architecture addition or an allowed extension
inside the already-frozen `portfolio` module.

## 2. Current ATHENA Portfolio Architecture

Current portfolio-related components:

- Frozen-domain DTO-like objects:
  `src/athena/domain/decision.py::Position` and `Portfolio`.
- Runtime Portfolio Engine:
  `src/athena/portfolio/models.py`, `src/athena/portfolio/engine.py`.
- Runtime Portfolio Analytics Engine:
  `src/athena/analytics/portfolio/models.py`,
  `src/athena/analytics/portfolio/engine.py`.
- Live dashboard owner-fill ledger:
  `owner_positions` table in `src/athena/data/store/schema.py`.
- Repository methods:
  `save_owner_position`, `get_owner_position`, `list_owner_positions`,
  `delete_owner_positions`.
- API provider:
  `src/athena/api/v1/providers/sqlite_providers.py::SqlitePortfolioProvider`.
- API service/router/DTO:
  `src/athena/api/v1/services/portfolio_service.py`,
  `src/athena/api/v1/routers/portfolio.py`,
  `src/athena/api/v1/dtos/portfolio.py`.
- Dashboard UI:
  `src/athena/api/static/index.html`,
  `src/athena/api/static/js/08-portfolio.js`,
  `src/athena/api/static/css/05-portfolio.css`.

The frozen blueprint already includes `portfolio` as a module: Portfolio
Intelligence consumes positions and scores and produces `portfolio_assessment`.
The implementation in this repository is more fragmented than the blueprint
ideal: current live dashboard state is repository-backed owner fills, while the
`PortfolioEngine` is richer but not wired as the live persisted source.

## 3. Existing Source of Truth

Current live dashboard source of truth: `owner_positions`.

Evidence:

- `GET /api/v1/portfolio` calls `PortfolioService.get_portfolio()`.
- `PortfolioService` delegates to a `PortfolioProvider`.
- The SQLite provider lists `owner_positions`, computes cash/exposure, adds
  best-effort quote marks to open positions, and returns domain `Portfolio`.
- Open/close/reset endpoints mutate `owner_positions`.

Important gap: `owner_positions` is not a canonical My Portfolio database. It is
an owner-entered fill ledger and can be reset. It has no import batch, upload
metadata, mapping status, reconciliation record, per-sync analysis snapshot,
market-data-as-of date, analysis version, or partial-success sync status.

## 4. Current Data Model

Relevant persisted tables:

- `symbol_master`: canonical listed-symbol catalogue, separate from ingested
  instruments.
- `symbol_group`: dated group/index membership.
- `resolved_universe`: materialized scanner universe snapshots.
- `instruments`: ingested tradable instruments; canonical market-data identity
  is `instrument_id`, typically `NSE:SYMBOL`.
- `candles`: market candles keyed by `(instrument_id, timeframe, ts_open)`.
- `quotes`: quote history keyed by `(instrument_id, ts)`.
- `market_snapshots`, `institutional_flows`, and run/detail tables: market
  context and pipeline provenance.
- `decisions`, `decision_traces`, `decision_journal`, `trade_outcomes`.
- `owner_positions`: current owner fill ledger.

`owner_positions` columns:

- `position_id`
- `instrument_id`
- `opened_ts`
- `quantity`
- `avg_price`
- `closed_ts`
- `exit_price`
- `decision_ref`
- `broker`
- `notes`
- `sector`
- `meta_json`

Missing from current portfolio persistence:

- Import batch/source metadata.
- Original uploaded row text and normalized parsed facts.
- Mapping confidence/status.
- Explicit current-holdings snapshot per import.
- Reconciliation event.
- Realized lot-level accounting.
- Current analysis snapshot/history per holding.
- Freshness dimensions: imported-at, synced-at, market-data-through, analysis
  version.

## 5. Position Lifecycle

Current `PortfolioEngine` lifecycle supports:

- OPEN
- INCREASE
- REDUCE
- CLOSE
- HOLD
- RESERVE
- RELEASE
- `apply_decision()` maps completed ATHENA decisions to portfolio operations.

Current live dashboard `owner_positions` lifecycle supports:

- Open a manual fill.
- Close a full position with an exit price.
- Reset open positions or all positions after typed `CONFIRM`.

Current lifecycle limitations for My Portfolio:

- No partial close endpoint in the live ledger.
- No direct average-price adjustment/reconciliation endpoint.
- No import/update-holdings operation.
- No transaction ledger.
- No lot model.
- Re-entry is represented as a new open row only if the owner logs it that way.
- Closed positions stay in `owner_positions` with `closed_ts`, but there is no
  canonical "position episode" identity tied to imports or instrument renames.
- Realized P&L exists in `trade_outcomes` for decision outcomes and as
  `exit_price` metadata on closed owner positions, but those are not unified.

## 6. Portfolio Persistence

There are two persistence realities:

- The richer `PortfolioEngine` has immutable in-memory `PortfolioSnapshot` and
  `PortfolioHistory`; it is not persisted in SQLite.
- The API/dashboard persists owner-entered positions directly in
  `owner_positions`.

For My Portfolio, relying on uploaded CSV/XLSX files as storage would violate
the requested ownership model. Reusing `owner_positions` directly would also be
too thin unless it is intentionally promoted into a new canonical holdings
schema with import/reconciliation metadata.

## 7. Existing Portfolio Calculations

Current calculations:

- `SqlitePortfolioProvider._compute_cash()` starts from
  `config/portfolio.json::initial_cash`, subtracts open position cost, and adds
  closed proceeds when `exit_price` exists.
- `SqlitePortfolioProvider._compute_exposure()` groups open cost basis by
  `sector` metadata.
- `SqlitePortfolioProvider._latest_mark()` reads latest persisted quotes and
  sets `current_price`/`mark_status` metadata.
- Dashboard `renderHoldingsTable()` computes current value and unrealized P&L
  client-side from `quantity`, `avg_price`, and `meta.current_price`.
- `PortfolioAnalyticsEngine.analyze()` computes unrealized P&L, realized P&L,
  portfolio value, return %, exposure, drawdown, win/loss stats, and cash
  utilization from a `PortfolioSnapshot` and `current_prices`.

Gap: for My Portfolio, Investment, Current Value, P&L, and P&L % should be
server-owned portfolio math, not client-side calculations.

## 8. Existing APIs

Current portfolio APIs:

- `GET /api/v1/portfolio`: current cash, exposure, positions.
- `POST /api/v1/portfolio/positions`: log an owner-entered open fill.
- `POST /api/v1/portfolio/positions/{position_id}/close`: close a fill.
- `POST /api/v1/portfolio/positions/reset`: reset open/all fills after typed
  `CONFIRM`.

Related APIs likely reusable:

- `GET /api/v1/decisions/latest`: one latest decision per instrument.
- `GET /api/v1/decisions/{decision_id}`: decision and trade plan.
- `GET /api/v1/decisions/{decision_id}/depth`: persisted score, confidence,
  risk, eligibility.
- `GET /api/v1/decisions/{decision_id}/context`: persisted regime and market
  health context.
- `GET /api/v1/decisions/{decision_id}/trade-plan/freshness`: plan freshness.
- `GET /api/v1/market/instruments/{instrument_id}/candles`: recent persisted
  intraday candles only today; no D1 API is exposed.
- `GET /api/v1/market/instruments/{instrument_id}/quote`: live Kite quote with
  persisted fallback.
- `POST /api/v1/market/validate`: scoped ingest + score.
- `POST/GET /api/v1/market/validate-all`: background full-universe validation.
- `GET /api/v1/dashboard/summary`: consolidated dashboard summary.
- `GET /api/v1/analytics/performance/snapshots`: portfolio analytics snapshots
  provider endpoint, but current live backing is not the My Portfolio analysis
  snapshot requested here.

Missing APIs for My Portfolio:

- Upload/parse/preview holdings file.
- Confirm import/reconcile holdings.
- List canonical My Portfolio holdings.
- Start/poll Sync Portfolio.
- Return 20-column Portfolio Snapshot rows.
- Return import history, sync history, mapping errors, partial-success status.

## 9. Existing Dashboard/UI

Current dashboard first tab is `Portfolio Overview`, not a separate `My
Portfolio` tab. It shows:

- Total portfolio value.
- Cash available/reserved.
- Active positions and closed count.
- Track record cards.
- Near misses.
- Holdings & Exposure table with 6 columns: Symbol, Quantity, Avg Cost, Current
  Value, Unrealized P&L, Actions.
- Log fill form.
- Capital allocation pools.
- Reset fills controls.

Current row action `Add & validate` calls the existing validate-symbol path.
This is conceptually close to Sync for one holding, but it is not a portfolio
sync. There is no upload control and no 20-column table.

## 10. Existing Tests

Relevant tests:

- `tests/runtime/test_portfolio.py`: PortfolioEngine lifecycle, immutability,
  history, decision application, scheduled pipeline integration.
- `tests/runtime/test_portfolio_analytics.py`: P&L, performance snapshots,
  analytics history, full Phase-5 style pipeline integration.
- `tests/runtime/test_dashboard.py`: dashboard snapshot generation from
  portfolio, execution, allocation, analytics artifacts.
- `tests/api/v1/test_owner_portfolio.py`: owner fill API, reset behavior,
  SQLite provider cash computation.
- `tests/api/platform/test_dashboard_hosting.py`: dashboard static assembly and
  UI regression checks including portfolio JS presence.
- Repository tests for candles, quotes, decisions, and point-in-time reads.
- Symbol tests under `tests/symbols/` for symbol master, groups, universes,
  eligibility, and resolved universe persistence.

Test gaps for My Portfolio:

- CSV/XLSX parser contract.
- Provider-independent column mapping.
- Symbol resolution ambiguity/unresolved behavior.
- Import preview and confirmation.
- Reconciliation semantics.
- Sync partial success and freshness.
- Analysis snapshot history.
- 20-column API and dashboard rendering.

## 11. Market Data / Candle Architecture

Market data persistence is centralized in SQLite:

- `candles` stores all timeframes keyed by `(instrument_id, timeframe, ts_open)`.
- `quotes` stores quote history keyed by `(instrument_id, ts)`.
- `SqliteRepository.get_candles()` returns bounded chronological candles.
- `SqliteRepository.list_candles_recent()` returns most recent candles
  oldest-first, with optional `as_of` market-time cutoff.
- `SqliteRepository.get_latest_quote()` returns a bounded latest quote with
  optional `as_of`.
- `LiveIngestionEngine` writes provider candles/quotes.
- `OwnerValidationPipeline` consumes persisted candles/quotes and writes
  decisions/traces/run detail.

After latest daily candle ingestion, current validation/scoring flow is:

1. Live ingestion writes candles/quotes/institutional data.
2. Universe/candidate resolution selects eligible instruments.
3. `OwnerValidationPipeline` reads D1 candles via `list_candles_recent(...,
   Timeframe.D1, as_of=as_of)`.
4. It computes regime, market health, sector health, indicators, scoring,
   confidence, risk, session/intraday contexts, relative strength, relative
   volume, and decisions.
5. It persists `Decision` and `DecisionTrace` rows and stores per-decision
   reports in run `detail_json`.

For Sync Portfolio, the preferred pattern is:

Market ingestion -> ATHENA candle persistence -> existing validation/scoring
cycle -> My Portfolio consumes stored market state, decisions, and reports.

Do not build a duplicate candle-fetching or indicator engine inside My
Portfolio.

## 12. Existing Technical/Decision Outputs Available to My Portfolio

Available now:

- Latest persisted decisions by instrument.
- Decision type: TRADE, WATCH, NO_TRADE, INSUFFICIENT_DATA, etc.
- Decision explanation.
- Direction.
- Gate results.
- TradePlan when decision type is TRADE: entry, stop_loss, one or more targets
  structurally, position_size, risk_amount, risk_reward, validity window.
- Score, confidence, risk blocks from persisted decision reports in run detail.
- Confidence level HIGH/MEDIUM/LOW when report confidence is OK.
- Regime evidence labels including trend.
- Market health context.
- Sector health used in scoring when mapped.
- Intraday context: session, VWAP, confluence, opening range, relative strength,
  gap, relative volume in current workflow capture/report path.
- Latest persisted candles/quotes.

Partially available:

- Trend/setup: score component `trend`, regime trend, confluence, technical
  structure, and decision explanation exist, but no single canonical "Trend /
  Setup" column exists.
- Key trigger: TradePlan entry zone can serve as an entry trigger for TRADE
  decisions only; WATCH/NO_TRADE rows often lack a trigger.
- Support/exit: TradePlan stop_loss can serve as invalidation/exit for TRADE
  decisions only; support levels are not separately modeled.
- Targets: TradePlan has a tuple, but the current DecisionEngine builds exactly
  one ATR target.
- Status/Next Action: decision type and freshness can inform a portfolio
  interpretation, but no portfolio-specific status/action mapping exists.

Missing:

- Canonical portfolio analysis snapshot per holding.
- Portfolio-specific interpretation layer.
- Support 1 vs Major Support / Exit distinction.
- Target 2 and Target 3 methodology in ATHENA core.
- Audit trail tying a sync to market-data-through and analysis-version.

## 13. Complete 20-Column Source Mapping

| Field | Input / Derived | Existing Source | Existing Component | Available Now? | Gap | Proposed Owner |
|---|---|---|---|---|---|---|
| Symbol | Input, then canonicalized | Uploaded file; `symbol_master`/`instruments` | `athena.symbols`, `SqliteRepository.get_instrument/list_instruments` | Partially | Current portfolio API accepts raw uppercased strings; no import resolver or ambiguity handling | My Portfolio import/mapping |
| Qty | Input portfolio fact | Uploaded file; currently manual form | `owner_positions.quantity`; `Holding.quantity` | Partially | No upload/update holdings flow; no reconciliation semantics | My Portfolio holdings |
| Avg Price | Input portfolio fact | Uploaded file; currently manual form | `owner_positions.avg_price`; `Holding.avg_price` | Partially | No upload/update holdings flow; no import validation | My Portfolio holdings |
| Last Price | Derived by ATHENA | Quotes or latest D1 close | `quotes`, `candles`, `MarketHistoryService.instrument_quote` | Partially | Current owner provider uses quotes, not latest D1 close; dashboard computes value client-side | My Portfolio sync |
| Price As Of | Derived by ATHENA | Quote `ts` or D1 candle `ts_open` | `Quote.ts`, `Candle.ts_open` | Partially | Not exposed on portfolio rows today | My Portfolio sync |
| Investment | Derived portfolio math | Qty x Avg Price | Dashboard JS; `PortfolioAnalyticsEngine` style math | Partially | Currently client-side in holdings table, not persisted/server-owned | My Portfolio math |
| Current Value | Derived portfolio math | Qty x Last Price | Dashboard JS; analytics engine if supplied current prices | Partially | Server should compute from sync snapshot | My Portfolio math |
| P&L | Derived portfolio math | Current Value - Investment | Dashboard JS; `PortfolioAnalyticsEngine.unrealized_pnl` | Partially | Server-side row value missing | My Portfolio math |
| P&L % | Derived portfolio math | P&L / Investment | Can be computed exactly | Missing | Not currently present on portfolio row DTO | My Portfolio math |
| Status | Derived interpretation | Decision type, gates, freshness, holding state | `Decision.decision_type`, `get_trade_plan_freshness` | Partially | Requires owner-approved portfolio status vocabulary; must not alter DecisionEngine | My Portfolio interpretation |
| Conviction | Derived from existing intelligence | Score/confidence/decision type | Decision report score/confidence; `confidence_level` | Partially | Need mapping rule: score? confidence? both? no arbitrary thresholds | My Portfolio interpretation with owner decision |
| Trend / Setup | Derived from existing intelligence | Regime trend, score trend component, confluence, technical structure, decision explanation | Scoring report, regime, intraday signal set | Partially | No canonical single field; needs selection rule and wording | My Portfolio interpretation |
| Key Trigger | Derived from existing intelligence | TradePlan entry zone; maybe decision explanation | `Decision.trade_plan.entry_low/high` | Partially | WATCH/non-TRADE rows may lack trigger; no separate trigger field | Existing decision output where present; My Portfolio gap handling |
| Support 1 | Derived from existing intelligence | None found as separate support level | Possibly TradePlan stop_loss only | Missing | No support/resistance algorithm/model in core ATHENA | Owner decision; do not invent in PS-P1 |
| Major Support / Exit | Derived from existing intelligence | TradePlan stop_loss for TRADE | `Decision.trade_plan.stop_loss` | Partially | Stop/invalidation is not identical to support; absent for non-TRADE | Existing decision output where present; owner decision for broader support |
| Target 1 | Derived from existing intelligence | TradePlan target | `Decision.trade_plan.targets[0]` | Partially | Only present on TRADE decisions with plan | Existing Decision output |
| Target 2 | Derived from existing intelligence or new methodology | TradePlan structurally supports tuple | Current DecisionEngine builds one ATR target | Missing | Multiple targets would require methodology decision unless existing tuple already populated by another path | Owner/Chief Architect |
| Target 3 | Derived from existing intelligence or new methodology | TradePlan structurally supports tuple | Current DecisionEngine builds one ATR target | Missing | Same as Target 2 | Owner/Chief Architect |
| Next Action | Derived interpretation | Decision type, explanation, freshness, gates | Decision DTO, counterfactual/freshness APIs | Partially | Needs portfolio-specific mapping; must not become new decision methodology | My Portfolio interpretation with owner decision |
| Last Review | Derived audit/freshness | Sync timestamp or latest decision timestamp | `Decision.ts`, run detail, future sync snapshot | Partially | No portfolio sync timestamp or analysis snapshot today | My Portfolio sync/audit |

## 14. Import Architecture Findings

No existing portfolio CSV/XLSX import path was found. Existing file handling is
market-data FileProvider CSV, not broker-holdings import.

Recommended importer boundary:

- Accept CSV/XLSX only as input.
- Parse into a provider-independent `ImportedHoldingRow` contract.
- Require at minimum Symbol, Qty, Avg Price after mapping.
- Preserve source metadata and original row values.
- Normalize but do not resolve symbols inside the parser.
- Resolve symbols in a separate mapping layer using canonical `instrument_id`.
- Produce an import preview with accepted rows, rejected rows, ambiguity rows,
  and warnings.
- Apply changes only after owner confirmation.

Provider-specific parsers can be added later as adapters. The canonical import
contract should not assume any one broker's column names.

## 15. Reconciliation Findings

Current architecture does not answer whether uploads are transactions,
snapshots, or reconciliation instructions.

Options:

- Transaction-derived reconciliation: uploaded differences become inferred buy
  or sell transactions. Pros: best auditability and realized P&L. Cons: cannot
  infer true trade dates/prices from a holdings snapshot without fabricating.
- Snapshot replacement/reconciliation: uploaded rows replace the canonical open
  holdings state after validation. Pros: matches broker holdings files and keeps
  Qty/Avg Price owner-supplied. Cons: realized P&L and partial sells are not
  reconstructable unless supplied separately.
- Hybrid: current holdings are snapshot-owned; optional transaction/outcome
  records are logged only when explicitly supplied. Pros: honest and practical.
  Cons: requires clear UI/audit language.

Recommendation: prefer hybrid with snapshot-based open holdings for PS-P1, but
record import/reconciliation events so transaction support can arrive later
without pretending inferred trades happened.

## 16. Sync Portfolio Architecture Findings

Upload/Import and Sync must be separate:

- Upload/Update Holdings changes canonical holdings facts: instrument, Qty, Avg
  Price, existence of open holding.
- Sync Portfolio does not change Qty or Avg Price. It refreshes ATHENA-derived
  fields.

Recommended Sync flow:

1. Load canonical My Portfolio holdings.
2. Resolve/verify each holding's `instrument_id`.
3. Check latest persisted D1 candle/quote availability.
4. If data is stale/missing, optionally invoke existing scoped ingest/validation
   mechanism rather than direct per-holding provider calls.
5. Run or reuse `OwnerValidationPipeline` scoped to portfolio symbols.
6. Read latest persisted decisions and decision reports by instrument.
7. Build My Portfolio analysis snapshot rows.
8. Persist sync status, market-data-through, per-row errors, and snapshot.
9. Refresh dashboard.

Existing background-job pattern:

- `src/athena/ops/full_validation.py` runs a daemon thread, uses
  `CycleRunnerLock`, opens its own SQLite connection, and exposes progress via
  `POST/GET /api/v1/market/validate-all`.

Normal-size portfolios may be able to sync synchronously, but because Sync can
trigger ingestion and validation, the safer PS-P1 design is a background job
reusing the existing single-flight pattern.

## 17. Portfolio Interpretation Boundary

Separation of concerns:

Portfolio Facts:

- Holding exists.
- Canonical `instrument_id`.
- Qty.
- Avg Price.
- Import source metadata.

Portfolio Math:

- Investment.
- Current Value.
- P&L.
- P&L %.
- Aggregated totals.

Existing ATHENA Intelligence:

- Last price/market data.
- Indicators.
- Regime/market/sector health.
- Score.
- Confidence.
- Risk.
- Decision.
- TradePlan entry/stop/target.
- DecisionTrace and persisted report.

Portfolio Interpretation Layer:

- Status.
- Conviction label.
- Trend / Setup label.
- Key Trigger selection.
- Next Action wording.
- Portfolio-row freshness.

The interpretation layer may translate existing outputs, but must not invent
new technical thresholds, target rules, support algorithms, or DecisionEngine
methodology.

## 18. Freshness / Review Semantics

Freshness dimensions required for My Portfolio:

- `portfolio_imported_at`: when holdings facts last changed from upload/import.
- `holdings_as_of`: timestamp/date represented by the input source when known.
- `market_data_through`: latest D1 candle date or quote timestamp used.
- `last_synced_at`: when derived analysis was refreshed.
- `analysis_version`: version of My Portfolio row-building logic.
- `decision_as_of`: latest ATHENA decision timestamp consumed per holding.
- `price_as_of`: price timestamp/date per row.

Current dashboard has advisory freshness for market/decision views and plan
freshness for individual decisions. It does not have portfolio import/sync
freshness.

## 19. Audit / History Capabilities

Existing audit strengths:

- Decisions are persisted with run/cycle IDs.
- Decision traces are persisted.
- Run detail stores per-decision reports.
- Candles and quotes retain market-time history.
- Symbol groups and resolved universes retain dating/provenance.
- `PortfolioEngine` has append-only in-memory history.
- Backup is created before owner-fill reset.

Missing for My Portfolio:

- Uploaded source metadata.
- Import batch history.
- Original row values.
- Mapping decisions and unresolved/ambiguous rows.
- Previous vs reconciled holdings diff.
- Sync run history.
- Per-holding analysis snapshots.
- Partial-success status.
- Market-data-through date per sync.
- Durable analysis version/digest.

## 20. Identified Gaps

- No CSV/XLSX holdings importer.
- No canonical My Portfolio schema.
- No import preview/confirmation workflow.
- No provider-independent column mapping.
- No symbol mapping workflow for portfolio uploads.
- Current owner fill API stores raw strings and may not canonicalize to
  `NSE:SYMBOL`.
- No reconciliation model decision.
- No Sync Portfolio API/job.
- No 20-column portfolio snapshot API.
- No server-owned portfolio row math for all requested fields.
- No support/resistance output separate from TradePlan stop.
- Only Target 1 exists in current DecisionEngine output.
- No Status/Conviction/Next Action mapping approved for portfolio context.
- No portfolio analysis snapshot/history persistence.
- Current dashboard has Portfolio Overview, not separate My Portfolio tab.

## 21. Risks / Regression Concerns

- Accidentally changing ScoringEngine/DecisionEngine to serve portfolio labels
  would violate the dependency boundary.
- Treating uploaded files as storage would create a second, uncontrolled
  portfolio database.
- Treating raw symbols as identity risks symbol changes, exchange ambiguity, and
  duplicate ticker names.
- Inferring transactions from holdings snapshots could fabricate realized P&L.
- Computing P&L client-side would conflict with server-owned explainable values.
- Running per-holding direct provider calls would duplicate the market-data
  pipeline and create rate-limit risk.
- Adding a separate tab could disturb dashboard routing and static JS assembly
  unless scoped carefully.
- Reusing `owner_positions` without migration/contract review risks mixing
  manual fill logging with canonical holdings reconciliation.
- Support/targets beyond existing Decision output are methodology-sensitive.

## 22. Files / Components Likely Involved

Likely backend additions:

- `src/athena/portfolio/imports.py` or a new subpackage under `portfolio/`.
- `src/athena/portfolio/sync.py`.
- `src/athena/portfolio/reconciliation.py`.
- `src/athena/portfolio/analysis.py`.
- `src/athena/api/v1/dtos/portfolio.py`.
- `src/athena/api/v1/services/portfolio_service.py`.
- `src/athena/api/v1/routers/portfolio.py`.
- `src/athena/api/v1/providers/sqlite_providers.py`.
- `src/athena/data/store/schema.py`.
- `src/athena/data/store/repository.py`.

Likely dashboard additions:

- `src/athena/api/static/index.html`.
- `src/athena/api/static/js/00-state-and-dom.js`.
- `src/athena/api/static/js/03-app-shell.js`.
- `src/athena/api/static/js/08-portfolio.js` or a new
  `my-portfolio` JS concern file.
- `src/athena/api/static/css/05-portfolio.css` or a new CSS concern file.
- `tests/api/platform/test_dashboard_hosting.py`.

Likely tests:

- New portfolio import/reconciliation tests.
- New repository schema tests.
- New API tests for upload/preview/confirm/sync.
- New Sync partial-success tests.
- New dashboard static assembly/rendering tests.
- Regression tests proving ScoringEngine/DecisionEngine behavior unchanged.

## 23. Explicit Do-Not-Change Boundaries

- Do not modify ScoringEngine methodology.
- Do not modify DecisionEngine methodology.
- Do not modify indicator formulas.
- Do not add support/resistance or target methodology inside portfolio sync.
- Do not add order placement, broker login automation, or trading automation.
- Do not make core ATHENA methodology depend on portfolio state.
- Do not add a second instrument master.
- Do not add a second market-data store.
- Do not use uploaded CSV/XLSX as persistent state.
- Do not redesign unrelated dashboard sections.
- Do not change DarvaX, EMR, or intraday methodology for this feature.

## 24. Recommended Architecture Direction

Add My Portfolio as an isolated extension of the existing `portfolio` module,
with its own persistence and sync state, while consuming:

- `symbol_master`/`instruments` for identity.
- `candles`/`quotes` for prices/freshness.
- existing ingestion and validation paths for data refresh.
- latest persisted decisions and decision reports for ATHENA intelligence.
- existing background-job/single-flight mechanics if sync can trigger ingest.

Recommended model:

- `portfolio_imports`: one row per upload/import batch.
- `portfolio_import_rows`: original parsed rows and validation/mapping status.
- `portfolio_holdings`: canonical current open holdings, keyed by
  `instrument_id` or by a stable position identity if the owner requires
  multiple independent lots.
- `portfolio_reconciliations`: before/after diffs for confirmed imports.
- `portfolio_sync_runs`: sync status, timestamps, data-through, partial-success
  counters.
- `portfolio_analysis_snapshots`: immutable row-level derived values and source
  refs.

This can live in `db/athena.db` as part of the portfolio module, unless the
owner/chief architect decides the "self-contained feature/module" requirement
means a DarvaX-style isolated database and ADR.

## 25. Proposed PS-P1 Scope

PS-P1 should be a design/schema/API contract milestone only, not full UI or full
sync implementation.

Recommended PS-P1 boundary:

- Freeze My Portfolio source-of-truth and reconciliation model.
- Define import row contract for CSV/XLSX preview.
- Define canonical holdings schema and analysis snapshot schema.
- Define symbol mapping semantics and unresolved/ambiguous behavior.
- Define 20-column DTO contract with explicit null/freshness/error fields.
- Define Sync Portfolio job contract and partial-success states.
- Add tests for parser boundary, mapping boundary, schema contracts, and
  no-methodology-change regressions.

Explicitly defer:

- Multi-broker-specific parsers beyond a generic configurable parser.
- Actual dashboard tab implementation if schema/API is not approved.
- Target 2/3 methodology.
- Support/resistance methodology.
- Realized P&L transaction reconstruction beyond snapshot reconciliation.

## 26. Owner / Chief Architect Decisions Required

1. Is My Portfolio allowed to extend the existing frozen `portfolio` module
   without an ADR, or does its self-contained persistence/API/sync surface
   require an ADR?
2. Should My Portfolio use the same `db/athena.db` or a separate database?
3. Should current holdings be snapshot-reconciled, transaction-derived, or
   hybrid?
4. Can one canonical open holding per `instrument_id` satisfy the product, or
   must multiple lots/position episodes exist per instrument?
5. Should `owner_positions` be migrated/reused, bridged read-only, or left as a
   legacy manual-fill ledger separate from My Portfolio?
6. What should happen when an uploaded symbol resolves to multiple instruments
   or no instruments?
7. Should Sync invoke scoped ingest automatically, or only consume already
   persisted ATHENA market data?
8. Should Sync be synchronous for small portfolios or always a background job?
9. What vocabulary should Status use?
10. What existing measure defines Conviction: confidence level, composite score,
    decision type, or an owner-approved combination?
11. What exact rule maps existing Decision Brief outputs to Next Action?
12. Are Target 2 and Target 3 required before launch, and if yes, who owns the
    methodology?
13. Are Support 1 and Major Support / Exit allowed to use only existing
    TradePlan stop/entry data, or is a new support/resistance methodology
    required?
14. Should closed positions, cash, reserved capital, allocation, and realized
    P&L be in PS-P1 or explicitly deferred?

## Implementation-Readiness Verdict

READY FOR PS-P1 WITH OWNER DECISIONS

Concrete reasons:

- Existing ATHENA market data, decision, trace, scoring, confidence, risk, and
  dashboard infrastructure can be reused without changing core methodology.
- Current portfolio persistence exists, but it is only an owner fill ledger and
  is not sufficient as the canonical My Portfolio source of truth.
- Import, reconciliation, sync status, and analysis snapshot persistence are
  missing and need a narrow design/schema milestone.
- Several required columns are only partially available; Support 1, Target 2,
  Target 3, Status, Conviction, and Next Action require owner-approved
  interpretation or methodology boundaries.
- PS-P1 can proceed only after source-of-truth, reconciliation, identity, sync
  job, and interpretation decisions are settled.
