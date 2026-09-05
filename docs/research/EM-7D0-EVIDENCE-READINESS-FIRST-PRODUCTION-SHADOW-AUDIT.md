# EM-7D0 — Evidence Readiness / First Production Shadow Audit

**Status (2026-09-05): READ-ONLY AUDIT COMPLETE. NO EM-7D STATISTICAL
VALIDATION BEGUN. NO CODE/CONFIG/METHODOLOGY CHANGE. NATURAL PRODUCTION
ACCUMULATION UNCHANGED AND ACTIVE.**

Owner/Chief Architect closed EM-7C and EM-7C.1 (natural EMR production
shadow accumulation active) and authorized this read-only audit to
determine whether the naturally accumulated production evidence in
`db/emr.db` is sufficiently complete and trustworthy to begin EM-7D
statistical methodology validation — not to begin that validation
itself.

All queries in this document were executed via a read-only SQLite
connection (`mode=ro` + `PRAGMA query_only=ON`) against `db/emr.db` — a
second, independent connection, never the live service's own writable
connection. Zero writes were made. `config/emr/operational.json`
(`enabled: true`, `base_universe: "athena_core"`, `model_version: "v1"`,
`max_staleness_minutes: 30.0`, `poll_interval_seconds: 30.0`) and the
frozen `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS = 300.0` constant were
only read, never modified.

---

## 1. Audit cutoff

