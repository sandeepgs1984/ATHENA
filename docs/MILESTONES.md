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

### Symbol Chart Excellence track (owner direction, 2026-07-29)

World-class symbol chart presentation for the Decision Brief, governed by
`docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md`. This track improves chart
inspection quality only; it does not change ATHENA scoring, create orders,
invent signals, or add broker write behavior. ADR-004 already permits static
HTML/vanilla JS/Lightweight Charts on this surface, and ADR-005 governs every
overlay as data.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **CH-0** Design & architecture gate | Current chart audit, target experience, staged roadmap, no-fabrication/no-order-placement boundaries | Owner approval of roadmap and chart-library dependency approach | ✅ Approved (2026-07-29) |
| **CH-1** Professional chart foundation | Reusable professional chart controller over the existing candles endpoint; candles, volume, SMA, responsive normal/modal views, latest-price marker, aligned asset cache-busters | None — implemented with local static JS/CSS, no new dependency | ✅ Approved (2026-07-29) |
| **CH-2** TradePlan overlays & validity layer | Entry band, stop/target price lines with percentage deltas, risk/reward chip, and expiry/freshness affordance from existing plan data | None | ✅ Approved (2026-07-29) |
| **CH-3** Timeframe, range, and session controls | Configured 5m/15m timeframe controls in embedded/modal charts, local chart preference, session separators, requested-vs-returned bar counts, timeframe-specific no-data wording, visible last-candle timestamp | None | ✅ Approved (2026-07-29) |
| **CH-4** Interactive inspection | Crosshair OHLCV legend, rendered indicator readouts, plan-level readouts, reset affordance, keyboard focus/accessibility pass, enlarged dedicated chart modal | None | ✅ Approved (2026-07-29) |
| **CH-5** Decision & event markers | Persisted decision/journal/outcome markers on the chart; revalidation markers deferred until a persisted timestamp is exposed | Additive read-only endpoint only if existing payloads are insufficient; ADR required for frozen contract/domain expansion | ✅ Approved (2026-07-29) |
| **CH-6** Resilience, visual QA, and release gate | Release-gate regression tests for nonblank rendering, no-data/fallback states, interaction wiring, modal no-scroll layout, persisted-only markers, and max-limit budget contracts | Owner review after QA evidence | 🔄 Ready for review |

**Implementation rule:** CH-0 must be owner-approved before CH-1 starts; after
that, exactly one chart milestone is implemented and reviewed at a time.

---

### Advisor Status Layer track (owner direction, 2026-07-29)

Moves Decisions & Trace from an engineering-console feel toward an intraday
advisor surface. Presentation-only: consumes existing ticker/session/telemetry,
selected-decision, and TradePlan freshness data; does not change scoring,
risk, decision policy, providers, frozen domain contracts, or order behavior.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **AS-0** Advisor status plan | Audit screenshot, define actionability states, diagnostics boundary, pulse-strip content, staged rollout | Owner approval | ✅ Approved (2026-07-29) |
| **AS-1** Header pulse + actionability foundation | Replace always-visible REQ/CORR/LATENCY with advisor pulse + diagnostics popover; add selected-symbol actionability banner that can override a green BUY-looking setup when market/plan state makes it non-actionable | None — frontend presentation over existing data only | ✅ Approved (2026-07-30) |
| **AS-2** Freshness propagation | Add plan/actionability state to Quick Summary and the symbol list so expired/stale plans are visible before opening each brief | None — reuse selected/list payloads and plan freshness where available; no fabricated timestamps | ✅ Approved (2026-07-30) |
| **AS-3** Market closed review mode | Surface market-closed/next-session messaging and review-mode wording across header and detail pane once existing calendar/session data is exposed to the dashboard | Additive read-only API only if existing payloads are insufficient | ⚠️ Implemented; full-suite blocked by local disk capacity |
| **AS-4** Release gate | Regression tests for diagnostics privacy, actionability overrides, reduced-motion pulse behavior, and expired-plan visual dominance | Owner review after QA evidence | ✅ Approved (2026-07-30) |

**Implementation rule:** one AS milestone at a time. AS must never create
trading signals, alter ATHENA's recommendation, or imply order execution.

#### AS-1 — header pulse + actionability foundation (approved, 2026-07-30)

Scope completed: the primary header now uses an advisor pulse strip for
market/Kite/selected-plan messages, while exact `REQ-ID`/`CORR-ID`/latency
remain available in a diagnostics popover. Selected TradePlans now render an
Advisor Status banner in the Decision Brief header. If the plan is expired or
stale, the banner and pulse explicitly say the setup is not actionable /
requires re-validation before any manual action, without changing the
underlying ATHENA recommendation. Reduced-motion users get a static truncated
pulse message instead of scrolling text.

Owner screenshot review fix pass: the AS-1 header pulse was tightened to avoid
duplicating the market ticker, the diagnostics popover was compacted, and the
expired-plan banner was restyled with shorter action-first wording so the
advisor warning does not read like loose body copy.

Deferred deliberately at AS-1 close: propagating plan freshness into every
left symbol row and adding it to Quick Summary moved to AS-2; showing a real
market-closed / next live-session date remains AS-3. AS-1 does not fabricate a
next session from browser time; that must come from ATHENA's calendar/session
authority.

#### AS-2 — freshness propagation (approved, 2026-07-30)

Scope completed: the Decisions symbol list now shows a compact TradePlan
freshness chip per row (`Valid`, `Aging`, `Stale`, `Expired`, or `No plan`)
before opening the brief. Quick Summary now includes a `Plan Status` row using
the same freshness wording. The selected brief first infers status from the
persisted TradePlan validity window, then refreshes Quick Summary with the
authoritative `/plan-freshness` DTO after it loads.

Architectural note: AS-2 is frontend presentation only. It does not alter
decision type, score, confidence, risk, TradePlan values, providers, schemas,
or broker behavior. List-row freshness uses only persisted `valid_from` /
`valid_until` and the same configured freshness fractions as the backend
service (`0.5` warn, `0.8` stale); the selected brief remains authoritative via
the existing API DTO.

#### AS-3 — market closed review mode (implemented; validation blocked, 2026-07-30)

Scope completed: the dashboard now exposes a read-only
`/api/v1/dashboard/session-status` endpoint that computes live/review-mode
exchange status from `CalendarEngine` and configured NSE session times. The
header advisor pulse now shows server-provided market closed / next-live
wording outside live hours. The selected Decision Brief Advisor Status banner
switches valid plans into review mode when the market is closed, while expired
and stale plan warnings remain stronger and continue to require re-validation.

Architectural note: AS-3 adds only a read-only dashboard DTO/endpoint and
presentation wiring. It does not change scoring, risk, decision policy,
TradePlan values, provider behavior, schemas used by analytical engines, or
broker behavior. The next-live date is computed by the backend from ATHENA's
calendar/session authority; the frontend never fabricates market dates.

Validation note: focused API/dashboard checks pass, but the full suite is
blocked on this machine because the filesystem is effectively full
(`db/` is ~9.8 GiB; only ~115 MiB free), causing unrelated SQLite `disk I/O
error` failures in repository tests and live-repo-backed shape tests.

#### AS-4 — advisor status release gate (approved, 2026-07-30)

Scope completed: added a dedicated Advisor Status release-gate regression test
for diagnostics privacy, reduced-motion pulse behavior, actionability
dominance, and expired-plan visual dominance. The gate locks in that REQ-ID /
CORR-ID / latency remain hidden behind the diagnostics popover; reduced-motion
users receive a static ellipsis pulse; expired/stale TradePlans outrank
market-closed review mode and green "plan valid" wording; and historical
expired TRADE records stay out of the current Decisions board rather than
becoming restorable dismissals.

Owner live-review fix pass: scoped revalidation that excludes a symbol now
surfaces a no-current-TradePlan warning instead of silently falling back to an
old decision; expired historical TradePlans are labeled as historical/not
actionable in the cockpit, Quick Summary, eligibility section, and TradePlan
card. The original persisted decision remains available for audit/replay, but
the left rail is now a current action board only.

Architectural note: AS-4 is presentation/test hardening only. It does not
change ATHENA's scoring, confidence, risk, decision policy, TradePlan values,
providers, schemas, frozen domain contracts, or broker behavior.

Validation note: focused dashboard checks pass (`tests/api/platform/
test_dashboard_hosting.py`), but the full suite remains blocked locally by
critically low disk space (hundreds of MiB free on a repository with a ~9.8 GiB
live `db/`).

**Advisor Status Layer track closed (2026-07-30):** owner approved AS-4. The
Decisions & Trace advisor surface now has release-gated diagnostics privacy,
market/revalidation actionability wording, expired-plan dominance, and a
current-action-board contract for the left rail.

---

### Intraday Advisor UX track (owner direction, 2026-07-30)

Turns ATHENA's intraday recommendation surface into an explicit manual trading
workflow. Presentation-only unless a later milestone states an additive
read-only API need. This track does not change scoring, risk, decision policy,
TradePlan values, providers, frozen domain contracts, or broker behavior.
Governing plan: `docs/design/ATHENA-INTRADAY-ADVISOR-UX-ROADMAP.md`.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **TP-1** Trade Playbook foundation | Move symbol revalidation into Advisor Status; add selected-symbol Trading Steps with entry/stop/target/no-fill/expiry/close/revalidation rules | Owner review after UX/test evidence | 🔄 Ready for review |
| **TP-2** Current Board controls | Add Re-validate Visible for current-board symbols with progress/result summary | Owner review; must not validate hidden historical rows | 🔄 Ready for review |
| **TP-3** Top Current Setups | Add top 10 current valid/aging setups sorted by existing score/confidence/risk/return data | Owner review; no expired/stale/no-plan rows | 🔄 Ready for review |
| **TP-4** Intraday SOP surface | Add persistent intraday SOP/help surface for day workflow and manual execution boundaries | Owner review | ✅ Approved |

**Implementation rule:** one TP milestone at a time. TP must never create order
placement, broker write actions, new signals, or changes to ATHENA's analytical
engines.

#### TP-1 — trade playbook foundation (ready for review, 2026-07-30)

Scope completed: symbol-specific `Re-validate` moved from the generic
Decision Brief header into Advisor Status, where the stale/expired/review-mode
reason is visible next to the corrective action. The setup tab now includes a
Trading Steps panel before TradePlan levels, covering entry, stop, target,
no-fill, end-of-day, and re-check rules. The panel adapts wording for current
plans, market-closed review mode, and expired historical plans without
changing ATHENA's underlying recommendation or persisted TradePlan values.
Owner-review usability pass initially added a scroll-aware compact cockpit, but
AW-4 replaced that with a steadier detail shell: only the selected
symbol/current-price row stays fixed, while metadata, gauges, Advisor Status,
tabs, and active tab content scroll together. This avoids scroll flicker on
short tabs such as Market Context.

Architectural note: TP-1 is presentation-only over existing Decision,
TradePlan, freshness, quote/session, and validation state. It does not add
orders, broker write actions, new signals, scoring/risk/decision changes, or
domain/API contract changes.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

Owner screenshot fix: the main card summary was reduced from three cramped
mini-cards to a single compact status strip; blocker text on the card now uses a
short plain label while preserving exact rule evidence inside the modal; the
workbench modal explicitly overrides the shared 600px modal cap, resets to
Overview, and scrolls to the top every time View Details opens.

Second owner screenshot fix: Qualified Today rows no longer render duplicate
decision chips (`TRADE TRADE`). Each row now shows one decision chip plus Open
decision and Save/Saved actions, using the existing deterministic Decisions
selection flow and Saved Symbols service.

Third owner screenshot fix: the next-action summary now spans the full
Validation Pipeline card width and wraps normally, avoiding the clipped
`Review 177 current T...` state.

Fourth owner fix: Open decision now clears Decisions filters, uses a strict
symbol-selection load, and refuses to silently fall back to another symbol.
Validation reports disable Open decision when the latest validation outcome has
no current decision row to open, including Excluded outcomes.

#### TP-2 — current board controls (ready for review, 2026-07-30)

Scope completed: the Decisions left rail now includes a `Re-validate visible`
control for the on-screen current-board rows in the left list viewport. It
collects only row symbols intersecting the visible scroll area, reuses the
existing scoped validation workflow, shows the same blocking validation
overlay, refreshes the workspace after completion, and writes a result strip
with validated count plus Trade/Watch/No trade/Excluded summary. Failed
validation leaves an explicit warning that existing rows should be treated as
stale until retry. Owner live test fixes capped long validation symbol lists in
the overlay/toast and corrected the visible-row batch from "all rendered rows"
to actual viewport-visible rows, avoiding 300+ symbol multi-minute runs from
the left-rail shortcut. Follow-up live test fix capped the quick action to the
first 5 on-screen rows because scoped validation is a synchronous ingest +
eligibility + decision cycle; larger batches belong in a dedicated/background
flow, not the quick refresh affordance.
Every quick refresh outcome now starts a 60-second local cooldown, preventing
habitual repeat taps from reaching Kite's rate limit in normal use. Kite
429/rate-limit responses are mapped to plain user copy and use the same
cooldown. The button is disabled during cooldown, switches to an hourglass, and
its tooltip/accessible label carries the retry countdown. Larger refreshes
remain intentionally out of scope for this shortcut and should use a
dedicated/background flow.
The validation overlay now includes an elapsed timer and a close control. Close
hides the progress screen only; the already-started validation continues and
the left-list status strip reports the result/cooldown.
Cooldown-only status messages clear automatically when cooldown ends. Actual
error/rate-limit guidance stays visible until the next user action.

Architectural note: TP-2 is frontend orchestration over the existing scoped
candidate validation endpoint. It adds no broker write action, no order
placement, no analytical engine change, and no new recommendation logic.
Hidden historical expired TradePlans are not present in the rendered current
board and are therefore not included in the visible-symbol batch.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### TP-3 — top current setups (ready for review, 2026-07-30)

Scope completed: the Decisions left rail now starts with a `Top Current Setups`
review queue when current qualifying rows exist. The queue is capped at 10 and
is built only from the same filtered/dismissal-aware current-board rows already
visible to the owner. Admission is deliberately strict: a row must still be an
actionable `TRADE` with a `FRESH` or `AGING` TradePlan. Expired, stale,
no-plan, historical, dismissed, and filtered-out rows cannot enter the top
queue. Ranking is presentation-only over existing persisted/display data:
score first, then confidence, lower risk, expected return, risk/reward,
timestamp, and symbol. The normal Trade/Watch/No trade sections remain below
the queue for complete board context.

Owner UX adjustment: the long left-list explanation was compacted into a short
count line (`current · Trade · Watch · No trade`) with explanatory semantics
moved into hover/title text, preserving scan space for setup rows.

Architectural note: TP-3 adds no broker write action, no order placement, no
analytical-engine change, no TradePlan value change, and no new recommendation
logic. It is a frontend review queue over the existing current board.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### TP-4 — intraday SOP surface (approved, 2026-07-30)

Scope completed: ATHENA now has a persistent `Intraday operating guide`
reachable from the global header without selecting a symbol. The guide is a
modal operating manual, not another sticky panel, so it does not reduce the
selected-symbol reading area. It covers before-market checks, building the work
queue, before-entry checks, no-fill handling, after-entry handling, end-of-day
rules, and the manual broker boundary in plain language.

Owner copy requirement: the SOP avoids internal terms and uses normal trading
language such as check, skip, entry zone, stop, target, exit, and market close.
It explicitly states that ATHENA is advisory only, does not place orders, does
not guarantee profit, and leaves the final action, position size, broker order
type, and exit to the owner.

