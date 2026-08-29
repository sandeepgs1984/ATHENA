# ID-0 — Intraday Intelligence: Runtime Audit & Architecture Freeze Report

**Date:** 2026-08-29
**Status:** Inspection only. No production code was modified to produce this
report. All findings are traced against the live working tree; every claim
below cites file, class/function, and (where useful) line number.
**Scope:** Establish ground truth for the Intraday Intelligence (ID) program
before ID-1 writes any code. Verifies runtime reality against
`ATHENA-WORKFLOW-METHODOLOGY.md` / `ATHENA-TECHNICAL-ARCHITECTURE.md`, maps
`PipelineContext`/indicators/`TradePlan`/freshness machinery, and proposes —
without implementing — the smallest architecture-compatible extension for
future intraday artifacts.

---

## 1. Executive Summary

The audit traced all six scheduled/triggered runtime flows (PREMARKET,
REFRESH, FAST, CLOSING, dashboard single-symbol Revalidate, owner-triggered
full-universe validation) end to end, plus `PipelineContext`/`ContextDelta`,
all eight indicators, Sector Health wiring, `TradePlan` construction,
freshness/revalidation machinery, market-data timestamps, and provider
execution-quality data availability.

**Three findings materially change the planning premise the ID program was
framed around:**

1. **The "may not participate in the live decision path" concern about
   `intraday_candles()` is false.** It is invoked from all six runtime
   flows, both 5m and 15m candles are genuinely fetched (5m-only under
   FAST), persisted with `timeframe` as part of the storage key, and **read
   downstream by `ScoringEngine`** — VWAP-reclaim and 5m/15m confluence
   bonuses are real, live, and already move the composite score today. What
   is genuinely true is narrower and more specific: intraday data reaches
   **scoring only** — `RegimeEngine`, `DecisionEngine` (directly), and
   `TradePlan` construction consume **zero** intraday data; `TradePlan` is
   built entirely from daily last_close and daily 14-period ATR. So the ID
   program is not bootstrapping intraday awareness from nothing — it is
   extending an existing, working, but narrow intraday-to-scoring channel
   into a proper WHETHER/WHEN qualification layer.
2. **The pipeline mechanism named in ADR-003 (`domain.context.PipelineContext`
   / `ContextDelta` / `IntelligenceModule`) is entirely dormant** — zero
   non-test callers anywhere in the codebase. The pipeline that actually
   runs every cycle is a different, functionally similar but distinctly
   implemented mechanism: `runtime.workflow.WorkflowContext` /
   `WorkflowStage` / `WorkflowEngine`, driving a Kahn-topological six-stage
   graph (`indicators → regime → scoring → risk → confidence → decision`)
   wired entirely inside `OwnerValidationPipeline._scan_eligible`. This is
   the single most consequential finding for the ID program's architecture
   proposal (§4, §12) — any new intraday stage must be designed against the
   *real* live mechanism, not the documented-but-unused one, and the
   ambiguity itself needs an explicit owner decision before ID-1 builds on
   top of it.
3. **Sector Health has one small, already-anticipated wiring gap, not a
   missing feature.** `SectorHealthEngine` runs live every cycle;
   `ScoringEngine._sector_quality()`, `EvidenceAggregationEngine.aggregate()`,
   and `DecisionEngine.decide()` all already accept a `sector_health`
   parameter and handle it correctly — three specific call sites in
   `owner_validation.py` simply never pass it. A code comment at
   `owner_validation.py:266-273` confirms this is a deliberate, already-named
   deferred milestone (SD-3), not an oversight.

Every other documented claim in the ID-0 prompt and in
`ATHENA-WORKFLOW-METHODOLOGY.md` / `ATHENA-TECHNICAL-ARCHITECTURE.md` was
verified **true** against code, with one dated exception: the FAST cadence
is documented in two places with two different values. See §11.

Indicators are genuinely timeframe-agnostic at the math layer — none assume
daily bars, VWAP is correctly session-reset by date comparison, and ATR
could compute an "intraday ATR" today with zero code change. The one real
structural gap is that `IndicatorResult` carries no timeframe/session
provenance, forcing every caller to track it externally by convention
rather than by contract (§5).

`TradePlan` is a frozen, `slots=True` dataclass constructed at exactly two
call sites with manual (non-generic) JSON serialization — this makes it
unusually safe to extend additively; 7 of 9 candidate future fields are
simple additive changes, one (`entry_zone`) requires no schema change at
all (the two-value `entry_low`/`entry_high` structure already exists), and
one (persisted "setup freshness") should explicitly **not** be added, since
the codebase already deliberately keeps freshness derived-at-read rather
than stored, to avoid a hidden-clock-read violation of ADR-005 (§7).

**Recommendation: GO WITH CONDITIONS.** See §18 for the full reasoning and
the specific conditions.

---

## 2. Verified Current Runtime Flow

There are two live entrypoints into the scheduled-cycle machinery, both
converging on the same runner:

- `athena run-due` CLI → `_cmd_run_due` (`src/athena/cli.py:644`) →
  `_execute_run_due` (`cli.py:582`), wrapped in `CycleRunnerLock.acquire()`/
  `release()` (`cli.py:649-664`).
- `athena serve --with-cycles` → `CycleWorker` (`src/athena/ops/serve_runtime.py:171-231`),
  ticking every `cycle_interval` seconds (default 60), itself acquiring
  `CycleRunnerLock` per tick (`serve_runtime.py:219-231`).

Cadence gating: pure functions in `src/athena/scheduling/cadence.py` —
`is_premarket_due` (22-44), `is_refresh_due` (47-72), `is_fast_due` (75-100),
`is_closing_due` (103-127), combined by `due_triggers` (130-186, evaluation
order PREMARKET → REFRESH → CLOSING → FAST).

`HostDueRunner.run` (`src/athena/ops/scheduled_run.py:114-222`) dispatches
each due trigger:

- **PREMARKET / REFRESH / CLOSING** → `DryRunCycleOrchestrator.run_cycle(trigger, as_of=as_of)`
  (`scheduled_run.py:192`), backed by a shared `LiveIngestionEngine` +
  `OwnerValidationPipeline(repo, config_dir)` with **no `symbols_filter`**
  (`cli.py:241-244`, wired at `cli.py:634`) — i.e. the full active
  owner-candidate universe every time.
- **FAST** → special-cased (`scheduled_run.py:171-191`): calls
  `run_fast_revalidation_cycle` (`src/athena/ops/fast_revalidation.py:55-103`),
  which builds its **own**, narrower `LiveIngestionEngine` +
  `OwnerValidationPipeline(symbols_filter=bare_symbols)` pair, scoped to
  `current_decision_list_instrument_ids(repo, max_symbols=150)`
  (`fast_revalidation.py:40-52`) — every instrument with a persisted
  decision, newest-decided first, capped at 150 — **not** the full
  candidate universe.
- **Dashboard single-symbol Revalidate** → `POST /api/v1/market/validate`
  (`src/athena/api/v1/routers/market.py:288-301`) →
  `CandidatesService.validate_candidates` (`candidates_service.py:173-201`) →
  `validate_symbols` (`src/athena/ops/symbol_validate.py:153-271`), run
  **synchronously in the request thread**, using `RunTrigger.REFRESH` (there
  is no distinct REVALIDATE trigger), scoped to the requested symbol(s) +
  up to 2 stale index/VIX instruments. **This path never acquires
  `CycleRunnerLock`** — confirmed by grep, and confirmed intentional per
  ADR-007 §5's "frozen scoped-validate contract" (capped at 20 symbols).
- **Owner-triggered full-universe validation** → `POST /api/v1/market/validate-all`
  (`market.py:302-318`, 202 Accepted) → `start_full_validation`
  (`src/athena/ops/full_validation.py:65-141`), which non-blockingly probes
  `CycleRunnerLock` first (refuses with `CycleBusyError`/409 if `run-due`/
  `CycleWorker` already holds it), then spawns a daemon thread that
  re-acquires the lock for the duration — the exact ADR-007-designed reuse
  of the lock, confirmed by code, not just by the ADR text.