**`audit_cutoff_session_date = 2026-09-04`** (the EM-7C activation
session — the only session with any persisted EMR production data).
**`audit_cutoff_checkpoint = 14:00`** (the last checkpoint of that
session; `15:45` CLOSING is not part of EMR's own checkpoint set).

2026-09-04 is a **complete** natural session for EMR's own purposes: all
9 of the frozen checkpoints (`09:20, 09:30, 09:45, 10:00, 10:30, 11:00,
12:00, 13:00, 14:00`) have a persisted `emr_scan_runs` row, each
`status=COMPLETE`. No later session exists — 2026-09-05 is a real NSE
non-trading day (`SessionType.WEEKEND`, confirmed independently during
ID-7F2's own preparation the same day), so no EMR checkpoint could have
fired since.

---

## 2. Natural EMR run inventory (§2)

All 9 runs, in checkpoint order:

| Checkpoint | `run_id` (truncated) | Status | `started_ts`=`finished_ts` | `eligible_count` | `ineligible_count` | `quote_request_count` |
|---|---|---|---|---:|---:|---:|
| 09:20 | `em5-scan-fffa4633…` | COMPLETE | 09:20:20.807822 | 0 | 518 | 136 |
| 09:30 | `em5-scan-ba4644a2…` | COMPLETE | 09:30:02.682278 | 517 | 1 | 134 |
| 09:45 | `em5-scan-8ae6ea74…` | COMPLETE | 09:45:16.671193 | 517 | 1 | 134 |
| 10:00 | `em5-scan-9ea59b86…` | COMPLETE | 10:00:29.975423 | 517 | 1 | 136 |
| 10:30 | `em5-scan-b628befa…` | COMPLETE | 10:30:17.467683 | 517 | 1 | 134 |
| 11:00 | `em5-scan-216a2d2c…` | COMPLETE | 11:00:08.983372 | 517 | 1 | 135 |
| 12:00 | `em5-scan-3c470bc3…` | COMPLETE | 12:00:25.519989 | 0 | 518 | 143 |
| 13:00 | `em5-scan-14e02e23…` | COMPLETE | 13:00:14.423004 | 517 | 1 | 143 |
| 14:00 | `em5-scan-7909f4b4…` | COMPLETE | 14:00:27.471368 | 517 | 1 | 142 |

`frozen_model_version = "v1"` on every row (unchanged). `finished_ts`
equals `started_ts` on every row — this is a pre-existing persistence
convention (the field is not a true wall-clock-duration measurement in
this schema; real per-checkpoint work time is instead visible via
`evidence_generation_duration_ms`/`quote_capture_duration_ms`/
`inference_duration_ms`/`total_duration_ms`, all genuinely distinct
per-run — see §29-31). `failure_type`/`failure_reason` are `NULL` on
every row (no run-level failure occurred). The scanner did not run;
this milestone only read what already existed.

---

## 3. Expected checkpoint contract (§3)

Frozen set: `09:20, 09:30, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00,
14:00` IST. **All 9 are present for 2026-09-04 — 100% checkpoint
coverage, zero missing checkpoints.** No EM-7B latest-due-skip logic
needed to be invoked or explained, since nothing is missing.

---

## 4. Run lifecycle audit (§4)

- Status values observed: `{COMPLETE: 9}`. **Zero `RUNNING`, zero
  `FAILED`, zero `PARTIAL`** (and `PARTIAL` is not even a legal value
  per the frozen EM-7A.1 two-terminal-outcome model — confirmed absent
  by direct query, not merely assumed).
- **Stale `RUNNING` rows: 0.**
- **`FAILED` run count: 0.**
- **Duplicate logical run identity** — checked via
  `(session_date, checkpoint, frozen_model_version)` (the deterministic-identity
  components persisted at the run level; `base_universe` is implicit
  in `athena_core`/`v1` for this entire session, confirmed constant
  throughout): **0 duplicates** — a `GROUP BY ... HAVING COUNT(*) > 1`
  query over all 9 rows returned zero groups.

---

## 5. Atomicity / persistence integrity (§5)

- **Orphan candidates** (`emr_candidates.run_id` with no matching
  `emr_scan_runs.run_id`): **0** (checked via `NOT EXISTS` over all
  74,448 candidate rows).
- **Orphan transitions** (`emr_transitions.run_id` with no matching
  `emr_scan_runs.run_id`): **0** (checked over all 10,922 transition
  rows).
- **Duplicate candidate identity**
  (`run_id, instrument_id, family, threshold_percent`): **0**.
- **Duplicate transition identity**
  (`run_id, instrument_id, family, threshold_percent, sequence_number`): **0**.
- **Partial-looking `COMPLETE` runs**: none found — every `COMPLETE` run
  with `eligible_count > 0` has exactly `eligible_count × 18`
  (3 families × 6 thresholds) candidate rows persisted (verified: 517 ×
  18 = 9,306, matching exactly for all 7 such runs); the 2 runs with
  `eligible_count = 0` are handled per §7's finding (one has 0 candidate
  rows, the other has candidate rows for all *tracked* instruments,
  all flagged `STALE` — both are internally coherent with their own
  `eligible_count`, not partial/corrupt).

**Atomicity/integrity verdict: SOUND. Zero defects of any kind found.**

---

## 6. Universe / mature-history audit (§6)

- **Configured base universe**: `athena_core` (unchanged, per
  `config/emr/operational.json`).
- **Model/version**: `v1` (unchanged).
- **Actual universe count**: **518** (`eligible_count + ineligible_count`
  on every run — constant across all 9 runs; confirms the universe
  membership itself did not change intra-session).
- **Distinct instruments actually receiving a candidate row**: **517**
  on every checkpoint that produced candidates (09:30 onward, plus
  12:00 — see §7); **0** at 09:20.
- **Excluded-for-history count**: not a separately persisted field in
  this schema (no `mature_history_count`/`excluded_for_history` column
  exists on `emr_scan_runs` or elsewhere) — inferred only indirectly:
  the constant **1-instrument gap** between the 518-count universe and
  the 517-distinct-instrument candidate population, present at *every*
  checkpoint that produced any candidates at all, is consistent with
  one universe member being structurally excluded from candidate
  construction throughout the session (e.g. insufficient daily-bar
  history) — reported as an observed pattern, not asserted as a proven
  cause, since no persisted field names it directly.

---

## 7. Current-session M5 availability — the central EM-7D0 question (§7)

**Answer: current-session M5 availability recovered almost immediately
after the 09:20 canary, held for five consecutive checkpoints, then
experienced one further real, transient regression at 12:00, then
recovered again for the remaining two checkpoints.**

| Checkpoint | Distinct instruments w/ candidate row | `eligible_count` | Candidate `freshness` | `evidence_generation_duration_ms` | `inference_duration_ms` |
|---|---:|---:|---|---:|---:|
| 09:20 | **0** | 0 | n/a (no rows) | **0.096** | **0.034** |
| 09:30 | 517 | 517 | FRESH ×9,306 | 2,561.05 | 1,933.92 |
| 09:45 | 517 | 517 | FRESH ×9,306 | 2,134.14 | 2,197.93 |
| 10:00 | 517 | 517 | FRESH ×9,306 | 2,775.42 | 3,103.33 |
| 10:30 | 517 | 517 | FRESH ×9,306 | 2,431.27 | 8,829.11 |
| 11:00 | 517 | 517 | FRESH ×9,306 | 2,343.32 | 4,561.62 |
| **12:00** | **517** | **0** | **STALE ×9,306** | 2,403.09 | 5,558.95 |
| 13:00 | 517 | 517 | FRESH ×9,306 | 2,905.58 | 5,567.49 |
| 14:00 | 517 | 517 | FRESH ×9,306 | 2,377.47 | 7,081.43 |

**Two structurally different zero/degraded-eligibility events, correctly
distinguished by the persisted evidence itself:**

- **09:20 (already root-caused and Owner-accepted under EM-7C):**
  `evidence_generation_duration_ms` and `inference_duration_ms` are both
  effectively **zero** (0.096ms / 0.034ms vs. ~2,000–3,000ms and
  ~2,000–8,800ms at every other checkpoint) — proving the per-instrument
  evidence-assembly loop itself never meaningfully ran; **zero**
  candidate rows exist for this checkpoint at all. This matches EM-7C's
  own already-accepted finding: canonical M5 ingestion had not yet
  landed the day's first bar for any of the 518 instruments at this
  exact instant.
- **12:00 (a new finding from this audit — not previously characterized):**
  `evidence_generation_duration_ms` (2,403ms) and `inference_duration_ms`
  (5,559ms) are **both fully in line with every other real checkpoint**
  — proving the per-instrument evidence-assembly and scoring loops ran
  completely normally, producing real logits/contributions for all 517
  tracked instruments (verified directly: sampled `logit_contributions_json`
  rows carry non-trivial `sma20_rel`/`rsi14`/`atr14_norm`/regime-feature
  values, not placeholder zeros). What differs is specifically the
  **hard-eligibility gate**: `state_reason = 'STALE_DATA'` is the
  persisted, literal value on every 12:00 candidate row — the exact
  `HardIneligibilityReason.STALE_DATA` value `evaluate_candidate_eligibility`
  (`eligibility.py:100-104`) emits when `most_recent_candle_ts` (the
  current-session M5 series) is either absent or older than
  `max_staleness_minutes` (30) relative to the checkpoint. Critically,
  `checkpoint_price` (the live quote) is **non-NULL for all 9,306** rows
  at 12:00 — the quote/price collection subsystem was entirely
  unaffected; this is specifically a **current-session M5 candle
  staleness** condition, not a quote/provider outage.

**Correlated, source-grounded (not proven) explanation for the 12:00
regression:** the real canonical `runs` table (main `db/athena.db`)
shows a `REFRESH` cycle **failed** at `11:35:48` and the next
`REFRESH` did not report `COMPLETED` until `11:59:46` — a real gap of
roughly 24+ minutes between the last known-good ingestion attempt and
the next one, landing almost exactly across EMR's own 12:00 checkpoint
(`started_ts` 12:00:25). Given ID-7P0's own already-measured ~9-10
minute real median REFRESH cycle duration, it is plausible that fresh
M5 candles for the current session had not yet been durably written to
`candles` by the moment EMR's 12:00 scan read them, pushing
`most_recent_candle_ts` beyond the 30-minute threshold for every
instrument simultaneously — exactly the uniform, all-518, hard-cutoff
pattern observed. This is reported as a **strong, corroborated
hypothesis**, not an independently proven causal chain (EMR's own exact
read instant relative to the REFRESH commit instant is not separately
timestamped in either system) — and it points to a **cross-system
ingestion-timing characteristic already documented elsewhere (ID-7P0)**,
not an EMR-specific code defect.

**Earliest checkpoint with sufficient current-session M5 evidence for
meaningful evaluation: 09:30** (the very next checkpoint after
activation).

---

## 8. Data-failure breakdown (§8)

Only one real, persisted ineligibility-reason value was observed across
the entire session: **`STALE_DATA`** (`HardIneligibilityReason.STALE_DATA`,
the same enum member covers both "no candle at all" and "candle older
than the staleness threshold" — the persisted schema does not further
distinguish these two sub-cases from each other). No other
`HardIneligibilityReason` member (`NOT_IN_UNIVERSE`,
`NO_OBSERVABLE_PRICE_AT_CHECKPOINT`, `PRICE_BAND_IMPOSSIBLE`) was
observed as a `state_reason` value anywhere in this session's 74,448
candidate rows.

| Checkpoint | `STALE_DATA` rows | % of that checkpoint's rows |
|---|---:|---:|
| 09:20 | n/a — 0 candidate rows exist to classify (see §7) | n/a |
| 09:30–11:00, 13:00–14:00 | 0 | 0% |
| 12:00 | 9,306 | 100% |

**Important scope note:** `emr_candidates` only ever contains rows for
instruments that reached candidate-row construction (517 of 518 at every
non-09:20 checkpoint, per §6). The **1-instrument gap** (whatever caused
it to never reach candidate-row construction at all) has **no persisted
reason code anywhere in this schema** — its own specific
`HardIneligibilityReason` (or an even earlier universe/mature-history
exclusion) is not durably recorded. This is reported as a genuine gap in
per-instrument diagnostic granularity, not fabricated.

---

## 9. Checkpoint reference / staleness audit (§9)

Concepts kept precisely distinct, per source:

- **`max_staleness_minutes = 30.0`** (`config/emr/operational.json`) —
  the M5-candle-vs-checkpoint staleness gate `evaluate_candidate_eligibility`
  applies (§7/§8 above).
- **`MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS = 300.0`** — a frozen
  Python constant in `checkpoint_reference_price.py` (confirmed
  unchanged, not a config field, per EM-7B.1's own authority
  correction), governing how old a captured *quote* observation may be
  relative to the checkpoint instant before being rejected as a
  reference price.
- **`checkpoint_price_latency_seconds`** (persisted per candidate row) —
  the actual measured gap between a captured quote's own
  snapshot/last-trade time and the checkpoint instant. Observed
  per-checkpoint averages: 09:30 7.85s, 09:45 18.52s, 10:00 30.17s,
  10:30 20.70s, 11:00 15.38s, 12:00 26.88s, 13:00 19.58s, 14:00 32.06s —
  all comfortably under the 300s bound, with per-row maxima up to 391s
  observed at 14:00 (a small number of individual instruments whose own
  quote was older, still well-described as legitimate, bounded quote
  latency, never a run-level failure).
- **No persisted checkpoint-reference-price rejection/failure count**
  exists as a separate field — `checkpoint_price` is non-NULL for
  100% of all 65,142 FRESH rows and all 9,306 STALE rows alike (9,306
  at 12:00 confirmed non-NULL directly), meaning the checkpoint-price
  collector itself never failed to obtain a price for any tracked
  instrument this session — the 12:00 exclusion is exclusively the
  separate M5-staleness gate, not a reference-price failure.

**These are not the same concept and were not conflated:** staleness
(minutes-scale, M5-candle-based) is what excluded every instrument at
12:00; checkpoint observation delay (seconds-scale, quote-based) never
triggered a rejection anywhere in this session's evidence.

---

## 10. Provider accounting (§10)

Per-checkpoint, directly persisted (never extrapolated from the 09:20
canary alone):

| Checkpoint | `quote_request_count` | `quote_capture_duration_ms` | `total_duration_ms` |
|---|---:|---:|---:|
| 09:20 | 136 | 301,460.68 | 310,920.15 |
| 09:30 | 134 | 301,306.21 | 312,467.18 |
| 09:45 | 134 | 300,200.70 | 311,822.75 |
| 10:00 | 136 | 302,015.12 | 315,346.66 |
| 10:30 | 134 | 300,993.52 | 319,619.75 |
| 11:00 | 135 | 301,839.02 | 316,487.96 |
| 12:00 | 143 | 300,985.65 | 316,661.07 |
| 13:00 | 143 | 301,856.34 | 317,885.83 |
| 14:00 | 142 | 302,250.90 | 317,991.49 |

`quote_request_count` (134–143, tightly clustered — the milestone's
own cited "136" for 09:20 is representative, not an outlier) and
`quote_capture_duration_ms` (~300,200–302,250ms ≈ 300–302 seconds,
remarkably stable across every checkpoint including 09:20 and 12:00) —
**the provider/collector subsystem's own behavior was completely
unaffected by either the 09:20 or the 12:00 M5-staleness event**,
confirming the two are independent subsystems exactly as designed.
**No persisted provider *failure* count field exists** on
`emr_scan_runs` (`failure_type`/`failure_reason` are both `NULL` on
every row) — no provider failure is claimed or was observed. **No
internal retry count is claimed or measurable** from this schema,
consistent with the same limitation already documented for the main
pipeline (ID-7P0.2).

---

## 11. Regime lookup (§11)

**`REGIME_LOOKUP_EXERCISED_SUCCESSFULLY`** — confirmed directly, not
inferred. `scanner.py:343` calls `regime_lookup(config.session_date)`
unconditionally while building every tracked instrument's evidence row
(i.e. whenever candidate-row construction runs at all — every
checkpoint except 09:20). A sampled real `logit_contributions_json`
(10:00, `NSE:360ONE`, `TOUCH`/5%) shows real, non-trivial one-hot regime
terms actually selected for that checkpoint —
`regime_trend__SIDEWAYS=1.0`, `regime_volatility__LOW_VOLATILITY=1.0`,
`regime_gap__NO_GAP=1.0` (all other regime one-hot terms correctly
`0.0`) — proving the regime path returned real, checkpoint-specific
classification data that flowed into the model's own feature vector,
not a placeholder/missing value. **518×8 (minus the 1-instrument gap)
= 4,136 eligible-path observations across the 8 candidate-producing
checkpoints all exercised this same path** (regime lookup is called for
every tracked instrument regardless of that instrument's own
eligibility outcome, since it happens before the eligibility gate is
applied per-family/threshold). `REGIME_ELIGIBLE_PATH_NOT_OBSERVED` does
**not** apply — the path was directly observed with real data.

---

## 12. Candidate distribution (§12)

- **Total candidate rows**: 74,448 (8 candidate-producing checkpoints ×
  9,306).
- **By checkpoint**: 9,306 at each of 09:30, 09:45, 10:00, 10:30, 11:00,
  12:00, 13:00, 14:00; 0 at 09:20.
- **By family/threshold** (3 families × 6 thresholds = 18 combinations,
  4,136 rows each — 517 instruments × 8 checkpoints): `CLOSE`
  {5,8,10,12,15,20}%, `OPEN_TO_HIGH` {5,8,10,12,15,20}%, `TOUCH`
  {5,8,10,12,15,20}%. No "direction" (LONG/SHORT) field exists in this
  schema — EMR's own family taxonomy (an upward-move-detection design,
  per the frozen EM-1/EM-4 methodology) encodes move-type, not a
  directional trade side.
