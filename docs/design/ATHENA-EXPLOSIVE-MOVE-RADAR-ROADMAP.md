# ATHENA Explosive Move Radar - Research and Delivery Roadmap

| Field | Value |
|---|---|
| Status | EM-5 Track B settled comparison complete, inconclusive; EM-4E owner-approved / GO 2026-08-28 |
| Governing ADR | ADR-012 (Accepted 2026-08-21) |
| Started | 2026-08-21 |
| Current gate | EM-5 Track B inconclusive settled comparison pending owner review |
| Canonical ATHENA impact | None permitted |

## 1. Purpose

Explosive Move Radar (EMR) will test whether ATHENA can rank NSE symbols by a historically supported chance of exceptional intraday expansion, with special attention to +10% events.

EMR is not a promise that a symbol will rise 10%, a daily tip generator, or a trade signal. The project succeeds only if it produces honest evidence about whether a useful edge exists. `No reliable edge found` is an acceptable result.

## 2. Non-negotiable boundaries

- Remain separate from ATHENA score, confidence, risk, Decision, TradePlan, and eligibility.
- Remain independent of DarvaX methodology and output.
- Add no order placement or broker execution.
- Perform no per-symbol provider calls in research or scanner loops.
- Represent missing evidence as `UNKNOWN`, never fabricated or silently zero.
- Make every feature point-in-time and cutoff-safe.
- Evaluate chronologically and out of sample.
- Persist freshness, source coverage, and artifact provenance.
- Start no live scanner until historical utility and calibration gates pass.
- Start no UI until the live scanner contract is accepted.

## 3. Required research questions

The research must answer all of the following without forcing a positive result:

1. What percentage of NSE symbol-days hit +10%?
2. How does the rate vary by year?
3. How does the rate vary by market regime?
4. Which sectors produce the most events?
5. How important is liquidity?
6. What happens after gap-ups?
7. Does an all-time-high or 52-week breakout materially increase hit rate?
8. Does relative volume materially increase hit rate?
9. Does increasing relative volume outperform static high relative volume?
10. Does compression improve the odds?
11. Which opening-range-breakout window performs best?
12. Does a successful retest improve continuation?
13. Does sector leadership matter?
14. Does market breadth matter?
15. Which feature combinations provide the highest precision at useful shortlist sizes?
16. At which intraday checkpoint does probability become meaningfully useful?
17. How much target distance can realistically remain at each checkpoint?
18. What are typical MFE and MAE after candidate identification?
19. Which conditions produce the worst false positives?
20. Are +10% events statistically predictable enough to justify production use?

The final report must say plainly if the answer to question 20 is no, if useful evidence appears only after a later checkpoint, or if a lower expansion threshold is materially more defensible.

## 4. Event contract

Configurable thresholds are 5%, 8%, 10%, 12%, 15%, and 20% for:

- `TOUCH_N`: intraday high reaches the threshold above the frozen reference;
- `CLOSE_N`: close reaches the threshold above the frozen reference;
- `OPEN_TO_HIGH_N`: high reaches the threshold above session open.

EM-1a freezes reference prices, exchange sessions, pre-open treatment, corporate-action policy, symbol changes, price bands/halts, incomplete candles, liquidity/tradability, point-in-time membership, target horizon, and timestamp semantics before any labels are generated.

## 5. Two-stage observation design

### Pre-open / early-open estimate

Uses only evidence available by its cutoff: prior-session structure and compression, market/sector regime, known catalyst evidence, authoritative pre-open gap, and opening observations available at that time.

### Intraday checkpoint estimate

The candidate checkpoint set is 09:20, 09:30, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00, and 14:00 IST. EM-1a must measure data coverage and freeze the checkpoints that can be researched honestly; later implementation may phase the accepted set, but it may not silently omit unsupported checkpoints. Every estimate uses only data available by its checkpoint. Candidate evidence includes opening range, time-normalized relative volume, volume acceleration, persistence, relative strength, and distance already travelled.

Each checkpoint is a separate prediction problem with its own cutoff, base rate, calibration, and artifact version.

## 6. Evidence families

| Family | Examples | Required treatment |
|---|---|---|
| Catalyst | results and material announcements | source and observed-at time required |
| Gap | prior close to open | corporate-action-safe reference |
| Volume | time-normalized RVOL and acceleration | compare like-for-like session minutes |
| Structure | breakout, resistance, compression | independent of DarvaX output |
| Opening range | 15/30-minute break and hold/failure | checkpoint-safe only |
| Persistence | close location and pullback behavior | deterministic definition |
| Relative strength | symbol vs sector and broad index | synchronized observations |
| Leadership | sector breadth and index leadership | partial coverage explicit |
| Regime | trend, volatility, breadth | persisted ATHENA evidence only |
| Feasibility | completed move, remaining range, remaining session minutes, price band, ATR | fail closed if required data is unknown |

