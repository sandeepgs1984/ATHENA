# ID-P0.1 — Sector Health Wiring Replay Impact Report

**Date:** 2026-08-29
**Status:** Measurement only. No config, scoring weight, formula, threshold,
`SectorHealthEngine` methodology, sector mapping, or UNKNOWN semantics was
modified anywhere in this checkpoint. No production code was changed.
**Purpose:** ID-P0 wired an already-computed `SectorHealthResult` (weight
15/100) into live scoring/evidence/decision. Before Intraday Intelligence
adds further behavior, quantify the real historical effect of that single
change, isolated from every other variable.

---

## 1. Executive Summary

Using a throwaway scratch copy of the real production database
(`db/athena.db`, never opened for write), 380 real, currently-eligible
instruments were evaluated at a single real historical snapshot
(2026-08-28, session close) under two conditions that differ in **exactly
one** input: `SectorHealthResult` absent (BASELINE, byte-for-byte
reproducing pre-ID-P0 behavior) vs. wired (ID-P0, the real, current code).

- **143/380 (37.6%)** instruments had a resolvable sector this cycle;
  237/380 (62.4%) stayed `UNKNOWN`, exactly as before — never guessed.
- **15/380 (3.95%)** decisions changed type (all `WATCH ↔ NO_TRADE`; no
  `TRADE` appeared in either condition at this snapshot).
- Composite delta over the **143 affected** instruments: mean **+0.24**,
  median **−0.04**, range **−5.32 to +4.47** — an order of magnitude
  smaller than the 60.1%-of-book worst-case modeled in `docs/MILESTONES.md`'s
  original SD-3 impact table, because real per-sector values vary (they are
  not the uniform 20/50/80 flat scenario that model used) and only 37.6% of
  the book has a resolvable sector at all.
- **Confidence also moves** (mean +1.05 over the 143 affected instruments) —
  a real, legitimate, previously-unmeasured second-order effect: sector
  data newly participates in `ConfidenceEngine`'s `cross_engine_agreement`,
  `unknown_ratio`, and `consistency` dimensions once it exists. Explained in
  §9, not a bug.
- **Risk is provably untouched**: delta is exactly `0.0` for all 380
  instruments — `RiskEngine` never accepted `sector_health` and still
  doesn't.
- Two independent full replay attempts produced **byte-identical** results
  for every one of 760 (380 × 2 conditions) comparisons — deterministic,
  confirmed by diff, not assumed.
- One real limitation found and reported, not papered over: ATHENA's
  candle store has no point-in-time query (§14) — this snapshot is a
  single real moment, not a multi-date historical replay, and that is the
  scientifically correct choice given the tooling that exists (a multi-date
  attempt would have silently looked ahead).

**Conclusion: ID-1 READY — measured impact understood.** See §16.

---

## 2. Replay Dataset / Historical Coverage

A read-only backup (`sqlite3.Connection.backup()`, source opened
`mode=ro`) of the real `db/athena.db` was taken; the original was never
opened for write. All work below ran against throwaway local copies of
that backup, deleted after this report was produced.

| | |
|---|---|
| Instruments (all) | 2,204 |
| Active owner candidates | 528 |
| Instruments with `.sector` set | 500 (20 distinct sector labels) |
| Sectors with a `config/sector_index_mapping.json` proxy | 8 of 20 |
| Daily (`1d`) candles | 1,398,459 rows, 2023-08-11 → 2026-08-28 |
| 15m candles | 214,992 rows, 2026-07-29 → 2026-08-28 |
| 5m candles | 979,788 rows, 2026-07-23 → 2026-08-28 |
| Sector proxy index daily candles (all 7 real indices: NIFTY IT/AUTO/PHARMA/FMCG/METAL/REALTY/ENERGY) | 92 rows each, 2026-04-20 → 2026-08-28 |
| Real persisted decisions in the source db | 188,470 rows, 2026-07-31 → 2026-08-28 |
| Replay `as_of` used | **2026-08-28T15:45:00+05:30** — the last real trading day/session-close moment this snapshot actually contains |
| Replay trigger | `RunTrigger.CLOSING` |

---

## 3. Replay Methodology

