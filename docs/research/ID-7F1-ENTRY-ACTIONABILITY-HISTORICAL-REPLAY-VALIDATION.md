# ID-7F1 — Entry Actionability Historical Replay Adapter + Deterministic Validation

**Status: COMPLETE — READY FOR OWNER / CHIEF ARCHITECT HISTORICAL-REPLAY
CLOSURE (2026-09-05).** Mode A only (historical market-time-bounded
replay), per the frozen ID-7F0 contract. No production shadow
equivalence, no schema migration, no service restart/deploy, no
Validate-All, no methodology change, no threshold tuning.

Owner/Chief Architect closed ID-7F0 on 2026-09-05 (validation contract
frozen, Classification B — `SMALL_ID7F_ADAPTER_REQUIRED` — accepted) and
authorized ID-7F1: implement the smallest adapter and run it, in
strict read-only mode, against the real historical WATCH/TRADE
`EntryQualification` population.

---

## 1. Implementation correctness

A new, isolated, read-only research module
[`src/athena/data/id7f1_entry_actionability_replay.py`](../../src/athena/data/id7f1_entry_actionability_replay.py)
implements exactly `run_replay(...)` — Mode A only. It reuses ID-6B.1's
`ReadOnlyStore` (SQLite URI `mode=ro` + `PRAGMA query_only=ON`) verbatim,
reuses the frozen `EntryActionabilityEngine` unmodified (`policy=None`),
and reuses every canonical composition helper ID-7E's own production
stage already uses (`session.latest_completed_candle`,
`IndicatorEngine.compute(VWAP, ...)`, `OpeningRangeEngine.assess`,
`SessionContextEngine.assess`) — no methodology, PIT rule, or completion
formula was re-derived. `run_shadow_equivalence` was **not** implemented
(explicitly out of scope for ID-7F1, per its own authorization).

**33 focused tests** (`tests/data_layer/test_id7f1_entry_actionability_replay.py`)
all pass: pure-function tests (`eq_identity`, `partition_duplicates`,
`_validate_binding` — every mismatched field, `_population_inventory`,
`_evidence_availability`, `_empirical_availability`,
`_watch_invariant_check`, source-scan proofs of zero provider/
currentness/persistence-write references) plus harness integration
tests against real, disposable temp SQLite databases (never
`db/athena.db`) seeded via the actual `OwnerValidationPipeline`: a real
WATCH reconstruction, a real TRADE+QUALIFIED→`ACTIONABLE`
reconstruction and a real TRADE+non-QUALIFIED→`NOT_ACTIONABLE`
reconstruction (both seeded via the same `DecisionEngine.decide`/
`EntryQualificationEngine.evaluate` monkeypatch-force pattern the ID-7E
test suite itself established — the real live database has zero
examples of either population, so this is the narrowest way to exercise
those code paths at all), determinism-across-two-separate-runs (SHA-256
summary equality), schema-version-unchanged, no-source-DB-mutation
(mtime unchanged), and order-independence.

## 2. Existing ID-6 code reused

`ReadOnlyStore` (imported directly from
`athena.data.id6b1_entry_qualification_baseline`, unmodified) for the
read-only connection and bounded candle/quote reads; the raw
`SELECT ... WHERE decision_id=?` exact-Decision-lookup pattern
(mirroring `id6e_replay_shadow_validation.py`'s own `_get_decision`);
the JSONL-observations + JSONL-defects + summary-JSON output shape and
the `analysis_sha256` reproducibility digest (mirroring
`_summarize`/`_analysis_digest`); the `HarnessDefect`-style "never fold
a harness failure into a methodology outcome" pattern, generalized into
ID-7F0's own frozen 4-relevant-category taxonomy (`UPSTREAM_BINDING_DEFECT`/
`PIT_EVIDENCE_DEFECT`/`PERSISTENCE_DEFECT`/`REPLAY_EQUIVALENCE_DEFECT`).

## 3. Read-only DB implementation