## 7. Data-readiness risks

- **Historical depth:** existing data does not prove five to ten years of complete point-in-time coverage. EM-1a reports actual usable sessions before a model scope is promised.
- **Survivorship:** a current universe cannot support an historical NSE-wide claim. Historical membership must be measured or results labelled as survivor research.
- **Corporate actions:** splits, bonuses, mergers, dividends, and symbol changes can create false events. Authoritative adjustment or explicit exclusion is mandatory.
- **Catalysts:** without authoritative observed-at history, catalyst evidence remains `UNKNOWN`.
- **Price bands and halts:** without authoritative evidence, the related +10% feasibility component is unavailable and cannot be inferred.

## 8. Provisional responsibility map

```text
src/athena/explosive_move/
  models.py          targets.py       coverage.py
  dataset.py         features.py      feasibility.py
  catalyst.py        structure.py     volume.py
  opening_range.py   intraday.py      probability.py
  ranking.py         evidence.py      scanner.py
  backtest.py        calibration.py   repositories.py
  service.py

config/explosive_move.json
```

This is not permission to create every file at once. Each approved milestone adds only what it needs.

## 9. Milestone roadmap

### EM-0 - Architecture and research contract

**Status:** Approved 2026-08-21.

Delivered ADR-012, this roadmap, milestone registration, and an explicit no-canonical-impact statement. **Exit:** owner accepted ADR-012 after the four review refinements were incorporated. No EMR implementation was started in EM-0.

### EM-1a - Data coverage and event contract

**Status:** Approved 2026-08-21; zero checkpoints accepted.

Inventory daily/intraday/quote/universe/sector/index/corporate-action/price-band/halt/catalyst coverage; quantify survivorship and adjustment risk; freeze labels, exclusions, checkpoints, and dataset/manifest contracts.

The measured audit is `docs/research/EM-1A-DATA-COVERAGE-AUDIT.md`; the
machine-readable contract is `config/explosive_move.json`. The audit accepted
zero checkpoints because corporate-action authority, point-in-time membership,
and canonical complete intraday sessions are unavailable. No labels, features,
models, scanners, or UI were created.

**Acceptance:** every claimed source is measured, unavailable evidence is explicit, false corporate-action labels have a tested prevention policy, point-in-time limitations are plain, and the owner approves the usable research scope.

### EM-1r - Research data remediation

**Status:** EM-1r1 through EM-1r5 approved (2026-08-26) -- see
`docs/design/EM-1-RESEARCH-DATA-REMEDIATION-PLAN.md` and
`IMPLEMENTATION_SUMMARY.md`'s top entry for EM-1r5's full detail.

The approval-gated EM-1r1 through EM-1r5 sequence covers authoritative
corporate actions, canonical intraday sessions, point-in-time population/quote
hygiene, and the final coverage re-audit. Its frozen ownership, provenance,
acceptance, and stop conditions live in
`docs/design/EM-1-RESEARCH-DATA-REMEDIATION-PLAN.md`.

No EM-1r milestone creates labels. EM-1r5 approved all 9 candidate
checkpoints as `accepted_ist` (research-ready evidence only, not
predictive value) -- EM-1b is now unblocked.

### EM-1b - Deterministic historical event dataset

Build immutable symbol-day/checkpoint records, event labels, deterministic partitions/manifests, and leakage/session/adjustment/replay tests. Identical inputs must reproduce labels and row counts.

**Status (2026-08-27):** dataset generated, self-validated, awaiting
Milestone Review Summary approval. Owner-approved chronological
partitions (`src/athena/explosive_move/partitions.py`): TRAIN
2023-08-14→2025-05-31 (440 sessions), VALIDATION 2025-06-01→2025-09-30
(85), CALIBRATION 2025-10-01→2025-12-31 (61), FINAL_TEST
2026-01-01→2026-08-21 (157, sealed holdout). Deterministic production
label dataset generated by
`src/athena/data/em1b_label_dataset_generation.py`:
`artifacts/research/em1b/{labels,manifests,dataset_index.json}`,
cross-validated against the independent partition-measurement script and
replay-verified deterministic. See `IMPLEMENTATION_SUMMARY.md`'s top
entry for the full Review Summary.

### EM-1c - Base-rate research report

Publish event frequencies by threshold, year, sector, cohort, and regime with sample counts, event counts, uncertainty, caveats, and a proceed/narrow/acquire-data/stop recommendation. Freeze the minimum-support policy that prevents very small cohorts from being promoted regardless of apparent lift. No feature lift is claimed here.

### EM-2 - Cutoff-safe feature engineering

Implement versioned evidence families with observed-at cutoffs and explicit unknown states. Definitions remain independent of DarvaX.

