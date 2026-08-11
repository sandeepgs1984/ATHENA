# ADR-010 — DarvaX as an isolated, opt-in satellite module

| | |
|---|---|
| Status | Accepted |
| Date | 2026-08-10 |
| Deciders | sandeep (owner) |

## Context

The owner wants the **DarvaX** methodology (Amitabh Jha / @AmitabhJha3, documented
in a 102-page deck compiled Dec 2022) available inside ATHENA, with an explicit
and overriding constraint:

> "completely independent module of current athena system … plug-n-play …
> should be disable whenever i want and should not affect athena in any form"

That constraint is the dominant design input and it **supersedes an earlier
suggestion made in-session** (before the constraint was stated) that DarvaX
contribute a `darvax_structure` component to `config/scoring.json`'s weights.
That approach is now explicitly rejected: a scoring component would make
ATHENA's own decisions change depending on whether DarvaX is enabled, which is
the exact opposite of what was asked. DarvaX must be a **parallel advisory
lane**, never a contributor to ATHENA's pipeline.

### What DarvaX actually is (source assessment)

The deck is 102 pages, of which **only pages 1–53 contain methodology**. Pages
54–102 have no text layer at all; read visually they are Twitter screenshots,
personal photographs, follower P&L screenshots, and donation posts. The
extractable method is a **Nicolas Darvas Box breakout system** adapted to Indian
equity cash:

- **Darvas Box rules**, reproduced on p.67 from Darvas' own "DAR-CARD": a stock
  in its *topmost box* is a HOLD and intra-box fluctuation is ignored; a move
  above the topmost box top is a BUY with a **10% stop** on first breakout; a
  fall below a newly-formed higher box's bottom is a SELL; there is no reason to
  hold or buy a stock that is not in its topmost box.
- **Screening checklist** (p.4): all-time-high price · less talked about · low
  float · superb quarterly numbers · bright future potential.
- **Stop ladder by horizon**, close-below basis ("DCB"): 5 EMA very-short-term ·
  10 EMA swing · 20 EMA positional · 200 EMA investor.
- **Entry trigger** (p.44): enter above previous day's high, 1% stop below entry.
- **Capital policy**: divide capital into 10 parts; never average down; cut
  losers fast, ride winners.
- **Fibonacci**: 23.6 / 38.2 / 50 / 61.8; a retracement holding in 23.6–38.2%
  denotes a very strong trend, 50–61.8% is the crash-accumulation zone.
- **ZigZag setup**: swing low → 61.8% retracement → buy above 10 EMA → ride to
  the next swing high.
- **Timeframe hierarchy**: weekly consolidation beats daily; monthly beats
  weekly.
- **Structure filters**: "uncharted territory" (no overhead supply), multiyear
  volume expansion, higher-high/higher-low structure, and a tight "baby candle"
  base after a 20–50% advance and a 10–20% correction (functionally VCP).

### Why this must not touch ATHENA's decision path — beyond the owner's constraint

