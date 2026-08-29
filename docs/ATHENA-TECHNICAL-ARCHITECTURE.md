# ATHENA — Complete Technical Implementation Reference

**What this document is.** A ground-truth account of *how ATHENA is actually
built* — backend architecture, frontend architecture, persistence, security,
testing, tooling, and operations — verified against the running code, not
against what other documents say it should be. Every claim below was checked
by reading the file cited; where documentation elsewhere in this repo turned
out to describe something the code no longer does (or never did), that is
stated explicitly rather than silently repeated. Treat a claim with no
file:line citation as unverified.

**What this document is not.** It does not re-derive trading formulas,
thresholds, or the regime/scoring/decision methodology — that is
[`docs/ATHENA-WORKFLOW-METHODOLOGY.md`](ATHENA-WORKFLOW-METHODOLOGY.md)'s job,
and this document cross-references it rather than duplicating it. It does not
re-document the platform diagnostics endpoints in full —
[`docs/API_PLATFORM_GUIDE.md`](API_PLATFORM_GUIDE.md) already does, and §4.6
below only confirms that guide against the code. Governing rules (git
workflow, milestone discipline) live in `CLAUDE.md`; product philosophy and
invariants live in `ATHENA-000-Master-Architecture.md` and
`ATHENA_BRIEFING.md`.

**How to keep this honest over time.** This is a snapshot. Numbers like test
counts, database sizes, and line numbers will drift the moment someone commits
again. Re-verify a claim before quoting it in a decision — grep for the
function name cited, don't trust the number attached to it.

---

## Table of contents

