# ID-6E — Entry Qualification Replay & Shadow Validation

**Status:** Analysis complete, corrected by ID-6E.1. Read-only, research-only.
**Depends on:** ID-6A through ID-6D.1 (all owner-approved/closed 2026-09-02
— methodology frozen, engine implemented, input-coherence hardened,
persisted, Decision-bound, workflow-wired, provenance-resolved,
persistence-time-corrected).
**Does not:** change methodology, tune thresholds, prove profitability,
test outcomes/targets, add API/UI, or start ID-7/EM-6.

**ID-6E.1 correction notice (2026-09-02):** the original ID-6E transition/
flicker and qualification-duration analysis grouped trajectories by
`(instrument_id, session_date, decision_type)`, incorrectly merging
distinct, superseding canonical Decision episodes of the same type into one
trajectory. Owner review held closure for this defect; ID-6E.1 corrected
the grouping to `(instrument_id, session_date, decision_id)` — the genuine
Decision-episode identity ID-6C/ID-6D already bind Entry Qualification to.
**§23, §24, §32, §33, §34, and §47 below reflect the corrected figures.**
The original flicker figure (39.76%) is superseded and retained only as a
labeled comparison point (§34, §48).

## 1. Executive summary

Two evidence modes were audited. **Replay** (settled historical market-time
evaluation via the real, unmodified `EntryQualificationEngine` and
`resolve_evidence_finality`, over the identical 10-session/17,082-
observation window ID-6B.1B used): fully sound — deterministic across two
independent runs (both before and after the ID-6E.1 correction), zero
harness defects, zero coherence failures, every frozen invariant holds, and
every point-observation headline statistic (QUALIFIED prevalence, WATCH/
TRADE split) matches ID-6B.1B's own research baseline almost exactly,
confirming the closed engine reproduces the pre-engine research formula's
behavior faithfully. The trajectory-based statistics (flicker rate,
qualification duration) initially appeared to match ID-6B.1B's own figures
as well, but ID-6E.1 found this apparent agreement was itself an artifact
of a shared grouping defect (§48) — the corrected, Decision-episode-pure
flicker rate is **11.73%**, not 39.76%. **Shadow** (real persisted runtime
observations in `db/athena.db`): **unavailable** — the
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

## 23. Transition/flicker analysis (corrected — ID-6E.1)

**Corrected grouping (ID-6E.1):** trajectories are grouped by
`(instrument_id, session_date, decision_id)` — the actual canonical
Decision episode — not `(instrument_id, session_date, decision_type)`. A
`DecisionType` is not a Decision identity: ID-6D binds Entry Qualification
to a specific canonical Decision, and ID-6C persists every observation
keyed to `decision_id`, so a newer Decision superseding an older one within
the same instrument/session/type must be treated as a separate episode, not
a continuation of the same trajectory. Ordering within each episode uses
the semantic `as_of` timestamp, not the checkpoint display string.

Of 14,699 total distinct Decision episodes in the window, **1,833** were
observed at 2+ checkpoints before being superseded or the window ending.
Among those 1,833 multi-checkpoint Decision episodes: **215 (11.73%)** show
the pattern "QUALIFIED at an earlier checkpoint, then not QUALIFIED at a
later checkpoint within the SAME canonical Decision." Full pattern table in
`artifacts/research/id6e/run1_corrected/id6e_summary.json`. Flicker is not
suppressed, and no confirmation/hysteresis/debounce logic exists anywhere
in the engine (unchanged, source-verified) — genuine same-Decision flicker
remains a real, observed property; it is simply measured at the correct
(Decision-episode) granularity now.

**Superseded figure:** the original ID-6E analysis (pre-ID-6E.1) reported
1,493/3,755 = 39.76%, grouping by `(instrument_id, session_date,
decision_type)`. That figure conflated multiple canonical Decision episodes
of the same type within one instrument/session into a single trajectory —
see §34/§48 for the full root-cause explanation and the audit of
ID-6B.1B's own research harness, which shares the same grouping contract.

## 24. Qualification-duration description (corrected — ID-6E.1)

Same corrected `(instrument_id, session_date, decision_id)` grouping as
§23, computed over all 14,699 distinct Decision episodes:

| Pattern | Decision episodes |
|---|---:|
| Never qualified | 11,382 |
| Qualified at exactly one observed checkpoint | 2,990 |
| Qualified at some but not all checkpoints | 66 |
| Qualified at every observed checkpoint | 261 |

