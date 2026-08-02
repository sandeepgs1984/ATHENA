# DD-12 — Sector Health Data Source

| | |
|---|---|
| Status | **ACCEPTED** — Owner approved Option A 2026-08-01, implemented same day |
| Date | 2026-08-01 |
| Trigger | `SD-2` (`docs/MILESTONES.md`) — F-5's sibling engine, `SectorHealthEngine` (M2.3, approved), was built and tested but has never run in the live pipeline. `sector_quality` (scoring weight 15) is permanently `UNKNOWN` for every symbol ever scored |
| ADR context | None required for Option A (see §3) — `SectorHealthEngine`'s M2.3 contract already expects a sector index candle series; Option A supplies exactly that via the already-approved `MarketDataProvider` Protocol (ADR-002). Option B would require an ADR |
| Code impact | `SD-2` (this decision) → `SD-3` (wire `sector_quality` into `ScoringEngine.score()` + recalibrate `config/decision.json` thresholds — separate owner-gated decision, ships with a before/after replay diff per the existing D-3 impact table) |

---

## 1. Decision question

`SectorHealthEngine.assess()` needs a **sector index candle series** (trend/breadth/momentum/volatility over time) to compute anything. The repository holds daily candles for exactly three non-equity instruments — `NSE:NIFTY 50`, `NSE:NIFTY BANK`, `NSE:INDIA VIX` — and zero sector indices. Which source should supply that series, so `sector_quality` can stop being permanently unknown, without fabricating a value or silently reshaping 60% of the book's TRADE/WATCH/NO_TRADE bands (see D-3's impact table)?

Owner already flagged two candidates in `docs/MILESTONES.md` (`SD-2`); this DD evaluates both plus the status quo, and adds a finding from re-checking feasibility now that IX-1 (2026-07-31) exists: **the mechanism Option A needs already works today, proven by IX-1's own live sector-index quotes.**

---

## 2. Decision criteria

| # | Criterion | Bar |
|---|---|---|
| C1 | Provenance | Traceable to an official NSE index value, or an explicitly-documented ATHENA computation — never a silent estimate |
| C2 | Replay | Same inputs → same `SectorHealthAssessment`; deterministic, no wall clock |
| C3 | Freshness | Available same-cycle as the equity candles it scores alongside |
| C4 | Coverage | How many of ATHENA's 20 distinct `instruments.sector` values actually get a real (non-`UNKNOWN`) sector score |
| C5 | Governance overhead | Does it fit the already-approved M2.3 engine contract (index series in) or does it require an ADR to change what "sector index" means computationally |
| C6 | Ops burden | New code/config surface, rate-limit impact, one-time backfill cost |
| C7 | Failure mode | Missing/partial data → `UNKNOWN` component, never a default "neutral" score, never aborts the cycle |

---

## 3. Candidates evaluated

### A. Ingest real NIFTY sectoral index history via Kite (recommended primary)