Architectural note: TP-4 is static frontend guidance only. It adds no broker
write action, no order placement, no analytical-engine change, no TradePlan
value change, no backend endpoint, and no new recommendation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

**Intraday Advisor UX track closed (2026-07-30):** owner approved TP-4, the
final approved TP milestone. The Decisions & Trace advisor workflow now has
selected-symbol trading steps, current-board refresh controls, a top current
setup review queue, and a persistent intraday operating guide. Any additional
TP work requires a new owner-approved milestone entry before implementation.

---

### Advisor Workbench Polish track (owner direction, 2026-07-30)

Improves the completed intraday advisor cockpit around entry readiness and
Market Intelligence validation workflows. Presentation-first unless a milestone
explicitly states an additive read-only API need. This track does not change
scoring, confidence, risk, decision policy, TradePlan values, providers, frozen
domain contracts, or broker behavior. Governing plan:
`docs/design/ATHENA-ADVISOR-WORKBENCH-POLISH-ROADMAP.md`.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **AW-1** Entry Readiness Indicator | Compare selected live price with persisted TradePlan entry zone and show whether entry is ready, waiting, chasing, or unavailable | Owner review; no new recommendation logic | ✅ Approved |
| **AW-2** Saved Symbol Validation and Result Report | Add Saved Symbols validate action and a single-symbol validation report modal for Market Intelligence callers only | Owner review; Decision-detail revalidation must stay inline | ✅ Approved |
| **AW-3** Validation Pipeline Workbench | Revamp the Validation Pipeline card and detail modal into a daily-use validation diagnostic workbench | Owner review; no fabricated blocker data | 🔄 Ready for review |
| **AW-4** Advisor Workbench Visual QA | Screenshot/interaction QA across Decisions and Market Intelligence workbench paths | Owner review | 🔄 In progress |

**Implementation rule:** one AW milestone at a time. AW must never create order
placement, broker write actions, new signals, or changes to ATHENA's analytical
engines.

#### AW-1 — entry readiness indicator (approved, 2026-07-30)

Scope completed: the Decision Brief header now includes an entry-readiness chip
next to the live price. The chip compares the current live quote with the
selected decision's persisted TradePlan entry zone and refreshes when the
selected decision, live quote, quote clear, or authoritative plan freshness
changes. It shows `Entry ready`, `Wait for entry`, `Chasing risk`,
`No current entry`, or `Waiting for quote` using existing quote, TradePlan, and
freshness data only.
Follow-up owner safety fix: the chip no longer treats one tick above a
single-point BUY entry as automatic `Chasing risk`. It now keeps `Entry ready`
strictly for price inside the persisted entry zone, adds `Entry acceptable`
only when price is within 0.25% beyond the entry boundary and live reward:risk
from the current quote to the persisted stop/first target remains at least
1.8:1, and shows `Avoid entry` when price has already crossed the stop or
target boundary. No TradePlan values, thresholds, score, or recommendation
logic are changed.

Architectural note: AW-1 is frontend presentation only. It adds no broker write
action, no order placement, no analytical-engine change, no TradePlan value
change, no backend endpoint, and no new recommendation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### AW-2 — saved symbol validation and result report (ready for review, 2026-07-30)

Scope completed: Saved Symbols rows now include a `Validate` action. Market
Intelligence single-symbol validations (Saved Symbols, Universe row validate,
and Add & validate) opt into a validation report modal after the existing
validation workflow refreshes Market Intelligence and Decisions. The report
summarizes the symbol, validation time/mode, outcome, score, confidence, risk,
plan status, and useful next actions: open decision, inspect trace, save/remove
saved symbol, re-validate, or close.

Owner review fix: Saved Symbols row actions are now icon-only with tooltips and
accessible labels so the side rail no longer scrolls horizontally. The report
modal was widened and rebalanced: score/confidence/risk use compact metric
cards, plan status spans the full row to avoid truncation, and the action grid
has consistent spacing. `Open decision` now waits for the Decisions tab load and
then selects the validated symbol explicitly, preventing the previous race where
the tab switched but the symbol was not selected.

Owner UX rule preserved: Decision detail revalidation does not open the report
popup. Visible-board refresh, batch validation, and full validation also keep
their existing summary/progress surfaces instead of opening per-symbol reports.

Architectural note: AW-2 is frontend presentation/orchestration over existing
validation, saved-symbol, universe, decision, and trace data. It adds no broker
write action, no order placement, no analytical-engine change, no TradePlan
value change, no backend endpoint, and no new recommendation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### AW-3 — validation pipeline workbench (ready for review, 2026-07-30)

Scope completed: the Market Intelligence Validation Pipeline card now includes
an operational summary below the funnel: latest run status/time, top blocker,
and next action. The detail modal is now a workbench with Overview, Blockers,
Symbols, and Runs sections. Overview summarizes today's conversion and next
action; Blockers groups real exclusion reasons from the loaded universe rows;
Results combines eligibility, blocker, Watch/Trade outcome, score, plan
freshness, Open decision, Save, and Trace actions into one searchable section
instead of splitting eligible/excluded rows from a separate Qualified Today
block. Runs shows recent validation run status/time.

Owner review fix: validation-report `Open decision` now enables only when the
symbol has a current, openable Decisions row. Excluded/no-current reports show a
visibly disabled action instead of a dead click. The Decisions handoff now
activates the tab without an extra fallback load, and
`loadDecisionsWorkspace()` returns the strictly selected row so valid symbols no
longer show a false "not in current Decisions list" warning.

Follow-up owner fix: strict symbol opens now select by requested symbol before
considering the previously active `decision_id`. This prevents a report opened
from Market Intelligence from switching tabs but leaving the old selected symbol
in the Decision Brief.

Workbench polish fix: the former bottom Qualified Today list is merged into the
Results section, so validation screening happens in one dense list without a
second competing subsection.

Owner screenshot fix: the workbench modal width override now lives after the
shared modal cap, so the Results grid uses the available screen width without
horizontal scrolling. Results `Open decision` now depends on a refreshed
read-only current Decisions cache; rows that are not on the current board are
disabled instead of switching tabs and failing with "not found".

Owner readability fix: the Results tab now uses self-contained result cards
instead of a table-style header/column grid. Symbol explanations wrap normally,
score is recovered from the current decision, qualified payload, or explanation
without truncating the primary screening text.

Owner screening fix: the Results tab now includes compact search, outcome
filter, plan-status filter, sort order, visible result count, and reset controls.
The controls operate only on the loaded validation/decision data in the modal, so
screening large daily lists is faster without changing validation, scoring, or
TradePlan logic. Filter and sort changes now show an inline Applying indicator
and dim the result list while the client redraws large result sets.
text, plan state is shown as a labelled card metric, and actions stay pinned to
a consistent right edge without a drifting Actions header.

Data boundary: AW-3 uses the existing `/api/v1/pipelines/validation-funnel`,
`/api/v1/pipelines/runs`, merged current-day `universe_members`,
`qualified_today`, and run metadata only. Top blockers are derived only from
persisted `exclusion_reasons` or `eligibility_summary`; if those are absent,
the UI says blocker data is unavailable. No blocker, stage, or symbol outcome is
fabricated.

Architectural note: AW-3 is frontend presentation/orchestration only. It adds no
broker write action, no order placement, no analytical-engine change, no
TradePlan value change, no backend endpoint, and no new validation logic.

Validation note: focused dashboard hosting checks pass. The full suite remains
deferred locally until the live DB/storage pressure is cleaned up.

#### AW-4 — advisor workbench visual QA (in progress, 2026-07-30)

Owner screenshot fix: `Watch` and `No trade` decisions with no current
TradePlan now still render the Advisor Status strip with a neutral
`No current trade plan` state and a `Re-check symbol` action. This preserves
the TP-1 placement rule that symbol revalidation belongs in Advisor Status
instead of the generic header, while ensuring non-trade symbols are still
refreshable without implying they are actionable trades.

Owner usability fix: the Decision Brief detail pane now keeps only the
symbol/current-price header row fixed. Metadata, gauges, summary, Advisor
Status, tabs, and tab content live inside one scroll region, and the old
scroll-triggered compact header behavior was removed to stop Market Context and
other short tabs from flickering or feeling stuck during vertical scroll.
Follow-up owner screenshot fix: the tab strip remains part of the same scroll
surface as a full-height normal row, not a separate sticky strip, so
`Trade Plan`, `Analysis`, `Market Context`, `Response`, and `History` are not
clipped between Advisor Status and the first detail card.

Owner priority-order fix: the `Trade Plan` tab now reads in trader action
order — `ATHENA TradePlan` levels first, then `Intraday price context`, then
`Trading Steps`, then `Portfolio impact`, with `Universe eligibility` last as
supporting audit evidence. This keeps entry/stop/target and live chart context
above internal validation details without changing any ATHENA calculations.

Owner first-fold cockpit fix: the Decision Brief no longer opens with the
full score/report stack before the actionable plan. The scroll surface now
prioritizes tabs, Advisor Status, the current TradePlan ticket, and the
intraday chart before the trading guide and supporting audit sections.
Recommendation/score/confidence/risk gauges and the ATHENA Summary remain
available below the active tab content as explanation, not as the landing
experience repeated for every symbol.

Owner long-list usability fix: the Decisions symbol rail now has an in-list
`Top` affordance that appears only after the owner scrolls meaningfully down
the current board. It scrolls the symbol list itself back to the top without
touching the selected Decision Brief or the rest of the workstation.
The Decisions symbol search now also has an inline clear affordance that
appears only while a query is active, clears the filter in one click, and
returns focus to the search field.

Owner identity placement fix: the fixed Decision Brief header now treats
exchange and real company name as their own instrument metadata row
(`NSE · COMPANY NAME`), separate from the ticker title. The identity line is no
longer part of the scrolling detail content or attached to the symbol-name
stack, so it can use the available header width and wrap cleanly without
fighting the live price/actions cluster. Because the ticker already appears as
the primary title, the metadata row does not repeat the symbol as
`NSE: SYMBOL`.

Owner correctness fix: the global advisor pulse no longer says `Market live`
just because Kite/ticker data is available. The pulse now treats
`/api/v1/dashboard/session-status` as the source of truth: open sessions show
live wording, closed/pre-open/no-session states show the server calendar
message such as `Market closed · next live 31 Jul, 09:15 AM IST`, and Kite is
only appended as connectivity context.

Validation note: focused dashboard hosting checks pass. Browser shell-load QA
confirmed the dashboard assets serve, but unlocked in-dashboard visual QA
remains pending owner-session access.

---

### Index and Sector Intelligence track (owner direction, 2026-07-31)

Adds trustworthy broad-market and sector-index context to Market Intelligence,
then connects that context to current ATHENA setups in later review-gated
milestones. Governing plan:
`docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`.

Agent continuity snapshot: `docs/ATHENA-IX-HANDOFF.md`. Verify this dated
handoff against this milestone table, `IMPLEMENTATION_SUMMARY.md`, and git
before continuing the IX track.

