# ATHENA — Implementation Summary

Permanent implementation log. One section per completed phase, newest first,
in the 7-part format mandated by CLAUDE.md. Written before owner review;
status updated on approval.

---

## Dashboard live data + owner fill ledger (READY FOR REVIEW)

| | |
|---|---|
| Completed | 2026-07-24 |
| Scope | Remove dashboard seed/demo data; serve Decisions + Market Intelligence from SQLite; owner-entered Kite/Groww fill ledger for Portfolio Overview |
| Tests | API + data_layer green; new `tests/api/v1/test_owner_portfolio.py`; decision-trace + dashboard-summary updated for empty/real data |
| Status | **READY FOR REVIEW** |
| Branch | develop |

- Dropped `seed_sample_data` from API startup; live app wires `SqliteDecisionProvider`, `SqlitePortfolioProvider`, `SqlitePipelineRunProvider` via `wire_sqlite_providers`.
- Decision traces return **stored** `DecisionTrace` stages only (no synthetic 7-stage DAG).
- SCHEMA_VERSION 4: `owner_positions` table; `POST /api/v1/portfolio/positions` + `.../close` for manual fills (symbol/qty/entry/exit); cash from `config/portfolio.json` `initial_cash` (`PortfolioConfig`).
- Market Intelligence: latest SQLite run context; falls back to `kite.json` symbols when run has no universe payload; honest empty copy when neither exists.
- Dashboard Overview form to log/close owner fills; no Kite holdings API (still blocked).

Files created: `src/athena/api/v1/providers/sqlite_providers.py`, `config/portfolio.json`, `tests/api/v1/test_owner_portfolio.py`. Files modified: schema/serialization/repository, dependencies/app, decisions/portfolio/dashboard services + routers/DTOs, dashboard static assets, tests, this log. No ADR; no order placement; frozen Position/TradeOutcome contracts reused.

---

## Production readiness -- R6 Closing / Day-Summary Cycle (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Post-close `CLOSING` cadence + dry-run cycle; briefing day roll-up + journal prompts (Blueprint §8). |
| Tests | Cadence closing cases; briefing day_summary + journal prompt clear when journaled |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- `RunTrigger.CLOSING`; `scheduling.closing` (`run_at` default 15:45); `is_closing_due` / `due_triggers`.
- Dry-run + `run-due` / CLI `cycle --trigger closing` support CLOSING.
- Briefings include `day_summary` + `journal_prompts` for decisions lacking journal rows.

Files created: (none new top-level). Files modified: `config/scheduling.json`, `src/athena/domain/enums.py`, `src/athena/config/models.py`, `src/athena/scheduling/{cadence,dry_run,__init__}.py`, `src/athena/notifications/{models,builder,__init__}.py`, `src/athena/ops/scheduled_run.py`, `src/athena/cli.py`, `docs/*`, tests. Public APIs: `is_closing_due`, `BriefingJournalPrompt`, extended `DailyBriefing`. No ADR; no order methods.

---

## Production readiness -- R5 Host Schedule + Failure Alerts (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | External launchd/cron invokes due cycles + brief; hard failures alert via file + webhook (DD-9). No embedded cron. |
| Tests | `tests/ops/test_host_ops.py` (file alert, webhook mock, idle path, failure alert, brief-after-cycle) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- CLI `athena run-due` + root `./athena-run-due` (sources `.env` for launchd).
- `HostDueRunner` evaluates cadence, runs due PREMARKET/REFRESH, optional brief, alerts on `AthenaError`.
- `FailureAlertDispatcher`: `artifacts/alerts/` + `ATHENA_ALERT_WEBHOOK_URL` (fallback `ATHENA_WEBHOOK_URL`).
- Docs: `docs/ops/HOST_SCHEDULE.md` + launchd plist example; email SMTP still deferred.