| Criterion | Assessment |
|---|---|
| C1 | **Pass** — official NSE sectoral indices (NIFTY IT, NIFTY AUTO, etc.), not a derived estimate |
| C2 | **Pass** — same deterministic daily-candle ingestion already used for the 3 benchmark indices |
| C3 | **Pass** — same ingestion cycle, same cadence |
| C4 | **Partial** — 8 of 20 `instruments.sector` values have a clean matching tracked index (IT, Auto, Pharma≈Healthcare, FMCG, Metals, Realty, Energy≈Oil&Gas, PSU Bank). The largest sector by symbol count, **Financial Services (101 stocks)**, plus Capital Goods (63), Chemicals (26), Power (17), Consumer Durables (16), Services (14), Construction (13), Construction Materials (11), Telecommunication (10), Textiles (5), Media (5), Diversified (3), have no exact match today |
| C5 | **Pass, no ADR needed** — `SectorHealthEngine`'s approved M2.3 contract already expects an index candle series; this supplies exactly that, through the existing `MarketDataProvider.daily_candles()` method (ADR-002), not a new Protocol |
| C6 | **Low** — re-verified directly against the code: `kite_provider.py`'s `_ensure_catalog()` already force-resolves any instrument in `index_instruments` regardless of the equity filter (this is *why* IX-1's live sector quotes already work), and `daily_candles(instrument_id, start, end)` is fully generic with no per-instrument special-casing. `cli.py`'s `_build_ingest_engine()` already has a block ("Always include configured index / VIX instruments") that adds whatever's in `kite_cfg.index_instruments` to the scoped daily-candle ingestion list every cycle, so adding the 8 IDs there gets them onto the ongoing daily ingest path with no other change. **Correction (2026-08-01):** an earlier read of this session claimed a "925-day benchmark history" existed to reuse for backfill — that number was a same-session misreading (it summed candle rows across all three timeframes, 1d+5m+15m, not daily bars). The real daily history for the 3 benchmark indices is 67 bars (2026-04-27 to 2026-07-31), accumulated by ordinary day-by-day ingestion under `ingestion.lookback_days: 90` — there is no dedicated backfill mechanism to reuse. A small one-off backfill utility is net-new work (see §4 note 2), not a reuse of an existing mechanism. Rate-limit impact of the ongoing daily fetch: 8 more sequential calls per cycle at the existing 0.334s spacing — trivial |
| C7 | **Pass** — same missing-data-→-`UNKNOWN` handling `MarketHealthEngine`/regime already use for benchmark indices |

**Fit:** Lowest cost and lowest governance overhead of the three, at the price of covering roughly 8 of 20 sectors rather than all of them.

### B. Derive sector aggregates from constituent candles (`instruments.sector`)