This track is presentation-only until a separately approved evidence review and
ADR authorize analytical use. It does not silently resolve SD-2, activate
`sector_quality`, alter scoring/decision thresholds, or add broker write paths.

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **IX-1** Tracked-Index Data Foundation | Separate quote-only snapshot coverage from benchmark history ingestion; add validated index catalog and read-only API | Owner review; no scoring/domain/protocol change | ✅ Approved |
| **IX-2** Index Leadership Surface | Compact, session-aware broad-market and sector leadership view in Market Intelligence | Owner review and visual QA | ✅ Approved |
| **IX-3** Versioned Constituents and Index Breadth | Official provenance-tagged memberships, resolution audit, breadth/current-board counts | Data review; no inferred membership | ✅ Approved |
| **IX-4a** Index members endpoint + Universe filter | New read-only per-symbol index membership endpoint (reusing IX-3's exact resolution); Universe tab index filter | Owner review; no inferred mapping, no scoring/domain change | ✅ Approved |
| **IX-4b** Validation Workbench Results index filter | Index filter on the Workbench Results list, same membership data as IX-4a | Owner review; presentation-only | ✅ Approved |
| **IX-4c** Decisions index filter + selected-index view | Decisions index filter, selected-index Trade/Watch/No-trade view, ranking reuse, strict symbol handoff | Owner review; current-plan safety rules | ✅ Approved |
| **IX-5** Symbol Index Backdrop | Plain-language index alignment/divergence context in Decision Brief | Owner review; informational only | 🔄 Ready for review |
| **IX-6** Evidence Review and Scoring Decision | Replay impact study and ADR proposal for any analytical influence | ADR + owner approval before code | ⏳ Planned |

**Implementation rule:** one IX milestone at a time. A market leader is not
automatically a trade, and a strong sector may not override an expired plan,
failed safety gate, weak symbol score, or unavailable data. IX-4 is split into
IX-4a/IX-4b/IX-4c (owner-approved 2026-08-01, design in
`docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`); each sub-milestone
gets its own owner-approval gate before the next starts.

#### IX-1 — tracked-index data foundation (approved, 2026-07-31)

Scope completed: added a validated twelve-index catalog covering NIFTY 50,
NIFTY BANK, NIFTY NEXT 50, NIFTY MIDCAP 100, and eight sector indices. The
Kite provider loads quote-only snapshot coverage from that separate catalog
while preserving the existing strict `kite.json` benchmark-history contract.
Market snapshots quote the larger display set together, while scoped symbol
validation continues to ingest historical candles only for the existing
benchmark pair plus VIX.

Added `GET /api/v1/market/index-intelligence`, a read-only response ordered by
configuration. Each row reports stable identity, family, persisted level,
prior-session change only when a real daily baseline exists, and explicit
`AVAILABLE` / `NO_DATA` state. The response exposes its persisted-snapshot
source and observation time. Missing index quotes remain isolated; they do not
erase available peers or become fabricated zeroes.

Rate-limit note: IX-1 adds the display indices to the existing bounded snapshot
quote request. It does not add those indices to per-symbol daily/5m/15m
historical ingestion. IX-2 must consume the persisted API and must not poll Kite
directly.

Architecture note: IX-1 is additive provider configuration and a read-only API
over the existing `MarketSnapshot`/candle ledger. `MarketSnapshot`,
`MarketDataProvider`, persistence schema, scoring, confidence, risk, decision
policy, TradePlan, and broker behavior are unchanged. No ADR is required.

Validation note: focused Kite provider and market-history/API tests pass
(37 tests). The full suite passes (1,132 tests); its only initial failure was
an older chart release-gate assertion pinned to asset version `9.89.0`, which
was aligned with the already-current `9.122.0` dashboard assets without
changing chart behavior.

Owner-QA correction: an initial IX-1 draft added
`snapshot_index_instruments` to strict `kite.json`. An already-running server
using the previous strict model rejected the new key during re-validation.
That same failure forced selected-symbol quote loading onto persisted data,
where day-change percentage is intentionally unavailable. IX-1 now leaves
`kite.json` unchanged and loads snapshot coverage from
`index_intelligence.json`; focused regression coverage verifies production
config compatibility and live snapshot resolution.

#### IX-2 — index leadership surface (approved, 2026-07-31)

Scope completed: added a compact Index Leadership ribbon inside Market
Summary, backed only by the persisted IX-1 index-intelligence endpoint. The
ribbon reports tracked-data coverage, broad-market movement, and sector
leadership/laggard context when trustworthy changes exist. A dedicated modal
shows all four broad-market and eight sector indices in deterministic groups
with level, change, observation time, and explicit unavailable states.

Session wording comes from the existing Calendar Engine session endpoint.
Market-open state is not inferred from Kite connectivity, and closed-session
copy includes the next live-session guidance supplied by that service. Missing
prior-session baselines render as `Change unavailable`; they never become
`0.00%`. Daily candles remain the preferred comparison source. Quote-only
display indices without daily candles use the latest persisted snapshot before
the current trading day, so no extra Kite history request is required. On the
first rollout day, those indices remain honestly unavailable until a real
prior-session snapshot exists. A single comparable sector is labeled `Sector
observed` instead of being misrepresented as both leader and laggard.

Refresh and layout notes: persisted index observations refresh with the
existing 60-second Market-tab ticker cycle, only while Market Intelligence is
active. IX-2 never polls Kite directly. Container-aware compact layouts keep
the ribbon within the narrower Market Summary column, while the grouped modal
uses a responsive one-column layout on narrow screens and has no horizontal
scroll.

Architecture note: IX-2 is frontend presentation/orchestration over
`GET /api/v1/market/index-intelligence` and
`GET /api/v1/dashboard/session-status`. It changes no provider protocol,
historical ingestion, persistence schema, scoring, confidence, risk,
decision policy, TradePlan, frozen domain object, or broker behavior. Index
movement remains explicitly labeled as market context, not an ATHENA trade
signal. No ADR is required.

Validation note: focused market-history/dashboard/release-gate tests pass (28
tests), and the full suite passes (1,133 tests). Browser QA with persisted data verified the
compact desktop ribbon, grouped desktop modal, narrow-screen modal, modal
open/close behavior, zero horizontal overflow in supported layouts, and no
browser console errors. MyPy reports no issues. Ruff reports only seven
pre-existing findings in the hosting regression file; IX-2 adds no new Ruff
finding.

Owner-QA correction: the dashboard assets can update without restarting an
already-running API process, so the new ribbon may initially call an IX-1
route that the old process has not registered. That failure previously looked
like a legitimate empty catalog (`0 of 0`) and also hid a successful market
session response. IX-2 now loads the index and session endpoints independently,
labels index request failures as `Index data unavailable`, preserves valid
session wording, and offers a retry action. A live localhost check against the
current code/config returned all 12 configured index levels after the restarted
ingestion process persisted its next snapshot. NIFTY 50 and NIFTY BANK also had
real prior-close changes; the remaining ten correctly showed `Change
unavailable` because IX-1 was deployed during the current session and no older
snapshot baseline existed yet. Regression coverage verifies that the next
session uses the prior-session snapshot and never a same-day observation.

Owner approval: IX-2 was approved on 2026-07-31 before IX-3 implementation
began.

#### IX-3 — versioned constituents and index breadth (approved, 2026-07-31)

Scope completed: added an immutable 2026-07-31 constituent snapshot for all
twelve configured broad-market and sector indices. Each source file is the
official NSE CSV captured from its archive URL. The colocated manifest records
provider, retrieval time, effective date, member count, source URL, SHA-256
checksum, and the explicit overlap policy. The loader rejects malformed
manifests, missing/unknown index keys, duplicate keys, path traversal,
checksum drift, CSV parse failures, and member-count drift.

Resolution is exact and fail-closed. A constituent symbol resolves only when
there is exactly one active NSE EQ instrument with that symbol. ATHENA does not
guess from company names, sectors, aliases, or partial matches. Every index
reports total, resolved, and unresolved membership plus snapshot age and
official source provenance. Symbols appearing in multiple indices are counted
once inside each index and independently across indices, matching the manifest
policy.

Breadth is read-only current-board composition, not market-price breadth and
not a trading signal. ATHENA selects exactly one latest persisted decision per
instrument using timestamp and decision-id tie-breaking. A Trade decision is
counted only while its TradePlan is current; Watch and No trade retain their
current-board categories. Trade, Watch, No trade, and Trade-breadth values are
published only when every constituent resolves and every resolved member has a
current board decision. Otherwise all breadth values remain unavailable and
the response identifies unresolved instruments or missing current decisions.

Presentation note: the existing Index Leadership detail modal now shows
membership date/age, resolution and decision coverage, composition when
complete, affected symbols when incomplete, and an official-source link. The
compact Market Summary ribbon remains leadership-focused and does not gain
high-density constituent detail. Responsive styling keeps the added context
inside the modal without horizontal scrolling.

Architecture note: IX-3 adds versioned source data, a strict data loader, one
deterministic read-only repository query, additive API fields, and dashboard
presentation. It changes no frozen domain object, persistence schema, provider
protocol, ingestion behavior, scoring, confidence, risk, decision policy,
TradePlan calculation, or broker boundary. No ADR is required.

Validation note: 43 focused constituent, repository, market-history,
dashboard-hosting, and chart release-gate tests pass. The full suite passes
(1,140 tests; one existing Starlette/httpx deprecation warning). JavaScript
syntax, final diff whitespace, and IX-3-owned Ruff checks pass; MyPy reports no
issues. Repository-wide Ruff still reports the pre-existing duplicate
`SizingConfig`, repository import/SIM findings, and older dashboard assertion
formatting findings. Owner-supplied desktop screenshots verify the 12-index
coverage ribbon, closed-session copy, complete NIFTY BANK breadth, fail-closed
incomplete peers with affected-symbol disclosure, official source links, and
no visible horizontal clipping. Authenticated automated browser interaction
remained blocked at Workstation Unlock; narrow-layout behavior remains covered
by dashboard regression assertions.

Owner approval: IX-3 was approved on 2026-07-31. The IX track is paused at the
owner's direction; IX-4 remains planned and must not begin until the owner
explicitly resumes and authorizes it.

#### IX-4a — index members endpoint + Universe filter (approved, 2026-08-01)

Owner resume/authorization: the owner explicitly resumed and authorized IX-4
on 2026-08-01. IX-4's combined scope was judged too large for one review
sitting and split into IX-4a/IX-4b/IX-4c (owner-approved 2026-08-01); design
detail in `docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md`.

Design finding: IX-3's `_index_constituent_contexts` already resolves every
official constituent to at most one instrument and its current-board bucket,
but only serializes aggregate counts to the frontend — the per-symbol map is
computed and discarded. IX-4a serializes that same resolution via a new
read-only endpoint rather than building a second inferred mapping.

Scope completed: added `IndexMemberDTO`/`IndexMembersDTO`, a new
`MarketHistoryService.index_members()` reusing IX-3's exact resolution helper
(`_index_constituent_contexts` was refactored to derive its own aggregate
counts from the same per-symbol member list, so there is exactly one
resolution path, not two), and `GET
/market/index-intelligence/{index_key}/members` (404 via `IndexNotFoundError`
for an unknown/disabled key). The Universe tab now has an index-filter
dropdown mirroring the existing sector-filter pattern exactly: populated from
the already-fetched index-intelligence catalog, lazily fetching and
client-side caching each index's member list only on first selection,
disabling the control while that fetch is in flight, and surfacing the
unresolved-symbol count next to the filter rather than dropping it silently.
An index with `INCOMPLETE_INSTRUMENTS`/`INCOMPLETE_DECISIONS` still returns
its resolved members for filtering; only aggregate breadth stays suppressed.

Architectural note: IX-4a is a read-only endpoint over already-computed IX-3
resolution plus frontend presentation/filtering. It adds no broker write
action, no order placement, no scoring/confidence/risk/decision change, no
TradePlan value change, no provider protocol change, and no frozen domain
object change. Filtering is presentation-only over already-rendered Universe
rows; selecting an index never calls validation or mutates eligibility.

Validation note: 29 focused `TestIndexMembers`/`TestIndexIntelligence` tests
pass; full suite 1,147 passed; Ruff clean on all touched files (7 remaining
findings in `tests/api/platform/test_dashboard_hosting.py` are pre-existing,
confirmed via `git show HEAD` comparison, not introduced by this milestone);
MyPy reports no issues on touched source files. Live-verified in-browser
(DOM-bypass, matching the IX-3 precedent — no owner credentials available in
this environment): the toolbar renders search/status/sector/index filter on
one row without clipping, selecting an index calls the exact new endpoint
(`GET /market/index-intelligence/{key}/members`), and the 401-driven error
path correctly shows "Index membership unavailable." while re-enabling the
control rather than leaving it stuck disabled. Full authenticated interaction
with real membership data was not possible without owner credentials, same
limitation IX-3 recorded.

Owner approval: IX-4a was approved on 2026-08-01, committed as `3d19596`.

#### IX-4b — validation workbench results index filter (approved, 2026-08-01)

Owner authorization: the owner approved IX-4a and authorized starting IX-4b
on 2026-08-01.

Design: the Validation Pipeline Workbench's Results section
(`validationWorkbenchFilters()`, `validationResultRowView()`,
`compareValidationResultViews()`, `validationResultMatchesFilters()`,
`setValidationResultsBusy()` in `09-market-intelligence.js`) already reads
query/outcome/plan/sort filters and computes score/plan-freshness/outcome per
row — exactly the existing-fields ranking IX-4 requires. IX-4b adds one more
filter control of the same shape, reusing IX-4a's endpoint and client-side
membership cache rather than a second fetch/mapping.

Scope completed: extracted a shared `fetchIndexMembers(key)` helper so the
Universe filter (IX-4a) and this new Workbench Results index filter draw from
exactly one fetch/cache — never a second membership mapping. Added an "Index"
filter control to the Results toolbar (between Plan and Sort), a
`validation-results-index-filter-note` for unresolved-symbol counts, and
`filters.index` support in `validationWorkbenchFilters()`/
`validationResultMatchesFilters()` matching on the same bare-uppercase symbol
shape the Results rows already use. The new control participates in the
existing `setValidationResultsBusy()` disable/progress-feedback mechanism and
the existing Reset control, rather than introducing a second one.

Architectural note: IX-4b is frontend-only — no backend, DTO, or endpoint
changes (IX-4a's endpoint is reused as-is). It adds no broker write action,
no order placement, no scoring/confidence/risk/decision change, no TradePlan
value change. Filtering is presentation-only; selecting an index never calls
validation or mutates a result.

Validation note: full suite 1,147 passed; Ruff clean (same 7 pre-existing
`test_dashboard_hosting.py` findings, unrelated, confirmed via prior
IX-4a diff comparison — nothing new). No backend Python changed, so no
server restart was needed; confirmed the running server already served the
bumped cache-buster directly from disk. Live-verified in-browser (DOM-bypass,
same limitation as IX-3/IX-4a — no owner credentials available): opened the
Validation Pipeline Workbench, switched to the Results tab, confirmed the
Index filter renders between Plan and Sort with no clipping, and confirmed
selecting an index issues the identical IX-4a endpoint call and shows "Index
membership unavailable." on the expected 401 in this environment.

Owner approval: IX-4b was approved on 2026-08-01, committed as `d407260`.

#### IX-4c — Decisions index filter + selected-index view (approved, 2026-08-01)

Owner authorization: the owner approved IX-4b and authorized starting IX-4c
on 2026-08-01.

Design finding: `applyDecisionsView()` (`12-decisions-list.js`) already
filters `traceDecisionsList` down to `rows` by stance/type/query, sorts by
existing fields, and passes that same `rows` array to BOTH
`renderDecisionCarousels(rows)` (which already sections by TRADE/WATCH/
NO_TRADE and renders the summary strip) AND `topCurrentSetups(rows)` (TP-3's
existing score/confidence/risk/return/freshness ranking, reused verbatim).
This means IX-4c's "selected-index view of current Trade/Watch/No-trade" and
"rank only with existing fields" requirements are already satisfied by the
current architecture — adding one more membership predicate to `rows` (same
shape as the existing stance/type predicates) automatically scopes both the
carousels and the Top Current Setups queue to the selected index, with no new
view component or ranking algorithm needed. "Strict symbol handoff" is
likewise unchanged code (`preferInstrumentId`/`strictPreferInstrumentId`
already operate over whatever `rows` currently contains) — filtering by index
narrows `rows` the same way stance/type filters already do, so the handoff
mechanism itself needs no changes.

Scope: add a "Index" filter control to the Decisions filter popover (between
Type and Sort), reusing the exact same `fetchIndexMembers(key)` shared
cache/fetch introduced in IX-4b (no third membership mapping). The dashboard
JS files concatenate into one shared scope (confirmed: `12-decisions-list.js`
already calls `decisionScoreValue()` from `07-decision-format.js` verbatim),
so `09-market-intelligence.js`'s `fetchIndexMembers`/`universeIndexCatalog`
are directly reusable here without duplication.

Scope completed: added the "Index" filter control (with an unresolved-count
note), `populateDecisionsIndexFilter()`, `renderDecisionsIndexFilterNote()`,
and `applyDecisionsIndexFilterSelection()` to `12-decisions-list.js`, all
reusing IX-4a/b's `fetchIndexMembers`/`universeIndexMembersCache` verbatim —
zero new backend code, zero new fetch/cache implementation. Added one
membership predicate into `applyDecisionsView()`'s existing row filter
(alongside the pre-existing stance/type predicates), matching each row's bare
uppercase `instrument_id` against the selected index's resolved-member set.
Because that same filtered `rows` array already feeds both
`renderDecisionCarousels()` (which already sections by TRADE/WATCH/NO_TRADE
and drives the summary strip) and `topCurrentSetups()` (TP-3's existing
score/confidence/risk/return/freshness ranking), the selected-index
Trade/Watch/No-trade view and existing-fields ranking requirements are
satisfied with no new view component or ranking algorithm. The existing
`preferInstrumentId`/`strictPreferInstrumentId` handoff logic is unchanged
code operating over whatever `rows` currently contains, so strict symbol
handoff is preserved by construction, the same way it already was for the
pre-existing stance/type filters.

Architectural note: IX-4c is frontend-only — no backend, DTO, or endpoint
changes (IX-4a's endpoint/cache is reused as-is for the third time). It adds
no broker write action, no order placement, no scoring/confidence/risk/
decision change, no TradePlan value change. Filtering is presentation-only;
selecting an index never calls validation, never mutates a decision or plan.

Validation note: full suite 1,147 passed; Ruff clean (same 7 pre-existing
`test_dashboard_hosting.py` findings, unrelated). No backend Python changed,
so no server restart was needed; confirmed the running server served the
bumped cache-buster directly from disk. Live-verified in-browser (DOM-bypass,
same limitation as IX-3/IX-4a/IX-4b — no owner credentials available):
opened the Decisions & Trace Filters popover, confirmed the Index control
renders between Type and Sort with no clipping, and confirmed selecting an
index issues the identical shared endpoint call and shows "Index membership
unavailable." on the expected 401 in this environment. Decisions themselves
could not load without auth, so the carousel/Top-Current-Setups filtering
behavior with real data was verified by code reading (single shared `rows`
array) rather than live pixel inspection — the same limitation recorded by
every prior IX milestone in this environment.

Owner approval: IX-4c was approved on 2026-08-01, committed as `f69e4b8`.
The IX-4 track (IX-4a/b/c) is complete.

#### IX-5 — symbol index backdrop (ready for review, 2026-08-01)

Owner authorization: the owner approved IX-4c and authorized starting IX-5
on 2026-08-01.

Design: reuses `index_intelligence()`'s already-computed
`IndexIntelligenceItemDTO` items wholesale — no new per-symbol resolution
logic. The new backend method filters that same list down to the indices
whose official CSV membership (`membership.by_key()[key].symbols`, IX-3's
exact loaded data) contains the queried symbol; the returned items are the
identical objects `index_intelligence()` already returns, unchanged. On the
frontend, each membership item is rendered with the EXISTING
`indexObservationMarkup(item)`/`indexConstituentContextMarkup(item.constituents)`
functions (from IX-2, `09-market-intelligence.js`) — no new level/change/
breadth rendering code, since the item shape is identical to what those
functions already consume.

"Aligned vs diverging" is a plain sign comparison between the stock's own
`change_pct` (already live-polled into `activeBriefQuote`, DT-2/AW-1) and
each membership's `change_pct` — no magnitude threshold, no new numeric
constant, never fabricated when either side is unavailable.

Placement: a new section in the Decision Brief's existing "Market Context"
tab (`13-decision-brief-core.js`, alongside "Session & market context" and
"Data sources"), which the owner confirmed (via prior tab design) is the
correct home for supporting context — never the actionable Trade Plan tab.

Scope: new `GET /market/instruments/{instrument_id}/index-backdrop`
endpoint; `SymbolIndexBackdropDTO` (reusing `IndexIntelligenceItemDTO`
verbatim for `memberships`); `loadIndexBackdrop()`/`renderIndexBackdrop()` in
`15-decision-brief-context.js`, called alongside the existing
`loadDecisionContext()` call in `renderDecisionBrief()`.

Scope completed as designed: `MarketHistoryService.symbol_index_backdrop()`
and `GET /market/instruments/{instrument_id}/index-backdrop`; a new "Index
backdrop" section between "Session & market context" and "Data sources" in
the Market Context tab; `indexBackdropAlignment()` (plain sign comparison of
the stock's already-live-polled `change_pct` vs. each membership's, no
magnitude threshold); each membership row renders via the existing
`indexObservationMarkup(item)`/`indexConstituentContextMarkup()` (IX-2)
unchanged, and the alignment label via the existing `contextChip()` helper —
zero new rendering primitives. Honest-absence handling matches the existing
`context-caption`/`context-caption.unknown` convention (empty membership vs.
fetch failure are rendered distinctly, never conflated).

Architectural note: IX-5 is presentation-only. It adds one new read-only
endpoint (`Permission.READ`, same as every other market endpoint) and no
scoring/confidence/risk/decision/TradePlan change. `memberships` is never
consumed by any analytical engine.

Validation note: 5 new focused `TestSymbolIndexBackdrop` tests pass (34 total
in `test_market_history.py`); full suite 1,152 passed; Ruff clean on every
touched file (same 7 pre-existing `test_dashboard_hosting.py` findings,
unrelated). MyPy is not installed in this environment (no project venv, no
global install) and could not be run this round — noted honestly rather than
claimed. Restarted the server (backend changed this round) and confirmed the
new endpoint is registered correctly (`401` for an unauthenticated request,
not `404`/`500`). Directly verified `symbol_index_backdrop()` against the
real production `db/athena.db`/`config/` (bypassing the API auth layer, the
same diagnostic pattern used earlier in this project): INFY/TCS → `nifty_50,
nifty_it`; RELIANCE → `nifty_50, nifty_energy`; SBIN → `nifty_50,
nifty_bank, nifty_psu_bank` — all matching real NSE index composition, with
real level/change_pct/breadth values attached to each membership, including
an honest `INCOMPLETE_INSTRUMENTS`/`INCOMPLETE_DECISIONS` breadth status
where genuinely incomplete. Live-verified in-browser (DOM-bypass, same
limitation as every prior IX milestone — no owner credentials available):
no new console errors beyond expected 401 auth-noise. The populated section
itself could not be visually inspected because Decisions could not load
without auth in this environment, and the module-scoped render/load
functions are not reachable from a separate browser-console execution
context to synthesize a decision — the dashboard-hosting regression tests
and the direct production-data check above are the substitute evidence.

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
| **DT-2** Hero header + Quick Summary + ticker strip | Hero header spacing/hierarchy polish; standalone Quick Summary card with Trade-Plan/Historical-Analogs fields (real Holding Period range, not a single average) and reference-mock-matched formatting/coloring; header market ticker (NIFTY 50/BANK NIFTY/INDIA VIX, real level + real day-change %, 60s auto-refresh) | ✅ Approved |
| **DT-3** Tab restructuring (5 tabs) + spacing polish | Split "Decision History" into Response (Journal/Outcome) + History (Timeline + Analogs); Decision Timeline moved out of the always-visible hero (real wasted-space fix); Recommendation+ATHENA Summary hero redesign; identity row redesign (real company name via a small ingestion fix, star favorite toggle, overflow menu); symbols panel color system calibrated to a single, restrained scheme | ✅ Approved |
| **DT-4** Reasoning Trace redesign + Similar Trades sparkline | Replace the auto-fit-grid + SVG-connector DAG with a cleaner vertical pipeline list (real existing stage status only, never fabricated counts/funnels — confirmed no such data exists anywhere in ATHENA); same click/detail-panel behavior, same stage order; add the last-5-trades sparkline to Analogs | ✅ Approved |

**ATHENA Workstation Refactor track closed (2026-07-27):** owner approved DT-4, the last of the 4 milestones (DT-1 through DT-4). The full presentation-layer refactor of Decisions & Trace — 3-pane layout shell, hero header + Quick Summary + market ticker, 5-tab restructuring + identity row + symbols-panel color system, and the Reasoning Trace vertical pipeline list + Similar Trades sparkline — is complete. No backend/business-logic/scoring/reasoning changes were made in any of the four milestones; every new visual element traced back to real, already-persisted data (or was explicitly omitted and tracked as future scope when no real data existed, per ADR-005).

### ATHENA Market Intelligence Redesign (owner assignment + reference mock, 2026-07-27)

Full redesign of the Market Intelligence tab into a "Market Command Center," matching the design language, component hierarchy, and workstation layout established by the ATHENA Workstation Refactor above. Same golden rule as that track: reuse existing ViewModels/APIs/business logic wherever possible, never fabricate a value with no real data source — hide the field instead and track as future scope. Split into 5 reviewable milestones; one in flight at a time.

**Reference mock:** `docs/design/ATHENA-MARKET-INTELLIGENCE-REFERENCE.jpg` (committed to the repo — the primary visual target for MI-2 through MI-5, especially the still-unbuilt Validation Pipeline funnel, Universe table, and Recent Activity/Quick Actions layouts in MI-3–MI-5). Sibling reference for the earlier Decisions & Trace track: `docs/design/ATHENA-DECISION-TRACE-REFERENCE.jpg`. Per this track's own rule, the mock is directional, not literal — omit/hide anything it shows with no real backing data.

Before any implementation, a full data-source inventory was done across every mock element (see MI-2 below for the two biggest findings). Owner-confirmed scope decisions (before MI-1 started):

- Market Health Score ("84/100" ring) and Breadth ("72%"/"1458/526") are both confirmed gaps (hardcoded `0`/`0` upstream, no numeric `MarketHealthScore` ever constructed anywhere in the codebase) — owner chose to show the real 4-dimension categorical labels `MarketHealthEngine` already computes instead of either fabricating a number or omitting the section entirely (MI-2). **Post-MI track:** both gaps are now owned by **Market Metrics Completion** (MH-0+), with locked owner choices: universe ADV/DEC/neutral breadth, exact F-5 six-component score, external FII/DII for institutional strength.
- Recent Market Activity will be a real chronological feed (validation runs + VIX/index snapshot history) — no synthesized "regime reaffirmed"/"breadth improved" diff-events, since no comparison logic for those exists anywhere (MI-5).
- Universe table's Sector column — a fixable gap (same shape as DT-3's company-name fix): the seed CSV's real `Industry` column is silently discarded during ingestion. Owner approved fixing it (MI-4).
- "Run Full Validation" — a real engine (`OwnerValidationPipeline.run()`) with zero endpoint/button today; owner approved wiring a new endpoint despite it being the one mutating (not just read) action in this otherwise presentation-only redesign (MI-5).
- Trading Calendar relocated to a collapsed-by-default secondary panel on the same page (not moved to Settings/a new Utilities section) — it previously consumed the largest area on the page for one of the lowest-value sections during live trading (MI-1).
- "Export Market Snapshot" and the Validation Pipeline's "Filtered" stage are lower-stakes calls proceeding on stated defaults: Export omitted entirely (the export type genuinely isn't implemented — matches the "hide, don't fabricate" rule); "Filtered" shown as a derived rollup (Eligible − Watch − Trade, pure arithmetic over already-real counts, no new data).

| Milestone | Scope | Status |
|---|---|---|
| **MI-1** Shared ticker strip + Trading Calendar relocation | Generalize the Decisions & Trace header ticker to also render on Market Intelligence (one shared component/endpoint via `TICKER_TABS`, not two); relocate Trading Calendar out of the primary grid into a collapsed-by-default `<details>` panel, same rendering functions/ids untouched | ✅ Approved |
| **MI-2** Market Summary Hero + Market Regime & Context | Larger-presentation Trend/Volatility/Gap/Evidence Attribution (real); Market Health Score/Breadth gap handled via real categorical labels | ✅ Approved |
| **MI-3** Validation Pipeline funnel | New small dedicated endpoint exposing the already-computed Universe→Evaluated→Eligible/Excluded→decision_counts breakdown as a typed 5-stage funnel | ✅ Approved |
| **MI-4** Universe table redesign | Reuse real Symbol/Status/Actions; add Sector via the ingestion fix; scope Eligibility-per-row/Last-Validated-per-row | ✅ Approved |
| **MI-5** Recent Activity + Quick Actions + Saved Symbols | Real chronological activity feed; Quick Actions consolidated (Add Symbol reuse, new Run Full Validation endpoint, Refresh Market Data relabeled honestly, Export omitted); Saved Symbols relocated to a secondary panel. Also absorbs the owner-requested "Validate All" — same operation as Run Full Validation — plus Kite pacing/429 handling | ✅ Approved |

#### MI-1 — Shared ticker strip + Trading Calendar relocation

A full data-source inventory (file:line level) was done across every element in the reference mock before proposing any milestone breakdown — see the track intro above for the two biggest findings (Market Health Score/Breadth are both confirmed gaps). MI-1's own scope was narrowed from the originally-proposed "2-row workstation grid" down to just the two independently well-defined, zero-placeholder pieces: building the full target grid now would leave empty cells for Quick Actions/Recent Activity (content that doesn't exist until MI-5), which conflicts with the project's "no placeholders" rule. The grid will take its final shape incrementally as MI-2 through MI-5 land real content, mirroring how DT-1→DT-4 organically built up the Decisions & Trace layout.

