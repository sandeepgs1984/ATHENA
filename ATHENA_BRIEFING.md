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
| `docs/adr/ADR-00{1..8}-*.md` | Architecture Decision Records: modular monolith, broker abstraction, pipeline context, static-HTML-first, explainability-as-data, circuit limits, owner-triggered background validation, institutional-flow provider (ADR-008 Accepted) | You're unsure whether a pattern is intentional or need to cite the decision that made it so |
| `docs/decisions/DD-*.md` | Deferred Decision resolutions (e.g. DD-1 broker/data vendor = Zerodha Kite Connect, DD-9 alerting = webhook+file, DD-11 FII/DII institutional flow) | Before assuming something is "still undecided" — check here first, it may already be resolved |
| `docs/design/F5-MARKET-HEALTH-SCORE.md` | Exact F-5 six-component Market Health Score contract (formulas, unknown-data policy, persistence, consumer alignment) | Changing F-5 formulas/weights/unknown-data policy, or debugging Market Summary Unavailable states |
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
| Foundations | `domain/` (frozen canonical model), `config/`, `calendar/` (sole trading-day/session authority), `observability/`, `errors.py` |
| Data | `data/` (providers incl. institutional flow file/NSE adapters, validation, corporate actions, strict versioned index-constituent loader, SQLite `store/repository`) |
| Market Intelligence | `regime/`, `market_health/` (categorical + F-5 score), `sector_health/`, `universe/`; dashboard `GET /api/v1/market/summary` (MH-3) |
| Decision Intelligence | `evidence/`, `indicators/`, `scoring/`, `confidence/`, `risk/`, `decision/`, `reporting/` (decision trace explanations *and* generic operational reports) |
| Orchestration & Ops | `orchestration/`, `scanner/`, `watchlist/`, `strategy/`, `backtest/`, `scheduling/` |
| Portfolio & planning (no execution) | `portfolio/`, `allocation/`, `sizing/`, `orders/` (planning only), `brokers/` (abstraction only), `execution/` |
| Presentation | `dashboard/`, `explainability/`, `timeline/`, `monitoring/`, `export/`, `analytics/` |
| Application platform | `api/` — FastAPI v1 REST + security + platform; `api/static/` — the dashboard SPA (`index.html`; `dashboard.js` and `dashboard.css` are each served-assembled from concern-based source files — `js/*.js` (concatenated server-side by an `app.py` route) and `css/*.css` (loaded via `@import`) respectively — hand-rolled, no framework/build step per ADR-004) |
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