| Criterion | Assessment |
|---|---|
| C1 | **Partial** — real constituent candles (already Kite-sourced), but the aggregation itself (e.g. cap- or equal-weighted mean return) is an ATHENA-invented computation, not an official index value |
| C2 | **Pass** — pure function over already-persisted candles; arguably *more* replay-robust since it never depends on a separate historical data delivery |
| C3 | **Pass** — identical freshness to whatever the constituent candles already have |
| C4 | **Pass — full coverage.** Derives directly from whatever `instruments.sector` values exist, so all 20 sectors get a real score, including Financial Services |
| C5 | **Requires an ADR.** `SectorHealthEngine`'s M2.3 contract was approved assuming an index candle series input; a constituent-derived aggregate is a different computation method entering the same slot, which is exactly what `SD-2`'s own text already flags as ADR-gated |
| C6 | **Higher** — needs a new weighting/aggregation methodology designed and tested (how to weight constituents, what to do with a sector missing 40% of its constituents' candles that day, etc.) — not a config change |
| C7 | **Partial** — needs its own explicit threshold for "too many constituents missing → sector `UNKNOWN`," which doesn't exist yet and would need calibrating |

**Fit:** Only path to full 20-sector coverage, but higher build cost and an ADR before any code, per `SD-2`'s own framing.

### C. Hybrid — Option A where a tracked index exists, Option B as fallback elsewhere

| Criterion | Assessment |
|---|---|
| C1–C7 | Inherits A's strengths where an index is tracked, B's coverage elsewhere — but combines both cost centers (config + backfill *and* a new aggregation method + ADR + its own missing-data threshold), and now needs a rule for exactly which sectors get which computation, documented as such so nothing looks like a single consistent methodology when it isn't |

**Fit:** Full coverage without giving up A's provenance where available, but the most expensive and most complex of the three — worth a future DD of its own if partial coverage from A alone proves insufficient in practice, not a v1 recommendation.

### D. Leave `sector_quality` permanently unknown (status quo)

Already implicitly rejected — the owner asked for this feasibility re-check specifically because D-3's impact table shows 60.1% of the live book would have its TRADE/WATCH/NO_TRADE band decided by sector score alone once wired, meaning the *absence* of this data is itself a real gap in explainability, not a neutral default. Listed here only for completeness, matching the DD-11 convention of recording what's already been rejected.

---

## 4. Recommendation (for owner acceptance)

**Select Option A** as the v1 data source:

1. Add the 8 already-IX-1-tracked instrument IDs to `config/providers/kite.json`'s `index_instruments`: `NSE:NIFTY IT`, `NSE:NIFTY AUTO`, `NSE:NIFTY PHARMA`, `NSE:NIFTY FMCG`, `NSE:NIFTY METAL`, `NSE:NIFTY REALTY`, `NSE:NIFTY ENERGY`, `NSE:NIFTY PSU BANK`.
2. Run a one-time historical backfill for those 8 instruments so `SectorHealthEngine` has meaningful trend/momentum lookback from day one instead of accumulating organically for weeks. **No existing mechanism does this today** (see correction in §3/C6) — `IngestionConfig.lookback_days` caps at 365 (Pydantic), there is no backfill script anywhere in the repo, and the current 67-day benchmark-index history came from ordinary daily ingestion, not a backfill. This needs a small, new, scoped utility: construct an `IngestionConfig` limited to these 8 instrument IDs with `lookback_days` set to match what equities/benchmarks already have (~90 days, well inside the 365 cap — no need to approach Kite's 2000-day capability ceiling), and run it through the existing, already-tested `LiveIngestionEngine.run_cycle()` — reusing its validation/quarantine/persistence path rather than writing new candle-fetching logic.
3. Add the sector-name → tracked-index-key mapping this needs (`instruments.sector` value → one of the 8 index keys) as a new, explicit config — not inferred by string-matching — so an unmapped sector fails loudly into `UNKNOWN` rather than guessing the nearest-sounding index.
4. **Defer full 20-sector coverage.** Ship with the ~8-sector partial coverage from Option A; treat Option C (hybrid) as a candidate for a *later* DD only if partial coverage proves insufficient once `SD-3` shows real usage — not a v1 requirement.

### Acceptance notes

1. **Scope of this DD:** the data source only. Wiring `sector_health` into `ScoringEngine.score()` and recalibrating `config/decision.json` thresholds is `SD-3` — a separate, already-identified, owner-gated decision with its own before/after replay-diff requirement. Accepting this DD does **not** activate `sector_quality`.
2. **Unmapped sectors** (Financial Services, Capital Goods, Chemicals, Power, and the other 9 not covered by the 8 tracked indices) continue to report `sector_quality: UNKNOWN` exactly as today — this DD does not regress or change their treatment.
3. **No ADR required** for this option specifically, since it uses the existing `MarketDataProvider.daily_candles()` Protocol (ADR-002) and supplies exactly the index-series input `SectorHealthEngine`'s approved M2.3 contract already expects.
4. **Config:** `config/providers/kite.json` → `index_instruments` (extend); new `config/sector_health.json` (or a new file) → sector-to-index mapping.
5. **Cycle resilience:** a missing/failed sector-index fetch on any given day → that sector's `sector_quality` is `UNKNOWN` for that cycle only, exactly like the existing benchmark-index missing-data handling; the daily cycle continues.
6. **Revisit:** if usage under `SD-3` shows the 8-sector partial coverage is materially insufficient (e.g. Financial Services' 101 stocks staying permanently unknown is judged too large a gap), raise Option B or C as a follow-up DD rather than reopening this one.

---

## 5. Explicit non-goals

- Fabricating a sector score for any of the 12 currently-unmapped sectors via string-matching or a guessed nearest index.
- Activating `sector_quality` in scoring — that is `SD-3`, gated separately with its own owner approval and replay diff.
- Changing `SectorHealthEngine`'s M2.3 contract, thresholds, or `config/sector_health.json`'s existing trend/breadth/momentum/volatility parameters.
- Any change to `MarketDataProvider` (ADR-002) itself — this uses the existing Protocol as-is.

---

## 6. Traceability

- Blocking milestone: `docs/MILESTONES.md` → `SD-2` (this DD resolves it), `SD-3` (remains separately gated)
- Prior finding: `docs/MILESTONES.md` → D-3 impact table (60.1% of the live book would have its band decided by sector score alone once wired — the reason this can't ship without `SD-3`'s separate recalibration gate)
- Engine: `src/athena/sector_health/engine.py` (`SectorHealthEngine`, M2.3, approved, currently unwired)
- Data mechanism verified: `src/athena/data/providers/kite_provider.py` (`_ensure_catalog`, `daily_candles`), `src/athena/cli.py` (`_build_ingest_engine`'s index-instrument inclusion block)
- Related, already-approved precedent: `docs/decisions/DD-11-institutional-flow-fii-dii.md` (the last time a new market-wide signal earned its way toward a frozen scoring component)
- Index tracking this reuses: `docs/design/ATHENA-INDEX-SECTOR-INTELLIGENCE-ROADMAP.md` (IX-1's tracked-index catalog and instrument IDs)

---

## 7. Implementation (2026-08-01)

- **`config/providers/kite.json`** — `index_instruments` extended from 2 to 10 entries (the 8 sector indices, matching IX-1's tracked set exactly).
- **`config/sector_index_mapping.json`** (new) — the explicit sector→index-key mapping from §4, 8 entries covering 8 of 20 `instruments.sector` values; the other 12 (Financial Services, Capital Goods, Chemicals, Power's non-energy overlap, etc.) are deliberately absent, not guessed.
- **`SectorIndexMappingEntry`/`SectorIndexMappingConfig`** (`src/athena/config/models.py`) — new, additive Pydantic models; `SectorHealthConfig` and `IndexIntelligenceConfig` (both frozen contracts) are untouched.
- **`OwnerValidationPipeline`** (`src/athena/ops/owner_validation.py`) — `SectorHealthEngine` (M2.3, previously never instantiated outside its own tests) now runs every cycle for whichever sectors have a mapped index with real candle data, persisting real, non-fabricated per-sector assessments into `detail["sector_health"]` — same persistence pattern as `market_health_score`. **Confirmed untouched**, by direct code reading: `ScoringEngine.score()`'s only call site (`owner_validation.py`'s `sco_stage`) does not pass `sector_health`, so `sector_quality` remains exactly as before (`_unknown(...)`, `SD-3` unstarted).
- **`athena backfill-sector-indices`** (new CLI command, `src/athena/cli.py`) — one-time historical backfill, reusing the existing `LiveIngestionEngine`/validator/quarantine path (not new candle-fetching logic), scoped to the 8 sector instrument IDs with a configurable `--lookback-days` (default 90).
- **Correction to this DD's own §3/C6/§4 note 2:** an earlier read of the session that produced this DD claimed a "925-day benchmark history" existed for the backfill to reuse — that number was itself a same-session misreading (summed candle rows across all three timeframes: 1d+5m+15m). The real benchmark daily history was 67 bars, and there was no existing backfill mechanism at all; the CLI command above is genuinely new code, not a reuse of something that already existed.
- **Verification:** full suite 1,166 passed (7 new tests: `SectorIndexMappingConfig` validation/uniqueness/shared-index-key cases in `tests/unit/test_config.py`; end-to-end `OwnerValidationPipeline.run()` wiring against the real production `config/` directory — not a copy — in `tests/ops/test_owner_validation.py`, covering both the populated and empty-sector-health cases). Ruff clean (same one pre-existing, unrelated `SizingConfig` redefinition finding as before this session). **Also live-verified**, not just unit-tested: ran `athena backfill-sector-indices` for real against Kite — fetched and wrote 504 real daily candles across all 8 sector indices (63 bars each, 2026-05-04 to 2026-07-31), confirmed directly against the database afterward.