1. [Technology stack](#1-technology-stack)
2. [Backend architecture](#2-backend-architecture)
3. [The decision pipeline — module map](#3-the-decision-pipeline--module-map)
4. [API layer](#4-api-layer)
5. [Frontend architecture](#5-frontend-architecture)
6. [Testing, tooling & dev workflow](#6-testing-tooling--dev-workflow)
7. [Scheduling, live data & operations](#7-scheduling-live-data--operations)
8. [DarvaX as a worked case study](#8-darvax-as-a-worked-case-study)
9. [Known documentation/implementation gaps](#9-known-documentationimplementation-gaps)
10. [Glossary & cross-reference index](#10-glossary--cross-reference-index)

---

## 1. Technology stack

| Layer | Choice | Version constraint | Source |
|---|---|---|---|
| Language | Python | `>=3.10` | `pyproject.toml:5` |
| Validation | Pydantic | `>=2.7` | `pyproject.toml:7` |
| Web framework | FastAPI | `>=0.115` | `pyproject.toml:8` |
| ASGI server | Uvicorn | `>=0.30` | `pyproject.toml:9` |
| Persistence | SQLite (WAL mode) | stdlib `sqlite3` | `src/athena/data/store/repository.py:114` |
| Auth | JWT (HS256) via PyJWT, bcrypt password hashing | — | `src/athena/api/security/token.py`, `security/service.py` |
| Frontend | Static HTML + hand-written vanilla JS/CSS | — | `docs/adr/ADR-004-static-html-first.md` |
| Charting | Hand-rolled inline SVG (primary) + Chart.js via CDN (secondary charts) | — | see [§5.5](#55-charting--the-record-corrected); **not** Lightweight Charts despite README/ADR-004 language |
| Dev tooling | pytest `>=8.0`, ruff `>=0.4`, mypy `>=1.10`, httpx `>=0.27` | `pyproject.toml:14-18` | — |
| Build | Hatchling | — | `pyproject.toml:21-24` |
| Broker/data | Zerodha Kite Connect (read-only) | — | `src/athena/data/providers/kite_provider.py` |
| CI | **None** | — | no `.github/`, `.gitlab-ci*`, or `.circleci/` directory exists |
| Containerization | **None** | — | no `Dockerfile` or `docker-compose*` anywhere in the repo |

The whole system is one Python process (`uvicorn` bound to `127.0.0.1`),
serving both the REST API and the static dashboard, with no separate frontend
build step, no bundler, and no container runtime. This is a deliberate,
current choice, not an oversight — see [§5.1](#51-adr-004-rationale) and
[§7.4](#74-deployment-model).

---

## 2. Backend architecture

### 2.1 Domain model

`src/athena/domain/` holds the canonical types every other module consumes.
They are genuinely immutable — `@dataclass(frozen=True, slots=True)`, not just
documented as such — covering `Instrument`, `Candle`, `CorporateAction`,
`CalendarContext`, `Quote`, `MarketSnapshot`, `InstitutionalFlowSession`,
`MarketHealthScore`, `RegimeAssessment`, `Universe` (`domain/market.py`);
`Evidence`, `Signal`, `Score`, `ConfidenceAssessment` (`domain/evidence.py`);
`TradePlan`, `RiskEvaluation`, `Decision`, `DecisionTrace`, `Position`
(`domain/decision.py`); plus `PipelineContext` (`domain/context.py`, **dormant/
legacy — see the note below**) and `RunRecord`/`ConfigurationSnapshot`
(`domain/run.py`).

- **Money is always `Decimal`.** `Candle.open/high/low/close: Decimal`
  (`market.py:45-48`), `TradePlan.stop_loss/risk_amount: Decimal`
  (`decision.py:20-23`). No `float` anywhere in the money path.
- **Timezone-awareness is enforced at construction**, not merely typed:
  `Candle.__post_init__` raises `ValueError("Candle.ts_open must be
  timezone-aware")` if `tzinfo is None` (`market.py:53-55`); the identical
  pattern repeats on `Quote` (`market.py:115-117`), `MarketSnapshot`
  (`market.py:131-133`), `Decision` (`decision.py:136-137`), and `Evidence`
  (`evidence.py:33-34`). A naive datetime cannot enter the domain layer at all.
- **`PipelineContext`** (`context.py:26-69`) is **dormant/legacy scaffolding,
  not the live runtime** (ADR-003 Amendment 1, ID-P0, 2026-08-29 — ID-0's
  runtime audit found zero non-test production callers). It reads as if it
  were the one shared per-run object — `data` wrapped in `MappingProxyType`
  in `__post_init__` (line 42), `.get()` raising with a producer hint if a
  key is missing (lines 44-49), `.with_delta()` raising if a stage tries to
  re-produce a key another stage already set (lines 55-61), returning a
  *new* `PipelineContext` rather than mutating the existing one — but no
  analytical engine actually constructs or consumes it. ATHENA's real,
  live per-cycle context is `runtime.workflow.WorkflowContext`
  (§3.2 below; ADR-003 Amendment 1), which enforces the identical "no hidden
  state, no silent overwrite" guarantee through its own `_merge` method
  instead. Both mechanisms illustrate the same principle; only the
  Workflow one is wired into any real decision.
- **No shared `Clock` abstraction.** Determinism is achieved by injecting an
  `as_of`/`now` parameter at each engine's boundary rather than through a
  central clock object — stated explicitly in `market_health/engine.py:13`
  ("no I/O, no clock reads (time injected as `as_of`)") and `regime/engine.py:5`.
  The only concrete `*Clock` class in the repo is `_MonoClock` in
  `ops/owner_validation.py:50`, which is ops-layer plumbing, not a domain
  abstraction other engines share.

### 2.2 Configuration system

`src/athena/config/models.py` defines a `_Strict(BaseModel)` base
(`models.py:19-29`) with `model_config = ConfigDict(extra="forbid",
frozen=True)` — every config model inherits this, so an unrecognized key in
any `config/*.json` file is a hard validation error at boot, not a silently
ignored typo. `config/loader.py` feeds each file through `model_validate` and
wraps any `ValidationError` into `ConfigError` with a per-field message
(`loader.py:89-133`); `ConfigError`'s policy is stated in `errors.py:15-16`:
"refuse to start."

Concrete examples of "configuration over hardcoding, not a slogan":

- `RiskConfig._risk_invariants` (`config/models.py:112-120`) rejects a config
  where `per_trade_risk_pct > max_daily_loss_pct` — a cross-field business
  rule enforced at load time, so a self-contradictory risk config cannot boot.
- `RsiScoringCfg._ordered` (`config/models.py:780-798`) validates that
  `mid_points` actually sits on the ramp between `weak_points` and
  `strong_points` — catches a hand-edited `scoring.json` that would otherwise
  silently invert a scoring curve.
- `F5WeightsCfg._sum_100` and its siblings on `ScoringWeightsCfg`,
  `ConfidenceWeightsCfg`, `RiskWeightsCfg` (`config/models.py:690-702` and
  nearby) enforce that weights sum to exactly 100 as a *validated config
  invariant*, not an assumption baked into the engine that computes with them.
- `IngestionConfig.lookback_days` (`config/models.py:486-496`) carries its
  empirical justification for the bound (3650, not 365) as a comment next to
  the field, not buried in the engine that consumes it.

### 2.3 Provider abstraction pattern

`domain/interfaces.py:53` defines `MarketDataProvider` as a
`@runtime_checkable Protocol`: `capabilities()`, `instruments()`,
`daily_candles()`, `intraday_candles()`, `quotes()`, `market_snapshot()`,
`health()` — **no order methods**, and the docstring states this is structurally
enforced by `tests/contract/provider_contract.py`. That file is real:
`MarketDataProviderContract` (`provider_contract.py:43+`) defines
`FORBIDDEN_NAME_MARKERS = ("order", "buy", "sell", "trade", "place", "execute",
"position")` (line 35) and scans any implementation for a method matching one
of those markers. Both `FileProvider` and `KiteProvider`
(`data/providers/kite_provider.py:68-69`) are required to pass the identical
contract suite (`tests/contract/test_file_provider_contract.py`,
`test_kite_provider_contract.py:14`) — a provider that grew an order-placement
method would fail this test, not just violate a convention.

A second Protocol, `InstitutionalFlowProvider` (`domain/interfaces.py:97-111`),
is deliberately separate rather than folded into `MarketDataProvider` — ADR-008
records the reasoning: institutional flow isn't quotes/candles, and forcing it
onto the broker-facing Protocol would pollute what a broker adapter has to
implement. Two adapters share the pattern:
`FileInstitutionalFlowProvider`(`data/providers/file_institutional_provider.py:28`)
and `NseInstitutionalFlowProvider` (`data/providers/nse_institutional_provider.py:115`).

**Enforcement is by convention plus contract tests, not by an automated
import-graph tool.** There is no `import-linter`, `pytest-archon`, or
equivalent configured anywhere in the repo — searched for and not found. "The
business logic never imports a concrete provider" holds because Protocol
typing plus the contract suite make a violation *detectable*, and because code
review has held the line, not because tooling would block a violating commit.
The one place a genuine automated seam exists is the DarvaX mount boundary —
see [§2.8](#28-module-boundary-enforcement) and [§8](#8-darvax-as-a-worked-case-study).

### 2.4 Persistence layer

`src/athena/data/store/repository.py` defines `SqliteRepository`. Concrete,
verified mechanics:

- **WAL mode is turned on at connection open**: `PRAGMA journal_mode=WAL`
  immediately followed by `PRAGMA foreign_keys=ON` (`repository.py:114-115`).
  Foreign keys are real constraints, not aspirational — e.g.
  `candles.instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id)`
  (`schema.py:108`) — and `verify_integrity()` runs `PRAGMA foreign_key_check`
  and reports violations (`repository.py:1221-1244`).
- **ADR-009's read-concurrency design is implemented, not just proposed.** One
  shared write connection is guarded by `threading.RLock()`
  (`repository.py:99`); reads instead get a **per-thread, read-only
  connection** opened via `sqlite3.connect(f"file:{path}?mode=ro", uri=True,
  ...)` (`repository.py:1292-1293`), cached in `threading.local()`
  (`repository.py:104`) and reused for the thread's lifetime.
  `_query_one`/`_query_all` route through this per-thread connection
  (lines 1302-1318); `_write`/`_write_many` still go through the shared lock
  (lines 1248-1266). An `:memory:` database is the one deliberate exception —
  it falls back to the shared connection, since a second `:memory:` connection
  would open a distinct, empty database (`repository.py:1279-1287`).
- **Schema versioning is one monotonic integer, not a migration-file chain.**
  `schema.py:13` — `SCHEMA_VERSION = 15`. `initialize()`
  (`repository.py:121-144`) runs idempotent `CREATE TABLE IF NOT EXISTS` DDL
  plus explicit, hand-written `ALTER TABLE` steps for additive columns (e.g.
  `_migrate_instruments_name_column`, lines 146-165), then upserts the version
  row. There is no Alembic or equivalent — every `initialize()` call re-runs
  every migration step idempotently.

DarvaX ([§8](#8-darvax-as-a-worked-case-study)) follows the identical pattern
independently: its own `SCHEMA_VERSION` (currently 9), its own idempotent
migrations, its own database file — proof the pattern generalizes to a second
module without needing to share code with the core repository.

### 2.5 Calendar module

`CalendarEngine` (`calendar/engine.py:29-129`) is the sole authority
translating a `date` into a `CalendarContext`: session type
(`NORMAL`/`HOLIDAY`/`WEEKEND`/`MUHURAT`), open/close times, holiday name,
expiry flags, and calendar events (`context_for`, lines 79-128). All of this
comes from `config/calendar/*.json` — the module's own docstring states "Data
lives in config/calendar/*.json — never in code" (`engine.py:4`). Asking about
an uncovered year fails loudly with the exact remediation named in the
exception: `CalendarError("Update config/calendar/holidays.json from the
current NSE circular")` (`engine.py:80-84`). Every module that needs to know
"is the market open" or "is today a trading day" is expected to ask this
engine rather than reimplement weekday/holiday logic — the scheduling cadence
engine ([§7.1](#71-cadence-engine)) is a concrete example of a downstream
consumer that stays calendar-ignorant by taking the answer as a parameter.

### 2.6 Observability & error handling

`errors.py` defines a flat `AthenaError` hierarchy — `ConfigError`,
`CalendarError`, `DataStaleError`, `ProviderError`, `RepositoryError`, and
others (`errors.py:11-117`) — each carrying a one-line "Policy:" docstring
stating exactly how that failure class should be handled (e.g.
`RepositoryError`: "Policy: fail loudly, name it" — line 44). This is not
theoretical: `SqliteRepository.__init__` catches `sqlite3.Error` on open and
re-raises `RepositoryError(f"cannot open database at {self._path}: {exc}")`
(`repository.py:116-117`) rather than falling back to an in-memory database or
swallowing the error and letting downstream code proceed as if there were
simply no data.

`observability/logging.py` emits structured JSON-lines logs: `JsonLineFormatter`
(lines 46-60) writes one JSON object per record —
`ts, level, module, run_id, cycle_id, event, payload` — and `_redact()`
(lines 34-43) masks any payload key matching `REDACTED_KEY_MARKERS = ("token",
"secret", "password", "api_key", "apikey", "auth")` (line 23) before
serialization. Secrets are structurally excluded from logs by the formatter
itself, not by a convention that a log call must remember to follow.

### 2.7 Explainability-as-data (ADR-005)

ADR-005 states the rule plainly: "Explanation is a field, not a stage...
every Evidence, Score, RiskEvaluation, and Decision carries its rationale...
at creation time" (`docs/adr/ADR-005-explainability-as-data.md:13-15`). The
concrete mechanism, using `MarketHealthScore` as the clearest example
(`domain/market.py:171-185`): the dataclass carries `components:
Mapping[str, int]`, `total: int`, **and** `explanation: str` together, and
`__post_init__` raises `ValueError("MarketHealthScore.explanation is
mandatory (ATHENA-000 p9)")` if `explanation` is empty (lines 180-182). The
computed value and its rationale are the same object, persisted together —
never a value row plus a rationale reconstructed later from the value. The
same shape repeats on `Score` (`evidence.py:58-77`, which additionally
validates `sum(breakdown.values()) == total`), `RiskEvaluation`
(`decision.py:40-53`), and `Decision` (`decision.py:116-147`). This is the
same principle DarvaX's DX-11 guide documents for its own screen results
(§1 of `src/athena/darvax/api/static/index.html`'s guide dialog) — the pattern
is load-bearing across both the core pipeline and the satellite module.

### 2.8 Module boundary enforcement

No automated import-linter or architecture-boundary test exists for the core
`src/athena/` modules — searched and confirmed absent. Enforcement between
core modules is Protocol typing plus the `tests/contract/` conformance
suites plus code review, not a tool that would fail a build on a forbidden
import.

**The one place a genuine, single, verifiable seam exists is
`src/athena/api/darvax_mount.py`.** Its own docstring calls it "the single
approved ATHENA→DarvaX seam" (line 1) and states it is "the *only* place in
ATHENA core that knows DarvaX exists" — knowing exactly one fact, the
`enabled` boolean. The `import athena.darvax` statement is *inside*
`mount_darvax_if_enabled()`, not at module scope, specifically so that
importing `athena.api.app` never pulls in `athena.darvax` unless the flag is
actually true. This is verified by tests, not just asserted: `test_dx1_isolation.py`
shells out to a **subprocess** (to sidestep false negatives from other tests'
import caches) and asserts `athena.darvax` is absent from `sys.modules` when
disabled (line 77); a companion test uses `ast` inspection to fail if the
import were ever hoisted to module scope (`test_04b_the_seam_imports_darvax_lazily_not_at_module_scope`,
line 173). No equivalent single-file seam exists for boundaries *between*
core modules (e.g. `scoring/` and `risk/`) — those rely on plain function
signatures plus each stage's `depends_on`/`produces` declaration on its
`WorkflowStage` (`athena.runtime.workflow`, wired in
`ops/owner_validation.py` — see §3.1/§3.2), not an import gate. **Not**
`domain/interfaces.py:115`'s `IntelligenceModule` Protocol — despite its own
docstring calling it "the universal module contract," ID-0's runtime audit
(ADR-003 Amendment 1, 2026-08-29) found no engine implements it; see §3.3.

---

## 3. The decision pipeline — module map

README states: "Modular monolith, 17 modules behind Protocol interfaces."
Verified against the code, this framing needs two corrections stated plainly
rather than repeated — the actual architecture is more interesting than the
one-line summary, and an implementation document should say so.

### 3.1 The real per-instrument execution graph has 10 stages (was 6; ID-1 added `session`, ID-2 added `intraday_analytics`, ID-4 added `relative_strength`, ID-5D added `relative_volume`), not 8 or 11

`ATHENA_BRIEFING.md` describes "regime → market health → evidence → indicators
→ score → confidence → risk → decision" — 8 named stages. The actual live
driver collapses two pairs of these into single computation steps. The real
driver is `src/athena/ops/owner_validation.py`'s `builder()` closure, which
wires `WorkflowStage` objects (`src/athena/runtime/workflow.py:65`) into this
dependency graph:

1. **`ind_stage`** — indicators, VWAP, confluence. **ID-2.1 correction
   (2026-08-29):** the 5m/15m candle series fed to VWAP and to the
   5m/15m confluence-direction reads are now filtered through
   `athena.session.completed_candles()` (ID-1's canonical
   `ts_open + duration <= as_of` rule) before any analytical use — **before**
   this correction, `ind_stage` read `repo.list_candles_recent()`'s raw
   result directly, so a still-forming last bar could silently influence
   VWAP's `deviation_pct` and `ConfluenceInputs.five_min_bullish`/
   `fifteen_min_bullish`, even though `SessionContext` (ID-1) already knew
   that same bar wasn't complete. One semantic authority for candle
   completion now governs both paths (proven non-vacuously — a crafted
   extreme forming candle is shown to have zero effect one second before
   completion and a real effect exactly at completion:
   `tests/ops/test_owner_validation.py::test_id21_forming_5m_candle_has_zero_influence_until_it_completes`
   / `test_id21_forming_15m_candle_excluded_from_confluence_until_completion`).
   No VWAP formula, confluence SMA period, or scoring weight/bonus changed
   — input-time correctness only.
2. **`reg_stage`** — regime **and** market health computed together
   (`market_health_engine.assess(..., regime=regime)`)
3. **`sco_stage`**, `depends_on=("indicators", "regime")`
4. **`conf_stage`**, `depends_on=("scoring", "regime")` — evidence bundle
   **and** confidence computed together via `evidence_engine.aggregate()`
   then `confidence_engine.assess()`
5. **`risk_stage`**, `depends_on=("indicators", "regime")`
6. **`dec_stage`**, `depends_on=("scoring", "confidence", "risk")`, which
   persists the result via `self._repo.save_decision(...)`
7. **`session_stage`** (ID-1, 2026-08-29; extended ID-5C, 2026-08-29) —
   `produces=("session_context", "gap_context")`, no `depends_on`, nothing
   else depends on it. Computes a `SessionContext` (`athena.session`) from
   the same 5m/15m candles + a bounded `repo.get_latest_quote()` read —
   genuinely live every cycle, but purely additive foundation work: no
   existing stage's inputs, outputs, or the topological order among
   stages 1-6 changed. Declared **last** in the stage list specifically so
   Kahn's declaration-index tie-break cannot reorder stages 1-6 relative
   to each other (proven by
   `tests/ops/test_owner_validation.py::test_id1_session_stage_is_produced_without_perturbing_existing_stage_order`,
   which reconstructs both the pre- and post-ID-1 graphs and diffs their
   real `execution_order`). **ID-5C** additionally computes
   `athena.intraday.GapContext` (`GapEngine`) here — previous-trading-
   session-close → current-session-open price transition, resolved from
   this same instrument's already-fetched D1 candle history (`cs`, zero
   new repository reads) plus
   `data.validation.calendar_expectations.latest_trading_day_on_or_before`
   for the previous trading session — no new `WorkflowStage` (this stage
   already had everything gap resolution needs), so the dependency graph
   itself is unchanged and the Kahn-ordering proof above needed no update.
   Deliberately independent of ID-5B's still-open current-session M5
   semantics question: `GapEngine` never reads M5 data at all.
8. **`intraday_analytics_stage`** (ID-2, 2026-08-29; extended ID-3, 2026-08-29) —
   `depends_on=("session", "indicators")`, `produces=("intraday_signal_set",)`.
   Formalizes the `vwap`/`confluence` values `ind_stage` already produced
   this cycle into typed evidence (`athena.intraday.IntradaySignalSet`/
   `IntradayTrendContext`) — computes nothing new, so it cannot diverge
   from what `ScoringEngine` already saw (proven by object-identity, not
   just equal values:
   `tests/ops/test_owner_validation.py::test_id2_intraday_signal_set_reuses_the_exact_same_vwap_and_confluence_scoring_used`).
   No BUY/SELL/probability field exists on either type. Nothing among
   `scoring`/`confidence`/`risk`/`decision` depends on it — proven not to
   perturb the other structural stages' relative order, same technique as
   `session_stage`'s own proof
   (`test_id2_intraday_analytics_stage_does_not_perturb_existing_stage_order`).
   **ID-3** extends this same stage (no new stage — the smallest
   architecture given it already produces `IntradaySignalSet`) with
   `OpeningRangeEvidence` (OR15/OR30, `athena.intraday.opening_range_engine.OpeningRangeEngine`):
   its own real 5m candle fetch, filtered through the same
   `athena.session.completed_candles()` authority ID-2.1 fixed `ind_stage`
   to use, plus `data.validation.calendar_expectations.expected_intraday_opens`
   for the window's own bar-count expectations. Genuinely new evidence
   (not a formalization of an existing scoring input, unlike VWAP/confluence)
   but held to the identical rule: no scoring/confidence/risk/decision
   dependency exists on it. **ID-3.1** corrected two production issues found
   in owner review: the 5m fetch (and VWAP's/`session_stage`'s own) is now
   bounded by `athena.session.session_day_start(as_of, tz)` through the
   repository's existing `get_candles()` rather than a fixed
   `list_candles_recent(limit=100)`, and `OpeningRangeEngine` now filters to
   exact canonical expected M5 timestamps (`athena.session.canonical_slot_candles`,
   a shared authority — promoted from a private `_canonical_slots()`,
   ID-4) before any formation/relation/breakout computation, so an
   off-grid row can never substitute for a missing canonical slot. See
   [§9 item 12](#9-known-documentationimplementation-gaps). **ID-4** adds
   `relative_strength=ctx.get("relative_strength")` to this stage's
   `IntradayAnalyticsEngine.assess()` call — composed, not recomputed.
   **ID-5D** likewise adds `relative_volume=ctx.get("relative_volume")` —
   composed, not recomputed; `depends_on` gains `"relative_volume"` as a
   fourth declared dependency.
9. **`relative_strength_stage`** (ID-4, 2026-08-29; corrected ID-4.1, 2026-08-29) —
   `depends_on=("session",)`, `produces=("relative_strength",)`.
   Computes `athena.intraday.RelativeStrengthContext`
   (`RelativeStrengthEngine`) — stock-vs-sector/market point-in-time
   comparative performance, NOT RSI, no scoring/composite/ranking use.
   Fetches its own bounded stock M5 series (same pattern as VWAP/ORB); the
   market benchmark's and each mapped sector's own M5 series are fetched
   ONCE per run (`market_five_min`/`sector_five_min_by_sector`, resolved
   in `_scan_eligible`'s outer scope), not per instrument. Depends only on
   `session` (for `SessionContext`'s open/close/date, which also govern
   the market/sector canonical-slot filtering) — no dependency on
   `indicators`, since nothing here reuses `ind_stage`'s output.
   `intraday_analytics_stage` (item 8) gains this as a third declared
   dependency to compose the result onto `IntradaySignalSet`. Proven not
   to perturb the six pre-existing structural stages' relative order,
   same Kahn-sort technique as items 7/8's own proofs
   (`test_id4_relative_strength_stage_does_not_perturb_existing_stage_order`).
   Market/sector benchmark identity is reused, never re-derived: the same
   `index_id` `_resolve_index_candles` already resolves for regime, and the
   same `Instrument.sector` → `config/sector_index_mapping.json` →
   `config/index_intelligence.json` chain `SectorHealthEngine` already
   uses. **ID-4.1** fixed a partial-availability correctness issue:
   `comparison_cutoff_ts` was computed from any constituent with at least
   one canonical bar, not only constituents that can genuinely form a
   return (`_ConstituentSeries.can_form_return` — a genuine opening
   reference AND a later canonical bar) — an opening-only constituent
   (real production shape: an index whose canonical M5 coverage is just
   its own first bar) was dragging the whole comparison down to a
   zero-duration window, erasing an otherwise valid stock (or stock+sector)
   return. See [§9 item 13](#9-known-documentationimplementation-gaps) for a
   severe real-data limitation found here.
10. **`relative_volume_stage`** (ID-5D, 2026-08-29) —
    `depends_on=("session",)`, `produces=("relative_volume",)`. Computes
    `athena.intraday.RelativeVolumeContext` (`RelativeVolumeEngine`) —
    cumulative same-time-of-day relative volume, NOT a surge/spike label,
    zero-threshold `ABOVE_BASELINE`/`BELOW_BASELINE`/`AT_BASELINE`/`UNKNOWN`
    only. Fetches its own bounded M5 read spanning a 120-calendar-day
    lookback window (a RETRIEVAL bound distinct from the engine's own
    baseline POLICY of using every comparable session found within
    whatever is retrieved — currently capped at ~23 trading days by real
    M5 data availability, not by this bound). Depends only on `session`
    (for `SessionContext`'s open/close/date, which govern the engine's own
    canonical-slot alignment) — same dependency shape as
    `relative_strength_stage`, no dependency on `indicators`.
    `intraday_analytics_stage` (item 8) gains this as a fourth declared
    dependency. Proven not to perturb the six pre-existing structural
    stages' relative order, same Kahn-sort technique as items 7/8/9's own
    proofs (`test_id5d_relative_volume_stage_does_not_perturb_existing_stage_order`).
    Deliberately independent of ID-5B's still-open current-session M5
    semantics question: only canonical completed M5 bars ever contribute
    to either the current cumulative volume or any historical comparison
    session — an off-grid or still-forming row can never enter the
    contract. See [§9 item 16](#9-known-documentationimplementation-gaps)
    for known limitations (corporate-action adjustment not audited, and an
    OWNER_PENDING rolling-baseline-cap policy question).

Sector health and universe are computed **once per run**, not per instrument —
`universe_engine.build(...)` and `SectorHealthEngine(sector_cfg).assess_many(...)`
in `OwnerValidationPipeline.run()` — feeding a shared payload into the
per-instrument graph above rather than appearing as stages in it. (Sector
health *is* additionally resolved per-instrument, via `Instrument.sector`,
inside `builder()` — see ADR-003 Amendment 1's SD-3 wiring, ID-P0 — but the
`SectorHealthEngine.assess_many()` computation itself stays run-level.)
`session_stage` is per-instrument (its own 5m/15m/quote reads vary by
instrument), unlike sector/universe. `relative_strength_stage` (ID-4) is a
hybrid: its own stock M5 read is per-instrument, but the market-benchmark
and each mapped sector's own M5 series are resolved once per run (like
sector health/universe) and shared across every instrument that reads them.

The dependency *direction* the briefing describes is real and import-verified:
`scoring/engine.py:20-32` imports from indicators/market_health/regime/
sector_health; `confidence/engine.py:35-37` imports evidence and scoring;
`risk/engine.py:26-37` imports regime/market_health/universe; `decision/engine.py:23-38`
imports confidence, evidence, risk, scoring, and regime as the terminal
consumer. What's inaccurate is the *stage count* — market_health rides inside
the regime stage, evidence rides inside the confidence stage.

### 3.2 Two independent execution frameworks, not one orchestrator

This is the most consequential correction. **`src/athena/orchestration/` does
not drive the regime→decision analytical chain described above.**
`orchestration/` (`PipelineStage`/`PipelineDefinition`/`PipelineContract` in
`orchestration/models.py` and `orchestration/contract.py`, run by
`PipelineCoordinator` at `orchestration/coordinator.py:23`) is a separate,
generic declarative framework defining exactly two named pipelines:

- The **Execution Pipeline** (`orchestration/pipelines/execution.py`) —
  portfolio → allocation → sizing → order_planning → broker_translation →
  lifecycle → analytics. This is the planning-stack pipeline, not the
  analytical one.
- The **Intelligence Pipeline** (`orchestration/pipelines/intelligence.py:60`)
  — four independent producers (Reporting / Explainability / Dashboard /
  Monitoring) feeding Timeline, then Export. This is the presentation-layer
  pipeline. Cross-pipeline context threading between Execution and
  Intelligence is explicitly deferred (`intelligence.py:12`).

The actual regime→...→decision chain is driven by a **separate, lighter**
engine: `athena.runtime.workflow.WorkflowStage`/`build_definition`
(`runtime/workflow.py:65,194`), invoked per-instrument from
`ops/owner_validation.py`'s `builder()` closure, and executed across the whole
scanner universe by `scanner/scanner.py:45`
(`DailyMarketScanner.scan()` → `_scan_one()` →
`self._workflow_engine.execute(plan.definition, ...)`).

**In practice: "orchestration" means two unrelated things depending on which
package you're reading**, and this document flags that explicitly rather than
presenting `orchestration/` as if it were the one pipeline driver for
everything.

### 3.3 Protocol interfaces — the actual count and where they concentrate

34 `class X(Protocol)` definitions exist across the repo (excluding tests),
concentrated in `api/` and `data/`, not evenly spread one-per-module across a
clean 17. Representative examples beyond the two already covered in
[§2.3](#23-provider-abstraction-pattern):

- `domain/interfaces.py:115` — `IntelligenceModule(Protocol)`, described in
  its own docstring as "the universal module contract (ATHENA-002 §7.1,
  ADR-003)" — **but ID-0's runtime audit (ADR-003 Amendment 1, 2026-08-29)
  found no engine implements it and it has zero non-test callers.** What
  actually governs the regime/scoring/decision engines' shape is each
  engine's plain method signature plus its `WorkflowStage`'s
  `depends_on`/`produces` declaration (§3.1/§3.2) — this Protocol is
  dormant/legacy scaffolding, not a live contract.
- `orchestration/models.py:134` — `PipelineStage(Protocol)`.
- `scheduling/dry_run.py:27` — `DryRunPipeline(Protocol)`.
- `data/providers/kite_transport.py:39` — `KiteTransport(Protocol)`.
- `api/v1/providers/base.py` — 10 Protocols alone (`HealthProvider`,
  `DecisionProvider`, `PortfolioProvider`, `ReportProvider`, and others) — API
  read-contracts, not analytical-pipeline contracts.

README's "17 modules behind Protocol interfaces" is best read as ATHENA-002
§2's module count (an architecture-document convention), not a literal count
of `Protocol` class definitions in the codebase — the real number is roughly
double, and skews toward API/data plumbing rather than the regime-to-decision
chain. Of `domain/interfaces.py`'s three Protocols, only two actually govern
anything live: `MarketDataProvider` (ADR-002, every provider implementation)
and `InstitutionalFlowProvider` (ADR-008). `IntelligenceModule` is dormant
(see immediately above) — the regime-to-decision chain's real per-stage
contract is each `WorkflowStage`'s `depends_on`/`produces` declaration, not
this Protocol.

### 3.4 Portfolio/planning stack — no order-placement code (verified, not assumed)

Given this is a load-bearing safety invariant (`ATHENA_BRIEFING.md` §2: "No
order-placement code anywhere in this repo... Grep for it before you trust a
claim that it doesn't exist"), it was checked directly rather than taken on
faith:

```bash
grep -rniE "place_order|placeorder|order\.place|submit_order|kite\.(place|modify|cancel)|\.place\(|execute_trade|send_order" src/athena --include="*.py"
# 0 matches
grep -rn "kiteconnect|KiteConnect" src/athena --include="*.py"
# only a `KiteConnectionState` Literal type and docstring references — no SDK import
```

Every planning package states the negative outright in its own `__init__.py`
docstring: `portfolio/__init__.py` — "Performs no market analysis";
`allocation/__init__.py` — "Performs no market analysis, position sizing, or
order execution"; `sizing/__init__.py` — same pattern; `orders/__init__.py` —
"Performs no broker communication, live order placement, or market analysis";
`brokers/__init__.py` — "Performs no network communication, OAuth flows, or
live order placement"; `execution/__init__.py` — "Performs no live broker
polling, WebSockets/REST calls, or exchange connectivity." The Kite provider
itself documents the same restriction from the data side:
`data/providers/kite_provider.py:1-7` — "Uses allowlisted GET-only HTTP
(`kite_transport`) — no order methods, no `kiteconnect` SDK (which exposes
placement APIs)."

### 3.5 Backtest, scanner, watchlist, strategy — reuse, not reimplementation

- **`scanner/`** (M4.2) is the production driver from
  [§3.1](#31-the-real-per-instrument-execution-graph-has-6-stages-not-8-or-11):
  it takes a universe of instrument ids and executes the real
  `runtime.workflow` engine per instrument, persisting genuine `Decision` rows.
  It is the harness *around* the live engines, not a parallel implementation.
- **`backtest/`** (M4.5) documents itself explicitly as "deterministic
  chronological replay of ATHENA's **existing operational pipeline**.
  Orchestrates only; the analytical core remains the single source of truth"
  (`backtest/__init__.py:1`) — it re-drives the same engines over historical
  `as_of` timestamps rather than reimplementing any formula.
- **`watchlist/`** (M4.3) is pure state-coordination over already-produced
  scan/decision artifacts — "Coordinates state only" (`watchlist/__init__.py:1-2`).
  It reads decisions; it does not produce them.
- **`strategy/`** (M4.4) is a selection-policy layer over completed decisions
  — "Coordinates evaluation only; no analytical calculation"
  (`strategy/__init__.py:1-3`). It filters/ranks what the pipeline already
  decided.

### 3.6 Reporting vs. explainability vs. timeline

`ATHENA_BRIEFING.md` §6 already flags `reporting/` as doing double duty, and
this is confirmed at the class level: `reporting/engine.py` contains both
`DecisionReportingEngine` (line 36, M3.7 — "transforms immutable decision
artifacts into deterministic human/machine-readable reports") and
`ReportingEngine` (line 361, P6.1 — generic operational reports). These are
genuinely two responsibilities in one package, not a naming accident.

`explainability/` (P6.3) is broader than `reporting/` — its docstring states
it "generates deterministic, human-readable explanations describing why
decisions, allocations, sizing, execution plans, lifecycle outcomes, and
analytics were produced" (`explainability/engine.py:1-5`), importing from
`allocation`, `brokers`, `execution`, and `analytics.portfolio` as well as
`decision` — it spans the whole platform, not just the decision engine.

`timeline/` (P6.4) is neither a report generator nor an explanation
generator: it "reconstructs chronological timelines and audit entries from
immutable platform artifacts" (`timeline/engine.py:1-4`), pulling from
`allocation`, `analytics.portfolio`, `dashboard`, `decision`, `execution`, and
`explainability` snapshots into one ordered audit trail — it is the
aggregation point that feeds `export/` in the Intelligence Pipeline described
in [§3.2](#32-two-independent-execution-frameworks-not-one-orchestrator).

---

## 4. API layer

### 4.1 App assembly

`create_app(settings: APISettings | None = None) -> FastAPI`
(`api/app.py:233`) is a factory function: loads `.env`, validates
`jwt_secret` is at least 32 bytes (raising `ValueError` otherwise, lines
244-250), constructs `FastAPI` with docs/OpenAPI URLs from
`AppMetadataConfig`, wires security singletons onto `app.state`
(`token_signer`, `claims_factory`, `auth_service`, `login_limiter`, seeded
owner user — lines 264-286), wires platform providers and SQLite providers
(lines 299-304), adds middleware (lines 307-314), registers exception
handlers (line 317), mounts a root `/` → `/dashboard/` redirect, includes the
platform routers, the v1 router, DarvaX conditionally, and finally the
dashboard static mount.

### 4.2 Versioning & response envelope

`api/v1/router.py` aggregates **18 router files** — health, metrics, auth,
dashboard, decisions, portfolio, market, pipelines, scheduler, workspace,
reports, analytics, exports, strategies, backtests, ops, saved_symbols.

Every successful response uses one contract, `AthenaResponse[T]`
(`v1/dtos/base.py:67-83`): `status: Literal["success"]`, `data: T`, `meta:
ResponseMeta` (request_id, api_version, as_of), optional `pagination`.
**Errors deliberately do not use this envelope** — they use RFC 9457 Problem
Details instead (see [§4.5](#45-errorexception-model)). Collections go
through `CollectionResult[T]` (`base.py:127-148`) with
`PaginationParams`/`SortParams`/`FilterParams` query models.

No customization exists beyond FastAPI's default OpenAPI generation — no
`custom_openapi` override anywhere in `src/athena/api`. Security schemes
appear in the generated schema because they're declared via FastAPI's
standard `fastapi.security` classes (`HTTPBearer`, `APIKeyHeader` in
`security/dependencies.py:35-36`), not via a manual schema patch.

### 4.3 Security & auth

Auth is **JWT (HS256)** via `HMAC256TokenSigner` (`security/token.py:31-61`).
`TokenClaimsFactory` (lines 64-119) issues access tokens (15 min default) and
refresh tokens (7 days default), each carrying `sub`, `username`, `role`,
`session_id`, `token_type`.

**Login** (`AuthService.login`, `security/service.py:57-120`) verifies a
bcrypt hash (12 rounds default), creates a session row, and stores only a
SHA-256 hash of the refresh token (line 100) — the raw refresh token is never
persisted. **Refresh** (lines 122-211) detects refresh-token reuse via
`secrets.compare_digest` and immediately revokes the session on a mismatch —
replay protection, not just expiry checking.

`get_current_user` (`security/dependencies.py:79-113`) tries, in order:
Bearer JWT → `X-API-Key` header → an `access_token` query parameter
(explicitly for `EventSource`, which cannot set headers — comment at line
94) → **single-user bypass**. The bypass
(`security/owner_seed.py:20-38`) is true only when no
`ATHENA_OWNER_PASSWORD_HASH` is set in the environment **and**
`ATHENA_SINGLE_USER=true` — setting an owner password hash always disables
the bypass regardless of the single-user flag, and the bypass is additionally
guarded by `"pytest" not in sys.modules` (`dependencies.py:103`) so a test
process never silently gets an admin principal.

**Client-side flow** (`static/js/01-auth.js`): tokens live in
**`sessionStorage`**, never `localStorage`. `bootstrapSession()` calls
`GET /api/v1/auth/status` on load; a 401 during any subsequent request
triggers one `refreshAccessToken()` attempt (guarded against infinite retry),
and on failure the tokens are cleared and the unlock screen re-shown
(`static/js/04-api-client.js:39-49`).

**Rate limiting**: `LoginAttemptLimiter` (`security/login_limiter.py`) is an
in-process, thread-safe limiter keyed by `(username, ip)` — 5 failures / 10
minute window / 15 minute lockout by default, raising
`AuthenticationLockedError` mapped to HTTP 429 with a `Retry-After` header.
This is login-only; there is no general per-route rate limiter.

**CORS**: `TransportConfig` defaults to `cors_origins: []`,
`cors_allow_methods: ["GET"]`, `cors_allow_credentials: False`
(`config.py:24-30`, comment: "Secure default: no origins allowed"). Critically,
`api_settings_from_env()` only overrides `SecurityConfig` fields from
environment variables — it never touches `TransportConfig`, so there is no
environment override that opens CORS up. Combined with `host: "127.0.0.1"`,
this is consistent throughout with a localhost-only, single-user design.

### 4.4 Middleware

Only one middleware stack is actually wired: `CORSMiddleware` then
`PlatformMiddleware` (`platform/middleware.py:38-93`), which generates and
propagates request/correlation IDs, wraps `call_next` to catch any exception
escaping the ASGI stack and route it through `exception_mapper.classify()`,
injects `X-Request-ID`/`X-Correlation-ID`/`X-API-Version` response headers,
and logs one structured line per request.

**A second middleware module, `api/middleware.py`, defining
`RequestIDMiddleware` and `StructuredLoggingMiddleware`, is dead code** — a
repo-wide grep found no `add_middleware` call referencing either class
anywhere in `src` or `tests`. `PlatformMiddleware` appears to have absorbed
both responsibilities in a later refactor without the superseded file being
removed.

### 4.5 Error/exception model

`exceptions.py` defines API-specific `AthenaError` subclasses
(`APIResourceError`, `ResourceNotFoundError`, and roughly 15 concrete
`*NotFoundError`/`*ConfirmationError` types). `errors.py` holds
`AthenaExceptionMapper` — an ordered registry mapping exception type to
`(http_status, problem_slug, title)`, matched by first-`isinstance` (so
ordering is MRO-sensitive). `classify()` logs full tracebacks server-side only
for 5xx responses, and always returns a `ProblemDetail` (RFC 9457: `type`,
`title`, `status`, `detail`, `instance`, `request_id`, `correlation_id`,
`timestamp`, optional `invalid_params`) — never a raw stack trace to the
client.

Four handlers (`api/app.py:115-230`) funnel every error path into this
mapper: `AthenaError`, `ValueError`, `RequestValidationError` (422 with
per-field messages), `StarletteHTTPException` (with a special case — a 404
under `/dashboard` serves `index.html` instead, so the SPA's client-side
routing works), and a catch-all `Exception` handler.

Two concrete traces: a `DecisionNotFoundError` resolves through
`ResourceNotFoundError` to HTTP 404 with `type=.../decision-not-found`. An
`AuthenticationLockedError` raised by the login limiter resolves to HTTP 429
plus a computed `Retry-After` header.

### 4.6 Platform diagnostics

Matches `docs/API_PLATFORM_GUIDE.md`, confirmed against the code:
`GET /health`, `/health/live`, `/health/ready` all return a
`PlatformHealthDTO`; `/live` is a pure process ping with no dependency check;
`/ready` and `/health` delegate to `HealthService` and aggregate component
statuses. One detail worth flagging: a component being `DOWN` is surfaced in
the response *body*, not as an HTTP 503 — the route itself always returns 200.
`GET /api/version` returns build metadata via the `BuildInfoProvider`
Protocol; `DefaultBuildInfoProvider` reads `ATHENA_BUILD_NUMBER`/
`ATHENA_COMMIT_HASH` from the environment but **falls back to shipped
placeholder values** (`build-456`, `commit-sha-placeholder`) when unset — see
[§9](#9-known-documentationimplementation-gaps).

### 4.7 The satellite-mount pattern

`api/darvax_mount.py` is the whole mechanism in one file (see
[§2.8](#28-module-boundary-enforcement) for the isolation guarantee).
`darvax_activation_requested()` reads only the `enabled` boolean from
`config/darvax.json`, treating a missing file as `False`.
`mount_darvax_if_enabled()` checks that flag first and returns immediately if
disabled; the DarvaX import happens only inside this function body. If
enabled but the module can't actually be imported or wired, it raises
`ConfigError` — "hard startup failure, not a silent downgrade" per the code
comment — rather than mounting a broken sub-app. Exactly two `app.state`
attributes (`token_signer`, `claims_factory`) are shared onto the mounted
sub-app, so DarvaX can delegate auth to ATHENA rather than build its own
login flow — nothing else (no providers, no repositories, no config) crosses
the seam. This is the template any future satellite module would follow.

### 4.8 Static asset serving

**Two different strategies coexist, and they are inconsistent.** ATHENA's own
dashboard is mounted with plain `StaticFiles(directory=static_dir,
html=True)` — no custom cache headers, no revalidation wrapper.
Cache-busting is entirely a client-side query-string convention:
`index.html` references `dashboard.css?v=9.147.0` and
`dashboard.js?v=9.147.0`. DarvaX, by contrast, uses a `RevalidatedStatic`
subclass (`darvax/api/app.py:34-53`) that forces `Cache-Control: no-cache,
must-revalidate` on every response, used only for its own `/static` mount.
ATHENA's core dashboard does not use this class. See
[§9](#9-known-documentationimplementation-gaps) for the practical
consequence.

---

## 5. Frontend architecture

### 5.1 ADR-004 rationale

ADR-004 (`docs/adr/ADR-004-static-html-first.md`) frames Phases 0-3 around
static HTML with vanilla JS, deferring a server "to Phase 4, triggered by the
first write-path feature (journal UI), not by speculation" (line 15) — the
stated reasoning being that "a server adds ports, auth surface, and a process
to babysit — costs that buy nothing until the UI must accept input" (line
11). Rejected alternatives, named explicitly: FastAPI from day one (server
complexity before any interactive need), a desktop GUI via Qt/Tauri (heavier
stack, violates the constitution's minimal-stack preference), and a terminal
UI (fails the dashboard-clarity philosophy). No React/Vue-class framework is
even named as a considered alternative — "no framework" is asserted directly
in the ADR's decision, not argued against a specific rejected one.

**The app has moved well past this ADR's original scope.** It is now
FastAPI-served with a genuine single-page-app shell, client-side tab
switching, and REST calls throughout — ADR-004 documents the *original phased
rationale* for starting static-first, not a description of the current SPA's
mechanics. The "no build step, no framework" *constraint* still holds
completely; only the "static HTML files, no server" *starting point* has been
superseded by Phase 4, exactly as the ADR itself anticipated.

### 5.2 Dashboard SPA structure

`api/static/index.html` (1,654 lines), titled "ATHENA — Investment Workstation
& Operations Console," has five nav-driven tabs, switched client-side with no
page reload:

1. **Overview** — portfolio snapshot (total value, cash, positions), holdings
   & exposure table, NAV trend and sector-exposure charts, a "Log fill" form
   for owner-entered positions, capital allocation pools, a guarded "Reset
   fills" control.
2. **Market Intelligence** — the Market Summary hero (F-5/MH-3), the
   Validation Pipeline funnel, the Universe browser, Recent Activity, Saved
   Symbols, Quick Actions, and a collapsible Trading Calendar & Events panel.
3. **Strategies & Scans** — Strategy Profiles Matrix and Backtest
   Replays/history.
4. **Decisions & Trace** — the largest tab: a grouped decisions list
   (Trade → Watch → No trade), a Decision Brief cockpit with a four-tab
   detail pane (recommendation, summary, chart, analysis breakdown), a Quick
   Summary card, and a Reasoning Trace pipeline view.
5. **Live Operations** — an ops/telemetry workspace (telemetry chart, restart
   control, diagnostics popover).

A sixth tab, **DarvaX**, is injected at runtime by a separate script and is
not present in `index.html`'s own markup at all — see
[§5.6](#56-darvax-as-a-second-independent-frontend).

### 5.3 Server-side JS assembly / native CSS @import

`DASHBOARD_JS_PARTS` (`api/app.py:54-79`) is a 24-item ordered tuple —
`_header.js`, `00-state-and-dom.js`, `01-auth.js`, `02-kite-gate.js`,
`03-app-shell.js`, `04-api-client.js`, `05-utils.js`, `06-ui-helpers.js`,
`07-decision-format.js`, `08-portfolio.js`, `09-market-intelligence.js`,
`10-strategies-backtests.js`, `11-decision-state.js`, `12-decisions-list.js`,
`13` through `19` (Decision Brief sub-parts: core, analysis, context, chart,
compare, trace, history), `20-operations.js`, `21-bootstrap.js`, `_footer.js`.
`assemble_dashboard_js()` reads each file fresh (no caching) and joins them,
reproducing the original single-file `dashboard.js`'s one
`DOMContentLoaded` closure **byte-for-byte** — confirmed by
`test_dashboard_js_assembled_losslessly_from_concern_split`
(`tests/api/platform/test_dashboard_hosting.py:2327`), which asserts the
served bytes equal the function's output and that the file still starts with
the original wrapper prefix and ends with `});`. This is served by a
dedicated route, `GET /dashboard/dashboard.js`, registered *before* the
`StaticFiles` mount so it intercepts that path.

**CSS needed no equivalent mechanism.** `dashboard.css` (21 lines) is a
static file using the browser's native `@import url(...)` for 14 part files
(`00-tokens.css` through `13-context-history.css`), served directly by
`StaticFiles`. Its header comment states import order is "load-bearing" to
reproduce the original single 4,900-line file's cascade. `<script>` tags have
no browser-native multi-file mechanism the way CSS's `@import` does — that
asymmetry is the entire reason JS needed a server-side workaround and CSS
didn't.

**Net effect**: the browser requests one `dashboard.js` (assembled per-request
by a FastAPI route; no such file exists on disk) and one `dashboard.css`
(itself a thin manifest resolved into 14 further requests natively by the
browser). Zero bundler, zero build step, either way.

### 5.4 State management

No framework means no component-local state and no reactive re-render.
`00-state-and-dom.js` defines one module-scoped `const state = {activeTab,
authRequired, authenticated, kiteRequired, kiteConnected, telemetry: {...},
advisorPulse: {...}, marketSession}` object, immediately followed by dozens
of `const` DOM-reference bindings captured once at load (`navItems`,
`tabPanes`, per-field elements, chart canvas contexts). Because all 24
concatenated files execute inside one shared `DOMContentLoaded` closure
(enforced byte-for-byte, [§5.3](#53-server-side-js-assembly--native-css-import)),
every part function reads and writes `state` and the cached DOM references as
ordinary closure variables — no module system, no pub/sub, no observed
reactivity. DarvaX's `tab.js` injector notes a direct consequence: ATHENA's
`navItems`/`tabPanes` are captured as a static `NodeList` via
`querySelectorAll` at load time, so anything injected into the DOM afterward
is invisible to ATHENA's own tab-switch logic — this is exactly why DarvaX has
to manage its own tab-activation state independently (§5.6).

### 5.5 Charting — the record, corrected

README, ADR-004, and `docs/design/ATHENA-SYMBOL-CHART-ROADMAP.md` all state
"Lightweight Charts" as the accepted charting library. **This is not what is
shipped, and the discrepancy is worth stating plainly rather than repeating
the aspirational documentation:**

- `index.html:1641` loads `<script src="https://cdn.jsdelivr.net/npm/chart.js">` —
  Chart.js, CDN-loaded, not vendored, and not Lightweight Charts.
- `new Chart(...)` is used in exactly four places, all secondary/summary
  charts: NAV trend and sector exposure on Overview (`08-portfolio.js:291,366`),
  the backtest comparison chart (`10-strategies-backtests.js:192`), and the
  ops telemetry chart (`20-operations.js:165`).
- The **primary** trading chart — the Decision Brief's symbol/price chart —
  is hand-rolled inline SVG, no library at all:
  `16-decision-brief-chart.js:529` builds
  `<svg class="decision-candlestick-chart decision-chart-svg" ...>` by string
  template.
- The roadmap document's own audit already acknowledges this: "Current
  renderer: `16-decision-brief-chart.js` — hand-rolled SVG chart"
  (`ATHENA-SYMBOL-CHART-ROADMAP.md:55-57`). Milestone CH-0 required a choice
  between vendored Lightweight Charts and a CDN fallback; `docs/MILESTONES.md:256`
  records CH-1's actual resolution as "None — implemented with local static
  JS/CSS, **no new dependency**." The whole 7-milestone "Symbol Chart
  Excellence" track closed without ever introducing Lightweight Charts.

**Conclusion for anyone reading only the older docs**: "Lightweight Charts"
is superseded aspirational language. The real chart stack is hand-rolled SVG
for the primary chart plus CDN-loaded Chart.js for four secondary charts.

### 5.6 DarvaX as a second, independent frontend

The injection into ATHENA's dashboard is **DOM manipulation from a
same-origin `<iframe>`**, not a build-time merge. `index.html` carries
exactly one DarvaX reference: `<script src="/darvax/static/tab.js" defer>`,
served only by the DarvaX sub-app — disable or delete DarvaX and this 404s,
and the injector script simply never runs. At runtime, `tab.js`'s `build()`
function creates its own `<style>` tag ("never in ATHENA's CSS," per its own
comment), appends a nav item to `nav.sidebar-nav`, and appends a `.tab-pane`
containing an `<iframe class="darvax-embed">` whose `src` is set only on
first activation to `/darvax/?embedded=1&v=<UI_VERSION>` — same-origin, so
the `sessionStorage`-held auth tokens carry over automatically. Because
ATHENA's tab-switch logic snapshotted its nav/pane lists before this
injection ran ([§5.4](#54-state-management)), DarvaX's tab is invisible to
ATHENA's own `switchTab()`; `tab.js` compensates with its own
activate/stand-down logic, listening in the capture phase for clicks on
ATHENA's other nav items so it can deactivate itself. This runtime coupling
is documented in the code itself as "the runtime coupling Amendment 1 records
as an accepted, monitored risk."

### 5.7 Asset versioning discipline

The `?v=` query-string bump is a purely manual convention — literal strings
in `index.html` (`dashboard.css?v=9.147.0`, `dashboard.js?v=9.147.0`), with
DarvaX carrying its own independent version string
(`?v=0.1.0-dx11a`, doubling as `UI_VERSION` for its iframe cache-busting). No
tooling derives or bumps this automatically. The only test coverage is a
**regression test that pins the current literal value**
(`tests/api/platform/test_dashboard_hosting.py:243-244`) — this catches the
version string being accidentally removed or reverted, but it structurally
cannot catch a source file being edited without the string being bumped
forward, since the test itself would need updating in lockstep with any
legitimate bump. This is a known, previously-hit risk (recorded separately as
a standing lesson: bump `?v=` on every static JS/CSS edit or the browser
keeps serving the stale file).

### 5.8 CSS approach

No framework — `dashboard.css` and its 14 `@import`ed parts are hand-written;
sampled class names (`.card`, `.metric-value`, `.tab-pane`, `.grid-layout`)
are ATHENA-specific, not a utility vocabulary like Tailwind's. Design tokens
live in `00-tokens.css`, the first import, consistent with a `:root`
custom-properties file — the exact token list and whether a dark-mode media
query exists were **not directly confirmed** in this pass (the file's
contents weren't read); state this as unconfirmed rather than asserting a
specific theme mechanism until someone reads `css/00-tokens.css` directly.

---

## 6. Testing, tooling & dev workflow

### 6.1 Test suite structure & hermetic isolation

`tests/` mirrors `src/athena/`'s ~33 module directories at a coarse,
concern-cluster granularity rather than 1:1 — e.g. `tests/market_intel`
covers `regime`+`market_health`+`sector_health` together, `tests/data_layer`
and `tests/data` split the persistence layer, and `tests/unit` catches
modules without a dedicated directory. **1,970 tests collected**
(`python3 -m pytest --collect-only -q`).

`tests/conftest.py`'s `config_dir` fixture `shutil.copytree`s the real
`config/` into `tmp_path` and injects deterministic calendar fixtures — no
test ever asserts against production config values directly.

**The hermetic-isolation guard exists because it was violated twice, in
production, for real.** `tests/conftest.py`'s autouse
`darvax_never_activates_in_tests` fixture monkeypatches
`mount_darvax_if_enabled` to a no-op for the entire suite; its docstring
records the first incident: enabling DarvaX made roughly 1,300 unrelated
tests silently open and migrate `db/darvax.db`, invisible because schema
initialization is idempotent. A second, more severe incident is recorded in
`tests/darvax/conftest.py`: on 2026-08-16 the owner had DarvaX enabled and
opted into a 2,191-instrument universe, and API tests that `POST /screen`
ran full sweeps against the **production** database — writing real sweeps,
screen results, and thousands of signals into it. The fix,
`darvax_config_is_hermetic` (also autouse), pins `ATHENA_CONFIG_DIR` and
monkeypatches the DarvaX repo-root resolver to a `tmp_path` root for every
test. **The general lesson recorded structurally, not just in a comment**: a
"remember to point the test at a scratch config" convention is not a
safeguard; making hermeticity autouse is.

### 6.2 Type checking scope

```toml
[tool.mypy]
python_version = "3.10"
strict = true
files = ["src/athena/domain", "src/athena/config"]
```

No ADR or comment anywhere in the repo documents *why* strict mypy is scoped
to exactly these two packages — this is an inference, not a stated decision:
`domain/` is the frozen canonical model every other module consumes (a type
error there propagates everywhere downstream), and `config/` is the
pydantic-validated boundary where every JSON file becomes a typed model —
together, the two highest-leverage places for a type error to be caught
early. `docs/PRODUCTION_READINESS_ROADMAP.md` has no item proposing to widen
strict-mypy scope beyond these two packages.

### 6.3 Linting

```toml
[tool.ruff]
line-length = 120
target-version = "py310"
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
```

In plain terms: **E** = pycodestyle style violations, **F** = pyflakes
(unused imports/names, real correctness bugs), **I** = import
ordering/grouping (isort-equivalent), **UP** = pyupgrade (modernize syntax to
the target Python version), **B** = flake8-bugbear (bug-prone patterns —
mutable default arguments, misused `except`, etc.), **SIM** =
flake8-simplify (redundant/overcomplicated code that collapses to something
simpler), **RUF** = Ruff-native checks not covered by the ported linters. In
active use: `cli.py:78` carries `# noqa: SIM108` suppressing a
simplify-to-ternary suggestion, with the reason stated inline ("explicit
block reads clearer").

**No CI runs any of this.** Confirmed: no `.github/`, `.gitlab-ci*`, or
`.circleci/` directory exists anywhere in the repo. Ruff, mypy, and pytest
execute only when a human or an agent invokes them locally — nothing gates a
commit or a push.

### 6.4 CLI & entry points

`pyproject.toml`'s `athena = "athena.cli:main"` resolves to `cli.py:960`.
Registered subcommands: `today` (calendar context), `health` (pre-flight
check), `version`, `ingest` (one live ingest cycle), `backfill-sector-indices`
(one-time historical backfill), `config-preview` (replay-based config diff),
`due` (show due scheduling triggers), `cycle` (one scheduled dry-run cycle),
`run-due` (run all due cycles, optionally brief/alert on failure), `serve`
(start the localhost API, optionally with the cycle worker), `seed-candidates`
(fetch Nifty 500 constituents), `validate-symbols` (ingest+score specific
symbols), `brief` (assemble/dispatch the daily briefing), `diagnose`
(playbook diagnostics), `weight-drift-baseline`, `set-owner-password` (bcrypt
hash generator), `kite-auth` (interactive daily Kite login).

`./athena-serve` (repo root, 15 lines) is **not a separate program** — it's a
thin bash wrapper that sets `PYTHONPATH`, sources `.env`, and execs
`python3 -m athena.cli serve "$@"`. So `athena-serve --with-cycles --open` is
literally the `serve` subcommand with two argparse flags forwarded.

---

## 7. Scheduling, live data & operations

### 7.1 Cadence engine

`--with-cycles` starts a `CycleWorker` ticking every `cycle_interval` seconds
(default 60), which runs `HostDueRunner`. The pure cadence logic lives in
`scheduling/cadence.py` — `is_premarket_due`, `is_refresh_due`, `is_fast_due`,
`is_closing_due`, and `due_triggers`, explicitly documented as pure functions
of an injected `as_of` and last-run markers: "no wall clock, no cron library"
(module docstring). Cadence source-of-truth is `config/scheduling.json`:
premarket at `08:15`, a refresh interval falling back to
`config/base.json`'s `refresh_interval_minutes: 15`, closing at `15:45`, and
a `fast` tier at 10-minute intervals for up to 150 symbols on 5-minute
timeframes — the config's own `_meta` comment records this fast tier having
been "scaled back 2026-08-10" after a 5-minute/400-symbol setting drove the
shared Kite historical endpoint to ~42% duty cycle, starving ad-hoc
single-symbol validation requests. This is a rare, valuable thing to have on
record: a config value with its own incident history attached.

**Calendar gating**: `due_triggers` takes an explicit `is_trading_day: bool`
parameter and short-circuits to `()` if false — the docstring records why:
"on a weekend/holiday, Kite's quotes are legitimately frozen at the last real
session's close — every REFRESH/CLOSING cycle the host cron fired anyway
failed the ingestion freshness check, all day." The caller resolves this via
`CalendarEngine.context_for(...)`. `cadence.py` itself imports no calendar
module — it stays a pure function of a boolean its caller computed, exactly
the separation described in [§2.5](#25-calendar-module).

### 7.2 Kite Connect ingestion & auth

`data/providers/kite_provider.py` documents itself as a "Zerodha Kite
Connect read-only MarketDataProvider," using allowlisted GET-only HTTP with
no order methods and no `kiteconnect` SDK (which exposes placement APIs) —
supporting `kite_transport.py` (the allowlisted HTTP layer), `kite_ltp.py`
(last-traded-price), and `factory.py` (provider selection). Timeframe
mapping and per-request chunk sizes are hardcoded to Kite's own API limits
(e.g. daily candles chunked at 2000 days, minute candles at 60 days).

**Auth is a daily manual step, not an automatic refresh.** `ops/kite_auth.py`
drives a login-URL → local-HTTP-redirect-capture → token-exchange flow that
writes `KITE_API_KEY`/`KITE_API_SECRET`/`KITE_ACCESS_TOKEN` into `.env`.
Kite tokens expire daily, and the CLI's `kite-auth` subcommand (help text:
"Interactive daily Kite login") must be re-run each trading day — `README.md`
frames this as the "Kite gate when needed" step in the morning
workstation-entry sequence.

**Corporate actions** get a dedicated module,
`data/corporate_actions/` — its docstring states it "applies corporate
actions to canonical candle datasets deterministically, producing ADJUSTED
COPIES with full evidence... never mutates originals," documenting exact
formulas for splits (`price *= from/to`), bonuses, and dividends
(`price *= (prev_close - amount) / prev_close`), all cumulative and
evidence-carrying per ADR-005 ([§2.7](#27-explainability-as-data-adr-005)).

### 7.3 Deployment model

No Dockerfile, no docker-compose file, anywhere in the repo. The k8s
reference in the platform guide and in `platform/health.py`'s own comment
("Standard k8s/runtime process liveness ping") is a compatibility gesture —
the `/health/live` endpoint's shape happens to satisfy what a k8s
livenessProbe expects — not evidence of an actual orchestration target.
There is no container image and no deployment manifest. The real deployment
is `./athena-serve` invoking `uvicorn.run(...)` bound to `127.0.0.1` as a
single local process, consistent with the README's safety invariants
describing local-only operation with a gitignored database.

### 7.4 Database footprint

```
db/athena.db      2,890.4 MB
db/athena.db-wal      4.1 KB
db/darvax.db         32.6 MB
db/darvax.db-wal      5.2 MB
```

Two entirely separate SQLite files, each with its own WAL sidecar — the
concrete evidence, at the filesystem level, of ADR-010's DarvaX-owns-its-own-
database boundary. `athena.db` is roughly 90× larger than `darvax.db`,
consistent with it holding candles/quotes/runs/decisions across the ~528-
symbol scanner universe accumulated over a much longer history than the
newer, opt-in DarvaX satellite.

---

## 8. DarvaX as a worked case study

DarvaX (ADR-010) is worth reading as a single example that exercises nearly
every pattern documented above, because it is the one module in the repo that
had to independently reinvent each of them rather than inherit shared
infrastructure — which is itself evidence the patterns generalize rather than
being accidental to the core codebase:

| Pattern | Core ATHENA | DarvaX |
|---|---|---|
| Frozen domain model | `domain/*.py` dataclasses | `darvax/signals/models.py`, `darvax/screening/models.py` — same `@dataclass(frozen=True)` convention |
| Config validation | `config/models.py` `_Strict` base | `darvax/config.py`'s own pydantic models, own file (`config/darvax.json`) |
| Persistence | `SqliteRepository`, `SCHEMA_VERSION` | Its own `DarvaxRepository`, own `SCHEMA_VERSION` (currently 9), own idempotent migrations, own database file |
| Provider abstraction | `MarketDataProvider` Protocol | Reads ATHENA's candles through the *same* Protocol, read-only, never a second concrete import |
| Explainability-as-data | `MarketHealthScore.explanation` | Every `ScreenResult` carries `action_reason`/`action_reason_plain` alongside the computed action |
| Module boundary seam | `darvax_mount.py` — the one file | Is the seam this pattern describes |
| Static-first frontend | `dashboard.js`/`.css` assembly | Its own completely separate `index.html`/`darvax.js`/`darvax.css`, zero shared assets |
| Asset versioning | `?v=` query string | Its own independent `?v=` string, `UI_VERSION` in `tab.js` |
| Validation-before-trust | (n/a — core engines are the trusted baseline) | `EXPERIMENTAL_UNVALIDATED` status gate, DX-5 sufficiency bar (200 closed trades **and** 500 trading days) before a claim of `VALIDATED` |

The DX-11 in-app guide (`darvax/api/static/index.html`'s `#guide` dialog) is
itself a smaller-scale example of exactly this document's own discipline:
every quoted rule and threshold in it is cross-checked in
`tests/darvax/test_dx11_guide.py` against the code that actually produces it,
for the same reason this document cites file:line throughout — a reference
document that can silently drift from the code it describes is worse than no
document.

---

## 9. Known documentation/implementation gaps

Recorded here rather than silently corrected elsewhere, so a future reader
knows these were found and not simply missed:

1. **Charting.** README, ADR-004, and the chart roadmap's introduction still
   say "Lightweight Charts." The shipped stack is hand-rolled SVG (primary
   chart) plus CDN Chart.js (four secondary charts) — see
   [§5.5](#55-charting--the-record-corrected). The roadmap's own body text
   already acknowledges this; only the older framing docs haven't caught up.
2. **"17 modules behind Protocol interfaces."** True as an architecture-plan
   module count, misleading as a literal count of `Protocol` classes (34
   exist, concentrated in `api/`/`data/`) — see
   [§3.3](#33-protocol-interfaces--the-actual-count-and-where-they-concentrate).
3. **Two orchestration frameworks share the word "orchestration."**
   `orchestration/` drives planning (Execution Pipeline) and presentation
   (Intelligence Pipeline); the live regime→decision analytical chain is
   driven by a separate `runtime.workflow` engine invoked from
   `ops/owner_validation.py` and `scanner/scanner.py`. See
   [§3.2](#32-two-independent-execution-frameworks-not-one-orchestrator).
4. **Dead middleware.** `api/middleware.py`'s `RequestIDMiddleware` and
   `StructuredLoggingMiddleware` are defined but never registered — 
   `PlatformMiddleware` superseded them. See [§4.4](#44-middleware).
5. **No CI, no containerization.** Ruff/mypy/pytest are local-only; there is
   no `.github/`, no Dockerfile. This may be entirely appropriate for a
   single-user, single-workstation tool — flagged as a fact, not a criticism.
6. **mypy's strict scope is undocumented.** `domain`/`config` only, with no
   ADR or roadmap item explaining the boundary or proposing to widen it. See
   [§6.2](#62-type-checking-scope).
7. **Static-asset caching is inconsistent between ATHENA core and DarvaX.**
   Core uses plain `StaticFiles` with a manual `?v=` bump; DarvaX forces
   `Cache-Control: no-cache, must-revalidate` via `RevalidatedStatic`. Neither
   is wrong, but a developer who has internalized one satellite's behavior
   will be surprised by the other's. See [§4.8](#48-static-asset-serving).
8. **`?v=` bumping is enforced only by a test pinning the current literal
   value**, which cannot catch a source edit made without a matching version
   bump — it can only catch the version string itself regressing. See
   [§5.7](#57-asset-versioning-discipline).
9. **Build-info placeholders are still the shipped defaults.**
   `DefaultBuildInfoProvider` falls back to `build-456` and
   `commit-sha-placeholder` when `ATHENA_BUILD_NUMBER`/`ATHENA_COMMIT_HASH`
   aren't set in the environment — worth noticing before trusting
   `GET /api/version` output as meaningful provenance. See
   [§4.6](#46-platform-diagnostics).
10. **No automated module-boundary enforcement outside the DarvaX seam
    (and, since ID-P0, one narrower exception).** No general import-linter
    or architecture test exists for boundaries between core modules (e.g.
    `scoring/` and `risk/`) — only Protocol typing, contract tests, and
    review. See [§2.8](#28-module-boundary-enforcement). One specific
    boundary now IS enforced by test: `tests/architecture/test_pipeline_mechanism_boundary.py`
    fails the suite if any production module imports the dormant
    `PipelineContext`/`ContextDelta`/`IntelligenceModule` types (item 11
    below) — narrower than a general import-linter, but a real, verified
    guard for the one boundary ID-0 found actually mattered.
11. **`PipelineContext`/`ContextDelta`/`IntelligenceModule` (ADR-003's
    originally specified mechanism) are dormant — zero non-test production
    callers.** ATHENA's real, live per-cycle pipeline runtime is
    `runtime.workflow.WorkflowContext`/`WorkflowStage`/`WorkflowEngine`
    (§2.1, §3.1, §3.2, §3.3). Found and resolved by ID-0/ID-P0
    (2026-08-29): see ADR-003 Amendment 1 and
    `docs/research/ID-0-RUNTIME-AUDIT-ARCHITECTURE-REPORT.md`. The dormant
    types are documented as legacy in their own module docstrings rather
    than deleted, pending a future cleanup milestone's dependency
    verification.
12. **`list_candles_recent(limit=100)` truncation and ORB slot-count-vs-
    canonical-slot completeness — found by ID-3, resolved by ID-3.1
    (2026-08-29).** ID-3's real-data sanity check found the shared
    `limit=100` fetch (VWAP/session/ORB) could exclude a session's own
    opening bars on a real day with elevated intraday row density (every
    one of 537 real instruments had 100-130 persisted `5m` rows for one
    session versus the canonical ~75). ID-3.1 fixed the retrieval itself:
    `session_stage`, `ind_stage`'s VWAP fetch, and
    `intraday_analytics_stage`'s ORB fetch now use the repository's
    existing `get_candles(instrument_id, timeframe, start, end)` bounded
    by `athena.session.session_day_start(as_of, tz)` — no new repository
    method, no arbitrary row-count ceiling. Owner code review separately
    found `OpeningRangeEngine._formation()` judged completeness by raw
    in-window row COUNT rather than exact canonical timestamp presence, so
    an off-grid/unexpected row could in principle substitute for a
    genuinely missing canonical opening-range slot; fixed by
    `_canonical_slots()`, which filters to exact expected M5 timestamps
    once, up front, before formation/relation/breakout ever run. A
    real-data acceptance check on the production retrieval path (no
    test-only limit) found OR15 resolves `COMPLETE` for 526/526 real
    candidates; OR30 resolves `COMPLETE` for only 3/526 — the real,
    previously-masked number (ID-3's own diagnostic read had been inflated
    by the counting bug) — traced to a real M5 timestamp-drift onset at
    the session's 6th canonical 5-minute slot (09:40) for 522/526
    instruments. See `docs/research/ID-3-*` and the ID-3.1 Milestone
    Review Summary for the full evidence. **Confluence's own 5m/15m
    fetches were deliberately left on the unbounded `list_candles_recent`
    path** — audited, not silently changed — because its rolling
    SMA(9)/SMA(5) genuinely reads across a session boundary early in the
    day today; whether that cross-session reach is intentional is an open
    methodology question for the owner, not yet decided either way.
13. **`RelativeStrengthContext`'s comparative dimensions for the settled
    2026-08-28 session: RESOLVED (2026-08-29, ID-5A); the underlying
    engine correctness was fixed earlier by ID-4.1.** ID-4's real-data
    audit found the market benchmark (`NSE:NIFTY 50`) and all 8
    sector-mapped indexes (`config/sector_index_mapping.json`) had only
    **1/75 canonical M5 slots** for 2026-08-28, materially worse than the
    equity-side drift item 12 found (clean through 5 canonical slots
    before onset). ID-4's ORIGINAL engine let this opening-only index data
    drag the GLOBAL `comparison_cutoff_ts` down to `09:15` for every
    candidate — collapsing `stock_available` to 0/526 too, an ENGINE
    artifact. ID-4.1 fixed this (`_ConstituentSeries.can_form_return`).
    **ID-5A then closed the DATA side**: the market benchmark and all 8
    sector indexes were opening-only specifically because 2026-08-28 had
    never been re-fetched by the settlement-repair mechanism (it was
    excluded as "today" when that mechanism last ran) — re-running it for
    this one now-settled date (owner-authorized, 2026-08-29) restored full
    75/75 canonical coverage. Re-measured on the identical production
    retrieval path, post-repair: `stock_return` 526/526 (unchanged);
    `sector_return`/`stock_vs_sector`/`sector_vs_market` 204/526 (exactly
    the real sector-mapping coverage — no data left unavailable);
    `market_return`/`stock_vs_market` 526/526. No nearest-neighbor/
    resampling/forward-fill/alignment rule was ever invented — the fix was
    re-fetching authoritative settled data, nothing else. **This result is
    for the settled 2026-08-28 session only** — whether TODAY's
    still-forming session ever offers this same coverage live, before it
    settles, is ID-5B's separate, still-open question (item 14). See the
    ID-4, ID-4.1, and ID-5/ID-5A Milestone Review Summaries for full
    evidence.
14. **Root cause of item 13's original index M5 coverage gap: CONFIRMED
    and the settled-history side REPAIRED (2026-08-29, ID-5/ID-5A) —
    Kite's own settle-lag on not-yet-settled candles, not an ATHENA code
    defect; live current-session semantics remain open (ID-5B).**
    `KiteProvider._historical()` (`src/athena/data/providers/kite_provider.py:406-476`)
    parses `ts_open` exclusively from the raw Kite historical-response row
    (`ts = _parse_kite_ts(str(row[0]))`, line 441) via a pure ISO-8601
    parser with zero rounding/flooring/substitution — independently
    re-verified by direct code reading. No index-vs-equity branching
    exists anywhere in the fetch path. This exact root cause was already
    investigated and mechanically fixed once before: a prior
    Owner/Chief-Architect-authorized repair
    (`src/athena/data/live_m5_settlement_repair.py`, core `athena.data`,
    dated 2026-08-28 — NOT an EMR module, zero `athena.explosive_move`/
    `athena.darvax` imports) corrected 1,051,481 off-grid M5 rows across
    537 instruments for 2026-07-28 through 2026-08-27. **ID-5A
    (owner-authorized, 2026-08-29) re-ran the identical, unmodified
    mechanism for the one remaining gap, 2026-08-28** (excluded from the
    prior run only because it was "today" then): 537/537 instruments
    succeeded, 0 failures, 60,410 off-grid rows → 0, backed by a fresh
    integrity-verified, checksummed backup
    (`db/backups/athena-pre-m5-repair-20260828-gap-20260829T155925Z.db`).
    No ATHENA code was changed. **Still open (ID-5B, not started):**
    Track B's live provisional-vs-settled OHLCV-content question
    (`live_m5_provisional_settlement_diagnostic.py` — built, unit-tested,
    never executed; needs an open trading session, next one 2026-08-31).
    ID-5 is not considered fully closed until ID-5B completes. See the
    ID-5/ID-5A Milestone Review Summary for full evidence.
15. **`GapContext` (ID-5C, 2026-08-29) does not account for corporate
    actions.** Whether ATHENA's persisted daily (`D1`) candles are
    split/bonus-adjusted around a corporate action was audited only to
    the extent of confirming no adjustment mechanism is invoked by
    `GapEngine` itself — not resolved further. If the underlying D1
    series is unadjusted, a genuine corporate action between the previous
    trading session and today could mechanically distort a raw
    `gap_pct` (e.g. a 1:2 split would show as an artificial ~50% gap
    down). No adjustment factor was invented to compensate; this is
    reported as a known, unaddressed limitation, not silently worked
    around.
16. **`RelativeVolumeContext` (ID-5D, 2026-08-29) does not account for
    corporate actions, and its baseline-length policy has an
    OWNER_PENDING question.** Volume series were not audited for
    split/bonus adjustment artifacts — if unadjusted, a corporate action
    between a historical comparison session and today could distort the
    ratio (e.g. a stock split roughly doubling share count without a
    corresponding real change in traded interest). No adjustment factor
    was invented. Separately: the engine uses ALL available comparable
    prior sessions rather than a hardcoded baseline-length N, currently
    capped at ~23 trading days by real M5 data availability (ingestion
    began 2026-07-28) — whether a rolling cap should be introduced once
    more history accumulates is an explicit, undecided OWNER_PENDING
    policy question, not resolved by this milestone.

---

## 10. Glossary & cross-reference index

| Term | Meaning | Where it's defined/governed |
|---|---|---|
| Frozen domain model | Immutable `@dataclass(frozen=True, slots=True)` canonical types | `src/athena/domain/`, `ATHENA-002-System-Blueprint.md` |
| Explainability-as-data | A computed value and its rationale are persisted as one object, never reconstructed later | ADR-005 |
| Provider abstraction | Business logic depends on a `Protocol`, never a concrete broker/data-source class | ADR-002, `domain/interfaces.py` |
| Modular monolith | One deployable process, internally divided by Protocol-typed module boundaries, not by network service | ADR-001 |
| PipelineContext | **Dormant/legacy** (ADR-003 Amendment 1) — reads as if it were the one per-run object every stage reads/writes, but has zero non-test production callers | `domain/context.py` |
| WorkflowContext | The real, live per-run object every pipeline stage reads from/writes to (via `WorkflowStage`/`WorkflowEngine`), immutable after each stage's contribution | `runtime/workflow.py`, ADR-003 Amendment 1 |
| Satellite module | An opt-in, self-contained module (own config/db/schema/frontend) mounted through exactly one seam file | ADR-010, `api/darvax_mount.py` |
| DAR-CARD | Darvas' own four-rule trading card, quoted verbatim wherever DarvaX cites it | `darvax/signals/models.py` `DAR_CARD_TEXT` |
| WAL mode | SQLite's write-ahead log, enabling concurrent readers alongside a writer | `data/store/repository.py:114`, ADR-009 |
| Single-user bypass | Auth shortcut active only when no owner password hash is configured and `ATHENA_SINGLE_USER=true` | `api/security/owner_seed.py` |
| Cadence engine | Pure functions computing which scheduled trigger is due, given an injected time and calendar answer | `scheduling/cadence.py` |
| DX-N / M-N / P-N | Milestone/phase identifiers used throughout commit messages and docstrings | `docs/MILESTONES.md` |

**Cross-references**:
- Trading methodology, formulas, thresholds → `docs/ATHENA-WORKFLOW-METHODOLOGY.md`
- REST API surface, per-endpoint detail → `docs/api/API-REFERENCE.md`, `docs/api/openapi.yaml`
- Platform diagnostics endpoints → `docs/API_PLATFORM_GUIDE.md`
- DarvaX satellite in full → `docs/adr/ADR-010-darvax-satellite-module.md` and `docs/design/DARVAX-*.md`
- Live status of any milestone mentioned here → `docs/MILESTONES.md` (never assume from this document — it is a snapshot)
- Process rules, commit discipline, milestone workflow → `CLAUDE.md`
- Fast orientation for a new session → `ATHENA_BRIEFING.md`