- **`probability_language`**: 100% `calibrated_probability` — every
  single observation this session used the fully-calibrated model
  tier, never the lower-fidelity `raw_estimate` fallback.
- **`feasibility`**: 100% `FEASIBILITY_UNKNOWN` — expected and
  documented (`eligibility.py:46-54`): no circuit-limit/price-band data
  source exists anywhere in ATHENA today, so this is honest absence, not
  a defect.
- **State distribution** (all 74,448 rows): `INACTIVE` 43,810;
  `INVALIDATED` 27,792; `FADING` 825; `DEVELOPING` 663; `CONFIRMED` 462;
  `HIGH_CONVICTION` 301; `WATCH` 374; `TARGET_REACHED` 221 — every
  state in the frozen state machine is represented with real production
  evidence.
- **`TARGET_REACHED` by family/threshold**: `OPEN_TO_HIGH` 5% → 69,
  8% → 9, 10% → 5, 12% → 5, 15% → 5 (0 at 20%); `TOUCH` 5% → 89,
  8% → 22, 10% → 6, 12% → 6, 15% → 5 (0 at 20%). `CLOSE` family: 0
  `TARGET_REACHED` observations this session.

This is evidence inventory only — no candidate is interpreted as a
profitable trade, and no new threshold was introduced or evaluated.

