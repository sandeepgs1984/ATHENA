# EM-6 — Discovery & Modeling Contract

**Status:** Discovery only. Implementation not started.
**Depends on:** EM-0 through EM-5 (all owner-approved/closed). Governing
boundary: `docs/adr/ADR-012-explosive-move-radar-boundary.md` (Accepted,
2026-08-21).
**Does not:** implement EM-6, fit/refit any model, read FINAL_TEST, select
any threshold, add API/UI, touch canonical Scoring/Confidence/Risk/
Decision/TradePlan, touch DarvaX, or start ID-7.

## 1. Executive summary

EM-6 does **not** need to be inferred from its number, and it does not
need new model-fitting, calibration, or holdout work — all three are
already done and closed (EM-4B fitting, EM-4D calibration, EM-4E sealed
FINAL_TEST evaluation, GO). The repository already documents, in one
place (`docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md` §9), what
EM-6 is meant to be: **the EMR research UI** — a Market Intelligence
dashboard surface, permanently labelled "Experimental," showing
freshness/checkpoint/calibration-context/evidence/missing-coverage, with
no trade-authorizing language. This is **documented roadmap intent**, not
an owner-ratified milestone contract (it never went through
Design→Implement→Test→Review); it is the only substantive EM-6 content
anywhere in the repo, and every other reference to EM-6 (dozens, across
`docs/MILESTONES.md`, `docs/ATHENA-EMR-HANDOFF.md`,
`IMPLEMENTATION_SUMMARY.md`, and the ID-track's own docs) is purely
procedural: "not started," "do not start without fresh explicit owner
authorization," "EM-5's closure does not authorize EM-6."

Recommended EM-6 shape from the owner's own menu (§21 below): **G. OTHER
— read-only presentation/UI work**, not A–E (those milestones are already
closed) and not F (no evidence found that more data is required before
UI work). This recommendation, and the proposed two-slice sub-milestone
split, await explicit owner decision (§23).

## 2. EM-5 closure recorded

`IMPLEMENTATION_SUMMARY.md:2689`: **"EM-5 — APPROVED / CLOSED — 2026-09-01."**
`docs/ATHENA-EMR-HANDOFF.md:43`: **"EM-5 is closed. This does not
authorize EM-6."** EM-6 remains **"Planned"** (the literal, and only,
status string associated with it anywhere in the repository —
`docs/MILESTONES.md:711`, `docs/ATHENA-EMR-HANDOFF.md:83`).

## 3. EMR roadmap reconstruction (dependency chain, source-grounded)

```
EM-0 (architecture/contract, Approved 2026-08-21)
 ↓
EM-1a (coverage audit — fail-closed, 0 checkpoints accepted, Approved 2026-08-21)
 ↓
EM-1r1→r5 (remediation: corporate actions, intraday reconstruction, cohort/quote
           hygiene, re-audit — all 9 checkpoints accepted 2026-08-26)
 ↓
EM-1b (label dataset + frozen chronological TRAIN/VALIDATION/CALIBRATION/
       FINAL_TEST partitions, Approved 2026-08-26)
 ↓
EM-1c (unconditional TRAIN-only base rates, minimum-support policy frozen
       n>=1000/k>=10, Approved 2026-08-27)
 ↓
EM-2 (cutoff-safe 28-field evidence contract, em2-evidence-v1, Approved 2026-08-27)
 ↓
EM-3 v1 (univariate TRAIN conditional analysis, 14,727 EXPLORATORY_CANDIDATE
         cells, Approved 2026-08-27)
 ↓
EM-4A (deterministic evidence score, frozen vote rule, Approved 2026-08-27)
 ↓
EM-4B (18 pooled logistic baselines, chronological CV, Approved 2026-08-27)
 ↓
EM-4C (real VALIDATION comparison — logistic beats deterministic 18/18 PR-AUC,
       owner GO 2026-08-28)
 ↓
EM-4D (Platt calibration, 162 cells, owner GO 2026-08-28)
 ↓
EM-4E (sealed FINAL_TEST evaluation, one-shot, replicates VALIDATION 18/18,
       owner GO 2026-08-28)
 ↓
EM-5 (replayable bulk-input live scanner, no UI, Approved/Closed 2026-09-01)
 ↓
EM-6 (?) — "Planned": per roadmap doc, "add EMR research UI only after
           scanner approval" — NOT owner-ratified as a formal contract
 ↓
EM-7 (Planned) — isolated shadow validation, OFF-vs-shadow comparison
 ↓
EM-8 (Planned) — research-only / continued shadow / retirement / new
                  integration ADR decision
```

This chain is reconstructed entirely from `IMPLEMENTATION_SUMMARY.md`
section headers/outcomes, `docs/MILESTONES.md`'s EMR track table, and
`docs/ATHENA-EMR-HANDOFF.md` — no step is invented or inferred from a
milestone number.

## 4. ADR-012 boundary (Accepted, 2026-08-21, `docs/adr/ADR-012-explosive-move-radar-boundary.md`)

- **"EMR will not contribute to or modify ATHENA scoring, confidence,
  risk, Decision, TradePlan, eligibility gates, or DarvaX output."** (line
  24) — "Any future influence on canonical ATHENA behavior requires a
  separate ADR."
- EMR owns its immutable records/repositories/config/manifests/artifacts
  in a **separate EMR SQLite database** (`db/emr.db`); **"It may not
  mutate canonical ATHENA tables."**