The source document carries **no validation evidence of any kind**. Its entire
evidential basis is cherry-picked winners (Tarmat +36%, BSL +65%, Adani Power
+80%) and follower P&L screenshots: no sample size, no loss rate, no expectancy,
no drawdown. That is survivorship bias, not a tested edge. The author states as
much himself on p.77 ("You will Lose More Money by Following me .. here u wont
get Charts with Serious Levels, U dont Get SL or Target"). Wiring an unvalidated
method into the engine that produces the owner's live decisions would violate
ATHENA's first-principles rule that every number it shows is explainable and
earned. Isolation is therefore both what the owner asked for *and* what the
evidence justifies.

The document also contains a **hard internal contradiction on stop sizing**:
Darvas' canonical rule is a 10% stop on breakout (p.67), while DarvaX's own "How
to Play" says 1% (p.44). These are not variants of one system; a 1% stop on a
breakout entry is removed by ordinary noise. This ADR does not resolve that by
fiat — see Decision.

### Constraints from ATHENA's own rules

- Architecture is frozen; a new analytical surface needs an ADR (this one).
- No order-placement code, ever. Large parts of the deck concern F&O/options
  trading; ATHENA is equity-cash, advisory-only, and stays that way.
- `config/base.json`'s `features` block exists but is **read nowhere in the
  codebase** (verified by grep). It is not a usable enable/disable mechanism and
  this ADR does not pretend otherwise; DarvaX ships its own real one.

## Decision

Build DarvaX as a **satellite module**: a self-contained package that *reads*
ATHENA's market data through a narrow read-only port, keeps **its own database
file**, exposes **its own mounted sub-application**, and produces **its own
artifacts**. ATHENA's core never imports it, never depends on it, and behaves
identically whether it is enabled, disabled, or deleted from disk.

**1. Dependency direction is one-way, enforced.**
`athena.darvax.*` may import ATHENA's frozen domain objects and read-only
contracts. No module under `src/athena/` outside `darvax/` may import
`athena.darvax` — except the single guarded mount seam in §4. A test asserts
this by scanning the import graph.

**2. Separate persistence — its own database file.**
DarvaX owns `db/darvax.db`, created lazily on first enabled run, with its own
`darvax_schema_version` table and its own DDL. ATHENA's `SCHEMA_VERSION`,
`ddl_statements()`, `record_counts()`, backup, restore, and integrity checks are
untouched and remain unaware of DarvaX. Consequences: zero schema coupling, zero
write contention against ATHENA's write connection/`RLock` (ADR-009 stays
exactly as-is), and deleting one file removes every trace of DarvaX's data.

**3. Read-only access to ATHENA's data through a port.**
A `DarvaxMarketDataPort` Protocol (candles, instruments, and nothing else),
implemented over `SqliteRepository`'s existing read methods. DarvaX issues no
writes to any ATHENA table, ever — the Protocol exposes no write method, so this
is structural, not a convention.

**4. One mount seam, capped and measured — and loud when misconfigured.**
`create_app()` gains a guarded block of the shape:

```python
if darvax_activation_requested(config_dir):   # reads ONLY the enabled flag
    try:
        from athena.darvax.api import create_darvax_app
    except ImportError as exc:
        raise ConfigError(
            "DarvaX is enabled in config/darvax.json but the DarvaX module is "
            "not installed/present — install it or set enabled=false"
        ) from exc
    app.mount("/darvax", create_darvax_app(config_dir, repo))
```

**Enabled-but-absent must fail loudly, never silently.** The two states are
defined explicitly:

| Config | Module present? | Behaviour |
|---|---|---|
| `enabled: false` | absent | ATHENA starts and behaves normally — the guard short-circuits before any import is attempted |
| `enabled: false` | present | ATHENA starts and behaves normally — DarvaX is inert, never imported |
| `enabled: true` | present | DarvaX mounts at `/darvax/` |
| `enabled: true` | **absent** | **Startup fails with an explicit configuration error** naming the contradiction and both remedies |

A silently-ignored `enabled: true` is forbidden: it would leave the owner
believing DarvaX is running when it is not, which is a worse failure than not
starting. This preserves "delete DarvaX freely" — deletion is a complete
operation only when paired with `enabled: false`, and the system says so out
loud rather than guessing.

DarvaX serves its **own** UI under `/darvax/` — its own HTML and its own JS. It
does **not** enter `DASHBOARD_JS_PARTS`, does not modify `index.html`'s tab
structure, and does not touch `dashboard.js`/`dashboard.css`. ATHENA's dashboard
version-bump discipline is unaffected because none of its assets change. An
optional single anchor in ATHENA's nav pointing at `/darvax/` is permitted as
the only cosmetic touch, and is itself flag-guarded.

**5. Its own scheduling.**
DarvaX exposes its own CLI entry point and is driven by its own schedule.
`HostDueRunner`, `CycleWorker`, `due_triggers()`, and `config/scheduling.json`
are not modified. DarvaX never runs inside an ATHENA cycle.

**6. Its own artifacts, never ATHENA `Decision` objects.**
DarvaX emits `DarvaxSignal` records into its own tables. It never writes a row
that ATHENA's Decisions & Trace, scoring, confidence, risk, or TradePlan
machinery can read. The two lanes are visually comparable to the owner but
computationally disjoint.