**Design decision, stated up front:** `SqliteRepository.list_candles_recent()`
(the only candle-read path `OwnerValidationPipeline` uses) takes no
`as_of`/cutoff parameter — it always returns literally the most recent N
rows in the table (`ORDER BY ts_open DESC LIMIT ?`), full stop. Neither it
nor `BacktestingEngine` (`src/athena/backtest/`, inspected directly) provide
genuine point-in-time truncation — the backtest engine only sequences
caller-supplied `pipeline_builder`s chronologically; it does not itself
scope candle reads to "as of" a replay date. **Re-running the live pipeline
at a series of distinct historical `as_of` values would therefore silently
look ahead** at every date except the very last one in the table — exactly
the kind of gap Part C of this checkpoint's instructions required reporting
rather than filling.

**The scientifically valid design given this constraint:** anchor the
entire comparison at the store's own real, most-recent moment (2026-08-28,
the last date the snapshot's candles/quotes/decisions actually reach), so
"most recent 500 rows" and "as of this as_of" coincide exactly — no
look-ahead is possible because there is no future data past that point in
this snapshot at all. Then, within that single fixed real moment, run
`OwnerValidationPipeline.run()` **twice**, changing exactly one thing:

```python
if disable_sector:
    # Exact pre-ID-P0 behavior: no sector-index candle series at all ->
    # run()'s `if sector_candles:` block never executes -> sector_results
    # stays {} -> every per-instrument sector_health resolves to None,
    # identically to how it behaved before ID-P0 wired anything.
    pipe._sector_candles_for_health = lambda candles_by_id: {}
```

This is an **instance-level monkeypatch applied only inside the throwaway
analysis script's own process** — `src/athena/ops/owner_validation.py` on
disk is never touched, and the patched instance is discarded when the
script exits. It reproduces the exact pre-ID-P0 code path (the `if
sector_candles:` block in `run()` never executing), not an approximation
of it.

Because both conditions run against the identical repository state, the
identical `as_of`, the identical `config/` directory, and the identical
`RunTrigger`, every non-sector input — universe eligibility, market
snapshot, `MarketHealthResult`, `RegimeResult`, all eight indicators, VWAP,
confluence, `RiskAssessment` — is **structurally guaranteed** to come out
identical, and this was verified directly (§4, §9), not merely assumed.

`OwnerValidationPipeline.run(RunTrigger.CLOSING, as_of=..., ingestion=<empty IngestionResult>, run_id=...)`
was called with a zero-fetch `IngestionResult` (no ingest happens; the
pipeline reads whatever the repository already holds) — the same real
`OwnerValidationPipeline`/`DailyMarketScanner`/`WorkflowEngine` machinery
that runs every live cycle, unmodified except for the one instance-level
monkeypatch above.

---

## 4. Determinism Evidence

Two fully independent local copies of the same read-only backup were made
(`attempt1`, `attempt2`). Both conditions (BASELINE, ID-P0) were run
against each copy independently — four full pipeline runs in total, no
shared process state between them. Every one of the 380 × 2 = 760
per-instrument `DecisionReport` JSON structures (`decision`, `trade_plan`,
`gates`, `score`, `confidence`, `risk`, `evidence`, `indicators`, `regime`,
`market_health`, `reasoning`, `references` — the full machine-readable
report) was compared byte-for-byte (`json.dumps(..., sort_keys=True)`
equality) between `attempt1` and `attempt2`:

```
determinism_diffs = {"baseline": [], "idp0": []}
```

**Zero differences**, in either condition. No wall-clock read (`as_of` is
an explicit, injected literal — `datetime(2026, 8, 28, 15, 45, tzinfo=IST)`
— never `datetime.now()`), no live provider/network call (`KiteProvider` is
never imported or instantiated anywhere in the replay script), no write
back to the source `db/athena.db` (only the throwaway local copies were
opened for write, and only by `OwnerValidationPipeline.run()`'s own normal
persistence calls, discarded afterward).

---

## 5. Sector Health Coverage

| | Count | % of 380 |
|---|---|---|
| Known (`sector_quality` status `OK`) | 143 | 37.63% |
| Unknown (no `.sector`, an unmapped `.sector`, or no resolvable proxy candles) | 237 | 62.37% |