- **"Architecture tests prevent EMR imports into canonical scoring, risk,
  decision, and TradePlan modules"** — enforced by
  `tests/explosive_move/test_em5_isolation.py`.
- **"EM-8 requires owner approval and a separate ADR for canonical
  integration."**
- Explicit UI gate (§4, step 7): **"expose UI only after the scanner
  contract is stable."**
- Rejected alternative, directly relevant to EM-6 timing: **"Build the
  live dashboard before historical study — Rejected: a polished scanner
  without calibrated out-of-sample evidence would create false
  confidence."** (This alternative is now moot — calibrated out-of-sample
  evidence exists, from EM-4C/D/E.)

## 5. EM-0 result

Owner-approved 2026-08-21. Accepted ADR-012 and the EMR roadmap; froze the
TRAIN/VALIDATION/CALIBRATION/FINAL_TEST requirement, leakage controls,
minimum-support-cohort protection, and feasibility requirements before any
dataset work began. Architecture/documentation milestone; no classification
string.

## 6. EM-1 family result

- **EM-1a** (Approved 2026-08-21): coverage audit, deliberately fail-closed
  — **"all nine proposed checkpoints remain candidates and zero
  checkpoints are accepted."**
- **EM-1r1** (Approved 2026-08-21): split remediation into EM-1r2–r5, gated.
- **EM-1r2** (Approved 2026-08-21): official NSE corporate-action coverage
  materialized against a bounded survivor cohort.
- **EM-1r3** (Approved 2026-08-21, corrected 2026-08-26): canonical
  intraday session reconstruction, provider-free, no invented candles. A
  real provider-boundary defect was found mid-workstream and invalidated/
  re-run (`artifacts/research/em1r3-INVALIDATED-2026-08-24-provider-
  boundary-defect/`).
- **EM-1r4** (Approved 2026-08-22): survivor-cohort admission + quote-
  timestamp hygiene; never projects current membership backward as
  point-in-time history.
- **EM-1r5** (Approved 2026-08-26): re-audit unblocked EM-1b — **"Owner
  approved promoting all 9 [checkpoints] to accepted_ist — explicitly
  research-ready evidence only, never predictive value, calibration, or
  scanner fitness."** Adopted calculation-window-crossing (not fixed
  proximity window) for corporate-action contamination — avoided
  5,970–7,971 symbol-days of unnecessary exclusion.
- **EM-1b** (Approved 2026-08-26): deterministic label dataset + frozen
  chronological partitions (§14 below). **"No purge/embargo is required,
  and none was added"** (boundary-leakage analysis).
- **EM-1c** (Approved 2026-08-27): TRAIN-only unconditional base rates
  (TOUCH 1.08%, CLOSE 0.49%, OPEN_TO_HIGH 0.87%); froze minimum-support
  policy **n>=1,000 AND k>=10**. Explicitly: "No feature lift is claimed
  here."

## 7. EM-2 result

Approved 2026-08-27. Implemented the frozen 28-field evidence contract
(`em2-evidence-v1`: 15 SESSION_INVARIANT + 13 CHECKPOINT_DYNAMIC fields),
generated real TRAIN evidence (206,351 symbol-day rows, 1,857,159
checkpoint rows), enforced point-in-time cutoffs (mutation-tested).
TRAIN-only; VALIDATION/CALIBRATION/FINAL_TEST never opened at this stage.

## 8. EM-3 result

Approved 2026-08-27. Joined EM-2 evidence with EM-1b labels and EM-1c
baselines; computed univariate conditional lift per (feature, bin, family,
threshold, checkpoint, regime-stratum). **14,727 of 185,004 cells met the
frozen minimum-support policy and are labelled `EXPLORATORY_CANDIDATE`**
— never `VALIDATED_SIGNAL` (confirmed: that value does not exist anywhere
in the codebase; `SupportLabel` has exactly `EXPLORATORY_CANDIDATE`,
`INSUFFICIENT_SUPPORT`, `MISSINGNESS_DIAGNOSTIC`).

## 9. EM-4/4A/4C result

- **EM-4 (env-unblock + EM-4C scaffolding)** (2026-08-27): clean-room
  Python 3.13/NumPy/scikit-learn reconstruction; built
  `em4c_ranking.py`/`em4c_metrics.py`/`em4c_aggregation.py`/`em4c_report.py`.
  2,485 tests passed.
- **EM-4A** (folded into the EM-4B milestone entry, no dedicated header;
  defined in `src/athena/explosive_move/deterministic_score.py:1-14`):
  **a plain, predeclared vote over EM-3's frozen `EXPLORATORY_CANDIDATE`
  register — never a fitted/weighted model.** Each admitted (feature, bin)
  contributes exactly +1 or −1; `score = (positive_votes -
  negative_votes) / total_votes`, range [−1, +1], `UNKNOWN` when
  `total_votes == 0`.
- **EM-4B** (Approved 2026-08-27): 18 pooled logistic baselines (3
  families × 6 thresholds), chronological/session-grouped/expanding-window
  CV. All 18 converged, deterministic-replay-verified. `C=0.01` chosen for
  13/18. No `random_state` needed — "no randomness ... for this
  L2-penalized binary case" (confirmed via source comment,
  `em4b_model.py:56`).
- **EM-4C** (owner GO 2026-08-28): real VALIDATION comparison (518
  instruments, 85 sessions, 380,232 rows) — **"the logistic model beats
  the deterministic model on pooled PR-AUC in 18 of 18 real
  combinations."**