---

## 13. Transition audit (§13)

- **Total transitions**: 10,922.
- **Types observed** (from→to, count): the full frozen state machine's
  transition set is represented, including `INACTIVE→INVALIDATED` (8,615,
  the dominant pattern — most tracked instruments never develop),
  `INACTIVE→WATCH` (317), `INACTIVE→DEVELOPING` (276), `WATCH→CONFIRMED`
  (100), `WATCH→FADING` (128), `WATCH→DEVELOPING` (124),
  `DEVELOPING→FADING` (213), `DEVELOPING→INVALIDATED` (166),
  `DEVELOPING→CONFIRMED` (66), `CONFIRMED→HIGH_CONVICTION` (141),
  `CONFIRMED→INVALIDATED` (98), `CONFIRMED→TARGET_REACHED` (14),
  `HIGH_CONVICTION→TARGET_REACHED` (18), `HIGH_CONVICTION→INVALIDATED`
  (74), `FADING→INVALIDATED` (295), `FADING→DEVELOPING` (46), and
  several smaller-count patterns (full table in §12's underlying query;
  every transition is a genuinely reachable edge in the frozen state
  machine — none unexpected).
- **Linkage integrity**: 0 orphan transitions (§5); every transition's
  `(run_id, instrument_id, family, threshold_percent)` corresponds to a
  real, coherent candidate lineage — `sequence_number` increments
  strictly per that lineage's own history length at write time (per
  `scanner.py:466`, `sequence_number = len(history) + 1`), never
  independently assigned.
