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

## Phase 10 — Live Dry-Run Operations & AI Playbook Learning (COMPLETE)

Establishes live scheduled paper-trading operations, real-time market data ingestion, daily trace briefings, and automated playbook diagnostics. One milestone in flight at a time.

| Milestone | Scope | Status |
|---|---|---|
| **M10.1** Live Data Ingestion | Real-time broker/feed Quote and Candle ingestion, duplicate/freshness validation in live loop | ✅ APPROVED |
| **M10.2** Scheduled Dry-Run Operations | Premarket and periodic intraday refresh cycles running daily on scheduler, logging to SQLite | ✅ APPROVED |
| **M10.3** Daily Briefing Notifications | Automated email/webhook notifications dispatching daily decision traces and summaries | ✅ APPROVED |
| **M10.4** AI Playbook Diagnostics | Diagnostic analysis over Decision Journal outcomes, proposing configuration weight tuning suggestions | ✅ APPROVED |

**Phase 10 closed (2026-07-23):** owner approved M10.4. Production readiness for daily advisory use continues under [`docs/PRODUCTION_READINESS_ROADMAP.md`](PRODUCTION_READINESS_ROADMAP.md) tracks R1–R6 (not authorized until owner gates each item).

### Production readiness track

| Milestone | Scope | Status |
|---|---|---|
| **R1** File-backed Daily Ops SOP | SOP + smoke script for file-backed mock trading day | ✅ APPROVED |
| **R2** Decision Journal Persistence | Persist decisions/traces for OK briefings | ✅ APPROVED |
| **R3–R6** | See production readiness roadmap | R3–R6 ✅ APPROVED |

SOP: [`docs/ops/FILE_BACKED_DAILY_OPS.md`](ops/FILE_BACKED_DAILY_OPS.md) · Smoke: `./scripts/smoke_file_backed_day.sh`

### Dashboard ops extensions (post Phase 9/10)

| Milestone | Scope | Status |
|---|---|---|
| **D-P1** Portfolio reset | Reset open \| all owner fills with ADMIN + CONFIRM | 🔄 Ready for review |
| **D-V1** Owner candidate list | SQLite `owner_candidates` + MI CRUD, shared with CLI | 🔄 Ready for review |
| **D-V2** Eligibility in cycle | UniverseEngine on candidates → real Eligible/Excluded | 🔄 Ready for review |
| **D-V3** Qualify WATCH/TRADE | Scan eligible → persist decisions; MI qualified-today | 🔄 Ready for review |
| **D-U1–U3** Nifty 500 seed | Daily merge-unique Nifty 500 → `owner_candidates` | 🔄 Ready for review |

### Professional live-entry track (post Phase 9/10)

| Milestone | Scope | Status |
|---|---|---|
| **M-E1** Auth surface | Owner env seed, unlock UI, JWT login/refresh/logout/me | ✅ Approved |
| **M-E2** Workstation host | `athena serve`, optional due-cycle worker, shared runner lock | ✅ Approved |
| **M-E3** Kite morning gate | Verified read-only session, in-UI authorize/exchange/reconnect | ✅ Approved |
| **M-E4** macOS Dock launcher | Thin `.app` wrapper + installer; health-aware open/start | ✅ Approved |
| **M-E5** Hardening & ops polish | Login lockout, JWT hardening, optional TLS, live-entry SOP, QA verification | ✅ Approved |

**Professional live-entry track closed (2026-07-24):** owner approved M-E5;
the complete Dock/URL → unlock → Kite → LIVE workflow is operational.

### Instrument decision brief track (post Phase 9/10)

| Milestone | Scope | Status |
|---|---|---|
| **M-D1** Decision Brief foundation | Selected-stock brief, TradePlan presentation, non-destructive daily dismiss | ✅ Approved |
| **M-D2** Chart + plan overlays | Read-only candles API, intraday chart, entry/stop/target overlays, freshness; after-hours validate clamps to last session close | ✅ Approved |
| **M-D3** ATHENA depth | Eligibility, decision timeline, score/confidence/risk detail, re-validate/remove candidate | ✅ Approved |
| **M-D4** Context lane | Session events, deterministic brief export, approved external context links | ✅ Approved |
| **M-D5** News evidence | Provenance-first news annotation after DD-5/provider approval | ⏸ Deferred |