### EM-3 - Historical conditional analysis

Publish conditional frequencies, lift, interactions, sample counts, event counts, uncertainty, ablations, and regime stability. Enforce EM-1c's minimum-support policy and select only defensible features for modelling.

### EM-4 - Expansion probability model

Evaluate deterministic score, empirical tables, logistic baseline, and only then a justified tree or boosted-tree model. Preserve explicit chronological `TRAIN`, `VALIDATION`, `CALIBRATION`, and untouched `FINAL TEST` roles; the final test cannot select features, model classes, hyperparameters, thresholds, calibration, or shortlist sizes. Produce walk-forward metrics, calibration, false-positive rate, MFE, MAE, time-to-target, and target hit rate by probability bucket. This is the live-scanner go/no-go gate.

### EM-5 - Intraday live scanner

If EM-4 passes, freeze and implement the `INACTIVE`, `WATCH`, `DEVELOPING`, `CONFIRMED`, `HIGH_CONVICTION`, `FADING`, `INVALIDATED`, and `TARGET_REACHED` transition contract, coherent bulk-input ranking, feasibility gates including remaining session minutes, checkpoint updates, evidence explanations, and replay. No UI and no per-symbol provider calls. Persist scanner duration and database query volume for the later isolation comparison.

### EM-6 - Market Intelligence UI

If EM-5 is approved, add `Explosive Move Radar` with permanent Experimental labelling, freshness, checkpoint, calibration context, evidence, missing coverage, and no trade-authorizing language.

### EM-7 - Live shadow validation

Run without affecting ATHENA. Track precision, lift, calibration, MFE, MAE, misses, false positives, regime drift, data failures, and latency. Compare EMR disabled with EMR shadow mode for dashboard load time, symbol-validation latency, canonical cycle timing, database query latency and volume, CPU and memory use, and EMR scanner-cycle duration. Any material canonical regression blocks promotion.

### EM-8 - Integration decision

Choose research-only, continued shadow validation, retirement, or a separate ADR for limited integration. No automatic promotion.

## 10. Model and evaluation gates

EM-4 cannot pass on accuracy or ROC AUC alone. It must report base rate, precision/lift at practical shortlist sizes, recall, precision-recall AUC, Brier score, calibration error, reliability, cohort/regime stability, uncertainty, ablations, simple-baseline comparison, and false-positive/false-negative review.

EM-4's final test is a once-only evaluation surface for the frozen pipeline. Results from it may reject or retire the pipeline, but may not feed back into feature, model, threshold, calibration, or shortlist choices under the same test designation.

No universal numeric threshold is invented now. EM-1c establishes the real base rate and operational shortlist size; EM-4 proposes evidence-based gates for owner approval before live work.

## 11. Live result contract

An approved live result includes symbol/exchange, checkpoint/cutoff, state, calibrated probability or honestly named estimate, EMR-owned confidence based on estimate reliability and evidence coverage, base-rate/lift reference, feasibility, positive/negative/unknown evidence, source freshness/coverage, artifact versions, rank explanation, and `Experimental - not a trade signal`. EMR confidence is not canonical ATHENA confidence.

Ranks use one coherent bulk snapshot. Mixed-age inputs are rejected or marked partial.

## 12. Operating procedure

Every milestone follows Design -> Implement -> Test -> Self-Validate -> Review Summary -> documentation update -> owner review. Stop after every milestone. No future-milestone code, placeholder model, speculative UI, or hidden integration is allowed.

Each review summary records objective, completed scope, architecture alignment, files created and modified, data sources, algorithms or features, tests and full results, Ruff/static checks, historical evidence, performance measurements, leakage and replay verification, known limitations, remaining work, and one consolidated commit message.

## 13. Current handoff

ADR-012 is Accepted. Current status is authoritative in
`docs/MILESTONES.md` and `docs/ATHENA-EMR-HANDOFF.md`. As of 2026-09-01,
EM-5 Track B settled comparison is complete and inconclusive under the frozen
three-label Track B classification contract: Tuesday 2026-09-01 live capture
had 0 off-grid raw `ts_open` values, so the accepted classifier left
`classification=null` rather than inventing a fourth outcome. The Monday
2026-08-31 Track B evidence was not captured and is recorded as
`NOT_OBSERVED_LIVE` for all nine frozen checkpoints in
`docs/research/EM-5-TRACK-B-LIVE-M5-CAPTURE-2026-08-31.md`. The Tuesday
2026-09-01 live capture and settled comparison are recorded in
`docs/research/EM-5-TRACK-B-LIVE-M5-CAPTURE-2026-09-01.md`. EM-5 remains open
pending owner review/decision; EM-6 must not start until EM-5's canary blocker
closes and the owner explicitly authorizes the next milestone.