Descriptive only. No pattern is labeled "valid" or "false"; no new
confirmation rule is implied or authorized by this table. The large
"qualified at exactly one checkpoint" and "never qualified" counts are
consistent with §48's finding that most Decision episodes in this window
span only 1-2 checkpoints before being superseded by a newer Decision —
see §48 for the descriptive Decision-supersession audit.

**Superseded figure:** the original ID-6E table (pre-ID-6E.1), grouped by
`(instrument_id, session_date, decision_type)`: never qualified 2,342;
exactly one checkpoint 1,087; some but not all 895; every checkpoint 139.

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

## 32. Determinism/digest (corrected — ID-6E.1)

**Pre-correction (superseded):** Run 1: 17,082 observations, 401.16s,
`analysis_sha256 = 0de3a8e161dcc4a97b980b0f806a6c8d6a75a153d4095dbcfd6218f3b63b2475`.
Run 2: 17,082 observations, 367.839s, identical digest. This digest reflects
the superseded `decision_type`-based trajectory aggregation (§23/§24) and
is retained here only for audit continuity.

**Post-correction (current):** the ID-6E.1 grouping fix legitimately
changes the transition/qualified-duration/decision-supersession sections
of the summary, so a new digest is expected and was not required to match
the old one. Run 1 (corrected): 17,082 observations, 330.872s,
`analysis_sha256 = d18c2cb1c43688804c7aea8430b1d4a1539c48f4b3cab3e2a05fd2bba8a70ef9`.
Run 2 (corrected): independently re-executed against the same source
database with identical parameters — 17,082 observations, 314.081s (timing
excluded from the digest by design), identical
`analysis_sha256 = d18c2cb1c43688804c7aea8430b1d4a1539c48f4b3cab3e2a05fd2bba8a70ef9`.
**Exact digest match** across the two corrected runs — observation count,
state distribution, per-observation fields, corrected transitions/
qualified-duration/decision-supersession, and every other summary field are
byte-identical. No provider/network calls in either run. `db/athena.db`
confirmed unmodified (checksum identical before and after both runs).

## 33. Replay runtime/performance