## 10. EM-5 result

Approved/Closed 2026-09-01. Replayable bulk-input live scanner
(`explosive_move/live/`), no UI, no per-symbol provider calls except one
authorized checkpoint-price seam. Track B live capture (Tuesday
2026-09-01): 9 frozen symbols × 9 frozen checkpoints, 81/81 raw files
captured, 1,768 raw candles, **0 off-grid observations**. Corrected
classification: **`NO_OFF_GRID_PROVISIONAL_OBSERVED`**. Final production
canary (contract §14): **518/518 mature instruments, 9,324/9,324
all-fields-known, 0 provider/network calls, deterministic replay, PASS.**
Final validation: 2,956 passed, 1 skipped, 1 warning, Ruff clean, `git
diff --check` clean. All numbers independently confirmed against
`docs/research/EM-5-TRACK-B-LIVE-M5-CAPTURE-2026-09-01.md` — no
discrepancy from the owner's own stated figures.

## 11. Existing EM-6 references (full audit)

Every literal `EM-6`/`EM6`/`EM_6` match in the repository was searched.
Only the hyphenated `EM-6` form is ever used.

**Roadmap-intent content (the only substantive EM-6 spec anywhere):**
`docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md:194-196` — **"### EM-6
- Market Intelligence UI. If EM-5 is approved, add `Explosive Move Radar`
with permanent Experimental labelling, freshness, checkpoint, calibration
context, evidence, missing coverage, and no trade-authorizing language."**
This is conditionally-framed ("If EM-5 is approved") roadmap author intent
— it never went through the milestone review cycle that closed EM-0–EM-5.

**Firm, currently-binding procedural gates (not content, just "not yet"):**
- `docs/ATHENA-EMR-HANDOFF.md:43`: **"EM-5 is closed. This does not
  authorize EM-6."**
- `docs/ATHENA-EMR-HANDOFF.md:94`: **"Do not start EM-6 without a fresh,
  explicit owner instruction."**
- `docs/ATHENA-EMR-HANDOFF.md:126`: "No production recommendation,
  canonical score input, or UI may be built before EM-6 is explicitly
  authorized."
- `docs/MILESTONES.md:711`: `| EM-6 | Add the EMR research UI only after
  scanner approval | Planned |` — status literally **"Planned."**
- `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md:14`: "No UI (EM-6), no
  shadow validation (EM-7), no canonical integration (EM-8)" — confirms
  EM-6/7/8 are three distinct, sequential, non-overlapping scopes: UI,
  then shadow validation, then integration decision.
- `docs/design/EM-5-LIVE-SCANNER-CONTRACT.md:845-863` (§17 "No UI"): EM-5
  deliberately built `top_candidates(...)`/`top_touch_10_candidates(...)`
  plain-Python query functions over `emr_candidates`, **"callable by a
  future EM-6 without any HTTP route, dashboard change, or
  index.html/DASHBOARD_JS_PARTS touch"** — a technical seam left ready for
  EM-6, not an authorization.
- ADR-012 itself never names EM-6 by number (confirmed: zero hits).
- `IMPLEMENTATION_SUMMARY.md` (38 matches across many historical entries,
  all in the pattern "EM-6/7/8 not started" or "do not start EM-6 without
  fresh owner authorization" — several older entries predate EM-5's actual
  2026-09-01 closure and describe EM-6 as "blocked pending EM-5," now
  superseded).
- The ID-track's own docs (`docs/ATHENA-ID-TRACK-HANDOFF.md`,
  `docs/MILESTONES.md` ID-6 rows) reference EM-6 only as a cross-track
  out-of-scope boundary marker ("...ID-7, EM-6, EMR, DarvaX...") — never
  as ID-track content.

**Classification: DOCUMENTED ROADMAP INTENT for EM-6's shape (UI); FROZEN
procedural gate that it cannot start without fresh explicit authorization;
no OWNER-APPROVED contract exists yet.**

## 12. Unresolved scientific question after EM-5

There is, per repository evidence, **no unresolved scientific/modeling
question left for EM-6 to answer** — EM-4B (fitting), EM-4C (held-out
comparison), EM-4D (calibration), and EM-4E (sealed FINAL_TEST evaluation,
GO) already closed the model-selection/evaluation arc, and EM-5 closed the
live-replay/data-integrity arc. The next genuinely open scientific
question — **does the calibrated model's live/shadow behavior match its
FINAL_TEST behavior over time** — is explicitly EM-7's scope ("isolated
shadow validation, OFF-vs-shadow performance comparison"), not EM-6's.
EM-6, per the one existing roadmap description, is a **presentation/UI**
milestone: expose what already exists (ranked candidates, calibrated
probability, evidence, calibration context, freshness) to a human reader,
nothing more.

## 13. Current EMR implementation surface (production/research/test/dormant)

40 `.py` files under `src/athena/explosive_move/` (23 top-level research
modules + 12 `live/` + 2 `store/` + 3 `__init__.py`), plus 15 orchestration
scripts under `src/athena/data/em*.py` that import from the package
one-way (confirmed: no non-EMR canonical module imports
`athena.explosive_move`; enforced by `test_em5_isolation.py`).