Sector-quality value distribution among the 143 known instruments: min
33.33, p10 33.33, p25 43.33, median 61.67, mean 55.80, p75 63.33, p90
73.33, max 73.33 (all strictly positive — the 4-dimension average
naturally excludes `SECTOR_BREADTH_UNKNOWN`, so values cluster on the
scoreable trend/momentum/volatility labels' point map).

---

## 6. Decision Transition Matrix

All 380 comparable decisions (instruments that passed Universe Eligibility
and reached `dec_stage` in both conditions — the same 380 in both, since
eligibility is decided before any sector wiring is consulted):

| Baseline → ID-P0 | Count |
|---|---|
| `WATCH → WATCH` | 206 |
| `WATCH → NO_TRADE` | 4 |
| `NO_TRADE → NO_TRADE` | 159 |
| `NO_TRADE → WATCH` | 11 |
| `TRADE → *`, `* → TRADE`, `INSUFFICIENT_DATA → *`, `* → INSUFFICIENT_DATA` | 0 (none occurred at this snapshot in either condition) |

Marginals: `WATCH` 210 baseline / 217 ID-P0; `NO_TRADE` 170 baseline / 163
ID-P0. (206+4=210 ✓, 159+11=170 ✓, 206+11=217 ✓, 4+159=163 ✓.)

---

## 7. Classification Change Rate

**15 / 380 = 3.95%** of decisions changed type — all `WATCH ↔ NO_TRADE`
around the composite=50 watch threshold; none crossed into or out of
`TRADE` (composite=60) as an actual decision-type change (see §12 for the
4 cases where the *composite* crossed 60 without the *decision* changing).

Changed instruments: `NSE:ABDL, NSE:ANANTRAJ, NSE:DRREDDY, NSE:EXIDEIND,
NSE:GMDCLTD, NSE:GRANULES, NSE:HEXT, NSE:HONASA, NSE:JAINREC, NSE:LLOYDSME,
NSE:MAXHEALTH, NSE:MRPL, NSE:PRESTIGE, NSE:SONATSOFTW, NSE:UNITDSPR`.

This is roughly **1/15th of the scale** the original SD-3 impact model
projected (60.1% of book) — because that model deliberately used a
flat/uniform sector value (20, 50, or 80 for the *entire* book) to bound
the worst case, whereas real sector data varies per sector and only
reaches 37.6% of the book at all. The real, measured number is
substantially smaller, but not zero — real classification changes do
occur, and are enumerated above for direct inspection.

---

## 8. Composite Score Delta

**All 380 comparable decisions** (237 of which are mechanically exactly
`0.0`, since `sector_quality` stayed `UNKNOWN` in both conditions for
those instruments):

| Stat | Value |
|---|---|
| min | −5.32 |
| p10 | −0.76 |
| p25 | 0.00 |
| median | 0.00 |
| mean | +0.09 |
| p75 | 0.00 |
| p90 | +1.83 |
| max | +4.47 |
| positive / zero / negative | 67 / 237 / 76 |

**Restricted to the 143 instruments where sector became known** (the
actually-affected population — dividing by the full 380 dilutes the
central tendency with 237 exact zeros):

| Stat | Value |
|---|---|
| min | −5.32 |
| p10 | −2.00 |
| p25 | −0.78 |
| median | −0.04 |
| mean | +0.24 |
| p75 | +1.87 |
| p90 | +2.71 |
| max | +4.47 |
| positive / zero / negative | 67 / 0 / 76 |

The near-zero median and roughly balanced positive/negative split (67 vs.
76) reflect that real sector-quality values (mean 55.8, median 61.7 — see
§5) sit close to the composite's typical range for this book, so activating
the component is closer to *re-weighting toward real information* than to
a one-directional push.

---

## 9. Confidence/Risk Impact

**Risk: exactly zero effect, proven, not assumed.** `RiskEngine.assess()`
was not given a `sector_health` parameter in either ID-0's audit or this
wiring — it doesn't accept one. Measured delta across all 380 instruments:
min `0.0`, max `0.0`, mean `0.0`, 380/380 exactly zero. This is the
expected null result and is reported as confirmatory evidence of correct
isolation, not skipped as "nothing to say."

**Confidence: a real, legitimate, previously-unmeasured second-order
effect.** Restricted to the 143 sector-newly-known instruments: mean
**+1.05**, median **+1.26**, range −2.12 to +1.26, 132 positive / 11
negative / 0 zero. Traced to source (`src/athena/confidence/engine.py`),
this is not a side channel or a bug — three of `ConfidenceEngine`'s six
dimensions structurally read `scoring.components`, and `sector_quality`
joining that dict as a *known* component (instead of `UNKNOWN`) changes
their inputs by construction:

- **`cross_engine_agreement`** — literally `100 − (max known component
  value − min known component value)`. Adding a 7th known value can only
  change the spread, in either direction.
- **`unknown_ratio`** — the fraction of `scoring.components` that are
  `UNKNOWN`; `sector_quality` flipping to known directly reduces the
  numerator.
- **`consistency`** — checks a fixed pair list including
  `("market_quality", "sector_quality")` for a large divergence; that
  specific check can only fire once `sector_quality` is known, so it newly
  participates (and can only ever be neutral-or-negative once active,
  matching why negative confidence deltas exist).

`evidence_completeness`, `data_freshness`, and `indicator_availability`
are unaffected — verified directly: `required_sources=(EvidenceSource.REGIME,)`
is the only completeness-gating source (unchanged by sector wiring), and
VWAP/confluence's own prior isolation design (M-X6/M-X7) already keeps
`indicator_availability` from moving; sector wiring does not disturb that.

---

## 10. Sector-Level Breakdown

Change count / total instruments, by `Instrument.sector` (all 20 real
labels present in the 380-instrument comparable set):

| Sector | Changed / Total |
|---|---|
| Fast Moving Consumer Goods | 3 / 18 |
| Metals & Mining | 3 / 17 |
| Healthcare | 3 / 24 |
| Information Technology | 2 / 20 |
| Realty | 2 / 8 |
| Oil Gas & Consumable Fuels | 1 / 16 |
| Automobile and Auto Components | 1 / 23 |
| Financial Services, Chemicals, Consumer Services, Power, Services, Construction, Construction Materials, Capital Goods, Consumer Durables, Telecommunication, Textiles, Media Entertainment & Publication, (no sector) | 0 / (each) |

Every sector with a nonzero change count is one of the 7 sectors that
actually has a real proxy-index candle series (§2) — mechanically expected,
since a sector with no mapping/no index data can never leave `UNKNOWN` and
therefore can never change a decision. `Realty`'s 2/8 (25%) is the highest
*rate*; the larger-count sectors (`Healthcare` 3/24, `FMCG` 3/18) have
lower rates but more absolute instruments.

---

## 11. Regime-Level Breakdown

At this single real snapshot, **every one of the 380 instruments shared
the identical regime** — `SIDEWAYS` / `LOW_VOLATILITY` / `NO_GAP` — because
regime is computed once, index-level, and shared across the whole cycle
(confirmed directly: `regime` is byte-identical across all 380 instruments
in both conditions, per §4's determinism check and the isolation check in
§13). This is not a limitation of the measurement; it is the real,
structural behavior of `RegimeEngine` (ID-0 §3, Q10) — sector wiring cannot
and does not interact with regime, and a single real day genuinely has one
real regime. A regime-conditioned breakdown with more than one bucket would
require multiple real trading days with different regimes, which the
available point-in-time-unsafe tooling cannot provide without look-ahead
(§14).

---

## 12. Existing-Threshold Crossings

19 instruments' **composite** crossed one of `config/decision.json`'s two
numeric bands (`watch_composite=50`, `min_composite_for_trade=60`) between
BASELINE and ID-P0. **Neither threshold was changed to produce or observe
this** — they were read from the existing, untouched config.

15 of the 19 are the classification changes already listed in §7
(composite crossing 50 and the *decision* actually changing WATCH↔NO_TRADE).
The other **4 crossed composite=60 without the decision type changing**
— all stayed `WATCH` in both conditions:

| Instrument | Composite band change | Composite (baseline → ID-P0) |
|---|---|---|
| `NSE:ADANIPOWER` | ABOVE_TRADE → ABOVE_WATCH_BELOW_TRADE | 62.83 → 59.90 |
| `NSE:AWL` | ABOVE_TRADE → ABOVE_WATCH_BELOW_TRADE | 63.83 → 59.26 |
| `NSE:BPCL` | ABOVE_TRADE → ABOVE_WATCH_BELOW_TRADE | 61.96 → 59.16 |
| `NSE:SARDAEN` | ABOVE_WATCH_BELOW_TRADE → ABOVE_TRADE | 59.06 → 61.20 |

This is a genuine, correctly-observed nuance of the existing, unmodified
`DecisionEngine` contract: a `TRADE` decision requires the composite
**and** all six quality gates **and** a resolvable direction **and** a
buildable `TradePlan` (`decision/engine.py:115-116`) — composite crossing
60 is necessary but not sufficient. These 4 cases show that contract
working exactly as designed, not a gap introduced by this checkpoint.

---

## 13. Unchanged Decisions With New Sector Evidence

**128 of the 143 (89.51%)** instruments whose `sector_quality` newly
resolved to a real value kept the **same** `Decision.type` in both
conditions. This is the intended, expected majority outcome: sector data
is one of six components in a weighted composite (15/100), so most
instruments' overall classification is robust to it — the wiring mostly
*enriches the explanation and the composite's precision* (a real,
measurable score movement, §8) without flipping the actionable outcome.
The 15 that did flip (§7) are the minority where the instrument was
already close enough to a band boundary that this one component's real
value tipped it across — exactly the behavior a correctly-wired,
appropriately-weighted component should produce, and exactly what makes it
worth measuring before ID-1 rather than assuming.