330.872s total for 17,082 observations across 396 instruments (corrected
run 1) — approximately **51.6 observations/second**; run 2 measured
314.081s (~54.4 obs/sec). Comparable to the pre-correction runtime (401.16s/
367.839s) and to ID-6B.1B's own 17,082-observation run (418.469s, ~40.8
obs/sec) — the ID-6E.1 grouping/ordering correction is O(n) post-processing
over already-collected rows and did not materially change per-observation
replay cost. No O(N²) behavior observed; no repeated full-history reads per
observation (market/sector index candle series are cached per checkpoint,
matching ID-6B.1's own caching pattern, unmodified).

## 34. Comparison with ID-6B.1B (corrected — ID-6E.1)

| Metric | ID-6B.1B (research formula) | ID-6E (real engine, corrected) |
|---|---:|---:|
| Observations | 17,082 | 17,082 |
| Candidate/QUALIFIED match, population | 21.70% | 21.70% |
| TRADE match rate | 24.17% | 24.17% |
| WATCH match rate | 19.93% | 19.93% |
| Flicker — Decision-episode-pure | not measured (see §48) | **11.73%** |
| Flicker — pre-correction, decision_type-grouped (superseded) | 39.76% | 39.76% |
| M15-caused non-evaluability | 4 obs (0.02%) | 1 obs (0.01%, UNKNOWN-specific) |

The real-engine replay reproduces ID-6B.1B's research-formula **point-
observation** figures (QUALIFIED prevalence, WATCH/TRADE split) to within
rounding — direct confirmation that `EntryQualificationEngine` faithfully
implements the same methodology ID-6B.1B validated, with no silent drift
introduced across ID-6B.2/2A/6C/6C.1/6D/6D.1's implementation and hardening
work. The trajectory-based flicker figure is **not** directly comparable
between the two: ID-6B.1B never computed a Decision-episode-pure flicker
rate (its own harness shares the same `decision_type`-grouping defect ID-6E
inherited — see §48), so 11.73% has no ID-6B.1B counterpart to match
against. No engine tuning was performed anywhere in this comparison — every
match and every difference was observed, not sought.

## 35. Shadow observation availability (updated — ID-6E.2)

**Available as of 2026-09-03 (ID-6E.2).** At the time this report was first
written, a direct read-only query confirmed the `entry_qualifications`
table did not exist in production, and status was reported
`SHADOW_OBSERVATIONS_NOT_YET_AVAILABLE`. ID-6E.2 (owner-authorized
operational activation) found the schema had, by the time of its own
preflight, already reached SCHEMA_VERSION 17 with the table present (via
ATHENA's own routine, idempotent `repo.initialize()` calls — no ad-hoc
migration was issued), and observed the live, already-scheduled production
server's own PREMARKET cycle (08:15:29 IST, 2026-09-03) persist **165**
genuine `EntryQualification` rows through the normal
`OwnerValidationPipeline` -> `entry_qualification` stage ->
`save_entry_qualification()` runtime path — no manual insert, no direct
`save_entry_qualification()` call, no fabricated data. Full detail:
`docs/ops/ID-6E2-ENTRY-QUALIFICATION-PRODUCTION-SCHEMA-ACTIVATION.md`.

## 36. Shadow source/read-only posture

`run_shadow_audit` uses the identical `mode=ro` + `PRAGMA query_only=ON`
posture as the replay harness. It was executed against the real
`db/athena.db` twice: once (ID-6E) confirming the table-missing result,
and once (ID-6E.2) against the now-populated table — both read-only, both
verified to make no writes. Integrity logic was additionally test-proven
against synthetic temp-DB data (§49).

## 37. Shadow observation count/sessions/instruments (updated — ID-6E.2)

**165 observations, 1 distinct session (2026-09-03), 165 distinct
instruments** — one row per eligible WATCH candidate in that single
PREMARKET cycle. All from a single `as_of` (08:15:29.919615+05:30);
`run_shadow_audit`'s `earliest_persisted_at`/`latest_persisted_at` span
08:24:37.844185 to 08:24:43.035112 IST — the ~5.2-second wall-clock spread
of persisting 165 rows sequentially within the cycle.

## 38. Shadow state distribution (updated — ID-6E.2)

100% `EXPIRED` (165/165). Root-caused (read-only, no frozen code touched)
to genuine, correct, by-design behavior: the cycle's `as_of` (08:15:29 IST)
falls before `config/market.nse.json`'s `sessions.preopen_start` (09:00),
so `classify_session_phase` (`src/athena/session/engine.py:150-171`)
correctly returns `SessionPhase.CLOSED` for this `as_of` — which the
frozen engine's state precedence (ID-6B.2) maps to `EXPIRED`. This is not
a defect; ATHENA's "PREMARKET" operational cadence label and NSE's own
session-phase "PRE_OPEN" window are distinct concepts, and 08:15 IST falls
in neither NSE's PRE_OPEN (09:00-09:15) nor REGULAR (09:15-15:30) window.

## 39. Shadow finality distribution (updated — ID-6E.2)

100% `UNKNOWN_PROVENANCE` (165/165) — exactly the expected `resolve_evidence_finality`
result for a non-REGULAR-phase evaluation (§38), consistent with ID-6D's
own frozen resolver contract.

## 40. Shadow integrity audit (updated — ID-6E.2)

Full-population (not sampled) read-only audit of all 165 rows:
Decision-binding mismatches (instrument_id/decision_type/run_id/cycle_id
vs. the bound Decision) — **0**; orphaned `decision_id` — **0**;
`session_date` incoherent with `as_of`'s local calendar date — **0**;
naive (non-timezone-aware) `as_of` — **0**; naive `persisted_at` — **0**;
unexpected `reason_codes` for `state` — **0**; non-`entry-qualification-v0`
methodology version — **0**; `DISQUALIFIED_FOR_SESSION` — **0**;
non-`NOT_EVALUATED` confirmation — **0**; duplicate logical identity —
**0**. Every invariant this integrity audit checks holds cleanly against
genuine production data for the first time.

## 41. Persistence-latency distribution (updated — ID-6E.2)

Genuine, non-fabricated latency across all 165 rows: median 550.77s, p90
552.58s, p95 552.82s, max 553.12s, **0 negative-latency rows**. This
reflects the real wall-clock duration between the cycle's `as_of` capture
(at cycle start) and each instrument's own `entry_qualification` stage
actually executing, sequentially, later in the same PREMARKET cycle — the
first genuine evidence of the `as_of`/`persisted_at` separation ID-6D.1
built. No pass/fail threshold is asserted, per instruction.

## 42. Shadow transition/flicker analysis

Not applicable — all 165 observations share a single `as_of` (one
checkpoint), so there is no multi-checkpoint trajectory to reconstruct yet.
This requires observations spanning multiple `as_of` values for the same
instrument/session/decision_id, which will only exist once further cycles
(REFRESH, or a future PREMARKET) run.

## 43. Replay-vs-shadow comparison (updated — ID-6E.2)

Only partially possible now. Comparable dimensions: WATCH/TRADE split —
shadow is 100% WATCH (165/165) vs. replay's 74.5%/25.5% WATCH/TRADE split;
not directly comparable, since the shadow sample is a single CLOSED-phase
moment (no TRADE decisions were eligible/produced at that hour) while
replay spans full REGULAR-phase sessions. State prevalence — shadow is
100% EXPIRED (a CLOSED-phase artifact); replay's population excludes
CLOSED-phase observations by construction (§9/§18), so there is no
directly overlapping state distribution to compare yet. Finality — shadow
is 100% `UNKNOWN_PROVENANCE` vs. replay's 100% `LIVE_M5_PROVISIONAL` —
this is expected and consistent: replay only samples REGULAR-phase
WATCH/TRADE observations, while the one real shadow cycle observed so far
ran before market open. A meaningful behavioral comparison (state/finality
distribution during REGULAR phase) requires shadow evidence from a cycle
that runs during NSE market hours — not yet observed.

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

**None found in the engine/persistence/workflow path.** 0 harness defects
(missing Decisions, input-coherence failures) across 17,082 replay
observations. All frozen invariants hold (§19-20). No non-v0 methodology
version observed. No naive/non-timezone-aware timestamp anywhere in the
replay output (the engine's own `as_of` is always tz-aware by domain-object
construction, unchanged since ID-6A). One defect *was* found and corrected,
but it was in this milestone's own **research-analysis code**, not in any
production path: the original ID-6E transition/qualified-duration analysis
grouped trajectories by `decision_type` instead of `decision_id`,
incorrectly merging distinct canonical Decision episodes. Corrected by
ID-6E.1 — see §23/§24/§48.

## 47. Validation classification (updated — ID-6E.2)

## **REPLAY_SOUND_SHADOW_EVIDENCE_INSUFFICIENT**

Deterministic replay is sound (§32); runtime/workflow invariants are
clean everywhere they are observable through the replay path (§19-20,
§46), and now also clean against genuine production data (§40). Shadow
evidence is no longer *unavailable* — 165 genuine, fully-coherent
observations exist as of ID-6E.2 (2026-09-03) — but it remains
*insufficient* for behavioral characterization: every observation shares
one `as_of`, one state (`EXPIRED`), one finality (`UNKNOWN_PROVENANCE`),
and one decision type (`WATCH`), a CLOSED-session artifact of the single
observed cycle running before NSE's own pre-open window. No REGULAR-phase,
QUALIFIED/NOT_YET/UNKNOWN, or TRADE-type shadow observation exists yet.
The classification therefore remains unchanged, for a different reason
than before: previously because shadow evidence was structurally absent;
now because the evidence that exists cannot yet support a behavioral
comparison against the replay findings. This is reported
as a factual precondition for any future shadow characterization, not a
defect in ID-6D/ID-6D.1's own implementation (which is itself
schema-correct and fully tested against temp databases throughout ID-6C
through ID-6D.1). The ID-6E.1 trajectory-identity correction (§48) changed
the measured flicker/qualification-duration figures but did not change
this classification: it was a research-analysis correction, not a change
to the replay's point-observation soundness or to the shadow-availability
finding.

