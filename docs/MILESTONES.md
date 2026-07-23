# ATHENA — Milestone Roadmap

Official milestone roadmap per the milestone-based workflow (AGENTS.md).
One milestone at a time; owner approval gates every transition. A milestone
too large for a single-sitting review is split BEFORE implementation.

## Phase 0 — Foundations ✅ APPROVED (2026-07-20)

Delivered as one batch before this workflow existed; retroactive milestone map:
M0.1 Repository & Project Setup · M0.2 Canonical Domain Model · M0.3 Configuration
Framework · M0.4 Trading Calendar · M0.5 Observability & CLI.

## Phase 1 — Data Foundation ✅ APPROVED (2026-07-20)

| Milestone | Scope | Status |
|---|---|---|
| **M1.1** MarketDataProvider Contracts | Provider Protocol hardening, ProviderCapabilities, ProviderHealth, behavioral contract, reusable contract test suite | ✅ Approved |
| **M1.2** FileProvider | FileProvider; daily/intraday/instrument/quote loaders; provider health | ✅ Approved |
| **M1.3** Validation Layer | Freshness, OHLC, duplicate, gap validation; validation reports; quarantine handling | ✅ Approved |
| **M1.4** Corporate Actions Engine | Splits, bonuses, dividends, renames; historical adjustment strategy | ✅ Approved |
| **M1.5** SQLite Repository | Schema, WAL, foreign keys, repository layer, append-only storage, integrity verification | ✅ Approved |
| **M1.6** Backup & Restore | Backup, restore, recovery validation, repository recovery tests | ✅ Approved |

## Phase 2 — Market Intelligence ✅ APPROVED (2026-07-21)

| Milestone | Scope | Status |
|---|---|---|
| **M2.1** Regime Engine | Deterministic regime (trend/volatility/gap) with evidence | ✅ Approved |
| **M2.2** Market Health | Breadth, trend quality, participation, momentum, volatility health | ✅ Approved |
| **M2.3** Sector Health | Sector-level strength, deterministic + explainable | ✅ Approved |
| **M2.4** Universe Engine | Investable universe construction with explainable inclusion | ✅ Approved |

## Phase 3 — Decision Intelligence ✅ APPROVED (2026-07-21)

| Milestone | Scope | Status |
|---|---|---|
| **M3.1** Evidence Aggregation | Single immutable evidence graph with provenance + missing detection | ✅ Approved |
| **M3.2** Indicator Engine | Deterministic technical indicators (SMA/EMA/RSI/ATR/MACD/ADX/vol avgs) | ✅ Approved |
| **M3.3** Scoring Engine | Transparent component scores from approved evidence/indicators | ✅ Approved |
| **M3.4** Confidence Engine | Evidence reliability (completeness, agreement, freshness, contradictions) | ✅ Approved |
| **M3.5** Risk Engine | Descriptive trading-risk assessment (volatility/liquidity/gap/event/concentration) | ✅ Approved |
| **M3.6** Decision Engine | First explainable decisions from bundle+indicators+scores+confidence+risk | ✅ Approved |
| **M3.7** Decision Trace & Reporting | Human + machine-readable decision reports | ✅ Approved |

## Phase 4 — Orchestration & Operational Intelligence ✅ APPROVED (2026-07-21)

Turns the analytical core into an operational platform; consumes Phase 0–3 engine outputs only, modifies no analytical engine.

| Milestone | Scope | Status |
|---|---|---|
| **M4.1** Workflow Orchestration Engine | Deterministic DAG pipeline runner (stages, execution, report, failure isolation, replay) | ✅ Approved |
| **M4.2** Daily Market Scanner | Run ATHENA across the universe → DailyScanReport | ✅ Approved |
| **M4.3** Watchlist Manager | Dynamic watchlists from decision outcomes | ✅ Approved |
| **M4.4** Strategy Framework | Deterministic strategies consuming DecisionReport | ✅ Approved |
| **M4.5** Backtesting Engine | Historical replay through the full pipeline | ✅ Approved |
| **M4.6** Reporting & Analytics | Daily/weekly/monthly summaries + statistics | ✅ Approved |
| **M4.7** Scheduling Framework | Daily/weekly/manual/replay/batch job scheduling | ✅ Approved |

## Phase 5 — Portfolio & Execution Platform ✅ APPROVED (2026-07-21)

Manages capital responsibly; consumes completed Decision artifacts produced by the existing pipeline; performs no market analysis.

| Milestone | Scope | Status |
|---|---|---|
| **P5.1** Portfolio Engine | Deterministic portfolio state, holdings, cash allocation, reserved capital, closed positions | ✅ Approved |
| **P5.2** Capital Allocation Engine | Capital allocation policy and reserve floor enforcement | ✅ Approved |
| **P5.3** Position Sizing Engine | Executable unit quantity calculation & precision handling | ✅ Approved |
| **P5.4** Order Planning Engine | Broker-neutral execution instructions & order batching | ✅ Approved |
| **P5.5** Broker Abstraction Layer | Canonical broker contracts & capability validation | ✅ Approved |
| **P5.6** Order Lifecycle Engine | Order tracking, fill reconciliation, state machine | ✅ Approved |
| **P5.7** Portfolio Analytics & Performance | Realized P&L, performance metrics, portfolio statistics | ✅ Approved |

## Phase 6 — Reporting, Dashboards & User Intelligence ✅ APPROVED (2026-07-21)