**7. Kill switch semantics — precise.**
With `enabled: false` in `config/darvax.json` (the shipped default): no DarvaX
module is imported, no sub-app is mounted, no route exists, no database file is
created or opened, no scheduled work runs, and no ATHENA behaviour differs in
any observable way. This is asserted by tests, not asserted by prose.

**8. DarvaX owns its configuration entirely; ATHENA learns only "on or off".**
`config/darvax.json` is a **DarvaX-owned** file. The boundary is absolute:

- **ATHENA core** may read exactly one thing from it — whether satellite
  activation is requested — via a minimal, methodology-blind helper used solely
  at the mount seam in §4. That is the total extent of ATHENA's knowledge.
- **DarvaX** loads, validates, and owns `DarvaxConfig` in full, after the mount
  decision has already been made.

ATHENA's configuration models and loaders (`athena.config.*`) must **never**
gain awareness of DarvaX methodology parameters — stop policies, the EMA ladder,
Fibonacci parameters, box construction settings, signal thresholds, or any
future DarvaX-specific parameter. No DarvaX field may appear in an ATHENA
pydantic config model. Configuration coupling must not be introduced for
convenience: the fact that both files live under `config/` is a filesystem
convention, not a shared ownership claim.

Within that DarvaX-owned config, contested source parameters are expressed as
settings rather than settled by fiat. The 1%-vs-10% stop contradiction defaults
to Darvas' canonical **10%** (the documented, attributable source rule) with the
1% variant selectable; the EMA stop ladder (5/10/20/200) is likewise
configuration. Which performs better is a question for DX-5's evidence, not for
an author's assertion.

**9. Uncomputable criteria degrade honestly, never fabricated.**
Of the five screening criteria, only the technical ones are computable from data
ATHENA holds. "Low float" and "superb quarterly numbers" require a fundamentals
/ float data source that does not exist in this system; "less talked about" and
"bright future potential" are irreducibly subjective. These emit an explicit
UNKNOWN and are shown as unavailable — the same honest-degradation posture
`MarketSnapshot.india_vix` and ADR-006's circuit fields already establish. No
proxy is invented to fill the gap.