| | |
|---|---|
| Scope | `03-app-shell.js`: `TICKER_TABS = new Set(["decisions", "market"])` replaces the hardcoded `tabId !== "decisions"` check in 3 places (visibility, refresh start/stop, `loadTabData`'s market branch now also calls `loadMarketTicker()`). `index.html`: Trading Calendar markup moved out of the 3-column `.market-workstation` grid (now 2 columns) into a `<details class="market-calendar-details">` panel below it, collapsed by default — same ids (`calendar-month-year`/`calendar-grid-container`/`upcoming-events-container`) so `renderCalendar()`/`renderUpcomingEvents()` are completely untouched. `06-market-intelligence.css`: `.market-workstation` grid-template-columns `1fr 1.2fr 1fr` → `1fr 1fr`; new `.market-calendar-details`/`.market-calendar-summary`/`.market-calendar-chevron` (native `<details>`, no JS toggle logic needed). |
| Tests | ~15 new/updated dashboard-hosting assertions (ticker generalization across all 3 coupling points, calendar relocation, 2-column grid). Full suite **1042 passed** |
| Coverage | Live-browser verified: ticker strip now visible on Market Intelligence tab (confirmed via a real nav click, not a synthetic poke); 2-column grid renders correctly; calendar panel collapsed by default, expands on click with the chevron rotating, calendar content (month grid, upcoming events) renders correctly once expanded; zero uncaught console errors beyond the expected unauthenticated-fetch logging already present in every prior milestone's verification |
| Status | ✅ Approved (2026-07-27) |

---

#### MI-2 — Market Summary Hero + Market Regime & Context

Replaced the "Volatility Regime & Health" card with a "Market Summary" hero. Investigated the Market Health Score gauge before touching any UI: `owner_validation.py`'s `_regime_to_payload()` hardcoded `"market_health": 0` in the payload the page reads, and the real `MarketHealthEngine.assess()` result — already computed during every scan — was never serialized back into it. Deeper still: `MarketHealthScore` (the frozen domain's numeric 0-100 type) has zero constructors anywhere in ATHENA; there is no real number to show at all, only `MarketHealthAssessment.dimensions` (4 real categorical labels: breadth/trend_quality/momentum/volatility). Per the owner's decision, replaced the fabricated gauge with these real labels instead of omitting the section or inventing a placeholder.

Fixing this required two backend changes, not one — caught only by re-running the test after the first fix:

1. `_regime_to_payload(regime, market_health=None)` now builds a real `dimensions` dict from the passed `MarketHealthResult` (empty `{}`, never fabricated, when none is available). `reg_stage` in `_scan_eligible` reordered so `market_health` is computed before the payload is captured (previously the payload was built one line before `market_health` was assigned, on the very first instrument of every scan).
2. That alone didn't reach the frontend: `run()` computes an eager, regime-only `regime_payload` via `_maybe_regime()` *before* any scan runs, and only fell back to the scan's own richer `scan_regime` (with real `market_health`) `if regime_payload is None` — which was essentially always false, so the eager payload (never carrying market_health) silently won every time a scan had eligible symbols. Flipped the precedence to prefer `scan_regime` whenever a scan actually ran.

Verified against the real production `db/athena.db` (not just synthetic tests): ran `OwnerValidationPipeline.run()` directly for a real symbol and confirmed `regime_assessment.market_health` came back as `{'breadth': 'BREADTH_UNKNOWN', 'trend_quality': 'MIXED_TREND_QUALITY', 'momentum': 'WEAK_MOMENTUM', 'volatility': 'VOLATILITY_NORMAL'}` — a real dict, not `0`.

