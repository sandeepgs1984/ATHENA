# ATHENA — Agent Briefing

**Read this file first, in every session, before touching any code or docs.**
It is a map, not a snapshot: it tells you what ATHENA is and exactly where to
look for facts that change over time. Nothing about *current status* is
hardcoded here — status lives in `docs/MILESTONES.md` and
`IMPLEMENTATION_SUMMARY.md`, and this file always defers to them.

---

## 1. What ATHENA is (stable — rarely changes)

ATHENA is a **single-user, advisory-only decision-intelligence platform** for
one trader's NSE/BSE swing and intraday equity trading. It is not a screener,
not a bot, and **never places or executes trades**. It ingests market data,
runs a deterministic analytical pipeline (regime → market health → evidence →
indicators → score → confidence → risk → decision), and produces fully
explainable `Decision` objects (TRADE / WATCH / NO_TRADE / etc.) with a
persisted reasoning trace. The owner reads the Decision Brief, decides, and
executes manually through their own broker. The "learning engine proposes,
the trader approves" — ATHENA never acts autonomously on capital.

## 2. Non-negotiable invariants (frozen — do not weaken, ever)

- **No order-placement code anywhere in this repo.** Not a flag, not a
  "future" stub, not behind a feature flag. Grep for it before you trust a
  claim that it doesn't exist.
- **Every number ATHENA shows is explainable.** Explanations are computed and
  *persisted as data* by the engine that produced the value (ADR-005) — the
  API/dashboard render only; they never reconstruct or recompute a rationale.
- **Deterministic and replayable.** Injected clocks, `Decimal` money,
  timezone-aware timestamps, no hidden state, no `random`/`datetime.now()`
  inside analytical engines.
- **Provider independence.** Broker/price-data concerns live behind
  `MarketDataProvider`/broker abstraction Protocols (ADR-002);
  institutional cash-flow (FII/DII) is a separate Protocol under ADR-008
  — business logic never imports a concrete provider.
- **Architecture is FROZEN.** `ATHENA-002-System-Blueprint.md` is the single
  source of truth for module boundaries. A genuine architectural limitation
  means: stop, write an ADR proposal, wait for owner approval — never
  silently work around it.
- **Secrets live only in `.env`** (gitignored). Never in `config/*.json`,
  never committed.

## 3. Orientation checklist — do this before any work