**Universe resolution:** PREMARKET/REFRESH/CLOSING/Revalidate/full-validation
all resolve from `SqliteCandidateStore(repo).list_candidates(active_only=True)`
(owner-curated candidates, resolved against the live Kite catalog); FAST
resolves from the persisted **decision list** instead (already-scanned,
already-decided instruments only).

**MarketDataProvider calls, every trigger, via `LiveIngestionEngine.run_cycle`**
(`src/athena/data/ingestion/engine.py:69-253`): `instruments()` (73),
`daily_candles()` (112, gated on `include_daily`), `intraday_candles()`
(132, once per configured timeframe per instrument), `quotes()` (153),
`market_snapshot()` (216, capability-gated).

**Pipeline stages actually executed** (identical shape across all six
flows, per-instrument, built inside `OwnerValidationPipeline._scan_eligible`
→ `WorkflowEngine`): the declared `WorkflowStage` graph
(`owner_validation.py:985-1018`) is
`indicators (no deps)`, `regime (no deps)`,
`scoring (deps: indicators, regime)`,
`confidence (deps: scoring, regime)`,
`risk (deps: indicators, regime)`,
`decision (deps: scoring, confidence, risk)`. Running the actual Kahn
topological sort (`runtime/workflow.py:104-118`, ties broken by declaration
order) against these declarations gives the real execution order:

```
indicators → regime → scoring → risk → confidence → decision
```

Note `risk` executes **before** `confidence`, despite being declared third —
its dependencies (`indicators`, `regime`) are satisfied one round earlier
than `confidence`'s (`scoring`, `regime`). This is not documented anywhere
as the real order and would be easy to get wrong from declaration order
alone.

**Decision and TradePlan creation:** `DecisionEngine.decide()`
(`src/athena/decision/engine.py:66-163`) runs for every eligible instrument
in every flow, persisted immediately via `repo.save_decision()`
(`owner_validation.py:969`). `TradePlan` is built inside `decide()` when the
outcome resolves to TRADE, entirely from daily data (§6, §7).

---

## 3. Intraday Data Reality

Answering the ID-0 prompt's 14 numbered questions directly:

| # | Question | Finding |
|---|---|---|
| 1 | Is `intraday_candles()` actually invoked live? | **YES — CONFIRMED_LIVE.** Real protocol method (`domain/interfaces.py:86-88`), real Kite implementation (`kite_provider.py:173-193`, hits the real Kite historical endpoint), single live call site `data/ingestion/engine.py:132` inside `LiveIngestionEngine.run_cycle`. |
| 2 | From which of the 6 flows? | **All six.** Every flow ultimately constructs a `LiveIngestionEngine` and calls `.run_cycle()`. |
| 3 | Which timeframes requested? | PREMARKET/REFRESH/CLOSING/Revalidate/full-validation: **both `5m` and `15m`** (`config/ingestion.json:6`). FAST: **`5m` only** (`config/scheduling.json:23`). |
| 4 | Both 5m and 15m fetched anywhere? | Yes — five of six flows fetch both. Only FAST is 5m-restricted. |
| 5 | Does FAST really request 5m data? | Yes, traced precisely: `fast.timeframes` from config → `fast_revalidation.py:83-88` → `ingest_cfg.model_copy(update={"timeframes": ["5m"], "include_daily": False, ...})` → `engine.py:127-132` → `provider.intraday_candles(iid, Timeframe.M5, ...)`. |
| 6 | Where are intraday candles persisted? | The single unified `candles` table (`data/store/repository.py`), same table as daily candles — `add_candles` (302-323), `get_candles`/`list_candles_recent` (372-381, 1332-1347). |
| 7 | Is timeframe part of the persistence key? | **YES.** `UNIQUE(instrument_id, timeframe, ts_open)` is the upsert conflict target (`repository.py:318`); every read helper takes `timeframe` as a mandatory filter argument. |
| 8 | Are intraday candles read by any downstream engine? | Narrowly, yes — `OwnerValidationPipeline._scan_eligible`'s `ind_stage` (`owner_validation.py:822-884`) fetches M5 (→ VWAP) and M15 (→ confluence) directly via `repo.list_candles_recent`, feeding `ScoringEngine.score(vwap=..., confluence=...)`. `regime`, `market_health`, `sector_health`, `risk`, `confidence`, `decision` (direct), and `evidence` never receive intraday candles. |
| 9 | Does `ScoringEngine` consume intraday data? | **YES — CONFIRMED_LIVE.** `_trend` adds a confluence bonus (up to `cfg.confluence.max_bonus`) from real 5m/15m agreement (`scoring/engine.py:167-186`); `_technical_structure` adds a VWAP-reclaim bonus ramped by real deviation (`scoring/engine.py:315-330`). Both genuinely move the composite. |
| 10 | Does `RegimeEngine` consume intraday data? | **NO.** `RegimeEngine.assess(index_symbol, index_candles, snapshot, *, as_of)` takes one candle sequence, always resolved to **daily** index history (`owner_validation.py:561-614`, `Timeframe.D1`). No intraday parameter exists on the signature at all. |
| 11 | Does `DecisionEngine` consume intraday data? | Only indirectly, through `scoring.composite.value` (which already baked in Q9's bonuses upstream). `decide()`'s own signature has no `vwap`/`confluence` parameter. |
| 12 | Does `TradePlan` consume intraday data, or daily/last_close? | **Daily/last_close only — matches documentation exactly.** `_build_plan` (`decision/engine.py:232-266`): `entry_low = entry_high = last_close` (from the daily SMA indicator's own recorded input); `stop = last_close ∓ ATR(14, daily) × 1.5`; `target = last_close ± ATR × 3.0`; `valid_until = as_of + 6h`. All multiples/window config-driven (`config/decision.json`). Zero intraday input reaches `_build_plan`. |
| 13 | Is VWAP from real intraday bars or approximated? | **Real bars.** `calc.vwap` (`indicators/calculations.py:196-225`) is a genuine session-cumulative Σ(typical×volume)/Σvolume, filtered to `c.ts_open.date() == as_of.date()` — real, correct session reset, fed by real persisted 5m candles from that day's ingest. |
| 14 | Does multi-timeframe confluence receive real inputs? | **Yes, real — CONFIRMED_LIVE** in the five flows that fetch both timeframes. `owner_validation.py:854-879` computes daily/5m/15m directional agreement from three genuinely separate candle series. **Caveat:** on a FAST-only tick, the 15m leg reads whatever the last REFRESH cycle persisted — real data, but up to one REFRESH interval (15 min) stale, not freshly fetched that tick. |

**Bottom line:** the "intraday data may not participate" concern that
motivated deeper verification is not supported by the code. What's true is
narrower: intraday participation stops at `ScoringEngine`. `RegimeEngine`,
`DecisionEngine`'s direct inputs, and `TradePlan` construction are 100%
daily. This is precisely the seam the ID program needs to extend, not
route around.

---

## 4. PipelineContext / ContextDelta Reality

**Three unrelated things share variants of the name "PipelineContext" in
this codebase:**

| | Symbol | Location | Status |
|---|---|---|---|
| A | `PipelineContext` / `ContextDelta` / `IntelligenceModule` Protocol | `src/athena/domain/context.py:14-69`, `domain/interfaces.py:114-127` | **DORMANT.** Grep for `IntelligenceModule` across `src/athena` returns only `domain/interfaces.py` and its re-export. No engine implements the protocol. Only exercised by isolated unit tests of the dataclass itself (`tests/unit/test_domain.py`), never wired to a real engine. |
| B | `orchestration.models.PipelineContext` (+ `StageResult`/`PipelineDefinition`/`SystemPipelineResult` etc., `orchestration/models.py:39-248`) | 14 stage files under `orchestration/stages/` | **Live only as a read-side reconstruction.** `src/athena/cli.py` — the only entrypoint driving real daily cycles — never imports `orchestration`. It's used exactly once, in `sqlite_providers.py:437-449`, to repackage an already-persisted `RunRecord` into a DTO shape for the dashboard's "pipeline runs" view. It executes nothing. |
| C | `runtime.workflow.WorkflowContext` / `WorkflowStage` / `WorkflowEngine` | `src/athena/runtime/workflow.py:31-191` | **CONFIRMED_LIVE — this is the real per-cycle context.** A `dict`-based accumulator (not a fixed-field dataclass), with `WorkflowDefinition._topological_order` (104-118) doing a deterministic Kahn sort. The only concrete production wiring anywhere in the repo (non-test) is `owner_validation.py:982-1019`. |

**Fields on (C), the live mechanism** — not fixed fields but declared stage
outputs, per `owner_validation.py:985-1018`:
`indicators`, `vwap`, `confluence` (from `indicators` stage);
`regime`, `market_health` (from `regime` stage — though `market_health` is
usually a cache-hit from the run-level shared value, see below);
`scoring` (from `scoring`); `evidence_bundle`, `confidence` (from
`confidence` — evidence aggregation is folded into this stage's body, not a
separate declared stage); `risk` (from `risk`); `outcome` (from `decision`).

**Persistence:** the schema (`data/store/schema.py`) has **no dedicated
tables** for indicators, regime, market_health, sector_health, scoring,
confidence, risk, or evidence-bundle snapshots. Only `decisions`
(`schema.py:214-229`, with `score_ref`/`confidence_ref`/`risk_ref` as plain
strings — **not** foreign keys, since no such tables exist),
`decision_traces` (242-246, summary strings only), and `runs.detail_json`
(181-196, a free-form JSON blob, mostly run-level not per-instrument) — all
intermediate analytical artifacts are transient, in-memory-only for the run.

**Does explanation/provenance survive aggregation?** Within one run
(in-memory), yes — whole result objects pass through `WorkflowContext`
untransformed, and `EvidenceItem.payload` explicitly preserves "the
original (frozen) intelligence object" (`evidence/models.py:30-42`). Into
persistence, only headline explanations survive: `DecisionEngine._trace`
(`decision/engine.py:270-301`) captures only each stage's top-level
`.explanation` string — per-indicator formula/inputs and per-evidence-item
text are never individually persisted. ADR-005's "mandatory non-empty
explanation" invariant **is** genuinely enforced, consistently, via
`__post_init__` checks in every producing model (`IndicatorEvidence`,
`GateResult`, `TraceStage`, `Decision`, `EvidenceItem` — all cited with line
numbers in the underlying agent report). So: the per-object invariant is
real; the depth of what survives to disk is shallower than "provenance
survives aggregation" would suggest.

**How unknown/missing inputs are represented — the real, consistent
pattern:** never `None`, never a silent default. Every analytical dimension
in every engine (indicators, regime, market health, sector health, scoring,
confidence, risk) has its own named `*_UNKNOWN` enum label, paired with a
constructor invariant forbidding a numeric value on an UNKNOWN result. This
is a genuinely load-bearing, repo-wide convention — any new intraday
artifact should follow it exactly, not invent a new missing-data
representation.

**Stage 2.5 placement question — evidence, not a decision:**

- `regime` has **zero** dependency on `indicators` today — they're declared
  as independent producers that happen to run consecutively only because of
  Kahn tie-breaking by declaration order, not because either needs the
  other's output. A step wedged strictly "between Indicators and Regime"
  would occupy a dependency slot that doesn't structurally exist.
- `scoring` is the first stage that genuinely needs both `indicators` and
  `regime` together, and it's also the stage that already consumes
  intraday-derived `vwap`/`confluence` today.
- The evidence points toward a new "Session/Intraday Intelligence"
  producer occupying **the same dependency slot `indicators` currently
  occupies relative to `scoring`** — i.e., a sibling producer that
  `scoring` (and possibly `risk`/`confidence`) depend on — rather than
  insertion between `indicators` and `regime`.
- Nothing observed suggests the new stage needs `scoring`/`confidence`/
  `risk`/`decision` outputs (all later, valuation-facing, not raw
  market-structure inputs), so there's no dependency evidence for placing
  it downstream of `decision` either — unless its purpose is genuinely
  post-decision monitoring of an already-open plan, which is a different
  concern (see §12, `PlanValidity`) and would sit nearer the (currently
  dormant) `monitoring`/`timeline` orchestration stages, not the live scan
  path.
- **Practical constraint:** daily candles are pre-loaded at the run level
  for the whole scanned universe; intraday (M5/M15) candles are fetched
  only **inside `ind_stage`, per-instrument, on demand**
  (`owner_validation.py:847-849, 870-872`). A dedicated intraday stage
  needs either the same on-demand pattern or a run-level bulk-prefetch
  extension — a real design decision for ID-1, not a blocker.

---

## 5. Indicator Reusability

All eight indicators (`indicators/calculations.py`) are genuinely
timeframe-agnostic at the math layer — none hardcode daily assumptions,
calendar-day iteration, or one-bar-per-day logic. `IndicatorEngine.compute`/
`compute_all` (`indicators/engine.py:53-65`) takes a generic
`Sequence[Candle]`, sorts by `ts_open`, and dispatches purely by indicator
name and config-supplied period — there is no daily-specific branch
anywhere.

| Indicator | Timeframe-agnostic | Callable on 5m/15m today | Live status |
|---|---|---|---|
| SMA | Yes (`calculations.py:29-47`, count-windowed) | Yes | **CONFIRMED_LIVE intraday** — already called directly (bypassing `IndicatorEngine`) for confluence, `owner_validation.py:875-878` |
| EMA | Yes (63-78) | Yes, mechanically | DORMANT for intraday — no call site passes it intraday candles anywhere |
| RSI | Yes (81-97, Wilder, count-windowed) | Yes | CONFIRMED_LIVE daily-only; intraday path mechanically ready, unused |
| ATR | Yes (108-125, pairwise high/low/close, no day assumption) | Yes | DORMANT for intraday, **zero code change needed** — only a caller passing an intraday series, exactly the pattern already used for VWAP |
| MACD | Yes (128-143, built on `ema_series`) | Yes | CONFIRMED_LIVE daily-only; intraday DORMANT |
| ADX | Yes (156-186, Wilder DM/DI/DX) | Yes | CONFIRMED_LIVE daily-only; intraday DORMANT |
| Volume MA | Yes (189-193, trailing mean) | Yes | CONFIRMED_LIVE daily-only; intraday DORMANT |
| VWAP | Yes, and **explicitly session-aware** | Yes — already running on 5m bars in production | **CONFIRMED_LIVE intraday** |

**VWAP session reset — exact mechanism:** `calc.vwap`
(`calculations.py:196-225`) filters to
`session_bars = [c for c in candles if c.ts_open.date() == as_of.date()]`
(line 211) — resets purely by calendar-date comparison per bar, correct for
NSE's single-session-per-day structure.

**One real gap:** `IndicatorResult` (`indicators/models.py:52-72`) carries
`name, status, parameters, window_used, values, evidence, ts` — **no
`timeframe` field, no session-date field**, even though `Candle` itself
carries `timeframe` per bar. `IndicatorEngine.compute` strips this
information rather than propagating it. The live code compensates by
convention — `ind_stage` keeps `indicators`, `vwap_result`, and
`confluence_inputs` as three separately-named locals rather than one merged
structure specifically because nothing else tracks which timeframe each
result came from. **This is the one indicator-layer change worth making
early** (§15) — any future multi-timeframe stage needs its results to be
self-describing, not tracked externally by naming convention.

**One real config constraint:** `IndicatorsConfig`
(`config/models.py:180-189`) fixes exactly one period per indicator name
globally — there is no per-timeframe parameter set. This is *why* the
existing confluence calculation bypasses `IndicatorEngine` entirely and
calls `calc.sma()` directly (explicit comment, `owner_validation.py:858-862`).
Any future multi-timeframe indicator stage (e.g. a 5m RSI at a different
period than the daily RSI) will hit this same limitation and need either
the same bypass pattern or a config-schema extension — flagged as an open
design question in §17, not resolved here.

---

## 6. Sector Health Wiring Gap

1. **Computed live, every cycle.** `SectorHealthEngine.assess_many()`
   (`sector_health/engine.py:84`), invoked unconditionally at
   `owner_validation.py:278` inside `OwnerValidationPipeline.run()`.
   Persisted only into `runs.detail_json` via `_sector_health_payload()`
   (`owner_validation.py:381, 480`) — informational, not fed into scoring.
2. **Never enters the live per-instrument context.** `sector_results`
   (computed at line 278) is a local variable of `run()` that is never
   passed into `_scan_eligible()` — neither the call site
   (`owner_validation.py:311-323`) nor `_scan_eligible`'s own signature
   (741-755) thread it through.
3. **`EvidenceAggregationEngine.aggregate()` already accepts
   `sector_health=`** (`evidence/engine.py:30-41`, flattens into
   `EvidenceItem`s tagged `EvidenceSource.SECTOR_HEALTH`) — but the live
   call (`owner_validation.py:924-930`) never passes it.
4. **`ScoringEngine._sector_quality()` exists exactly as named**
   (`scoring/engine.py:244-248`), is called unconditionally with the
   composite already weighting it at 15% (`config/scoring.json`), and is
   fully correct when given real data — but the live caller
   (`owner_validation.py:910-922`) never supplies `sector_health`, so the
   `sector_health is None` branch ("no sector health assessment available")
   fires on every single cycle.
5. **Exact call sites missing the argument:** `sco_stage` (910-922),
   `conf_stage` (924-940), `dec_stage` (955-980) — all three inside
   `_scan_eligible`'s `builder()` closure.
6. **`DecisionEngine.decide()` already has a `sector_health=None` parameter**
   (`decision/engine.py:80`) — but it only feeds `_trace()`'s explanation
   text (279-281), not the decision itself. The actual quantitative
   influence runs entirely through `scoring.composite.value`, which is
   where item 4's wiring matters.
7. **What specifically blocks it:** pure wiring, not missing data or config.
   `SectorHealthEngine` runs and succeeds every cycle; the gap is that its
   result is never passed down three call sites. A secondary gap: even if
   passed, `builder(instrument_id)` currently has no per-instrument
   `Instrument.sector` lookup in scope to resolve *which* sector's result
   applies — the `instruments` list built in `run()` (128-153) is also
   never passed into `_scan_eligible`. A code comment at
   `owner_validation.py:266-273` explicitly documents this as a deliberate,
   already-named, still-pending milestone ("SD-3"), not a bug.
8. **ADR-011's `symbol_group`/`resolve_universe()` is not a substitute —
   don't misapply it.** `GroupKind` (`symbols/groups.py:33-46`) has exactly
   five kinds — `INDEX`, `SEGMENT`, `BOARD`, `CURATED`, `DERIVED` — **there
   is no `SECTOR` kind**, and the whole module is about universe/scan
   eligibility, not sector taxonomy. The constituent-to-sector mapping
   already exists directly on `Instrument.sector: str | None`
   (`domain/market.py:24`). `config/sector_index_mapping.json` does a third,
   unrelated job — mapping sector *labels* to tracked benchmark *indices*
   for `SectorHealthEngine`'s own candle lookup, not stock-to-sector
   membership. All three (ADR-011 groups, `Instrument.sector`,
   `sector_index_mapping.json`) solve different problems; none should be
   collapsed into another.

**Smallest possible wiring change (documented for completeness — this is
explicitly out of ID-0's scope to implement):** pass the already-computed
`sector_results` (and the already-built `instruments` list, for `.sector`
lookup) into `_scan_eligible`; resolve each instrument's sector once inside
`builder(instrument_id)`; pass the resolved `SectorHealthResult` as
`sector_health=` into the three existing calls. No new engine, no new
config key, no schema change — every consuming parameter already exists and
already does the right thing with real input.

---

## 7. TradePlan Constraints

`TradePlan` (`domain/decision.py:14-36`) — `@dataclass(frozen=True, slots=True)`.
Fields: `entry_low`, `entry_high`, `stop_loss`, `targets: tuple[Decimal, ...]`,
`position_size: int`, `risk_amount`, `risk_reward`, `valid_from`,
`valid_until`.

**Verified construction** (`decision/engine.py:232-266`, all daily-derived,
per §3 Q12):

| Field | Behavior | Source |
|---|---|---|
| `entry_low`/`entry_high` | Both = `last_close` (zero-width today) | `sma.evidence.inputs["last_close"]` |
| `stop_loss` | `last_close ∓ ATR(14, daily) × 1.5` | ATR from daily `IndicatorEngine`, multiple from `config/decision.json` |
| `targets` | Single element: `last_close ± ATR × 3.0` | same |
| `direction` | Not on `TradePlan` itself — derived earlier in `decide()` from regime's trend label | `decision/engine.py:225-230` |
| `risk_reward` | Computed once at construction, stored (not derived on read) | `target_dist / stop_dist` |
| `position_size` | `config.default_units = 1` — **explicitly a provisional unit, not capital-based sizing.** Real capital sizing is a fully separate module (`sizing/engine.py`'s `PositionSizingEngine`), producing unrelated `PositionSize`/`PositionSizingPlan` objects | docstring `decision/engine.py:10-11` |
| `valid_from`/`valid_until` | `as_of` / `as_of + 6h`, config-driven (`validity_hours: 6`) | `config/decision.json:18` |

**SMA requirement:** confirmed — `_build_plan` returns `None` (no
`TradePlan`, hence no TRADE decision possible) if SMA or ATR is
missing/not-OK/`≤0`.

**FRESH/AGING/STALE/EXPIRED:** **not a field on `TradePlan` at all.**
Computed at read time, in two independently-maintained but currently
consistent places — `DecisionsService.get_trade_plan_freshness()`
(`decisions_service.py:803-846`) and `_plan_freshness()`
(`opportunities_service.py:262-284`) — both pure arithmetic over the
persisted `valid_from`/`valid_until` and an `as_of` instant, both
explicitly documented in their own docstrings as intentional: never a
recomputed plan, never a hidden clock read inside an analytical engine
(consistent with ADR-005). Thresholds config-driven
(`freshness_warn_fraction: 0.5`, `freshness_stale_fraction: 0.8`).

**Extensibility.** Exactly two construction call sites (`decision/engine.py:262`,
`data/store/serialization.py:266`), both keyword-based; serialization is
manual field-by-field JSON, not generic `dataclasses.asdict()`. A new field
with a default is mechanically safe everywhere, and historical rows replay
cleanly by defaulting the field on read.

| Candidate | Verdict | Reasoning |
|---|---|---|
| `setup_type` | Safe additive | Pure descriptive metadata, touches no invariant |
| `entry_zone` | **No schema change needed** | `entry_low`/`entry_high` already exist as two separate fields, currently populated as a zero-width zone — widening it is a change to `_build_plan`'s computation, not the domain object |
| `invalidation_level` | Safe additive | Independent of `stop_loss`'s TRADE-gating role |
| Target ladder | Safe **only if additive** (parallel weights field); **not safe** if it repurposes `targets`'s existing meaning — three live readers (`decision/engine.py:299`, `serialization.py:253`, `TradePlanDTO.targets`) already treat entries as plain `Decimal` |
| Trailing-stop metadata | Safe additive | Doesn't alter `stop_loss`'s existing meaning |
| Time-stop | Safe additive, but **name it distinctly** — `valid_until` already carries a different meaning ("this analysis is stale"), not "close the position after N hours" |
| Execution assumptions (slippage/fill) | Safe additive | Pure explanatory metadata |
| Data freshness metadata | Safe additive, but likely **redundant** with `valid_from` (already = `as_of`) unless it's meant to capture something `valid_from` doesn't (e.g. the underlying candle's own timestamp) |
| Setup freshness (persisted FRESH/AGING/STALE/EXPIRED) | Mechanically safe, but **architecturally contrary to existing, deliberate design** — recommend NOT adding; the current derived-at-read approach exists specifically to avoid the ADR-005 hidden-clock-read violation this would reintroduce |

---

## 8. Freshness / Revalidation Machinery

**Plan freshness API** — `GET /api/v1/decisions/{decision_id}/plan-freshness`
(`api/v1/routers/decisions.py:246-269`) → `TradePlanFreshnessDTO`
(`dtos/decisions.py:467-485`). Pure decay-clock arithmetic (§7) — never
re-runs the pipeline, never re-fetches a quote. (A separate, unrelated
concept — `AdvisoryFreshnessDTO`/`AdvisoryFreshnessService`, `CURRENT/AGING/
STALE/UNAVAILABLE` — covers market-snapshot freshness, likewise pure clock
arithmetic.)

**Dashboard freshness display:** list views use a client-side JS mirror of
the identical formula (`api/static/js/05-utils.js:81-141`, explicitly
commented as a "presentation-only mirror" to avoid extra API calls); the
single "selected brief" detail panel calls the authoritative server
endpoint (`api/static/js/14-decision-brief-analysis.js:157-181`).

**Scheduled FAST validation:** re-validates only the persisted decision
list (§2), always under `CycleRunnerLock` (via `run-due`'s explicit
acquire or `CycleWorker`'s per-tick acquire) — **no bypass**.

**Synchronous dashboard Revalidate:** confirmed **bypass** of
`CycleRunnerLock` — by design, per ADR-007 §5's frozen scoped-validate
contract, capped at 20 symbols. Nothing prevents two concurrent Revalidate
requests, or a Revalidate racing a `CycleWorker` tick, from writing to the
same SQLite DB / hitting the Kite provider concurrently — an accepted,
documented risk, not an oversight, but one worth re-examining if
event-driven revalidation (below) increases call frequency (§17).

**Owner-triggered full-universe validation:** properly ADR-007-compliant —
non-blocking probe + daemon-thread re-acquire of `CycleRunnerLock`,
confirmed in code exactly as the ADR describes.

**Event-driven invalidation feasibility** — the structural fact governing
all nine trigger types: every entrypoint above is a **pull** function,
invoked either by a fixed timer or an explicit HTTP click. Nothing in the
ingestion/candle/quote path observes incoming data and reacts —
`LiveIngestionEngine.run_cycle` and `DryRunCycleOrchestrator.run_cycle` are
both single bulk-loop methods with no callback/observer/hook parameter.

| Trigger | Verdict |
|---|---|
| PRICE_MOVE | Structurally absent; a detector *could* call `validate_symbols(symbols=[sym])` (single-symbol-scoped, already exists) once built, but nothing today watches for the condition |
| VOLUME_SHOCK | Same — raw `Quote.volume`/`Candle.volume` already persisted, but no detector exists |
| VWAP_LOSS | Structurally absent — VWAP isn't computed inline during ingestion, only inside the scan's `ind_stage` |
| ORB_FAILURE | Structurally absent — no opening-range state machine anywhere |
| TREND_REVERSAL | Structurally absent — regime/indicator engines run only inside a full cycle |
| DATA_STALE | Computed on read (`AdvisoryFreshnessService`, candle `freshness_status`) but never converted into an automatic revalidate call |
| MARKET_HEALTH_CHANGE | Structurally absent as a push — health is a cycle output, not a between-cycle watcher |
| SECTOR_REVERSAL | Same as MARKET_HEALTH_CHANGE |
| TIME_EXPIRY | **The one trigger with an existing read-time signal ready to act on** — `TradePlanFreshnessDTO.status == "EXPIRED"` is already computed on every poll; nothing currently *acts* on it, but wiring an action would be the smallest lift of the nine |

**Bottom line:** the revalidation *entrypoints* themselves
(`validate_symbols`, `run_fast_revalidation_cycle`, `start_full_validation`)
are reusable as-is by a future detector — no new job queue or locking model
needed, per ADR-007. What's missing for eight of the nine triggers is the
**detector**, which is new code but not new execution architecture.

---

## 9. Market Data Freshness Capability

Schema check (`data/store/schema.py`) against the five requested distinct
timestamps:

| Timestamp | Exists as a distinct column? |
|---|---|
| Exchange/event timestamp | Collapsed into candle/quote's own `ts`/`ts_open` — not separate |
| Candle timestamp | **Yes** — `candles.ts_open`, sourced from Kite's own historical payload |
| Provider response timestamp | **Absent** — no field distinguishes "when Kite's HTTP response arrived" |
| ATHENA received timestamp | **Absent** — `Quote.ts` is the exchange's own timestamp, not a local receive-clock read |
| Persistence timestamp | **Absent** — no `inserted_at`/`created_at` column on `candles`, `quotes`, or `market_snapshots` |

Only **2 of 5** requested instants exist (exchange-sourced candle/quote
timestamp; coarse per-run `runs.started_ts`/`finished_ts`, not per-record).

**What can be measured today without inventing anything:**
- **Quote freshness — yes.** `AdvisoryFreshnessService.get_freshness()`:
  `age_seconds = local_now − latest_snapshot.ts`. Real, already shipped.
- **Intraday candle freshness — yes.** `MarketHistoryService`:
  `age_minutes = (now − latest_ts.ts_open) // 60`, compared against a
  configured threshold.
- **Provider-to-ATHENA latency — no.** No stored instant distinguishes
  "when Kite produced/sent this data" from "when ATHENA received or wrote
  it." Comparing a cycle-level `runs.started_ts` against a candle's
  `ts_open` would conflate scheduling cadence with actual network latency
  and would not be a defensible measurement. **The specific missing piece
  is an ATHENA-local receive-time (or persistence-time) column** — nothing
  currently captures `datetime.now()` at parse or write time.

---

## 10. Execution-Quality Data Availability

`MarketDataProvider` Protocol (`domain/interfaces.py:52-84`):
`capabilities()`, `instruments()`, `daily_candles()`, `intraday_candles()`,
`quotes()`, `market_snapshot()`, `health()`. `Quote`
(`domain/market.py:105-117`): `instrument_id, ts, last_price, volume, source`
— no bid/ask/depth/turnover/circuit fields at all.

| Field | In Protocol? | Populated from real Kite data? |
|---|---|---|
| LTP | Yes (`Quote.last_price`) | **CONFIRMED_LIVE** |
| Bid | **No** | N/A |
| Ask | **No** | N/A |
| Market depth | **No** | N/A |
| Volume | Yes | **CONFIRMED_LIVE** |
| Turnover | **No** | N/A |
| OHLC | Only via `Candle` (historical bars); `Quote` itself only harvests `ohlc.close` for a prior-close comparison, discarding the rest of the payload it's given | **PARTIALLY_WIRED** |
| Upper circuit limit | **No** | N/A |
| Lower circuit limit | **No** | N/A |

**This is a contract limitation, not an under-populated implementation.**
The frozen `MarketDataProvider` Protocol was never designed to carry
bid/ask/depth/turnover/circuit-limit data — adding them is a genuine
ADR-002-governed Protocol extension, not a KiteProvider bug fix.

**ADR-002 compliance:** confirmed clean at the business-logic layer — zero
matches for `kite|Kite` across `decision`, `scoring`, `risk`, `evidence`,
`indicators`, `confidence`. One presentation-layer exception worth flagging
(not a business-logic violation as literally scoped): `api/v1/services/
market_history_service.py:35` imports `fetch_live_quote`/`fetch_live_quotes`
directly from `data/providers/kite_ltp.py`, bypassing the
`MarketDataProvider` Protocol, for a dashboard price poll.

---

## 11. Documentation vs Runtime Contradictions

**FAST cadence interval/capacity — stale in one doc, correct in another.**
`ATHENA-WORKFLOW-METHODOLOGY.md:525,533,662` states FAST runs "every 5 min"
with `max_symbols: 400`. The live config
(`config/scheduling.json:20-25`) is `interval_minutes: 10, max_symbols: 150`,
with its own `_meta` field recording why: *"Fast tier scaled back
2026-08-10: 5min/400 symbols left the shared Kite historical endpoint at
~42% duty cycle... starving ad-hoc single-symbol validates."*
`ATHENA-TECHNICAL-ARCHITECTURE.md:918-923` already correctly documents the
current value and the incident history. **The ID-0 prompt's own framing
("FAST cadence runs every 5 minutes") reflects the stale document, not the
current runtime** — this should be corrected in any future planning that
cites cadence numbers.

**The "`intraday_candles()` may not participate in the live decision path"
premise — false as a blanket claim, true in a narrower sense.** See §1/§3:
it participates in scoring, not in regime/decision-direct/tradeplan. Worth
correcting the framing for the rest of the ID program so effort isn't spent
re-solving an already-solved problem (intraday ingestion → scoring) instead
of the real gap (scoring → decision/tradeplan/qualification).

**ADR-003's documented contract vs. runtime reality — not a doc typo, a
live architectural fork.** ADR-003 describes every pipeline module
implementing `IntelligenceModule`, consuming `PipelineContext`, producing
`ContextDelta`. The live system instead runs on `WorkflowContext`/
`WorkflowStage`/`WorkflowEngine` — functionally similar (typed
producer/consumer declarations, deterministic ordering) but a distinct,
undocumented-as-the-real-mechanism implementation. This is flagged
separately in §17 as requiring an explicit owner decision, not silently
resolved here.

Everything else checked — VWAP formula, confluence bonus mechanics,
ATR-based TradePlan, REFRESH's 15-minute interval, FAST excluding daily
candles, the UNKNOWN-state convention, ADR-005's mandatory-explanation rule
— matches documentation precisely. No other mismatches found.

---

## 12. Proposed Intraday Architecture

The following eight artifacts are **proposed for future design**, not
implemented here. Each is evaluated against the actual live mechanism
(`WorkflowContext`/`WorkflowStage`, §4) — not the dormant
`domain.context.PipelineContext`, unless and until an explicit decision (§17)
migrates the live system onto that contract.

### 1. SessionContext
- **Purpose:** session-relative state (session date, phase, elapsed-since-open,
  session candle counts) needed by any intraday-aware stage.
- **Producer:** a new run-level computation, ideally built on `calendar/`
  (the sole trading-day/session authority) rather than each future stage
  re-deriving "is this candle in today's session" the way `calc.vwap`
  currently does ad hoc via date comparison.
- **Consumers:** `IntradaySignalSet`, `IntradayTrendContext`,
  `EntryQualification`.
- **Lifecycle:** per-cycle, computed once at run level (like
  `MarketHealthEngine` today), not per-instrument — session phase is
  universe-wide.
- **Persistence:** transient, matching every other run-level artifact
  today; optionally surfaced in `runs.detail_json`.
- **Explainability:** mandatory explanation string per ADR-005 if it will
  influence any decision.
- **UNKNOWN behavior:** e.g. before market open, or before any candle has
  printed in the session yet.
- **New domain object:** yes — a small frozen dataclass paralleling
  `RegimeResult`/`MarketHealthResult`.
- **ADR:** not on its own; folds into whichever ADR formalizes the new
  stage (see `IntradaySignalSet`).

### 2. IntradaySignalSet
- **Purpose:** the bundle of raw intraday technical signals (ORB status,
  RVOL, VWAP relation, momentum flags) computed per instrument from 5m/15m
  bars — the "ingredients" for entry qualification.
- **Producer:** a new `WorkflowStage`, sibling to `indicators`, occupying
  the same dependency slot `indicators` currently holds relative to
  `scoring` (§4's dependency-direction finding) — **not** wedged between
  `indicators` and `regime`.
- **Consumers:** `EntryQualification`. **Explicitly recommend NOT feeding
  this into `ScoringEngine` directly** — per the ID program's own stated
  intent to keep STRUCTURAL QUALIFICATION and INTRADAY EXECUTION
  QUALIFICATION distinct, and consistent with the instruction to consider a
  separate downstream Intraday Qualification stage rather than forcing
  every intraday signal into the existing daily `ScoringEngine`.
- **Lifecycle:** per-cycle, per-instrument, likely computed only for
  instruments that already passed structural (daily) qualification — reuse
  FAST's existing narrower decision-list scoping
  (`current_decision_list_instrument_ids`) rather than the full universe,
  since this needs to run at higher frequency than REFRESH.
- **Persistence:** likely transient per-cycle initially; individual values
  worth exposing via a new read API for the dashboard, similar to how
  VWAP/confluence work today.
- **Explainability:** mandatory per-signal explanation, ADR-005 pattern.
- **UNKNOWN:** e.g. before ORB window completes, insufficient RVOL history.
- **New domain object:** yes.
- **Requires ADR:** **yes** — this is a genuinely new stage in the
  live workflow graph, and its dependency wiring is a structural pipeline
  change even though it reuses the existing `WorkflowStage` mechanism.

### 3. IntradayTrendContext
- **Purpose:** session-relative trend state (VWAP relation, 5m/15m
  directional agreement) — formalizing the existing ad hoc confluence
  calculation into a typed, reusable object, distinct from `regime`'s daily
  trend dimension.
- **Producer:** same new stage as `IntradaySignalSet` — open design
  question whether this should be a separate artifact or a field within
  `IntradaySignalSet` (recommend deciding at design time, not here).
- **Blocked by the same `IndicatorsConfig` one-period-per-name limitation**
  noted in §5 — extending intraday trend logic beyond what the current
  direct-`calc` bypass already does will need either continuing that bypass
  pattern or a config-schema extension.
- **New domain object:** yes, pending the merge-or-split decision above.
- **ADR:** covered by the same ADR as `IntradaySignalSet` if merged.

### 4. RelativeStrengthContext
- **Purpose:** instrument performance relative to its sector/index
  intraday (e.g., "beating Nifty by X% since open").
- **Dependency:** genuinely needs per-instrument `Instrument.sector` plus
  sector/index intraday candles — this **directly depends on the Sector
  Health wiring fix (§6)** being done first, and additionally needs the
  run-level loader extended to prefetch intraday candles for tracked
  sector indices (today only fetched per-instrument on demand).
- **Producer:** same new stage, once its sector/index intraday data
  dependency is available.
- **Consumers:** `EntryQualification`; potentially a future
  `sector_quality`-analogous scoring dimension, but per `IntradaySignalSet`'s
  reasoning, recommend keeping this in the intraday qualification layer,
  not folded into daily `ScoringEngine`.
- **New domain object:** yes.
- **Sequencing:** should follow, not precede, the Sector Health wiring
  decision — flagged as a hard dependency in §16/§17, not an independent
  ID-1 candidate.

### 5. EntryQualification
- **Purpose:** the core "WHETHER the candidate is actionable now" artifact
  — consumes `IntradaySignalSet` + `IntradayTrendContext` +
  `RelativeStrengthContext` + the existing daily `Decision` (as an
  eligibility gate — only intraday-qualify instruments that already have a
  live/valid daily-structural decision) to produce something like
  QUALIFIED / NOT_YET / DISQUALIFIED with a mandatory explanation.
- **Explicitly the "separate downstream Intraday Qualification stage"** the
  ID program instructions point toward — recommend implementing this as a
  new engine/stage downstream of (logically after) `decision`, not as a
  modification of `ScoringEngine`/`DecisionEngine`.
- **Producer:** new `EntryQualificationEngine`.
- **Consumers:** future `IntradayTradePlan` construction, dashboard.
- **Lifecycle:** likely evaluated at FAST cadence for already-decided
  TRADE/WATCH candidates only, reusing the existing decision-list scoping.
- **Persistence:** this genuinely needs to be queryable standalone (e.g.
  "show me all currently-qualified intraday opportunities") — recommend a
  **new dedicated table**, mirroring the existing `decisions`/
  `decision_traces` pattern, not a `runs.detail_json` blob (§14).
- **Explainability:** mandatory, ADR-005.
- **UNKNOWN:** e.g. insufficient intraday history yet.
- **New domain object:** yes, clearly.
- **Requires ADR:** **yes** — this is the centerpiece of the proposed
  architecture; a new persisted concept and a new pipeline stage, both
  warranting explicit owner approval before implementation.

### 6. IntradayTradePlan metadata
- **Purpose:** entry/stop/target parameters for opportunities that pass
  `EntryQualification` — a genuine entry_zone (not a point), tighter
  %-based stop, faster time-stop.
- **Recommend a separate, small `IntradayTradePlan` domain object, not a
  mutation of `TradePlan`.** §7 found most candidate `TradePlan` extensions
  safe, but specifically flagged that a "time-stop" field risks colliding
  semantically with `valid_until`'s existing 6-hour "this analysis is
  stale" meaning. A distinctly-named companion object avoids conflating the
  daily TradePlan's already-frozen, already-serialized, ADR-governed
  contract with intraday minutes-scale semantics, while still reusing
  whatever's genuinely reusable (the entry_low/entry_high pattern, the
  frozen-dataclass/manual-serialization approach).
- **Requires ADR:** yes — new persisted domain object with its own
  contract.

### 7. PlanValidity / Revalidation state
- **Purpose:** track whether an (intraday) plan remains valid, covering the
  nine event-driven trigger types from §8.
- **Recommend staying derived-at-read for anything time-based** (consistent
  with §7's finding that the existing FRESH/AGING/STALE/EXPIRED design is
  deliberately not stored, to avoid a hidden-clock-read ADR-005 violation).
- **But pure derived-at-read cannot detect event-based triggers**
  (PRICE_MOVE, VOLUME_SHOCK, etc.) without a stored baseline — e.g., "did a
  0.5% move happen since plan creation" requires a reference price captured
  *at* plan creation, compared against current data at read time. This
  needs a small stored baseline snapshot (reference price/VWAP at creation)
  plus a still-derived-at-read comparison — an open design point to
  resolve at implementation time, not decided here.
- **Requires ADR:** yes — changes how "is this plan still good" is
  computed and adds new persisted baseline fields.

### 8. ExecutionQuality
- **Purpose:** advisory analytics on how "clean" an entry would be.
- **Hard constraint from §10:** the most obviously useful inputs
  (spread from bid/ask, depth) are **not in the `MarketDataProvider`
  Protocol at all** — not under-populated, contractually absent. A
  meaningful `ExecutionQuality` artifact beyond volume/LTP/OHLC-based
  proxies requires an ADR-002-governed Protocol extension (adding bid/ask/
  depth/turnover/circuit-limit fields) as an explicit, separate decision
  point before this artifact can be usefully scoped.
- **Recommend:** treat as out of near-term scope; if pursued early, scope
  strictly to what's already available (LTP, volume, OHLC, market
  snapshot) and label the limitation explicitly rather than implying
  spread-awareness that doesn't exist yet.
- **Requires ADR:** yes, for the Protocol extension itself — likely
  deferred past ID-1.

---

## 13. ADR Impact Matrix

| ADR | Touched by ID-0 findings? | Impact |
|---|---|---|
| ADR-001 (modular monolith) | No | No violation observed or proposed; every new artifact stays in-process |
| ADR-002 (MarketDataProvider abstraction) | Yes | Confirmed compliant today (zero business-logic Kite imports); one presentation-layer bypass flagged (`market_history_service.py`, not urgent). `ExecutionQuality` (§12.8) would require a governed Protocol extension |
| ADR-003 (PipelineContext/ContextDelta module contract) | **Yes — materially** | The documented contract is entirely dormant; the live system runs a different, undocumented-as-canonical mechanism (`WorkflowContext`/`WorkflowStage`). **Needs an explicit owner decision** (formally amend ADR-003 to document the real mechanism, or migrate the live pipeline onto the dormant one) before ID-1 layers new stages onto an ambiguous foundation. Flagged, not resolved, per CLAUDE.md's "ask before implementing" rule |
| ADR-005 (mandatory explanation) | Yes | Confirmed enforced consistently at the per-object level; every new intraday artifact must follow the same `__post_init__`-enforced, non-empty-explanation, `*_UNKNOWN`-label pattern |
| ADR-006 (circuit-limit risk, proposed not implemented) | Indirect | `ExecutionQuality`'s circuit-limit input (once the Protocol supports it) overlaps this ADR's scope — should be designed together with ADR-006's eventual implementation, not independently |
| ADR-007 (CycleRunnerLock authoritative) | Yes | All cadence-based paths comply; dashboard single-symbol Revalidate is a documented, deliberate bypass. New event-driven revalidation triggers (§8, §12.7) should reuse existing entrypoints, not invent new locking |
| ADR-009 (read concurrency) | Minor | No violation found; a future run-level bulk-prefetch of intraday candles for a larger scanned set (per §4's practical constraint) should be re-checked against read-concurrency assumptions at design time |
| ADR-010 (DarvaX isolation) | No | Not touched by any finding or proposal; must remain isolated |
| ADR-011 (symbol_group/resolve_universe) | Yes | Confirmed **not** a sector-mapping substitute — no `SECTOR` `GroupKind` exists. `RelativeStrengthContext` (§12.4) should use `Instrument.sector` + `sector_index_mapping.json`, not ADR-011 machinery |
| ADR-012 (EMR isolation) | No | Not touched by any finding or proposal; must remain isolated |

---

## 14. Database/Persistence Impact

- **No dedicated tables exist today** for indicators/regime/scoring/
  confidence/risk/evidence — only `decisions`, `decision_traces` (summary
  strings), and `runs.detail_json` (run-level blob). Any new artifact that
  needs to be dashboard-visible, queryable across cycles, or referenced
  standalone (`EntryQualification`, `IntradayTradePlan`, `PlanValidity`
  baselines) needs **new persistence** — recommend new dedicated tables
  mirroring the `decisions`/`decision_traces` pattern, not extending
  `runs.detail_json`, which is not efficiently queryable per-instrument.
- **`candles` already supports arbitrary timeframes** via its composite
  `(instrument_id, timeframe, ts_open)` key — no schema change needed to
  store additional intraday timeframes later.
- **No provider-response/ATHENA-received/persistence timestamp columns
  exist** (§9). If `PlanValidity`'s PRICE_MOVE/VOLUME_SHOCK detection or
  `ExecutionQuality` wants to reason about data staleness precisely, new
  timestamp column(s) are needed — a minor, additive schema change, not an
  architecture change.
- **`TradePlan` remains a single JSON blob inside `decisions.trade_plan_json`**
  — additive fields there are cheap; a genuinely new `IntradayTradePlan`
  object (§12.6) would need its own column or table depending on whether it
  travels with the daily Decision or lives independently (open design
  question).

---

## 15. Proposed ID-1 Scope

Given the milestone-discipline rule (smallest reviewable increment) and
that ID-0 must not pre-select production behavior, the recommended ID-1
scope is deliberately narrow and foundational — no thresholds, no gating
logic, no new persisted decision-relevant artifact yet:

1. **Resolve the ADR-003 ambiguity (§4, §13) first.** Before any new stage
   is added to the live workflow graph, get an explicit owner decision:
   formally document `WorkflowContext`/`WorkflowStage` as the real
   mechanism (retiring the dormant `domain.context.PipelineContext`/
   `ContextDelta`/`IntelligenceModule` as unused scaffolding), or migrate
   the live pipeline onto the documented-but-unused contract. Building
   Stage "2.5" on an unresolved foundation compounds the debt.
2. **Add timeframe/session provenance to `IndicatorResult`** (§5) — a
   small, additive domain change (new optional field(s) on an existing,
   already-extensible result type), needed as a prerequisite for any
   self-describing multi-timeframe stage.
3. **Design (not implement) `SessionContext` + `IntradaySignalSet` as
   domain objects and a new `WorkflowStage` producer**, formalizing what
   `ind_stage`'s ad hoc VWAP/confluence logic already does — without yet
   building `EntryQualification`'s gating logic or freezing any threshold
   (per the numeric-threshold governance rule).
4. **Decide the `IndicatorsConfig` per-timeframe-parameter question** (§5,
   §12.3) — extend the config schema to support per-timeframe periods, or
   formally adopt the existing direct-`calc`-call bypass pattern as the
   sanctioned approach for multi-timeframe indicators.

**Explicitly not ID-1:** `EntryQualification`'s decision logic,
`IntradayTradePlan`, `ExecutionQuality`, `RelativeStrengthContext` (blocked
on the Sector Health wiring decision below), and any numeric
threshold/gate.

**Sequencing note on Sector Health (§6):** the smallest wiring fix is fully
scoped and low-risk, but it is arguably a separate track (already named
"SD-3" in the codebase) rather than part of ID-0..13 itself. Recommend the
owner explicitly decide whether to fold it into ID-1 (since
`RelativeStrengthContext` depends on it) or run it as its own quick,
parallel milestone before ID-1 starts.

---

## 16. Explicitly Deferred Work

Per the ID-0 instructions' explicit "do not do these yet" list: ORB, gap
fade, RVOL, intraday RSI rules, new ATR stop multipliers, target ladders,
position sizing, backtesting, Monte Carlo, any scoring-weight change, any
Decision-threshold change, new trade gates, any `TradePlan` semantic
change, arbitrary timing windows, EMR changes, DarvaX changes, external TA
libraries, another database, another scheduler, order APIs.

Additionally, from this audit's own findings: `EntryQualification`'s full
build, `IntradayTradePlan`, the `ExecutionQuality` Protocol extension,
event-driven `PlanValidity` detectors (§8/§12.7), and
`RelativeStrengthContext` (blocked on the Sector Health wiring decision).

---

## 17. Risks / Open Questions

- **ADR-003 ambiguity** (§4, §13) — needs an explicit owner decision before
  any new stage is layered onto the live pipeline mechanism.
- **`IndicatorsConfig`'s one-period-per-name-globally limitation** (§5)
  blocks clean multi-timeframe indicator configuration — needs a config-schema
  decision before `IntradaySignalSet`/`IntradayTrendContext` can avoid the
  current calc-bypass pattern.
- **FAST-only 15m staleness** (§3, Q14 caveat) — up to 15 minutes stale
  during FAST-only ticks. A real data-freshness risk for any intraday-trend
  logic that assumes fresh 15m data on every tick.
- **Dashboard single-symbol Revalidate bypasses `CycleRunnerLock`** (§8) —
  a known, accepted risk today (ADR-007 §5), but race likelihood grows if
  ID work increases revalidation call frequency; worth re-examining then,
  not now.
- **Provider-to-ATHENA latency is currently unmeasurable** (§9) — needed if
  `PlanValidity`'s DATA_STALE trigger or `ExecutionQuality` want precise
  staleness/latency reasoning; requires a new timestamp column, not an
  architecture change.
- **Execution-quality data (bid/ask/depth/circuit limits) is entirely
  absent from the provider Protocol** (§10) — caps `ExecutionQuality`'s
  usefulness until an ADR-002-governed extension is explicitly decided.
- **Sector Health wiring (SD-3) is a hard prerequisite for
  `RelativeStrengthContext`** but is arguably outside the ID-0..13 track's
  own ownership — a sequencing/ownership question for the owner, not
  something to resolve unilaterally here.
- **No dedicated persistence exists yet for any future intraday artifact**
  (§14) — schema additions are needed before `EntryQualification`/
  `IntradayTradePlan` can be built; the size/shape of those additions
  should be its own explicit design step at ID-1+, not decided in this
  audit.

---

## 18. Recommendation

**ID-0 recommendation: GO WITH CONDITIONS.**

**Why GO:** the runtime audit found no violation of frozen architecture
anywhere, and no evidence that the ID program's premise is broken. Intraday
data ingestion, persistence, and (partial) consumption already work
end-to-end in production today — proving the underlying mechanism is
sound, not something to be built from zero. Indicators are genuinely
timeframe-agnostic and require no rework to run on intraday bars. The
existing `WorkflowContext`/`WorkflowStage` mechanism, while not the one
described in ADR-003, is a real, working, extensible foundation — Kahn
topological ordering, per-stage dependency declarations, consistent
UNKNOWN-state handling, and enforced mandatory explanations are all
genuinely in place and reusable as-is. `TradePlan`'s structure is unusually
safe to extend additively. `CycleRunnerLock`/ADR-007 already provides
everything needed for future event-driven revalidation without inventing
new concurrency machinery.

**Why WITH CONDITIONS, not unconditional GO:**

1. **The ADR-003 dormant-vs-real ambiguity must be resolved explicitly**
   before ID-1 adds any new stage — building on an undocumented foundation
   compounds architectural debt exactly where the ID program most needs
   clarity.
2. **The `IndicatorsConfig` per-timeframe limitation must be decided**
   (config-schema extension vs. sanctioned bypass pattern) before
   `IntradaySignalSet`/`IntradayTrendContext` design proceeds.
3. **Sector Health wiring's relationship to the ID track must be
   sequenced explicitly** by the owner — it's a real dependency for
   `RelativeStrengthContext` but is not itself an ID-0..13 deliverable per
   the original task framing.
4. **`ExecutionQuality` must be treated as gated on an ADR-002 Protocol
   extension decision**, not assumed available — the provider Protocol
   simply doesn't carry the data most people would expect "execution
   quality" to mean.
5. **No numeric threshold gets frozen without deterministic historical
   replay/walk-forward evidence**, per the ID-0 instructions' own
   governance rule (§J) — this applies to every future ID milestone, not
   just ID-1.

None of these conditions require new architecture or contradict anything
frozen — they are decision points the owner should make explicitly, once,
now, so that ID-1 through ID-13 build on solid, agreed ground rather than
each milestone re-discovering the same ambiguities.

---

## Files Inspected

*(Consolidated from all four audit passes — full paths, working tree root
`/Users/cbz-sandeep/DEVELOPMENT DRIVE/GITHUB Projects/ATHENA`.)*

**Orientation / docs:** `ATHENA_BRIEFING.md`, `docs/adr/ADR-007-owner-triggered-background-validation.md`, `docs/ATHENA-TECHNICAL-ARCHITECTURE.md`, `docs/ATHENA-WORKFLOW-METHODOLOGY.md`.

**Entrypoints / scheduling / ops:** `src/athena/cli.py`, `src/athena/scheduling/cadence.py`, `src/athena/scheduling/engine.py`, `src/athena/scheduling/dry_run.py`, `src/athena/ops/serve_runtime.py`, `src/athena/ops/scheduled_run.py`, `src/athena/ops/fast_revalidation.py`, `src/athena/ops/owner_validation.py` (full file), `src/athena/ops/symbol_validate.py`, `src/athena/ops/full_validation.py`.

**Domain / runtime / orchestration:** `src/athena/domain/context.py`, `src/athena/domain/interfaces.py`, `src/athena/domain/enums.py`, `src/athena/domain/market.py`, `src/athena/domain/decision.py`, `src/athena/domain/evidence.py`, `src/athena/runtime/workflow.py`, `src/athena/orchestration/models.py`, `src/athena/orchestration/system_runner.py`, `src/athena/orchestration/pipelines/intelligence.py`, `src/athena/orchestration/stages/decisions.py`, `src/athena/orchestration/stages/monitoring.py`, `src/athena/scanner/scanner.py`.

**Data layer:** `src/athena/data/ingestion/engine.py`, `src/athena/data/store/repository.py`, `src/athena/data/store/schema.py`, `src/athena/data/store/serialization.py`, `src/athena/data/providers/kite_provider.py`, `src/athena/data/providers/kite_ltp.py`.

**Analytical engines:** `src/athena/indicators/engine.py`, `src/athena/indicators/calculations.py`, `src/athena/indicators/models.py`, `src/athena/regime/engine.py`, `src/athena/market_health/engine.py`, `src/athena/sector_health/engine.py`, `src/athena/evidence/engine.py`, `src/athena/evidence/models.py`, `src/athena/scoring/engine.py`, `src/athena/confidence/engine.py`, `src/athena/risk/engine.py`, `src/athena/decision/engine.py`, `src/athena/sizing/engine.py`, `src/athena/sizing/models.py`.

**Symbols / config:** `src/athena/symbols/groups.py`, `src/athena/symbols/universes.py`, `src/athena/config/models.py`, `config/scheduling.json`, `config/ingestion.json`, `config/decision.json`, `config/base.json`, `config/indicators.json`, `config/scoring.json`, `config/sector_index_mapping.json`.

**API layer:** `src/athena/api/v1/routers/market.py`, `src/athena/api/v1/routers/decisions.py`, `src/athena/api/v1/services/candidates_service.py`, `src/athena/api/v1/services/decisions_service.py`, `src/athena/api/v1/services/opportunities_service.py`, `src/athena/api/v1/services/advisory_freshness_service.py`, `src/athena/api/v1/services/market_history_service.py`, `src/athena/api/v1/services/pipelines_service.py`, `src/athena/api/v1/providers/sqlite_providers.py`, `src/athena/api/v1/dtos/decisions.py`, `src/athena/api/static/js/05-utils.js`, `src/athena/api/static/js/09-market-intelligence.js`, `src/athena/api/static/js/12-decisions-list.js`, `src/athena/api/static/js/14-decision-brief-analysis.js`.

**Monitoring:** `src/athena/monitoring/engine.py`.

Plus targeted grep/symbol sweeps (not full reads) over the remaining files
in `orchestration/stages/`, `regime/models.py`, `market_health/models.py`,
`scoring/models.py`, `confidence/models.py`, `risk/models.py`,
`sector_health/models.py`, and `tests/unit/test_domain.py` (existence/shape
checks only).
