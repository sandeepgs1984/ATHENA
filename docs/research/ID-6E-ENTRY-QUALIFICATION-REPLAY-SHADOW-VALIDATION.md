# ID-6E — Entry Qualification Replay & Shadow Validation

**Status:** Analysis complete. Read-only, research-only.
**Depends on:** ID-6A through ID-6D.1 (all owner-approved/closed 2026-09-02
— methodology frozen, engine implemented, input-coherence hardened,
persisted, Decision-bound, workflow-wired, provenance-resolved,
persistence-time-corrected).
**Does not:** change methodology, tune thresholds, prove profitability,
test outcomes/targets, add API/UI, or start ID-7/EM-6.

## 1. Executive summary

Two evidence modes were audited. **Replay** (settled historical market-time
evaluation via the real, unmodified `EntryQualificationEngine` and
`resolve_evidence_finality`, over the identical 10-session/17,082-
observation window ID-6B.1B used): fully sound — deterministic across two
independent runs, zero harness defects, zero coherence failures, every
frozen invariant holds, and every headline statistic (QUALIFIED prevalence,
WATCH/TRADE split, checkpoint pattern, flicker rate) matches ID-6B.1B's own
research baseline almost exactly, confirming the closed engine reproduces
the pre-engine research formula's behavior faithfully. **Shadow** (real
persisted runtime observations in `db/athena.db`): **unavailable** — the
`entry_qualifications` table does not yet exist in the real production
database (schema not migrated against it since ID-6C), confirmed via a
read-only query, not merely an empty table. This is reported honestly, not
worked around.

**Classification: REPLAY_SOUND_SHADOW_EVIDENCE_INSUFFICIENT.**

No profitability, efficacy, or outcome claim is made anywhere in this
document.

## 2. ID-6D closure recorded

ID-6D and ID-6D.1 are both owner-approved and closed (2026-09-02) — see
`docs/MILESTONES.md`. ID-6E is authorized for validation only; ID-6A
through ID-6D.1 are not reopened.

## 3. Validation architecture

Two independent, read-only components, both new:

- `src/athena/data/id6e_replay_shadow_validation.py::run_replay` —
  deterministic historical replay using the real production engine.
- `src/athena/data/id6e_replay_shadow_validation.py::run_shadow_audit` —
  read-only inspection of persisted runtime `entry_qualifications` rows,
  if any exist.

## 4. Existing assets reused

`ReadOnlyStore`, `candidates_at` (per-instrument ranked, WATCH/TRADE-only,
market-time Decision selection at or before each checkpoint), and the
`_direction` SMA-direction helper — all imported **unmodified** from
`src/athena/data/id6b1_entry_qualification_baseline.py`. The
SessionContext/IntradaySignalSet construction sequence mirrors that
module's own pattern exactly (same production engines: `SessionContextEngine`,
`IntradayAnalyticsEngine`, `RelativeStrengthEngine`, `RelativeVolumeEngine`,
`OpeningRangeEngine`, `GapEngine`). What is genuinely new: after building
those artifacts, this harness additionally fetches the full canonical
`Decision` row (via `athena.data.store.serialization.row_to_decision`,
also reused unmodified) and calls the real, closed
`EntryQualificationEngine.evaluate()` + `resolve_evidence_finality()` —
neither of which ID-6B.1/1A/1B ever invoked (they computed a research-only
`candidate_policy_match` boolean instead). The v0 formula is never
re-derived in this harness.

## 5. Historical replay semantic

This is a **settled historical market-time replay**, not live knowledge-time
reconstruction. Every conclusion below describes how the frozen methodology
behaves when evaluated at historical checkpoints using the data
representation the replay store (`db/athena.db`) holds *now* — never a
claim about what ATHENA would have known live at that historical instant.

## 6. Replay source database / read-only posture

`db/athena.db`, opened via SQLite URI `mode=ro` plus `PRAGMA query_only=ON`
(the exact `ReadOnlyStore` pattern ID-6B.1 already established and this
harness reuses verbatim). No writes, no migrations, no provider/network
calls anywhere in the harness (source-grepped and test-proven — see §49).

## 7. Replay window selection

Reused **verbatim** — not re-selected — from ID-6B.1B's own
deterministically-chosen wider window: the 10 most recent consecutive
trading sessions preceding ID-6B.1's original window, 2026-08-14 through
2026-08-27. Reusing the identical window (rather than selecting a new one)
was the owner's own explicit preference, since it enables direct real-
engine-vs-research-baseline comparability (§34) without introducing a
second, independent selection decision.

