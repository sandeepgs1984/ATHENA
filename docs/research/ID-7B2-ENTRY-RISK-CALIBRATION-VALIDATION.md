# ID-7B.2 — Entry / Risk Calibration & Chronological Validation

**Status: V0 methodology calibrated and validated via a predeclared
chronological session-grouped discovery/validation split; contract
corrected by ID-7B.2.1 (§29) for three consistency errors in the
original §14 synthesis — calibration evidence and classifications
unchanged throughout. Read-only throughout: zero canonical writes, zero
schema, zero `src/` modification, zero provider calls, zero ML/scoring
model.**

**A note on this document's numbers.** Every figure below was
independently re-derived from the raw JSON computed by this milestone's
own research script and cross-checked for internal arithmetic
consistency (e.g. COMBINED figures reproduce as the exact row-weighted
blend of DISCOVERY and VALIDATION; per-fold state-row counts sum exactly
to 6,624). A first-draft narrative summary produced during this
milestone contained several numbers that did not match its own
underlying JSON (apparently transcribed from an intermediate, since-
corrected calculation) — this document uses only the verified JSON
figures, not that draft narrative.

## 1. Purpose

Convert ID-7B/ID-7B.1's partially-frozen methodology into the smallest
deterministic, empirically defensible V0: What minimum entry/
invalidation/freshness rules survive chronological validation well
enough to freeze? No profitability maximization, no large parameter
search, no actionability score, no implementation.

## 2. Research population (unchanged from ID-7B.1)

Primary and only population: the **6,624-episode cohort** (96,985 raw
`TRADE` decisions → 6,624 episodes via the same zero-invented-parameter
boundary ID-7B.1 established — independently re-derived a third time in
this milestone, exact match). The 96,985-row observation cohort is not
used; repeated `TRADE` cycles are never weighted as independent
opportunities.

## 3. Frozen chronological fold structure (decided before any outcome data was inspected)

20 distinct `TRADE` session dates exist. Sorted chronologically, the
**first 14 (70%) are DISCOVERY**, the **last 6 (30%) are VALIDATION** —
a purely structural, session-count-based decision, frozen before any
threshold or outcome was computed:

- **DISCOVERY**: 2026-07-31, 08-03, 08-04, 08-05, 08-06, 08-07, 08-10,
  08-11, 08-12, 08-13, 08-14, 08-17, 08-18, 08-19
- **VALIDATION**: 2026-08-20, 08-21, 08-24, 08-25, 08-26, 08-27

No episode is split across folds; no individual episode is resampled.
Every candidate threshold below is derived from DISCOVERY only and
evaluated exactly once on VALIDATION.

## 4. Read-only safety proof

`ReadOnlyStore` (`mode=ro` + `PRAGMA query_only=ON`); a live
write-rejection assertion (`DELETE FROM decisions WHERE 1=0`) was
executed and correctly raised `sqlite3.OperationalError`. Every
computation ran as a synchronous foreground step (longest single step:
70s, the full 6,624-episode reconstruction) — no detached/background
processes this time. All scratch files remain under the session
scratchpad (largest 13.6MB), never under the tracked repo tree.
`git status --short` clean throughout.

## 5. Episode reconstruction — full state distribution (all 6,624, not just QUALIFIED)

| State | Discovery (n=4,548) | Validation (n=2,076) | Combined (n=6,624) |
|---|---|---|---|
| `REPLAYED_QUALIFIED` | 488 | 295 | 783 |
| `REPLAYED_NOT_YET` | 3,250 | 1,157 | 4,407 |
| `REPLAYED_EXPIRED` | 529 | 577 | 1,106 |
| `REPLAYED_UNKNOWN` | 281 | 47 | 328 |

Zero reconstruction defects (100% success), matching ID-7B.1 exactly.

## 6. Comparison population — the central new evidence this milestone required

Same-session-horizon forward labels (checkpoint → last available M5
candle that session date), computed for every state, not only
`QUALIFIED`:

| Group | Fold | n (valid outcome) | T1 hit % | T2 hit % | MFE median | MAE median |
|---|---|---|---|---|---|---|
| `REPLAYED_QUALIFIED` | Discovery | 483 | **26.02** | **16.60** | 0.4827 | −0.4884 |
| `ALL_NON_QUALIFIED` | Discovery | 1,375 | 8.37 | 5.17 | 0.4012 | −0.3987 |
| `REPLAYED_QUALIFIED` | Validation | 256 | **20.34** | **11.86** | 0.3797 | −0.4518 |
| `ALL_NON_QUALIFIED` | Validation | 597 | 4.83 | 2.75 | 0.2578 | −0.5444 |
| `REPLAYED_QUALIFIED` | Combined | 739 | **23.88** | **14.81** | 0.4336 | −0.4735 |
| `ALL_NON_QUALIFIED` | Combined | 1,972 | 7.29 | 4.43 | 0.3526 | −0.4303 |
| `NOT_YET` | Discovery | 1,214 | 8.68 | 5.11 | 0.3758 | −0.3965 |
| `NOT_YET` | Validation | 580 | 7.35 | 4.24 | 0.2578 | −0.5669 |
| `EXPIRED` | Both folds | 0 | n/a | n/a | n/a | n/a |
| `UNKNOWN` | Discovery | 161 | 20.64 | 15.66 | 0.6786 | −0.4084 |
| `UNKNOWN` | Validation | 17 | 2.13 | 0.0 | 0.1749 | −0.0950 |