**Instrument decision brief track closed (2026-07-25):** owner approved M-D4
after live smoke-test review (regime/market-health persistence, external
links, Decision Brief export, Reasoning Trace DAG redesign, header
Re-validate). M-D5 remains deferred until DD-5/provider approval.

---

### Intraday Edge Program (post M-D4, owner direction 2026-07-25)

AI-driven roadmap toward a "no compromise" world-class intraday analyzer.
AI proposes and implements; owner approves each completed milestone before
the next starts (per CLAUDE.md milestone workflow — unchanged). Every item
below was checked against ATHENA-002 §2/§4/§7/§19 and Risk Register R6
(module map closed, domain/contracts frozen, no scope creep) before being
added here — anything touching a frozen contract is ADR-gated; anything
needing a new external data source is DD-gated. Nothing on this list is
implemented silently past those gates.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **M-X0** Decision Journal & Outcome capture | Wire the already-modeled `DecisionJournalEntry`/`TradeOutcome` (frozen domain, existing repository methods) to a real owner action: Accept/Reject/Ignore on the Decision Brief, realized-outcome logging with server-computed pnl/holding-time/TradePlan-adherence. Closes the gap where `save_journal_entry` was called nowhere in the codebase and M10.4 AI Playbook Diagnostics ran against an always-empty journal. Prerequisite for M-X1/M-X10. | None — existing frozen domain objects + repository methods, just unconnected | ✅ Approved |
| **M-X1** Historical analog matcher | Deterministic nearest-neighbor retrieval of past decisions with a similar score/confidence/risk fingerprint + their logged outcomes, surfaced in the Decision Brief | None — read-only query over existing persisted Decision Journal | ✅ Approved |
| **M-X2** "Why not" counterfactual | Quantify exact score/confidence gap between a WATCH and the TRADE gate | None | ✅ Approved |
| **M-X3** Confidence-decay clock | Persisted, deterministic decay indicator for TradePlan staleness through the session | None | ✅ Approved |
| **M-X4** Circuit-limit / price-band risk signal | New Risk Engine dimension from Kite's already-fetched, currently-discarded circuit-limit fields | **ADR-006 (Proposed)** — extends frozen `Quote` domain object | ⏸ Blocked on ADR approval |
| **M-X5** Opening Range Breakout playbook | First-15/30-min range break/hold as a deterministic strategy-framework pattern | None | ⏳ Planned |
| **M-X6** VWAP deviation scoring dimension | Intraday VWAP reclaim/deviation as a new scoring input | None | ⏳ Planned |
| **M-X7** Multi-timeframe confluence | 1m/5m/15m agreement as a scoring/confidence dimension | None | ⏳ Planned |
| **M-X8** Synthetic canary decision | Fixed synthetic instrument through the full pipeline each cycle to catch silent engine regressions | None | ⏳ Planned |
| **M-X9** Config-change impact preview | Deterministic replay-based diff of a scoring-weight change against recent decisions, before it goes live | None | ⏳ Planned |
| **M-X10** Outcome-tagged setups + signal drift monitor | Extends M10.4 AI Playbook Diagnostics with per-pattern hit-rate tagging and weight-drift alerts | None | ⏳ Planned |

**Explicitly not started — owner decision required, not an AI call:**

| Item | Why it's gated | Revisit point |
|---|---|---|
| ASM/GSM surveillance-stage awareness | New NSE data source; no existing DD covers it | Needs a new DD (owner decision on vendor/method) before any code |
| Delivery % (NSE daily delivery data) | New NSE data source | Needs a new DD |
| Bulk/block deal feed | New NSE data source | Needs a new DD |
| Options data + F&O ban-list feed | **DD-4** already exists in ATHENA-002 §15, deferred to "Phase 7" — Phase 7 is now approved, so DD-4 is revisit-eligible | Owner decision: open DD-4 now or keep deferred |

---

### ATHENA UX Overhaul track closed (2026-07-26): all 9 milestones (UX-1 through UX-9b) approved