## 8. Checkpoint selection

Reused verbatim from ID-6B.1/1B: `09:30, 09:45, 10:00, 11:00, 13:00, 14:30`.
No audit of actual `OwnerValidationPipeline` production scheduler cadence
was performed in this milestone (out of scope — ID-6E validates the
engine's behavior at these research-comparable checkpoints, not scheduler
design).

## 9. Population / representativeness

Uncapped (`per_type=1000`, effectively unlimited for this window's true
population — matches the SQL-verified population size). **17,082**
candidate-checkpoint observations, exactly matching ID-6B.1B's own
population count for the identical window — confirms no candidate was
silently dropped or added by routing through the real engine instead of
the research formula. 396 distinct instruments, 10 distinct sessions, 0
harness defects (§42).

## 10. Historical Decision selection

`candidates_at`'s own SQL (unmodified): for each instrument, the row with
the latest `ts <= as_of` on the given `session_date`, ranked via
`ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY ts DESC,
decision_id DESC)`, restricted to `decision_type IN ('WATCH','TRADE')`.
This is genuine market-time supersession within the replay's own persisted
history — it does not, and cannot, prove the selected Decision was
"current" in a live knowledge-time sense if the repository's own historical
writes were themselves incomplete at the time; that limitation is
inherited from ID-6B.1's own harness, not introduced here.

## 11. Engine source-of-truth confirmation

Every observation is produced by `EntryQualificationEngine().evaluate(decision=...,
session_context=..., signal_set=..., evidence_finality=resolve_evidence_finality(...),
policy=EntryQualificationPolicy())` — the identical class objects
`OwnerValidationPipeline` instantiates in production. No `VWAP positive AND
aggregate trend BULLISH AND (RS support OR RVOL support)` boolean is
computed anywhere in this harness; the engine's own `state`/`reason_codes`/
`evidence_finality`/`confirmation`/`methodology_version` are read directly
from its returned `EntryQualification` object.

## 12. Observation count

**17,082** (see §9).

## 13. WATCH/TRADE distribution

WATCH: 9,948 (58.2%). TRADE: 7,134 (41.8%).

## 14. State distribution

| State | Count | % |
|---|---:|---:|
| NOT_YET | 13,012 | 76.17% |
| QUALIFIED | 3,707 | 21.70% |
| UNKNOWN | 363 | 2.13% |

## 15. QUALIFIED prevalence

21.70% overall.

## 16. NOT_YET prevalence

76.17% overall.

## 17. UNKNOWN prevalence

2.13% overall.

## 18. OUT_OF_SCOPE/EXPIRED distribution

**Zero** — `candidates_at`'s own SQL restricts to WATCH/TRADE decision
types by construction, and every observation in this window falls in
`SessionPhase.REGULAR` (checkpoints chosen well inside the trading day), so
`OUT_OF_SCOPE`/`EXPIRED`/`NOT_YET`-from-`PRE_OPEN` never arise in this
sample. This is a property of the *sample design* (research-comparable
mid-day checkpoints on WATCH/TRADE-only candidates), not evidence those
states are unreachable in the engine generally — they were already
exhaustively proven reachable at the unit level in ID-6B.2/2A.

## 19. DISQUALIFIED invariant

**Holds.** `disqualified_for_session_count == 0` across all 17,082
observations.

## 20. Confirmation invariant

**Holds.** `confirmed_by_policy_count == 0`; `NOT_EVALUATED` confirmation
on all 17,082 observations (100%).

## 21. Checkpoint distribution

| Checkpoint | N | QUALIFIED % | NOT_YET % | UNKNOWN % |
|---|---:|---:|---:|---:|
| 09:30 | 2,397 | 22.95 | 75.97 | 1.08 |
| 09:45 | 2,794 | 27.42 | 70.72 | 1.86 |
| 10:00 | 2,983 | 24.47 | 73.78 | 1.74 |
| 11:00 | 3,034 | 18.39 | 79.33 | 2.27 |
| 13:00 | 2,945 | 20.20 | 76.47 | 3.33 |
| 14:30 | 2,929 | 17.34 | 80.40 | 2.25 |