Presents, organizes, and explains information already produced by the core platform; read-only; no state mutation.

| Milestone | Scope | Status |
|---|---|---|
| **P6.1** Reporting Framework | Generic operational reporting engine (portfolio, execution, allocation, analytics, audit) | ✅ Approved |
| **P6.2** Dashboard & Snapshot Engine | Derived, read-only dashboard views & snapshots | ✅ Approved |
| **P6.3** Explainability Engine | Human-readable decision & performance explanations | ✅ Approved |
| **P6.4** Timeline & Audit Engine | End-to-end pipeline audit reconstruction & timelines | ✅ Approved |
| **P6.5** Operational Monitoring | Execution pipeline & component health observing | ✅ Approved |
| **P6.6** Export & Presentation Layer | Deterministic presentation formatting & export | ✅ Approved |
| **P6.7** Unified Intelligence Workspace | Read-only operational workspace orchestration | ✅ Approved |

## Phase 7 — Production Orchestration & Scheduling ✅ APPROVED (2026-07-21)

Integrated runtime orchestration layer linking all pipelines and job schedules.

| Milestone | Scope | Status |
|---|---|---|
| **P7.1** Generic Pipeline Infrastructure | Immutable models for stage execution, context propagation, definition, and history | ✅ Approved |
| **P7.2** Execution Pipeline Registration | Dual-root execution topology combining portfolio, capital allocation, sizing, and analytics | ✅ Approved |
| **P7.3** Intelligence Pipeline Registration | Wiring 6 presentation/intelligence stage adapters under declarative topology | ✅ Approved |
| **P7.4** Pipeline Runner Integration | PipelineContract validation, PipelineCoordinator, WorkspaceAssembler, and SystemPipelineRunner | ✅ Approved |
| **P7.5** Pipeline Scheduler Registration | Scheduling-domain bridge adapter wrapping ScheduledJob, ScheduleRunRequest, and history | ✅ Approved |

## Phase 8 — Application Platform ✅ APPROVED (2026-07-22)

Exposes internal pipeline artifacts, execution records, portfolios, and reports through a production-grade REST API.

| Milestone | Scope | Status |
|---|---|---|
| **P8.1** Platform API Foundation | FastAPI integration, ASGI/Lifespan lifecycle, unified response envelope, Problem Details, Health/Metrics | ✅ Approved |
| **P8.2** Authentication & RBAC | Users, Roles, Permissions, JWT, API Keys, Sessions, Audit Logging | ✅ Approved |
| **P8.3** Core Platform APIs | Decisions, Portfolios, Pipelines, Scheduler, and Workspace endpoints | ✅ Approved |
| **P8.4** Reports, Analytics & Export APIs | Generic Reports, Portfolio Analytics snapshots, and file format exports | ✅ Approved |
| **P8.5** API Platform Completion | Versioning, metadata endpoints, request context middleware, audit logger, and OpenAPI audit | ✅ Approved |

## Phase 9 — Dashboard & Operations Console (COMPLETE)

Builds the visual workstation dashboard console for a single-user Swing/Intraday trading platform.

| Milestone | Scope | Status |
|---|---|---|
| **P9.1** Dashboard Architecture | Static asset hosting, fallback routing, dashboard HTML/CSS workstation layout | ✅ Approved |
| **P9.2** Consolidated Dashboard API | High-performance aggregated summary endpoint, sidebar & header telemetry integrations | ✅ Approved |
| **P9.3** Portfolio & Capital Dashboard | NAV area line chart, Sector Exposure donut, Holdings grid, and single-user bypass | ✅ Approved |
| **P9.4** Market & Universe Dashboard | Trading calendar session grid, Volatility regime badges, Universe inclusion traces | ✅ Approved |
| **P9.5** Strategy & Backtest Workspace | Strategy profiles matrix, Backtest performance metrics & drawdown charts | ✅ Approved |
| **P9.6** Decision Trace DAG Viewer | Briefing documents browser, interactive Decision Trace React Flow DAG viewer | ✅ Approved |
| **P9.7** Live Monitoring & Admin | SSE live warning streams, stage telemetry bar charts, manual DB backup/restore controls | ✅ Approved |

**Phase 9 closed (2026-07-23):** owner approved P9.7; console hotfixes and Overview correctness patches remain recorded in `IMPLEMENTATION_SUMMARY.md`.

## Phase 10 — Live Dry-Run Operations & AI Playbook Learning (AUTHORIZED)

Establishes live scheduled paper-trading operations, real-time market data ingestion, daily trace briefings, and automated playbook diagnostics. One milestone in flight at a time.

| Milestone | Scope | Status |
|---|---|---|
| **M10.1** Live Data Ingestion | Real-time broker/feed Quote and Candle ingestion, duplicate/freshness validation in live loop | ✅ APPROVED |
| **M10.2** Scheduled Dry-Run Operations | Premarket and periodic intraday refresh cycles running daily on scheduler, logging to SQLite | ❌ Not started |
| **M10.3** Daily Briefing Notifications | Automated email/webhook notifications dispatching daily decision traces and summaries | ❌ Not started |
| **M10.4** AI Playbook Diagnostics | Diagnostic analysis over Decision Journal outcomes, proposing configuration weight tuning suggestions | ❌ Not started |

---

*Status legend: a milestone is "In Progress" (🔄) when actively being designed or built, "Approved" (✅) only when the owner signs off. Never two milestones in flight.*