**Isolation cross-check** (not a v Part-B requirement per se, but computed
as further proof of correct scope): for all 380 instruments,
`regime`, `market_health`, `indicators`, `risk.overall`, and the other five
`score.components` (`trend`, `momentum`, `market_quality`, `liquidity`,
`technical_structure`) were compared field-for-field between BASELINE and
ID-P0. **Zero mismatches in every category.** The wiring touches
`sector_quality` and, through it, `confidence` and `composite`/`Decision`
— nothing else.

---

## 14. Data / Replay Limitations

Stated plainly rather than worked around:

1. **No genuine point-in-time candle query exists in ATHENA today.**
   `SqliteRepository.list_candles_recent()` has no `as_of`/cutoff parameter
   — it always returns the literal most-recent N rows. `src/athena/backtest/`
   does not fill this gap; it only sequences externally-supplied
   `pipeline_builder`s and never itself scopes a candle read to a replay
   date. **Consequence:** this checkpoint could not validly replay
   *multiple distinct historical dates* without look-ahead, so it
   deliberately anchored on the single real moment where "most recent" and
   "as of" coincide (the snapshot's own latest real date). A genuine
   multi-session historical replay would require new point-in-time-scoped
   repository infrastructure — out of this checkpoint's scope (measurement
   only, no new production code).