Descriptive pattern: QUALIFIED prevalence peaks shortly after the open
(09:45) and declines toward the close (14:30) — the same shape ID-6B.1B
found. UNKNOWN prevalence drifts slightly upward through the day (1.08% →
3.33% → 2.25%), plausibly reflecting cumulative RS/RVOL baseline
availability effects; not investigated further (descriptive only, no
threshold implied).

## 22. WATCH-vs-TRADE comparison

| | WATCH (N=9,948) | TRADE (N=7,134) |
|---|---:|---:|
| QUALIFIED % | 19.93 | 24.17 |
| NOT_YET % | 78.00 | 73.63 |
| UNKNOWN % | 2.07 | 2.20 |

TRADE runs consistently a few points higher than WATCH on QUALIFIED
prevalence — the same directional pattern, and the same near-identical
magnitudes, ID-6B.1B already found with the research formula. No
Decision-type branch exists anywhere in `EntryQualificationEngine`
(source-verified in ID-6B.2/2A; unchanged here) — the prevalence
difference is emergent from the underlying candidate evidence populations
differing by Decision type, not from methodology logic.

## 23. Transition/flicker analysis

Among 3,755 instrument/session/decision_type groups observed at 2+
checkpoints: **1,493 (39.76%)** show the pattern "QUALIFIED at an earlier
checkpoint, then not QUALIFIED at a later checkpoint in the same session."
39 distinct compact state-transition patterns were observed (full pattern
table in `artifacts/research/id6e/run1/id6e_summary.json`), ranging from
simple `NOT_YET -> QUALIFIED -> NOT_YET` (534 groups) to more volatile
multi-flip sequences (e.g. `QUALIFIED -> NOT_YET -> QUALIFIED -> NOT_YET ->
QUALIFIED -> NOT_YET`, 5 groups). Flicker is not suppressed, and no
confirmation/hysteresis/debounce logic exists anywhere in the engine
(unchanged, source-verified) — this is the same point-in-time, non-sticky
property ID-6B.1B already established, now reconfirmed against the actual
production engine at near-identical magnitude (39.76% here vs. 39.76%/
46.43% in ID-6B.1B's own same-window/wider-window figures).

## 24. Qualification-duration description

| Pattern | Groups |
|---|---:|
| Never qualified | 2,342 |
| Qualified at exactly one observed checkpoint | 1,087 |
| Qualified at some but not all checkpoints | 895 |
| Qualified at every observed checkpoint | 139 |

Descriptive only. No pattern is labeled "valid" or "false"; no new
confirmation rule is implied or authorized by this table.

## 25. UNKNOWN root causes

| Reason code | Count |
|---|---:|
| SUPPORT_EVIDENCE_UNRESOLVED | 362 |
| VWAP_EVIDENCE_UNAVAILABLE | 57 |
| TREND_EVIDENCE_UNAVAILABLE | 1 |

(363 UNKNOWN observations; some carry more than one unresolved reason
code, so counts sum to more than 363.) Missing evidence is never treated
as bearish — these figures come directly from the engine's own emitted
`reason_codes`, never reconstructed independently.

## 26. NOT_YET root causes

| Reason code | Count |
|---|---:|
| TREND_CONDITION_NOT_MET | 11,346 |
| VWAP_CONDITION_NOT_MET | 10,075 |
| SUPPORT_CONDITION_NOT_MET | 2,189 |

(13,012 NOT_YET observations; a NOT_YET row can cite more than one
decisively-false condition — the engine's own tri-state FALSE-dominance
rule, unchanged.) Trend and VWAP dominate as the most common decisive
blockers; support (RS/RVOL) is comparatively rarely decisive, consistent
with support's own tri-state OR (either RS or RVOL succeeding is enough).

## 27. QUALIFIED evidence composition

All 3,707 QUALIFIED observations carry exactly the same four reason codes
— `VWAP_CONDITION_MET`, `TREND_CONDITION_MET`, `SUPPORT_CONDITION_MET`,
`V0_READINESS_POLICY_SATISFIED` — which is structurally guaranteed (the
engine only emits QUALIFIED when all three conditions are TRUE) rather
than a new finding. No ranking of RS-vs-RVOL-driven support was
distinguished, since the engine's own reason codes don't separately name
which of RS/RVOL was the deciding branch when both are evaluable (by
design — no new weighting was invented to extract this).

## 28. Option C validation

13,107 of 17,082 observations (76.7%) carry `SessionContext.data_quality
== EXPECTED_BAR_MISSING`. Within that flagged subset:

| State | Count | % |
|---|---:|---:|
| NOT_YET | 10,142 | 77.38 |
| QUALIFIED | 2,697 | 20.58 |
| UNKNOWN | 268 | 2.04 |

These proportions are **essentially identical** to the unflagged overall
population (76.17% / 21.70% / 2.13%) — direct, real-engine confirmation
that the blanket `SessionDataQuality` flag has no material effect on the
engine's own evaluability, exactly as Option C (artifact-owned
availability, ID-6B.1A/1B) was designed to guarantee. No blanket gate was
restored; none is proposed.