## 48. ID-6E.1 addendum — Decision-episode trajectory-identity correction

**Root defect.** `_transitions` and `_qualified_duration` grouped
observations by `(instrument_id, session_date, decision_type)`. A
`DecisionType` (WATCH/TRADE) is not a Decision *identity*. Two separate
canonical Decisions of the same type for the same instrument/session
(e.g. a 09:30 WATCH superseded by a 09:45 WATCH) were merged into one
apparent trajectory, even though ID-6D established Entry Qualification is
bound to a specific Decision episode, and ID-6C persists every observation
keyed to `decision_id` precisely so that identity is preserved.

**Decision-id availability.** Audited first: every replay observation row
already carries `decision_id` (populated from `candidate.decision_id`,
the same value used to fetch the bound `Decision` and to build the
`HarnessDefect` record on failure) and `as_of` (the semantic evaluation
timestamp). No new field was needed — the defect was purely in how the
existing fields were (not) used for grouping.

**Correction.** `_transitions`/`_qualified_duration` now group by
`(instrument_id, session_date, decision_id)` via a shared
`_decision_episode_groups` helper, ordered by `as_of` (parsed via
`datetime.fromisoformat`) rather than the zero-padded checkpoint label.
`decision_type` is retained only as descriptive metadata in the new
Decision-supersession audit below, never as a grouping key.