**10. Explainability, determinism, replayability still apply.**
Being independent does not mean being exempt. Every DarvaX signal persists its
own computed explanation as data (ADR-005's principle), uses injected clocks and
`Decimal`, and is replayable. The module is optional; the engineering standard
is not.

## Alternatives considered

- **Scoring-component integration** (add `darvax_structure` to
  `config/scoring.json`, feed evidence into the existing pipeline). This was the
  initial in-session suggestion and is **rejected**: enabling or disabling it
  would silently change ATHENA's own scores, confidence, and decisions, breaking
  the owner's core requirement and making decision history non-comparable across
  the toggle. It would also give an unvalidated method direct influence over
  live advisory output.
- **Shared database, namespaced `darvax_*` tables in `db/athena.db`.** Simpler
  to join against candles, but couples DarvaX to ATHENA's schema version,
  backup/restore, integrity report, and write lock; "delete DarvaX entirely"
  stops being a clean operation. Rejected for a separate file.
- **A generic plugin/extension registry in ATHENA core.** More "elegant" in the
  abstract, but it is speculative infrastructure for exactly one consumer, and
  ATHENA's engineering rules prefer clarity over cleverness and forbid
  speculative abstraction. A single explicit guarded mount is smaller, more
  obvious, and trivially removable. Rejected.
- **DarvaX as a separate repository/process entirely.** Maximum isolation, but
  it would duplicate Kite ingestion, the instrument catalog, and the candle
  store for no benefit, and the owner wants it usable from the same workstation
  surface. Rejected as over-isolation.
- **Embedding DarvaX as a tab inside ATHENA's dashboard.** Better UX, but it
  requires editing `index.html`, `DASHBOARD_JS_PARTS`, and the shared CSS —
  coupling DarvaX to ATHENA's asset-versioning discipline and making "disable"
  a partial rather than total operation. Rejected for Phase 1; may be revisited
  as a deliberate, separately-approved trade of isolation for convenience.

## Consequences

- DarvaX can be enabled, disabled, or deleted with no effect on ATHENA's
  decisions, schema, backups, scheduling, or dashboard assets.
- **Performance isolation is architectural, not physical — stated precisely.**
  The guarantee is that DarvaX introduces **no synchronous dependency** into
  ATHENA's request path, decision path, scoring path, scheduler/cycle path,
  persistence write path, or dashboard rendering path. Nothing ATHENA does ever
  waits on DarvaX. It is **not** claimed that an enabled DarvaX has literally
  zero performance effect: both run on the same workstation and process
  environment, and DarvaX reads ATHENA's market data, so host-level contention
  for CPU, memory, and SQLite/filesystem I/O remains possible. That contention
  is to be **measured, not assumed away** (see DX-4a in the milestone table).
  This explicitly does **not** license premature worker-process architecture,
  resource schedulers, or queues in DX-1 — measurement first, and only then a
  decision about whether any mitigation is warranted at all.
- ATHENA's decision history stays comparable across the toggle, because the
  toggle cannot influence it.
- The owner gets two independent readings of the same market — ATHENA's and
  DarvaX's — and can judge them side by side without either contaminating the
  other.
- Cost of isolation, accepted deliberately: DarvaX re-derives some indicator
  values ATHENA already computes (EMAs in particular) rather than reading
  ATHENA's persisted indicator artifacts. This duplication is the price of the
  one-way dependency rule and is preferred to coupling.
- DarvaX's UI is a separate surface at `/darvax/`, not an ATHENA tab. Slightly
  worse UX, deliberately traded for total separability.
- **No DarvaX signal may be treated as validated until it has produced its own
  expectancy, win-rate, loss-rate, drawdown, and sample-size evidence.** The
  source document supplies none; that evidence must be generated here rather
  than inheriting an unproven claim. Until then the UI labels DarvaX output as
  Experimental / Unvalidated.
- **Validation must not quietly undo the isolation DX-1…DX-4 established.**
  DarvaX may consume ATHENA's existing generic backtesting capability (M4.5)
  **only** through an already-stable, generic contract, or through a
  **DarvaX-owned adapter**. Three hard rules govern this:
  1. A `DarvaxSignal` is **never** converted into an ATHENA `Decision` merely to
     satisfy the backtest engine. That conversion would re-couple the two lanes
     through the back door and corrupt the meaning of ATHENA's own decision
     artifacts.
  2. ATHENA's backtest domain model is **never** modified to understand DarvaX
     concepts — no DarvaX-shaped field, enum value, or branch enters it.
  3. If M4.5's existing interface cannot evaluate DarvaX without modifying
     ATHENA core, then DX-5 implements a **DarvaX-owned backtest harness**
     instead. Re-implementing evaluation inside DarvaX is explicitly the
     preferred outcome over bending ATHENA core to fit.

  All validation outputs — expectancy, win rate, loss rate where applicable,
  drawdown, sample size, and any methodology-specific evidence — are DarvaX-owned
  artifacts, persisted in `darvax.db` and surfaced on `/darvax/`.
- The named DarvaX chart patterns ("Chikni Chameli", "Lal Dabangg", "Jalwa",
  "High Dry Fry") are **out of scope**: the deck defines them only by
  illustrative screenshots, with no precise criteria to implement. Coding them
  would mean inventing definitions and attributing them to the source. The
  computable structural equivalent of "High Dry Fry" (advance → correction →
  range contraction) is covered by the range-contraction measure instead.
- All F&O/options material in the deck is out of scope permanently, per the
  constitution.

## Implementation gate

No implementation begins until the owner approves this ADR. Status stays
`Proposed` until the owner changes it. On approval, delivery follows the normal
process (Design → Implement → Test → Self-Validate → Milestone Review Summary →
Owner/Chief Architect approval), split into small reviewable milestones. **Each
DX milestone stops after implementation and testing and returns a Milestone
Review Summary for approval before the next one begins** — no auto-continuation
across the DX sequence.

**DarvaX is a parallel satellite workstream.** DX milestones are never mixed
with, blocked on, or bundled into ATHENA's core roadmap (Phase 9 and beyond);
ATHENA's own milestones continue independently, and a DX milestone and an
ATHENA milestone are never in flight in the same change set.

| Milestone | Scope |
|---|---|
| **DX-1** | Module skeleton, DarvaX-owned `config/darvax.json` (default `enabled: false`), own DB file + schema, `DarvaxMarketDataPort`, the guarded mount seam including enabled-but-absent failure, and the full kill-switch/isolation test suite. **No trading logic at all.** No worker processes, queues, or resource schedulers. |
| **DX-2** | Deterministic primitives: Darvas box construction, swing points, distance-to-ATH, range contraction, volume expansion, inside bar, Fibonacci levels — pure functions, unit-tested against hand-worked fixtures. |
| **DX-3** | Signal engine: box-breakout/retest state machine, stop policies (10% canonical, 1% variant, EMA ladder), persisted per-signal explanations. |
| **DX-4** | `/darvax/` UI surface and its own API, labelled Experimental / Unvalidated. |
| **DX-4a** | **Performance evidence.** Measure ATHENA's responsiveness (validate latency, dashboard load, decision-path timings) with DarvaX disabled vs enabled-and-running, on the real workstation, and publish before/after numbers. Confirms the §Consequences guarantee empirically and quantifies any host-level contention. Mitigation, if any proves warranted, is a separate decision — not assumed here. |
| **DX-5** | Validation evidence: expectancy, win rate, loss rate, drawdown, sample size — via a stable generic M4.5 contract or a DarvaX-owned harness, under the three isolation rules in §Consequences. Only after this may the Experimental label be reconsidered. |

**Acceptance tests required for DX-1 (the isolation contract):**

1. With `enabled: false`, no `athena.darvax` module appears in the imported
   module set after `create_app()` runs.
2. With `enabled: false`, no `/darvax` route is registered and requests to it
   return 404.
3. With `enabled: false`, `db/darvax.db` is never created.
4. No module under `src/athena/` outside `darvax/` imports `athena.darvax`,
   except the single guarded seam in `app.py` (import-graph scan).
5. ATHENA's `SCHEMA_VERSION`, `ddl_statements()`, and `record_counts()` are
   byte-identical to their pre-DarvaX state.
6. The full existing ATHENA suite passes unchanged with DarvaX both enabled and
   disabled — proving enablement alone changes no ATHENA behaviour.
7. `DarvaxMarketDataPort` exposes no write method (contract inspection), and
   DarvaX holds no write handle to `db/athena.db`.
8. Deleting `src/athena/darvax/` plus `config/darvax.json` plus the guarded seam
   leaves the full ATHENA suite green.
9. **`enabled: false` + module absent** → `create_app()` succeeds and ATHENA
   behaves normally (simulated by making the DarvaX import unavailable).
10. **`enabled: true` + module absent** → `create_app()` raises an explicit
    configuration error whose message names both the contradiction and the two
    remedies. It must **not** start silently, and must **not** degrade to a
    disabled state.
11. **ATHENA's config layer stays methodology-blind**: no DarvaX methodology
    field (stop policy, EMA ladder, Fibonacci, box settings, signal thresholds)
    appears in any `athena.config` model, and ATHENA reads nothing from
    `config/darvax.json` beyond the activation flag (asserted by inspecting the
    ATHENA-side reader's parsed surface).
12. **DarvaX owns its own config validation**: a `config/darvax.json` containing
    an invalid methodology value fails inside DarvaX's own loader, not
    ATHENA's — and with `enabled: false` that same invalid file is never parsed
    at all.

**Explicitly out of scope for every milestone above:** any change to ATHENA's
scoring weights, confidence, risk, decision engine, TradePlan, universe,
scheduling, dashboard assets, or schema; any order-placement capability; any
options/F&O logic; any fabricated stand-in for float or fundamentals data.