1. Read this file (you're doing it).
2. Read `CLAUDE.md` (a.k.a. `AGENTS.md`) — the mandatory process rules:
   git-action restrictions, commit message format, milestone workflow,
   implementation discipline. These override your default behavior.
3. Read `docs/MILESTONES.md` in full (it's compact) — the live roadmap. It
   tells you what's Approved, what's Ready for review / In design, what's
   Deferred, and what (if anything) is currently in flight. **Never assume a
   milestone's status from memory, from IMPLEMENTATION_SUMMARY.md's title,
   or from this briefing — this table is the only authority.**
4. Read the **top entry only** of `IMPLEMENTATION_SUMMARY.md` (newest-first
   log) for the full detail of the most recent milestone: scope, files
   touched, tests, risks, remaining work. Do not read the whole file — it is
   a permanent, ever-growing history (100K+ words), not a briefing document.
5. Run `git log --oneline -20` and `git status` to see what's actually
   committed vs. still sitting in the working tree, and cross-check against
   step 3/4 — the docs are updated by the AI before commit, so a milestone
   can be documented as done before the user has actually committed it.
6. Only then start work — and only on the single milestone the owner has
   authorized. If asked to "continue" or "what's next," answer from steps
   3–5, don't guess.

## 4. Governing documents — what's in each, and when to open it

| Document | What it contains | Open it when... |
|---|---|---|
| `ATHENA-000-Master-Architecture.md` | The constitution: why ATHENA exists, product philosophy, what it must never do | You need to justify a product-level decision or check a first-principles rule |
| `ATHENA-001-Engineering-Review.md` + `ATHENA-001R-Owner-Review.md` | Engineering review across 7 roles, disagreements resolved, accepted amendments | You need the *reasoning* behind an engineering rule (referenced as "ATHENA-001 amendment N") |
| `ATHENA-002-System-Blueprint.md` + `ATHENA-002R-Owner-Review.md` | The frozen architecture: module boundaries, phase plan, Definition of Done per phase | Before writing **any** code — confirm the relevant section and Definition of Done |
| `docs/adr/ADR-0*.md` | Architecture Decision Records: modular monolith, broker abstraction, pipeline context, static-HTML-first, explainability-as-data, circuit limits, owner-triggered background validation, institutional-flow provider (ADR-008 Accepted), repository read-concurrency (ADR-009 Accepted), DarvaX satellite module (ADR-010 Accepted, + Amendment 1 dashboard tab Accepted, Amendment 2 universe screening Accepted), canonical symbol master + scanner-specific universes (ADR-011 Accepted 2026-08-15), isolated Explosive Move Radar research boundary (ADR-012 Accepted 2026-08-21), and Entry Qualification architecture boundary (ADR-013 Accepted 2026-09-02) | You're unsure whether a pattern is intentional or need to cite the decision that made it so |
| `docs/decisions/DD-*.md` | Deferred Decision resolutions (e.g. DD-1 broker/data vendor = Zerodha Kite Connect, DD-9 alerting = webhook+file, DD-11 FII/DII institutional flow) | Before assuming something is "still undecided" — check here first, it may already be resolved |
| `docs/design/F5-MARKET-HEALTH-SCORE.md` | Exact F-5 six-component Market Health Score contract (formulas, unknown-data policy, persistence, consumer alignment) | Changing F-5 formulas/weights/unknown-data policy, or debugging Market Summary Unavailable states |
| `docs/design/DARVAX-CONFIGURATION.md` | Complete `config/darvax.json` reference: the ATHENA/DarvaX ownership boundary (ATHENA reads only `enabled`), enable/disable procedure, every key with default + range + deck provenance, which blocks are omitted-but-live, methodology-digest implications, and every failure mode | Turning the DarvaX satellite on or off, changing any DarvaX parameter, or diagnosing why DarvaX did or didn't mount |
| `docs/design/DARVAX-PERFORMANCE-EVIDENCE.md` | DX-4a measured evidence: what mounting DarvaX costs ATHENA (nothing detectable), what a scanning DarvaX costs at realistic vs worst-case cadence, the state-ordering confound and how it was controlled, and why no mitigation is recommended | Judging whether an enabled DarvaX is affecting ATHENA responsiveness, or before proposing any DarvaX isolation/queueing work |
| `docs/design/DARVAX-VALIDATION-EVIDENCE.md` | DX-5 validation: why DarvaX's `EXPERIMENTAL_UNVALIDATED` label still stands, the sufficiency gate that enforces it, the measured 1%-vs-10% stop comparison, and the `ingestion.lookback_days` blocker | Before trusting any DarvaX signal, or before proposing that the experimental label be removed |
| `docs/design/SYMBOL-UNIVERSE-INVESTIGATION.md` | Why the scanner universe is 528 symbols and not the NSE equity list: the `owner_candidates` → ingest → `instruments` chain, what the Kite dump can and cannot classify (no series column; `instrument_type` is `EQ` for all 10,197 rows), the 365-day question answered, and the three-symbol validation results | Before changing any universe, eligibility filter or ingest scope, or when asking why a symbol a scanner should see is invisible to it |
| `docs/ATHENA-DARVAX-UX-ROADMAP-HANDOFF.md` | Agent handoff for picking up the UX roadmap: the mandatory read order, non-negotiable invariants restated for a fresh session, the Design→Implement→Test→Review workflow, and a "gotchas paid for the hard way" section (DarvaX test-database isolation, asset-version cache-busting, a JS escaped-em-dash string-matching trap, a duplicate-function-declaration bug, and a local-preview charset/viewport false-alarm) | You are a new agent (or session) about to start implementing a UX roadmap item and need the full context in one place |
| `docs/design/ATHENA-DARVAX-UX-ROADMAP.md` | 29 advisory-dashboard UX improvement ideas spanning ATHENA core and the DarvaX satellite, each checked against a code survey of what already exists (notifications, decision-compare, saved symbols, search, responsive coverage, personalization, the Decision Journal/outcome tracker, onboarding, keyboard shortcuts, ATHENA↔DarvaX cross-linking) so nothing reproposes a feature that's already built. A menu for the owner, not a plan — nothing here is scheduled | Deciding whether a UX idea already exists in some form before proposing it, or picking the next UX milestone |
| `docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md` | Accepted research-first EMR sequence, evidence and promotion gates, explicit train/validation/calibration/final-test discipline, performance-isolation requirements, and current EM handoff | Starting or reviewing any Explosive Move Radar milestone; confirm the current status in `docs/MILESTONES.md` first |
| `docs/ATHENA-EMR-HANDOFF.md` | Dated EMR continuity snapshot: approved milestones, measured evidence, frozen research boundaries, mandatory read order, and the exact next-milestone scope | Resuming EMR work in a new agent or session after confirming current status in `docs/MILESTONES.md` |
| `docs/ATHENA-ID-TRACK-HANDOFF.md` | Dated Intraday Intelligence (ID-track) continuity snapshot: approved milestones ID-0 through ID-5G.1, frozen boundaries, ID-5B's pending live-session scope and CASE A/B/C/D classification framework, and a verified cross-track isolation finding vs. EMR | Resuming ID-track work in a new agent or session, and mandatory reading (alongside `docs/ATHENA-EMR-HANDOFF.md`) before either track's Monday-dependent live-session milestone (ID-5B / EM-5 Track B) |
| `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md` | EM-5 live-scanner design contract (proposed 2026-08-28, pending Owner approval): frozen-artifact promotion/loading, the exact state-transition table, eligibility/feasibility gates, ranking/probability-language rules, bulk-data/isolation design (mirrors DarvaX's ADR-010 pattern), replay determinism, performance/canary gates, persistence schema, and required tests | Before writing any EM-5 scanner code, or reviewing/approving that contract |
| `docs/research/EM-1A-DATA-COVERAGE-AUDIT.md` | Measured production-ledger coverage, survivorship and corporate-action risks, intraday integrity findings, frozen event/checkpoint contract, and the remediation gate that currently leaves zero checkpoints accepted | Reviewing EM-1a or deciding whether EM-1b can safely generate labels |
| `docs/research/EM-1R2-CORPORATE-ACTION-COVERAGE-CONTRACT.md` | Frozen official-NSE authority, survivor-cohort, identity-resolution, exclusion, and replay rules for EM-1r2 | Working on EMR corporate-action acquisition or downstream event-window admission |
| `docs/research/EM-1R2-CORPORATE-ACTION-COVERAGE-REPORT.md` | Measured EM-1r2 interval, cohort, actions, exclusions, replay evidence, and limitations | Reviewing EM-1r2 status or handing off to the next EM remediation milestone |
| `docs/design/EM-1-RESEARCH-DATA-REMEDIATION-PLAN.md` | Approval-gated EM-1r sequence for authoritative corporate actions, canonical intraday sessions, point-in-time cohort/quote hygiene, provenance, and checkpoint re-admission | Reviewing EM-1r1 or designing any EM data-remediation milestone before EM-1b |
| `docs/research/PS-P0-PORTFOLIO-SYNC-DISCOVERY-REPORT.md` + `docs/research/PS-P1-PORTFOLIO-CONTRACT-DESIGN.md` + `docs/research/PS-P2-PORTFOLIO-IMPORT-RECONCILIATION.md` + `docs/research/PS-P3-MY-PORTFOLIO-DASHBOARD-UX.md` + `docs/research/PS-P4-PORTFOLIO-SYNC-ORCHESTRATION.md` | Portfolio Sync / My Portfolio discovery, frozen contract design, import/reconciliation implementation, dashboard upload UX, and background sync orchestration: isolated source of truth, CSV/XLSX preview, canonical symbol resolution, atomic confirmation, stale-preview recovery, immutable analysis snapshots, factual current-holdings display, server-owned valuation math, expected-session freshness/provenance, coherent Decision/TradePlan evidence, nullable methodology fields, and 20-column Portfolio Snapshot DTO | Starting or reviewing any My Portfolio / Portfolio Sync milestone; confirm current PS status in `docs/MILESTONES.md` first |
| `docs/ATHENA-TECHNICAL-ARCHITECTURE.md` | Complete implementation reference: full tech stack, backend architecture (domain model, config system, provider abstraction, persistence, calendar, observability, explainability-as-data), the real decision-pipeline module map (with corrections to the "17 Protocol interfaces" and "11-stage pipeline" framings), the API layer (auth, versioning, error model, the DarvaX satellite-mount pattern), the frontend (static HTML/vanilla JS assembly, the actual chart stack vs. the aspirational "Lightweight Charts" docs), testing/tooling/ops, and a dedicated "known documentation/implementation gaps" section | You need to know how ATHENA is actually built rather than how a formula works, are onboarding to the codebase, or are about to state a claim about the stack/architecture that this document can verify or correct |
| `docs/ATHENA-WORKFLOW-METHODOLOGY.md` | End-to-end reference: full 11-stage decision pipeline with every formula/threshold/weight currently in config, scheduling cadences, dashboard workflow, and an explicit "Known Gaps" section (declared-but-dormant code paths, proposed-but-unimplemented ADRs) | You need the exact current formula/threshold for any engine, or want to know what's actually live vs. only declared in the architecture, without re-deriving it from source |
| `docs/api/openapi.yaml` + `postman_collection.json` + `API-REFERENCE.md` | The full REST API surface (81 operations, generated from the live `/api/openapi.json`), a ready-to-import Postman collection, and a human-readable walkthrough (auth flow, envelope/error model, per-resource examples) | Integrating against the API, or checking a route/parameter/schema exists — regenerate from `/api/openapi.json` whenever routes change, since these are snapshots, not live-synced |
| `docs/ATHENA-IX-HANDOFF.md` | Dated IX-track continuity snapshot: implemented data flow, runtime contracts, QA evidence, known unavailable states, and remaining approval gates | Picking up IX work after verifying current status in Milestones, Implementation Summary, and git |
| `docs/PRODUCTION_READINESS_ROADMAP.md` | R1–R6 daily-advisory-use readiness tracks | Working on live/ops-facing concerns |
| `docs/ops/*.md` | Runbooks: file-backed daily ops, Kite live data, host schedule/alerts, live-entry, QA verification | Doing anything with the live workstation, Kite auth, or scheduled cycles |
| `README.md` | Human-facing landing page: doc index, workstation entry commands, core stack decisions | Quick doc-index lookup or the exact `athena-serve` invocation |
| `CLAUDE.md` / `AGENTS.md` (symlink) | Mandatory AI process rules — git actions, commit format, milestone workflow | Every session, before doing anything |

## 5. How to determine current status — procedure, not a fact

Status changes constantly; this section never states a status, only the
procedure to find it, so it can't go stale:

1. `docs/MILESTONES.md` → find the track/phase table → read the **Status**
   column. Legend: ✅ Approved · 🔄 Ready for review / In design ·
   ⏸ Deferred · ⏳ Planned. A track is "closed" only when its heading says so
   explicitly (e.g. "*Foo track closed (date):* ...").
2. If a milestone shows 🔄, check whether it's actually still in flight or
   just awaiting a final "approve" from the owner in-chat — search recent
   conversation/commit history for the milestone's name.
3. `IMPLEMENTATION_SUMMARY.md` top entry → full detail on whatever
   `docs/MILESTONES.md` says is most recent.
4. `git log --oneline -20` → what's actually committed. The docs can be
   ahead of git (AI documents before the owner commits) or, less often,
   behind it.
5. Never state "ATHENA is at phase/milestone X" without having just done
   steps 1–4 in *this* session — a memory or a prior summary is not a
   substitute for reading the live files.

## 6. Repo map (current shape — see `src/athena/` for the authoritative list)

Non-code:
- `config/*.json` — all runtime configuration. Never hardcode a threshold,
  weight, or path that belongs here.
- `data/index_constituents/<effective-date>/` — immutable official NSE index
  membership snapshots plus checksum/provenance manifest; never overwrite an
  existing effective-date directory.
- `tests/` — mirrors `src/athena/` structure, 1000+ tests. Full suite must
  pass before any milestone is considered done.
- `docs/` — see table above.
- `IMPLEMENTATION_SUMMARY.md`, `docs/MILESTONES.md` — status (§5).

`src/athena/` grouped by concern (a directory existing here doesn't imply
its milestone is approved — check §5):

| Concern | Packages |
|---|---|
| Symbol master & universes (ADR-011) | `symbols/` — canonical `symbol_master` with series/board provenance, dated `symbol_group` membership, config-driven universe resolver, named eligibility profiles, coverage planner. Scanners reference a universe *name*; DarvaX reads a materialised universe as data through its port |
| Foundations | `domain/` (frozen canonical model), `config/`, `calendar/` (sole trading-day/session authority), `observability/`, `errors.py` |
| Data | `data/` (providers incl. institutional flow file/NSE adapters, official NSE corporate-action adapter and bounded ingestion, immutable EMR intraday source capture/replay orchestration, validation, corporate actions, strict versioned index-constituent loader, SQLite `store/repository`) |
| Market Intelligence | `regime/`, `market_health/` (categorical + F-5 score), `sector_health/`, `universe/`; dashboard `GET /api/v1/market/summary` (MH-3) |
| Decision Intelligence | `evidence/`, `indicators/`, `scoring/`, `confidence/`, `risk/`, `decision/`, `reporting/` (decision trace explanations *and* generic operational reports) |
| Intraday Intelligence (ID-track, evidence + contracts + a pure Entry Qualification engine, now persisted AND wired into the canonical runtime — no API/UI, no Decision gate) | `session/` (ID-1: `SessionContext`, completed-candle rule, `session_day_start`/`session_open_close_ts`/`canonical_slot_candles` — the shared completed + canonical-slot authorities every consumer below reuses) and `intraday/` — `IntradaySignalSet` (ID-2, formalizes existing VWAP/5m-15m-confluence evidence), `OpeningRangeEvidence` (ID-3/ID-3.1: OR15/OR30, canonical-slot-integrity-corrected), `RelativeStrengthContext` (ID-4/ID-4.1, Owner-approved: stock-vs-sector/market point-in-time comparative performance, not RSI — comparative dimensions data-blocked pending ID-5's index M5 remediation, check `docs/MILESTONES.md`), `GapContext` (ID-5C, Owner-approved/CLOSED: previous-trading-session-close → current-session-open price transition, D1-only, deliberately independent of ID-5B's now-closed live M5 semantics question), `RelativeVolumeContext` (ID-5D methodology Owner-accepted; ID-5D.1 owner-approved/CLOSED: corrected current-window contiguity + retrieval-policy correctness fixes on top of ID-5D's accepted cumulative same-time-of-day relative volume, no hardcoded baseline-length cap, canonical-M5-only so deliberately independent of ID-5B too), `EntryQualification` contracts (ID-6A: immutable state/evidence-finality/confirmation/reason/evidence-ref types bound to canonical `Decision`), `EntryQualificationEngine` (ID-6B.2/ID-6B.2A, owner-approved/CLOSED: pure, deterministic, side-effect-free v0 readiness evaluator for the owner-frozen ID-6B.1B methodology — VWAP positive AND aggregate trend BULLISH AND (RS support OR RVOL support) — plus input-coherence hardening), and `resolve_evidence_finality` (ID-6D: pure `EntryEvidenceFinality` resolver reusing the engine's own public structural/lifecycle eligibility gate, never its tri-state formula). ID-6C/ID-6C.1 (owner-approved/CLOSED) added durable append-only persistence — `entry_qualifications` SQLite table lives in `data/store/schema.py` (FK-bound to `decisions`, plus repository-level canonical-Decision-binding validation), read/write API on `SqliteRepository`; design note `docs/design/ID-6C-ENTRY-QUALIFICATION-PERSISTENCE.md`. ID-6D (owner review pending) wires the whole chain into `OwnerValidationPipeline._scan_eligible`'s per-instrument `WorkflowStage` graph as a new `entry_qualification` stage (depends on `decision` + `intraday_analytics`) — persists WATCH/TRADE observations every real cycle; design note `docs/design/ID-6D-ENTRY-QUALIFICATION-WORKFLOW-INTEGRATION.md`. ID-5B and ID-5 are owner-approved/CLOSED as of 2026-09-01 with final `CASE_B_CONTENT_CHANGES`; ADR-013, ID-6A0, ID-6A, ID-6B.0, ID-6B.1, ID-6B.1A, ID-6B.1B, ID-6B.2, ID-6B.2A, ID-6C, and ID-6C.1 are owner-approved/CLOSED as of 2026-09-02 — check `docs/MILESTONES.md` for ID-6D's current review status. Still no API/UI, no outcome/shadow validation (ID-6E) |
| Explosive Move research (isolated, ADR-012) | `explosive_move/` — EM-1a immutable event/readiness contracts, EM-1r2 read-only corporate-action coverage/cohort evidence, EM-1r3 provider-free exact-slot intraday reconstruction/manifests, EM-1r4 survivor-cohort admission/quote-timestamp hygiene, EM-1r5's corporate-action boundary-crossing rule, and EM-1b's forward-label contract (`event_labels.py`) and frozen chronological TRAIN/VALIDATION/CALIBRATION/FINAL_TEST partition contract (`partitions.py`); a real deterministic label dataset exists at `artifacts/research/em1b/` (git-ignored), generated by `src/athena/data/em1b_label_dataset_generation.py`. **EM-5 (owner-approved / closed 2026-09-01; contract accepted — check `docs/MILESTONES.md` before relying on this):** `explosive_move/live/` — the v1 replayable live scanner (`run_scan_cycle`) plus the contract §14 fail-fast production canary gate (`canary_gate.py`), reading promoted artifacts from `config/emr/frozen_models/` (`src/athena/data/em5_artifact_promotion.py`) and writing to `explosive_move/store/`'s own isolated `db/emr.db`; Tuesday 2026-09-01 Track B live capture completed for all nine frozen checkpoints; Track B.1 is owner-accepted and classifies the complete zero-off-grid canary as `NO_OFF_GRID_PROVISIONAL_OBSERVED`; the final Section 14 nine-checkpoint canary passed against `athena_core` / 2026-08-28 with zero provider/network calls. Still no UI, canonical score input, or production recommendation |
| Orchestration & Ops | `orchestration/`, `scanner/`, `watchlist/`, `strategy/`, `backtest/`, `scheduling/` |
| Portfolio & planning (no execution) | `portfolio/` — existing portfolio engine plus My Portfolio contracts (`my_portfolio_contracts.py`), PS-P2 generic import parsing/resolution (`imports.py`), and PS-P4 sync orchestration (`sync.py`) for CSV/XLSX current-holdings preview, canonical symbol resolution, reconciliation, server-owned snapshot math, background sync state, immutable analysis snapshots, freshness, and provenance; isolated `portfolio_*` SQLite tables live in `data/store/schema.py`, API endpoints live under `/api/v1/my-portfolio`, dashboard UX lives in `api/static/js/08b-my-portfolio.js` and `api/static/css/05b-my-portfolio.css`, and `owner_positions` remains the legacy/manual-fill ledger. Also `allocation/`, `sizing/`, `orders/` (planning only), `brokers/` (abstraction only), `execution/` |
| Presentation | `dashboard/`, `explainability/`, `timeline/`, `monitoring/`, `export/`, `analytics/` |
| Application platform | `api/` — FastAPI v1 REST + security + platform; `api/static/` — the dashboard SPA (`index.html`; `dashboard.js` and `dashboard.css` are each served-assembled from concern-based source files — `js/*.js` (concatenated server-side by an `app.py` route) and `css/*.css` (loaded via `@import`) respectively — hand-rolled, no framework/build step per ADR-004) |
| DarvaX satellite (opt-in, ADR-010) | `darvax/` — self-contained: own `config`, `store` (own `db/darvax.db`, own schema version), `ports`/`adapters` (read-only view of ATHENA candles), `primitives`, `signals`, `scan`, `screening` (tiers, universe sweep, action classification, liquidity, calendar-aware daily-sweep freshness), `positions` (owner-recorded holdings; stop-loss frozen at entry, never deleted on close), `validation` (DX-5 outcome harness), `api` (own sub-app, own static assets — three views: Advisor / Levels / Table). ATHENA's only knowledge of it is `api/darvax_mount.py`, which reads activation configuration and injects a read-only host session-calendar port; DarvaX never imports ATHENA calendar/config modules directly |
| Live ops | `notifications/`, `diagnostics/`, `ops/` (owner candidate lists, live validation pipeline, alerts, owner-triggered full-universe validation job) |
| Cross-cutting | `runtime/` (workflow/execution models shared across phases) |

## 7. Stack quick facts

Python (pydantic config, `Decimal` money, tz-aware `datetime`), SQLite
(WAL), FastAPI (localhost-only), static HTML + vanilla JS dashboard (no
frontend framework), in-house indicators (no external TA-lib), pytest.
Broker: Zerodha Kite Connect (DD-1), read-only market data — no order API
integration exists.

## 8. Mandatory workflow (full detail in `CLAUDE.md` — this is the headline)

- **AI never runs git actions** (add/commit/push/etc.) unless the owner
  explicitly asks in that specific instance. Provide a consolidated commit
  message instead — `<type>(<scope>): <summary>` + WHAT/WHY bullets.
- **One milestone in flight at a time.** Design → Implement → Test →
  Self-validate → Milestone Review Summary → owner approval → next. Never
  auto-continue past an approval gate.
- Update `IMPLEMENTATION_SUMMARY.md` after every completed milestone, and
  `docs/MILESTONES.md`'s status column the moment the owner approves.
- **When a track/phase closes, or the module map in §6 changes materially,
  update this file's §6 in the same change set.** This is the one part of
  this briefing that can drift — keep it honest.

## 9. Absolute prohibitions

- No order-placement code, under any milestone, ever.
- No architecture change without an ADR + explicit owner approval.
- No secrets outside `.env`.
- No git actions without explicit, per-instance owner request.
- No skipping the milestone approval gate "to save time."