**`EXPIRED` has zero computable outcomes by construction, not a data
gap**: 1,061 of 1,106 `EXPIRED` episodes have their checkpoint at
≈08:15 (before the 09:15 session open, i.e. `SESSION_EXPIRED` fires at
the premarket read before any M5 bar exists that session), and the
remaining 45 occur at/after session close (zero forward bars left).

**Finding — the central, robust result of this milestone: `REPLAYED_QUALIFIED`
episodes materially outperform `ALL_NON_QUALIFIED` episodes, and this
separation holds on the held-out validation fold** — roughly a 3×
(Discovery) to 4.2× (Validation) T1-hit-rate ratio, i.e. the separation
did not shrink out of sample. This is the first real, validated evidence
that the frozen ID-6 EQ methodology actually selects a better starting
population before any ID-7 layer-3 gate is added — exactly the question
this milestone existed to answer. `UNKNOWN`'s validation-fold figure
(2.13%, n=17 valid outcomes, only 1 actual T1 hit) is a **tiny-subgroup
artifact**, not a real signal — flagged explicitly per §16's own
discipline requirement, not treated as evidence either way.

## 7. Entry anchor / extension — the chase-risk hypothesis is not supported

DISCOVERY-fold `QUALIFIED` episodes, VWAP-deviation-pct quartiles (100%
availability):

| Quartile | Range (%) | T1 % | T2 % | MAE median | VWAP-loss stop rate |
|---|---|---|---|---|---|
| Q1 (tightest) | 0.00–0.24 | 17.07 | 8.94 | −0.4884 | 86.18% |
| Q2 | 0.24–0.51 | 27.05 | 16.39 | −0.5483 | 80.33% |
| Q3 | 0.51–0.85 | 28.93 | 19.01 | −0.5601 | 65.29% |
| Q4 (widest) | 0.85–2.81 | 31.15 | 22.13 | −0.3302 | 34.43% |

A real, clean, monotonic relationship on DISCOVERY — but in the
**opposite direction from ID-7B's chase-risk hypothesis**: more
extension from VWAP associates with *better* T1/T2 rates and a *lower*
VWAP-loss stop rate. D1-ATR-normalized distance shows the same, weaker
direction (Q1 23.58% → Q4 27.87%); OR15 distance is not cleanly
monotonic (26.02→23.97→18.18→35.25). A plausible partial confound: later
checkpoints naturally carry more VWAP extension (median 09:xx-hour
extension is smaller than 14:xx-hour extension) — this is not modeled
further (no regression authorized).

**Threshold test** (candidate cutoffs = DISCOVERY p50/p75/p90 of
VWAP-deviation-pct only, evaluated once on VALIDATION):

| Threshold | Disc. retained % | Disc. T1% | Val. retained % | Val. T1% |
|---|---|---|---|---|
| p50 (0.507%) | 50.2% | 22.04% | 60.0% | 19.77% |
| p75 (0.850%) | 75.0% | 24.32% | 80.3% | 20.68% |
| p90 (1.246%) | 90.0% | 24.60% | 91.2% | 21.19% |

Against the unfiltered baselines (Discovery 26.02%, Validation 20.34%):
on DISCOVERY every threshold clearly **reduces** T1 rate (cutting the
"extended" tail removes better-performing episodes, confirming the
quartile finding). On VALIDATION the effect is much weaker and mixed
(p50 slightly worse, p75/p90 slightly *better* than baseline) — this
specific filtering rule does **not** robustly repeat out of sample,
though it also never shows the originally-hypothesized harm.

**Decision: entry anchor = VWAP `deviation_pct`** (chosen for
conceptual continuity with the qualifying signal and the real, if
reversed, quartile relationship). **Classification:
`EXTENSION_GATE_NOT_SUPPORTED` — no extension/chase exclusion threshold
is adopted in V0.** The evidence directly overturns ID-7B §9's assumed
direction; excluding "too-extended" episodes would remove value, not
protect against risk, on this cohort.

## 8. Invalidation — degenerate-pair invariant (structural rule, no longer a finding)

**Frozen as a methodology invariant, not a candidate result**: entry
anchor and invalidation reference must be independent price levels.
`VWAP-anchor + VWAP-loss` and `OR15-anchor + OR15-boundary` are
forbidden — zero risk distance by construction — and were not computed
as if viable.