- Ordering/coherence: transitions only ever fire when
  `transition.to_state != prior_state` (`scanner.py:462`) — confirmed
  structurally, not just counted.

---

## 14. TOUCH-10 (§14)

`TOUCH` family at `threshold_percent=10` (the dashboard's own
"Touch-10 Radar" naming): **4,136 total observations** across the 8
candidate-producing checkpoints (517 × 8). State breakdown:
`INACTIVE` 2,437; `INVALIDATED` 1,548; `FADING` 45; `DEVELOPING` 37;
`CONFIRMED` 25; `WATCH` 20; `HIGH_CONVICTION` 18; **`TARGET_REACHED` 6**
— genuine TOUCH-10 target-reached evidence exists (6 observations). No
precision/lift/profitability is computed from this — inventory only.

---

## 15. Profitability/outcome-analysis absence confirmation (§15/§41)

**No T1/T2/target-hit rate, win rate, PnL, expectancy, MFE, MAE,
precision, recall, lift, or false-positive rate was calculated anywhere
in this audit.** `TARGET_REACHED` counts (§12/§14) are reported as
*persisted operational state labels* only (the state machine's own
terminal-state name), never interpreted as a profitability or
correctness claim. The question this milestone answers is evidence
*readiness*, not EMR *profitability*.