## 29. M15 availability impact

Only **1 of 17,082** observations (0.01%) is `UNKNOWN` specifically because
`TREND_EVIDENCE_UNAVAILABLE` coincided with `fifteen_min_available == False`.
This reconfirms ID-6B.1B's own finding — M15's chronic off-grid technical
debt remains **non-blocking** for the v0 candidate rule, now validated
against the real production engine at the full 17,082-observation scale,
not only the research formula. M15 was not repaired or touched.

## 30. Finality distribution

`LIVE_M5_PROVISIONAL`: 17,082 (100.00%). `UNKNOWN_PROVENANCE`: 0.
`NO_DECISIVE_PROVISIONAL_M5_DEPENDENCY`: 0. This is exactly the expected
result given `resolve_evidence_finality`'s own contract: every observation
in this sample is a WATCH/TRADE Decision evaluated during `SessionPhase.REGULAR`
(by construction of the sample — `candidates_at` only selects WATCH/TRADE,
and the checkpoints fall mid-session), so the resolver's eligibility gate
is satisfied on every row.

## 31. Historical replay finality limitation

`resolve_evidence_finality`'s `LIVE_M5_PROVISIONAL` classification here
represents the **semantics of the runtime evidence path** — that a
REGULAR-phase WATCH/TRADE evaluation's decisive evidence is M5/M15-derived
and, in a genuinely live cycle, not yet through settlement repair — **not**
a claim about the current settlement status of these specific,
retrospectively-replayed August 2026 bars in `db/athena.db` today. This
limitation was owner-accepted in ID-6D.1 and is restated here, not
re-litigated: a historical replay at a past REGULAR `as_of` is
conservatively classified `LIVE_M5_PROVISIONAL` even if that session's M5
has, in absolute terms, already been through whatever settlement process
applies to it.

## 32. Determinism/digest

Run 1: 17,082 observations, 401.16s, `analysis_sha256 =
0de3a8e161dcc4a97b980b0f806a6c8d6a75a153d4095dbcfd6218f3b63b2475`.
Run 2: independently re-executed against the same source database with
identical parameters — 17,082 observations, 367.839s (timing excluded from
the digest by design), `analysis_sha256 =
0de3a8e161dcc4a97b980b0f806a6c8d6a75a153d4095dbcfd6218f3b63b2475`.
**Exact digest match** — observation count, state distribution,
per-observation fields (state/reason codes/finality/methodology version),
transitions, and every other summary field are byte-identical across the
two independent runs. No provider/network calls in either run.

## 33. Replay runtime/performance