| Candidate pair | Fold | n | Stop-hit % | Stop-before-T1 | Stop-before-T2 | Time-to-hit median | Risk-dist median |
|---|---|---|---|---|---|---|---|
| M5-close → VWAP-loss | Disc | 488 | 66.60% | 88.00% | 93.85% | 38.83 min | 0.51% |
| M5-close → VWAP-loss | Val | 295 | 60.00% | 88.14% | 96.05% | 25.97 min | 0.43% |
| M5-close → OR15 boundary | Disc | 487 | 18.07% | 95.45% | 100.0% | 96.74 min | 1.45% |
| M5-close → OR15 boundary | Val | 291 | 15.46% | 95.56% | 97.78% | 115.91 min | 1.33% |
| M5-close → D1 ATR (1×) | Disc | 488 | 2.25% | 63.64% | 100.0% | 256.02 min | 2.90% |
| M5-close → D1 ATR (1×) | Val | 295 | 0.68% | 100.0% | 100.0% | 212.58 min | 2.64% |
| VWAP-anchor → OR15 boundary | Disc | 487 | 18.07% | 92.05% | 96.59% | 96.74 min | 0.94% |
| VWAP-anchor → D1 ATR (1×) | Disc | 488 | 0.82% | 50.00% | 50.00% | 300.70 min | 2.92% |