**Decision-supersession descriptive audit (new).** Across the 17,082-
observation window: 3,401 distinct instrument/session groups were
observed; **3,210 of those (94.4%) contained more than one distinct
`decision_id`** across the 6 replay checkpoints — confirming Decision
churn within a session is the norm, not the exception, in this candidate
population. 14,699 total distinct Decision episodes were observed (average
~4.3 per instrument/session group). Decision-type replacement patterns:
WATCH→WATCH 5,695, TRADE→TRADE 4,050, WATCH→TRADE 747, TRADE→WATCH 806 —
descriptive only; no judgment is made about whether a given replacement is
desirable.

**Corrected trajectory statistics.** Of 14,699 Decision episodes, 1,833
were observed at 2+ checkpoints (most episodes — 12,866 of 14,699 — are
single-checkpoint, consistent with the high supersession rate just
measured). Among those 1,833 multi-checkpoint episodes, corrected flicker
is **215 (11.73%)** — materially lower than the superseded 39.76%
(1,493/3,755 under the old grouping). Corrected qualification duration:
never qualified 11,382; qualified at exactly one checkpoint 2,990;
qualified at some but not all checkpoints 66; qualified at every observed
checkpoint 261 (sums to 14,699, matching the corrected episode count
exactly).

**Why the figures changed.** The old grouping's 3,755
"instrument/session/decision_type" groups conflated an average of
several distinct Decision episodes per group whenever a symbol's Decision
was re-issued within a session (the norm, per the 94.4% figure above). A
QUALIFIED checkpoint under one Decision followed by a NOT_YET checkpoint
under a *different, superseding* Decision was counted as flicker even
though no single canonical Decision ever transitioned from QUALIFIED to
NOT_YET. The correction eliminates exactly that class of false-positive
flicker while preserving genuine same-Decision flicker (verified by a
dedicated non-vacuous test, §51/§28 below).

**ID-6B.1B grouping audit.** ID-6B.1B's own `_transitions` function
(`src/athena/data/id6b1_entry_qualification_baseline.py`) groups by
`(instrument_id, session_date, decision_type)` — the identical defect
pattern, predating ID-6E. This is not a coincidence requiring
investigation: ID-6B.1B's harness computed a research-only
`candidate_policy_match` boolean before ID-6C's Decision-binding
persistence contract existed, so it had no architectural reason to treat
`decision_id` as the trajectory identity. Per the owner's explicit
instruction, **ID-6B.1B's own historical artifacts were not modified** —
its reported 39.76%/46.43% flicker figures remain valid descriptions of
*that* research-formula grouping contract; they are simply not
Decision-episode-pure under the frozen Entry Qualification binding
contract, and are not directly comparable to ID-6E.1's corrected 11.73%
(§34).

**Point-observation invariants unchanged.** This correction is trajectory
aggregation only. Re-verified unchanged after the fix: total observations
(17,082), WATCH/TRADE counts, QUALIFIED/NOT_YET/UNKNOWN counts and rates,
Option C statistics, M15 statistics, finality distribution, confirmation
invariants, and methodology-version invariants (§13-20, §28-30 above) —
all identical to the pre-correction run, confirming the correction touched
only trajectory-analysis code, never the per-observation replay path.

## 49. ID-6E.2 addendum — Production schema activation & first genuine shadow canary

Owner-authorized operational activation (2026-09-03). Full detail:
`docs/ops/ID-6E2-ENTRY-QUALIFICATION-PRODUCTION-SCHEMA-ACTIVATION.md`.

**Migration.** Preflight against real `db/athena.db` found SCHEMA_VERSION
already at 17 with `entry_qualifications` present (0 rows) — the migration
had already occurred via ATHENA's own routine, idempotent
`SqliteRepository.initialize()` calls (`_open_repo()`/API startup), which
this milestone's own explicit second `initialize()` call reconfirmed as a
structural no-op. No ad-hoc SQL was written anywhere. A full,
integrity-verified, checksummed safety backup was taken before any further
production activity (`db/backups/athena-pre-id6e2-shadow-canary-20260903T024201Z.db`,
SHA-256 `42c1ecb267d6652389ed59b05cefb690e66d827b4bf572faa3aac1773ff8beaa`).
Structural verification against a fresh v17 reference schema found zero
drift (28/28 tables, 56/56 indexes, exact `entry_qualifications` column/PK/FK/index
match).