---

## 16. Session completeness (§16)

**2026-09-04: `COMPLETE_FOR_OPERATIONAL_AUDIT`.** All 9 frozen
checkpoints present, zero run-level failures, zero persistence-integrity
defects, a full real state-machine transition population, and two
genuinely distinct, source-explained M5-availability episodes (09:20
structural/expected, 12:00 transient/correlated-but-real) rather than
silence or ambiguity. This one session is **not** treated as
statistically sufficient on its own (§17) — it is a single, complete,
internally coherent operational sample, not a multi-session population.

---

## 17. Statistical-readiness classification

**Evidence dimensions currently represented:** all 9 checkpoints; a
full, real state-machine population (all 8 states, transitions between
every reachable pair observed); all 3 families × 6 thresholds (18
combinations) with real calibrated probabilities and real logit
contributions; a real, non-degenerate regime-feature population (all
three regime dimensions — trend/volatility/gap — exercised with
genuine, varying one-hot values); a real `TARGET_REACHED` population
across multiple families/thresholds including `TOUCH-10`; two
genuinely distinct data-availability failure episodes, both correctly
and honestly attributed rather than silently smoothed over; zero
persistence/atomicity/duplicate/orphan defects.

**Evidence dimensions still absent or sparse:** only one calendar
session exists — zero cross-session variation (different market
regimes on different days, day-of-week effects, multi-day
candidate-lifecycle continuity) has been observed yet; the 1-instrument
universe/mature-history gap has no persisted specific reason; the
09:20/12:00 STALE_DATA episodes cannot be sub-classified between
"no candle at all" vs. "candle present but too old" from persisted
data alone; no SHORT-side or down-move family exists in EM-5's own
design (out of scope for this audit, an inherited methodology
characteristic, not a defect).