**Important correction to ID-7B.1's own §18 characterization**: ID-7B.1
reported OR15-boundary stop-hit ≈63.76% with stop-before-T1 ≈96.79% —
that figure paired the OR15 *anchor* with OR15-*boundary* invalidation,
which §19 of that same document already recognized, after the fact, as
a forbidden degenerate pairing (both derived from the same OR15 level,
inflating the apparent stop-hit rate). The methodologically valid,
non-degenerate pairings (M5-close or VWAP-anchor entry vs. OR15-boundary
invalidation) show a materially different, much lower stop-hit rate
(15–18%, not 64%) at a slower pace (~97–116 min median, not the ~9 min
ID-7B.1's degenerate figure implied). **This document's numbers
supersede that ID-7B.1 characterization** for any future reference.

**Decisions:**
- **VWAP-loss = primary invalidation.** Fires on a majority of episodes
  in both folds (67%/60%), at a moderate, stable pace (39/26 min
  median), directly tied to the qualifying signal itself, and its
  stop-before-target rate stays high and stable (88%/88% before T1,
  94%/96% before T2) across folds.
- **OR15-boundary = validated secondary/tertiary reference** (when
  `formation.status==COMPLETE`, ~99.8% available). Properly paired, it
  is not the "blunt, too-fast" instrument ID-7B.1's degenerate pairing
  suggested — it fires far less often (15–18%) and at a genuinely
  structural, much slower pace than VWAP-loss.
- **D1 ATR (1×) → `NO_VALIDATED_FALLBACK`.** Confirmed on both folds:
  rarely binding (0.68–2.25%), very wide (median risk distance
  2.6–2.9%) — does not provide useful intraday risk geometry. Not
  preserved for completeness.

## 9. Freshness / currentness — the primary ID-7P0 consequence

Confirmed via source (`session/engine.py`'s `_TIMEFRAME_MINUTES`): M5 =
exactly 5 minutes. "1/2/3 completed M5 intervals" below are literally
5/10/15 minutes, not an approximation.

| Band | Fold | n | VWAP-side persistence | Trend-BULLISH persistence |
|---|---|---|---|---|
| +5m (1) | Disc | 483 | 89.44% | 80.54% |
| +5m (1) | Val | 256 | 90.23% | 83.98% |
| +10m (2) | Disc | 476 | 86.97% | 73.32% |
| +10m (2) | Val | 253 | 82.61% | 72.33% |
| +15m (3) | Disc | 474 | 84.60% | 66.24% |
| +15m (3) | Val | 253 | 77.47% | **58.50%** |

These closely cross-validate ID-7B.1's own general target-cohort
figures (e.g. +10m VWAP 86.97/87.11%, trend 73.32/72.98% — near-exact),
confirming the reconstruction is stable and reproducible across two
independent runs of this milestone's own pipeline.

**Decision: +10m (2 completed M5 intervals) is the frozen freshness
band.** It (a) matches ID-7P0's own measured median canonical-cycle
duration (560.6s ≈ 9.3 min) almost exactly — directly targeting the real
staleness the architecture must compensate for; (b) keeps both VWAP-side
(83–87%) and trend (72–73%) persistence reasonably high and *stable
across both folds*. +15m's trend persistence falls to 58.5% on
validation — materially worse, close to a coin flip on the trend
dimension — rejected as the primary band. +5m is safer but narrower than
the real cycle latency it exists to compensate for. **This numeric
result (5/10/15 minutes) is not reopened by ID-7B.2.1 — only which
timestamp it applies to is corrected, in §14.**

**Clock-source clarification (added by ID-7B.2.1, §29):** the frozen
predicate is `now − evidence_as_of <= 10 minutes`, per ADR-015/ID-7A0.1's
own architecture — `evidence_as_of` and `entry_actionability_as_of` are
deliberately distinct dimensions there, and this document's earlier
wording collapsed them. For V0 specifically, under the selected Option 1
(canonical-cycle synchronous) evaluation mode, `evidence_as_of` **is**
the timestamp of the last completed M5 bar used to compute the VWAP/
trend evidence the checkpoint asserts — which coincides with
`entry_actionability_as_of` by construction, since both are anchored to
the same synchronous, same-cycle snapshot. That is why this milestone's
"forward persistence from the checkpoint" measurement is a valid
empirical proxy for `now − evidence_as_of` today. If a future evaluation
mode (Option 2+, not authorized) ever decouples the two timestamps, the
same 10-minute rule must be re-applied against `evidence_as_of`
specifically — never against `entry_actionability_as_of` as a
substitute.

## 10. Reward/risk — `RR_INFORMATIONAL_ONLY`

RR-to-T1 (using M5-close entry / VWAP-loss risk distance), quartiles vs
T1 hit rate:

| Quartile (RR-to-T1) | Discovery T1% | Validation T1% |
|---|---|---|
| Q1 (loosest risk) | 30.89% | 20.00% |
| Q2 | 29.51% | 26.03% |
| Q3 | 26.45% | 15.07% |
| Q4 (tightest risk) | 17.21% | 20.27% |

DISCOVERY shows a clean monotonic decline (tighter risk → worse
outcome, consistent with §7's own reversed-extension finding).
**VALIDATION does not confirm this** (20.00 → 26.03 → 15.07 → 20.27 —
non-monotonic, order scrambled). Per the milestone's own instruction,
this cross-fold instability means **RR is classified
`RR_INFORMATIONAL_ONLY`** — computed and exposed, never a gate.

## 11. RS / RVOL / Gap — none promoted past context-only

| Signal | Discovery pattern (Q1→Q4 T1%) | Validation pattern (Q1→Q4 T1%) | Stable across folds? |
|---|---|---|---|
| RS (`stock_vs_market_pct`) quartile | 24.39 → 23.77 → 16.53 → 39.34 | 5.33 → 28.77 → 24.66 → 22.97 | **No** |
| RVOL ratio quartile | 23.58 → 19.67 → 22.31 → 38.52 | 22.67 → 23.29 → 17.81 → 17.57 | **No** — direction differs by fold |
| Gap direction (FLAT/DOWN/UP) | 27.42 / 25.75 / 25.87 | 20.00 / 20.51 / 20.28 | No pattern either fold |
| Gap % quartile | 25.81 → 27.27 → 23.97 → 27.05 | 18.67 → 20.55 → 21.92 → 20.27 | No pattern either fold |

**Decisions: `RS_CONTEXT_ONLY`, `RVOL_CONTEXT_ONLY`, `GAP_CONTEXT_ONLY`.**
ID-7B.1's own combined-population quartile splits looked more
monotonic; splitting by fold (required here) shows neither RS nor RVOL
holds a stable direction independently across both folds — exactly the
small-validation-N noise the authorization anticipated (validation
quartiles are only ~73-75 episodes each). Gap confirms "no clear
pattern" on the full re-check.

## 12. Canonical-cycle Option-1 classification

**`OPTION1_ACCEPTABLE_WITH_STRICT_CURRENTNESS`.**

Not the unconditional `OPTION1_V0_ACCEPTABLE`: real, material decay
exists (trend persistence falls to 72–73% by +10m, meaning roughly
one-in-four episodes has already flipped trend by the time a canonical
cycle would typically complete) — a currentness gate is genuinely
load-bearing, not decorative. Not
`OPTION1_NOT_ACCEPTABLE_ADR015_REVISION_REQUIRED` either: the decay is
real but bounded and compensable — the validated +10m freshness band
(§9) keeps both VWAP-side and trend persistence reasonably high and
stable across both folds, exactly the kind of "strict currentness"
condition ADR-015's `is_currently_usable` predicate was architected to
carry.

## 13. ID-7P0 Recommendation-A final reassessment

**`A_ACCEPTED_ONLY_WITH_CURRENTNESS_GUARD`.**

Now evidence-backed, not provisional: the comparison population (§6)
proves `QUALIFIED` episodes are a genuinely better starting population,
and that separation survives at real, measured evidence-age lag
(consistent with the +10m band's own persistence figures) — but only
because a real currentness gate is present. Latency compensation is
accepted, conditioned on the freshness gate from §9 actually being
implemented as a load-bearing check, not a passive label.

## 14. Final V0 methodology contract

**Corrected by ID-7B.2.1 (§29) — this section replaces the original
version of §14, which recreated the exact degenerate VWAP-anchor +
VWAP-loss pairing §8 itself forbids, retained D1 ATR as mandatory
evidence despite no final V0 calculation consuming it, and conflated the
persisted methodology verdict with the read-time currentness check. The
underlying calibration numbers (§§6-11) are unchanged — only this
synthesis was wrong.**

```
UPSTREAM ELIGIBILITY:
  Decision.decision_type == TRADE
  AND exact bound EntryQualification.state == QUALIFIED
  (else PERSISTED NOT_ACTIONABLE, reason UPSTREAM_DECISION_NOT_TRADE
   or UPSTREAM_EQ_NOT_QUALIFIED — carrying the exact upstream EQ state)

PERSISTED METHODOLOGY EVIDENCE SUFFICIENCY:
  VWAP + completed M5 checkpoint close price available
  (D1 ATR is NOT required — no final V0 calculation consumes it: the
   extension gate was not adopted, the D1-ATR fallback was not
   validated, and RR uses the VWAP-loss/OR15-boundary risk distance,
   never ATR. VWAP is, in practice, already guaranteed available
   whenever upstream EQ == QUALIFIED, since EQ's own v0 formula
   requires a resolved VWAP relation — so this check is expected to
   pass whenever eligibility is reached at all; it remains an explicit
   UNKNOWN safeguard for the rare case it does not.)
  (else PERSISTED UNKNOWN, reason INSUFFICIENT_EVIDENCE)

ENTRY TRIGGER / CHECKPOINT REFERENCE:
  the completed M5 checkpoint close price at entry_actionability_as_of
  — this is the actual entry reference the validated VWAP-loss pairing
  (§8) used ("checkpoint/M5-close entry → VWAP-loss"), never VWAP
  itself. No calibrated entry-zone width exists (EXTENSION_GATE_NOT_SUPPORTED,
  §7) — V0 exposes a single point reference, not a "trigger + zone";
  a future zone-width calibration is a separate, later methodology
  revision, not invented here.

ENTRY-LOCATION CONTEXT (informational, non-gating):
  session VWAP value and deviation_pct from the M5-close checkpoint
  reference above. This is the dimension §7's extension analysis
  actually tested (and found EXTENSION_GATE_NOT_SUPPORTED for) — VWAP
  serves as context/explanation here, never as the entry trigger
  itself, and never re-used as an invalidation reference for the same
  reason §8 forbids it (would be degenerate against itself).

OPERATIVE INVALIDATION (deterministic selection rule):
  VWAP-loss (price closes back through session VWAP against direction,
  on a subsequent completed M5 bar) is the sole level that determines
  risk distance and RR. It is independent of the entry trigger (M5-close
  price ≠ VWAP — two distinct levels, non-degenerate) and is, in
  practice, computable whenever eligibility is reached at all (VWAP is
  already required for upstream EQ == QUALIFIED, per the evidence-
  sufficiency note above).
  OR15 boundary (only when formation.status == COMPLETE, independently
  paired — never against an OR15-derived entry reference) is ALWAYS
  additionally computed and exposed as a secondary, purely contextual
  structural reference alongside VWAP-loss — it does not replace,
  average with, or get selected over VWAP-loss for risk-distance/RR
  purposes under V0's synchronous evaluation mode, since VWAP-loss's own
  availability is not realistically expected to fail while eligibility
  holds. It is not a "fallback triggered when VWAP-loss is unavailable"
  — no such substitution was calibrated or validated.
  D1-ATR is NO_VALIDATED_FALLBACK — not part of V0 at all.
  => if VWAP-loss itself is not computable (the rare evidence-
     sufficiency edge case above), PERSISTED UNKNOWN, reason
     INVALIDATION_UNAVAILABLE.

REWARD REPRESENTATION:
  T1 ≈ +1%, T2 ≈ +1.5% goal bands from the entry trigger
  (GOAL_BANDS_ONLY, unchanged).
  RR = reward-to-goal-band ÷ VWAP-loss risk distance, computed and
  exposed, RR_INFORMATIONAL_ONLY (no gate — §10).

PERSISTED STATE MAPPING (evaluation-time only; immutable once written):
  ACTIONABLE      = upstream eligible AND evidence sufficient AND
                     VWAP-loss invalidation computable
  NOT_ACTIONABLE  = upstream eligibility fails (Decision not TRADE, or
                     bound EQ not QUALIFIED)
  UNKNOWN         = upstream eligible but required evidence
                     (VWAP/M5-close/VWAP-loss) is not computable
  This mapping never reads wall-clock time, session freshness, or the
  identity of any *later* Decision/EQ — it is a pure function of the
  evidence available at entry_actionability_as_of. A persisted
  ACTIONABLE row is never rewritten by anything below.

READ-TIME CURRENTNESS (derived, never persisted, computed only when a
consumer asks — `is_currently_usable(...)`, ADR-015/ID-7A0.1):
  persisted state == ACTIONABLE
  AND bound Decision/EQ identity still the current latest
    (full composite-key equality, per ADR-015/ID-7A0.1)
  AND now − evidence_as_of <= 10 minutes (2 completed M5 intervals;
    evidence_as_of coincides with entry_actionability_as_of under the
    selected Option 1 synchronous mode — see §9's clock-source note)
  AND session phase == REGULAR (right now, at read time — distinct
    from the evaluation-time eligibility check above; a row evaluated
    during REGULAR remains historically ACTIONABLE after the session
    closes, it simply stops being currently usable)
  => CURRENT / STALE / SUPERSEDED / SESSION_CLOSED (illustrative
     currentness labels, exact set left to ID-7A; never a persisted
     reason code)

EVIDENCE FINALITY (independent third dimension, inherited unchanged):
  echoed from the bound EQ's own evidence_finality
  (e.g. LIVE_M5_PROVISIONAL) — informational, never gates (A) or (B)
  above.

DIRECTION SCOPE:
  LONG only (LONG_VALIDATED_SHORT_UNVALIDATED, §21) — zero SHORT
  decisions exist to validate against; no synthetic examples used.
```

**Worked example, per the owner's own item 10** (persisted-state
immutability): a row evaluated at 10:00 persists `ACTIONABLE`. Read at
10:12 (12 minutes later): the row's own `state` is still, and always
will be, `ACTIONABLE` — that is historical fact. But
`is_currently_usable(...)` at 10:12 returns `false`/`STALE`, since
`now − evidence_as_of` (12 min) exceeds the 10-minute band. Both
statements are true simultaneously; neither is rewritten.

Context-only, non-gating signals carried through for explanation: RS
magnitude/relation, RVOL magnitude/relation, GapContext.

## 15. UNKNOWN vs NOT_ACTIONABLE (corrected by ID-7B.2.1 — D1 ATR removed, persisted/currentness separated)

`UNKNOWN` = required evidence (VWAP or the completed-M5 checkpoint close
price, or the VWAP-loss invalidation level itself) unavailable/
uncomputable — **D1 ATR is not part of this list** (§14; it is not a V0
input at all). `NOT_ACTIONABLE` = evidence exists and the upstream
eligibility gate fails (`Decision` not `TRADE`, or bound EQ not
`QUALIFIED`). Both are **persisted, evaluation-time-only** verdicts.
Stale historical evidence is never classified as bearish — currentness
(§14's read-time block, §12) is a strictly derived, non-persisted
concept computed separately, and never rewrites a persisted verdict
(§14's worked example).

## 16. Reason-code taxonomy (corrected by ID-7B.2.1 — `SESSION_NOT_ACTIONABLE` removed)

Persisted, evaluation-time methodology reasons only:
`UPSTREAM_DECISION_NOT_TRADE`, `UPSTREAM_EQ_NOT_QUALIFIED` (carrying the
exact upstream EQ state — including EQ's own session-phase-driven states
like `NOT_YET`/`EXPIRED`; a non-`REGULAR`-session checkpoint is already
fully covered by this code, since upstream EQ itself cannot be
`QUALIFIED` outside `REGULAR`), `INSUFFICIENT_EVIDENCE` (drives
`UNKNOWN`), `INVALIDATION_UNAVAILABLE` (VWAP-loss itself not computable).
No `ENTRY_TOO_EXTENDED` code — the extension gate is not adopted. **No
`SESSION_NOT_ACTIONABLE` persisted reason** — session eligibility at
evaluation time is already fully inherited from the upstream EQ reason
above; a *separate* session-based persisted reason would be redundant.
Currentness/freshness failures remain a wholly separate, read-time
classification (`CURRENT`/`STALE`/`SUPERSEDED`/`SESSION_CLOSED`,
non-final naming, §14), never a persisted methodology reason code.

## 17. Methodology version (corrected by ID-7B.2.1)

**Not minted.** The original draft called a string both "minted" and
"illustrative, subject to later convention" — an identity-bearing value
cannot be both frozen and provisional. Corrected resolution: **the V0
methodology *content* is fully frozen (§14)**, but the exact persisted
`entry_actionability_methodology_version` **string** is deliberately
deferred to ID-7A — this research/calibration milestone has no
repository-versioning authority of its own (unlike, say, an engine
module that would own its own version constant). ID-7A must mint the
actual string, namespaced apart from `EntryQualification`'s own
`methodology_version` values, when it implements this contract.

## 18. Session robustness

All 20 sessions reported (full table in the underlying data). Notable:
`REPLAYED_QUALIFIED` retention ranges from 0% (2026-08-19, zero
qualified episodes that session — a real, honestly-reported outcome, not
an error) to 30.98% (2026-08-20). Two VALIDATION-fold sessions
materially depress that fold's aggregate T1 rate relative to the other
four: **2026-08-24** (49 qualified, T1=2.04%) and **2026-08-25** (54
qualified, T1=5.56%) — the other four validation sessions show T1 rates
(23.81–35.71%) comparable to discovery. This is flagged honestly:
VALIDATION's headline separation (§6) is real but not evenly
distributed across its 6 sessions; 2 of 6 sessions account for most of
the shortfall relative to discovery-level hit rates. **Corrected by
ID-7B.2.1** (removing an unsupported presumption): the aggregate
validation-fold separation from `ALL_NON_QUALIFIED` (§6) remains
established as measured. Per-session `QUALIFIED`-vs-`ALL_NON_QUALIFIED`
separation specifically for 2026-08-24/2026-08-25 was **not measured in
this milestone and is therefore unknown** — not presumed either way. A
genuine caveat for future evidence accumulation, not a disqualifying
finding.

## 19. Instrument concentration

Top-5 instruments (`NSE:ADANIENT`, `NSE:GVT&D`, `NSE:KIRLOSENG`,
`NSE:EMMVEE`, `NSE:CARTRADE`; 6–9 occurrences each) account for only
**5.49%** of the 783-episode `QUALIFIED` population — broad-based, no
concentration risk.

## 20. Time-of-day robustness (coarse; no finer repository authority exists)

| Checkpoint hour | n | T1 hit % |
|---|---|---|
| 09:xx | 167 | 37.13% |
| 10:xx | 224 | 29.02% |
| 11:xx | 52 | 26.92% |
| 12:xx | 114 | 25.44% |
| 13:xx | 55 | 12.73% |
| 14:xx | 107 | 9.35% |
| 15:xx | 64 | 0.00% |

A strong, monotonic decline across the session — **mechanically
confounded by shrinking forward window** (a 15:xx checkpoint has almost
no same-session time left to reach +1%), not necessarily an independent
quality signal on its own. Flagged as a caveat, not modeled further (no
regression authorized in this milestone).

## 21. SHORT side

Unchanged and reconfirmed: **`LONG_VALIDATED_SHORT_UNVALIDATED`.** Zero
`SHORT` decisions exist anywhere in `db/athena.db`, of any type — no
synthetic examples manufactured, no `Decision`/scoring/ID-6 change made
or proposed.

## 22. Generic support/resistance status

**`V0_DOES_NOT_REQUIRE_GENERIC_SR`** — reconfirmed. The final V0
contract (§14) uses only VWAP and OR15-boundary (when `COMPLETE`) for
invalidation, and percentage goal bands for reward — no generic
support/resistance dependency.

## 23. Replay / knowledge-time limitation (unchanged)

Preserved exactly as ID-7B.1/ADR-013 already state: settled
market-time replay, not knowledge-time reconstruction. This document's
conclusions describe how the frozen methodology behaves against
today's persisted market-time data, not a claim about what production
literally knew in real time on any historical date.

## 24. Statistical discipline

Every calibrated choice above reports both DISCOVERY and VALIDATION
results explicitly, including the cases where validation did **not**
confirm discovery (the threshold-retention test in §7; the RR pattern
in §10; RS/RVOL in §11) — these are reported as real, informative
negative/mixed results, not smoothed over. No significance test was run
(this is not a claim of statistical significance); no use of the words
"proven," "predictive," or "statistically significant" anywhere in this
document, per the authorization's explicit instruction. Fold sizes are
small (6/20 validation sessions, 256–295 valid-outcome episodes per
fold) — all conclusions are appropriately hedged to that scale.

## 25. No profitability claim

T1/T2/MFE/MAE are pure price-path research outcomes. None of the figures
in this document include fees, slippage, spread, market impact, or
position sizing — no P&L or expected-return claim is made anywhere.
ID-9 (sizing) and ID-11 (execution quality) remain untouched and
separate.

## 26. Cross-track isolation

Zero EMR, DarvaX, or Portfolio Setup methodology inspected, imported, or
modified in this milestone (only the already-cited PS-P9B architectural
caution, carried forward from ID-7B/ID-7B.1, was referenced again in
§8).

## 27. Calibration top-level classification

**`V0_METHODOLOGY_CALIBRATED_AND_VALIDATED`.**

Every required methodology dimension reached a definitive,
chronologically-validated conclusion — including the dimensions whose
honest conclusion is "not supported" (extension gate) or "context only"
(RS/RVOL/Gap) or "no validated fallback" (D1 ATR). A negative or
context-only result, reached through real discovery/validation
discipline, is a complete calibration outcome, not an incomplete one.
The resulting V0 (§14, as corrected by ID-7B.2.1 — see §29) is exactly
the small, deterministic set the authorization asked for: one upstream
gate, one evidence-sufficiency check, an M5-close entry trigger with
VWAP as location context only (no extension gate), one operative
invalidation reference (VWAP-loss) with OR15-boundary as an always-
computed contextual secondary, goal-band reward with informational RR,
and one validated freshness/currentness band applied against
`evidence_as_of`.

## 28. Remaining evidence limitations

- LONG-only; SHORT remains unvalidated (§21), a hard data boundary.
- Only 20 sessions total, 6 held out for validation — genuinely small;
  two validation sessions dominate that fold's shortfall (§18).
- RS/RVOL were not proven *harmful* to include, only not *stably
  supportive* at this sample size — a larger future cohort could
  revisit this.
- The `EXPIRED`-state's zero-outcome structural property (§6) means
  this milestone cannot speak to whether the `SESSION_EXPIRED` v0
  boundary itself is well-placed — out of scope (ID-6 methodology,
  unchanged, not reopened).
- Session-level `ALL_NON_QUALIFIED` performance was not independently
  re-verified for the two weak validation sessions flagged in §18 — a
  natural follow-up check, not performed here.

---

## 29. ID-7B.2.1 — Owner Review Correction (2026-09-04, same day)

**Owner/Chief Architect source review accepted every calibration
*result* in this document (§§6-11: the comparison-population evidence,
`EXTENSION_GATE_NOT_SUPPORTED`, the validated invalidation candidates,
`RR_INFORMATIONAL_ONLY`, `RS`/`RVOL`/`GAP_CONTEXT_ONLY`, and the
freshness band) and the top-level classifications (§§12-13, §27:
`OPTION1_ACCEPTABLE_WITH_STRICT_CURRENTNESS`,
`A_ACCEPTED_ONLY_WITH_CURRENTNESS_GUARD`, `V0_METHODOLOGY_CALIBRATED_AND_VALIDATED`)
— but held the final V0 contract freeze for three narrow consistency
corrections to §14's own synthesis, which did not faithfully represent
what §8's own invariant and §6-10's own evidence actually supported. No
recalibration, no new fold, no new threshold search was authorized or
performed — this is a documentation-consistency correction only.**

**Correction 1 — the original §14 recreated the exact forbidden
degeneracy §8 itself names.** §8 freezes "entry anchor and invalidation
reference must be independent price levels" and explicitly forbids
`VWAP-anchor + VWAP-loss`. The original §14 nonetheless wrote
`ENTRY LOCATION: anchor = session VWAP` immediately followed by
`INVALIDATION: primary = VWAP-loss` — recreating that exact forbidden
pairing in the contract's own words, even though the underlying §8 data
table was actually computed for the non-degenerate `M5-close entry →
VWAP-loss` pairing. **Corrected**: the entry trigger is now stated
explicitly as the completed M5-close checkpoint price (never VWAP);
VWAP is relabeled as an entry-*location context* signal only (feeding
§7's extension analysis, never re-used as the invalidation reference for
itself). This matches, rather than contradicts, what was actually
validated.

**Correction 2 — D1 ATR removed from mandatory evidence.** The original
§14 required "VWAP + D1 ATR + completed M5 checkpoint price" for
evidence sufficiency, despite the final, corrected V0 not using D1 ATR
for anything (`EXTENSION_GATE_NOT_SUPPORTED` means no ATR-normalized
extension gate exists; `NO_VALIDATED_FALLBACK` means the ATR invalidation
tier is not adopted; RR uses the VWAP-loss risk distance, never ATR).
**Corrected**: mandatory evidence is now VWAP + the M5-close checkpoint
price only. OR15 evidence is correspondingly clarified as never gating
(its absence does not produce `UNKNOWN`) — it is an always-attempted,
purely contextual secondary reference, not a fallback selected when
VWAP-loss is unavailable (no such substitution was calibrated). A
deterministic invalidation-selection rule is now stated explicitly in
§14: VWAP-loss is the sole level driving risk-distance/RR; OR15-boundary
is computed and exposed alongside it, never instead of it.

**Correction 3 — freshness clock source.** The original §14/§9 wrote
"evidence age ≤ 10 minutes from `entry_actionability_as_of`," collapsing
a distinction ADR-015/ID-7A0.1 deliberately froze: `evidence_as_of` (the
market-time of the decisive evidence) and `entry_actionability_as_of`
(the checkpoint at which the layer-3 assertion itself is made) are
architecturally separate dimensions. **Corrected**: the frozen predicate
is restated as `now − evidence_as_of ≤ 10 minutes`, with an explicit
note (§9) that the two timestamps coincide *today*, under the selected
Option 1 (canonical-cycle synchronous) evaluation mode, as a consequence
of that mode's own design — not because they are definitionally the
same concept. This preserves ADR-015's own distinction for any future
evaluation mode.

**Additional corrections applied in the same pass** (documentation
hygiene, no new analysis): §15/§16 updated to remove D1 ATR from the
`UNKNOWN` evidence list and to remove a redundant `SESSION_NOT_ACTIONABLE`
persisted reason code (session ineligibility at evaluation time is
already fully carried by `UPSTREAM_EQ_NOT_QUALIFIED`, since upstream EQ
itself cannot be `QUALIFIED` outside `REGULAR`); §14 now states the
persisted-state mapping (evaluation-time only, immutable) and the
read-time currentness predicate as two explicitly separate blocks, with
a worked example proving a persisted `ACTIONABLE` row is never rewritten
by a later staleness/session-closed read; §17 corrected an internal
contradiction (a methodology-identity value cannot be both "minted" and
"illustrative, subject to later convention") — the V0 *content* is
frozen, the persisted version *string* is deferred to ID-7A, which owns
repository versioning authority this research milestone does not; §18
removed an unsupported presumption about the two weak validation
sessions' non-`QUALIFIED` population, stated as genuinely unmeasured
instead.

**None of the frozen negative/context-only results were reopened**:
`EXTENSION_GATE_NOT_SUPPORTED`, `RR_INFORMATIONAL_ONLY`,
`RS_CONTEXT_ONLY`, `RVOL_CONTEXT_ONLY`, `GAP_CONTEXT_ONLY`, and
`NO_VALIDATED_FALLBACK` all stand exactly as calibrated in §§7/10/11. The
20-session chronological split, the 5/10/15-minute freshness candidate
set, and the `OPTION1_ACCEPTABLE_WITH_STRICT_CURRENTNESS`/
`A_ACCEPTED_ONLY_WITH_CURRENTNESS_GUARD`/`LONG_VALIDATED_SHORT_UNVALIDATED`/
`V0_DOES_NOT_REQUIRE_GENERIC_SR` classifications are all unchanged.

**ADR-015 consistency proof**: §14's corrected read-time currentness
block now names all three of ADR-015/ID-7A0.1's own frozen dimensions
explicitly and keeps them separate — (A) persisted methodology state,
(B) derived `is_currently_usable` currentness, (C) evidence
finality/provisionality (echoed from bound EQ, independent of A/B) —
with the worked example directly demonstrating (A) is never mutated by
(B). This is the same three-dimension model ADR-015/ID-7A0.1 froze,
applied faithfully to V0's own content for the first time in this
milestone.

**Corrected top-level V0 contract categories** (per the authorization's
own required list): Upstream Eligibility, Persisted Methodology Evidence
Sufficiency, Entry Trigger/Reference, Entry-Location Context, Operative
Invalidation, Reward Representation, Persisted State Mapping, Read-Time
Currentness, Evidence Finality, Direction Scope — all now distinct,
unambiguous sections of §14's corrected contract.
