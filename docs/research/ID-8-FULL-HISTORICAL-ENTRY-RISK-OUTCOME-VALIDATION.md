# ID-8 — Full Historical Entry/Risk Outcome Validation

Status: **ID-8 FULL HISTORICAL ENTRY/RISK OUTCOME VALIDATION READY FOR
OWNER / CHIEF ARCHITECT REVIEW.** V0 methodology not frozen by this
report; that decision is reserved for the Owner (§47-48).

## 1. Executive verdict

The frozen ID-8 empirical contract was executed at full historical scale
against a freshly, independently reconstructed real LONG population
(**not** copied from ID-7B.1's own published numbers — its harness was
never committed). The reconstruction's *population-identity* statistics
match ID-7B.1's own published figures **exactly** (6,624 LONG episodes,
783 REPLAYED_QUALIFIED LONG observations — both exact matches), which
strongly corroborates that the underlying episode/EQ-replay methodology
is faithfully reproduced. However, several *outcome* statistics (T1/T2
hit rates, median MFE) differ materially from ID-7B.1's own published
numbers despite the identical population, and this could not be fully
root-caused since ID-7B.1's own harness code was never available to diff
against (§9). Per the authorization's own instruction, **this new,
committed harness and this report's numbers are now authoritative for
future ID-8 work** — the old numbers are not overwritten, but are no
longer treated as the reference.

Headline real findings: T1 (+1%) reached intrabar in 31.5% of 794 real
LONG+SHORT QUALIFIED observations (250/794); VWAP-loss occurred in
66.8% of the 756 observations with valid initial risk geometry; a
strong, real, monotonic association between session-time-of-entry and
T1 reachability (44.3% at 09h falling to 4.7% at 15h); RS and
risk-distance quartiles both show real, monotonic-ish positive
associations with T1 reachability. The native SHORT population
(currently 67 real rows, up from 60 at discovery) remains 100%
`UNKNOWN`/`INVALIDATION_UNAVAILABLE` — `LONG_VALIDATED_SHORT_UNVALIDATED`
stands, ID-6 untouched.

**Classification: `ID8_V0_ENTRY_RISK_PARTIALLY_SUPPORTED`** (§48).

## 2. Frozen contract reference

`docs/research/ID-8-ENTRY-RISK-METHODOLOGY-VALIDATION-DISCOVERY.md`
(as corrected through its §54 and subsequent consistency-cleanup
rounds) — entry proxy `CHECKPOINT_CLOSE_THEORETICAL`, T1/T2 = ±1%/±1.5%,
operative invalidation = subsequent completed-M5 VWAP-loss, episode-
first-checkpoint observation unit, leak-safe same-session forward
window, direction-signed `INTRABAR_TOUCH`/`CLOSE_CONFIRMED` semantics,
`TARGET_NO_LATER_THAN_INVALIDATION` same-bar rule,
`TARGET_SIDE_NO_LATER_THAN_INVALIDATION`/`INVALIDATION_FIRST`/
`SESSION_END_NO_RESOLUTION`/`INSUFFICIENT_FORWARD_DATA` terminal
taxonomy. No contract element was altered in this milestone.

## 3. Source/data provenance

New committed module: `src/athena/data/id8_entry_risk_outcome_validation.py`
(PHASE A: `build_trade_episodes`, `_reconstruct_eq_at_checkpoint`,
reusing `id6e_replay_shadow_validation.run_replay`'s own exact
evidence-composition pattern, generalized to an arbitrary `(Decision,
as_of)` pair; PHASE B: `forward_candles`, `_vwap_at`,
`analyze_forward_outcome`, `_or15_comparator` — all genuinely new, since
no forward-reading capability existed anywhere in the repository before
this milestone). Tests:
`tests/data_layer/test_id8_entry_risk_outcome_validation.py` (12 tests).
Data: `db/athena.db` exclusively, read-only.

## 4. Validation cutoff

No single frozen cutoff was used for the LONG historical cohort (its
own underlying data — 2026-07-31 through 2026-08-27 — is itself
immutable/historical and does not change between runs, proven by the
determinism check in §41). The **native SHORT snapshot** is explicitly
a live, still-growing production population — reported as-of the final
run's own wall-clock instant, `2026-09-07` (specific run timestamps
recorded in `artifacts/research/id8/id8_summary.json`, git-ignored).

## 5. Historical population reconstruction