- **PRODUCTION-shaped but not yet wired to any trigger**: all of
  `explosive_move/live/*.py` (`scanner.py::run_scan_cycle`,
  `canary_gate.py`, `eligibility.py`, `evidence_assembly.py`,
  `regime_source.py`, `checkpoint_reference_price.py`,
  `frozen_inference.py`, `deterministic_scoring.py`, `explanation.py`,
  `ranking.py`, `state_machine.py`, `market_data_port.py`). Deterministic,
  DB-writing (`db/emr.db`), frozen-model-driven — but `run_scan_cycle` has
  **no caller outside the package itself** (`canary_gate.py`) and tests.
  Not called from `cli.py`, not called from any scheduler/cron script
  found in the repo. Invoked manually/operator-driven today (e.g. via
  `em5_track_b_capture_cli.py`'s two-phase capture flow).
- **RESEARCH-ONLY, frozen functions reused unmodified by the live path**:
  `event_labels.py`, `session_invariant_evidence.py`,
  `checkpoint_dynamic_evidence.py`, `regime_replay.py`,
  `em4b_preprocessing.py`, `em4c_scoring.py`, `em4c_ranking.py`,
  `em4d_calibration.py`, `deterministic_score.py`, `evidence_contract.py`,
  `evidence_values.py`, `contracts.py`.
- **RESEARCH-ONLY, never touched by live**: `partitions.py`,
  `corporate_action_coverage.py`, `corporate_action_boundary.py`,
  `cohort_admission.py`, `intraday_reconstruction.py`,
  `em1r2_materialize.py`, `wilson_interval.py`, `conditional_analysis.py`,
  `em4_config.py`, `em4b_model.py`, `em4c_metrics.py`,
  `em4c_aggregation.py`, `em4c_report.py`, `forward_excursion.py`.
- **TEST-ONLY**: 53 test files (`tests/explosive_move/`, 39 files;
  `tests/data_layer/test_em*`, 14 files) — including two isolation-
  enforcement tests critical to EM-6: `test_em5_isolation.py` (import-
  direction/no-canonical-mutation) and `test_em5_no_model_learning.py`
  (asserts no numpy/sklearn in the inference chain).
- **DORMANT**: nothing orphaned found inside the package; the closest is
  `explosive_move/live/` as a whole relative to production triggering
  (see above), and one invalidated artifact directory
  (`artifacts/research/em1r3-INVALIDATED-2026-08-24-provider-boundary-defect/`).

**EM-6 must consume `explosive_move/store/` (`db/emr.db`) and the plain
query functions EM-5 built for it — never invoke `run_scan_cycle` itself,
never write to `db/emr.db`, and never gain a scheduler/production
trigger of its own** (that would silently become an EM-6+EM-production
milestone, not UI-only).

## 14. EM-4C capability audit (do not duplicate)

| Capability | Present? | Evidence |
|---|---|---|
| Chronological session-grouped TRAIN CV folds | Present, but in `em4_config.py`/`em4b_model.py`, not the EM-4C scaffolding itself | `em4_config.py:36-51` `TEMPORAL_CV_FOLDS` |
| PR-AUC computation | **YES** | `em4c_metrics.py:31` `average_precision()` |
| Candidate models (fit/score) | Fitting: NO (that's `em4b_model.py`). Scoring a frozen model: YES | `em4c_scoring.py` — pure dot-product+sigmoid, byte-identical to sklearn `predict_proba` |
| Calibration (fit) | NO — that's `em4d_calibration.py` (EM-4D) | — |
| Calibration (diagnostic/reliability) | YES | `em4c_metrics.py:72-80` `CalibrationBin`/`calibration_bins()` |
| Held-out evaluation | YES | `em4c_validation_evaluation.py` opened real VALIDATION |
| Deterministic artifacts | YES | `em4c_report.py:34` `CrossSectionResult`, `:61` `build_evaluation_manifest()` (sha256 fingerprinted) |
| Metric comparison (det. vs logistic vs base rate) | YES | `em4c_ranking.py:69` `base_rate()` |
| Baseline comparison | YES | same as above |
| Threshold-independent metrics | YES | PR-AUC, Brier score (`em4c_metrics.py:59`) |
| Thresholded operating points | YES | `em4c_ranking.py:79` `precision_at_k()`, `:100` `lift_at_k()` |

**EM-6 must reuse this scaffolding for any metric/evidence display it
needs — never reimplement PR-AUC, calibration bins, or ranking.**

## 15. Model-fitting status — exact answers

- Has any predictive EMR model actually been trained? **YES** — EM-4B, 18
  logistic models, all converged.
- Has hyperparameter/model selection occurred? **YES** — `C`
  (regularization) selected per model via the frozen chronological CV,
  PR-AUC as sole selection metric.
- Has calibration been fitted? **YES** — EM-4D, Platt scaling, 162 cells
  (135 checkpoint-specific, 27 pooled fallback, 0 insufficient-support).
- Has an untouched holdout been evaluated? **YES, once** — EM-4E,
  FINAL_TEST, one-shot, sealed policy, GO decision recorded 2026-08-28.
  See §26 for the exact "sealed" semantics.
- Has walk-forward evaluation occurred? **NOT YET PERFORMED** — only a
  single chronological TRAIN/VALIDATION/CALIBRATION/FINAL_TEST split
  exists; no rolling/expanding walk-forward re-evaluation over time has
  been done.
- Has live shadow model inference occurred? **NOT YET PERFORMED** — EM-5
  built the replay/live-scan capability and ran the production canary
  (replaying one already-elapsed real session, zero provider calls), but
  no continuous live-shadow run against genuinely new, arriving-in-real-
  time market data has occurred. That is EM-7's explicit scope.
- Has any model artifact been promoted? **YES** — `config/emr/frozen_models/v1/`
  (EM-3 register, 18 EM-4B logistic models, 18 EM-4D calibration
  artifacts), integrity-verified via `FROZEN_MODEL_MANIFEST.json`, loaded
  unmodified by `live/frozen_inference.py`.
- Has any threshold been selected? **NO** — confirmed via source: the
  live scanner's `ScannerState` machine (`live/state_machine.py`) is
  **"purely rank/eligibility-driven — no FINAL_TEST-derived probability
  threshold anywhere"** (rank cutoffs 20/10/5, a shortlist-size
  configuration, not a statistical threshold). No probability cutoff,
  top-K alert threshold, or precision/recall target has been chosen
  anywhere in the codebase.
- Has any profitability claim been made? **NO** — EM-4C/D/E measure
  PR-AUC/Precision@K/Lift@K/calibration against a predictive label
  (explosive-move touch/close/open-to-high), never a trading return,
  entry price, or risk/reward figure.

## 16-19. Calibration / holdout / walk-forward / live-shadow status

See §15 — calibration: DONE (EM-4D). Holdout: DONE ONCE, sealed (EM-4E).
Walk-forward: NOT YET PERFORMED. Live-shadow: NOT YET PERFORMED (EM-7
scope).

## 20. Frozen label/outcome contract

Source: `src/athena/explosive_move/event_labels.py`,
`src/athena/explosive_move/contracts.py`, `em4_config.py` (MFE/MAE/TTT).

- **Event families**: TOUCH, CLOSE, OPEN_TO_HIGH.
- **Thresholds**: 5/8/10/12/15/20% (6 thresholds × 3 families = 18
  combinations, matching the 18 EM-4B/4D models).
- **`threshold_price`**: reference-price-relative, per-family rule
  (frozen in `config/explosive_move.json`).
- **Forward-candle boundary**: strict candle-observability — no
  look-ahead; a checkpoint-conditioned forward window within the same
  regular session.
- **MFE** (Max Favorable Excursion, %) = `max(high over forward candles) /
  reference_price - 1, x100`.
- **MAE** (Max Adverse Excursion, %) = `min(low over forward candles) /
  reference_price - 1, x100`.
- **time_to_target** (minutes) = first forward candle whose high >=
  threshold_price, minus checkpoint instant; computed only for
  TOUCH/OPEN_TO_HIGH positive cases; `NOT_APPLICABLE` for CLOSE.
- **Censored/unresolved cases**: `ALREADY_OCCURRED` outcome class exists
  in the label contract for cases where the event condition was already
  true before the checkpoint (excluded, not silently labelled negative).
- **Session boundary**: same regular session only, no overnight/next-day
  carry.
- **Exclusion rules**: corporate-action calculation-window-crossing
  (EM-1r5's adopted rule), survivor-cohort admission (EM-1r4), corrupted/
  off-grid intraday data (EM-1r3 quarantine).

**EM-6 is NOT allowed to change any of these — default NO, per
instruction, and no owner-approved documentation authorizes a change.**
EM-6 only displays already-computed label/evidence/score outputs.

## 21. Frozen feature contract

Source: `src/athena/explosive_move/evidence_contract.py`,
`session_invariant_evidence.py`, `checkpoint_dynamic_evidence.py`,
`conditional_analysis.py`.

- **28-field `em2-evidence-v1` contract**: 15 `SESSION_INVARIANT` fields
  (13 PRIOR_HISTORY + 2 SESSION_OPEN_CONTEXT, computed once per
  symbol/session) + 13 `CHECKPOINT_DYNAMIC` fields (per symbol/session/
  checkpoint).
- **Known/unknown semantics**: every evidence field is an `EvidenceValue`
  — a real value XOR an explicit `unknown_reason`, never a silent `None`.
- **Feature availability timing**: point-in-time cutoff-safe by
  construction (mutation-tested in EM-2); no field ever reads
  after-the-fact data.
- **Exploratory-only fields**: EM-3's `conditional_analysis.py` bins each
  feature and labels the resulting (feature, bin) cell
  `EXPLORATORY_CANDIDATE` / `INSUFFICIENT_SUPPORT` /
  `MISSINGNESS_DIAGNOSTIC` — 14,727 of 185,004 cells reached
  `EXPLORATORY_CANDIDATE`.
- **Production-available fields**: the same 28 fields are recomputed live
  by `live/evidence_assembly.py`, calling the frozen EM-2 modules
  unmodified, with one documented, owner-accepted substitution (a
  synthetic `Candle` for the not-yet-closed checkpoint candle — "live
  checkpoint-price substitution").
- **Leakage protections**: cutoff-safe evidence (EM-2), point-in-time
  regime replay (EM-1c/`regime_replay.py`, T-1 cutoff enforced),
  chronological non-overlapping partitions with no per-row randomness
  (`partitions.py`).
- **Features rejected/deferred**: none found rejected outright; EM-3's
  `INSUFFICIENT_SUPPORT`/`MISSINGNESS_DIAGNOSTIC` labels are the
  documented "not (yet) usable" classifications, not rejections.

**EM-6 must not add new features during discovery or implementation** —
confirmed no evidence anywhere authorizes this, and it is out of scope
for a UI milestone regardless.

## 22. Available dataset characterization

- **TRAIN**: 440 sessions (2023-08-14 → 2025-05-31, 59.2%), 206,351
  symbol-day rows, 1,857,159 checkpoint rows (EM-2).
- **VALIDATION**: 85 sessions (2025-06-01 → 2025-09-30, 11.4%), 518
  instruments, 380,232 rows (opened once, EM-4C).
- **CALIBRATION**: 61 sessions (2025-10-01 → 2025-12-31, 8.2%), 279,495
  rows (opened once, EM-4D).
- **FINAL_TEST**: 157 sessions (2026-01-01 → 2026-08-21, 21.1%), 702,702
  checkpoint rows (opened exactly once, EM-4E, sealed policy — see §26).
- **743 real trading sessions total**, strictly chronological, contiguous,
  non-overlapping, whole-session partition assignment — no per-row or
  per-symbol randomness (`partitions.py`, import-time validated).
- **TRAIN base rates** (unconditional, EM-1c): TOUCH 1.08% (n=205,303,
  k=2,226), CLOSE 0.49%, OPEN_TO_HIGH 0.87% — genuine, heavy class
  imbalance.
- **Source/provenance**: settled historical intraday data, provider-free
  reconstruction (EM-1r3), official-NSE corporate-action authority
  (EM-1r2) — not live/provisional.
- **Frozen partition**: yes, exactly as above, module-enforced.

EM-6 needs no new dataset — it consumes `db/emr.db`'s already-persisted
scan/candidate/transition records (written by EM-5's live scanner runs),
not the TRAIN/VALIDATION/CALIBRATION/FINAL_TEST research datasets
directly.

## 23. Leakage audit

- **Future-candle leakage**: protected — `event_labels.py`'s strict
  candle-observability boundary, EM-2's cutoff-safe evidence, mutation-
  tested.
- **Same-session future knowledge**: protected — checkpoint-conditioned
  forward windows only, no look-ahead within EM-2/EM-4 fields.
- **Candidate-selection leakage**: protected — EM-1r4's survivor-cohort
  admission never projects current membership backward as point-in-time
  history.
- **Label leakage**: protected — MFE/MAE/time-to-target formulas operate
  strictly forward from the checkpoint instant.
- **Cross-fold session leakage**: protected — CV folds are session-grouped
  (a whole session always stays in one fold-role), chronological/
  expanding-window, never random/shuffled (`em4_config.py`).
- **Calibration leakage**: protected — Platt scaling fit on CALIBRATION
  only, never TRAIN/VALIDATION, using frozen EM-4B logits as input.
- **Test-set leakage**: protected — FINAL_TEST opened exactly once, under
  an explicit owner-approved one-shot policy; EM-4E's own closing
  instruction: "FINAL_TEST must not be read again regardless of the
  decision made here."
- **Duplicate symbol/session observations across folds**: not separately
  audited by any research report found; session-grouping structurally
  prevents a session's rows from splitting across folds, which is the
  primary defense.
- **Point-in-time feature availability**: protected — EM-2's own mutation
  tests plus `regime_replay.py`'s T-1 cutoff enforcement.

**No leakage gap requiring a fix was found. EM-6 introduces no new
leakage surface — it is read-only presentation of already-computed,
already-leakage-audited outputs.**

## 24. Frozen model-selection rules (preserved, not decided here)

- Chronological, session-grouped, expanding-window TRAIN-internal CV
  folds — base window = first 220 of 440 TRAIN sessions, remaining 220
  split into 4 expanding-eval blocks of 55 sessions each.
- **PR-AUC (average precision), averaged across the 4 folds, is the sole
  CV-selection metric** — applied identically across all 18 models, never
  swapped.
- **Platt minimum-support policy**: reuses EM-1c's frozen policy exactly
  (`n>=1000` eligible, `k>=10` positive); isotonic only ever considered
  later if support clears a materially higher bar (`k>=50`), never used
  automatically.
- No `random_state`/seed needed — the L2-penalized binary logistic case
  is deterministic by construction (confirmed in source comment).
- Tie-breaking (EM-4C ranking): score descending, `instrument_id`
  ascending — deterministic.

These are all **already frozen by EM-4** and out of scope for EM-6 to
revisit.

## 25. Unresolved model-selection rules — flagged as OWNER DECISIONS

None found. Every model-selection rule that exists is already frozen; EM-6
(as a UI milestone) does not introduce new model-selection questions. See
§32 for the actual owner decisions this discovery surfaces (all about
EM-6's own scope, not modeling).

## 26. FINAL_TEST / sealed-data status

`partitions.py`'s own docstring defines "sealed" precisely: **"dataset-
integrity checks (row counts, partition membership, replay verification)
may inspect it freely; model-performance results may not be used for any
development decision before the approved final evaluation gate."**
FINAL_TEST **has already been opened once**, under that explicit
Owner-approved one-shot policy (EM-4E, 2026-08-28) — it is not untouched.
"Remains sealed" (repeated in later entries) means **must never be read
again**, not "was never inspected." **EM-6 must not re-read FINAL_TEST
outcomes under any circumstance** — it only needs already-computed,
already-published EM-4E summary results (PR-AUC comparison, GO decision)
if it displays historical model performance at all, and even that should
prefer citing the frozen EM-4E report rather than touching the dataset.

## 27. EM-5→EM-6 dependency

EM-5 had to finish before EM-6 because EM-6's own roadmap description is
explicitly conditional: **"If EM-5 is approved, add..."** — EM-6 exposes
the live scanner's *output* (ranked candidates, scores, evidence), which
did not exist as a running, replay-verified, integrity-checked system
until EM-5 closed. `NO_OFF_GRID_PROVISIONAL_OBSERVED` and the production
canary PASS remove the specific blocker that live current-session data
might be structurally unstable/off-grid before EM-6 displays it — they do
**not** prove the underlying model is profitable, do not authorize
canonical integration, and do not by themselves authorize starting EM-6
(per `docs/ATHENA-EMR-HANDOFF.md:43`, explicitly). EM-5's closure removes
a **data-integrity** blocker, not a **scope-authorization** blocker; the
latter requires the owner's own fresh instruction, which this document is
now enabling by proposing a precise contract to approve.

## 28. ID-track isolation confirmation

The ID-track's current state
(`REPLAY_SOUND_SHADOW_EVIDENCE_STILL_ACCUMULATING`) has **zero bearing**
on EM-6 methodology. Confirmed via source: `grep`-verified zero references
to `explosive_move` anywhere in `src/athena/session/`,
`src/athena/intraday/`, or the ID-track's own modified repository/
workflow files; EMR's own code never calls any ID-track repository
method. `db/emr.db` and `db/athena.db` are separate files. EM-6 must not
use EntryQualification state/finality/reason-codes, ID-6 replay/shadow
results, or ID-7 future entry semantics — none of this discovery has done
so, and the recommended EM-6 contract (§30) has no dependency on the
ID-track whatsoever.

## 29. DarvaX isolation confirmation

No coupling found or proposed. EM-6 must not use DarvaX boxes as EMR
labels, use EMR probability as DarvaX confirmation, combine scores, share
thresholds, or modify DarvaX code. `db/emr.db` remains separate from
`db/darvax.db`; shared generic market-data infrastructure (candles) is
the only architecturally-shared surface, unchanged by this discovery.

## 30. Proposed EM-6 milestone shape

**Recommendation: G. OTHER — read-only research-UI/presentation work.**
Not A (model fitting — done, EM-4B), not B (calibration — done, EM-4D),
not C (holdout evaluation — done once, sealed, EM-4E), not D (walk-forward
— genuinely unperformed, but not documented anywhere as EM-6's job), not
E (live shadow — genuinely unperformed, but explicitly EM-7's documented
job, not EM-6's), not F (data expansion — no evidence anywhere that more
data is required before UI work; the existing frozen dataset and live
`db/emr.db` records are sufficient for a UI to display). This
recommendation rests on: the one existing roadmap description naming EM-6
explicitly as UI; `EM-5-LIVE-SCANNER-CONTRACT.md`'s own explicit sequencing
("No UI (EM-6), no shadow validation (EM-7), no canonical integration
(EM-8)"); and the technical seam (`top_candidates`/`top_touch_10_candidates`)
EM-5 already built specifically for EM-6 to call.

## 31. Proposed EM-6 sub-milestones (if EM-6 is authorized)

Not implemented here — proposed for owner review only.

**EM-6A — Read-only query/service layer (no HTTP, no dashboard)**
- Objective: expose `top_candidates(...)`/`top_touch_10_candidates(...)`
  (already built in EM-5) as a documented, tested, stable Python API
  surface that a future UI can call; add any additional read-only
  aggregation needed (e.g. "latest scan per checkpoint," "candidate
  history for one instrument") strictly over `db/emr.db`.
- Inputs: `db/emr.db` (read-only), the EM-5 query functions.
- Allowed changes: new pure read functions in `explosive_move/live/` or a
  new `explosive_move/live/query.py`-style module; new tests.
- Forbidden changes: any write to `db/emr.db`, any call to
  `run_scan_cycle`, any provider/network call, any canonical ATHENA
  import, any API route or dashboard file.
- Evidence required: deterministic query results against fixture data;
  confirmed read-only (no mutation) against a temp DB.
- Exit criteria: a stable, tested, documented function surface.
- Owner decision required afterward: whether to proceed to EM-6B.

**EM-6B — Dashboard/UI surface**
- Objective: render EM-6A's query results as a Market Intelligence
  dashboard tab, permanently labelled "Experimental," showing freshness,
  checkpoint, calibration context, evidence, missing-coverage — no
  trade-authorizing language anywhere.
- Inputs: EM-6A's query functions only.
- Allowed changes: new dashboard JS/CSS files, a new API route mounted
  read-only (mirroring DarvaX's own `api/darvax_mount.py` isolation
  pattern, per ADR-012), new `index.html`/`DASHBOARD_JS_PARTS` entries.
- Forbidden changes: anything in `explosive_move/live/scanner.py` or
  below; any canonical Scoring/Decision/TradePlan/API surface; any write
  path from the dashboard back into `db/emr.db`.
- Evidence required: manual/browser verification (per this repo's UI
  verification convention), no regression in existing dashboard tests.
- Exit criteria: a working, isolated, read-only "Experimental" tab.
- Owner decision required afterward: whether EM-6 is complete, or EM-7
  (shadow validation) is next.

This split is proposed because §17 (ADR-012) explicitly gates UI behind
"the scanner contract is stable," and separating "can we safely query
this data" from "should we show it to a human" lets the owner approve the
lower-risk, no-product-surface half first if preferred. If the owner
judges EM-6 small enough for one controlled step, this split is not
required.

## 32. Owner decisions required

Only genuine, source-unanswered decisions:

1. **Confirm or redirect EM-6's scope.** Is EM-6 = the documented UI
   milestone (§11/§30), or should the owner instead authorize something
   else first (e.g. EM-7's shadow validation, or a walk-forward
   re-evaluation) ahead of any UI work? Repository evidence supports UI
   as the documented next step, but it was never owner-ratified as a
   formal contract — this discovery does not manufacture that
   ratification.
2. **Single milestone or the EM-6A/EM-6B split (§31)?**
3. **If UI is confirmed: exact dashboard placement and API-mount pattern**
   (mirror DarvaX's `api/darvax_mount.py` isolation seam, or something
   else?) — a genuine open implementation-design choice, not yet decided
   anywhere.
4. **Whether any operational trigger for `run_scan_cycle` (scheduler/cron)
   is needed before or alongside EM-6**, since the live scanner currently
   has no production trigger — displaying "live" data in a UI implies the
   scanner needs to actually run on a schedule, which is arguably a
   separate operational decision from the UI itself and is not addressed
   by any existing document.

## 33. Risk register

| Risk | Classification | Basis |
|---|---|---|
| Overfitting | CONTROLLED | Chronological CV, held-out VALIDATION/CALIBRATION/FINAL_TEST all independently confirm the logistic model's advantage 18/18 — no single-split overfitting pattern found. |
| Low positive support | CONTROLLED | Minimum-support policy (n>=1000, k>=10) enforced at EM-1c/EM-3/EM-4D; 0 insufficient-support Platt cells. |
| Calibration support | CONTROLLED | 135/162 cells checkpoint-specific, 27/162 pooled fallback, 0 insufficient, 0 unstable (EM-4D). |
| Regime concentration | DEFERRED | EM-1c stratifies base rates by regime, but no EM-6-relevant regime-concentration study was found for the live scanner's actual candidate stream — not blocking for a UI milestone, worth EM-7 attention. |
| Symbol concentration | DEFERRED | Same — not audited for live output composition; not blocking for UI. |
| Leakage | CONTROLLED | Full leakage audit (§23) found protections at every stage, no gap. |
| Unstable features | CONTROLLED | EM-2's `EvidenceValue`/`unknown_reason` contract + EM-3's `MISSINGNESS_DIAGNOSTIC` label make instability explicit, never silently imputed to look stable. |
| Provisional-vs-settled differences | CONTROLLED (for EM-5/current scope) | Track B.1's `NO_OFF_GRID_PROVISIONAL_OBSERVED` classification and the production canary both directly address this for EM-5's live-scan path; EM-6 inherits this evidence unchanged since it only displays EM-5's outputs. |
| Class imbalance | CONTROLLED | PR-AUC (not accuracy/ROC-AUC) chosen specifically for this reason; base rates as low as 0.49% handled throughout. |
| Multiple-comparison bias | CONTROLLED | 18 (family×threshold) models evaluated identically and consistently across VALIDATION and FINAL_TEST — the 18/18 sweep result itself is evidence against cherry-picking, and no threshold/model selection occurred after seeing FINAL_TEST. |
| FINAL_TEST contamination | BLOCKING (procedural, not evidentiary) | FINAL_TEST is sealed — any code touching it again would be a genuine violation. EM-6, as a UI-only milestone consuming `db/emr.db` records, has no reason to touch it; this must be enforced as an absolute constraint on implementation, not merely "controlled." |
| Research-to-production coupling | CONTROLLED, requires ongoing vigilance | ADR-012 isolation is architecture-test-enforced (`test_em5_isolation.py`); EM-6 must extend the same enforcement to any new dashboard/API code it adds. |

## 34. Determinism requirements to freeze before any EM-6 fitting-adjacent
work (none currently anticipated, but recorded for completeness)

EM-6 as scoped (UI) performs no fitting, so no new determinism controls
are needed. If EM-6A/6B ever needs to aggregate across scan runs (e.g.
"today's top candidates across all checkpoints"), that aggregation
ordering must be explicitly deterministic (sort key + tie-break), mirroring
`em4c_ranking.py`'s existing score-desc/instrument_id-asc convention —
reuse it, do not invent a new one.

## 35. Test strategy (for a future EM-6 implementation, not written here)

- EM-6A: deterministic query-function tests over fixture `db/emr.db` data
  (empty DB, single scan, multiple scans/checkpoints); read-only-never-
  mutates proof (mtime unchanged); no provider/network call proof (source
  grep, matching the ID-6E harness convention already used elsewhere in
  this repo).
- EM-6B: standard dashboard-tab UI verification per this repo's existing
  convention (start the dev server, verify via browser, check no
  regression in existing tabs) — not a new automated-test category.
- Both: an architecture test extending `test_em5_isolation.py`'s pattern
  to assert the new EM-6 code never imports canonical Scoring/Decision/
  Risk/TradePlan modules and never writes to `db/emr.db` or `db/athena.db`.

## 36. Provider/data requirement

None. EM-6 (as scoped) needs no new provider data — it reads
already-persisted `db/emr.db` records written by EM-5's own (currently
manually-triggered) scan cycles. If the owner decides EM-6 also needs a
production scheduler trigger for `run_scan_cycle` (§32 item 4), that is a
separate, explicit decision — this discovery does not recommend starting
a new capture campaign.

## 37. Recommendation

Bring this document to the owner for the decisions in §32. If confirmed,
authorize EM-6A first (read-only query layer, lowest risk, no product
surface) as the narrowest scientifically/architecturally valid next
controlled step, holding EM-6B (actual dashboard) for a second, separate
review — consistent with ADR-012's own "expose UI only after the scanner
contract is stable" sequencing and this repo's general one-milestone-at-
a-time discipline.