`ReadOnlyStore.__init__` opens `sqlite3.connect(f"file:{db_path}?mode=ro",
uri=True)` + `conn.execute("PRAGMA query_only=ON")` — reused verbatim,
never `SqliteRepository`'s writable connection. `run_replay` performs
only `SELECT` statements throughout (`entry_qualifications`, `decisions`,
`candles`, `quotes`, `schema_version`) — confirmed by source review and
by the real-run's own `mtime`-unchanged / `schema_version`-unchanged
proof (§9 below).

## 4. Replay observation identity

One observation = one exact `EntryQualification` composite identity
(`instrument_id, session_date, as_of, decision_id, methodology_version`
— `eq_identity(...)`) bound to its own exact `Decision`. Never
instrument/date alone (confirmed: 317 distinct instruments, 2 distinct
sessions, 11,986 distinct observations in the real run — far more than
one per instrument/date pair).

## 5. Population query

`SELECT ... FROM entry_qualifications WHERE decision_type IN ('WATCH','TRADE')
ORDER BY instrument_id, session_date, as_of, decision_id` — every
persisted WATCH/TRADE row, no filter on eventual actionability result,
no exclusion of any EQ state. Real run: **11,986 of 11,986** persisted
rows selected (100% — the table itself contains no other decision types,
confirming EQ persistence's own WATCH/TRADE-only gate).

## 6. Exact Decision loading

`_get_decision(store, eq.decision_id)` — a raw
`SELECT {_DECISION_COLUMNS} FROM decisions WHERE decision_id=?`, never
"latest Decision" or "latest Decision for instrument."

## 7. Exact EQ loading

`_load_eq_population(store)` — a raw bounded `SELECT` restricted to
`decision_type IN ('WATCH','TRADE')`, deserialized via the existing
`serialization.row_to_entry_qualification` (unmodified).

## 8. Decision/EQ binding validation

`_validate_binding(eq, decision)` checks, in order: Decision exists;
`decision_id`, `decision_type`, `run_id`, `cycle_id` agree; `instrument_id`
agrees when the Decision specifies one (mirroring
`EntryActionabilityEngine._validate_binding`'s own exact rule set,
including its `None`-instrument fallback). Any disagreement is
classified `UPSTREAM_BINDING_DEFECT` and the observation is skipped —
**never** silently converted into a methodology `UNKNOWN`. Real run:
**0** binding defects across all 11,986 rows.

## 9. Historical M5 query

`store.candles(instrument_id, Timeframe.M5, session_day_start(eq.as_of, tzinfo), eq.as_of)`
— identical `ts_open BETWEEN start AND end` bound `ind_stage`'s own
production `vwap_raw` fetch uses; the upper bound *is* the checkpoint,
so no future candle can structurally enter.

## 10. M5 PIT/completion semantics

`session.latest_completed_candle` and `session.completed_candles` are
imported and reused directly, unmodified — no local re-derivation of
`ts_open + 5m <= as_of`.

## 11. VWAP reconstruction

`IndicatorEngine.compute(IndicatorName.VWAP, completed_candles(...), as_of=eq.as_of)`
over the identical bounded M5 series `latest_completed_m5` is itself
selected from — the same construction ID-7E's own `ind_stage` performs.

## 12. VWAP provenance

`session_vwap_as_of = latest_completed_m5.ts_open + timedelta(minutes=5)`
— derived, never proxied from `eq.as_of`/`evaluated_at`.

## 13. M5/VWAP exact checkpoint proof

Structural by construction (§11/§12 both derive from the same selected
candle) — additionally, `EntryActionabilityMarketEvidence.__post_init__`'s
own frozen exact-equality invariant (ID-7C.1) independently re-proves
this at every single observation. Real run: **0** M5/VWAP checkpoint
violations recorded (the redundant local check never fired, as
expected).

## 14. OR15 reconstruction

`OpeningRangeEngine.assess(instrument_id, as_of=eq.as_of,
session_context=reconstructed_session_context, five_min_candles=<same
bounded series>, calendar=calendar, tzinfo=tzinfo)` — identical to
production; `SessionContext` is itself reconstructed via
`SessionContextEngine.assess` using the same bounded M5/M15/quote reads.

## 15. OR15 PIT proof

`or15.as_of` *is* `eq.as_of` (the OR engine's own `as_of` parameter);
`EntryActionabilityEngine._validate_or15_coherence` independently
re-proves instrument/session/checkpoint coherence at every observation
regardless. Real run distribution: 93.55% `COMPLETE`, 5.68% `FORMING`,
0.77% `INCOMPLETE_DATA` — a legitimate descriptive spread, never gated.

## 16. `evaluated_at` replay semantics

One fixed, module-level constant, `DEFAULT_REPLAY_EVALUATED_AT =
datetime(2026, 1, 1, tzinfo=UTC)`, reused for every observation across
the entire run — explicitly labeled in the summary metadata as "replay
compute metadata only -- NOT a historical knowledge-time claim." A
naive value is rejected with `ValueError` (tested).

## 17. `EntryActionabilityMarketEvidence` composition

Constructed with exactly the frozen four fields
(`completed_m5_close`, `session_vwap`, `session_vwap_as_of`,
`opening_range_15`) — no ATR, RS, RVOL, gap, resistance, or extension
input anywhere in the module.

## 18. Production engine invocation

`EntryActionabilityEngine().evaluate(decision=..., entry_qualification=eq,
market_evidence=..., evaluated_at=..., policy=None)` — the real,
unmodified class, imported directly from `athena.intraday`. No
replay-specific evaluator, no methodology copy anywhere in the module
(confirmed by source review and by the module's own docstring
declaration).

## 19. Replay persistence/write behavior

`save_entry_actionability` is never referenced as a call (confirmed by
a dedicated source-scan test checking for the call-site pattern, not
merely the bare identifier, since the module's own docstring
legitimately *mentions* the name in prose). No `INSERT INTO
entry_actionabilities` anywhere. The real run's own
`schema_version_observed_at_start == schema_version_observed_at_end == 17`
additionally proves no write of any kind reached the database.

## 20. Output artifact format/location

`artifacts/research/id7f1/` (git-ignored, mirroring the existing
`artifacts/research/em1b/` convention): `id7f1_observations.jsonl` (one
line per successfully-reconstructed observation), `id7f1_defects.jsonl`
(one line per classified defect), `id7f1_summary.json` (aggregate
statistics + an `analysis_sha256` reproducibility digest + full run
metadata: source DB path, schema version at start/end, run started_at
via `runtime_seconds`, the fixed `evaluated_at`, methodology version
counts). No secrets/tokens recorded.

## 21. Failure classification implementation

All four ID-7F0-relevant categories implemented and reported per-kind:
`UPSTREAM_BINDING_DEFECT`, `PIT_EVIDENCE_DEFECT` (also covers any
`ValueError` this module's own reconstruction might raise — documented
explicitly in the module docstring as a deliberate mapping, not a new
taxonomy category), `PERSISTENCE_DEFECT` (duplicate identity),
`REPLAY_EQUIVALENCE_DEFECT` (determinism mismatch). `WORKFLOW_DEFECT`
and `DATA_AVAILABILITY` are not separately counted as "defects" here —
the former has no applicable meaning for an offline reconstruction (no
`WorkflowStage` is involved), and the latter is deliberately reported
only descriptively (`evidence_availability`), never as a defect count,
per ID-7F0 §24's own explicit instruction.

## 22. Duplicate detection

`eq_identity(...)` + `partition_duplicates(...)` — pure, independently
unit-tested functions (real duplicates are additionally structurally
prevented by `entry_qualifications`'s own composite `PRIMARY KEY`,
confirmed by source review of `schema.py:478`; this is defense-in-depth,
tested directly rather than assumed unreachable). Real run: **0**
duplicates found (as expected, given the PK).

## 23. Determinism implementation

Every single observation (all 11,986, not a sample) is independently
**reconstructed and evaluated twice** — a full second bounded-candle
fetch, second `SessionContext`/OR15 reconstruction, and second
`EntryActionabilityEngine.evaluate()` call — and the two resulting
`EntryActionability` dataclass instances compared via `==` (full field
equality, since `evaluated_at` is identical by construction — the same
fixed constant both times). Real run: **0/11,986 mismatches**,
`determinism_holds: true`.

## 24. Order-independence behavior

Each observation is processed independently with no shared mutable
state across loop iterations (verified by source review — the only
cross-observation state is the append-only `seen_identity`/`defects`/
`rows` accumulators, none of which affects any other observation's own
computed result). A dedicated test confirms forward- vs. reversed-order
iteration over the same observation set yields identical per-identity
results.

## 25. Provider/network absence

Source-scan test confirms none of `kite`, `requests.`, `httpx.`,
`urllib.request` appear anywhere in the module (case-insensitive).

## 26. Currentness absence

Source-scan test confirms none of `is_currently_usable`,
`EntryActionabilityCurrentness`, `current_decision_id`, `CURRENT`,
`STALE`, `SUPERSEDED`, `SESSION_CLOSED` appear anywhere in the module.

## 27. Profitability-analysis absence

No future-relative-to-checkpoint candle is ever read (every bounded
query's upper bound is `eq.as_of` itself); no T1/T2/stop-hit/PnL/
win-rate/expectancy/MFE/MAE computation exists anywhere in the module.

## 28. Knowledge-time limitation

Stated explicitly in the summary metadata itself
(`replay_semantics: "market-time bounded deterministic reconstruction --
not bitemporal knowledge-time replay"`) and in the module's own
docstring — carried forward unchanged from ADR-013/ID-7F0.

## 29. Initial real DB schema version

**17** (`schema_version_observed_at_start`).

## 30. Final real DB schema version

**17** (`schema_version_observed_at_end`) — **unchanged**, confirmed
identical to the start value (`schema_version_unchanged: true`). No
migration was performed; none was authorized.

## 31. Real population total

**11,986** persisted `entry_qualifications` rows, all WATCH/TRADE
(matching ID-7F0's own snapshot exactly — the population has not
materially changed since 2026-09-05's earlier discovery).

## 32. WATCH count

**11,986** (100% of the population).

## 33. TRADE count

**0** — confirming ID-7F0's own finding is still current: zero
TRADE-bound `EntryQualification` rows exist in the real database.

## 34. EQ-state distribution

`NOT_YET` 8,443 (70.44%); `QUALIFIED` 1,913 (15.96%); `UNKNOWN` 985
(8.22%); `EXPIRED` 645 (5.38%). (`DISQUALIFIED_FOR_SESSION`/
`OUT_OF_SCOPE`: 0, consistent with WATCH-only, session-open-only
persistence.)

## 35. Direction distribution

**100% `NONE`** — every real persisted WATCH Decision in this population
carries `Direction.NONE` (WATCH decisions in this dataset never set a
directional bias). No LONG/SHORT signal is present in the WATCH
population at all; this is a separate, additional confirmation that
directional empirical validation depends entirely on the (currently
absent) TRADE population.

## 36. Sessions/instruments represented

2 distinct sessions (2026-09-03, 2026-09-04); 317 distinct instruments.

## 37. Rows attempted

**11,986**.

## 38. Rows reconstructed successfully

**11,986** (100%).

## 39. Binding-defect count

**0**.

## 40. PIT-evidence-defect count

**0**.

## 41. Duplicate-identity count

**0**.

## 42. Evaluation-exception count

**0** unexpected (non-`ValueError`) exceptions occurred; all
`ValueError`s that would have been raised (none were) are classified
under §40 (`PIT_EVIDENCE_DEFECT`) — none occurred in the real run.

## 43. Determinism-mismatch count

**0** of 11,986.

## 44. WATCH methodology result distribution

100% `NOT_ACTIONABLE`. Reason codes: `UPSTREAM_DECISION_NOT_TRADE` on
all 11,986 (the frozen invariant); `UPSTREAM_EQ_NOT_QUALIFIED`
additionally present on 10,073 of them (exactly the count of non-
`QUALIFIED` EQ rows, `11986 - 1913`) — directly confirming the engine's
own frozen "both upstream reasons reported together when both fail"
behavior on real production data for the first time.

## 45. TRADE methodology result distribution, if any

Not applicable — 0 TRADE observations in the real population.

## 46. UNKNOWN distribution, if any

Not applicable at the `EntryActionability` level for this population —
every real observation resolved to `NOT_ACTIONABLE` (upstream-ineligible,
since none are TRADE). `UNKNOWN` `EntryActionability` states require
TRADE + QUALIFIED, which does not occur in real data yet.

## 47. ACTIONABLE distribution, if any

Not applicable — same reason as §46.

## 48. Completed-M5 availability

93.55% present (11,213 / 11,986); 6.45% absent (773) — legitimate,
descriptive data availability, never gating for WATCH (confirmed: the
`watch_invariant_check` holds across the full population regardless of
M5 availability, since ID-7C.2's upstream short-circuit means layer-3
evidence is never even consulted for an ineligible WATCH candidate).

## 49. VWAP availability

Identical to §48 (93.55% present) — by construction, VWAP presence is
always exactly paired with completed-M5 presence in this module's
composition.

## 50. OR15 distribution

`COMPLETE` 93.55%; `FORMING` 5.68%; `INCOMPLETE_DATA` 0.77%.

## 51. M5/VWAP checkpoint violation count

**0**.

## 52. Replay wall time

**20.37 seconds** for the complete 11,986-row population (no sampling
was needed or used).

## 53. Real replay acceptance verdict

**PASS.** Every architectural acceptance criterion for a clean
WATCH-only population (ID-7F0/ID-7F1's own frozen expectation) is met
exactly: zero binding defects, zero PIT evidence defects, zero
duplicate logical identities, zero deterministic mismatches, zero
unexpected evaluator exceptions, and 100% of WATCH observations resolve
to `NOT_ACTIONABLE`/`UPSTREAM_DECISION_NOT_TRADE`. M5/VWAP availability
is 93.55%, well short of 100% — expected and explicitly not required
for WATCH per ID-7F0's own instruction.

## 54. TRADE empirical-validation availability

`TRADE_EMPIRICAL_VALIDATION_NOT_AVAILABLE` (0 real TRADE-bound EQ rows).

## 55. ACTIONABLE empirical-validation availability

`ACTIONABLE_EMPIRICAL_VALIDATION_NOT_AVAILABLE`.

## 56. UNKNOWN empirical-validation availability

`UNKNOWN_EMPIRICAL_VALIDATION_NOT_AVAILABLE` (at the `EntryActionability`
level; the *upstream* `EntryQualificationState.UNKNOWN` is well-populated,
985 rows, but that is a different, already-well-validated dimension).

## 57. SHORT empirical-validation availability

`SHORT_EMPIRICAL_VALIDATION_NOT_AVAILABLE` — reinforced further by §35's
finding that the real WATCH population carries no directional signal at
all (100% `Direction.NONE`).

## 58. Focused test results

33/33 passed (`tests/data_layer/test_id7f1_entry_actionability_replay.py`).

## 59. Full-suite results

**3,637 passed, 1 pre-existing unrelated skip, 0 failures** (up from
3,604 at ID-7E.1 closure — exactly +33, all new).
`tests/data_layer/`, `tests/market_intel/`, `tests/ops/` run together:
1,215 passed.

## 60. Schema preservation

Zero diff to `src/athena/data/store/schema.py`; the real DB's own
`schema_version` confirmed unchanged (17 → 17) by direct measurement,
not merely by absence of a code diff.

## 61. Repository preservation

Zero diff to `src/athena/data/store/repository.py`. The new module
never imports or constructs `SqliteRepository` at all — only
`ReadOnlyStore`.

## 62. Workflow preservation

Zero diff to `src/athena/runtime/workflow.py` / `src/athena/ops/owner_validation.py`.
No `WorkflowStage`/`WorkflowEngine` object is constructed or touched
anywhere in the new module.

## 63. Decision/ID-6 isolation

Zero diff to `src/athena/decision/`, `src/athena/intraday/entry_qualification_engine.py`,
`src/athena/intraday/entry_qualification_models.py`. Both are only
*read* (via the real, unmodified `EntryQualification`/`Decision`
domain objects).

## 64. EntryActionability methodology isolation

Zero diff to `src/athena/intraday/entry_actionability_engine.py` /
`entry_actionability_models.py`. The engine is imported and called
unmodified.

## 65. EMR isolation

Zero diff to `src/athena/explosive_move/`.

## 66. DarvaX isolation

Zero diff to `src/athena/darvax/`.

## 67. `git diff --check`

Clean (exit 0).

## 68. `git status`

Exactly the new module
(`src/athena/data/id7f1_entry_actionability_replay.py`) and its new test
file (`tests/data_layer/test_id7f1_entry_actionability_replay.py`) —
matches the authorized scope exactly. `artifacts/research/id7f1/` (the
real run's own output) is git-ignored and does not appear.

## 69. Remaining risks

Unchanged from ID-7F0: TRADE-bound population remains entirely absent
from real data (now doubly confirmed — both by the earlier read-only
query and by this full replay run over the identical, still-unchanged
11,986-row population); SHORT remains unvalidated; schema v18 has still
never been migrated against the live database. None of these are
defects introduced or left unaddressed by ID-7F1 — they are honestly
reported population/deployment limitations, exactly as ID-7F0 predicted.

## 70. Shadow/deployment prerequisites

Unchanged from ID-7F0 §36: (1) migrate schema v18 against the live
database, (2) restart `athena-serve` through its normal wrapper. Neither
was performed or is recommended to be performed by this milestone.
Once both occur and real cycles run, `run_shadow_equivalence` (not yet
implemented) becomes the next concrete deliverable.

## 71. Recommended next milestone (recommendation only)

Two independent options, either of which the owner may choose to
authorize next, in either order: (a) implement `run_shadow_equivalence`
now, as a dormant capability ready for the moment real production rows
exist (it needs no live data to be *written*, only to be exercised
against a schema-v18-migrated database once one exists); or (b) proceed
directly to the schema v18 migration + `athena-serve` restart
(operational, not a code milestone) to start accumulating the real
TRADE/ACTIONABLE/SHORT population this replay confirms is still
entirely absent. Recommend (b) first, since it is the actual blocker
for closing the empirical gaps §54–57 identified — no further replay
code work changes that fact.

---

## Source-review correction (ID-7F1.1, 2026-09-05)

Owner/Chief Architect source review **accepted the original 11,986-row
real historical replay result in full** (§37–53 above stand unchanged —
same population, same zero-defect outcome, same determinism proof) and
held final ID-7F1 closure for one narrow harness-accounting/
observability defect, corrected same day as ID-7F1.1:

- **`rows_attempted` accounting was unsafe.** The original formula,
  `rows_attempted = len(rows) + len(defects)`, double-counts any
  observation that both reconstructs successfully (appended to `rows`)
  **and** carries a `REPLAY_EQUIVALENCE_DEFECT` (appended to `defects`)
  — a determinism mismatch does both. The real accepted run happened to
  have zero such mismatches, so its own `11,986` figure was coincidentally
  correct, but the formula itself was not generally safe for a future
  defect-bearing run. **Fixed:** `population_total`, `duplicate_population_total`,
  `unique_population_total`, and `rows_attempted` (`= unique_population_total`,
  computed once, never derived from `len(rows) + len(defects)`) are now
  tracked as independent, explicit summary fields.
- **Unexpected (non-`ValueError`) exceptions had no dedicated
  observability.** The frozen `ValueError` → `PIT_EVIDENCE_DEFECT` rule
  is unchanged, but a genuinely unexpected per-observation failure
  previously had no distinct diagnostic category and would have
  terminated the entire replay run. **Fixed:** a new, deliberately
  separate `UnexpectedReplayException` diagnostic (never folded into
  ID-7F0's frozen defect taxonomy, never mapped to `UNKNOWN`/
  `DATA_AVAILABILITY`) catches only `Exception` (never `BaseException`/
  `KeyboardInterrupt`/`SystemExit`) around one observation's own
  reconstruction/evaluation, records it, and continues to the next
  independent observation — while forcing the run's own new explicit
  `replay_acceptance` verdict to `False` whenever any exist. A
  genuinely unexpected failure can therefore never silently "pass" a
  review of the summary.
- **A new explicit `replay_acceptance` boolean** was added, requiring
  zero binding/PIT/persistence/replay-equivalence defects, zero
  unexpected exceptions, zero determinism mismatches, zero M5/VWAP
  checkpoint violations, and zero WATCH-invariant violations — TRADE/
  ACTIONABLE/UNKNOWN/SHORT empirical availability is deliberately
  **excluded** from this criterion (those populations remain honestly
  absent from real data, per ID-7F0, and are never an acceptance gate).
- **7 new focused tests** added (proving: a determinism defect does not
  double-count its own attempt; a pre-evaluation binding failure counts
  as attempted but not reconstructed; a synthetic duplicate counts
  toward `population_total` but not `rows_attempted`; an unexpected
  `RuntimeError` is recorded under its own diagnostic, not relabeled,
  and forces `replay_acceptance` false; a `ValueError` remains
  classified `PIT_EVIDENCE_DEFECT`, never rerouted to the unexpected-
  exception bucket; an infrastructure failure (missing source DB) still
  propagates normally, proving no broad exception-swallowing boundary
  was introduced; and the clean seeded-WATCH population yields
  `replay_acceptance: true`). Full suite: **3644 passed, 1
  pre-existing unrelated skip, 0 failures** (exactly +7 from ID-7F1's
  own 3637).
- **No PIT/methodology/config/schema/repository/workflow change of any
  kind.** `M5`/`VWAP`/`OR15` reconstruction, `evaluated_at` semantics,
  Decision/EQ loading, binding validation, and the
  `EntryActionabilityEngine` call are all byte-for-byte unchanged from
  ID-7F1 — confirmed by diff (only `ReplayDefect`'s sibling
  `UnexpectedReplayException` dataclass, the population-counter
  bookkeeping, the new exception boundary, and `_replay_acceptance`
  were added).

**Rerun of the hardened harness against the real `db/athena.db`, same
strict read-only mode, complete population, no sampling:** **11,986 /
11,986** rows reconstructed successfully (population unchanged from the
original run — no source-data delta occurred between runs), **0**
binding defects, **0** PIT-evidence defects, **0** persistence/duplicate
defects, **0** replay-equivalence defects, **0** unexpected replay
exceptions, determinism holds across all 11,986 double-reconstructions,
`schema_version` unchanged at 17 → 17, and the new explicit
**`replay_acceptance: true`**. Runtime 19.83s (materially identical to
the original 20.37s). All empirical-availability flags unchanged:
`TRADE_EMPIRICAL_VALIDATION_NOT_AVAILABLE` /
`ACTIONABLE_EMPIRICAL_VALIDATION_NOT_AVAILABLE` /
`UNKNOWN_EMPIRICAL_VALIDATION_NOT_AVAILABLE` /
`SHORT_EMPIRICAL_VALIDATION_NOT_AVAILABLE`. `git diff --check`/
`git status --short` clean; diff scoped to exactly
`src/athena/data/id7f1_entry_actionability_replay.py` and its test
file — zero touches to schema/repository/workflow/Decision/ID-6/
EntryActionability methodology/EMR/DarvaX.

**ID-7F1.1 COMPLETE — ID-7F1 READY FOR FINAL OWNER / CHIEF ARCHITECT
CLOSURE.**