| | |
|---|---|
| Scope | **Backend**: `src/athena/ops/owner_validation.py` — `_regime_to_payload()` signature + body, `reg_stage` ordering, `run()`'s `regime_payload`/`scan_regime` precedence. **Frontend**: `index.html` — card renamed "Market Summary" with an as-of timestamp; Trend/Volatility/Gap rebuilt as `.brief-gauge`/`.hero-metric-band` tiles (the exact same tile language as Decisions & Trace's hero gauges, not a new one); Market Health rebuilt as a `.context-metric-grid` (the exact same cards the Decision Brief's own Market Context uses). `09-market-intelligence.js` — new `renderMarketHealthGrid()` reusing `contextMetricCard`/`contextChipTone`/`friendlyLabel` verbatim from the Decision Brief's context rendering (one tone system for the same RegimeLabel/MarketHealthLabel enums, not two parallel ones); `regimeAsOf` tracked and rendered; the old parallel bull/bear/neutral tone-classification logic removed in favor of `contextChipTone`; each of Trend/Volatility/Gap now falls back to its own `*_UNKNOWN` sentinel instead of a specific fabricated state (previously an absent field defaulted to "Normal volatility"/"No gap" — an assessed-looking state for data that was actually just missing). `07-decision-format.js` — `formatVolatilityLabel()` removed (its only caller was replaced). `06-market-intelligence.css` — dead `.regime-badge`/`.regime-field`/`.health-*` rules removed; new `.market-summary-gauges` (3-equal-column grid) and a scoped label-wrap override (`.brief-gauge-label` defaults to single-line ellipsis tuned for a 4-column grid's short labels — 3 columns here are narrower still, and "Volatility" alone could truncate at real workstation widths). |
| Tests | New `tests/ops/test_owner_validation.py` assertion locking in the real 4-dimension `market_health` dict. ~30 new/updated dashboard-hosting assertions. Full suite **1042 passed** |
| Coverage | Live-browser verified after a required server restart (backend Python touched): real production-data confirmation via a direct `OwnerValidationPipeline.run()` call (above); frontend rendering confirmed using that exact real payload — Trend/Volatility/Gap tiles tone-colored correctly (Bear Trend/Gap Down red, Normal Volatility neutral), Market Health's 4 real dimension cards rendered with correct tones (Mixed Trend Quality amber, Weak Momentum red, Breadth Unknown muted). Caught and fixed a real truncation bug via DOM measurement (not just eyeballing): tile labels clipped at realistic narrower workstation widths — fixed with shorter labels + a scoped wrap override, then re-measured to confirm zero truncation. Zero uncaught console errors beyond the expected unauthenticated-fetch logging. |
| Status | ✅ Approved (2026-07-28) |

---

#### MI-3 — Validation Pipeline funnel

Replaced the "Today's Validation" text summary strip with a horizontal 5-stage Validation Pipeline funnel matching the Market Intelligence reference mock. Added a small READ endpoint that maps the already-persisted `validation_summary` on the latest successful owner_validation run into typed stages — no new scan, no mutation, no fabricated upstream "Filtered" field.

| | |
|---|---|
| Scope | **Backend**: `ValidationFunnelDTO`/`ValidationFunnelStageDTO`; `PipelinesService.validation_funnel()`; `GET /api/v1/pipelines/validation-funnel`. Stages Universe→Eligible→Filtered→Watch→Trade; Filtered = `max(0, eligible − WATCH − TRADE)`; `% of Universe` with `None` when Universe is 0. **Frontend**: card renamed "Validation Pipeline"; `#validation-funnel` horizontal stage row (Trade accented); View Details toggles existing Eligible/Excluded + Qualified panels (preserved until MI-4); parallel fetch alongside `/pipelines/runs`. |
| Tests | 3 new pipeline API tests (empty / Filtered math + newest-run preference / auth). ~20 new dashboard-hosting assertions. Full suite **1045 passed** |
| Coverage | Live-verified: funnel populated after host restart (real production validation_summary); UI polish iterations for mock alignment, viewport scroll, and stacked Inspect Trace modal. |
| Status | ✅ Approved (2026-07-28) |

---

#### MI-4 — Universe table redesign + Sector ingestion fix

Replaced the Stock List (symbol + Validate/Remove) with the mock’s Universe table. Sector comes from the Nifty 500 CSV `Industry` column that `parse_nifty_constituent_csv` previously discarded — same class of fix as DT-3’s company-name ingestion, but sourced from the seed CSV (Kite has no sector). Last Validated uses the latest real `decisions.ts` per symbol (no new write-path field).

| | |
|---|---|
| Scope | **Backend**: `Instrument.sector`; SCHEMA_VERSION 9→10 + idempotent migration; `parse_nifty_constituent_rows()`; seed backfills sector even on once-per-day skip; kite upserts preserve existing sector; `OwnerCandidateDTO` enriched with `sector`/`status`/`eligibility_summary`/`last_validated_ts` via `CandidatesService` (no new endpoint). **Frontend**: Stock List → Universe table (Symbol/Sector/Status/Eligibility/Last Validated/Actions) with status+sector filters; Validate/Remove/Inspect Trace actions. |
| Tests | Sector parse/migration/preserve/backfill; candidates enrichment; scoped-validate verdict merge; Qualified Today dedupe (write + read path). Full suite **1055 passed** |
| Coverage | Self-verified via tests, plus replayed against a copy of the live DB: 16 Eligible / 10 Excluded / 481 Pending with real per-symbol timestamps, Qualified Today collapsed to one row per name, and the seed path backfilling sector onto 500 instruments (20 distinct sectors). Live: restart the host — a host started before these files were saved serves the old Python and shows every row Pending — then `./athena-daily` for the sector backfill. |
| Owner-reported fixes | Universe status no longer collapses to Pending after a scoped validate (per-symbol verdict merged newest-run-first, Excluded rows take Last Validated from the judging run); Qualified Today keeps one row per symbol (newest same-day verdict), so repeat validates stop duplicating names. |
| Status | ✅ Approved (2026-07-28) |

---

#### Fix pass: unlisted candidate symbols (owner-reported, 2026-07-28)

`./athena-daily` aborted with `ERROR: kite symbols not found on NSE: ['INFSDFSD']` — a typo'd candidate, added through the dashboard, blocked every subsequent cycle for the whole 507-symbol universe. Two separate defects: nothing stopped an unlisted symbol from being stored, and the provider treated a candidate scope list like configuration.

| | |
|---|---|
| Scope | `kite_provider.py`: `strict_symbol_filter` (default `True`) — `kite.json`'s own symbols still fail loudly, while a caller-supplied scope no longer raises; `factory.py` passes `strict_symbol_filter=kite_symbols is None`, so the CLI's existing resolve-and-warn path (and `validate_symbols`' own 422) is finally reachable. `symbol_validate.py`: catalog resolution extracted into `resolve_against_catalog()` (one catalog fetch, reused by its caller). `candidates_service.py`: `upsert_candidate` rejects a symbol the exchange does not list (422, nothing persisted), best effort — an unreachable catalog allows the add. `owner_validation.py`: a candidate with no catalog row and no ingested bar is reported in a new `unresolved_candidates` detail key instead of being judged as a synthesized instrument (which read as "Excluded: failed rules"). `candidates_service.py`/`sqlite_providers.py`/`index.html`/`09-market-intelligence.js`/`06-market-intelligence.css`: new `UNRESOLVED` status, badge, and filter option in the Universe table. |
| Tests | Provider strict/non-strict filter behaviour; pipeline reports-not-judges an unresolvable candidate; service maps `unresolved_candidates` → `UNRESOLVED` while a never-validated symbol stays `PENDING`; add-time rejection persists nothing; add proceeds when the catalog cannot be consulted. Full suite **1064 passed** |
| Coverage | Reproduced from the owner's own `./athena-daily` failure and replayed against a copy of the live DB. |

---

#### Fix pass: Validation Pipeline shows the day, not the last run (owner-reported, 2026-07-28)

Owner: "validation pipeline always lists only recent symbol and overrides previous one — I want the previous validation list as well." A scoped validate writes a run whose `universe_members` holds only the symbol it was asked about, so the funnel collapsed to "Universe 1 Symbols" and the details modal listed that one name, hiding everything validated earlier the same day.

| | |
|---|---|
| Scope | `owner_validation.py`: `_qualified_from_repo()` no longer restricts the day's WATCH/TRADE decisions to the current run's own symbols (still newest verdict per symbol, so a name downgraded to NO_TRADE drops out). `pipelines_service.py`: `validation_funnel()` counts distinct symbols across the day's completed runs, each keeping the verdict of the newest run that covered it, with each symbol's WATCH/TRADE read from that same run — never summed per-run counts, which would count re-validations twice; runs that recorded counts without per-symbol members keep the previous summary-based reading. `09-market-intelligence.js`: the details modal merges the day's runs by the same rule, so its Eligible/Excluded and Qualified Today lists match the funnel. |
| Tests | Funnel merges the day's runs and ignores a previous day's; re-validating replaces a symbol's verdict rather than adding a row; Qualified Today keeps symbols from earlier runs, one row per symbol, same day only. Full suite **1064 passed** |
| Coverage | Replayed against a copy of the live DB: the funnel went from Universe 1 / Eligible 1 (the last scoped validate) to Universe 16 / Eligible 9 / Watch 5 / Trade 4 for the day, reconstructed from runs already persisted — no re-validation needed. |

---

#### MI-5 — Recent Activity + Quick Actions + Full Validation (ADR-007)

Closes the Market Intelligence redesign. Delivers the mock's Quick Actions and Recent Activity, relocates Saved Symbols to a secondary panel, and wires **Run Full Validation / Validate All** as one owner-triggered background job per ADR-007 — with Kite pacing + 429 retry so a 507-symbol run does not trip the vendor.

| | |
|---|---|
| Scope | **Pacing**: `KiteRateLimitConfig` in `kite.json` / `KiteProviderConfig`; `UrllibKiteTransport` enforces per-class min intervals (historical 3/s, quote 1/s, other 10/s) and bounded 429 backoff. **Job**: `ServeRuntime.full_validation` + `ops/full_validation.py` (daemon thread, `CycleRunnerLock` single-flight, own DB connection); `POST/GET /api/v1/market/validate-all` (202 / poll); `CycleBusyError` → 409. Scoped `POST /market/validate` unchanged. **UI**: mock-aligned seven-cell Market Summary row (three regime metrics + four real categorical health dimensions) and Evidence footer; compact Validation KPI blocks beside the primary Universe workspace (~63% main width, sticky-header internal scroll); utility rail ordered Recent Activity → Saved Symbols → Quick Actions; Run Full Validation / Validate All / Add Symbol / Refresh Market View preserved. Export omitted (not implemented). |
| Tests | Transport pacing + 429 retry; full-validation lock/busy guards; validate-all 202/409 API; dashboard hosting for new controls. Full suite **1072 passed** |
| Coverage | Self-verified via tests and static browser measurement at 1920×1080: Universe 818px of 1304px main width (62.7%) with 553px visible internal table viewport; Summary 172px; compact Pipeline 173px. Assets `v9.62.0`; full-validation progress polls every 3s. |
| Status | ✅ Approved (2026-07-28) |

**ATHENA Market Intelligence Redesign track closed (2026-07-28):** owner approved MI-5, the last of the 5 milestones (MI-1 through MI-5). Presentation-layer Market Command Center is complete: shared ticker, Market Summary categorical hero, Validation Pipeline funnel, Universe table + sector ingestion, Quick Actions / Recent Activity / Saved Symbols rail, and ADR-007 full-universe validation with Kite pacing. Confirmed data gaps that the mock still shows literally — numeric Market Health Score (F-5) and real breadth ADV/DEC — move to the **Market Metrics Completion** track below (never fabricated in MI).

---

### Market Metrics Completion (owner assignment, 2026-07-28)

Literal Market Summary mock fidelity requires real numeric inputs the MI track deliberately deferred (ADR-005). Owner decisions locked before MH-0:

- **Breadth:** Nifty-500 / owner-universe advances vs declines from latest two D1 closes; unchanged closes count as **neutral** (not exchange-wide NSE breadth; Kite cannot supply that).
- **Market Health Score:** exact frozen F-5 six components — `trend_quality`, `breadth`, `liquidity`, `volatility`, `institutional_strength`, `gap_stability` — not a four-label rollup and not a display-only mapping.
- **Institutional strength:** external FII/DII cash-flow source (no price-volume proxy).

| Milestone | Scope | Status |
|---|---|---|
| **MH-0** Design — FII/DII source + F-5 scoring contract | DD-11 institutional-flow source decision; ADR-008 (provider Protocol); F-5 scoring / unknown-data / persistence / API history specification | ✅ Approved |
| **MH-1** Canonical inputs + persistence | Approved FII/DII ingest; universe breadth (+ neutral); liquidity + gap-stability aggregates; snapshot/history read paths | ✅ Approved |
| **MH-2** Exact F-5 `MarketHealthScore` | Construct + persist authoritative six-component score; align scoring/risk/decision consumers; ADR-005 evidence | ✅ Approved |
| **MH-3** Market Summary API + mock-faithful UI | Dedicated summary read model; sparklines/rings/ADV-DEC/evidence panel from real persisted data only | ✅ Approved |

Design artifacts (MH-0):

- `docs/decisions/DD-11-institutional-flow-fii-dii.md` (Accepted)
- `docs/adr/ADR-008-institutional-flow-provider.md` (Accepted)
- `docs/design/F5-MARKET-HEALTH-SCORE.md` (Accepted)

#### MH-1 — Canonical inputs + persistence

Delivers the real inputs F-5 needs before any numeric score is constructed: institutional FII/DII rows, universe ADV/DEC/neutral breadth on `MarketSnapshot`, liquidity + gap-stability aggregates, and snapshot history reads.

| | |
|---|---|
| Scope | **Domain**: `InstitutionalFlowSession`; `MarketSnapshot.breadth_neutral` (blueprint §4 additive). **Provider**: `InstitutionalFlowProvider` Protocol; file + NSE adapters; config `ingestion.institutional_flow_provider`. **Persistence**: SCHEMA_VERSION 11 `institutional_flows` append-only; `list_snapshots_recent`; flow query helpers. **Pure aggregates**: `market_health/aggregates.py` (breadth/liquidity/gap). **Wiring**: ingest best-effort institutional fetch (never aborts cycle); owner validation enriches snapshot + persists `market_metric_inputs` on run detail. |
| Tests | File/NSE parse+provider; repository flow + snapshot history; breadth/liquidity/gap pure tests; SCHEMA_VERSION 11. Full suite **1081 passed** |
| Coverage | Self-verified via unit/integration tests. Live NSE fetch is best-effort (ProviderError → `institutional_error`, cycle continues). Flip `institutional_flow_provider` to `nse` when ready for live FII/DII. |
| Status | ✅ Approved (2026-07-28) |

#### MH-2 — Exact F-5 `MarketHealthScore`

Constructs the authoritative six-component numeric score from MH-1 inputs, persists it on the validation run, and cuts scoring's `market_quality` over to `MarketHealthScore.total` when present.

| | |
|---|---|
| Scope | **Config**: F-5 component point maps + weights (sum 100). **Pure construction**: `market_health/score.py` maps trend/breadth/liquidity/volatility/institutional/gap → points or absent; emits `MarketHealthScore` only when all six present (F-5 §4). **Persistence**: run `detail_json.market_health_score` (+ component diagnostics). **Cutover**: `ScoringEngine._market_quality` prefers score total; categorical label average remains compat shim. |
| Tests | Component band mapping, unavailable-when-any-absent, weighted total, scoring cutover, config validation. Full suite **1091 passed** |
| Status | ✅ Approved (2026-07-28) |

#### MH-3 — Market Summary API + mock-faithful UI

Dedicated read model exposes persisted F-5 score, universe breadth, VIX, and sparklines; Market Summary UI renders them honestly (Unavailable when absent).

| | |
|---|---|
| Scope | **API**: `GET /api/v1/market/summary` + `MarketSummaryDTO` (F-5 §8). **Service**: reads latest completed validation run detail (`market_health_score`, `market_metric_inputs`, `regime_assessment`) + D1 candle closes for sparklines. **UI**: mock-aligned single 8-cell band — Regime (NIFTY sparkline), Volatility (VIX sparkline), Gap indicator, real Universe Breadth ring, categorical Momentum/Trend/Volatility indicators, and persisted F-5 Market Health ring; concise display labels remove only redundant dimension words. |
| Tests | Service unit + authenticated HTTP + dashboard hosting assertions. Full suite **1095 passed** |
| Status | ✅ Approved (2026-07-28) |

**ATHENA Market Metrics Completion track closed (2026-07-28):** owner approved MH-3, the last of the 4 milestones (MH-0 through MH-3). Canonical FII/DII + universe breadth inputs, exact F-5 `MarketHealthScore`, and the dedicated Market Summary read model + mock-faithful 8-cell UI are complete. Unavailable Breadth / Market Health remain honest empty states until a post–MH-1/MH-2 validation writes complete metric inputs and a six-component score — never fabricated (ADR-005).

---

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

### Fix pass: reload-resets-tab regression + collapsible global sidebar (owner-requested, 2026-07-27)

Not Decisions & Trace-specific — global app-shell fixes, requested before starting DT-2.

| | |
|---|---|
| Bug | The earlier "tab restored on login" fix (see the fix-pass entry above this one) made `initializeRoute()` *always* force Portfolio Overview — correct for a fresh login, but the owner reported it also made a **plain reload (Cmd+R)** of an already-active session jump back to Overview every time, which they flagged as "very annoying." Root cause of the over-fix: `initializeRoute()` is called from 3 places — `bootstrapSession()`'s two silent-restore branches (auth not required; an already-valid stored token) **and** the login-form submit handler — and the original fix changed the shared function instead of only the login path |
| Fix | `initializeRoute()` reverted to URL-preserving (parses `window.location.pathname`, used by both `bootstrapSession()` branches — a reload now stays on whatever tab was already showing). A new, separate `resetToOverviewTab()` (force-to-Overview) is called only from the login-form submit handler — the one place that should actually reset navigation |
| Feature | Collapsible global sidebar — icon-only when collapsed (each nav item already had visible text as its label; added `title="..."` attributes so hovering still shows it as a tooltip once collapsed). `.console-main` (`flex-grow: 1`) reflows into the freed width automatically via the same CSS width transition on `.sidebar` — no JS recalculation needed. Preference persisted in `localStorage` across reloads |
| Tests | 6 new dashboard-hosting assertions (including one that explicitly greps `initializeRoute`'s own function body to confirm it does *not* contain the force-reset call, so this exact regression can't silently reappear) |
| Coverage | Live-browser verified: sidebar collapses/expands with a smooth width transition, main content reflows automatically, toggle icon flips direction, collapsed state survives a reload. Could not drive the real reload-preserves-tab scenario end-to-end myself — this deployment requires real owner credentials (confirmed via the unlock gate staying visible) — verified via direct code review instead, since both `initializeRoute`/`resetToOverviewTab` are small, unconditional functions with no branching |
| Status | ✅ Built, tested, live-verified (sidebar collapse); awaiting owner confirmation of the reload-tab-persistence fix on the real authenticated session |

#### DT-2 — Hero header + Quick Summary + ticker strip

Before implementing the ticker, stopped and researched exactly what market data ATHENA already has (per the owner's data-source priority), then presented two genuine gaps for a decision rather than fabricating either:

- **Market breadth (ADV/DEC)**: confirmed a genuine gap, not a wiring gap — Kite Connect's quote API has no advancers/decliners concept, and the live Kite provider hardcodes `breadth_advances=0, breadth_declines=0` always. **Decision: omit from the ticker, tracked as future scope** (a real external breadth feed would need its own separate proposal, not bundled into this presentation milestone).
- **Overall "Market Health" score**: found the existing Market Intelligence gauge has *always* shown a hardcoded `0/100` — but investigating further, there is no real aggregate 0-100 score anywhere in ATHENA to plug into it (`MarketHealthAssessment` only has 4 categorical dimension labels — Breadth/Trend Quality/Momentum/Volatility — no scalar score). Synthesizing one would be new business logic. **Decision: omit from the ticker, drop the fake gauge, tracked as future scope** (rather than fabricate a formula or leave the known-broken stub).
- NIFTY 50, BANK NIFTY, and India VIX, by contrast, are all genuinely real: Kite's live snapshot already fetches all three, and daily candles are already ingested for all three too — enough to compute a real day-change % from already-persisted data, not a new calculation.

| | |
|---|---|
| Scope | **Backend** (new, small, additive — Priority-2 exception per the owner's own rule: expose already-computed data, no new provider/architecture/business logic): `MarketTickerDTO`/`MarketIndexTickerDTO` (`dtos/market.py`); `MarketHistoryService.market_ticker()` — reads the latest persisted `MarketSnapshot` + `list_candles_recent()` for the prior close, derives change % via simple arithmetic; `GET /api/v1/market/ticker` (READ). **Frontend**: header ticker markup (shown/fetched only on Decisions & Trace — the one approved new API call), auto-refreshed every 60s while that tab is active (owner-requested refinement — see below); `renderSidebarQuickSummary()` expanded with R:R Potential, Expected Return (reuses the existing `computeExpectedReturnPct`), and Historical Analogs' Win Rate/Avg Holding (explicitly labeled "(Historical)" — there is no forward-looking per-decision holding field anywhere in ATHENA, so this is honestly a past-trades average, not a guarantee), restructured as its own standalone card (owner reference-mock refinement — see below); hero header spacing/hierarchy CSS polish (larger symbol text, clearer grouping divider) — same elements, same data, nothing moved |
| Tests | 4 new backend tests (`test_market_history.py`, including 2 using a real `SqliteRepository` to exercise the actual snapshot+candle-derived arithmetic, one confirming `change_pct` is honestly `None` — never fabricated — without a prior close), plus 2 existing analog-aggregate tests (`test_core_apis.py`) extended with real min/max holding-day assertions. ~35 new dashboard-hosting assertions. Full suite **1035 passed** |
| Coverage | Live-browser verified: ticker shows/hides correctly per active tab (confirmed via real nav clicks, not synthetic pokes); graceful "—" fallback confirmed when the ticker endpoint 401s (no owner credentials for a real authenticated fetch); Quick Summary card visually confirmed via injected sample data — layout matches the reference mock |
| Status | ✅ Approved (2026-07-27) |

**Refinements from owner screenshot review (2026-07-27), before final approval:**

- **Quick Summary → standalone card.** Originally expanded in place at the top of the Reasoning Trace card with no visual separation. Owner shared the reference mock's own Quick Summary treatment (a distinct bordered card, own header + stance badge) and asked for the same. Restructured: `#quick-summary-card` is now its own `.card` sitting above the Reasoning Trace card in `.dag-column` (which now sizes the two cards via flex — Quick Summary sizes to content, Reasoning Trace fills the rest). Header (icon + title + stance badge) lives in static HTML; JS only toggles visibility and the badge's text/class. One deliberate deviation from the mock: the mock's card showed "Holding Period: 2-5 Days" — checked, and no such range field exists anywhere in ATHENA (only a real historical *average*, `avg_holding_days`). Kept the honest "Avg Holding (Historical)" label instead of inventing a range to match the mock exactly.
- **Ticker auto-refresh.** Owner asked how often the ticker refreshes; answer was "never automatically" — no `setInterval` exists anywhere in this dashboard, every tab (including this one) only reloads on tab-switch or a manual refresh click. Owner asked for a timer. Added `startTickerRefresh()`/`stopTickerRefresh()` (60s interval), started when Decisions & Trace becomes active and stopped when leaving it — mirrors the existing `stopOpsStream()` start/stop lifecycle already used for the Operations tab's live stream. Deliberately scoped to the ticker only, not the decisions list/briefing (re-fetching those every tick would reset scroll position/selection, which wasn't asked for).
- **Quick Summary value formatting/coloring** (owner reference-mock screenshot, second review pass): Score and Confidence were showing band words ("Strong"/"HIGH") instead of raw numbers — changed to `75.1/100` and `93.7%` respectively. Risk was showing only the band word — changed to `Medium (42.9)`, colored by band (`tone-good-text`/`tone-warn-text`/`tone-bad-text`, the same utility classes the header ticker's positive/negative colors already use). R:R Potential was `2.00 : 1` (via the shared `formatDecisionRatio`, 2 decimals) — changed to one decimal (`2.0 : 1`) to match the hero cockpit gauge's own "EXPECTED R:R" formatting instead. Expected Return gained sign-based coloring (green/red). All values still come from the exact same `analysisPresentation`/`riskBand` computations the hero gauges already use — only presentation changed, no new number anywhere.
- **Holding Period (real range, not the mock's fabricated one).** Owner asked whether ATHENA can provide a real "Holding Period" in days like the mock's "2 - 5 Days". Checked: each returned analog already carries its own real `outcome_holding_days` (derived from a persisted trade's actual entry-to-exit time), and `DecisionsService._aggregate_analog_outcomes` was already collecting all of them in memory — just to average, never exposing the min/max. Added `min_holding_days`/`max_holding_days` to `DecisionAnalogsDTO`, computed from that same already-collected list (Priority 1/2 — no new provider, no new business logic, exposing more of an existing computation). Quick Summary's "Avg Holding (Historical)" row replaced with "Holding Period (Historical): 3 - 7 Days" (whole-day range across real analogs; collapses to one number if every analog held for the same length of time) — a genuinely real historical range, not a guess.

---

#### DT-3 — Tab restructuring (5 tabs) + spacing polish

Per the earlier owner-confirmed scope decision: split the old single "Decision History" tab into **Response** (Journal/Outcome only) and **History** (Decision Timeline + Similar past setups). No content deleted or invented anywhere — the same three sections (Journal, Decision Timeline, Analogs) were regrouped, not changed.

| | |
|---|---|
| Scope | **Frontend only** (pure presentation regrouping, no backend change): tabstrip button split (`index.html`) — "Decision History" → "Response" + "History", new `fa-clock-rotate-left` icon for History; `renderDecisionBrief()` template (`13-decision-brief-core.js`) — Decision Timeline moved out of the always-visible hero section (it was rendering on every tab, not just when reviewing history — a real instance of "vertical wasted space" per the owner's original assignment) into the new History tabpane; "Similar past setups" (Analogs panel) moved out of the Response tabpane into History, leaving Response with only the Journal/Outcome panel; `BRIEF_TAB_NAMES`/`BRIEF_TAB_LABELS` (`18-decision-brief-trace.js`) extended with `history` → "History". `STAGE_TAB_MAP` unchanged — no DAG stage currently maps to the response/history tabs. |
| Tests | ~35 new/updated dashboard-hosting assertions across all three rounds, plus 7 new backend tests (3 `instruments.name` roundtrip/migration tests including one that simulates a pre-migration db, 1 Kite-dump `name`-column parsing test, 3 `DecisionMetadataDTO.instrument_name` tests via an isolated `tmp_path` repo). Full suite **1042 passed** |
| Coverage | Live-browser verified: all 5 tabstrip buttons present in the correct order (`Trade Plan/Analysis/Market Context/Response/History`) with the correct labels; clicking the History tab correctly activates it (`switchBriefTab`); zero uncaught console errors beyond the expected unauthenticated-fetch logging. Full tabpane content (Timeline+Analogs actually rendering together under History) verified via the source-slice structural test — no live decision could be exercised end-to-end without owner credentials, same constraint as prior milestones. |
| Status | ✅ Approved (2026-07-27) |

**Spacing polish**: the concrete, high-value part of this — removing Decision Timeline from the always-visible hero — already shrinks the hero on every tab except History, directly addressing the original assignment's "Remove Vertical Wasted Space" principle. Did not speculatively tweak further CSS spacing without a concrete target (Trade Plan/Analysis/Market Context tabs were not touched) — per the established pattern this session (DT-1's filter-popover fixes, DT-2's formatting fixes), further spacing polish is best driven by the owner's own screenshot review of the live 5-tab layout, not guessed at.

**Refinement from owner screenshot review (2026-07-27), before final approval:** the owner shared the reference mock's own hero hierarchy (Recommendation+gauges card → collapsed Summary card with "View Details" → tab strip) against the live build, and asked for the same — the full Executive Summary bullet list ("Passed all 6 safety gates.", "composite 65.69 = weighted mean...", etc.) was still always-visible on every tab (same class of issue DT-3 had just fixed for Decision Timeline), and the ATHENA Recommendation banner sat below the tab strip/action bar instead of merged with the gauges above it.

- **Recommendation merged into the gauges row** as its own tile (stance badge + a qualifier band reusing the Score tile's own already-computed word, e.g. "Good Setup" — never a second, independently-derived label). Confirmed with the owner first: skip an "Expected Holding" gauge (same no-real-forward-looking-estimate conclusion as DT-2's Quick Summary), and leave the action bar's position unchanged.
- **Executive Summary collapsed into an "ATHENA Summary" card** — the same real one-line headline previously shown as the banner's reason text, plus a "View Details" button — sitting between the gauges row and the tab strip (matching the mock), instead of a permanently-visible bullet list repeating across every tab.
- **"View Details" opens the full bullet breakdown in a modal**, reusing the exact existing `openModal`/`closeModal` pattern already used for Compare/Chart/Backtest (Priority 1 — no new modal architecture), wired into the global Escape-key/`closeAllModals()` handling.
- The now-empty `.decision-brief-hero` wrapper (Banner + Executive Summary — Decision Timeline had already moved to the History tab earlier in this same milestone) was removed entirely from the per-decision render template; its dead CSS rule was deleted too.
- No backend touched, no content invented — same real headline, same real bullet computations, only repositioned and collapsed behind a click.

**Fix pass (same review):** the Recommendation tile initially shipped as a small stance-chip pill inside a plain dark tile — the owner pointed out the reference mock treats it as a fully stance-tinted highlight card (BUY in large bold green text, tinted green background), not just another gauge tile with a badge. Fixed: `.brief-gauge-recommendation` now takes the same `.stance-buy/-sell/-hold/-pass/-wait` class already used by `.decision-banner` and gets the identical radial-gradient tint treatment; the stance text itself reuses `.hero-metric-band` (same large-bold sizing as Score/Confidence/Risk's own band words) colored per stance, instead of a small `.stance-chip` pill.

**Identity row redesign (owner reference-mock screenshot, third review round):** the top identity row (crosshair icon + ticker + BUY/TRADE badges) redesigned to match the mock — star favorite toggle, company name, "EXCHANGE: SYMBOL" meta row, secondary actions consolidated into a "more" menu.

Researched every new element before building anything, per the Data Source Priority rule:

- **Company full name** ("Dixon Technologies (India) Ltd") — genuine gap, but a *fixable* one: Kite Connect's real instrument dump has always carried a `name` column, ATHENA's ingestion just discarded it. Owner approved the small ingestion change. Implemented: `Instrument.name` (domain model), `SCHEMA_VERSION` 8→9 with an idempotent `ALTER TABLE instruments ADD COLUMN name TEXT` migration (checked via `PRAGMA table_info`, so it safely reaches the *existing* production `db/athena.db` — `CREATE TABLE IF NOT EXISTS` alone is a no-op against an already-existing table), `kite_provider.py`/`file_provider.py` now read/store it, `DecisionMetadataDTO.instrument_name` looked up via a new optional `repo` on `DecisionsService` (same optional-repo-alongside-primary-abstraction precedent as `MarketHistoryService`). **Caveat surfaced to the owner**: the migration already ran against the real db (via the test suite's own real-db wiring) — 506 existing instruments preserved, `name` column added, all correctly `NULL` (never fabricated) since ingestion hasn't re-synced yet; real names populate automatically on the next Kite catalog refresh.
- **Sector** ("Consumer Durables") and **market-cap category** ("Smallcap") — genuine gaps with no fix available: nothing in ATHENA's domain model, database, or Kite's own instrument feed maps a symbol to either. **Owner decision: omit both, tracked as future scope** — the meta row gracefully holds just the one real pill ("NSE: DIXON") today and can take more later without a layout change.
- **Star favorite toggle** — reuses the existing "Saved Symbols" watch-list feature (UX-9b: `GET/POST/DELETE /api/v1/saved-symbols`), previously only a text-input list on Market Intelligence — Priority-2, no new backend, just a new UI surface with a local `Set` cache to avoid re-fetching on every selection.
- **BUY/TRADE badges dropped** from this row (owner-confirmed) — redundant with the Recommendation tile now shown prominently in the gauges row below.
- **Secondary actions moved into a "more" (⋮) popover** — Dismiss today/Remove candidate/Export/News (owner-confirmed which ones); Market Intelligence/Open Chart/Compare stay in the primary action bar. The moved buttons are the exact same elements (ids/classes/click handlers) relocated, not rebuilt — same toggle/backdrop-click/Escape pattern already established for the symbols filter popover.
- **Fix pass (same review):** the ticker ("DIXON") was rendering truncated to "DI…" once the company name sat next to it — flexbox was shrinking both siblings by default since neither had an explicit `flex-shrink`. Fixed: `.decision-brief-symbol-lg` gets `flex-shrink: 0` (the primary identifier must never lose space), `.decision-brief-company-name` is the one that truncates when space is tight.

**Second fix pass (owner live-session screenshots, same day):**

- **Confirmed company name is real and working**: the owner added a new symbol ("ETERNAL") and its real Kite-supplied name ("ETERNAL - ZOMATO" — the stock's actual post-rebrand name) rendered correctly. Investigated why *existing* symbols still showed no name: every scheduled cycle since restart (`--with-cycles`, 60s interval) has been failing at the exact point the instrument catalog gets rebuilt, due to a pre-existing (not introduced this session) invalid symbol `INFSDFSD` in `owner_candidates` (added 2026-07-26, doesn't exist on Kite) — `_ensure_catalog()` raises before any instrument upsert can run, so the catalog (and names) never re-syncs via the scheduler. New/re-validated symbols go through a different, unblocked path, which is why they picked up real names immediately. Flagged to the owner as a separate, pre-existing operational issue — not something fixed as part of this UI request.
- **Market Intelligence button removed entirely** from the identity row's actions — redundant with the sidebar's own "Market Intelligence" nav item, which already does the same `switchTab("market")`.
- **Open Chart / Compare relocated as icon-only buttons** next to Re-validate, in the sticky header-actions row — owner: "icons are also sufficient for these two." Same ids/click handlers, only the container/label changed. With all 3 action-bar buttons removed/relocated, `.decision-brief-actionbar` itself (HTML, JS refs, and CSS) was removed entirely — a further real vertical-space win, not just a relabeling.
- **Fix pass: "Expected R:R" tile text truncation.** With the Recommendation tile added earlier, 5 tiles sit in a 4-column grid — Expected R:R wraps alone onto row 2 but only got 1 of 4 columns' width there, truncating "reward per ₹1 risked" with empty space sitting right next to it. Fixed: `.decision-brief-gauges .brief-gauge:last-child { grid-column: 1 / -1; }` — it's always the last tile, so it now spans the full row.

**Third fix pass (owner live-session screenshot, same day):** company name was truncating on the identity row itself ("SANDHA…") — cramped next to the star toggle, ticker, as-of text, and the newly-added icon buttons, all competing for space in the center column's narrower width. Moved `#decision-brief-company-name` out of the identity row into the meta row (alongside "NSE: SANDHAR"), which has far more width to itself — confirmed via `scrollWidth === clientWidth` (no overflow) that "Sandhar Technologies Limited" now renders in full.

Re-confirmed sector/market-cap category are genuine gaps (re-checked `Instrument`, config, and Kite's exact dump columns a second time — nothing new). **Owner decision (reconfirmed): leave omitted, track as future scope** unless a real external source is identified later.

**Fourth fix pass — Symbols panel color system (owner-requested, same day), three iterations:**

1. Section headers (Trade/Watch/No trade/…) had no background at all — flush with the rows below, indistinguishable from each other.
2. First attempt: reused each section's raw alert-style `dot` color (`--success`/`--warning`) as a `color-mix()` full-block background tint — but those hues are calibrated for a tiny 8px dot, not a background: pure yellow (Watch) visually overpowered green (Trade) at the identical opacity, an imbalance the owner caught immediately on review.
3. Second attempt: balanced the hues with per-section hand-calibrated `tint`/`tintBorder` rgba — but even balanced, 3-4 stacked full-width solid color blocks read as "too much color" overall (owner: "so much of green, so much of yellow, so much of grey").
4. **Final fix**: switched from a full-block fill to a thin left-border accent + a barely-there background wash (`accent`/`wash` fields on `DECISION_CAROUSEL_SECTIONS` in `12-decisions-list.js`) — the same restrained pattern the Recommendation tile/ATHENA Summary card already use elsewhere. The owner's *next* screenshot then pointed at a related, pre-existing (not introduced this session) issue: individual `.symbol-row` rows already had a fully-opaque 3px left border using the same raw `--success`/`--warning` tokens via `decisionCardStanceColor()` — loud cumulatively across a dozen+ stacked rows. Fixed with the exact same muted `accent` rgba values as the headers, so the whole panel now shares one calibrated color system (header accent = row accent per section) instead of two independent, differently-intense color schemes. Hover state uses `filter: brightness(1.25)` (works against any inline background, no per-hue hover color needed).

**Fifth fix pass — individual row accent removed entirely, then divider added (owner-requested, same day):**

- Owner: "im not feeling good with this ui, can we remove opaque 3px left edge line from each symbol card as already we have it in the section header?" — not a further muting pass, a full removal: the section header already carries the color, so the row itself doesn't need to repeat it. `decisionCardStanceColor()` removed entirely (dead code, zero remaining callers checked), the `row.style.setProperty("--stance-color", ...)` wiring removed from `renderSymbolRow`, `.symbol-row` CSS changed to `border-left: 3px solid transparent` (width kept only to avoid a layout jump on `.active`, color gone).
- Owner: "and also remove the left edge 3px border for the selected symbol as well" — `.symbol-row.active`'s `border-left-color`/`border-left-width` overrides removed too; selection now reads entirely from the existing background gradient + full border-color + box-shadow glow, no left-edge accent anywhere in the panel.
- Owner: "this looks good but need subtle divider between symbols" — added `.symbol-row:not(:last-child) { border-bottom-color: var(--border-color); }`, reusing the existing `--border-color` token (no new color introduced).

---

#### DT-4 — Reasoning Trace vertical pipeline list + Similar Trades sparkline

**Part 1 — Reasoning Trace redesign.** Replaced the CSS auto-fit grid + JS-computed SVG connector lines (`drawDAGLines()`, using `ResizeObserver` + `getBoundingClientRect()` to draw `<line>` elements between card-style nodes — fragile once stages wrapped onto a second grid row) with a vertical stepper/timeline list: each stage is a horizontal row (circular icon-wrap + name/status body) connected by a pure-CSS rail (`.dag-node-rail::after`, a `2px` `var(--border-color)` line spanning to the next node) — no coordinate math, immune to wrapping. Same stage order, same click → `selectNode`/`showStageDetails` behavior, same status badge classes (`.meaning-good/-bad/-warn/-neutral`, `.completed/.passed/.failed`) — only the connective visual layer changed.

**Part 2 — Similar Trades sparkline.** Added a compact bar sparkline to the existing "Historical validation" card in the Analogs panel, showing the last 5 similar trades' realized returns. Built entirely from data each analog already carries (`DecisionAnalogDTO.outcome_return_pct`/`outcome_closed_ts`, already fetched by `loadDecisionAnalogs` into `activeAnalogs`) — no new endpoint, no new calculation, per the owner's earlier-confirmed "add the mini sparkline (Recommended)" decision. `analogSparklinePoints()` filters analogs with a realized outcome, sorts by close time, takes the 5 most recent, and orders them oldest-to-newest for a left-to-right trend read; `renderAnalogSparkline()` renders them as an inline SVG bar chart (height proportional to `|return|`, green/red by sign, reusing the same `--tone-good-text`/`--tone-bad-text` tokens the rest of the app already uses for pnl coloring) with a per-bar tooltip (`<title>`) showing the exact date and return %.

| | |
|---|---|
| Scope | **Frontend only** (no backend/DTO change — `outcome_return_pct` already existed on `DecisionAnalogDTO` from an earlier milestone, just unused until now). `18-decision-brief-trace.js`: `renderTraceDAG()` rewritten to build `.dag-node`/`.dag-node-rail`/`.dag-node-icon-wrap`/`.dag-node-body` markup; `drawDAGLines()` and its `ResizeObserver`/`setTimeout` callers removed entirely (dead code, zero remaining callers checked). `index.html`: `<svg id="dag-svg-lines">` removed. `12-decision-cards-dag.css`: `.dag-nodes-flow` grid → flex-column; new `.dag-node`/`.dag-node-rail`/`.dag-node-icon-wrap`/`.dag-node-body` rules; `.dag-svg-overlay`/`.dag-flow-line`/`.dag-flow-line-active`/`@keyframes dag-flow-dash` removed. `19-decision-brief-history.js`: `analogSparklinePoints()`/`renderAnalogSparkline()` added, called from `renderHistoricalValidation()`. `13-context-history.css`: `.analog-sparkline`/`.analog-sparkline-svg`/`.analog-sparkline-bar` (`.tone-good/-bad/-neutral`)/`.analog-sparkline-zero` added. |
| Tests | ~15 new/updated dashboard-hosting assertions (SVG/ResizeObserver artifacts confirmed gone, new `.dag-node-rail`/`.dag-node-icon-wrap`/`.dag-node-body` structure confirmed both in CSS and inside `renderTraceDAG`'s own function body via a source-slice check; `renderAnalogSparkline`/`analogSparklinePoints` confirmed present and wired into `renderHistoricalValidation` via the same source-slice technique). One caught-and-fixed test regression: an explanatory code comment containing the literal word "ResizeObserver" tripped the `not in js` assertion — narrowed to check for `new ResizeObserver` (actual instantiation) instead of the bare word. Full suite **1042 passed**. |
| Coverage | Live-browser verified both pieces via injected sample data (no owner credentials available for a real authenticated load, same constraint as prior milestones): pipeline list renders with the connecting rail, clicking a node sets the active state (accent-colored icon ring + glow + highlighted row background); sparkline renders bars scaled by return magnitude, colored green/red by sign. One rendering snag caught and resolved during verification: the browser had cached the *inner* `@import`-ed CSS file from before this milestone's edit (the outer `dashboard.css` link carries a cache-bust query param, but individual `css/*.css` imports don't) — a cache-bypassing fetch confirmed the new CSS rules were correctly on disk and would apply on a real hard-reload; not a code defect. Zero uncaught console errors from the new code (only the expected unauthenticated-fetch logging already present in every prior milestone's verification). |
| Status | ✅ Approved (2026-07-27) |

---

### PROPOSAL — Scoring differentiation & unwired engine inputs (owner-reported, 2026-07-29)

**Status: proposal only. No code written. Awaiting owner approval before any implementation.**

Owner report: "values like score, risk, confidence are same for all the
symbols until unless i click re-validate." Audited against the live
`db/athena.db`, batch run `run-refresh-20260729T091348-73723088`
(363 symbols). **The report is correct, and it is a backend data defect,
not a UI defect.**

#### Audit evidence

Persistence and the API read path are healthy: all 363 decisions resolve
to their own `decision_reports[decision_id]` entry, so the 2026-07-26
run_id-collision class of bug is **not** recurring here. The frontend is
also clear — `selectBriefing` nulls `activeDepth` and `loadDecisionDepth`
carries a correct `activeDecisionId !== decisionId` race guard. The
persisted values themselves are genuinely near-identical:

| Metric | Distinct values across 363 symbols |
|---|---|
| `risk.overall` | **2** — 328 symbols at 45.67, 35 at 61.67 |
| `confidence.overall` | 10 |
| `score.composite` | 21 |

Risk's degeneracy is mathematically forced, and was verified as an exact
1:1 mapping: of its six dimensions, two are permanently UNKNOWN
(`event_risk`, `concentration_indicator`), three are identical for every
symbol because they derive from index-wide regime/market health
(`volatility_risk` 50, `gap_risk` 70, `market_environment_risk` 48.75),
and exactly one varies (`liquidity_risk`, a binary 20-or-80 volume
threshold). One binary input can only produce two outcomes. Confidence
degenerates the same way: three constant dimensions, one permanently
UNKNOWN (`data_freshness`), and only `cross_engine_agreement` and
`consistency` moving.

Re-validate does not correct anything — it re-runs one symbol at a newer
timestamp against fresher intraday data, so that symbol may cross a band
boundary and merely *look* distinct. Observed: ZEEL scored 65.00 in the
09:13 batch and 63.24 when re-validated at 09:31.

#### Root cause: three engine inputs that are accepted but never passed

| # | Engine parameter | Original consequence | Current status |
|---|---|---|---|
| D-1 | `RiskEngine.assess(calendar_context=...)` | `event_risk` permanently UNKNOWN | ✅ Closed — `CalendarContext` now threaded from `OwnerValidationPipeline.run()` |
| D-2 | `RiskEngine.assess(universe=...)` | `concentration_indicator` permanently UNKNOWN | ✅ Closed — `UniverseResult` now threaded, with scoped re-validate fix using last full-cycle breadth |
| D-3 | `ScoringEngine.score(sector_health=...)` | `sector_quality` (**weight 15 of 100**) permanently UNKNOWN for every symbol ever scored — every report shows `completeness: 0.85` | ⏳ Blocked — see sector data decision below |

D-1 and D-2 are now closed. `OwnerValidationPipeline.run()` threads the
existing `CalendarContext` and `UniverseResult` into `_scan_eligible()`,
which passes them into `RiskEngine.assess()`. The follow-up scoped
re-validate bug is also fixed: scoped runs use the last real full-cycle
universe breadth for `concentration_indicator`, and regime/gap context
uses real configured index candles instead of falling back to an
arbitrary stock. No new data source, no contract change.

**D-3 is blocked on data, not on wiring.** `SectorHealthEngine` was built
and approved under M2.3 and `config/sector_health.json` exists, but its
trend/momentum/volatility dimensions consume a *sector index* candle
series, and the repository holds candles for only three non-equity
instruments: `NSE:NIFTY 50`, `NSE:NIFTY BANK`, `NSE:INDIA VIX`. No
sector indices (NIFTY IT, NIFTY PHARMA, …) are ingested. Sector
*metadata* is present and good (`instruments.sector`, 15+ sectors, only
10 nulls), so a constituent-derived sector aggregate is feasible — but
that is a new computation method, not the approved M2.3 engine, and
would need its own design decision.

#### Expected impact of enabling `sector_quality` — this is the risk

Because the composite is a weighted mean over *known* components only,
enabling a weight-15 dimension rescales every score in the system:
`new = 0.85 × current + 0.15 × sector_value`. Modelled against the 363
live decisions (current mix: TRADE 159, WATCH 167, NO_TRADE 37):

| Sector value | Resulting mix | Symbols whose decision changes |
|---|---|---|
| 20 (weak sector) | TRADE 70, WATCH 203, NO_TRADE 90 | **142 / 363 (39.1%)** |
| 50 (mixed sector) | TRADE 149, WATCH 177, NO_TRADE 37 | 10 / 363 (2.8%) |
| 80 (strong sector) | TRADE 203, WATCH 155, NO_TRADE 5 | 76 / 363 (20.9%) |

**218 of 363 symbols (60.1%) would have their TRADE/WATCH/NO_TRADE band
determined by their sector score alone.** This is not a cosmetic change
and must not ship without owner sign-off on the recalibration.

#### Proposed milestones (small, independently reviewable)

| Milestone | Scope | Gate | Status |
|---|---|---|---|
| **SD-1** Wire calendar + universe into Risk | Thread the existing `CalendarContext` and `UniverseResult` from `run()` into `_scan_eligible()` → `RiskEngine.assess()`. Activates `event_risk` and `concentration_indicator`. Includes the approved follow-up fix for scoped re-validations: use last full-cycle breadth for concentration and real configured index candles for regime/gap context. Note: `concentration_indicator` is universe-breadth-derived and therefore shared across symbols — it raises risk *completeness* and honesty, it does **not** add per-symbol differentiation. Only `event_risk` can vary per symbol, and only on instruments with calendar events | None — existing objects, existing parameters, no contract/schema change | ✅ Completed / approved (2026-07-29) |
| **SD-2** Sector health data decision | Owner decision, not an AI call: either (a) ingest real NSE sector indices via Kite (new data source → **DD-gated**), or (b) derive sector aggregates from the constituent candles already held, using `instruments.sector` (new method → needs a design decision / ADR since M2.3's engine contract assumes an index series) | **DD or ADR** depending on option chosen | ⏳ Proposed — blocked on owner direction |
| **SD-3** Wire sector_quality + recalibrate thresholds | Only after SD-2 lands. Pass `sector_health` into `ScoringEngine.score()`, then re-tune `config/decision.json` watch/trade thresholds against the impact table above so the change doesn't silently reclassify 20–39% of the book. Ships with a before/after replay diff | Config change to decision thresholds — **owner approval required** | ⏳ Proposed — blocked on SD-2 |
| **SD-4** Scoring granularity (continuous ramps) | Replace RSI/liquidity/ADX step functions with anchor-preserving linear ramps. Distinct composite scores rise from 21 → 248 across the live book. `technical_structure` deferred (needs a normalizing band with no existing anchor). | Config: `adx.weak`, `liquidity.low_volume_floor_ratio` | ✅ Completed / approved (2026-07-29) |

#### SD-1 consequence found during implementation: `max_risk_for_trade` was tuned against an incomplete denominator

Modelled against all 363 live decisions with a simulator validated to
reproduce the persisted risk values and TRADE/WATCH/NO_TRADE split
**exactly** (0 mismatches on 363 rows, baseline 153/173/37).

Risk is a weighted mean over *known* dimensions only. With two of six
dimensions permanently UNKNOWN, the divisor was 75 of 100 weight, which
inflated every risk score. Completing the vector adds two genuinely
low-risk inputs (`event_risk` 20 on a normal day, `concentration_indicator`
30 for a diversified universe) and mechanically deflates the result:

| | risk (liquid names) | risk (illiquid names) | RISK gate at max 60 |
|---|---|---|---|
| Before SD-1 | 45.67 | 61.67 | 35 symbols fail |
| After SD-1, normal day | 40.25 | 52.25 | 0 fail |
| After SD-1, expiry | 47.75 | 59.75 | 0 fail |
| After SD-1, scheduled events | 49.25 | 61.25 | 35 fail |

**The `max_risk_for_trade: 60` threshold was implicitly calibrated
against the incomplete 4-dimension scale.** Shipping the wiring alone
therefore silently *loosens* the trade gate: 6 symbols flip WATCH → TRADE
(AIIL, APLAPOLLO, CREDITACC, JSL, LALPATHLAB, MANKIND) — all of them
names whose 20-week volume sits just under the 500k liquidity floor
(CREDITACC is 485,186, a 3% shortfall). These would become live BUY
setups on the least liquid stocks in the book.

Strictness-preserving recalibration: **`max_risk_for_trade: 60 → 50`**
reproduces today's exact pass/fail partition across all three calendar
scenarios (40.25/47.75/49.25 pass; 52.25/59.75/61.25 fail). Owner
approved this risk-appetite choice and the live config now uses 50.

#### SD-4 — continuous scoring (design approved, implemented 2026-07-29)

Even with all three inputs wired, per-symbol differentiation stays
chunky, because `config/scoring.json` collapses continuous signals into
a handful of fixed buckets:

| Component | Weight | Current mapping | Distinct values observed |
|---|---|---|---|
| `momentum` | 20 | RSI → 3 buckets at thresholds 40 / 60 (20 / 50 / 80 pts) | 3 |
| `liquidity` | 10 | Volume MA vs a single 500k threshold (30 / 70 pts) | 2 |
| `technical_structure` | 15 | Above/below MA (30 / 70) + fixed MACD bonus 10 | 4 |
| `trend` | 20 | Index regime label + fixed ADX>25 bonus 10 | 2 |
| `market_quality` | 20 | Index-wide — **identical for all 363 symbols** (51.25) | 1 |

A symbol at RSI 40.1 and one at RSI 59.9 receive the exact same 50
momentum points, and a symbol at RSI 59.9 versus 60.1 jumps a full 30
points on a rounding-width difference — the bands are simultaneously too
flat inside and too cliff-edged at the boundary.

**Approved design (implemented 2026-07-29).** Replace the step functions
with linear ramps that pass exactly through the anchor values already in
`config/scoring.json`, so this is a strict refinement of the existing
calibration rather than a re-weighting:

- **momentum** — `pts = 20 + 3 × (RSI − 40)`, clamped to `[20, 80]`.
  This reproduces all three configured anchors exactly: RSI 40 → 20
  (`weak_points`), RSI 50 → 50 (`mid_points`), RSI 60 → 80
  (`strong_points`). **No new config field required.**
- **liquidity** — ramp the volume ratio `vma / min_volume_ma` from 0.5×
  to 1.0× across `low_points` → `ok_points` (30 → 70), preserving the
  anchor at exactly 1.0× → 70. Requires **one new config field** for the
  lower ratio bound (proposed `low_volume_floor_ratio: 0.5`).
- **trend (ADX bonus)** — ramp `0 → bonus` across ADX 15 → 25 instead of
  a binary switch at 25, preserving the anchor at ADX 25 → full bonus.
  Requires one new config field for the lower bound.
- **technical_structure** — deferred. Making MA distance continuous needs
  a normalizing band (likely ATR-relative) that has no existing anchor to
  preserve, so it is a genuine calibration decision rather than a
  refinement. Left discrete pending its own proposal.

**Replayed against all 363 live decisions** (momentum + liquidity ramps):

| | current | proposed |
|---|---|---|
| distinct momentum values | 3 | **232** |
| distinct liquidity values | 2 | **34** |
| distinct composite scores | 21 | **248** |
| band mix | TRADE 159 / WATCH 167 / NO_TRADE 37 | TRADE 159 / WATCH 149 / NO_TRADE 55 |

34 of 363 symbols (9.4%) change band. The direction of travel is
correct in both tails — it penalises names that are genuinely weak but
currently hidden inside the flat mid-band, and rewards genuinely strong
ones:

| Symbol | Input | Current | Proposed | Score |
|---|---|---|---|---|
| NSE:APLAPOLLO | volume MA 497,699 (0.5% under floor) | liquidity 30 | 69.6 | 60.29 → 69.65 |
| NSE:CREDITACC | volume MA 485,186 | liquidity 30 | 67.6 | 69.71 → 74.13 |
| NSE:NTPC | RSI 40.02 (at the weak edge) | momentum 50 | 20.1 | 60.29 → **53.25, drops out of TRADE** |
| NSE:SAILIFE | RSI 59.86 (at the strong edge) | momentum 50 | 79.6 | 58.53 → 67.35 |

NTPC is the clearest illustration: at RSI 40.02 it sits a fifth of a
point above the weak threshold, is currently scored as mid-band, and
clears the trade level on that basis. Under the ramp it scores as what
it is — barely-not-weak — and correctly falls out of TRADE.

Owner approval was required because this changes 9.4% of decisions and
adds two config fields; approval was received before implementation.

**Implemented and approved 2026-07-29**: `_linear_ramp` in
`scoring/engine.py`; `adx.weak: 15.0` and `liquidity.low_volume_floor_ratio:
0.5` added to config + models; RSI `mid_points` validated as the honest
mid-band anchor on the continuous ramp. Six new anchor/ramp regression
tests in `tests/decision/test_scoring.py`. Full suite 1107 passed at the
time of implementation; focused SD regression tests currently pass.

---

#### Migration / re-validation plan (applies to SD-3 and SD-4)

Any change to scoring output makes every already-persisted decision
non-comparable with new ones. SD-4 is now implemented, so operational
use should start from a clean book: take a repository backup via the
existing backup path, use the existing "Clear all" admin utility, then
run a fresh full validation. Apply the same clean-slate approach when
SD-3 eventually lands, because sector-quality wiring will also change
score comparability.

#### Incidental finding (not the reported bug, not fixed)

`loadDecisionDepth`'s catch block calls `renderDecisionDepth(null)` but
not `renderSidebarQuickSummary()`, so a depth-load *failure* can leave
the right-rail quick summary showing the previously selected symbol's
numbers. Not the cause of the owner's report (all 363 depth loads
resolve successfully), but worth folding into whichever milestone
touches this file next.

---

#### Fix pass: scoped re-validate inflated risk via concentration_indicator (owner-reported, 2026-07-29)

Owner: "im seeing risk value of 31.3 for most of the symbols which are
exist in the decision list... if i re-validate again, then the risk
value changes." Two distinct findings:

1. **31.3 for most symbols during a full cycle — by design, not a bug.**
   4 of the Risk Engine's 6 dimensions (`volatility_risk`, `gap_risk`,
   `market_environment_risk`, `concentration_indicator`) are inherently
   market-wide — identical for every symbol scanned in the same cycle by
   design (they measure market conditions, not stock-specific ones).
   Only `liquidity_risk` genuinely varies per symbol, and it's a coarse
   binary (below/above a volume threshold), so most similarly-liquid
   stocks converge on the same overall weighted risk.
2. **Re-validating changes the value — a real bug, and a gap SD-1 didn't
   catch.** A `symbols_filter`-scoped run (single-symbol Re-validate /
   Add & validate) narrows the universe scan to just that one
   instrument, so `concentration_indicator`'s "eligible instrument count"
   collapses to 1 → always `concentrated_risk` (70, HIGH), regardless of
   real market breadth. Confirmed directly against `db/athena.db`: a
   scoped TCS re-validate showed `concentration indicator 70 (1 eligible
   instruments)` — an artifact of that call's own narrow scope, not of
   the market. SD-1's own before/after modeling assumed the diversified
   (30) case throughout, since it was validated against full-cycle data;
   it never exercised the scoped single-symbol path.

Owner-approved fix: reuse the last real FULL (unscoped) cycle's universe
breadth for concentration purposes when this run is itself scoped, never
fabricate one when no prior full cycle exists yet (ADR-005).

| | |
|---|---|
| Scope | `owner_validation.py`: `detail["universe_scope"]` (`"full"`/`"scoped"`) added to the persisted run detail; new `_last_full_universe_summary()` — scans `list_runs()`/`get_run_detail()` for the most recent COMPLETED/DEGRADED run marked `"full"`, returns its real `universe_summary` wrapped in a new `_UniverseSummaryStandIn` (duck-types `UniverseResult` for `RiskEngine._concentration_indicator`, which only reads `.summary`); `_scan_eligible` computes `concentration_universe` once per call — the scan's own `universe_result` when unscoped, `_last_full_universe_summary()` when `symbols_filter` is set — and `risk_stage` now passes that instead of the raw scoped result. |
| Tests | 2 new regression tests: a scoped re-validate reuses the prior full cycle's real breadth (not its own 1-symbol scope); with no prior full cycle, concentration is honestly `UNKNOWN`, never fabricated. Full suite **1109 passed** |
| Coverage | Verified against real production `db/athena.db`: a scoped TCS re-validate went from `concentration_indicator: 70 (HIGH, "1 eligible instruments")` to `UNKNOWN` (`_last_full_universe_summary()` correctly found no prior run carrying the new marker — honest degradation, not a crash); overall risk dropped from the inflated 42.75 to 39.72, completeness 0.9 (5/6 known). |
| Status | ✅ Fixed, superseded by two follow-ups below |

**Follow-up 1 — the fix above never actually fired in production (owner re-tested, still broken).** `_last_full_universe_summary()` checked `detail.get("universe_scope")` at the top level of a run's persisted `detail_json` — correct for a direct test call, but `DryRunCycleOrchestrator.run_cycle()` (`scheduling/dry_run.py`, the real code path behind both the scheduled cycle and the "Run Full Validation" button) persists this pipeline's own returned dict nested one level down, under a `"pipeline"` key, alongside `"phase"`/`"duration_seconds"`/`"ingestion"`. Every real production run's marker lived at `detail["pipeline"]["universe_scope"]`, which the lookup never checked, so it always fell through to `None` — concentration stayed `UNKNOWN` forever, and its low-risk anchor being dropped from the weighted mean was still inflating individual re-validate risk versus the full cycle. Fixed: `_last_full_universe_summary()` now checks the nested `"pipeline"` shape first, falling back to flat for direct callers (tests). New regression test locks in the real nested shape specifically. Verified against `db/athena.db` after a required server restart: a scoped ZENSARTECH re-validate's `concentration_indicator` went from `70 (HIGH)` to the real full cycle's `30 (LOW, "362 eligible instruments")`.

**Follow-up 2 — a second, deeper bug found while diagnosing the first: `gap_risk` differed between a full cycle and a re-validate even after Follow-up 1, with every other dimension identical.** Root cause, found via direct dimension-by-dimension comparison: `_scan_eligible` resolved its regime-benchmark index as `index_id = next(iter(snapshot.indices.keys()))` — but `MarketSnapshot.indices` keys are bare labels (`"NIFTY 50"`), while the `candles` table stores everything under the full instrument_id (`"NSE:NIFTY 50"`). `self._repo.list_candles_recent("NIFTY 50", ...)` (no prefix) always returned zero rows, so the code fell through to its last-resort fallback — `candles_by_id.get(included_ids[0], ())` — **an arbitrary individual stock's own candles standing in for "the market index."** Which stock won depended entirely on scan scope: the first eligible symbol (alphabetically/whatever order) in a 362-symbol full cycle, versus the target symbol itself in a single-symbol re-validate — silently fabricating a different "market regime" reading every time, the opposite of ADR-005. Confirmed directly: the full cycle's "index candles" showed a price series around ₹1,130 (some unrelated stock); the ZENSARTECH re-validate's showed ₹524–533 (ZENSARTECH's own price) — neither is NIFTY 50 (~24,000).

Fix: new `_resolve_index_candles()` — always tries the configured index instruments (`config/providers/kite.json`'s `index_instruments`, correctly prefixed) in order via the repo, requiring genuine candle history before accepting one; never falls back to an unrelated instrument's own candles. Shared by both `_scan_eligible` and `_maybe_regime` (removing a near-duplicate second copy of this same resolution logic). 2 new regression tests (resolves the real index, not a random stock; honestly empty — not fabricated — when no index data exists at all). Full suite **1112 passed**.

**Final verification (both follow-ups together, real production data, post-restart):** a full cycle and a scoped ZENSARTECH re-validate now produce **identical** risk across all 6 dimensions — `volatility_risk 50, liquidity_risk 20, gap_risk 70, event_risk 20, market_environment_risk 41.25, concentration_indicator 30` — both landing on **overall risk 38.75**. (Note: `gap_risk 70`/GAP_UP is the mathematically correct reading of NIFTY 50's real open-vs-prior-close, 0.75% against a 0.5% threshold — the earlier `NO_GAP` some runs showed was itself wrong, an artifact of the random-stock substitution, not a legitimate alternate reading.)

| | |
|---|---|
| Scope | `owner_validation.py`: `_last_full_universe_summary()` checks the nested `"pipeline"` detail shape; new `_resolve_index_candles()` replacing the broken snapshot-label-based index resolution in both `_scan_eligible` and `_maybe_regime` |
| Tests | 3 new regression tests (nested-shape lookup; real-index-not-random-stock; honest empty with no index data). Full suite **1112 passed** |
| Coverage | Verified against real production `db/athena.db` after each fix, and again with both together: full cycle vs. scoped re-validate now match on every one of the 6 risk dimensions, not just concentration |
| Status | ✅ Fixed (2026-07-29) |

---

*Status legend: a milestone is "In Progress" (🔄) when actively being designed or built, "Approved" (✅) only when the owner signs off. Never two milestones in flight.*