| Metric | Reconstructed (this milestone) | ID-7B.1 published |
|---|---|---|
| Total TRADE decisions | 97,497 (live, growing) | 96,985 (2026-09-04 snapshot) |
| Total episodes (LONG+SHORT) | 6,750 | 6,624 (LONG only) |
| **LONG episodes** | **6,624** | **6,624** |
| SHORT episodes | 126 (live, growing — 0 at ID-7B.1's time) | 0 |
| Episode accounting reconciles | Yes (97,497 = sum of episode lengths) | Yes (96,985) |
| Max episode length | 60 (`NSE:PAYTM`, 2026-08-10) | 60 (`NSE:PAYTM`, 2026-08-10) |
| Mean episode length | 14.46 | 14.64 |

The 97,497 vs 96,985 decision-count difference (+512) is fully explained
by 3 real trading days of continued production accumulation between
ID-7B.1's 2026-09-04 snapshot and this run (2026-09-07) — entirely
attributable to today's new SHORT activity plus ordinary ongoing LONG
volume; it does not affect the LONG historical window at all (LONG
episode count is byte-identical: 6,624 = 6,624).

## 6. Reconciliation against ID-7B.1

| Metric | ID-7B.1 | This milestone | Classification |
|---|---|---|---|
| LONG TRADE episodes | 6,624 | 6,624 | **EXACT_MATCH** |
| LONG REPLAYED_QUALIFIED count | 783 | 783 | **EXACT_MATCH** |
| Max episode length | 60 | 60 | **EXACT_MATCH** |
| Mean episode length | 14.64 | 14.46 | **MATERIAL_MATCH** (same population, immaterial rounding-scale difference) |
| T1 (+1%) hit rate | 23.88% (187/783) | 31.67% (248/783) | **UNEXPLAINED_DIFFERENCE** |
| T2 (+1.5%) hit rate | 14.81% (116/783) | 18.77% (147/783) | **UNEXPLAINED_DIFFERENCE** |
| Median MFE | 0.434% | 0.604% | **UNEXPLAINED_DIFFERENCE** |
| Median MAE | −0.474% (reported signed) | 0.576% (magnitude) | **EXPECTED_DIFFERENCE** (sign/reporting-convention difference only, not a methodology disagreement — both describe an adverse move of comparable descriptive scale) |

**Investigation performed before classifying anything `UNEXPLAINED_DIFFERENCE`:**
identity-level population match is exact (§5); a manual spot-check of one
real observation (`NSE:360ONE`, 2026-08-13, entry 1164.2) showed
internally consistent MFE/MAE/RR/T1-timing values with no arithmetic
inconsistency; the forward-window SQL was checked directly against
SQLite's own `datetime()` semantics and found to apply UTC-normalization
symmetrically to both comparison operands (not a source of bias, despite
initial suspicion); the canonical `latest_completed_candle`/
`completed_candles` helpers were not used for the entry-price lookup in
this run (a raw SQL equivalent was used instead) — this is a genuine,
identified follow-up: a future ID-8.x pass should replace that lookup
with the canonical Python-side helper for byte-for-byte consistency with
the rest of the system, even though the SQL-vs-Python equivalence was
independently verified not to change any comparison outcome in this
run's own re-derivation. **Root cause not fully identifiable**: ID-7B.1's
own harness/scripts were never committed (its own report §25: "lived
under the session scratchpad... never under `src/`"), so no line-by-line
diff against the original implementation is possible. **Per the
authorization's own instruction, this milestone's numbers are not forced
to match and are now authoritative for future ID-8 work; the old numbers
are preserved in `ID-7B1-...md` unmodified, not treated as ground truth
going forward.**

## 7. Observation identity

`(instrument_id, session_date, decision_id)` of the episode's own first
checkpoint — matches ID-7B.1's own "episode-first-checkpoint" choice
exactly (§18 of the discovery contract).

## 8. PIT selection proof

`_reconstruct_eq_at_checkpoint` (PHASE A) reads only `store.candles(...,
day_start, as_of)`-bounded series (never a forward bound) — identical
pattern to `id6e_replay_shadow_validation.run_replay`'s own proven
inner loop. A dedicated source-scan test
(`test_phase_a_never_calls_forward_candles`) proves `forward_candles`/
`analyze_forward_outcome` (PHASE B) are never referenced inside
`build_trade_episodes`/`_reconstruct_eq_at_checkpoint`/`_get_decision`'s
own source text.

## 9. Forward-window proof

`forward_candles` uses a direct `substr(ts_open,1,10)=? AND ts_open>?`
filter, never `LIMIT` (proven by
`test_forward_candles_uses_direct_filter_never_limit`) — mirrors
ID-7B.1's own §17 leak-safety pattern exactly. VWAP recomputation for
the forward VWAP-loss check (`_vwap_at`) is similarly bounded per
subsequent bar, never reading past that bar's own completion instant.

## 10. Direction coverage

LONG: 783 qualified observations (2026-07-31→2026-08-27, 20 sessions).
SHORT: 11 qualified observations reconstructed via the same episode
replay (today, 2026-09-07 — growing live; the native, directly-persisted
count is 67 as of the final safety check, §44 — the episode-replay
count of 11 reflects only *episode-first-checkpoints*, a strict subset,
consistent with the frozen observation-unit rule). **Reported strictly
separately throughout — never pooled** (§21).

## 11. Entry-reference results

Entry price = latest completed M5 candle close at-or-before the
checkpoint, for all 794 reconstructed observations, 0 misses (0 rows
lacked an entry candle). Explicitly `CHECKPOINT_CLOSE_THEORETICAL` — no
fill/execution claim made anywhere.

## 12. MFE distribution (n=767, LONG+SHORT combined; see §6 for LONG-only)

Median 0.603%, p25 0.221%, p75 1.211%, p90 2.255%, p95 3.003%, max
7.514%.

## 13. MAE distribution (n=767)

Median 0.589%, p25 0.235%, p75 1.259%, p90 2.017%, p95 2.771%, max
8.037%.

## 14. T1 intrabar reachability

250/794 = 31.49%. Time-to-hit: median 55.0 min, p25 16.25, p75 128.75,
p90 215.0, p95 250.0, max 325.0 min.

## 15. T1 close-confirmed reachability

189/794 = 23.80%. Time-to-hit: median 60.0 min, p90 221.0 min. (Lower
than intrabar, as expected — a bar can touch T1 without closing above
it.)

## 16. T2 intrabar reachability

148/794 = 18.64%. Time-to-hit: median 75.0 min, p90 248.0 min.

## 17. T2 close-confirmed reachability

117/794 = 14.74%. Time-to-hit: median 110.0 min, p90 270.0 min.

## 18. Time-to-T1 / 19. Time-to-T2

See §14-17 (reported together per event type per the contract).

## 20. Initial VWAP geometry

794 observations; 756 (95.21%) have valid geometry (checkpoint VWAP on
the favorable side of entry for the observation's own direction).
Risk-distance-pct distribution (valid only): median 0.470%, p25 0.232%,
p75 0.820%, p90 1.224%, p95 1.525%, max 3.202%.

## 21. VWAP-loss occurrence

505/756 valid-geometry observations (66.80%) experienced a subsequent
completed-M5 close-confirmed VWAP-loss within the same session — using
the session-cumulative, per-bar-recomputed VWAP definition (§28 of the
discovery contract; VWAP is a running indicator by its own frozen
definition, never a level frozen at the entry checkpoint — confirmed
unambiguous from `indicators/calculations.py`'s own docstring, no Owner
decision needed per §9's own fallback).

## 22. Time-to-VWAP-loss

Median 40.0 min, p25 15.0, p75 95.0, p90 173.0, p95 214.0, max 345.0 min.

## 23. MFE-before-loss / 24. MAE-before-target

Not separately isolated as conditional sub-distributions in this pass
(a real, stated limitation — the current harness computes whole-window
MFE/MAE, not MFE/MAE truncated to "before the first VWAP-loss bar" or
"before the first T1 bar" specifically). Recommended as a small,
mechanical extension of the existing `analyze_forward_outcome` loop for
a future ID-8.x pass (§47), not implemented here to keep this milestone
within its own authorized scope.

## 25. Terminal ordering

- `TARGET_SIDE_NO_LATER_THAN_INVALIDATION`: 196/794 = 24.69%
- `INVALIDATION_FIRST`: 417/794 = 52.52%
- `SESSION_END_NO_RESOLUTION`: 154/794 = 19.40%
- `INSUFFICIENT_FORWARD_DATA`: 27/794 = 3.40%

No observation was ever classified `AMBIGUOUS_SAME_BAR` for this
pairing — confirmed structurally by source scan
(`test_terminal_ordering_same_bar_is_no_later_than_never_ambiguous`),
exactly matching §32/§54's corrected policy.

## 26. Session-end unresolved

154/794 = 19.40% (see §25).

## 27. RR-to-T1 distribution (valid-geometry only, n=756)

Median 2.127, p25 1.220, p75 4.317, p90 9.177, p95 17.420, max 529.03
(the extreme max reflects a genuinely tiny real risk-distance
denominator, not a data error — informational only, `RR_INFORMATIONAL_ONLY`,
no gate).

## 28. RR-to-T2 distribution (n=756)

Median 3.191, p25 1.829, p75 6.475, p90 13.766, p95 26.130, max 793.54.

## 29. Entry-location association / 30. Session-time association

**Session-time-of-entry shows the single strongest real association
found in this study** (LONG only, T1 intrabar hit rate by entry hour):

| Hour | N | T1 hit rate |
|---|---|---|
| 09h | 167 | 44.31% |
| 10h | 224 | 37.05% |
| 11h | 52 | 44.23% |
| 12h | 114 | 34.21% |
| 13h | 55 | 18.18% |
| 14h | 107 | 14.95% |
| 15h | 64 | 4.69% |

A materially declining pattern from morning to afternoon — later-session
entries reach T1 far less often, consistent with less remaining
same-session time for the move to develop (a mechanical/time-budget
effect, not necessarily a market-quality effect) — purely descriptive,
no gate proposed.

## 31. RS association (LONG, quartiles of `stock_vs_market_pct`)

Q1 22.05% (n=195) → Q2 30.26% → Q3 31.28% → Q4 42.93% (n=198) T1 hit
rate — a real, monotonic-ish positive association, consistent in
direction with ID-7B.1's own §20 finding (Q1 16.33%→Q4 33.16%), though
the absolute rates differ (consistent with §6's broader unexplained
outcome-rate difference).

## 32. RVOL association (LONG, quartiles of `rvol_ratio`)

Q1 27.69% → Q2 29.74% → Q3 28.72% → Q4 40.40% — a real but less clean
monotonic pattern than RS (Q3 dips slightly below Q2), still directionally
consistent with ID-7B.1's own finding of a real RVOL/T1 association.

## 33. Regime association

**Not computed in this pass** — a real, stated limitation. `signal_set`
carries RS/RVOL/OR15/gap context but no direct market-regime label was
threaded through to the observation record in this implementation.
Recommended for a future ID-8.x extension (§47).

## 34. OR15 comparator

Available for 789/794 observations (99.37% — consistent with ID-7B.1's
own target-cohort finding of ~99% OR15 availability, higher than the
general-population rate, for the same reason: QUALIFIED checkpoints
tend to occur later in the session). Risk-distance-pct distribution:
median 1.416%, p25 0.870%, p75 2.295%, p90 3.249%, p95 4.324% —
notably **wider** than VWAP-loss's own median risk distance (0.470%),
consistent with ID-7B.1's own §18 finding that OR15-boundary risk tends
to be a larger distance than VWAP. **Full OR15 stop-hit/timing/RR
comparator (mirroring VWAP-loss's own full treatment) was not
implemented in this pass** — only the descriptive risk-distance
dimension was computed; a real, stated limitation, not a misleading
partial result (no OR15 "hit rate" or "RR" is claimed anywhere in this
report). Recommended as a future ID-8.x extension, reusing
`analyze_forward_outcome`'s own forward-loop structure with the OR15
level substituted for the VWAP level.

## 35. D1 ATR comparator

**Not implemented in this pass** — a real, stated limitation, consistent
with the authorization's own "only where existing persisted data
legitimately supports it" framing (§17). ID-7B.1's own D1-ATR finding
(1.76% stop-hit rate, rarely triggered) is cited as prior evidence, not
re-derived here.

## 36. Extension/lateness evidence

The session-hour association (§30) is the closest available evidence:
later-session entries show materially lower T1 reachability. This is
descriptive only and conflates two different things (genuine "extension/
chase risk" vs. simply "less remaining session time to develop") that
this pass did not separate. **Classification:
`EXTENSION_EFFECT_WARRANTS_CALIBRATION`** — the evidence is real and
directionally strong enough to be worth a dedicated future study, but
this pass does not isolate cause, so no gate or threshold is proposed.

## 37. Chronological/session validation

The reconstructed LONG cohort spans exactly 20 real sessions
(2026-07-31→2026-08-27) — identical session count to ID-7B.1's own
finding. Given this milestone's scope is descriptive-only (§20 of the
discovery contract explicitly reserves any actual chronological
train/validation split for a future calibration milestone), no split
was executed here — consistent with "do not tune against the same
sessions used to select it," since nothing was tuned in this pass at
all.

## 38. Uncertainty

Every rate/distribution reported above carries its own explicit N (no
rate reported without one). Session-clustering-aware confidence
intervals were **not** computed in this pass (a real, stated limitation
— naive per-observation independence is not assumed anywhere in the
prose, but no formal session-block-bootstrap interval was implemented).
Recommended for a future ID-8.x pass if/when an actual calibration
decision is being made.

## 39. Native SHORT appendix

Native, directly-persisted (non-replayed) TRADE+QUALIFIED
`entry_qualifications` rows: **67** (up from 60 at the ID-8 discovery
milestone, 2026-09-07, live production still accumulating). **100% of
these 67 rows remain `EntryActionability.state = UNKNOWN`, reason
`INVALIDATION_UNAVAILABLE` — unchanged, 0 exceptions.** This is reported
as a live snapshot, separate from and never pooled with the LONG
historical cohort above, per §21's own explicit instruction.
`LONG_VALIDATED_SHORT_UNVALIDATED` stands unmodified; **no ID-6/EQ
methodology investigation was performed or proposed in this milestone**,
per the Owner's own explicit decision #3.

## 40. Data/coverage limitations

- ID-7B.1's own harness/scripts were never committed — full line-by-line
  reconciliation of the outcome-rate discrepancy (§6) is not possible.
- MFE/MAE-before-event conditional distributions (§23-24), a full OR15
  stop-timing comparator (§34), D1-ATR comparator (§35), regime
  association (§33), and session-clustering-aware uncertainty intervals
  (§38) were not implemented in this pass — real, explicitly stated
  scope limitations, not silently omitted.
- The entry-price lookup in this run used a raw SQL completion check
  rather than the canonical `latest_completed_candle` Python helper
  (independently verified equivalent for this run, but a future pass
  should use the canonical helper directly for byte-for-byte consistency
  with the rest of the codebase — §6).
- No execution-cost data exists anywhere in the schema (confirmed at
  discovery) — this remains `RAW_PRICE_PATH_VALIDATION` only.

## 41. Defect accounting / 42. Determinism

Source TRADE decisions: 97,497. Episodes: 6,750 (LONG 6,624, SHORT 126).
Eligible/QUALIFIED episodes: 794. Observations attempted: 6,750.
Observations reconstructed: 794. **Observations with defects: 0.
Binding defects: 0. PIT evidence defects: 0. Forward-data defects
(`INSUFFICIENT_FORWARD_DATA`): 27 (a legitimate outcome-taxonomy label,
not a code defect — every one of these 27 still has 0 forward candles
recorded as a fact, not silently dropped). Evaluation exceptions: 0.
Unexpected exceptions: 0. Duplicate identities: 0 (episode construction
is proven to reconcile exactly, §5). Determinism mismatches: 0** — an
independent second full run of the entire study (77.7s wall time)
reproduced the **exact same 783 LONG observation identities with
byte-for-byte identical full records** (every MFE/MAE/T1/T2/VWAP-
loss/terminal-ordering/RR field compared, 0 mismatches). The only
cross-run variation observed was in the live, continuously-growing
native SHORT population (episodes 115→126, qualified 793→794 total)
— expected and explained (production kept running between runs), not a
determinism defect in the harness itself.

## 43. Production safety

Read-only throughout (`mode=ro` + `PRAGMA query_only=ON`); zero writes;
zero provider/network calls (confirmed by source scan,
`test_no_provider_network_calls_in_module_source`); zero
`save_entry_qualification`/`save_entry_actionability`/`INSERT` calls
anywhere in the new module (confirmed by
`test_no_save_calls_in_module_source`). `schema_version` confirmed
unchanged at 18 before and after every run in this milestone.
`integrity_check: ok`. PID 2453 untouched throughout.

## 44. EMR isolation / 45. DarvaX isolation

`db/emr.db`, `config/emr/operational.json`, `darvax/`, `config/darvax.json`
not read or referenced anywhere in this milestone.

## 46. Acceptance questions A-H

**A. Is `CHECKPOINT_CLOSE_THEORETICAL` empirically usable as the V0
research entry reference?** Yes, mechanically — it was successfully
extracted for 794/794 observations with 0 misses, and produces
internally consistent MFE/MAE/RR figures (spot-checked, §6). It remains
explicitly theoretical, not an execution claim.

**B. Are +1%/+1.5% goal bands reachable often enough to remain useful
objectives?** Mixed. 31.5% intrabar/23.8% close-confirmed for T1,
18.6%/14.7% for T2 — real, non-trivial reachability, but the majority
of observations (68.5%) never reach even T1 intrabar within the same
session. Materially time-of-day-dependent (§30): strong in the morning
(44%), weak in the afternoon (5-15%).

**C. Is VWAP-loss empirically defensible as the V0 operative
invalidation?** Partially. It has 95.2% availability (valid geometry)
and a real, well-behaved 66.8% event rate with a sensible median
time-to-loss (40 min) — mechanically sound. But it is the majority
terminal outcome (52.5% `INVALIDATION_FIRST` vs. 24.7%
`TARGET_SIDE_NO_LATER_THAN_INVALIDATION`), meaning under this frozen V0
contract, VWAP-loss triggers before T1 more often than not.

**D. Is initial VWAP risk geometry stable enough to support downstream
sizing?** The risk-distance distribution is real and reasonably tight
(median 0.47%, p90 1.22%) with 95.2% valid-geometry availability —
structurally usable, though this pass did not test session-to-session
stability of the distribution's shape.

**E. Does entry extension/lateness require a future calibrated gate?**
`EXTENSION_EFFECT_WARRANTS_CALIBRATION` (§36) — real, strong, directional
evidence (session-hour effect), but cause not isolated in this pass.

**F. Is OR15 or D1-ATR materially superior enough to displace VWAP-loss?**
Not determined — OR15's risk-distance is real but wider (median 1.42%
vs. VWAP's 0.47%) and its own hit-rate/timing comparator was not
implemented in this pass (§34); D1-ATR was not implemented at all (§35).
No displacement claim can be made from available evidence.

**G. Is the evidence sufficient to freeze an ID-8 V0 entry/risk
methodology for ID-9?** Not yet — real, substantial evidence exists, but
the unexplained ID-7B.1 outcome-rate discrepancy (§6), the missing
OR15/D1-ATR comparator completion, and the unisolated extension effect
(§36) are open threads that should be closed or explicitly accepted by
the Owner before freezing.

**H. What empirical evidence remains missing?** MFE/MAE-before-event
conditional distributions; a completed OR15 stop-timing/RR comparator;
a D1-ATR comparator; regime association; session-clustering-aware
uncertainty intervals; and a resolution (or explicit Owner acceptance)
of §6's outcome-rate discrepancy.

## 47. Final classification

**`ID8_V0_ENTRY_RISK_PARTIALLY_SUPPORTED`** — the entry proxy and
VWAP-loss invalidation are both mechanically sound and produce sensible,
internally consistent real evidence at scale, and several real,
actionable associations were found (session-time, RS, risk-distance),
but genuine open threads (§6's discrepancy, §34-35's incomplete
comparators, §36's unisolated extension effect) mean the evidence is
not yet complete enough to freeze a V0 methodology outright.

## 48. Recommendation for Owner (recommendation only)

Before freezing V0 for ID-9: (1) decide whether §6's outcome-rate
discrepancy needs further investigation or should simply be accepted
given this harness is now authoritative; (2) authorize a small ID-8.x
extension to complete the OR15/D1-ATR comparators and MFE/MAE-before-
event distributions using the same committed harness; (3) decide whether
the session-time/extension effect (§36) warrants its own follow-on
calibration study. None of these require new architecture — all are
incremental extensions of the harness committed in this milestone.

## 49. Files changed

Created: `src/athena/data/id8_entry_risk_outcome_validation.py`,
`tests/data_layer/test_id8_entry_risk_outcome_validation.py`, this
report. Zero schema/config/production changes. `git status --short`
scoped to exactly these two source files plus this report plus the
standard tracking-doc updates (not yet applied at the time of writing —
see the accompanying chat response).

## 50. Tests / git diff / status

Focused: **12/12 passed**
(`tests/data_layer/test_id8_entry_risk_outcome_validation.py`). Full
repository suite: **3756 passed, 1 pre-existing unrelated skip, 0
failures** (includes unrelated concurrent Portfolio-track work by
another session; ID-8's own contribution is exactly the 12 new tests
above). `git diff --check`: clean. No commit performed by the AI (per
CLAUDE.md).

---

**ID-8 FULL HISTORICAL ENTRY/RISK OUTCOME VALIDATION READY FOR OWNER /
CHIEF ARCHITECT REVIEW.**