**Shadow canary.** The already-running, already-scheduled production
server (`athena serve --with-cycles`) fired its own PREMARKET cycle at
08:15:29 IST on its own schedule — no triggering action from this
milestone — and persisted **165** genuine `EntryQualification` rows
through the normal `OwnerValidationPipeline` runtime path. Full-population
(not sampled) integrity audit: 0 Decision-binding mismatches, 0 orphaned
`decision_id`, 0 timezone/session-date incoherence, 0 unexpected reason
codes, 0 invariant violations of any kind across all 165 rows.

**Why all 165 rows are `EXPIRED`/`UNKNOWN_PROVENANCE`.** Read-only audited
(no frozen code touched): the cycle's `as_of` (08:15:29 IST) precedes
`config/market.nse.json`'s `sessions.preopen_start` (09:00), so
`classify_session_phase` correctly returns `SessionPhase.CLOSED` — which
the frozen engine maps to `EXPIRED`/`UNKNOWN_PROVENANCE`. Verified
by-design, not a defect: ATHENA's "PREMARKET" operational label and NSE's
own session-phase PRE_OPEN window are distinct concepts.

**Genuine persistence latency observed for the first time in production:**
median 550.77s, p90 552.58s, p95 552.82s, max 553.12s, 0 negative-latency
rows — the real wall-clock gap between `as_of` capture and each
instrument's sequential `entry_qualification` stage execution later in the
same cycle.

**Classification impact.** Shadow evidence is no longer *unavailable* (as
it was when this report was first written), but the single CLOSED-phase
cycle observed so far does not yet support behavioral characterization (no
REGULAR-phase, QUALIFIED/NOT_YET/UNKNOWN, or TRADE observation exists).
Milestone-level status:
**ID-6E.2 ACTIVATION COMPLETE — SHADOW ACCUMULATION STARTED.** Overall
ID-6E classification remains **REPLAY_SOUND_SHADOW_EVIDENCE_INSUFFICIENT**,
now for evidence-insufficiency rather than evidence-absence (§47).

## 50. ID-6E.3 addendum — Genuine REGULAR-session shadow characterization

Owner-authorized, read-only characterization (2026-09-03). Full detail in
this section only (no separate ops doc — this is analysis, not an
operational procedure).

**Audit cutoff.** `persisted_at <= 2026-09-03T04:09:59.748488+00:00`
(`max(persisted_at)` at audit start) — a bounded, deterministic population
of **654** rows, chosen so a live, continuously-accumulating production
table could not make this report internally inconsistent. Production
continued accumulating during the audit (893 rows by report-writing time)
— not analyzed, noted for context only.

**Session-phase reconstruction.** The bounded population spans exactly 3
distinct `as_of` values, one per real scheduled cycle. Each was classified
using the actual, unmodified `classify_session_phase` (`src/athena/session/engine.py`),
imported read-only, never re-derived:

| `as_of` (IST) | run_id | cycle_id | SessionPhase | n | states |
|---|---|---|---|---:|---|
| 08:15:29.919615 | `run-premarket-20260903T081529` | `2026-09-03-premarket` | CLOSED | 165 | EXPIRED: 165 |
| 09:15:16.873333 | `run-refresh-20260903T091516-a0dbc231` | `2026-09-03-refresh` | REGULAR | 255 | NOT_YET 169, UNKNOWN 86 |
| 09:30:40.848473 | `run-refresh-20260903T093040-4be47fed` | `2026-09-03-refresh` | REGULAR | 234 | NOT_YET 151, QUALIFIED 76, UNKNOWN 7 |

One session (2026-09-03) throughout; 0 PRE_OPEN observations (none fell
between 09:00 and 09:15). The 165 CLOSED/EXPIRED rows from ID-6E.2 are
unchanged (still 100% EXPIRED/UNKNOWN_PROVENANCE) — confirmed not mutated.