Files created: `config/host_ops.json`, `src/athena/ops/{failure_alerts,scheduled_run}.py`, `athena-run-due`, `docs/ops/HOST_SCHEDULE.md`, `docs/ops/launchd/com.athena.run-due.plist.example`, `tests/ops/test_host_ops.py`. Files modified: `src/athena/config/{models,loader,__init__}.py`, `src/athena/cli.py`, `src/athena/ops/__init__.py`, `.env.example`, `docs/*`, `README.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `HostDueRunner`, `FailureAlertDispatcher`, `load_host_ops_config`, `athena run-due`. No ADR; localhost/secrets policy preserved; no order methods.

---

## Production readiness -- R4 Kite Live Provider Adapter (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Read-only Zerodha Kite `MarketDataProvider`; config-selected bind; FileProvider remains default; secrets in `.env` only. |
| Tests | Contract suite green via fake transport; unit tests for quotes/candles/snapshot/allowlist; owner live smoke: INFY ingest OK |
| Status | **APPROVED** — Owner approved 2026-07-23 (live smoke + runbook) |
| Branch | develop |

- `KiteProvider` + allowlisted GET-only `UrllibKiteTransport` (`/instruments*`, `/quote*` only — no order paths, no kiteconnect SDK).
- Config: `config/providers/kite.json`; `ingestion.provider` accepts `file` \| `kite` (default `file`).
- Factory `build_market_data_provider`; CLI ingest/cycle loads `.env` then resolves provider.
- Ops: `docs/ops/KITE_LIVE_DATA.md` (token refresh, enable steps, limits); root `./kite-auth` interactive helper.
- Instrument ids: `NSE:SYMBOL`. Snapshot: index LTPs + India VIX; breadth left 0.

Files created: `src/athena/data/providers/{kite_provider,kite_transport,factory}.py`, `src/athena/config/env.py`, `config/providers/kite.json`, `docs/ops/KITE_LIVE_DATA.md`, `tests/data_layer/test_kite_provider.py`, `tests/contract/test_kite_provider_contract.py`. Files modified: `src/athena/config/{models,loader,__init__}.py`, `src/athena/cli.py`, `src/athena/api/app.py`, `config/ingestion.json`, `.env.example`, `docs/*`, `IMPLEMENTATION_SUMMARY.md`, `README.md`. Public APIs: `KiteProvider`, `build_market_data_provider`, `load_kite_provider_config`, `load_dotenv`. No ADR; frozen Protocol unchanged; no order methods.

---

## Production readiness -- R3 DD-1 Live Vendor Decision (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Written DD-1 decision record: criteria matrix, candidate vendors, **Zerodha Kite Connect** accepted; **no adapter code**. |
| Tests | N/A (documentation milestone) |
| Status | **APPROVED** — Owner approved 2026-07-23 (existing Kite account; Groww for manual execution only) |
| Branch | develop |

- Created `docs/decisions/DD-1-broker-live-data-vendor.md` against ATHENA-002 §15 and ADR-002.
- Recommendation: **Zerodha Kite Connect** as first live provider for R4; FileProvider remains default/fallback; C2 deep history deferred to DD-10/accumulation.
- Explicit non-goals: no R4 code, no orders, no websocket (DD-2).

Files created: `docs/decisions/DD-1-broker-live-data-vendor.md`. Files modified: `docs/MILESTONES.md`, `docs/PRODUCTION_READINESS_ROADMAP.md`, `README.md`, `IMPLEMENTATION_SUMMARY.md`.

---

## Production readiness -- R2 Decision Journal Persistence (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Persist Decision/Trace/Journal in SQLite (schema v3); SqliteDecisionSummarySource for `athena brief`; smoke seeds decision → briefing OK. |
| Tests | Full suite green; new `tests/data_layer/test_decision_journal.py`; smoke asserts briefing status OK |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- SCHEMA_VERSION 3: `decisions`, `decision_traces`, `decision_journal` tables.
- Repository: `save_decision`, `get_decision`, `get_trace`, `list_decisions`, `save_journal_entry`, `list_journal`.
- `SqliteDecisionSummarySource` wired into CLI brief; briefings reach OK when runs + decisions exist.
- Smoke seeds a fixture WATCH after cycle until live cycle emits decisions.

Files created: `src/athena/notifications/decision_source.py`, `tests/data_layer/test_decision_journal.py`. Files modified: `schema.py`, `serialization.py`, `repository.py`, `notifications/__init__.py`, `cli.py`, smoke script, ops SOP, MILESTONES, roadmap, IMPLEMENTATION_SUMMARY. No ADR; frozen Decision contracts unchanged; no order APIs.

---

## Production readiness -- R1 File-backed Daily Ops SOP (APPROVED)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Written SOP for file-backed daily advisory use; executable mock-day smoke on fixtures; fix CLI AthenaConfig nesting for due/cycle/brief/diagnose. |
| Tests | smoke script PASS + `tests/ops/test_file_backed_daily_smoke.py` |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

- Added `docs/ops/FILE_BACKED_DAILY_OPS.md` (prereqs, refresh CSVs, premarket/refresh CLI sequence, failure playbook, smoke checklist).
- Added `scripts/smoke_file_backed_day.sh` (temp config/DB, fixture FileProvider, health → due → cycle → brief → diagnose).
- Fixed Phase 10 CLI to read `cfg.base.*` / `cfg.market.*` correctly on `AthenaConfig`.

Files created: `docs/ops/FILE_BACKED_DAILY_OPS.md`, `scripts/smoke_file_backed_day.sh`, `tests/ops/test_file_backed_daily_smoke.py`. Files modified: `src/athena/cli.py`, `docs/MILESTONES.md`, `docs/PRODUCTION_READINESS_ROADMAP.md`, `IMPLEMENTATION_SUMMARY.md`, `README.md`. No ADR; R2+ still unauthorized.

---

## Phase 10 -- Live Dry-Run Operations & AI Playbook Learning (COMPLETE — owner closed 2026-07-23)

Phase outcome: M10.1–M10.4 owner-approved. FileProvider-backed dry-run ops, briefings, and propose-only playbook diagnostics delivered. Broker binding (DD-1) deferred. No order-placement code. Next: production-readiness tracks R1–R6 in `docs/PRODUCTION_READINESS_ROADMAP.md` (unauthorized until gated).

### M10.4 -- AI Playbook Diagnostics

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Rules-based playbook diagnostics over run ledger + injectable decisions/journal; TuningProposal artifacts only; `athena diagnose`; never auto-applies config. |
| Tests | 870 passed / 0 failed (11 new diagnostics tests) |
| Status | **APPROVED** — Owner approved 2026-07-23; closes M10.4 and Phase 10 |
| Branch | develop |

Implemented propose-only diagnostics (no LLM; no R2 journal schema; no config mutation).
- `PlaybookDiagnosticsAnalyzer`: ops failure rate, insufficient-data share, gate concentration, adherence → threshold/weight proposals with `min_sample_size` gate (`blocked=True` when under-sampled).
- Paired scoring weight proposals keep sum-100 invariant in the proposed snapshot.
- `PlaybookDiagnosticsService` + `DiagnosticReportWriter` → `artifacts/diagnostics/diag-<date>.{json,txt}`.
- CLI: `athena diagnose [--as-of] [--dry-run]` (dry-run accepted; apply path does not exist).

Files created: `config/diagnostics.json`, `src/athena/diagnostics/{__init__.py,models.py,analyzer.py,writer.py,service.py}`, `tests/runtime/test_diagnostics.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/errors.py`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `DiagnosticReport`, `TuningProposal`, `PlaybookDiagnosticsService`, `load_diagnostics_config`, `athena diagnose`. No ADR; human approval required for any config change; R1–R6 still unauthorized.

### M10.3 -- Daily Briefing Notifications

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Assemble immutable DailyBriefing from SQLite run ledger (+ optional injected decisions); dispatch via FileNotifier / optional WebhookNotifier; CLI `athena brief`. |
| Tests | 859 passed / 0 failed (8 new briefing tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented assemble→notify path (no decision-pipeline rebuild; no P8.9 alert center).
- `DailyBriefingBuilder`: runs for `as_of.date()` from ledger; missing runs → `BriefingError`; no decisions → `DEGRADED` with explicit reason; failed runs degrade.
- Notifiers: `FileNotifier` (JSON+txt), `WebhookNotifier` (`ATHENA_WEBHOOK_URL` from `.env`), `EmailNotifier` refuses loudly if enabled (SMTP deferred).
- `BriefingDispatcher` + config `notifications.json`; `--dry-run` forces file-only delivery.
- CLI: `athena brief [--as-of] [--dry-run]`.

Files created: `config/notifications.json`, `src/athena/notifications/{__init__.py,models.py,builder.py,notifiers.py,dispatch.py}`, `tests/runtime/test_daily_briefing.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/errors.py`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `DailyBriefing`, `BriefingDispatcher`, notifiers, `load_notifications_config`, `athena brief`. No ADR; secrets stay in `.env`; M10.4 AI deferred.

### M10.2 -- Scheduled Dry-Run Operations

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Premarket + intraday refresh cadence; dry-run cycle = ingest → optional paper pipeline hook → SQLite run ledger; CLI `athena due` / `athena cycle`. |
| Tests | 851 passed / 0 failed (12 new dry-run/cadence tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented schedule cadence and dry-run cycle orchestration (no embedded cron; external launcher may call CLI).
- Extended `SchedulingConfig` / `scheduling.json` with `premarket.run_at` and `refresh.interval_minutes` (null → `base.refresh_interval_minutes`).
- Pure cadence helpers: `is_premarket_due`, `is_refresh_due`, `due_triggers` (injected `as_of` + last-run markers).
- `DryRunCycleOrchestrator.run_cycle(trigger, as_of=…)`: `LiveIngestionEngine` → optional `DryRunPipeline` → persist `RunRecord` (FAILED runs saved before re-raise).
- SQLite schema v2: append-only `runs` table; `save_run` / `get_run` / `list_runs` / `latest_run`; `initialize` upgrades version.
- CLI: `athena due [--as-of]`, `athena cycle --trigger premarket|refresh [--as-of]`.

Files created: `src/athena/scheduling/{cadence.py,dry_run.py}`, `tests/runtime/test_dry_run_schedule.py`. Files modified: `config/scheduling.json`, `src/athena/config/models.py`, `src/athena/scheduling/__init__.py`, `src/athena/data/store/{schema.py,repository.py,serialization.py}`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: cadence helpers, `DryRunCycleOrchestrator`, `DryRunCycleResult`, run ledger methods, `athena due`/`cycle`. No ADR; no broker SDK; no order placement; M10.3 notifications / M10.4 AI deferred.

### M10.1 -- Live Data Ingestion

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Callable live ingest cycle: MarketDataProvider quotes/candles → duplicate/freshness validation → SQLite persist; FileProvider only; `athena ingest` CLI. |
| Tests | 839 passed / 0 failed (9 new ingestion tests) |
| Status | **APPROVED** — Owner approved 2026-07-23 |
| Branch | develop |

Implemented `LiveIngestionEngine.run_cycle(as_of=…)` as a deterministic poll→validate→persist step (scheduler deferred to M10.2).
- Config: `config/ingestion.json` + `IngestionConfig` / `load_ingestion_config` (provider=`file` only until DD-1).
- Reuses `DatasetValidator` (OHLC/duplicates/freshness; gaps off by default for live lookback) and `QuarantineRegistry`; adds `validate_quotes` for quote price/freshness/dupes.
- Empty candle fetches skip (provider contract); failed validation quarantines and raises `DataStaleError` / `DataValidationError` with no writes for that cycle’s failed path.
- `skip_existing` filters already-persisted candles/quotes for idempotent re-runs.
- CLI: `athena ingest [--as-of ISO]` wires FileProvider + calendar + SQLite (`ATHENA_DB_PATH` override).

Files created: `config/ingestion.json`, `src/athena/data/ingestion/{__init__.py,engine.py,models.py}`, `tests/data_layer/test_ingestion.py`. Files modified: `src/athena/config/{models.py,loader.py,__init__.py}`, `src/athena/data/validation/{validators.py,__init__.py}`, `src/athena/cli.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs: `LiveIngestionEngine`, `IngestionResult`, `build_ingest_validator`, `validate_quotes`, `load_ingestion_config`, `athena ingest`. No ADR; frozen `MarketDataProvider` unchanged; no broker SDK; no order methods.

---

## Phase 9 -- Dashboard & Operations Console (COMPLETE — owner closed 2026-07-23)

Phase outcome: single-user workstation console delivered and approved (P9.1–P9.7), including console reliability hotfixes and Overview capital correctness. Architecture frozen; no order-placement code; Phase 10 authorized after Phase 9 close.

### P9.7 -- Live Monitoring & Admin

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Replace Live Operations placeholder with SSE warning stream, stage telemetry Chart.js bars, and CONFIRM-gated SQLite backup/restore admin controls. |
| Tests | 830 passed / 0 failed (11 new ops + hosting update) |
| Status | **APPROVED** — closes P9.7 and Phase 9 (Owner approved) |
| Branch | develop |

Implemented Live Operations workstation APIs and UI on `#tab-operations`.
- Added `GET /api/v1/ops/stream` (SSE heartbeats + derived health/metrics/stage/database warnings).
- Added `GET /api/v1/ops/telemetry` aggregating latest pipeline stage statuses for charts.
- Added `GET/POST /api/v1/ops/backups` and `POST /api/v1/ops/backups/{id}/restore` reusing `create_backup` / `restore_backup`; restore requires exact token `CONFIRM`.
- Built Operations UI: EventSource warning feed, horizontal stage telemetry chart, backup list + create/restore admin panel.
- Clarified restore UX (CONFIRM unlocks buttons; explicit row click required; toast + last-restore feedback).
- Paths configurable via `ATHENA_DB_PATH` / `ATHENA_BACKUP_DIR` and `app.state.ops_*` for tests; missing live DB fails loudly (503).

Files created: `src/athena/api/v1/dtos/ops.py`, `src/athena/api/v1/services/ops_service.py`, `src/athena/api/v1/routers/ops.py`, `tests/api/v1/test_ops.py`. Files modified: `src/athena/api/v1/router.py`, `src/athena/api/dependencies.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/static/{index.html,dashboard.js,dashboard.css}`, `tests/api/platform/test_dashboard_hosting.py`, `docs/MILESTONES.md`, `IMPLEMENTATION_SUMMARY.md`. Public APIs added: ops stream/telemetry/backups/restore. No ADR; frozen contracts preserved; Phase 9 closed before Phase 10 authorization.

---

### Hotfix -- Console modal leak & loader failure UX (2026-07-23)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Repair workstation console defects observed in live screenshots: inactive modals leaking into page flow, silent loader failures leaving permanent "Loading..." states, and a fake Live Operations loader ahead of P9.7. |
| Tests | 819 passed / 0 failed (hosting suite extended +1) |
| Status | **OWNER VERIFIED** — not a new milestone; hardening of P9.1–P9.6 console |
| Branch | develop |

Root cause: `.modal-overlay` previously used `display: flex` while inactive (opacity-only hide), so trace/backtest modal chrome rendered inside the document flow across every tab. Concurrently, auth/env startup gaps caused API failures; strategies/decisions loaders swallowed errors and never cleared placeholder text.
- Moved trace and backtest modals outside `#app`, marked `hidden` + `aria-hidden` at rest, and forced inactive overlays to `display: none !important`.
- Added `openModal` / `closeModal` / Escape-to-dismiss helpers; cache-busted static assets to `?v=9.6.2`.
- Hardened Market / Strategies / Decisions loaders to always replace Loading placeholders on empty, error, or missing context (with nested `final_context` fallback).
- Replaced Live Operations fake loader with an explicit P9.7 placeholder (milestone not started — no speculative ops UI).
- Extended `tests/api/platform/test_dashboard_hosting.py` to lock modal inertness and placeholder contracts.

Files modified: `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.css`, `src/athena/api/static/dashboard.js`, `tests/api/platform/test_dashboard_hosting.py`, `IMPLEMENTATION_SUMMARY.md`.

---

### Correctness patch -- Overview exposure & day-change (2026-07-23)

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Fix capital-screen correctness: sector donut was 100% fake cash because summary omitted `exposure_by_sector`; day-% was a hardcoded HTML placeholder. |
| Tests | 819 passed / 0 failed |
| Status | **OWNER VERIFIED** |
| Branch | develop |

- Extended `DashboardSummaryDTO` with `exposure_by_sector` and `day_change_pct`.
- `DashboardService` now maps portfolio sector exposure + cash into absolute ₹ slices and computes day-change from the two most recent NAV snapshots.
- Seeded prior-day + current NAV snapshots aligned to live portfolio value (₹1,25,050) so Overview chart and % are deterministic.
- Wired Overview UI for day-change (+/− classes) and sector tooltips; title-cased strategy profile names.
- Updated summary + analytics list tests; cache-bust `?v=9.6.3`.

Files modified: `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/static/{index.html,dashboard.js}`, `tests/api/platform/test_dashboard_summary.py`, `tests/api/v1/test_reports_analytics_export.py`, `IMPLEMENTATION_SUMMARY.md`, `docs/MILESTONES.md`.

---

### P9.6 -- Decision Trace DAG Viewer

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Implement backend REST trace endpoint, briefing document browser list, and interactive 7-node DAG flowchart rendering connection lines using SVG overlay layers. |
| Tests | 818 passed / 0 failed (3 new) |
| Status | **APPROVED** — closes P9.6 (Owner approved) |
| Branch | develop |

Implemented backend services and interactive visual workstation features to explore decision rationales.
- Created `GET /api/v1/decisions/{id}/trace` resolving execution logs and mapping variables to 7 sequential pipeline stages.
- Developed search-enabled Briefing Documents browser card listing past recommendation entries.
- Designed node flow diagram representing Universe Ingest, Indicators, Scoring, Confidence, Risk, Quality Gates, and Recommendation outputs.
- Programmed dynamic connector line drawing inside absolute SVG viewport, wired to window resize triggers.
- Wired click-to-open node parameter details card rendering composite scores, indicators thresholds, and gate checklists.

Files created: `tests/api/v1/test_decision_trace.py`. Files modified: `src/athena/api/v1/dtos/decisions.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/services/decisions_service.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `docs/MILESTONES.md`. Public APIs added: `GET /api/v1/decisions/{id}/trace`. 3 new integration tests validating trace node schemas and exception parameters. All quality checks pass; 818 total suite tests run successfully.

---

### P9.5 -- Strategy & Backtest Workspace

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Implement backend APIs, seed mock runs, and build front-end workstation widgets under the Strategies & Scans tab (`#tab-strategies`) to display active strategy profiles and historical backtest runs. |
| Tests | 815 passed / 0 failed (6 new) |
| Status | **APPROVED** — closes P9.5 (Owner approved) |
| Branch | main |

Implemented backend services, mock seeding, and interactive workstation UI components for strategy configuration and backtest execution.
- Created `GET /api/v1/strategies/profiles` returning active strategy profiles and selection rules.
- Created `GET /api/v1/backtests/runs` and `GET /api/v1/backtests/runs/{run_id}` exposing backtest replays and performance metrics.
- Seeded a 10-step mock backtest session spanning all 5 reference strategies inside `in_memory.py`.
- Developed a two-column UI grid displaying Strategy Profiles Matrix and Backtest Replays.
- Integrated a Chart.js comparison bar chart showing completed vs failed steps for each run.
- Implemented a detailed modal drawer showing chronological timelines and horizontal strategy match performance bars.

Files created: `src/athena/api/v1/dtos/strategies.py`, `src/athena/api/v1/dtos/backtests.py`, `src/athena/api/v1/services/strategies_service.py`, `src/athena/api/v1/services/backtests_service.py`, `src/athena/api/v1/routers/strategies.py`, `src/athena/api/v1/routers/backtests.py`, `tests/api/v1/test_strategies_backtests.py`. Files modified: `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/router.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `docs/MILESTONES.md`. Public APIs added: `GET /api/v1/strategies/profiles`, `GET /api/v1/backtests/runs`, `GET /api/v1/backtests/runs/{id}`. 6 new integration tests validating payload formats, authentication guards, and details lookup. All quality checks pass; 815 total suite tests run successfully.

---

### P9.4 -- Market & Universe Dashboard

| | |
|---|---|
| Completed | 2026-07-23 |
| Scope | Build the Swing Trading Workstation's Market Intelligence and Universe Dashboard containing Volatility regime badges, interactive trading calendar session grid, and search-enabled Universe inclusion traces. |
| Tests | 809 passed / 0 failed (1 new) |
| Status | **APPROVED** — closes P9.4 (Owner approved) |
| Branch | main |

Implemented visual market and universe dashboard workstation panels under `src/athena/api/static/`.
- Created `GET /api/v1/dashboard/calendar` returning NSE segment holidays, expiries, special timings, and macro events.
- Extended dashboard service to resolve and load calendar configuration files dynamically.
- Seeded sample pipeline runs with volatility regime evaluations and eligibility traces in `in_memory.py`.
- Designed three-column grid workstation layout displaying Trend/Volatility/Gap badges, health gauge, interactive calendar cells with dots indicators, and search-enabled universe list.
- Implemented step-by-step eligibility trace inspector modals detailing rule checks outcomes (PASS/FAIL).

Files created: None. Files modified: `src/athena/api/v1/dtos/dashboard.py`, `src/athena/api/v1/services/dashboard_service.py`, `src/athena/api/v1/routers/dashboard.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/static/dashboard.css`, `tests/api/v1/test_core_apis.py`. Public APIs added: `GET /api/v1/dashboard/calendar`. 1 new integration test validating calendar structure. All quality checks pass; 809 total suite tests run successfully.

---

### P9.3 -- Portfolio & Capital Allocation Dashboard

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Build visual dashboard components showing exposure breakdowns, asset balances, and portfolio charts including NAV area line chart, Sector Exposure donut chart, and open holdings table detail. |
| Tests | 818 passed / 0 failed (0 new) |
| Status | **APPROVED** — closes P9.3 (Owner approved) |
| Branch | main |

Implemented visual portfolio dashboard components under `src/athena/api/static/` utilizing Chart.js CDN hosting.
- Integrated canvas configurations for `#nav-chart` and `#sector-chart` inside `index.html`.
- Implemented `renderNavChart(snapshots)` and `renderSectorChart(exposure)` functions in `dashboard.js` with responsive configurations, tooltips, currency formatting, and fallback points.
- Wired charts rendering to load portfolio performance snapshots data asynchronously from `/api/v1/analytics/performance/snapshots`.
- Introduced environment-controlled single-user mode authentication bypass when `ATHENA_SINGLE_USER=true` is set.

Files created: None. Files modified: `src/athena/api/static/index.html`, `src/athena/api/static/dashboard.js`, `src/athena/api/security/dependencies.py`, `task.md`. Public APIs added: None. All quality checks pass; 818 total suite tests run successfully.

---

## Phase 8 -- Application Platform (completed)

### P8.5 -- API Platform Completion & Production Readiness

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Finalize the API platform infrastructure and establish a production-grade API foundation with health, versioning, metadata, feature/capability discovery, standard headers, request context middleware, unified RFC 9457 error mappings, and OpenAPI contract completeness. |
| Tests | 806 passed / 0 failed (7 new) |
| Status | **APPROVED** — closes P8.5 (Owner approved) |
| Branch | main |

Finalized REST API platform infrastructure.
- Established a dedicated `platform` module defining extensible `BuildInfoProvider` and `MetadataProvider` protocols.
- Implemented `/health`, `/health/live`, and `/health/ready` check diagnostics.
- Implemented `/api/version` and `/api/info` consolidated startup metadata endpoints for desktop/UI clients.
- Introduced `PlatformMiddleware` combining request ID, correlation ID, logging, execution timing, standard headers injection, and unhandled exception-to-ProblemDetails mapping.
- Standardized error handling, migrating all mappings to use unified RFC 9457 `ProblemDetail` schemas.
- Audited all routes to confirm OpenAPI tags, operation IDs, summaries, descriptions, and pagination metadata schemas are 100% complete and consistent.

Files created: `src/athena/api/platform/health.py`, `src/athena/api/platform/version.py`, `src/athena/api/platform/metadata.py`, `src/athena/api/platform/info.py`, `src/athena/api/platform/headers.py`, `src/athena/api/platform/problem_details.py`, `src/athena/api/platform/middleware.py`, `src/athena/api/platform/providers/build_info_provider.py`, `src/athena/api/platform/providers/metadata_provider.py`, `tests/api/platform/test_platform.py`, `docs/API_PLATFORM_GUIDE.md`. Files modified: `src/athena/api/app.py`, `src/athena/api/errors.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/routers/health.py`, `src/athena/api/v1/routers/metrics.py`. Public APIs added: `GET /health`, `GET /health/live`, `GET /health/ready`, `GET /api/version`, `GET /api/meta`, `GET /api/features`, `GET /api/capabilities`, `GET /api/info`. 7 new integration tests validating process liveness/readiness, headers propagation, timing, unhandled panic mappings, contract schemas, and pagination consistency. All quality checks pass; 806 total suite tests run successfully.

---

### P8.4 -- Reports, Analytics & Export APIs

| | |
|---|---|
| Completed | 2026-07-22 |
| Scope | Expose Generic Reports, Portfolio Performance Analytics, and Presentation Format Export generation endpoints under versioned REST paths, backed by CQRS-aligned query and command providers. |
| Tests | 799 passed / 0 failed (14 new) |
| Status | **APPROVED** -- closes P8.4 (Principal Engineer review passed) |
| Branch | main |

Implemented reports, analytics, and exports API endpoints under versioned REST paths `/api/v1/`.
- Domain exceptions (`ReportNotFoundError`, `PerformanceSnapshotNotFoundError`, `ExportSnapshotNotFoundError`, `ExportArtifactNotFoundError`, `ExportGenerationError`) registered and mapped to HTTP Problem Details.
- Composed, nested DTOs (including `ArtifactMetadataDTO`, `ReportMetadataDTO`, `AnalyticsProvenanceDTO`, `SourceReferenceDTO`, `ExportOptionsDTO`, `ExportRequestDTO`, `ExportJobDTO`) decouple the transport interface from internal structures.
- Structured export requests and job status wrappers model export generation as a job abstraction, maintaining forward-compatibility for future asynchronous workers.
- CQRS-aligned provider separation decouples query interfaces from command mutation.
- Verified lease privilege and RBAC permission checks across all endpoints.

Files created: `src/athena/api/v1/dtos/reports.py`, `src/athena/api/v1/dtos/analytics.py`, `src/athena/api/v1/dtos/exports.py`, `src/athena/api/v1/services/reports_service.py`, `src/athena/api/v1/services/analytics_service.py`, `src/athena/api/v1/services/exports_service.py`, `src/athena/api/v1/routers/reports.py`, `src/athena/api/v1/routers/analytics.py`, `src/athena/api/v1/routers/exports.py`, `tests/api/v1/test_reports_analytics_export.py`. Files modified: `src/athena/api/v1/dtos/base.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/in_memory.py`, `src/athena/api/dependencies.py`, `src/athena/api/v1/services/__init__.py`, `src/athena/api/v1/routers/__init__.py`, `src/athena/api/v1/router.py`. Public APIs added: `GET /api/v1/reports`, `GET /api/v1/reports/{id}`, `GET /api/v1/analytics/performance/snapshots`, `GET /api/v1/analytics/performance/snapshots/{id}`, `GET /api/v1/exports/snapshots`, `GET /api/v1/exports/snapshots/{id}`, `GET /api/v1/exports/artifacts/{id}`, `POST /api/v1/exports`. 14 new integration tests covering listing summaries, detail specs, provenance tracking, dynamic export generation jobs, and header/permission guards. All 10 validation checklist items passed; 799 total suite tests pass clean.

---

### P8.3 -- Core Platform APIs

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Expose trading decisions, portfolios, execution run logs, scheduling history, and workspace snapshots under secure, authenticated, role-based controls. |
| Tests | 785 passed / 0 failed (14 new) |
| Status | **APPROVED** -- closes P8.3 (Principal Engineer review passed) |
| Branch | main |

Implemented core intelligence and operational API resources under versioned REST paths `/api/v1/`.
- Domain lookup exceptions mapped to RFC 9457 HTTP Problem Details via `AthenaExceptionMapper` (e.g. `DecisionNotFoundError`, `PortfolioUnavailableError`).
- Composed, generic DTO structures defined under `athena.api.v1.dtos.base` (including `CollectionResult`, `QuerySpecification`, `ResourceReference`).
- Decisions, Portfolios, Pipelines, Scheduler, and Workspace services map internal domain objects to clean public DTOs.
- Secured all routes with `RequirePermission(Permission.READ)` dependency.
- Collection list endpoints support query-based specification parsing for pagination, sorting, and filtering.
- Consolidated DTO optimization ensures workspace snapshots list returns lightweight metadata summaries while GET details returns full entries.

Files created: `tests/api/v1/test_core_apis.py`. Files modified: `src/athena/api/exceptions.py`, `src/athena/api/errors.py`, `src/athena/api/v1/dtos/__init__.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/v1/routers/portfolio.py`, `src/athena/api/v1/routers/pipelines.py`, `src/athena/api/v1/routers/scheduler.py`, `src/athena/api/v1/routers/workspace.py`, `src/athena/api/v1/services/decisions_service.py`. Public APIs added: `GET /api/v1/decisions`, `GET /api/v1/decisions/{id}`, `GET /api/v1/portfolio`, `GET /api/v1/pipelines/runs`, `GET /api/v1/pipelines/runs/{id}`, `GET /api/v1/scheduler/history`, `GET /api/v1/scheduler/history/{id}`, `GET /api/v1/workspace/snapshots`, `GET /api/v1/workspace/snapshots/{id}`. 14 new integration tests covering listing pagination, specs, filtering, details lookup, error status, and permission/RBAC bounds. All 10 validation checklist items passed; 785 total suite tests pass clean.

---

### P8.2 -- Authentication & RBAC

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Introduce production-grade authentication and authorization: Users, Roles, Permissions, JWT, API Keys, Sessions, RBAC, Password hashing, Permission middleware, Token refresh, Audit logging |
| Tests | 771 passed / 0 failed (16 new) |
| Status | **APPROVED** -- closes P8.2 (Principal Engineer review passed) |
| Branch | main |

Implemented the production authentication and authorization layer. `SecurityConfig` isolates cryptographic parameters (secret keys, algorithms, expiries, rounds) into `APISettings`. `AuthenticatedPrincipal` defines the immutable, runtime security context carrying pre-resolved user ID, role, and fine-grained permissions. `PasswordHasher` protocol abstraction uses `BcryptPasswordHasher` for password validation, shielding high-level components from raw password schemas. `TokenSigner` and `TokenClaimsFactory` divide signature verification from JWT claim generation. API Key persistence is split between `APIKeyMetadata` (hashes and active flags) and `APIKeySecret` (one-time returned key plain-text `key_id.raw_secret`). `SessionStore` protocol abstracts session status and token rotation tracking, using an `InMemorySessionStore` implementation that revokes session trees upon detecting refresh token reuse. `AuthenticationProvider` and `AuthorizationProvider` coordinate credential verification and permission validation. Security exceptions are mapped inside `AthenaExceptionMapper` to generate RFC 9457 Problem Details. FastAPI dependencies `get_current_user` and `RequirePermission` guard controller routes, integrating natively with OpenAPI schemas. `LoggingAuditSink` writes structured audit events to stdout log lines.

Files created: `src/athena/api/security/exceptions.py`, `src/athena/api/security/models.py`, `src/athena/api/security/hashing.py`, `src/athena/api/security/token.py`, `src/athena/api/security/repos.py`, `src/athena/api/security/providers.py`, `src/athena/api/security/dependencies.py`, `src/athena/api/security/audit.py`, `src/athena/api/security/__init__.py`, `tests/api/v1/test_security.py`. Files modified: `src/athena/api/config.py` (SecurityConfig), `src/athena/api/errors.py` (mappings), `src/athena/api/app.py` (app state initialization). Public APIs added: None (dependencies and exceptions only). 16 security integration tests covering hashing, claim parsing, token rotation, API key hashing checks, RBAC route bounds, and custom security exceptions. All 10 validation checklist items passed; 771 total suite tests pass clean.

---

### P8.1 -- Platform API Foundation

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Design and implement ATHENA's production REST API infrastructure: FastAPI app factory, ASGI/Lifespan lifecycle, API versioning (`/api/v1/`), unified response envelope `AthenaResponse[T]`, generic filtering (`FilterParams`), pagination/sorting params, `HealthProvider`/`MetricsProvider` protocols, `AthenaExceptionMapper` (RFC 9457 Problem Details) |
| Tests | 755 passed / 0 failed (24 new) |
| Status | **APPROVED** -- closes P8.1 (Principal Engineer review passed) |
| Branch | main |

Implemented the production FastAPI REST API platform foundation. `APISettings` separates TransportConfig (deployment) from AppMetadataConfig (application identity) with secure-by-default empty CORS origin list. `create_app()` uses a lifespan context manager (`@asynccontextmanager lifespan`) to manage startup and shutdown events cleanly. `AthenaResponse[T]` is the single, unified response envelope used across all endpoints, carrying optional pagination and links metadata. `PaginationMeta` and `PaginationParams` are future-ready, reserving cursor fields next to standard offset page parameters. `FilterParams` and `SortParams` establish consistent collection query interfaces. `AthenaExceptionMapper` functions as a central registry mapping domain errors to HTTP status codes and RFC 9457 `ProblemDetail` structures. Service components (`HealthService` and `MetricsService`) depend entirely on abstract `HealthProvider` and `MetricsProvider` protocols, with default implementations reading from system health checks and returning scaffold telemetry metrics. Middlewares inject unique `X-Request-ID` headers to all responses and format structured request logs. OpenAPI 3.1 is auto-generated with interactive documentation at `/api/docs`.

Files created: `src/athena/api/config.py`, `src/athena/api/errors.py`, `src/athena/api/middleware.py`, `src/athena/api/dependencies.py`, `src/athena/api/app.py`, `src/athena/api/v1/router.py`, `src/athena/api/v1/dtos/base.py`, `src/athena/api/v1/dtos/common.py`, `src/athena/api/v1/providers/base.py`, `src/athena/api/v1/providers/observability.py`, `src/athena/api/v1/routers/health.py`, `src/athena/api/v1/routers/metrics.py`, `src/athena/api/v1/services/health_service.py`, `src/athena/api/v1/services/metrics_service.py`, `tests/api/conftest.py`, `tests/api/v1/test_health.py`, `tests/api/v1/test_metrics.py`, `tests/api/v1/test_error_handling.py`. Files modified: `pyproject.toml` (dependencies). Public APIs added: `GET /api/v1/health`, `GET /api/v1/metrics`, `/api/docs`. 24 new integration tests covering endpoint payloads, headers, CORS behavior, validation errors, and custom exception mappings. All 10 validation checklist items passed; 755 total suite tests pass clean.

---

## Phase 7 -- Production Orchestration & Scheduling (complete)

### P7.5 -- Pipeline Scheduler Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Introduce scheduling-domain bridge adapter: `ScheduleRunRequest`, `PipelineScheduleRun`, `PipelineScheduleHistory`, `SystemScheduleAdapter` |
| Tests | 731 passed / 0 failed (26 new) |
| Status | **APPROVED** -- closes Phase 7 (Principal Engineer review passed) |
| Branch | main |

Introduced ATHENA's scheduling-domain bridge. `ScheduleRunRequest` is a stable, versioned input contract bundling `ScheduledJob`, `decisions`, `current_prices`, and `as_of`; validation fires at construction, establishing the request-rejected lifecycle boundary before execution begins. `PipelineScheduleRun` is a thin, immutable scheduling envelope holding only the scheduling-domain metadata (`schedule_run_id`, `job_id`, `definition_id`, `duration_seconds`) backed by `SystemPipelineResult` as the authoritative execution record -- no fields duplicated. `PipelineScheduleHistory` is an immutable append-only history exposed as a read-only property; the adapter holds the current instance and replaces it via `record()` with no mutable state leakage. `SystemScheduleAdapter` coordinates the four-step lifecycle: validate-and-build context (via private `_ScheduleContextBuilder`), measure duration, delegate to `SystemPipelineRunner`, wrap result, record history. Failure recording policy is lifecycle-based: request-rejected failures produce no history record; execution-started failures (pipeline failure, contract failure, workspace failure) always produce a `PipelineScheduleRun` and are always recorded. The scheduling domain never touches `PipelineDefinition`, artifact keys, or stage topology.

Files created: `src/athena/orchestration/schedule_models.py`, `src/athena/orchestration/schedule_adapter.py`, `tests/runtime/test_pipeline_scheduler.py`. Files modified: `src/athena/orchestration/__init__.py` (exported four new APIs). Public APIs added: `ScheduleRunRequest`, `PipelineScheduleRun`, `PipelineScheduleHistory`, `SystemScheduleAdapter`. Private (not exported): `_ScheduleContextBuilder`. 26 new tests across four test classes covering request validation, thin-envelope design, append-only history semantics, adapter execution lifecycle, failure recording policy, and scheduler-pipeline isolation. No ADR required; no architecture drift; zero technical debt. All 10 validation checklist items passed; 731 total suite tests pass clean.

---

### P7.4 -- Pipeline Runner Integration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Implement integrated runtime orchestration layer: `PipelineContract`, `validate_contract`, `PipelineCoordinator`, `WorkspaceAssembler`, `SystemPipelineRunner`, `SystemPipelineResult` |
| Tests | 705 passed / 0 failed (12 new) |
| Status | **APPROVED** — closes P7.4 (Principal Engineer review passed) |
| Branch | main |

Implemented ATHENA's integrated production runtime. `PipelineContract` declares symmetric input/output requirements per pipeline; `validate_contract()` is a pure validation function that raises `OrchestrationError` on missing required inputs. `PipelineCoordinator` executes an ordered sequence of `(PipelineDefinition, PipelineContract)` pairs generically — enforcing contracts between runs and threading functional context — with no knowledge of specific artifact keys. `WorkspaceAssembler` is a standalone post-processing adapter that extracts intelligence artifacts from the final `PipelineContext` and delegates construction to `UnifiedIntelligenceWorkspace`, fully isolating workspace assembly from the orchestration layer. `SystemPipelineRunner` is the high-level system entry point, composing coordinator and assembler with explicit four-boundary failure handling: execution failure → immediate termination; contract validation failure → raises `OrchestrationError`; intelligence failure → skips workspace; workspace failure → exception caught, pipelines preserved, `overall_status=FAILED`. `SystemPipelineResult` is an immutable generic container holding `pipeline_runs: tuple[PipelineResult, ...]` to scale beyond two pipelines.

Files created: `src/athena/orchestration/contract.py`, `src/athena/orchestration/coordinator.py`, `src/athena/orchestration/workspace_adapter.py`, `src/athena/orchestration/system_runner.py`, `tests/runtime/test_pipeline_runner_integration.py`. Files modified: `src/athena/orchestration/models.py` (added `SystemPipelineResult`), `src/athena/orchestration/__init__.py` (exported all P7.4 APIs). Public APIs added: `PipelineContract`, `validate_contract`, `EXECUTION_PIPELINE_CONTRACT`, `INTELLIGENCE_PIPELINE_CONTRACT`, `PipelineCoordinator`, `WorkspaceAssembler`, `SystemPipelineRunner`, `SystemPipelineResult`. 12 new tests covering: contract construction and validation, coordinator sequence execution, coordinator contract failure boundary, workspace assembler extraction, end-to-end system cycle success, execution failure early exit, workspace assembly failure handling, deterministic replayability, and `FrozenInstanceError` immutability. No ADR required; no architecture drift; zero technical debt. All 10 validation checklist items passed; 705 total suite tests pass clean.

---

### P7.3 — Intelligence Pipeline Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Wire six presentation/intelligence stage adapters into a validated, declarative `PipelineDefinition`; model topology as four independent producer roots, Timeline as intermediate aggregator, and Export as terminal aggregator |
| Tests | 693 passed / 0 failed (21 new) |
| Status | **APPROVED** — closes P7.3 (Owner approved) |
| Branch | main |

Built ATHENA's second production pipeline. `create_intelligence_pipeline()` returns an immutable `PipelineDefinition` with six stages: four independent roots (`ReportingStage`, `ExplainabilityStage`, `DashboardStage`, `MonitoringStage`), one intermediate aggregator (`TimelineStage` depending on the four roots), and one terminal aggregator (`ExportStage` depending on all five upstream stages). `validate_intelligence_pipeline()` enforces the correct topological shape, stage count (6), and expected stage IDs. The explicit execution-artifact input contract is defined by `INTELLIGENCE_PIPELINE_REQUIRED_INPUTS` and `INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS` to prevent implicit runtime assumptions. `IntelligenceArtifactKey` and `IntelligenceStageId` enums eliminate all raw string keys in context propagation. Each stage adapter wraps its engine internally with no concrete engine injection at builder level.

Files created: `src/athena/orchestration/pipelines/intelligence.py`, `src/athena/orchestration/stages/{reporting,explainability,dashboard,monitoring,timeline,export}.py`, `tests/runtime/test_intelligence_pipeline.py`. Files modified: `src/athena/orchestration/pipelines/keys.py`, `src/athena/orchestration/pipelines/__init__.py`, `src/athena/orchestration/stages/__init__.py`, `src/athena/orchestration/__init__.py`. Public APIs added: `IntelligenceArtifactKey`, `IntelligenceStageId`, `INTELLIGENCE_PIPELINE_REQUIRED_INPUTS`, `INTELLIGENCE_PIPELINE_OPTIONAL_INPUTS`, `create_intelligence_pipeline`, `validate_intelligence_pipeline`, and all six stage classes. 21 new tests: registration, topology validation, stage count, roots, validators, stage execution, failure isolation, and deterministic replayability. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 693 suite tests pass.

---

### P7.2 — Execution Pipeline Registration

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Wire all eight execution-domain stage adapters into a validated, declarative `PipelineDefinition` using the P7.1 generic orchestration framework; typed artifact key model replaces all string-based context access |
| Tests | 672 passed / 0 failed (7 new) |
| Status | **APPROVED** — closes P7.2 (Principal Engineer review passed) |
| Branch | main |

Built ATHENA's first production pipeline. `create_execution_pipeline()` returns an immutable `PipelineDefinition` (not a live executor) with eight `PipelineStage` adapters wired in correct topological order: two independent root stages (`PortfolioSnapshotStage`, `DecisionsLoadStage`) followed by `AllocationStage → SizingStage → OrderPlanningStage → BrokerTranslationStage → OrderLifecycleStage → PortfolioAnalyticsStage`. Each stage adapter owns its own engine dependencies and writes a typed `ExecutionArtifactKey` value into the context; no concrete engines are injected at the builder level. `validate_pipeline_definition()` asserts stage count, dependency integrity, key-to-stage consistency, and dual-root topology. `ExecutionArtifactKey` and `ExecutionStageId` enums replace all string-based context access, satisfying the typed key model requirement from the architecture review. Pipeline topology is immutable in code; operational parameters (timeout, retries) remain configurable via `PipelineConfig`. The dual-root design preserves future parallel execution of the two root stages without any structural change.

Files created: `src/athena/orchestration/pipelines/{__init__,keys,execution}.py`, `src/athena/orchestration/stages/{__init__,portfolio_snapshot,decisions,allocation,sizing,order_planning,broker_translation,lifecycle,analytics}.py`, `tests/runtime/test_execution_pipeline.py`. Files modified: `src/athena/orchestration/__init__.py` (exported new APIs). Public APIs added: `ExecutionArtifactKey`, `ExecutionStageId`, `create_execution_pipeline`, `validate_pipeline_definition`, and all eight stage classes. 7 new tests: definition type, stage count, dual independent roots, validator passes, stage execution artifact, failure isolation, deterministic replayability. Fixed 4 E501 linter warnings in stage success-message strings. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 672 suite tests pass.

---

### P7.1 — Generic Pipeline Infrastructure

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Domain-agnostic pipeline execution framework: stage-based orchestration, typed execution context, composable retry/fallback/timeout policies, deterministic structured execution record |
| Tests | 665 passed / 0 failed (10 new) |
| Status | **APPROVED** — closes P7.1 (Principal Engineer review passed) |
| Branch | main |

Built the Generic Pipeline Infrastructure (`src/athena/orchestration/`). `PipelineExecutor` performs topological sort of `PipelineStage` dependencies, gates downstream stages on upstream success (propagates `SKIPPED` through dependents of failed stages), evaluates configurable `RetryPolicy` (max attempts + delay), invokes an optional `fallback_handler` on exhaustion, enforces `timeout_seconds` per stage, and accumulates all outcomes into an immutable `PipelineResult`. All data types are `frozen=True, slots=True`. The framework is entirely domain-independent — zero imports from any ATHENA business module.

**Phase 6 engine bug fixes (identified during P7.1 full-suite self-validation):** Seventeen stale field-name references in Phase 6 presentation/analytics engines (dashboard, explainability, timeline, monitoring, reporting, analytics/portfolio) were corrected against the actual `PortfolioSnapshot` and `AllocationPlanSummary` contracts. NAV formula in `analytics/portfolio/engine.py` corrected from `total_cash + gross_exp` (double-counted) to `available_cash + reserved_cash + gross_exp`. Two test files corrected (`test_portfolio_analytics.py` — wrong kwarg names and monotonic timestamp; `test_workspace.py` — fixture omitted `schedule_execution`/`workflow` sentinels). No domain models, frozen contracts, or business logic were changed.

Files created: `src/athena/orchestration/{__init__,models,engine}.py`, `config/pipeline.json`, `tests/runtime/test_orchestration.py`. Files modified (bug fixes only): `src/athena/reporting/engine.py`, `src/athena/dashboard/engine.py`, `src/athena/explainability/engine.py`, `src/athena/timeline/engine.py`, `src/athena/monitoring/engine.py`, `src/athena/analytics/portfolio/engine.py`, `tests/runtime/test_portfolio_analytics.py`, `tests/runtime/test_workspace.py`. Public APIs added: `PipelineStage`, `PipelineContext`, `StageResult`, `PipelineResult`, `RetryPolicy`, `PipelineExecutor`. 10 new tests: single-stage execution, dependency ordering, skip propagation, retry with success, retry exhaustion + fallback, timeout enforcement, deterministic independent ordering, deterministic replay, immutable outputs, config validation. No ADR; no drift; no tech debt. Validation checklist 1–10 passed; all 665 suite tests pass.

---

## Phase 1 — Data Foundation (complete)

### M1.6 — Backup & Restore  (completes Phase 1)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic backup + restore with integrity verification, schema-compat enforcement, recovery validation |
| Tests | 182 passed / 0 failed (11 new) |
| Status | **APPROVED** — closes Phase 1 (Principal Engineer review passed) |
| Branch | main |

Built the backup/restore layer. `create_backup` integrity-verifies the source, snapshots it via SQLite's online backup API written atomically (temp + `os.replace`, so a backup file is always complete), and writes a JSON metadata sidecar (schema version, per-table counts, provenance). `restore_backup` validates the backup first (integrity + schema-version compatibility — no silent repair, no automatic migration), replaces the target atomically, clears stale WAL sidecars, then re-verifies the restored repository (integrity, foreign keys, schema version, record counts vs metadata) and reports the outcome. Every failure mode raises `RepositoryError` with an actionable message and never leaves the target inconsistent. Repository-focused; no business/provider/intelligence logic.

Files created: `src/athena/data/store/backup.py`, `tests/data_layer/test_backup_restore.py`. Files modified: `src/athena/data/store/{__init__,repository}.py` (exports; repo `path`/`connection`/`record_counts` accessors). Public APIs added: `create_backup`, `restore_backup`, `BackupResult`, `RestoreResult`. 11 new tests: successful backup/restore, overwrite behavior, read-only destination, recovery of every entity, restored==original, deterministic repeated cycles, missing/corrupted backup, incompatible schema refusal (+ target untouched), unhealthy-source refusal.

**Codebase-wide quality pass (this milestone):** ran `ruff` for the first time (not previously available in the sandbox). Applied safe modernizations tree-wide — `typing.List/Dict/Tuple/Optional/Union` → builtin generics and `X | None` (verified against the 3.10 floor; all tests green), raw-string regex patterns in tests, and minor nits. Set ruff `target-version = py310` and `line-length = 120` (a deliberate project-standard width suited to this explainability-heavy code, avoiding low-value wrapping churn). `ruff check src tests` now passes clean. `mypy` could not run — v2.3.0 in the sandbox crashes with an INTERNAL ERROR on any input (tooling bug); strict typing remains configured for `domain`/`config` and should be verified on the owner's machine.

Validation checklist 1–10 passed; frozen contracts unchanged; no ADR; no drift; no tech debt.

---

## Phase 6 — Reporting, Dashboards & User Intelligence (in progress)

### P6.7 — Unified Intelligence Workspace

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Read-only unified intelligence composition workspace orchestrating query lookups, artifact filtering, and consolidated snapshots across all Phase 6 intelligence artifacts |
| Tests | 669 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — Phase 6 completed; Phase 7 blocked until approved |
| Branch | main |

Built the Unified Intelligence Workspace (`src/athena/workspace/`), which answers one question: "How can all immutable ATHENA intelligence artifacts be accessed through a single, unified, read-only interface?" `UnifiedIntelligenceWorkspace` provides a consolidated view across 6 canonical workspace views (`REPORT`, `DASHBOARD`, `EXPLAINABILITY`, `TIMELINE`, `MONITORING`, `EXPORT`) into `WorkspaceSnapshot`s. It **aggregates and organizes information only**: it performs no state mutation, no user authentication, no REST APIs, no Web/Desktop/Mobile UI rendering, and no market analysis.

Workspace features: `assemble_workspace(reports=None, dashboard_snapshot=None, explanation_snapshot=None, timeline_snapshot=None, monitoring_snapshot=None, export_snapshot=None, *, as_of)` aggregates all Phase 6 intelligence artifacts into cataloged `WorkspaceEntry` records, provides deterministic filtering (`filter_by_type()`), identifier lookup (`find_by_id()`), and a high-level `WorkspaceSummary`. All outputs (`WorkspaceEntry`, `WorkspaceSummary`, `WorkspaceSnapshot`, `WorkspaceHistory`) are immutable and preserve full `WorkspaceReferences` back to originating platform artifacts (`report_id`, `dashboard_snapshot_id`, `explanation_snapshot_id`, `timeline_snapshot_id`, `monitoring_snapshot_id`, `export_snapshot_id`).

Files created: `src/athena/workspace/{__init__,models,engine}.py`, `config/workspace.json`, `tests/runtime/test_workspace.py`. Files modified: `src/athena/errors.py` (+`WorkspaceError`), `src/athena/config/{models,loader,__init__}.py` (+`WorkspaceConfig`, `load_workspace_config`, exports). No analytical engine, export engine, monitoring engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `UnifiedIntelligenceWorkspace`, `WorkspaceEntry`, `WorkspaceSummary`, `WorkspaceSnapshot`, `WorkspaceHistory`, `WorkspaceReferences`, `WorkspaceConfig`, `load_workspace_config`. 12 new tests: workspace assembly across all 6 Phase 6 artifact types, filtering by artifact type, lookup by ID, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming all Phase 6 intelligence artifacts. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.6 — Export & Presentation Layer

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Presentation format transformation (JSON, Markdown, Text, CSV) for immutable platform artifacts; pure presentation adapter |
| Tests | 657 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Export & Presentation Layer (`src/athena/export/`), which answers one question: "How can immutable ATHENA artifacts be exported and presented in standardized formats without changing their meaning or contents?" `ExportPresentationEngine` transforms immutable platform artifacts into 4 canonical presentation formats (`ExportFormat`: `JSON`, `MARKDOWN`, `TEXT`, `CSV`). It **transforms representations only**: it performs no state mutation, no PDF rendering, no REST endpoints, no file upload services, and no market analysis.

Export features: `export_report()`, `export_dashboard()`, `export_explanation()`, `export_timeline()`, `export_monitoring()`, and `create_snapshot(exports, *, as_of)`. Standardized format rendering ensures deterministic payloads, content-type mapping (`application/json`, `text/markdown`, `text/plain`, `text/csv`), and standardized extension generation (`.json`, `.md`, `.txt`, `.csv`). All outputs (`ExportRequest`, `ExportArtifact`, `ExportSummary`, `ExportSnapshot`, `ExportHistory`) are immutable and preserve full `ExportReferences` back to originating platform artifacts (`report_id`, `dashboard_snapshot_id`, `explanation_snapshot_id`, `timeline_snapshot_id`, `monitoring_snapshot_id`).

Files created: `src/athena/export/{__init__,models,engine}.py`, `config/export.json`, `tests/runtime/test_export.py`. Files modified: `src/athena/errors.py` (+`ExportError`), `src/athena/config/{models,loader,__init__}.py` (+`ExportConfig`, `ExportFormat`, `load_export_config`, exports). No analytical engine, monitoring engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ExportPresentationEngine`, `ExportRequest`, `ExportArtifact`, `ExportSummary`, `ExportSnapshot`, `ExportHistory`, `ExportReferences`, `ExportFormat`, `ExportConfig`, `load_export_config`. 12 new tests: export generation across all 4 canonical formats, format-specific content-type verification, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming Reporting, Dashboard, Explainability, Timeline, and Monitoring artifacts across all 4 formats. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.5 — Operational Monitoring

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Operational health snapshot generation and component monitoring across 10 platform domains; read-only health observation only |
| Tests | 645 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Operational Monitoring Engine (`src/athena/monitoring/`), which answers one question: "What is the current operational health of ATHENA and are all platform components functioning correctly?" `OperationalMonitoringEngine` evaluates platform health across 10 canonical domains (`MonitoringDomain`: `SCHEDULER`, `WORKFLOW`, `PORTFOLIO`, `EXECUTION`, `ANALYTICS`, `REPORTING`, `DASHBOARD`, `EXPLAINABILITY`, `TIMELINE`, `OVERALL`). It **observes operational health only**: it performs no state mutation, no live polling, no alert delivery, no Prometheus/Grafana integration, and no market analysis.

Monitoring features: `evaluate_health(schedule_execution=None, workflow=None, portfolio_snapshot=None, execution_state=None, performance_snapshot=None, reports=None, dashboard_snapshot=None, explanation_snapshot=None, timeline_snapshot=None, *, as_of)` aggregates component status, detects missing/stale artifacts, and computes overall platform health (`HEALTHY`, `DEGRADED`, `CRITICAL`). All outputs (`MonitoringCheck`, `MonitoringSummary`, `MonitoringSnapshot`, `MonitoringHistory`) are immutable and preserve full `MonitoringReferences` back to originating platform artifacts across every layer.

Files created: `src/athena/monitoring/{__init__,models,engine}.py`, `config/monitoring.json`, `tests/runtime/test_monitoring.py`. Files modified: `src/athena/errors.py` (+`MonitoringError`), `src/athena/config/{models,loader,__init__}.py` (+`MonitoringConfig`, `MonitoringDomain`, `load_monitoring_config`, exports). No analytical engine, timeline engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OperationalMonitoringEngine`, `MonitoringCheck`, `MonitoringSummary`, `MonitoringSnapshot`, `MonitoringHistory`, `MonitoringReferences`, `MonitoringDomain`, `MonitoringConfig`, `load_monitoring_config`. 12 new tests: component health check aggregation across 10 domains, missing artifact detection, overall status calculation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting, Dashboard, Explainability, and Timeline engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.4 — Timeline & Audit Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Chronological timeline reconstruction and audit stream generation across 11 platform domains; read-only reconstruction only |
| Tests | 633 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Timeline & Audit Engine (`src/athena/timeline/`), which answers one question: "What happened across the complete ATHENA pipeline, in what order, and how can every platform event be reconstructed?" `TimelineAuditEngine` reconstructs chronological timelines across 11 canonical domains (`TimelineDomain`: `DECISION`, `PORTFOLIO`, `ALLOCATION`, `SIZING`, `ORDER_PLANNING`, `BROKER_TRANSLATION`, `LIFECYCLE`, `ANALYTICS`, `REPORTING`, `DASHBOARD`, `EXPLAINABILITY`). It **reconstructs immutable history only**: it performs no state mutation, no live streaming, no distributed tracing, and no market analysis.

Timeline features: `build_timeline(decisions=None, portfolio_snapshot=None, allocation_plan=None, sizing_plan=None, execution_plan=None, broker_plan=None, execution_state=None, performance_snapshot=None, reports=None, dashboard_snapshot=None, explanation_snapshot=None, *, as_of)` extracts, sorts, and sequence-numbers platform events into causally ordered `AuditEntry` records inside a `TimelineSnapshot`. All outputs (`TimelineEvent`, `AuditEntry`, `TimelineSummary`, `TimelineSnapshot`, `TimelineHistory`) are immutable and preserve full `TimelineReferences` back to all originating platform artifacts across every layer.

Files created: `src/athena/timeline/{__init__,models,engine}.py`, `config/timeline.json`, `tests/runtime/test_timeline.py`. Files modified: `src/athena/errors.py` (+`TimelineAuditError`), `src/athena/config/{models,loader,__init__}.py` (+`TimelineConfig`, `TimelineDomain`, `load_timeline_config`, exports). No analytical engine, explainability engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `TimelineAuditEngine`, `TimelineEvent`, `AuditEntry`, `TimelineSummary`, `TimelineSnapshot`, `TimelineHistory`, `TimelineReferences`, `TimelineDomain`, `TimelineConfig`, `load_timeline_config`. 12 new tests: timeline building across 11 domains, strict 1-indexed sequence numbering, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting, Dashboard, and Explainability engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.3 — Explainability Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic human-readable explanation generator explaining why decisions, allocations, sizing, execution plans, lifecycle outcomes, and analytics were produced; rationale only |
| Tests | 621 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Explainability Engine (`src/athena/explainability/`), which answers one question: "Why did ATHENA produce this decision, allocation, position size, execution plan, lifecycle outcome, or analytical result?" `ExplainabilityEngine` generates deterministic, human-readable explanations across 9 canonical domains (`ExplanationDomain`: `DECISION`, `PORTFOLIO`, `ALLOCATION`, `SIZING`, `ORDER_PLANNING`, `BROKER_TRANSLATION`, `LIFECYCLE`, `ANALYTICS`, `REPORTING`). It **explains existing platform outcomes only**: it performs no state mutation, no decision altering, no LLM generation, and no market analysis.

Explainability features: `explain_decision()`, `explain_portfolio()`, `explain_allocation()`, `explain_sizing()`, `explain_order_planning()`, `explain_broker_translation()`, `explain_lifecycle()`, `explain_analytics()`, `explain_reporting()`, and `create_snapshot(explanations, *, as_of)`. All outputs (`ExplanationSection`, `Explanation`, `ExplanationSnapshot`, `ExplanationHistory`) are immutable and preserve full `ExplanationReferences` back to `decision_id`, `portfolio_snapshot_id`, `allocation_plan_id`, `position_sizing_plan_id`, `execution_plan_id`, `broker_execution_plan_id`, `execution_state_id`, `performance_snapshot_id`, `report_id`, and `schedule_execution_id`.

Files created: `src/athena/explainability/{__init__,models,engine}.py`, `config/explainability.json`, `tests/runtime/test_explainability.py`. Files modified: `src/athena/errors.py` (+`ExplainabilityError`), `src/athena/config/{models,loader,__init__}.py` (+`ExplainabilityConfig`, `ExplanationDomain`, `load_explainability_config`, exports). No analytical engine, dashboard engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ExplainabilityEngine`, `ExplanationSection`, `Explanation`, `ExplanationSnapshot`, `ExplanationHistory`, `ExplanationReferences`, `ExplanationDomain`, `ExplainabilityConfig`, `load_explainability_config`. 12 new tests: explanation generation across all 9 canonical domains, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming artifacts across the complete execution pipeline together with Reporting and Dashboard engines. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.2 — Dashboard & Snapshot Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Derived, read-only operational dashboard snapshots aggregating platform status, portfolio health, execution progress, and analytics; presentation layer only |
| Tests | 609 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Dashboard & Snapshot Engine (`src/athena/dashboard/`), which answers one question: "Given the current immutable platform artifacts, what is the current operational view of ATHENA?" `DashboardEngine` aggregates platform status across 9 canonical sections (`Portfolio Overview`, `Capital Allocation Overview`, `Active Positions`, `Execution Status`, `Order Lifecycle Summary`, `Portfolio Performance`, `Risk & Exposure Summary`, `Reporting Status`, `Platform Health`) into `DashboardSnapshot`s. It **presents derived operational views only**: it performs no state mutation, no UI rendering, no live polling, and no market analysis.

Dashboard features: `create_snapshot(portfolio_snapshot=None, allocation_plan=None, execution_state=None, performance_snapshot=None, reports=None, *, as_of)` aggregates available platform artifacts into modular `DashboardSection`s and a high-level `DashboardSummary`. All outputs (`DashboardSection`, `DashboardSummary`, `DashboardSnapshot`, `DashboardHistory`) are immutable and preserve full `DashboardReferences` back to `portfolio_snapshot_id`, `performance_snapshot_id`, `execution_state_id`, `allocation_plan_id`, `report_id`, and `schedule_execution_id`.

Files created: `src/athena/dashboard/{__init__,models,engine}.py`, `config/dashboard.json`, `tests/runtime/test_dashboard.py`. Files modified: `src/athena/errors.py` (+`DashboardError`), `src/athena/config/{models,loader,__init__}.py` (+`DashboardConfig`, `load_dashboard_config`, exports). No analytical engine, reporting framework, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `DashboardEngine`, `DashboardSection`, `DashboardSummary`, `DashboardSnapshot`, `DashboardHistory`, `DashboardReferences`, `DashboardConfig`, `load_dashboard_config`. 12 new tests: dashboard snapshot creation with all sections, partial artifact handling, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming real artifacts from Phase 5 execution pipeline and Reporting Framework. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P6.1 — Reporting Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Generic operational reporting engine generating immutable, structured machine-readable and human-readable reports from platform artifacts; read-only |
| Tests | 597 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Reporting Framework (`src/athena/reporting/`), which answers one question: "Given ATHENA's completed artifacts from Phases 1–5, how can we produce generic, immutable, human-readable and structured operational reports?" `ReportingEngine` consumes immutable platform artifacts (`PortfolioSnapshot`, `ExecutionState`, `AllocationPlan`, `PerformanceSnapshot`, audit events) to produce `GenericReport`s. It **presents and formats information only**: it performs no state mutation, no order execution, no analytical calculation, and no market analysis.

Supported report types: `ReportType` (`PORTFOLIO`, `EXECUTION`, `ALLOCATION`, `ANALYTICS`, `AUDIT`). Report generation operations: `generate_portfolio_report(portfolio_snapshot, *, as_of)`, `generate_execution_report(execution_state, *, as_of)`, `generate_allocation_report(allocation_plan, *, as_of)`, `generate_analytics_report(performance_snapshot, *, as_of)`, `generate_audit_report(run_id, events, *, as_of)`. All reports provide dual presentation views (`to_dict()` machine-readable view and `to_text()` human-readable summary view). All outputs (`GenericReport`, `ReportingReferences`, `ReportingHistory`) are immutable and preserve full `ReportingReferences` back to `portfolio_snapshot_id`, `execution_state_id`, `allocation_plan_id`, `performance_snapshot_id`, `audit_id`, and `schedule_execution_id`.

Files modified: `src/athena/reporting/{__init__,models,engine}.py` (added `ReportingEngine`, `GenericReport`, `ReportingReferences`, `ReportingHistory` while preserving M3.7 `DecisionReportingEngine` & `DecisionReport` intact), `config/reporting.json`, `tests/runtime/test_reporting_framework.py`. Files modified: `src/athena/errors.py` (+`ReportingError`), `src/athena/config/{models,loader,__init__}.py` (+`ReportingFrameworkConfig`, `ReportType`, `load_reporting_framework_config`, exports). No analytical engine, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `ReportingEngine`, `GenericReport`, `ReportingReferences`, `ReportingHistory`, `ReportType`, `ReportingFrameworkConfig`, `load_reporting_framework_config`. 12 new tests: portfolio report generation, execution report generation, allocation report generation, analytics report generation, audit report generation, machine/text rendering verification, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming real artifacts across all Phases 1–5. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

---

## Phase 5 — Portfolio & Execution Platform (COMPLETED)

### P5.7 — Portfolio Analytics & Performance

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Computes portfolio returns, realized/unrealized P&L, exposures, win/loss stats, and drawdowns; performance calculation only |
| Tests | 585 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Portfolio Analytics Engine (`src/athena/analytics/portfolio/`), which answers one question: "Given completed portfolio activity and execution history, how has the portfolio performed?" `PortfolioAnalyticsEngine` consumes `PortfolioSnapshot`s and `ExecutionState`s to compute comprehensive performance metrics (`PortfolioPerformance`, `TradePerformance`, `AnalyticsSummary`, `PerformanceSnapshot`). It **computes performance metrics and analytics only**: it performs no investment decision making, no capital allocation, no position sizing, no order planning, no broker communication, and no execution state modification.

Core performance metrics & analytics: Realized P&L, unrealized P&L, total P&L, total return %, portfolio valuation, peak portfolio value, drawdown, drawdown %, max drawdown %, gross exposure, net exposure, cash utilization %, trade-level win/loss classification, win rate %, average gain, average loss, win/loss ratio, and average holding period (days). Analytics operations: `analyze(portfolio_snapshot, execution_state=None, current_prices=None, *, as_of)` processes portfolio state deterministically. All outputs (`TradePerformance`, `PortfolioPerformance`, `AnalyticsSummary`, `PerformanceSnapshot`, `PortfolioAnalyticsHistory`) are immutable and preserve full `PortfolioAnalyticsReferences` back to `execution_state_id`, `broker_execution_plan_id`, `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/analytics/portfolio/{__init__,models,engine}.py`, `config/portfolio_analytics.json`, `tests/runtime/test_portfolio_analytics.py`. Files modified: `src/athena/errors.py` (+`PortfolioAnalyticsError`), `src/athena/config/{models,loader,__init__}.py` (+`PortfolioAnalyticsConfig`, `load_portfolio_analytics_config`, exports). No analytical engine, order lifecycle engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PortfolioAnalyticsEngine`, `TradePerformance`, `PortfolioPerformance`, `AnalyticsSummary`, `PerformanceSnapshot`, `PortfolioAnalyticsHistory`, `PortfolioAnalyticsReferences`, `PortfolioAnalyticsConfig`, `load_portfolio_analytics_config`. 12 new tests: unrealized P&L & valuation, win/loss accounting & realized P&L, drawdown calculation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative initial capital rejection, production config loading), and an **end-to-end integration test** consuming real outputs from the entire Phase 5 pipeline (`PortfolioEngine` → `CapitalAllocationEngine` → `PositionSizingEngine` → `OrderPlanningEngine` → `BrokerManager` → `OrderLifecycleEngine` → `PortfolioAnalyticsEngine`). ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.6 — Order Lifecycle Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Tracks order lifecycle states, validates legal state transitions, and records execution history; execution state model only |
| Tests | 573 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Order Lifecycle Engine (`src/athena/execution/`), which answers one question: "What is the current lifecycle state of every planned order from creation until completion or cancellation?" `OrderLifecycleEngine` consumes `BrokerExecutionPlan`s and tracks order state transitions (`OrderLifecycleState`: `CREATED`, `ACCEPTED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELLED`, `REJECTED`, `EXPIRED`). It **tracks execution state transitions only**: it performs no live broker polling, no WebSockets/REST communication, no exchange connectivity, and no market analysis.

State machine & transition features: Enforces strict legal state transition graph (e.g. `CREATED` → `SUBMITTED` → `PARTIALLY_FILLED` → `FILLED`); illegal transitions (e.g. `CREATED` → `FILLED`, or transitioning out of terminal states `FILLED`/`CANCELLED`/`REJECTED`/`EXPIRED`) fail loudly with `LifecycleError`. Accumulates fill quantities and calculates weighted average fill price (`avg_fill_price`). Auto-promotes `PARTIALLY_FILLED` to `FILLED` when 100% of target quantity is filled. All outputs (`ExecutionEvent`, `OrderLifecycle`, `LifecycleSummary`, `ExecutionState`, `LifecycleHistory`) are immutable and preserve full `ExecutionReferences` back to `broker_execution_plan_id`, `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/execution/{__init__,models,engine}.py`, `config/execution.json`, `tests/runtime/test_execution.py`. Files modified: `src/athena/errors.py` (+`LifecycleError`), `src/athena/config/{models,loader,__init__}.py` (+`ExecutionConfig`, `OrderLifecycleState`, `load_execution_config`, exports). No analytical engine, broker abstraction layer, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OrderLifecycleEngine`, `OrderLifecycle`, `ExecutionEvent`, `ExecutionState`, `LifecycleSummary`, `LifecycleHistory`, `ExecutionReferences`, `OrderLifecycleState`, `ExecutionConfig`, `load_execution_config`. 12 new tests: legal state transitions, illegal transition rejection, terminal state protection, partial fills & weighted average price, cancellation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming a real `BrokerExecutionPlan` from `BrokerManager`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.5 — Broker Abstraction Layer

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Canonical broker contracts, capability validation, and translation from broker-neutral execution plans into broker requests; contract definition only |
| Tests | 561 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Broker Abstraction Layer (`src/athena/brokers/`), which answers one question: "How can ATHENA communicate with different brokers through a single canonical interface?" `BrokerManager` registers broker contract definitions (`BrokerDefinition`, `BrokerCapabilities`) and translates broker-neutral `ExecutionPlan`s into canonical `BrokerExecutionPlan`s containing `BrokerRequest`s. It **defines contracts and validates capabilities only**: it performs no network communication, no OAuth flows, no REST/WebSocket clients, and no live order submission.

Capability validation & contract features: `BrokerCapabilities` enforces supported order types (`OrderType`), fractional trading support (`supports_fractional`), shorting support (`supports_shorting`), and supported time-in-force policies (`TimeInForce`: `DAY`, `IOC`, `FOK`, `GTC`). Translation operations: `translate_plan(execution_plan, broker_id=None, *, as_of, time_in_force=None)` validates broker availability and capabilities, mapping planned orders into canonical `BrokerRequest`s (`ACCEPTED`, `REJECTED_UNSUPPORTED_ORDER_TYPE`, `REJECTED_UNSUPPORTED_FRACTIONAL`, `SKIPPED_HOLD`); `create_mock_response` generates abstract `BrokerResponse` artifacts for contract testing. All outputs (`BrokerDefinition`, `BrokerCapabilities`, `BrokerRequest`, `BrokerResponse`, `BrokerExecutionPlan`, `BrokerSummary`, `BrokerHistory`) are immutable and preserve full `BrokerReferences` back to `execution_plan_id`, `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/brokers/{__init__,models,engine}.py`, `config/brokers.json`, `tests/runtime/test_brokers.py`. Files modified: `src/athena/errors.py` (+`BrokerError`), `src/athena/config/{models,loader,__init__}.py` (+`BrokerConfig`, `TimeInForce`, `load_broker_config`, exports). No analytical engine, order planning engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `BrokerManager`, `BrokerDefinition`, `BrokerCapabilities`, `BrokerRequest`, `BrokerResponse`, `BrokerExecutionPlan`, `BrokerSummary`, `BrokerHistory`, `BrokerReferences`, `TimeInForce`, `BrokerConfig`, `load_broker_config`. 12 new tests: canonical translation, unsupported order type rejection, unsupported fractional quantity rejection, unsupported time-in-force error, mock response creation, unregistered & disabled broker handling, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (production config loading), and an **end-to-end integration test** consuming a real `ExecutionPlan` from `OrderPlanningEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.4 — Order Planning Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Transforms position sizes into broker-neutral execution instructions and batches; execution plan generation only |
| Tests | 549 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Order Planning Engine (`src/athena/orders/`), which answers one question: "Given approved position sizes, what broker-neutral execution instructions should ATHENA prepare?" `OrderPlanningEngine` converts `PositionSizingPlan` outputs into broker-neutral `ExecutionPlan`s composed of `PlannedOrder`s grouped into `ExecutionBatch`es. It **prepares execution instructions only**: it performs no broker communication, no live order placement, no order fill tracking, and no market analysis.

Supported order actions & instruction types: `OrderAction` (`BUY`, `SELL`, `HOLD`) and `OrderType` (`MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`). Planning operations: `plan_execution(sizing_plan, *, as_of, decisions=None, order_type=None)` processes all position sizes in deterministic sorted order; `create_order(instrument_id, action, quantity, *, as_of, order_type=None, limit_price=None, stop_price=None)` creates a single explicit instruction. Batching policy (`batch_by_action`, `max_orders_per_batch`) groups planned orders into deterministic action batches (e.g. `BUY` batch, `SELL` batch) and chunks larger sets. Zero-quantity or `ZERO_ALLOCATION` items automatically generate `OrderAction.HOLD` instructions. All outputs (`PlannedOrder`, `OrderInstruction`, `ExecutionBatch`, `ExecutionPlan`, `OrderPlanningSummary`, `OrderPlanningHistory`) are immutable and preserve full `OrderReferences` back to `position_sizing_plan_id`, `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/orders/{__init__,models,engine}.py`, `config/orders.json`, `tests/runtime/test_orders.py`. Files modified: `src/athena/errors.py` (+`OrderPlanningError`), `src/athena/config/{models,loader,__init__}.py` (+`OrderPlanningConfig`, `OrderAction`, `OrderType`, `load_order_planning_config`, exports). No analytical engine, position sizing engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `OrderPlanningEngine`, `PlannedOrder`, `OrderInstruction`, `ExecutionBatch`, `ExecutionPlan`, `OrderPlanningSummary`, `OrderPlanningHistory`, `OrderReferences`, `OrderAction`, `OrderType`, `OrderPlanningConfig`, `load_order_planning_config`. 12 new tests: BUY planning, SELL planning, HOLD handling, MARKET & LIMIT order types, action batching & chunking, single order creation, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (positive batch size enforcement, production config loading), and an **end-to-end integration test** consuming a real `PositionSizingPlan` from `PositionSizingEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.3 — Position Sizing Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Converts approved capital allocations into executable share/unit quantities with rounding & precision policy; quantity calculation only |
| Tests | 537 passed / 0 failed (13 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Position Sizing Engine (`src/athena/sizing/`), which answers one question: "Given an approved capital allocation, how many units of the instrument should ATHENA purchase or sell?" `PositionSizingEngine` converts allocated capital amounts from an `AllocationPlan` into executable unit quantities based on instrument prices. It **calculates unit quantities only**: it performs no market analysis, no capital allocation policy decisions, no risk limit checks, and no order placement.

Supported sizing models & rounding policies: `WHOLE_SHARE` (integer share quantities via `int(raw_qty)`) and `FRACTIONAL` (decimal unit quantities up to configured `decimal_precision`, default 4 decimal places), combined with `ROUND_DOWN` (floor / conservative sizing ensuring cost <= allocation) or `ROUND_UP` (ceiling sizing). Sizing operations: `size_plan(allocation_plan, prices, *, as_of, model=None, rounding=None)` processes all allocations in deterministic sorted order; `size_amount(allocated_amount, unit_price, instrument_id, *, as_of)` calculates single-opportunity quantity. Zero-allocation items get `status="ZERO_ALLOCATION"`, `quantity=0`; missing or non-positive price items get `status="REJECTED_ZERO_PRICE"`, `quantity=0`. All outputs (`PositionSize`, `PositionSizingPlan`, `PositionSizingSummary`, `PositionSizingHistory`) are immutable and preserve full `SizingReferences` back to `allocation_plan_id`, `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/sizing/{__init__,models,engine}.py`, `config/sizing.json`, `tests/runtime/test_sizing.py`. Files modified: `src/athena/errors.py` (+`SizingError`), `src/athena/config/{models,loader,__init__}.py` (+`SizingConfig`, `SizingModel`, `RoundingMode`, `load_sizing_config`, exports). No analytical engine, capital allocation engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PositionSizingEngine`, `PositionSize`, `PositionSizingDecision`, `PositionSizingPlan`, `PositionSizingSummary`, `PositionSizingHistory`, `SizingReferences`, `SizingModel`, `RoundingMode`, `SizingConfig`, `load_sizing_config`. 13 new tests: whole-share sizing with round down & round up, fractional unit sizing with precision, zero-allocation handling, missing price handling, single-amount sizing, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative precision rejection, production config loading), and an **end-to-end integration test** consuming a real `AllocationPlan` from `CapitalAllocationEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.2 — Capital Allocation Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Policy-driven capital allocation per approved opportunity; enforces reserve floors and allocation models without position sizing or order execution |
| Tests | 524 passed / 0 failed (12 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Capital Allocation Engine (`src/athena/allocation/`), which answers one question: "How much capital should be reserved for each approved investment opportunity?" `CapitalAllocationEngine` evaluates available portfolio capital from a `PortfolioSnapshot` and allocates capital to candidate opportunities according to policy. It **determines capital allocation policy only**: it performs no market analysis, no position sizing (shares calculation), no risk limit checks, and no order execution.

Supported allocation models: `FIXED_AMOUNT` (configured fixed INR amount per opportunity), `FIXED_PERCENTAGE` (configured percentage of total portfolio cash), and `EQUAL_WEIGHT` (equal division of the allocatable pool among active candidates up to `max_opportunities`). Minimum cash reserve floor (`min_cash_reserve_pct`, default 20%) is strictly enforced before any allocation occurs (`allocatable_pool = max(0, available_cash - min_reserve_floor)`). Candidate opportunities (filtered for `TRADE` / `INCREASE_POSITION` decision types) are processed in deterministic sorted order. If remaining allocatable cash is less than target, a `status="PARTIAL"` allocation is issued; if pool is exhausted, `status="REJECTED_INSUFFICIENT_CASH"` or `REJECTED_RESERVE_FLOOR` is returned. Opportunities beyond `max_opportunities` are rejected as `REJECTED_MAX_OPPORTUNITIES`. `allocate_amount` provides explicit single-opportunity allocation. All outputs (`CapitalAllocation`, `AllocationPlan`, `AllocationSummary`, `AllocationHistory`) are immutable and preserve full `AllocationReferences` back to `portfolio_snapshot_id`, `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`.

Files created: `src/athena/allocation/{__init__,models,engine}.py`, `config/allocation.json`, `tests/runtime/test_allocation.py`. Files modified: `src/athena/errors.py` (+`AllocationError`), `src/athena/config/{models,loader,__init__}.py` (+`AllocationConfig`, `AllocationModel`, `load_allocation_config`, exports). No analytical engine, portfolio engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `CapitalAllocationEngine`, `CapitalAllocation`, `AllocationDecision`, `AllocationPlan`, `AllocationSummary`, `AllocationHistory`, `AllocationReferences`, `AllocationModel`, `AllocationConfig`, `load_allocation_config`. 12 new tests: fixed percentage allocation, fixed amount allocation, equal weight allocation, cash reserve threshold enforcement, max opportunities limit, partial & rejected statuses, deterministic replay (`to_dict` & `to_json` equality), immutable outputs (`FrozenInstanceError`), append-only history, config validation (negative values rejection, production config loading), and an **end-to-end integration test** consuming a real `PortfolioSnapshot` from `PortfolioEngine`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### P5.1 — Portfolio Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic portfolio state management, holdings, cash allocation, reserved capital, closed positions, and append-only history; state tracking only |
| Tests | 512 passed / 0 failed (18 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Portfolio Engine (`src/athena/portfolio/`), which answers one question: "Given ATHENA's completed investment decisions, what should the portfolio currently own?" `PortfolioEngine` manages portfolio state, active holdings, available cash, reserved capital, realized/closed positions, and append-only history. It **records state only**: it performs no market analysis, no position sizing calculations, no risk limit checks, and no order execution; it consumes completed `Decision` artifacts produced by the operational pipeline and maintains deterministic portfolio ledger state.

State operations: `open_position` (creates holding, allocates cash), `increase_position` (recomputes quantity & average price), `reduce_position` (reduces holding quantity, releases cost & records proceeds), `close_position` (removes holding, records immutable `ClosedPosition`, releases cash), `hold_position` (updates last-seen timestamp), `reserve_capital` / `release_capital` (allocates/frees reserved cash), and `apply_decision` (convenience mapper dispatching `open`, `increase`, `reduce`, `close`, or `hold` based on `DecisionType` and existing holdings). All operations return immutable `PortfolioSnapshot` objects referencing originating `decision_id`, `strategy`, `watchlist`, and `schedule_execution_id`. `PortfolioHistory` is **append-only** (`record()` returns a new history). Cash accounting enforces strict invariants (`total_cash == available + allocated + reserved`). Backdated operations, duplicate holdings on open, over-reduction, and cash deficits fail loudly with `PortfolioError`.

Files created: `src/athena/portfolio/{__init__,models,engine}.py`, `config/portfolio.json`, `tests/runtime/test_portfolio.py`. Files modified: `src/athena/errors.py` (+`PortfolioError`), `src/athena/config/{models,loader,__init__}.py` (+`PortfolioConfig`, `load_portfolio_config`, exports). No analytical engine, scheduling framework, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `PortfolioEngine`, `Portfolio`, `PortfolioSnapshot`, `Holding`, `ClosedPosition`, `CashBalance`, `ReservedCapital`, `PortfolioReferences`, `PortfolioSummary`, `PortfolioHistory`, `PortfolioConfig`, `load_portfolio_config`. 18 new tests: open/increase/reduce/close/hold operations, capital reservation & release, `apply_decision` with TRADE & FULL_EXIT decisions, duplicate holding protection, insufficient cash handling, backdated timestamp rejection, deterministic replay (`to_dict` and `to_json` equality), immutable snapshots (`FrozenInstanceError`), append-only history, config validation (negative cash rejection, production config loading), and an **end-to-end integration test** consuming the completed operational pipeline via `SchedulingFramework`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

---

## Phase 4 — Orchestration & Operational Intelligence (APPROVED)

### M4.7 — Scheduling Framework (completes Phase 4)

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic execution coordination over the completed pipeline; schedules and records when ATHENA runs without changing how ATHENA analyzes markets |
| Tests | 494 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed (completes Phase 4) |
| Branch | main |

Built the Scheduling Framework (`src/athena/scheduling/`), which answers one question: "When should ATHENA execute its existing operational pipeline?" `SchedulingFramework` coordinates the execution of existing operational components — the M4.1 `WorkflowEngine`, M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, M4.4 `StrategyFramework`, M4.5 `BacktestingEngine`, and M4.6 `ReportingAnalyticsEngine`. It **coordinates execution only**: it invokes no analytical engine directly, evaluates no strategy rules, derives no market intelligence, and modifies no completed decision.

Two execution paths: `execute(definition, *, as_of, pipeline_builder, universe, previous_watchlist=None)` runs the full daily pipeline (scanner → watchlist → strategy → analytics), returning an immutable `ScheduleExecution` referencing every upstream artifact (`scan_id`, `watchlist_snapshot_id`, `strategy_execution_id`, `analytics_report_id`); `execute_replay(definition, *, as_of, replay_points)` runs the replay pipeline (backtester → analytics), returning a `ScheduleExecution` referencing `backtest_run_id` and `analytics_report_id`. Five deterministic scheduling modes supported: `MANUAL`, `DAILY`, `WEEKLY`, `REPLAY`, `ONE_TIME`. Scheduling policies are configuration-driven (`config/scheduling.json`, `record_history` toggle). `ScheduleHistory` is **append-only** (`record()` returns a new history). **Failure isolation**: any pipeline or replay exception is caught, recorded as `ExecutionStatus.FAILED` with a diagnostic note, and never crashes the framework. Determinism: with `as_of` injected and no clock read for business decisions (monotonic clock used for duration measurement only), identical inputs produce identical execution records (verified). Disabled definitions are rejected loudly before execution.

Files created: `src/athena/scheduling/{__init__,models,engine}.py`, `config/scheduling.json`, `tests/runtime/test_scheduling.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `SchedulingConfig`, `load_scheduling_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, backtesting engine, reporting & analytics engine, workflow engine, or frozen-domain type touched. Public APIs added: `SchedulingFramework`, `ScheduleDefinition`, `ScheduledJob`, `ScheduleExecution`, `ExecutionReferences`, `ScheduleHistory`, `ScheduleSummary`, `ScheduleMode`, `SchedulingConfig`, `load_scheduling_config`. 21 new tests: full pipeline manual execution (all artifact references preserved), recurring schedules (daily/weekly/one-time modes), replay schedule execution (backtest + analytics references, execute() rejection of REPLAY mode), chronological execution ordering in history, deterministic rerun (`to_dict` equality), immutable outputs (`FrozenInstanceError` on execution and history), history filtering by definition and mode, summary generation, record_history disabled toggle, disabled definition rejection, failure isolation (BrokenScanner recorded as FAILED), config validation (unknown-key rejection, production config loads, missing fails loudly), and a **real end-to-end scheduled execution** through the full M4.1→M4.6 operational pipeline across three instruments. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; all prior engines and operational components unchanged.

### M4.6 — Reporting & Analytics

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic operational summaries and analytical statistics aggregated from completed artifacts; presentation + aggregation only |
| Tests | 473 passed / 0 failed (14 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Reporting & Analytics layer (`src/athena/analytics/`), which answers operational questions — "What happened today?", "How many instruments matched each strategy?", "How did decisions distribute across the universe?", "What activity occurred during replay?" — purely by aggregating completed artifacts from the M4.2 scanner, M4.3 watchlist manager, M4.4 strategy framework, and M4.5 backtester. `ReportingAnalyticsEngine` is **presentation + aggregation only**: it invokes no analytical engine, derives no new market intelligence, and modifies no completed decision. Every metric is a count or roll-up of an existing immutable artifact, and every report preserves references back to its sources.

Two entry points: `daily_report(scan_report, *, as_of, watchlist=None, strategy_execution=None)` produces a `kind="daily"` `AnalyticsReport` embedding `DailyAnalytics` (decision distribution taken from the scan's own summary; scan success/fail/skip counts; confidence and risk **level distributions** aggregated from completed decision reports; optional `WatchlistAnalytics` and `StrategyAnalytics`); `backtest_report(run, *, as_of)` produces a `kind="replay"` report embedding `BacktestAnalytics` (step counts, replay coverage, decision distribution summed across every replayed scan, and per-strategy match/instrument roll-ups from the run's performance). Confidence/risk distributions honour config: `confidence_levels`/`risk_levels` fix display order and `include_unknown` toggles the UNKNOWN bucket. Determinism: all inputs are immutable, no clock is read (`as_of` injected), distributions are built in fixed config-driven order, and `to_json()` emits sorted-key output — identical inputs yield an identical report (verified). Empty inputs produce empty distributions, not errors.

Files created: `src/athena/analytics/{__init__,models,engine}.py`, `config/analytics.json`, `tests/runtime/test_analytics.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `AnalyticsConfig`, `load_analytics_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, backtesting engine, workflow engine, or frozen-domain type touched. Public APIs added: `ReportingAnalyticsEngine`, `AnalyticsReport`, `DailyAnalytics`, `WatchlistAnalytics`, `StrategyAnalytics`, `BacktestAnalytics`, `AnalyticsSummary`, `AnalyticsConfig`, `load_analytics_config`. 14 new tests: decision/confidence/risk distributions, embedded watchlist+strategy analytics, skipped-count aggregation, include_unknown toggle, empty scan, deterministic replay, immutable report, sorted-JSON serialization, config validation (unknown-key rejection, lowercase-level rejection, production config loads, missing fails loudly), and a real **BacktestRun end-to-end** produced by the M4.5 chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, strategy framework, backtesting engine, workflow engine, and analytical engines all unchanged.

### M4.5 — Backtesting Engine

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic chronological replay of the existing operational pipeline across historical points, with no alternate analytical logic |
| Tests | 459 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Backtesting Engine (`src/athena/backtest/`), which answers one question: "How would ATHENA's completed analytical pipeline and strategy framework have behaved across historical market snapshots?" `BacktestingEngine.run(points, *, run_id=None)` replays a chronological sequence of caller-supplied `ReplayPoint`s (each a timezone-aware `as_of`, a universe, and the per-instrument pipeline builder for that date — identical in shape to what the live scanner consumes) through the **existing** operational components: the M4.2 `DailyMarketScanner`, M4.3 `WatchlistManager`, and M4.4 `StrategyFramework` (which in turn run the M4.1 `WorkflowEngine` and the analytical core). It **orchestrates only** — it introduces no alternate analytical logic, computes no market values, and replays the same deterministic pipeline used live; the analytical core stays the single source of truth. Out-of-scope items (portfolio valuation, P&L, sizing, brokerage/slippage/cost simulation, order execution) are deliberately absent.

Each replay point produces an immutable `BacktestStep` referencing the artifacts the real pipeline emitted — scan id, watchlist snapshot id, strategy execution id, replay date, and execution timestamp — and retaining the full `DailyScanReport`, `WatchlistSnapshot`, and `StrategyExecution` for complete history preservation. Watchlist state **threads forward** chronologically (per `carry_watchlist` config) so trend-based watchlists and strategies observe prior scans exactly as they would live. Steps run in strict chronological order (sorted by `as_of`; duplicate timestamps fail loudly). **Failure isolation**: any step whose scan/apply/execute raises is recorded `FAILED` with a diagnostic note; with `continue_on_error` the replay proceeds (and a failed step does not advance carried state), otherwise it stops. Results aggregate into a `BacktestRun` (run identity + period + `BacktestSession`) carrying a `BacktestSummary` with sum-checked step counts and per-strategy `StrategyPerformance` (total matches, steps with matches, distinct instruments) across the whole period. Determinism verified: with `as_of` injected and no clock read, the same dataset yields an identical `to_dict()` on rerun (internal per-stage timings are excluded from serialization).

Files created: `src/athena/backtest/{__init__,models,engine}.py`, `config/backtest.json`, `tests/runtime/test_backtest.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `BacktestConfig`, `load_backtest_config`, exports). No analytical engine, scanner, watchlist manager, strategy framework, workflow engine, or frozen-domain type touched. Public APIs added: `BacktestingEngine`, `ReplayPoint`, `BacktestStep`, `BacktestSession`, `BacktestRun`, `BacktestSummary`, `StrategyPerformance`, `BacktestConfig`, `load_backtest_config`. 19 new tests: chronological ordering (incl. out-of-order input), all-steps-completed, step references, watchlist carry-forward (and disabled), multi-strategy performance aggregation, partial-failure isolation, stop-on-error, failed-step-doesn't-advance-state, deterministic rerun, empty dataset, immutable run, duplicate-replay-point rejection, history preservation, config validation (defaults, unknown-key rejection, production config loads, missing fails loudly), and a three-day **end-to-end replay** through the real workflow → scanner → watchlist → strategy chain. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; workflow engine, scanner, watchlist manager, strategy framework, and analytical engines all unchanged.

### M4.4 — Strategy Framework

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Deterministic framework for multiple strategies to select completed decision artifacts by policy, without any analytical calculation |
| Tests | 440 passed / 0 failed (19 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Strategy Framework (`src/athena/strategy/`), which answers one question: "Which completed ATHENA decisions satisfy each strategy's deterministic selection policy?" `StrategyFramework.execute(scan_report, watchlist, *, as_of)` runs every registered strategy over the immutable outputs of the M4.2 scanner (`DailyScanReport` → `DecisionReport`) and M4.3 watchlist manager (`WatchlistSnapshot`), producing an immutable `StrategyExecution`. It **coordinates strategy evaluation only** — it parses completed decision artifacts into read-only views, invokes each strategy, and aggregates; it never invokes an analytical engine, computes an indicator, or reinterprets a decision. Strategies express *selection*, not intelligence.

The `Strategy` contract (`base.py`) is a small ABC declaring `name`, `version`, `description`, and a pure `select(views) -> tuple[MatchProposal, ...]`. Each strategy sees only `InstrumentView`s — a pre-parsed, read-only lens bundling one instrument's completed decision facts (type, direction, and the score/confidence/risk values *already produced* by the core, read as-is, UNKNOWN preserved as `None`) with its current watchlist memberships. Five reference strategies (Momentum, Swing, Breakout, Mean Reversion, Sector Rotation) share a `ConfigurableStrategy` base that applies declarative `StrategyRuleCfg` filters (decision set, direction, watchlist overlap, min score, min confidence, max risk). A threshold set against an UNKNOWN value never matches — missing analytical values exclude an instrument rather than being defaulted (no fabrication). Multiple strategies may select the same instrument; overlaps are surfaced in the summary.

Determinism: instruments are viewed in stable sorted order, strategies run in registration order (and `from_config` registers enabled reference strategies in id-sorted order), and matches are ordered by instrument — with `as_of` injected and no clock read, identical inputs yield an identical `StrategyExecution` (verified via `to_dict` replay equality). Each `StrategyMatch` records the instrument, originating decision id, originating watchlist memberships, a strategy-specific explanation, and supporting references (decision id, scan id, watchlist snapshot id, and the score/confidence/risk refs lifted faithfully from the decision report). Duplicate strategy registration and unknown reference-strategy ids fail loudly; failed/skipped scan results are ignored.

Files created: `src/athena/strategy/{__init__,models,base,strategies,framework}.py`, `config/strategy.json`, `tests/runtime/test_strategy.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `StrategyConfig` + `StrategyRuleCfg`, `load_strategy_config`, exports). No analytical engine, scanner, watchlist manager, workflow engine, or frozen-domain type touched. Public APIs added: `StrategyFramework`, `Strategy`, `InstrumentView`, `MatchProposal`, `StrategyMatch`, `StrategyResult`, `StrategySummary`, `StrategyExecution`, the five reference strategies + `ConfigurableStrategy` + `REFERENCE_STRATEGIES`, `StrategyConfig`, `load_strategy_config`. 19 new tests: multiple strategies, overlapping matches, no matches, UNKNOWN-value exclusion, failed-results ignored, explanation + references preservation, registration, duplicate-registration rejection, `from_config` enabled-only + unknown-id rejection, deterministic replay, immutable output, empty universe, config validation (unknown decision, unknown direction, empty strategies, production config loads, missing config fails loudly), and a **real chain** consuming a scanner-produced `DailyScanReport` and a watchlist-manager-produced `WatchlistSnapshot`. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, watchlist manager, workflow engine, and analytical engines all unchanged.

### M4.3 — Watchlist Manager

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Maintain deterministic, explainable named watchlists derived exclusively from completed scan/decision artifacts |
| Tests | 421 passed / 0 failed (21 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Watchlist Manager (`src/athena/watchlist/`), which answers one question: "Which instruments deserve ongoing attention based on ATHENA's completed decisions?" `WatchlistManager.apply(scan_report, *, as_of, previous=None)` folds an immutable `DailyScanReport` (M4.2) into a new immutable `WatchlistSnapshot`. It **coordinates state only** — it never executes an analytical engine, never recalculates a decision, and never invents a conclusion; it reads only the completed decision outcomes already produced by the pipeline and scanner, and organises them into named watchlists.

Classification is entirely **configuration-driven** (`config/watchlist.json`, validated by `WatchlistConfig`). Two rule kinds cover the initial five watchlists: a `decision_in` rule (membership when the instrument's current decision type is in a configured set — **High Conviction** ← TRADE/INCREASE_POSITION, **Watch** ← WATCH/WAIT, **Rejected** ← NO_TRADE/AVOID_SECTOR) and a `trend` rule (membership by change in decision *strength* versus the previous scan, using a configurable `decision_rank` map — **Improving** when the rank rose, **Weakening** when it fell). An instrument may belong to several watchlists at once (e.g. both High Conviction and Improving).

`apply` is a **pure function** of `(config, previous, scan_report, as_of)`: no hidden state, no clock read (`as_of` injected), instruments processed in stable sorted order — so replaying the same scan sequence yields bit-identical snapshots (verified). Every membership change is recorded as an explained `WatchlistChange` (ADDED / RETAINED / REMOVED) stating *why the instrument entered, why it remained, or why it exited* (rule no longer satisfied, or absent from the current scan). `entered_as_of` is preserved across retentions so an entry's original entry time is never lost. `WatchlistHistory` is **append-only** — `record()` returns a new, extended history and never overwrites prior state. Failed/skipped scan results are ignored (only completed decisions classify); a scan report containing a duplicate instrument fails loudly.

Files created: `src/athena/watchlist/{__init__,models,manager}.py`, `config/watchlist.json`, `tests/runtime/test_watchlist.py`. Files modified: `src/athena/config/{models,loader,__init__}.py` (add `WatchlistConfig` + rule models, `load_watchlist_config`, exports). No analytical engine, scanner, workflow engine, or frozen-domain type touched. Public APIs added: `WatchlistManager`, `WatchlistSnapshot`, `WatchlistEntry`, `WatchlistChange`, `WatchlistChangeType`, `WatchlistHistory`, `WatchlistSummary`, `WatchlistConfig`, `load_watchlist_config`. 21 new tests: decision-in classification, multi-watchlist membership, additions/retention/removal (rule-lapse and absence), improving/weakening trends, no-trend-without-prior, append-only history + entry/exit explanation, deterministic replay, immutable snapshots, empty scan (and empty-scan removals), duplicate-instrument protection, failed/skipped results ignored, config validation (duplicate names, unknown decision, production config loads, missing config fails loudly), and a **real DailyScanReport** produced by the M4.2 scanner classified across two cycles. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed; scanner, workflow engine, and analytical engines all unchanged.

### M4.2 — Daily Market Scanner

| | |
|---|---|
| Completed | 2026-07-21 |
| Scope | Coordinate ATHENA's full analytical workflow across the approved universe into one immutable daily scan report |
| Tests | 400 passed / 0 failed (10 new) |
| Status | **APPROVED** — Principal Engineer review passed |
| Branch | main |

Built the Daily Market Scanner (`src/athena/scanner/`), which answers a single question: "What does ATHENA conclude today for every eligible instrument?" `DailyMarketScanner.scan(universe, *, as_of, pipeline_builder)` iterates the universe in **stable sorted order** (`sorted(set(universe))` — deterministic, deduplicated), asks the caller-supplied `pipeline_builder` for a per-instrument `InstrumentPlan`, executes that plan's `WorkflowDefinition` through the shared `WorkflowEngine`, and — after the workflow completes — reads the captured `ScanCapture` and renders a `DecisionReport` via the existing `DecisionReportingEngine`. It **coordinates only**: it reuses M4.1's engine and M3.7's reporting engine, invokes analytical engines exclusively inside workflow stages defined by the caller, and recalculates nothing.

The design challenge was that M4.1's `WorkflowExecution` (frozen, approved) does not surface the `DecisionOutcome`. Rather than modify the approved engine (which would need an ADR), the scanner uses a **capture pattern**: `InstrumentPlan` pairs the workflow definition with a `collect()` callable; workflow stages populate a closure, and the scanner calls `collect()` after `execute()` to retrieve the outcome. No M4.1 change, no frozen-domain change.

**Failure isolation** is total — every per-instrument step (build, execute, collect, report) is wrapped so one instrument's failure produces a `FAILED` result with a diagnostic note and never aborts the scan; a builder returning `None` yields `SKIPPED`. Results aggregate into an immutable `DailyScanReport` with `ScanStatistics` (sum-checked total/successful/failed/skipped) and a `ScanSummary` (decision-type distribution, frozen via `MappingProxyType`), plus `result_for()` lookup and a JSON-safe `to_dict()`. Determinism verified: two scanners under fixed clocks produce bit-identical `to_dict()`.

Files created: `src/athena/scanner/{__init__,models,scanner.py}`, `tests/runtime/test_scanner.py`. Files modified: none (pure addition; no engine or contract touched). Public APIs added: `DailyMarketScanner`, `DailyScanReport`, `InstrumentPlan`, `InstrumentScanResult`, `ScanCapture`, `ScanStatistics`, `ScanSummary`, `PipelineBuilder`. 10 new tests: multi-instrument scan, deterministic ordering, empty universe, partial-failure isolation, skipped instrument, failed result carries no report, replay determinism, immutability, `to_dict` shape, and a **real multi-instrument pipeline** wiring indicator → regime → scoring → decision engines through workflows. ruff clean; no ADR; no drift; no tech debt. Validation checklist 1–10 passed.

### M4.1 — Workflow Orchestration Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic central orchestrator that runs analytical engines as coordinated pipeline stages |
| Tests | 390 passed / 0 failed (17 new) |
| Status | **APPROVED** — orchestration foundation for Phase 4 |
| Branch | main |

Built the runtime orchestration layer (`src/athena/runtime/`, realizing the blueprint's reserved §2 `runtime` module — building the plan, not a new module). `WorkflowEngine` executes a `WorkflowDefinition` (a validated DAG of `WorkflowStage`s) in a deterministic topological order, passing a read-only `WorkflowContext` accumulator through the stages; each stage's callable invokes an existing analytical engine and returns named outputs the engine merges (collisions rejected). It **coordinates only** — performs no analysis, duplicates no engine logic, modifies no engine. Dependency validation rejects missing dependencies, cycles, and duplicate stage names up front (`WorkflowError`). Failure isolation: a failed stage is recorded with its error and its downstream dependents are SKIPPED, while independent branches still run. Timing is captured per stage (offset + duration) via an **injected clock**, so under a fixed clock an execution is bit-identical — replay determinism verified. Produces an immutable `WorkflowExecution` (the execution report) plus a presentation-only `WorkflowReport` (`to_dict`/`to_json`/`to_text`). Verified end-to-end by wiring the real indicator → regime → scoring → decision engines as stages — the orchestrator ran the full pipeline without duplicating any engine.

Runtime types live in `src/athena/runtime/` — the blueprint's planned orchestration module — no ADR, no frozen-domain change, no analytical engine touched. Files created: `src/athena/runtime/{__init__,models,workflow,report}.py`, `tests/runtime/test_workflow.py`. Files modified: `src/athena/errors.py` (+WorkflowError). Public APIs added: `WorkflowEngine`, `WorkflowDefinition`, `WorkflowStage`, `WorkflowContext`, `WorkflowExecution`, `WorkflowReport`, `StageResult`, `ExecutionStatus`, `build_definition`. ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence (COMPLETE — pending formal review)

### M3.7 — Decision Trace & Reporting  (completes Phase 3)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Presentation-only human- and machine-readable decision reports from immutable artifacts |
| Tests | 373 passed / 0 failed (11 new) |
| Status | **Awaiting owner approval** — closes Phase 3; Phase 4 blocked pending full Phase-3 review |
| Branch | main |

Built `DecisionReportingEngine` (`src/athena/reporting/`), completing Phase 3. It consumes a `DecisionOutcome` plus the source artifacts (scoring, confidence, risk, evidence bundle, indicators) and produces an immutable `DecisionReport` offering two views derived from the same source: `to_dict()`/`to_json()` (machine-readable, JSON-safe, sorted-key deterministic) and `to_text()` (human-readable, sectioned). The report faithfully mirrors the decision — decision summary/outcome/status/direction, trade-plan summary, all six gate results, score summary with component breakdown, confidence dimensions, risk dimensions, evidence summary (provenance + missing sources), indicator summary, full reasoning-stage trace, and referenced artifact ids. Presentation only: it never modifies, reinterprets, or recalculates any artifact, and adds no new conclusions. UNKNOWN is displayed explicitly for every absent artifact (verified on the INSUFFICIENT_DATA path). Pure and deterministic: no I/O, clock, or randomness; both views reproducible.

Report types live in `src/athena/reporting/` (not frozen domain §4) — no ADR. Files created: `src/athena/reporting/{__init__,models,engine}.py`, `tests/decision/test_reporting.py`. No config needed. Public APIs added: `DecisionReportingEngine.report`, `DecisionReport` (`to_dict`, `to_json`, `to_text`). Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 3 — Decision Intelligence: COMPLETE (pending formal review)

All seven milestones implemented and individually reviewed: M3.1 Evidence Aggregation, M3.2 Indicator Engine, M3.3 Scoring, M3.4 Confidence, M3.5 Risk, M3.6 Decision, M3.7 Reporting. ATHENA now runs a complete, end-to-end, evidence-first decision pipeline: canonical data → market intelligence → aggregated evidence → objective indicators → transparent scores → confidence → risk → gated, auditable decisions → faithful human/machine reports. Every decision is deterministic, replayable, and traceable back to explicit evidence, measurements, and configuration; the frozen-domain TRADE invariant is enforced at construction. 373 tests, ruff-clean, zero technical debt. Ready for full Phase-3 review before Phase 4 is authorized.

---

### M3.6 — Decision Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First deterministic, auditable decisions combining scores + confidence + risk via config-driven gates |
| Tests | 362 passed / 0 failed (12 new) |
| Status | **Awaiting owner approval** — M3.7 (Decision Trace & Reporting) blocked until approved |
| Branch | main |

Built `DecisionEngine` (`src/athena/decision/`), the capstone that combines the analytical pipeline into the first explainable decisions. It consumes approved artifacts only (ScoringResult, ConfidenceAssessment, RiskAssessment, EvidenceBundle, RegimeResult, indicators, optional market/sector health) and produces the **frozen-domain** `Decision` + `DecisionTrace` wrapped in a `DecisionOutcome`. It evaluates all six §8.5 quality gates (DATA, EVIDENCE, RISK, EXPLAINABILITY, CONFIDENCE, MARKET) as `GateResult`s, then applies config-driven policy: TRADE (all gates pass + composite ≥ trade threshold + directional regime + buildable plan), WATCH (composite in watch band), NO_TRADE (below watch), or INSUFFICIENT_DATA (no composite). Every frozen invariant is honored — a TRADE always carries a `TradePlan`, a direction, and zero failed gates (verified end-to-end: a strong-bull pipeline yields TRADE with all six gates green). Trade plans use analytical levels only (last close ± ATR multiples for stop/target, constant risk-reward); `position_size` is a provisional unit — **no capital-based sizing** (deferred to the capital layer). The `DecisionTrace` records the full reasoning path (regime → market/sector health → evidence → score → confidence → risk → decision → trade_plan) with references. Pure and replayable: injected `as_of`, Decimal math, thresholds from `decision.json`; consumes approved artifacts, never recalculates lower layers or touches providers/repositories.

Engine + `DecisionOutcome` live in `src/athena/decision/` (the frozen `Decision`/`DecisionTrace` come from `athena.domain.decision` — no §4 change) — no ADR. Files created: `src/athena/decision/{__init__,models,engine}.py`, `config/decision.json`, `tests/decision/test_decision.py`. Files modified: `config/models.py` (+DecisionConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_decision_config). Public APIs added: `DecisionEngine.decide`, `DecisionOutcome`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.5 — Risk Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic descriptive exposure assessment across six independent risk dimensions |
| Tests | 350 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M3.6 (Decision Engine) blocked until approved |
| Branch | main |

Built `RiskEngine` (`src/athena/risk/`). It consumes approved artifacts only and produces an immutable `RiskAssessment` of six independently explainable dimensions (higher value = more risk), each degrading to explicit `UNKNOWN`: volatility risk (regime volatility label), liquidity risk (Volume MA vs configured minimum), gap risk (regime gap label), event risk (CalendarContext expiries/scheduled events), market-environment risk (market-health labels mapped to risk points, averaged), and a concentration indicator (investable-universe breadth). Each dimension carries `RiskContribution` traces and a LOW/MEDIUM/HIGH level; the overall risk is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Risk measures exposure only — independent of opportunity, and never a recommendation or position size. Missing artifacts produce transparent UNKNOWN; nothing is fabricated. Pure and replayable: injected `as_of`, Decimal math, all point maps from `risk_assessment.json` (a new file, kept separate from the F-4 no-trade rules in `risk.json`). Consumes approved artifacts, never providers/repositories.

Result types in `src/athena/risk/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/risk/{__init__,models,engine}.py`, `config/risk_assessment.json`, `tests/decision/test_risk.py`. Files modified: `config/models.py` (+RiskAssessmentConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_risk_assessment_config). Public APIs added: `RiskEngine.assess`, `RiskAssessment`, `RiskDimension`, `RiskContribution`, `RiskLevel`, `RiskStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.4 — Confidence Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic evaluation-reliability assessment across six independent confidence dimensions |
| Tests | 334 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M3.5 (Risk Engine) blocked until approved |
| Branch | main |

Built `ConfidenceEngine` (`src/athena/confidence/`). It consumes approved artifacts only — EvidenceBundle, ScoringResult, IndicatorResults — and produces an immutable `ConfidenceAssessment` of six independently explainable dimensions, each degrading to explicit `UNKNOWN`: evidence completeness (present vs required sources), data freshness (validation reports passed vs total), indicator availability (OK vs total), cross-engine agreement (dispersion of known component scores), unknown ratio (share of known artifacts), and consistency (absence of contradictory signals among known scores, config divergence gap). Each dimension carries `ConfidenceContribution` traces and a LOW/MEDIUM/HIGH level; the overall confidence is a config-weighted mean over known dimensions with a `completeness` ratio and `unknown_stats`. Confidence measures evaluation reliability only — never market direction, attractiveness, or risk. Missing artifacts transparently reduce confidence; nothing is fabricated or inferred. Pure and replayable: injected `as_of`, Decimal math, thresholds/weights from `confidence.json`; consumes approved artifacts, never providers/repositories.

Result types in `src/athena/confidence/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/confidence/{__init__,models,engine}.py`, `config/confidence.json`, `tests/decision/test_confidence.py`. Files modified: `config/models.py` (+ConfidenceConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_confidence_config). Public APIs added: `ConfidenceEngine.assess`, `ConfidenceAssessment`, `ConfidenceDimension`, `ConfidenceContribution`, `ConfidenceLevel`, `ConfidenceStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.3 — Scoring Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Transparent, config-driven component + composite scores from approved evidence and indicators |
| Tests | 317 passed / 0 failed (18 new) |
| Status | **Awaiting owner approval** — M3.4 (Confidence Engine) blocked until approved |
| Branch | main |

Built `ScoringEngine` (`src/athena/scoring/`). It consumes approved artifacts only — regime, market-health, sector-health assessments and `IndicatorResult`s — and produces six independent `ComponentScore`s (trend, momentum, market quality, sector quality, liquidity, technical structure), each 0–100 with a full `Contribution` trace referencing the exact regime/health dimension, indicator, and configured point value behind it, plus a plain-language explanation. A `CompositeScore` weights the known components (config weights sum to 100) and retains a complete `CompositeBreakdownItem` breakdown including each component's weight, value, and weighted contribution, with a `completeness` ratio. UNKNOWN propagation is strict: any missing evidence/indicator yields an explicit UNKNOWN component (no value, no fabricated default), unscoreable dimensions are excluded from averages, and the composite is UNKNOWN only when nothing is scoreable. Scores are intermediate artifacts — no buy/sell/hold, sizing, risk, or portfolio logic. Pure and replayable: injected `as_of`, Decimal math, all point maps from `scoring.json`; consumes approved artifacts, never raw providers/repositories.

Result types in `src/athena/scoring/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/scoring/{__init__,models,engine}.py`, `config/scoring.json`, `tests/decision/test_scoring.py`. Files modified: `config/models.py` (+ScoringConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_scoring_config). Public APIs added: `ScoringEngine.score`, `ScoringResult`, `ComponentScore`, `CompositeScore`, `CompositeBreakdownItem`, `Contribution`, `ScoreStatus`. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.2 — Indicator Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic technical-indicator measurement layer over canonical candles |
| Tests | 299 passed / 0 failed (26 new) |
| Status | **Awaiting owner approval** — M3.3 (Scoring Engine) blocked until approved |
| Branch | main |

Built `IndicatorEngine` (`src/athena/indicators/`) computing SMA, EMA, RSI (Wilder), ATR (Wilder), MACD, ADX (Wilder), and Volume MA from canonical candle data. Parameters are configuration-driven (`indicators.json`, extended with sma/macd/adx/volume_ma); calculations are pure Decimal functions in `calculations.py`; each result is an immutable `IndicatorResult` carrying name, status, parameters, window used, value(s), `IndicatorEvidence` (formula + inputs + explanation), and tz-aware ts. Insufficient history yields an explicit `UNKNOWN` result with no values (never a fabricated number). Strictly measurement-only — no signals, crossovers-as-events, composites, scoring, or interpretation; results never imply bullish/bearish/strength/weakness. Pure and replayable: injected `as_of`, deterministic Decimal math (fixed 28-digit context), candles sorted; provider/repository/intelligence-independent.

Result types in `src/athena/indicators/models.py` (measurement types, not frozen domain §4) — no ADR. Files created: `src/athena/indicators/{__init__,models,calculations,engine}.py`, `tests/decision/test_indicators.py`. Files modified: `config/indicators.json` (added sma/macd/adx/volume_ma params + versions; ema now single-period). Public APIs added: `IndicatorEngine.compute` / `compute_all`, `IndicatorName`, `IndicatorStatus`, `IndicatorResult`, `IndicatorEvidence`. Tests validate exact SMA/Volume-MA values, RSI boundaries (all-gains→100, all-losses→0, alternating≈50), ATR/MACD zero on flat/constant series, ADX range, Decimal precision, UNKNOWN handling, determinism, and immutability. Prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M3.1 — Evidence Aggregation Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Gather all approved intelligence into a single immutable, provenance-tagged evidence graph |
| Tests | 273 passed / 0 failed (10 new) |
| Status | **Awaiting owner approval** — M3.2 (Indicator Engine) blocked until approved |
| Branch | main |

Built `EvidenceAggregationEngine` (`src/athena/evidence/`), the first Decision Intelligence module. It gathers approved intelligence — regime, market health, sector health, universe, corporate-action evidence, and validation reports — into a single immutable `EvidenceBundle` of provenance-tagged `EvidenceItem`s. Each item records its `source`, `kind`, `reference_id`, timezone-aware `ts`, explanation, and the original (frozen) intelligence object as `payload` — so nothing is transformed or lost; provenance is preserved verbatim. The engine detects missing required sources (`required_sources` → `missing_sources`, `is_complete`) and publishes a per-source provenance count. Aggregation only — no scoring, signals, decisions, or transformation. Pure and replayable: injected `as_of`, deterministic fixed source ordering (sectors sorted), no I/O/clock/randomness; `EvidenceBundle` exposes `by_source`, `has_source`, `present_sources`.

Result types in `src/athena/evidence/models.py` (decision-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/evidence/{__init__,models,engine}.py`, `tests/decision/test_evidence_aggregation.py`. Public APIs added: `EvidenceAggregationEngine.aggregate`, `EvidenceBundle`, `EvidenceItem`, `EvidenceSource`. All prior engines and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence (COMPLETE — pending formal review)

### M2.4 — Universe Engine  (completes Phase 2)

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic investable-universe construction via config-driven eligibility rules + constituent-breadth export |
| Tests | 263 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — closes Phase 2; Phase 3 blocked pending full Phase-2 review |
| Branch | main |

Built `UniverseEngine` (`src/athena/universe/`). It evaluates each instrument independently against configuration-driven eligibility rules — active status, supported series, eligible exchange, data present, minimum trading history, minimum liquidity, and (when a calendar + window are supplied) data completeness — producing an immutable per-instrument `UniverseAssessment` (inclusion status, exclusion reasons, per-rule `RuleEvidence`, eligibility summary) and the frozen-domain `Universe` of included members (each with a full inclusion trace). Missing datasets produce explicit evidence, never silent exclusion. It also publishes **constituent advances/declines per sector** as a canonical output (`constituent_breadth`), completing the data dependency anticipated by Sector Health (M2.3) — computed from included instruments' latest vs prior close, and never by calling the Sector Health Engine. `max_universe_size` is advisory only (a hard cap would require ranking, which is out of scope) — all eligible instruments are included and the cap is surfaced in the summary. Pure and replayable (injected `as_of`, Decimal math, thresholds from `universe.json`); eligibility-focused, no ranking/scoring/selection.

Result types in `src/athena/universe/models.py` + `UniverseResult` in engine (not frozen domain §4; the canonical included set uses the frozen `Universe`/`UniverseMember`) — no ADR. Files created: `src/athena/universe/{__init__,models,engine}.py`, `tests/market_intel/test_universe.py`. Files modified: `config/models.py` (UniverseConfig +eligibility fields), `config/universe.json`. Public APIs added: `UniverseEngine.build`, `UniverseResult`, `UniverseAssessment`, `RuleEvidence`. Regime, Market Health, Sector Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

---

## Phase 2 — Market Intelligence: COMPLETE (pending formal review)

All four milestones implemented and individually reviewed: M2.1 Regime Engine, M2.2 Market Health, M2.3 Sector Health, M2.4 Universe Engine. The Market Intelligence layer now describes market conditions (regime, market health), sector conditions (sector health), and constructs a trustworthy investable universe — all deterministic, explainable, replayable, and strictly descriptive/eligibility-focused (no scoring, ranking, or decisions). Engines consume canonical data + approved intelligence and are aware-but-not-dependent on one another. 263 tests, ruff-clean, zero technical debt. Ready for full Phase-2 review before Phase 3 (Decision Intelligence) is authorized.

---

### M2.3 — Sector Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive per-sector condition across four independently explainable dimensions |
| Tests | 246 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M2.4 (Universe Engine) blocked until approved |
| Branch | main |

Built `SectorHealthEngine` (`src/athena/sector_health/`). Per sector it consumes canonical sector-index `Candle` history (plus optional constituent breadth) and produces an immutable `SectorHealthAssessment` of four independently explainable dimensions, each degrading to explicit `*_UNKNOWN`: **trend** (fast/slow SMA → UPTREND/DOWNTREND/SIDEWAYS), **breadth** (constituent participation — reported `SECTOR_BREADTH_UNKNOWN` unless constituent advances/declines are supplied; never inferred, since constituent data arrives with M2.4), **momentum** (period ROC), and **volatility** (realized volatility = stdev of returns, a sector-specific context that complements — not duplicates — Market Health). `assess_many` evaluates multiple sectors deterministically. Every dimension emits `SectorHealthEvidence` with inputs, thresholds, outcome, and explanation. Pure and replayable (injected `as_of`, Decimal math incl. `Decimal.sqrt`, thresholds from `sector_health.json`); descriptive only — no ranking, rotation, selection, or signals. Regime-aware and Market-Health-aware but dependent on neither (optional, explanation-only).

Result types in `src/athena/sector_health/models.py` (not frozen domain §4) — no ADR. Files created: `src/athena/sector_health/{__init__,models,engine}.py`, `config/sector_health.json`, `tests/market_intel/test_sector_health.py`. Files modified: `config/models.py` (+SectorHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_sector_health_config). Public APIs added: `SectorHealthEngine.assess` / `assess_many`, `SectorHealthResult`, `SectorHealthAssessment`, `SectorHealthEvidence`, `SectorHealthLabel`, `SectorHealthConfig`, `load_sector_health_config`. Regime, Market Health, and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.2 — Market Health Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Descriptive assessment of overall market condition across four independently explainable dimensions |
| Tests | 223 passed / 0 failed (24 new) |
| Status | **Awaiting owner approval** — M2.3 (Sector Health) blocked until approved |
| Branch | main |

Built `MarketHealthEngine` (`src/athena/market_health/`). It consumes canonical `Candle` history + optional `MarketSnapshot`, and produces an immutable `MarketHealthAssessment` composed of four independently explainable dimensions, each always labelled (explicit `*_UNKNOWN` on insufficient data): **breadth** (advance ratio from snapshot advances/declines), **trend quality** (one-directional consistency of recent index returns — complements the Regime Engine's direction, does not replace it), **momentum** (period rate-of-change of the index), and **volatility** (contextual read of India VIX on market stability, framed as health not re-classification). Every dimension emits `HealthEvidence` carrying inputs, the thresholds that produced the label (owner suggestion #3), the outcome, and a human explanation. Pure and replayable (injected `as_of`, Decimal math, thresholds from `market_health.json`); descriptive only — no scores, rankings, or recommendations. Regime-aware but not regime-dependent: an optional `RegimeResult` enriches the trend-quality explanation only; labels are identical with or without it (verified by test).

Result types live in `src/athena/market_health/models.py` (market-intelligence types, not frozen domain §4) — no ADR. Files created: `src/athena/market_health/{__init__,models,engine}.py`, `config/market_health.json`, `tests/market_intel/test_market_health.py`. Files modified: `config/models.py` (+MarketHealthConfig and nested cfgs), `config/loader.py` + `config/__init__.py` (+load_market_health_config). Public APIs added: `MarketHealthEngine.assess`, `MarketHealthResult`, `MarketHealthAssessment`, `HealthEvidence`, `MarketHealthLabel`, `MarketHealthConfig`, `load_market_health_config`. Regime Engine and frozen domain unchanged; ruff clean; no drift; no tech debt.

### M2.1 — Regime Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Deterministic market-regime classification from canonical market data; descriptive, not prescriptive |
| Tests | 199 passed / 0 failed (17 new) |
| Status | **Awaiting owner approval** — M2.2 (Market Health) blocked until approved |
| Branch | main |

Built `RegimeEngine` (`src/athena/regime/`), the first Market Intelligence module. It consumes canonical `Candle` history (an index) plus an optional `MarketSnapshot` (India VIX) and produces the frozen-domain `RegimeAssessment` plus a supporting `RegimeEvidence` chain. Three orthogonal, deterministic dimensions, each always labelled (explicit `*_UNKNOWN` when data is insufficient — never a silent omission): **trend** (BULL/BEAR/SIDEWAYS via fast-vs-slow SMA and last close), **volatility** (HIGH/LOW/NORMAL via India VIX against configured bands), and **gap** (UP/DOWN/NONE via latest open vs prior close against the gap threshold). Pure and replayable: no I/O, no clock reads (time injected as `as_of`), no randomness; Decimal math throughout; thresholds from the existing `regime.json`. Output is strictly descriptive — labels, evidence, and explanation only; no scoring, ranking, or recommendation.

Regime result types live in `src/athena/regime/models.py` (market-intelligence types, not additions to frozen domain §4, which already provides `RegimeAssessment`) — no ADR required. Files created: `src/athena/regime/{__init__,models,engine}.py`, `tests/market_intel/test_regime.py`. Public APIs added: `RegimeEngine.assess`, `RegimeResult`, `RegimeEvidence`, `RegimeLabel`. Validation checklist passed; frozen contracts unchanged; ruff clean; no drift; no tech debt.

---

## Phase 1 — Data Foundation: COMPLETE ✅ (approved 2026-07-20)

All six milestones implemented and individually reviewed: M1.1 provider contracts, M1.2 FileProvider, M1.3 validation layer, M1.4 corporate actions, M1.5 SQLite repository, M1.6 backup & restore. The data foundation now ingests (via an abstract, order-incapable provider), validates, historically adjusts, persists, and recovers canonical market data — deterministically, explainably, and replayably. 182 tests, ruff-clean. **Phase 1 approved; Phase 2 (Market Intelligence) authorized.**

---

### M1.5 — SQLite Repository

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Persistent storage layer: schema, repository, WAL/FK config, integrity verification, quarantine + corporate-action persistence |
| Tests | 171 passed / 0 failed (23 new) |
| Status | **Awaiting owner approval** — M1.6 (backup & restore) blocked until approved |
| Branch | main |

Built `SqliteRepository`, ATHENA's persistent ledger. Deterministic schema (ATHENA-002 §5) with a single `candles` table keyed by (instrument_id, timeframe, ts_open) serving both daily and intraday, plus `instruments`, `quotes`, `market_snapshots`, `corporate_actions`, `quarantine_records`, and a `schema_version` table for future migrations. Explicit primary keys, foreign keys, and a range index; all decimals/timestamps stored as TEXT (ISO-8601, tz-aware) to preserve exact precision. SQLite configured with WAL mode and enforced foreign keys per connection; writes wrapped in transactions with a public `transaction()` context manager (commit on success, rollback on exception). Repository returns canonical domain objects, never rows — no provider, validation, or intelligence logic lives here. Append-only history (duplicate primary keys rejected as `RepositoryError`); instruments and quarantine support idempotent upsert. `verify_integrity()` runs `PRAGMA integrity_check` + `PRAGMA foreign_key_check` + schema-version check and returns an immutable `IntegrityReport`; corrupt/non-SQLite files fail loudly. Quarantine persistence serializes/restores `QuarantineRecord`s with full validation evidence, timestamps, types, severities, and explanations.

Storage types live in `src/athena/data/store/` — §5 schema is not among the §19-frozen items, and the milestone checklist confirms no ADR — so schema evolution is allowed within the data module. Files created: `src/athena/data/store/{__init__,schema,serialization,repository}.py`, `tests/data_layer/test_repository.py`. Files modified: `src/athena/errors.py` (+RepositoryError), `.gitignore` (WAL sidecars + db/). Public APIs added: `SqliteRepository` (initialize, upsert_instrument, get_instrument, list_instruments, add_candles, get_candles, add_quotes, get_quotes, add_snapshot, get_latest_snapshot, add_corporate_action, get_corporate_actions, save_quarantine, get_quarantine, list_quarantine, verify_integrity, transaction, close), `IntegrityReport`, `SCHEMA_VERSION`. Validation checklist 1–10 passed; provider contract, Validation Layer, and Corporate Actions Engine untouched; no drift; no tech debt.

### M1.4 — Corporate Actions Engine

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider/storage-independent modeling + deterministic back-adjustment for splits, bonuses, dividends, renames |
| Tests | 148 passed / 0 failed (19 new) |
| Status | **Awaiting owner approval** — M1.5 (SQLite repository) blocked until approved |
| Branch | main |

Built a Corporate Actions Engine that interprets the canonical (frozen) `CorporateAction` domain object into validated typed actions (`Split`, `Bonus`, `Dividend`, `Rename`) and applies deterministic back-adjustment to candle datasets, producing **adjusted copies** with full evidence — originals are never mutated (and `Candle` is frozen regardless). Standard model: an action with ex_date D adjusts only candles strictly before D; split from→to scales price by from/to and volume by to/from; bonus b:h scales price by h/(h+b); dividend scales price by (prev_close − amount)/prev_close using the raw close before D; factors are cumulative across sequential actions; renames map identifiers (with chain resolution A→B→C) and never touch candle values. Four explicit, traceable strategies (RAW, SPLIT_ADJUSTED, SPLIT_BONUS_ADJUSTED, FULLY_ADJUSTED) — no hidden behavior. Every adjustment emits immutable `AdjustmentEvidence` (action, ex_date, price/volume factor, affected record count, explanation, metadata); the whole run returns an immutable `AdjustmentResult`. Deterministic Decimal math (fixed context) and injected `as_of` make it fully replayable. Optional Calendar Engine only annotates whether an ex_date is a trading session — effective dates are never inferred. No fetching, no persistence, no provider/file/SQLite awareness.

Engine types live in `src/athena/data/corporate_actions/` — not additions to the frozen domain §4 — so no ADR was required. Files created: `src/athena/data/corporate_actions/{__init__,models,evidence,engine}.py`, `tests/data_layer/test_corporate_actions.py`. Files modified: `src/athena/errors.py` (+CorporateActionError). Public APIs added: `CorporateActionsEngine` (`adjust`, `build_symbol_map`, `resolve_symbol`), `parse_action`, `Split`/`Bonus`/`Dividend`/`Rename`, `CorporateActionType`, `AdjustmentStrategy`, `AdjustmentEvidence`, `AdjustmentResult`. Validation checklist 1–10 passed; provider contract and Validation Layer untouched; no drift; no tech debt.

### M1.3 — Validation Layer

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider-independent data-quality framework: freshness, OHLC, duplicate, gap validation; immutable reports; quarantine |
| Tests | 129 passed / 0 failed (25 new) |
| Status | **Awaiting owner approval** — M1.4 (corporate actions) blocked until approved |
| Branch | main |

Built a reusable validation framework that operates exclusively on canonical `Candle` objects and the Phase-0 Calendar Engine — no file/SQLite/broker/provider awareness. Validators are pure functions with an injected `as_of` (no clock reads → deterministic and replayable). Freshness compares daily data against the calendar's expected latest trading day and intraday data against the reference time, with configurable thresholds. OHLC validation checks the one business rule the Candle contract does NOT guarantee — strictly positive prices — and explicitly does not re-check H/L ordering (structurally enforced by the domain object) to avoid duplicating provider responsibility. Duplicate detection targets cross-dataset/ingestion-boundary duplicates (provider within-request dedup untouched). Gap detection uses the Calendar Engine for both missing trading sessions (weekends/holidays never counted) and missing intraday intervals; sessions are never inferred manually. Every check produces an immutable `ValidationReport` (type, result, severity, explanation, evidence, statistics, tz-aware timestamp); `DatasetValidator` aggregates into an immutable `ValidationSummary`; `QuarantineRegistry` records invalid datasets with preserved failure evidence and never auto-repairs.

Validation types live in `src/athena/data/validation/` — data-layer result types, NOT additions to the frozen canonical domain model (§4) — so no ADR was required. Files created: `src/athena/data/validation/{__init__,reports,validators,dataset_validator,quarantine,calendar_expectations}.py`, `config/validation.json`, `tests/data_layer/test_validation.py`. Files modified: `config/models.py` (+ValidationConfig/FreshnessConfig/GapConfig), `config/loader.py` + `config/__init__.py` (+load_validation_config). Public APIs added: `DatasetValidator`, `ValidationReport`, `ValidationSummary`, `ValidationType`, `ValidationResult`, `Severity`, `QuarantineRegistry`, `QuarantineRecord`, the five `validate_*` functions, `load_validation_config`, `ValidationConfig`. Validation checklist 1–10 passed; provider contract untouched; no drift; no tech debt.

### M1.2 — FileProvider

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | First production `MarketDataProvider`, backed by local CSV/JSON files; reference implementation for all future providers |
| Tests | 104 passed / 0 failed (37 new) |
| Status | **Awaiting owner approval** — M1.3 (validation layer) blocked until approved |
| Branch | main |

Implemented `FileProvider` conforming 100% to the frozen contract (passes the M1.1 suite unchanged). Loads daily candles, intraday candles, instrument metadata, market snapshots, and quotes from configurable file locations (`config/providers/file.json`, loaded via a new `load_file_provider_config` + `FileProviderConfig` model — `AthenaConfig` untouched, so config compatibility is preserved). Deterministic: no caching, no mutable global state, no clock reads, no concurrency; candles sorted ascending and deduplicated to honor the contract. Decimal precision and tz-aware timestamps preserved end to end. Error taxonomy differentiates missing files, invalid format (wrong header), unsupported instrument/timeframe/capability, and corrupted data (non-numeric values, impossible OHLC, naive timestamps, duplicate timestamps) — all `ProviderError` with file:line context. Validation is limited to what loading correctness requires; freshness/gap/cross-dataset validation deferred to M1.3 as instructed.

Files created: `src/athena/data/__init__.py`, `src/athena/data/providers/__init__.py`, `src/athena/data/providers/file_provider.py`, `config/providers/file.json`, two deterministic fixture datasets (`tests/data/fileprovider/` synthetic, `tests/data/fileprovider_sample/` sanitized-realistic with real symbols/ISINs but fictional prices), `tests/contract/test_file_provider_contract.py`, `tests/data_layer/test_file_provider.py`, dataset READMEs. Files modified: `config/models.py` (+FileProviderConfig, ProviderCapabilitiesConfig), `config/loader.py` + `config/__init__.py` (+loader). Public APIs added: `FileProvider`, `FileProvider.from_config_dir`, `load_file_provider_config`, `FileProviderConfig`. Validation checklist 1–10 passed; contract unchanged; no ADR; no drift; no tech debt.

### M1.1 — MarketDataProvider Contracts

| | |
|---|---|
| Completed | 2026-07-20 |
| Scope | Provider Protocol behavioral contract, ProviderCapabilities/ProviderHealth invariants, reusable contract test suite |
| Tests | 67 passed / 0 failed (16 new) |
| Status | **Awaiting owner approval** — M1.2 (FileProvider) blocked until approved |
| Branch | main |

Frozen Protocol signatures untouched (contract compatibility preserved). Added: constructor invariants on `ProviderCapabilities` (non-empty unique timeframes, history ≥ 1 day) and `ProviderHealth` (mandatory detail, tz-aware timestamps); a documented behavioral contract on the Protocol (capability honesty, candle ordering/uniqueness/range, emptiness-is-not-error, determinism, unknown-id failures, structurally-forbidden order methods); `tests/contract/provider_contract.py` — the conformance suite every provider (M1.2 FileProvider, future broker adapters per DD-1) must pass unchanged, including a `test_no_order_methods_exist` structural-safety check; proven against a deterministic in-memory `StubProvider` (test infrastructure only, arithmetic data, no randomness/clock reads) plus negative tests showing the suite catches rogue order methods and invalid capabilities. Validation checklist 1–10 passed; no ADR needed; no config changes.

---

## Phase 0 — Foundations

| | |
|---|---|
| Completed | 2026-07-20 |
| Blueprint scope | ATHENA-002 §14, Phase 0 |
| Tests | 51 passed / 0 failed |
| Status | **APPROVED** (owner + principal engineer review passed, 2026-07-20) |
| Branch | main |
| Lessons learned | Phase-sized batches are too large to review well — milestone-based workflow adopted from Phase 1 (see CLAUDE.md, docs/MILESTONES.md) |

### 1. Summary of completed work

Project scaffolding (`pyproject.toml`, `justfile`, `.env.example`); complete canonical domain model; layered configuration framework with strategy profiles, feature flags, and cross-file invariants; JSONL logging with secret redaction and run/cycle correlation; observability skeleton (metric timers, performance-budget violations, system-health pre-flight); Trading Calendar Engine loaded with the real NSE 2026 holiday calendar (16 weekday holidays + Muhurat on 2026-11-08); CLI commands `athena today`, `athena health`, `athena version`.

### 2. Architectural compliance review

All Phase 0 exit criteria pass: CalendarContext correct for the 10 acceptance dates including Republic Day (holiday) and Muhurat (special session overriding a Sunday, timings honestly "TBD" until NSE notifies); config invariant violations fail with readable errors naming field and rule; full suite green. Contracts match the blueprint exactly: PipelineContext enforces consumes/produces discipline (re-producing a key raises, F-1/ADR-003); `MarketDataProvider` Protocol contains no order methods (ADR-002); explanations are constructor-mandatory — a TRADE decision without a TradePlan, without a direction, or with a failed quality gate cannot be instantiated (F-12, ADR-005); prices are Decimal; timestamps are timezone-aware; clocks are injected. No architectural deviations; no ADR was needed.

### 3. Files created

- `src/athena/domain/` — enums, market, evidence, decision, run, health, context, interfaces (8 files)
- `src/athena/config/` — models (pydantic), loader + snapshot hashing (2 files)
- `src/athena/observability/` — logging, metrics, health (3 files)
- `src/athena/calendar/engine.py`, `src/athena/cli.py`, `src/athena/errors.py`
- `config/` — base, market.nse, risk, capital, regime, universe, indicators, profiles/intraday-momentum, calendar/{holidays,expiries,events} (10 files)
- `tests/` — conftest + 5 test modules + golden-dataset skeleton README
- Scaffolding: `pyproject.toml`, `justfile`, `.env.example`

### 4. Tests added (51)

Calendar acceptance (10 parametrized dates, timings, trading-session semantics, budget event, fail-loud on uncovered year, determinism); config (11 cases: invariants, typo rejection, missing file, unknown profile, unversioned indicator, out-of-session trading window, snapshot hash determinism and change-sensitivity); domain invariants (immutability, impossible OHLC, naive timestamps, mandatory explanations, score-breakdown sum, decision contract, context discipline, read-only context data); observability (JSON-line shape, run/cycle correlation, secret redaction, budget violation detection, health pre-flight honest WARNs, calendar-coverage BLOCKED); CLI (5 commands/paths).

### 5. Remaining work

Phase 1 (Data): `MarketDataProvider` contract test suite, FileProvider (EOD bhavcopy + intraday files), validation layer (freshness, OHLC sanity, gaps, duplicates), corporate-actions handling, SQLite store with backup/restore. Owner actions before relying on calendar-aware features: verify `config/calendar/holidays.json` against the NSE circular and set `verified_by_owner: true`; populate `config/calendar/expiries.json` from the current derivatives circular (left empty by design — expiry weekdays change by circular and were not guessed).

### 6. Risks discovered

The AI sandbox cannot delete files, so `athena health` reports storage/logs BLOCKED when run there — the check is working as designed and passes on the owner's machine. The blueprint pins Python ≥ 3.12 but verification ran on 3.10; `pyproject.toml` currently declares ≥ 3.10 — tighten to 3.12 once the production interpreter is confirmed.

### 7. Suggested improvements (implementation-only)

A `just verify-calendar` target that diffs `holidays.json` against the NSE circular each January; a minimal GitHub Actions workflow (ruff + mypy + pytest) once the owner wants CI on pushes.