2. **One real day → one real regime.** §11's single-bucket regime
   breakdown is a direct, correct consequence of limitation 1, not an
   analysis shortcut — regime genuinely does not vary within one real
   snapshot.
3. **No `TRADE` decisions existed at this particular snapshot** in either
   condition, so the transition matrix's `TRADE`-involving cells and
   `INSUFFICIENT_DATA`-involving cells are all real, correctly-reported
   zeros for this specific moment — not evidence that sector wiring can
   never produce or block a `TRADE` (§12 shows composite crossing the
   TRADE band did happen, just not with every other gate aligned).
4. **`constituent_breadth` remains unavailable** (unrelated to ID-P0,
   already documented) — `sector_quality`'s value is the mean of only the
   scoreable trend/momentum/volatility dimensions; breadth stays
   `SECTOR_BREADTH_UNKNOWN` for every sector, in both conditions, as
   before.

None of these were filled with fabricated data — each is reported as a
boundary of what the existing store/tooling can validly support.

---

## 15. EMR/DarvaX Isolation Confirmation

The replay script imports only `athena.data.ingestion.models`,
`athena.data.store.repository`, `athena.domain.enums`, and
`athena.ops.owner_validation` — no module under `athena.explosive_move` or
`athena.darvax` was imported, read, executed, or referenced at any point.
No EMR model, evidence, label, scanner output, probability, or
configuration was consumed. No DarvaX output was consumed. Nothing in this
checkpoint's result depends on, or was compared against, EMR or DarvaX in
any way, and neither was modified.

---

## 16. Conclusion

The activation of an already-approved, already-weighted (15/100) scoring
component was measured end-to-end against 380 real, currently-eligible
instruments from the real production book, isolated to a single verified
independent variable, and shown deterministic across two independent full
replay attempts. The effect is real (3.95% of decisions change type, a
mean +0.24/median −0.04 composite shift among the 143 affected
instruments, a genuine confirmatory confidence-machinery interaction) but
an order of magnitude smaller than the original worst-case model — and
risk, regime, market health, indicators, and every other scoring component
are proven byte-for-byte untouched. No threshold, weight, or methodology
was changed to produce or in response to this measurement.

**ID-1 READY — measured impact understood.**