**REGULAR population (the primary ID-6E.3 population): 489 rows**, all
`decision_type=WATCH` (0 TRADE), all `methodology_version=entry-qualification-v0`.
State distribution: NOT_YET 320 (65.44%), UNKNOWN 93 (19.02%), QUALIFIED
76 (15.54%). **REGULAR finality invariant holds exactly: 489/489
`LIVE_M5_PROVISIONAL`, 0 violations.** `DISQUALIFIED_FOR_SESSION`: 0.
`OUT_OF_SCOPE`/`EXPIRED` inside the REGULAR population: 0 (as required).
258 distinct instruments; 489 distinct `decision_id` (i.e. essentially
every instrument received a newly-issued Decision on each of the 2
checkpoints — high churn, consistent with historical replay's own finding
that Decision churn is the norm, not the exception, in this population).

**Full-population integrity audit (all 654 rows, not just REGULAR):**
Decision-binding mismatches 0; orphaned `decision_id` 0; duplicate logical
identity 0; `session_date`/`as_of` incoherence 0; naive `as_of` 0; naive
`persisted_at` 0; invalid state enum 0; invalid finality enum 0; invalid
confirmation enum 0; malformed `reason_codes_json`/`evidence_refs_json` 0;
`DISQUALIFIED_FOR_SESSION` 0; non-`NOT_EVALUATED` confirmation 0; non-v0
methodology version 0. Every observed `(state, finality)` combination is
valid under the frozen contract: `(EXPIRED, UNKNOWN_PROVENANCE)`,
`(NOT_YET, LIVE_M5_PROVISIONAL)`, `(UNKNOWN, LIVE_M5_PROVISIONAL)`,
`(QUALIFIED, LIVE_M5_PROVISIONAL)` — no impossible combination observed.
**Zero integrity defects of any kind.**

**Decision-episode trajectories (canonical `(instrument_id, session_date,
decision_id)` grouping, per ID-6E.1 — never `decision_type`).** All 489
REGULAR Decision episodes are **single-checkpoint** — 0 multi-checkpoint
episodes exist. Root cause: essentially every instrument's Decision is
re-issued (new `decision_id`) on each cycle (231 of 258 instrument/session
groups already show >1 distinct `decision_id` across just these first 2
REGULAR checkpoints). **Consequence: genuine shadow flicker is not yet
measurable** — there is no multi-checkpoint episode to compute a
transition on. This is reported as a real evidentiary gap, not
approximated or forced: 0 multi-checkpoint episodes, 0 flicker
observations, evidence limited. Qualification duration (all single-
checkpoint by construction): never-qualified 413, qualified-at-exactly-
one-checkpoint 76 (trivially "duration = its one checkpoint").

**Decision churn.** 258 instrument/session groups observed in the REGULAR
population; 231 (89.5%) already show more than one distinct `decision_id`
across only 2 checkpoints — directionally consistent with (if not higher
than) historical replay's own high-churn finding.

**Checkpoint-level detail explains the UNKNOWN concentration.** UNKNOWN
was 86/255 (33.7%) at 09:15:16 — essentially the literal instant of
market open, when few M5 candles have completed yet — dropping to 7/234
(3.0%) just 15 minutes later at 09:30:40. Reason codes confirm this: 87 of
93 REGULAR UNKNOWN rows cite `VWAP_EVIDENCE_UNAVAILABLE` (VWAP needs a
completed M5 bar), and all 93 cite `SUPPORT_EVIDENCE_UNRESOLVED`. This is
a genuine, sensible live-market artifact of evaluating essentially at the
open — not a defect, and not something replay's own earliest checkpoint
(09:30, already 15 minutes post-open) ever exercised. QUALIFIED shows the
inverse pattern: 0/255 (0%) at 09:15:16, rising to 76/234 (32.5%) by
09:30:40 — the readiness formula simply has no chance to be satisfied in
the first seconds of a session.

**NOT_YET root causes (REGULAR, 320 observations):** `TREND_CONDITION_NOT_MET`
241 (75.3%), `VWAP_CONDITION_NOT_MET` 135 (42.2%), `SUPPORT_CONDITION_NOT_MET`
24 (7.5%) — trend and VWAP dominate, support rarely decisive — directionally
matching replay's own NOT_YET root-cause finding exactly (§26).

**QUALIFIED evidence composition (REGULAR, 76 observations):** all 76
carry exactly the structurally-guaranteed 4 reason codes
(`VWAP_CONDITION_MET`, `TREND_CONDITION_MET`, `SUPPORT_CONDITION_MET`,
`V0_READINESS_POLICY_SATISFIED`) — matching replay (§27). The engine's own
reason-code vocabulary does not separately name RS-driven vs. RVOL-driven
support satisfaction, so an RS-vs-RVOL breakdown is not reconstructable
from persisted evidence — reported honestly, not inferred.