Owner-authored 40-point UX/UI audit: transform ATHENA from an "engineering
dashboard" into a professional decision workstation (Bloomberg/TradingView/
Linear/Stripe-grade). Current: 8.2/10 across visual quality, engineering
quality, information architecture, decision UX, product polish. Target:
9.8+/10. Grouped into themed milestones (AI-proposed grouping of the 40
points, owner-confirmed order pending). One explicit exclusion: the
"Place Order" quick action (owner confirmed 2026-07-26 — not required,
conflicts with ATHENA's absolute no-order-placement prohibition anyway).
Two milestones need a small, additive backend piece (no ADR, no domain
change) rather than pure frontend re-skinning — flagged per-row below.

| Milestone | Scope | Backend touch | Status |
|---|---|---|---|
| **UX-1** Hero Decision Card + Executive Summary + Decision Banner | Sticky cockpit becomes an "executive briefing": symbol/stance/score/confidence/risk/R:R at a glance, a 5-line plain-English summary composed from already-persisted engine explanations (never generated), and a one-line recommendation banner. Holding-period and strategy-name fields from the owner's example dropped — confirmed neither exists prospectively anywhere in the backend (research: 2026-07-26) | None | ✅ Approved |
| **UX-2** Score/Confidence/Risk storytelling | Meaning over decimals: risk/score bands (Weak→Excellent), star-rated score contributors, confidence "why ATHENA trusts this" checklist, risk as categorized summary, safety gates as a reassuring checklist, a "Why?" contribution breakdown | None | ✅ Approved |
| **UX-3a** Trade Plan visual redesign | Bigger, cleaner entry/stop/target/R:R presentation; new Expected Return % computed from the plan's own persisted entry/target values | None | ✅ Approved |
| **UX-3b** Chart ATR/moving-average/volume overlay | Chart gains an ATR envelope band, a moving-average line, and a volume bar subplot, all sourced from new `atr`/`moving_average` fields on `CandleDTO` | None (additive DTO fields, additive `atr_series`/`sma_series` functions — existing `atr()`/`sma()` now delegate to them, byte-identical output, verified by the pre-existing indicator test suite) | ✅ Approved |
| **UX-4** Tab renaming + progressive disclosure + Market Context cards | Setup→Trade Plan, Context→Market Context, Response→Decision History (internal `data-brief-tab` keys unchanged); Analysis component breakdown behind a "View detailed breakdown" toggle; regime/market-health render as labeled metric cards instead of a flat chip row | None | ✅ Approved |
| **UX-5** Reasoning Trace redesign | Animated dash-flow connector lines (respects `prefers-reduced-motion`); each stage shows its own real computed state (e.g. Bullish, BUY, Authorized) once that stage's data has loaded, falling back to the generic lifecycle badge when no mapping applies — never fabricated. Per-stage completion/data-quality percentage deferred: only score/confidence/risk persist a `completeness` field, and it's already shown in their existing detail cards; there is no equivalent field for regime/market-health/decision/trade-plan/evidence stages to draw from without inventing one | None | ✅ Approved |
| **UX-6** Sidebar summary + Historical Validation + Decision Timeline narrative + Decision History polish | Sticky right-rail quick summary (symbol/stance/score/confidence/risk pinned to the top of the Reasoning Trace panel); Historical Validation block (win-rate/avg-return/avg-holding aggregate across analog matches — new `DecisionAnalogsDTO` fields, exact arithmetic over each analog's realized `TradeOutcome`); Decision Timeline now narrates a factual stance/score delta per entry instead of a bare timestamp; Decision History shows a friendly "call paid off/didn't pay off" accuracy label wrapping the same real pnl sign | Added `outcome_return_pct`/`outcome_holding_days` to `DecisionAnalogDTO` and `win_rate_pct`/`avg_return_pct`/`avg_holding_days`/`outcomes_sample_size` to `DecisionAnalogsDTO`, computed in `decisions_service.get_decision_analogs` from the `TradeOutcome` already fetched per analog — additive, no schema break | ✅ Approved |
| **UX-7** Typography, spacing, elevation, color-language, micro-animations, accessibility + CSS codebase refactor | Owner requested full design-token normalization plus a proper split of the single 4,903-line `dashboard.css` (was flagged as an unmaintainable monolith). Delivered: (1) lossless split into 14 `css/*.css` files by concern, loaded via an `@import` manifest, verified byte-identical to the original before any value changed; (2) ~85 new design tokens (spacing/typography/elevation/color scales) added by naming every distinct value already in use — zero visual drift, verified by resolving every token back to its literal and diffing against the pre-refactor file (688 changed lines, 0 real mismatches, 2 intentional/verified-equivalent px→rem conversions); (3) accessibility fixes: global `:focus-visible` ring (previously only 5 hand-picked inputs had any focus style), dashboard-wide `prefers-reduced-motion: reduce` coverage (previously only 1 of 4 animations was gated), `aria-label` on 3 icon-only header buttons, `aria-hidden` on the decorative DAG connector SVG, keyboard-operable "Today's Decisions" cards (tabindex/role/keydown, previously click-only) | None (pure frontend refactor + additive tokens; no backend/API change) | ✅ Approved |
| **UX-8** Copy pass | Replaced raw ALL_CAPS enum leakage (TRADE/WATCH/NO_TRADE/INSUFFICIENT_DATA, INCLUDED/EXCLUDED/UNKNOWN) with friendly labels; rewrote dense engineering paragraphs ("persisted"/"config thresholds"/"ingestion"/"generated rationale", the internal "AI Playbook Diagnostics" module name, "deterministic nearest-neighbor...fingerprint") in plain English; fixed several unhelpful empty-state messages; added the market-health explanation sentence (real, already-persisted field) for parity with the regime block, which already had one; renamed hero "Composite score" → "Score" to match the app's own established convention. CLI-command/HTTP-status operational messages were deliberately left as-is — this is a single owner-operator who runs those commands directly, not jargon leaking to a separate non-technical audience | None | ✅ Approved |
| **UX-9** Quick actions + Portfolio Context + export/deep-link/share | Scope resolved with owner: Compare = symbol-vs-symbol side-by-side; Open Chart = enlarge in a modal; deep-link/share deferred to a future enhancement (no existing infra, out of scope here). Split into two reviewable parts | Deep-link/share deferred (documented as future enhancement); Add Watchlist needs a new small backend domain (UX-9b) | ✅ Approved (2026-07-26) — both UX-9a and UX-9b approved |
| **UX-9a** Open Chart / Compare / News / Portfolio Impact | Pure frontend, built entirely on existing endpoints (`?instrument_id=`, `/depth`, `/portfolio`, `/market/instruments/{id}/candles`) — no new backend routes. Open Chart reuses the existing chart renderer in a modal; Compare fetches a second symbol's latest decision + depth and renders side-by-side; Portfolio Impact aggregates open positions for the instrument and computes gain % against the latest real close | None | ✅ Approved (2026-07-26) |
| **UX-9b** Add Watchlist (Saved Symbols) | New minimal owner-curated "Saved Symbols" domain, deliberately independent of two unrelated concepts: the `owner_candidates` pipeline-input validation list (Market Intelligence "Stock List" — saving a symbol here has no ingest/scoring effect) and the automated M4.3 `watchlist` package (config-driven, no owner input at all). New Market Intelligence card: add/list/remove | New `saved_symbols` SQLite table (schema v8) + `SavedSymbolsService` + `GET/POST/DELETE /api/v1/saved-symbols` (mirrors the `owner_candidates` CRUD shape exactly — closer analog than M-X0) | ✅ Approved (2026-07-26) |

---

### Data-integrity fix: REFRESH run_id collision (owner-reported, 2026-07-26)

Not a UX item — a backend correctness bug, tracked separately per owner
instruction. Owner reported Score/Confidence/Risk showing "Unknown"/0.0
for a decision selected from a carousel, fixed only by re-validating it —
and the same happening to whichever OTHER decision had been re-validated
most recently. Root-caused via direct SQLite inspection (`db/athena.db`):
DIXON, TCS, and HFCL's decisions from the same day all shared run_id
`run-refresh-20260724T153000`, but that run's `detail_json.pipeline.
decision_reports` contained an entry for only one of the three.

| | |
|---|---|
| Root cause | `_default_run_id(trigger, as_of)` (`src/athena/scheduling/dry_run.py`) derives the run_id purely from `(trigger, as_of)`. Outside live trading hours, `resolve_validate_as_of` always resolves to the same fixed session-close timestamp, so every ad-hoc "Re-validate" (`RunTrigger.REFRESH`) call on the same day computed the *identical* run_id. `SqliteRepository.save_run`'s upsert (`ON CONFLICT(run_id) DO UPDATE SET ... detail_json=excluded.detail_json`) then silently overwrote the previous call's `decision_reports` with the new call's — orphaning the earlier decisions from their own analysis, which is why they rendered "Unknown" until re-validated again (which just moved the same bug onto whichever symbol was validated *before* it) |
| Fix (part 1) | Append a `uuid4` disambiguator to the run_id for `RunTrigger.REFRESH` only (`run-refresh-{stamp}-{8 hex chars}`), so every ad-hoc validation gets a genuinely unique run_id regardless of `as_of` collapsing to the same value. `PREMARKET`/`CLOSING` are untouched — those are scheduled, at-most-once-per-day cycles where a stable id may be relied on for idempotent retries of the same logical run |
| **Correction (same day)** | Part 1 alone was **incomplete** — confirmed by the owner still seeing "Unknown" values after a successful re-validate. Direct SQLite inspection showed the `runs` table row *did* get a correctly-unique id (part 1 worked for that), but the actual `Decision` row saved to the `decisions` table still pointed at the old, colliding, non-unique id. Root cause: `OwnerValidationPipeline.run()` (`src/athena/ops/owner_validation.py`) independently **recomputed its own local `run_id`** from `(trigger, as_of)` — using the exact same old, collision-prone formula — completely disconnected from the orchestrator's now-fixed, actually-unique run_id. `DryRunPipeline.run()`'s Protocol never had a way to receive the real run_id at all |
| Fix (part 2) | `DryRunPipeline` Protocol and `DryRunCycleOrchestrator.run_cycle()` now thread the orchestrator's own real `run_id` through to `OwnerValidationPipeline.run(..., run_id=run_id)`, which uses it directly instead of recomputing one locally. Every `Decision` saved now correctly points at the exact run whose `detail_json` holds its own analysis — no more silent divergence between "the run record's identity" and "the identity the decision was tagged with" |
| Scope | `src/athena/scheduling/dry_run.py` (`_default_run_id`, `DryRunPipeline` Protocol, `run_cycle`), `src/athena/ops/owner_validation.py` (`run()` signature); no API/DTO/schema change |
| Tests | 2 regression tests in `tests/runtime/test_dry_run_schedule.py` (part 1) + 1 new regression test in `tests/ops/test_owner_validation.py` (`test_repeat_validate_with_same_as_of_does_not_orphan_earlier_decision`, part 2 — validates two different symbols back-to-back with the same `as_of` and asserts each decision keeps its own distinct run_id) + an existing test extended to assert the saved decision's `run_id` matches what was passed in. Full suite **1023 passed** |
| Note | Existing decisions already orphaned by a past collision (this session's TCS/HFCL, and any created between the part-1-only fix and this correction) are not retroactively repaired — see the "Clear all" feature below for a clean-slate path instead |
| Status | ✅ Fixed (both parts), tested, server restarted — awaiting owner confirmation on the live dashboard |

---

### Feature: "Clear all" for Decisions & Trace (owner-requested, 2026-07-26)

Not a UX item — an owner-requested admin utility, tracked separately.
Lets the owner wipe the Decisions & Trace domain and start fresh (e.g.
after the run_id collision above orphaned some test decisions) instead
of re-validating each affected symbol individually. Built as a close
mirror of the existing "Reset fills" (Portfolio) feature — same
CONFIRM-token gate, same automatic pre-delete backup pattern.

| | |
|---|---|
| Scope | Deletes all rows in `decisions`, `decision_traces`, `decision_journal`, `trade_outcomes`. Does **not** touch `runs` (shared with Market Intelligence's universe/regime history), portfolio positions, or owner candidates |
| Backend | `SqliteRepository.delete_decisions_data()`; `DecisionsService.reset_decisions()` (CONFIRM-gated, auto-backup via the same `create_backup` helper Portfolio reset uses, saved as `db/backups/athena-pre-decisions-reset-<timestamp>.db`); `POST /api/v1/decisions/reset` (ADMIN-only) |
| Frontend | "Clear all" button in the Decisions & Trace toolbar → a confirmation modal with a "type CONFIRM to unlock" gate (same UX pattern as Portfolio's reset gate) → "Delete everything" button, disabled until the token matches exactly |
| Tests | 2 new backend tests (confirmation + admin-role gating refuses before touching data; a real clear deletes and a subsequent list is empty) + 6 new dashboard-hosting assertions. Full suite **1022 passed** |
| Status | ✅ Built, tested, server restarted — awaiting owner confirmation on the live dashboard |

### Feature: blocking validate overlay for Decisions & Trace / Market Intelligence (owner-requested, 2026-07-26)

Not a UX item — a correctness/UX fix tracked separately. Owner reported
being able to click other UI mid "Re-validate"/"Validate"/"Add & validate",
risking acting on stale state. Adds a full-viewport, non-dismissible,
ATHENA-branded overlay for the duration of any validate call.

| | |
|---|---|
| Scope | Frontend only — `#validate-overlay` markup + CSS + `showValidateOverlay`/`hideValidateOverlay` centralized inside the shared `validateSymbolsNow`, so all 4 existing call sites (Portfolio row, Market Intelligence row, "Add & validate", Decision Brief "Re-validate") get it automatically |
| Tests | 15 new dashboard-hosting assertions. Full suite **1024 passed** |
| Status | 🔄 Built, tested, visually verified via browser DOM inspection (no owner credentials to trigger a real authenticated validate) — awaiting owner confirmation on the live dashboard |

### Refactor: dashboard.js concern-based split (owner-requested, 2026-07-26)

Not a UX item — a maintainability refactor tracked separately, mirroring
UX-7's `dashboard.css` split. Owner flagged `dashboard.js` at 6,108 lines in
one file. Unlike CSS, the whole file lived inside one
`document.addEventListener("DOMContentLoaded", () => { ... })` closure with
real cross-section coupling (shared mutable state, a 3-way cycle between the
DAG/analysis/context renderers, an auth/api-client cycle) — real ES modules
would have required behavioral code changes at those points with no way to
verify equivalence by diff. Owner chose the lower-risk option instead: split
the source into 22 concern-based files under `static/js/`, reassembled
server-side (new `/dashboard/dashboard.js` route, registered ahead of the
`StaticFiles` mount) into the exact original single-closure script.

| | |
|---|---|
| Scope | `src/athena/api/static/js/00-state-and-dom.js` through `21-bootstrap.js` (+ `_header.js`/`_footer.js` carrying the exact original wrapper boilerplate) — no manual retyping anywhere; every file was mechanically sliced from the original using an Acorn-parsed statement inventory (Node 26 + acorn, installed for this refactor only, not a runtime/build dependency). `src/athena/api/app.py` gains `DASHBOARD_JS_PARTS`/`assemble_dashboard_js()` and a route serving `/dashboard/dashboard.js` by concatenating them in order, read fresh per request (no restart needed to see an edit, same as before) |
| Verification | A standalone Node script parsed the original file into its 372 top-level statements, verified 100% coverage (no gap/duplicate) across the 22-file partition, then re-parsed the reassembled output and did a **content-equality check per statement**: every one of the 372 original statements' exact source text was confirmed present, unaltered, at its new (relocated) position — plus a non-whitespace character-count match end to end. The live server's actual `/dashboard/dashboard.js` response was then diffed against that verified reference: **byte-identical**. Full regression **1031 passed** (new: `test_dashboard_js_assembled_losslessly_from_concern_split`, which re-derives the expected assembly from the real files on every test run — never a frozen snapshot). Live browser check: zero console errors on load; all 5 tabs exercised via real click-wired handlers (not synthetic DOM pokes) with only the expected, pre-existing unauthenticated-API-call error logging (since no owner credentials were available to authenticate), no ReferenceError/TypeError/SyntaxError anywhere |
| Status | ✅ Built, verified, live-tested — old monolithic `dashboard.js` deleted (fully superseded) |

### Fix pass: stale Reasoning Trace sidebar + tab restored on login (owner screenshot, 2026-07-27)

Two bugs the owner found via live screenshots.

| | |
|---|---|
| Bug 1 | After "Clear all" (Decisions & Trace), the main brief correctly went empty but the Reasoning Trace sidebar kept showing the previously selected symbol's quick-summary chips (score/confidence/risk) and DAG stage-detail card ("Regime / COMPLETED / regime-NIFTY 50-..."). Root cause: `renderSidebarQuickSummary()` already correctly hides itself when there's no active decision, but nothing re-invoked it after Clear all nulled the decision state, and the DAG stage-detail panel had no reset path at all. Fix: `renderDecisionBriefEmpty()` — the one function whose job is "there is no decision to show" — now authoritatively nulls `activeDecisionData`/`selectedStageId`, re-invokes `renderSidebarQuickSummary()`, and hides the DAG details panel, so every caller (Clear all, zero-filter-results, a failed decision-detail fetch) is covered, not just the one path the owner happened to hit |
| Bug 2 | Login sometimes reopened whatever tab was active before instead of always landing on Portfolio Overview. Root cause: `initializeRoute()` read `window.location.pathname` to pick a tab — if the browser's address bar still pointed at e.g. `/dashboard/decisions` (left over from a prior session), login honored that stale URL. Fix: `initializeRoute()` now always resets to `/dashboard/overview` and switches to Overview, mirroring the reset the logout handler already did |
| Tests | 4 new dashboard-hosting assertions. Full suite **1031 passed** |
| Status | ✅ Built, verified via code-level correctness (both fixes are small, unconditional, no branching) + a live check confirming `history.replaceState` behaves as expected in-browser. Could not drive a real authenticated login/Clear-all end-to-end myself (this deployment requires real owner credentials) — awaiting owner confirmation on the live dashboard |

### ATHENA Workstation Refactor (owner assignment + reference mock, 2026-07-27)

Presentation-layer-only refactor of Decisions & Trace to match a reference
"professional trading workstation" mock — reposition existing information,
never invent new. No backend/business-logic/scoring/reasoning changes in
any of DT-1 through DT-4. Split into 4 reviewable milestones per the
milestone-workflow discipline; one in flight at a time.

Owner-confirmed scope decisions (before DT-1 started):
- Tabs split into 5 (Trade Plan / Analysis / Market Context / Response /
  History) rather than keeping today's 4 — Response = Journal/Outcome only,
  History = Timeline (moved from the always-visible hero) + Analogs (DT-3).
- Market ticker strip (NIFTY/BankNifty/VIX/breadth) approved as a header
  addition, with a strict data-source priority: reuse ATHENA's existing
  Kite/Regime/Market-Health pipeline data first; a genuinely new external
  feed is only a last resort requiring its own stop-and-propose gate (DT-2).
- "Similar Trades" mini sparkline approved — reuses each analog's
  already-fetched `outcome_return_pct` (DT-4).
- Two nav placeholders ("Reports & Analytics", "Settings") added as visibly
  disabled, no backing route — explicitly future-implementation (DT-1).

| Milestone | Scope | Status |
|---|---|---|
| **DT-1** Layout shell — 3-pane workstation | Replaced the horizontal outcome carousels + toolbar-above-the-fold layout with a permanent left Symbols panel (search always visible, collapsible BUY/WATCH/PASS-equivalent groups, strong selected-row highlight) beside the center detail (now immediately visible, zero scroll) and the existing right Reasoning Trace (untouched — its redesign is DT-4). Same data/selection/filter/sort/dismiss logic throughout — only the DOM position and row/group markup shape changed | ✅ Approved |
| **DT-2** Hero header + Quick Summary + ticker strip | Rearrange the hero header hierarchy; build a "Quick Summary" card from existing gauges/Trade-Plan/Historical-Analogs data only; add the market ticker strip per the data-source priority above | ⏳ Planned |
| **DT-3** Tab restructuring (5 tabs) + spacing polish | Split "Decision History" into Response (Journal/Outcome) + History (Timeline + Analogs); whitespace/hierarchy polish across Trade Plan/Analysis/Market Context — no content changes | ⏳ Planned |
| **DT-4** Reasoning Trace redesign + Similar Trades sparkline | Replace the auto-fit-grid + SVG-connector DAG with a cleaner vertical pipeline list (real existing stage status only, never fabricated counts/funnels — confirmed no such data exists anywhere in ATHENA); same click/detail-panel behavior, same stage order; add the last-5-trades sparkline to Analogs | ⏳ Planned |

#### DT-1 — Layout shell: 3-pane workstation

| | |
|---|---|
| Scope | `index.html`: new `.decisions-workstation` (3-column grid) replacing `.trace-workstation` (2-column); new `.symbols-panel` (search + icon-triggered filter/sort/clear-all popover + summary strip + collapsible outcome groups), replacing the old toolbar card + `#decisions-carousel-groups` carousel container. `12-decisions-list.js`: `renderDecisionCarousels` rewritten to build vertical rows instead of a horizontal scroll-snap track (nav-arrow buttons and `wireCarouselOverflow` removed as dead code); `renderDeckCard` renamed `renderSymbolRow`; left-panel scroll position preserved across re-renders. `13-decision-brief-core.js`'s `selectBriefing`: resets only the center panel's scroll to top on a new selection, leaves left/right panels untouched. `09-decision-brief-shell.css`/`12-decision-cards-dag.css`: new grid + row/group styling, strong selected-state (accent wash, left indicator, glow, bolder symbol text). Two disabled nav placeholders added to the global sidebar |
| Tests | 2 new dashboard-hosting assertions sets (structural markup/CSS/JS presence + a real div-nesting-depth check for the filter popover, which caught a real bug — see below). Full suite **1031 passed** |
| Coverage | Live-browser verified: 3-pane layout renders correctly with zero scroll to reach the detail panel; injected sample decision data to confirm row/group rendering, selected-row highlight, and collapse-toggle all match the reference mock; verified the responsive single-column collapse below 1400px; confirmed zero console errors (only the expected, pre-existing unauthenticated-API-call logging, since no owner credentials were available) |
| Status | ✅ Built, tested, live-verified |

**Bug caught and fixed during live verification**: the filter popover initially rendered off-screen, anchored to the wrong ancestor — it was a DOM *sibling* of `.symbols-panel-header` rather than a *child*, so its `position: absolute` resolved against an unrelated ancestor instead of the header. Fixed by nesting it inside the header in the HTML; added a test that checks actual div-nesting depth between the two elements (not just that both class names exist somewhere in the page), so this exact regression can't silently reappear.

**Fix pass (owner live screenshots, 2026-07-27)** — four refinements to the filter popover, found once the owner tried it on real data:
1. Excessive vertical gaps between Stance/Type/Sort: each `<label class="decisions-filter-label">` was inheriting `flex: 1 1 100px` from an unrelated shared rule written for the old horizontal toolbar (`05-portfolio.css`), which stretched each label to fill the popover's height inside this new vertical flex layout. Pinned to `flex: none`.
2. "Clear all" moved out of the popover entirely into its own separate, danger-styled icon button — sitting inside a view-only filter panel, it read as "clear the filters" rather than "wipe my decisions."
3. Added an explicit "Reset" (view only — stance/type/sort back to defaults, distinct from "Clear all" which deletes data) and a close (×) button — the filter icon toggle was previously the only way to dismiss the popover, which the owner flagged as undiscoverable. Reset also dismisses the popover afterward (owner follow-up).
4. Added a backdrop behind the popover, scoped to the list area only (the header stays outside it and interactive) — previously the symbol list stayed fully visible *and clickable* underneath the open popover, with no visual differentiation. Verified via `elementFromPoint` in a live browser that the backdrop itself, not the list, receives clicks in that region.

11 new dashboard-hosting assertions. Full suite **1031 passed**.

---

*Status legend: a milestone is "In Progress" (🔄) when actively being designed or built, "Approved" (✅) only when the owner signs off. Never two milestones in flight.*