**Classification: B — `OPERATIONALLY_SOUND_BUT_NOT_YET_STATISTICALLY_READY`.**

Production behavior is structurally sound (zero integrity defects, 100%
checkpoint coverage, every architectural subsystem — eligibility,
regime lookup, calibration, state machine, provider/quote collection —
demonstrated exercising real logic on real data), but the evidence is
still a **single calendar session**. No arbitrary minimum session count
is asserted here (per this milestone's own §18 instruction) — the
observed gap is qualitative (zero cross-session variation observed
yet), not a missing count against an invented number. Natural
accumulation should continue unchanged; a future EM-7D1 (or similar)
should define its own sample-sufficiency contract once more sessions
exist, mirroring how ID-6E's own precedent staged canary → one full
session → multi-session review before closing its own track.

**Outcome A** (`EVIDENCE_READY_FOR_MULTI_SESSION_EM7D_VALIDATION`) is
not yet chosen because "multi-session" itself requires more than one
session to exist, which it does not yet. **Outcome C**
(`PRODUCTION_EVIDENCE_DEFECT_REQUIRES_CORRECTION`) is explicitly
rejected — no defect was found; the 12:00 episode is a real,
understood, cross-system timing characteristic (correlated with a
known REFRESH-cycle gap), not a persistence, integrity, or code defect.

---

## 18. Natural accumulation / isolation confirmations

- `config/emr/operational.json` read only, values unchanged
  (`enabled: true`, `athena_core`/`v1`, `max_staleness_minutes: 30.0`,
  `poll_interval_seconds: 30.0`).
- `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS = 300.0` read only,
  unchanged.
- No scanner code executed by this audit; no artificial/backdated scan
  triggered.
- `db/emr.db` opened only via `mode=ro` + `PRAGMA query_only=ON`;
  observed file size 651.2 MB, `-wal` 85.9 MB, `-shm` 192 KB, both
  before and after this audit's own queries — unchanged.
- `db/athena.db` (queried only for the independent REFRESH-cycle
  cross-reference in §7) remains exactly as ID-7F2 left it:
  `schema_version = 17`, PID 2453 untouched, the ID-7F2 pre-migration
  backup untouched and not referenced by this milestone at all. ID-7F2
  remains **PRE-ACTIVATION PREPARATION COMPLETE / PRODUCTION ACTIVATION
  DEFERRED / OPEN** — unaffected by this EMR audit.
- No DarvaX source, config, database, or runtime action of any kind.

---

## 19. Recommended next EMR milestone (recommendation only)

Continue natural production accumulation unchanged through additional
real trading sessions (no action needed to enable this — it is already
active). Once at least a small number of additional complete sessions
exist, spanning some real day-to-day variation, authorize a follow-up
read-only audit (or proceed directly to defining the EM-7D statistical-
validation contract itself) to determine actual sample sufficiency —
never against an invented fixed number, per this milestone's own
instruction, but against the real cross-session evidence dimensions
accumulated by then.