**Option C shadow reconstruction: not possible from persisted evidence.**
`entry_qualifications` does not persist `SessionContext.data_quality` (or
any `EXPECTED_BAR_MISSING`-equivalent marker) — only `reason_codes_json`/
`evidence_refs_json`, neither of which encodes data-quality provenance.
This is stated honestly rather than inferred or refetched from the
provider.

**M15 shadow observations.** 0 of 93 REGULAR UNKNOWN rows cite
`TREND_EVIDENCE_UNAVAILABLE` — M15 caused zero non-evaluability in this
shadow sample, consistent with (if not stronger than) replay's own
"non-blocking technical debt" conclusion. Not investigated further, not
modified.

**Persistence latency by cycle** (`persisted_at - as_of`, genuine, not
fabricated): PREMARKET — median 550.77s, p90 552.58s, max 553.12s;
REFRESH #1 (09:15:16) — median 555.76s, p90 557.65s, max 558.12s; REFRESH
#2 (09:30:40) — median 556.28s, p90 558.33s, max 558.90s. **0 negative-
latency rows in any cycle.** The near-identical ~550-559s pattern across
all three cycles — PREMARKET and both REFRESH cycles alike — confirms
ID-6E.2's own observation was not a PREMARKET-specific artifact: the
sequential, full-universe, single-threaded pipeline produces this latency
shape regardless of cycle type.

**Replay baseline comparison (population differences documented before
interpreting, per instruction).** Overall REGULAR shadow (489 obs, 2
near-open checkpoints, one real day) vs. the 17,082-observation replay
baseline (6 checkpoints spanning 09:30-14:30, 10 historical sessions):
QUALIFIED 15.54% (shadow) vs. 21.70% (replay); NOT_YET 65.44% vs. 76.17%;
UNKNOWN 19.02% vs. 2.13%. Checkpoint-matched comparison is far more
informative: shadow's 09:30:40 checkpoint (QUALIFIED 32.5%, UNKNOWN 3.0%)
vs. replay's own 09:30 checkpoint (QUALIFIED 22.95%, UNKNOWN 1.08%) — much
closer, though still directionally higher QUALIFIED and higher UNKNOWN in
shadow. Plausible, non-defect explanations (not adjudicated between):
genuine live/provisional-market knowledge-time effects at real-time
evaluation vs. replay's settled historical data; a single real trading
day's specific market regime and candidate funnel vs. a 10-session
average; small-sample (N=489, 1 day) vs. large-sample (N=17,082, 10 days)
variance. **Flicker cannot be compared at all** — shadow has 0
multi-checkpoint Decision episodes against replay's 11.73% corrected
figure; this is the dimension where shadow evidence is most clearly still
accumulating, not a discrepancy.

**Provider/network status.** Zero calls — every figure above comes from
already-persisted `entry_qualifications`/`decisions` rows, read via
`mode=ro`+`PRAGMA query_only=ON`.

**Production DB mutation status.** None. No `initialize()`, no insert/
update/delete, no manual `save_entry_qualification()` call, no scheduler/
config change. The production server continued its own independent,
already-scheduled accumulation throughout (654 → 893 rows during this
audit) — outside this milestone's control, exactly as expected.

**Sufficiency assessment.** REGULAR phase: present. More than one REGULAR
`as_of` checkpoint: present (2). QUALIFIED/NOT_YET/UNKNOWN: all present.
WATCH: present. **TRADE: absent.** **Multi-checkpoint Decision episodes:
absent (0).** More than one session: absent (still 2026-09-03 only). Per
instruction, absence of a dimension constrains the claim rather than
blocking all conclusions: operational/contract correctness is strongly
supported (zero integrity defects across 654 rows, exact finality
invariant, directionally sensible root causes); genuine behavioral
characterization — especially anything touching trajectory/flicker/
persistence-over-time or TRADE-type behavior — is not yet supported.

**Classification: `REPLAY_SOUND_SHADOW_EVIDENCE_STILL_ACCUMULATING`.**
Every observed runtime row remains clean; genuine REGULAR evidence now
exists and is directionally consistent with the replay baseline on every
comparable dimension, but two structurally important dimensions (Decision-
episode trajectories/flicker, and TRADE-type representation) have zero
data points so far. This is not a defect — it is the expected shape of one
real trading morning's first two REGULAR cycles. Continued natural
accumulation (no artificial trigger) is recommended; no numeric threshold
is proposed for when to re-audit.