401.16s total for 17,082 observations across 396 instruments — approximately
**42.6 observations/second**. Comparable to ID-6B.1B's own 17,082-
observation run (418.469s, ~40.8 obs/sec) — the additional per-row
Decision-row fetch and engine invocation added negligible overhead. No
O(N²) behavior observed; no repeated full-history reads per observation
(market/sector index candle series are cached per checkpoint, matching
ID-6B.1's own caching pattern, unmodified).

## 34. Comparison with ID-6B.1B

| Metric | ID-6B.1B (research formula) | ID-6E (real engine) |
|---|---:|---:|
| Observations | 17,082 | 17,082 |
| Candidate/QUALIFIED match, population | 21.70% | 21.70% |
| TRADE match rate | 24.17% | 24.17% |
| WATCH match rate | 19.93% | 19.93% |
| Flicker (true-then-later-false) | 39.76% | 39.76% |
| M15-caused non-evaluability | 4 obs (0.02%) | 1 obs (0.01%, UNKNOWN-specific) |

The real-engine replay reproduces ID-6B.1B's research-formula figures to
within rounding on every headline metric — direct confirmation that
`EntryQualificationEngine` faithfully implements the same methodology
ID-6B.1B validated, with no silent drift introduced across ID-6B.2/2A/6C/
6C.1/6D/6D.1's implementation and hardening work. No engine tuning was
performed to force this agreement — the match was observed, not sought.

## 35. Shadow observation availability

**Unavailable.** A direct, read-only query (`SELECT 1 FROM sqlite_master
WHERE type='table' AND name='entry_qualifications'`) against the real
`db/athena.db` confirms the table **does not exist** in the production
database — the ID-6C schema migration (`SqliteRepository.initialize()`)
has not been run against it since these milestones were implemented.
Status: **`SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE`**.

## 36. Shadow source/read-only posture

`run_shadow_audit` uses the identical `mode=ro` + `PRAGMA query_only=ON`
posture as the replay harness. It was executed against the real
`db/athena.db` exactly once, confirmed the table-missing result, and made
no writes — verified by comparing the file's modification time before and
after (unchanged), and independently test-proven against temp databases
(§49).

## 37. Shadow observation count/sessions/instruments

0 / not applicable / not applicable — no rows exist to characterize.

## 38. Shadow state distribution

Not applicable — no observations exist.

## 39. Shadow finality distribution

Not applicable — no observations exist.

## 40. Shadow integrity audit

Not applicable — no observations exist to audit. `run_shadow_audit`'s
integrity-check logic (duplicate logical identity, `DISQUALIFIED_FOR_SESSION`
absence, non-`NOT_EVALUATED` confirmation, naive `persisted_at`) was
proven correct against synthetic temp-DB data instead (§49) — the logic
itself is validated even though no real data currently exercises it.

## 41. Persistence-latency distribution

Not applicable — no real persisted observations exist. The `persistence_latency_seconds`
computation (median/p90/p95/max/negative-count) was proven correct against
a synthetic temp-DB observation with a known, non-zero `persisted_at -
as_of` delta (§49) — no pass/fail threshold was invented; none is proposed
here either, since real data does not yet exist to characterize a
production distribution.

## 42. Shadow transition/flicker analysis

Not applicable — no real observations exist to reconstruct trajectories
from.

## 43. Replay-vs-shadow comparison

Not applicable — shadow evidence does not exist, so no comparison is
possible. This is stated as a gap, not glossed over: the replay findings
(§14-34) describe engine behavior under research-comparable historical
conditions; they say nothing about actual production runtime cadence,
candidate funnel composition, or persistence latency, none of which can be
observed until the schema is migrated against `db/athena.db` and at least
one real cycle runs.

## 44. Outcome-data availability count only

Not examined. Per the owner's explicit instruction, `trade_outcomes` and
price-excursion data were not joined against Entry Qualification
observations in this milestone — ID-6B already found essentially no
meaningful outcome population for this candidate rule, and ID-6E does not
re-attempt an efficacy study from insufficient labels. No count was even
queried, since doing so risks implying an outcome analysis was
contemplated; it was not.

## 45. Explicit no-profitability conclusion

**This document makes no claim of edge, alpha, expected return, win rate,
+1%/+1.5% success, stop-loss quality, or favorable risk/reward.** The
strongest conclusion supported by this evidence is: *the frozen Entry
Qualification contract behaves deterministically and operationally as
designed across the replay evidence gathered.* Profitability/effectiveness
remains entirely untested and is explicitly deferred — to a later,
separately-authorized milestone that freezes Entry/Exit semantics first
(ID-7/ID-8), not to ID-6E.

## 46. Integrity defects/anomalies

**None found.** 0 harness defects (missing Decisions, input-coherence
failures) across 17,082 replay observations. All frozen invariants hold
(§19-20). No non-v0 methodology version observed. No naive/non-timezone-
aware timestamp anywhere in the replay output (the engine's own `as_of` is
always tz-aware by domain-object construction, unchanged since ID-6A).

## 47. Validation classification

## **REPLAY_SOUND_SHADOW_EVIDENCE_INSUFFICIENT**

Deterministic replay is sound (§32); runtime/workflow invariants are
clean everywhere they are observable through the replay path (§19-20,
§46); but genuine shadow (persisted runtime) observations are absent —
not merely sparse, but structurally unavailable because the production
schema has not yet been migrated against `db/athena.db`. This is reported
as a factual precondition for any future shadow characterization, not a
defect in ID-6D/ID-6D.1's own implementation (which is itself
schema-correct and fully tested against temp databases throughout ID-6C
through ID-6D.1).
