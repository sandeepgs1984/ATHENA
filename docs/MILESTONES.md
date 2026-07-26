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

### ATHENA UX Overhaul (owner audit, 2026-07-26)

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
| **UX-8** Copy pass | Replace engineering vocabulary (persisted/provenance/fingerprint/etc.) throughout; better empty states; "ATHENA explains" narrative blocks | None | ⏳ Planned |
| **UX-9** Quick actions + Portfolio Context + export/deep-link/share | Open Chart/Compare/News(→existing curated links)/Add Watchlist/Portfolio Impact quick actions (Place Order excluded); "you own N shares, avg price, gain %"; deep-link + share | Portfolio-position lookup by instrument — small, additive; "Compare"/"Portfolio Impact" need a precise scope definition first | ⏳ Planned |

---

*Status legend: a milestone is "In Progress" (🔄) when actively being designed or built, "Approved" (✅) only when the owner signs off. Never two milestones in flight.*
