# ID-7F3 — Entry Actionability Production-vs-Replay Mode B Shadow Equivalence

Status: **ID-7F3 MODE-B PRODUCTION EQUIVALENCE EXACT — READY FOR OWNER /
CHIEF ARCHITECT REVIEW.** Not marked Owner-approved.

## 1. Objective

Independently reconstruct real persisted production `EntryActionability`
observations using the frozen ID-7F0 Mode-B contract and compare the
independent offline result against the production-persisted artifact,
field-by-field. This is deterministic behavioral-equivalence validation —
not methodology tuning, not profitability analysis, not currentness
validation, not historical backfill, not a second live evaluator, and not
a new production execution path.

## 2. Scope and safety

All work in this milestone is read-only against canonical production
data (`db/athena.db` opened via SQLite URI `mode=ro` + `PRAGMA
query_only=ON`, exactly mirroring ID-7F1's own established pattern). No
restart, migration, row modification, or synthetic production cycle was
triggered. No provider/network call was made. `symbol_validate` was not
triggered to manufacture test cases — the harness only reads rows the
production system has already persisted through its own real paths.
Every output artifact is disposable JSON/JSONL under
`artifacts/research/id7f3/` (git-ignored).

## 3. Implementation approach

Rather than a new module, `run_shadow_equivalence` was added directly to
the existing `src/athena/data/id7f1_entry_actionability_replay.py` —
reusing `ReadOnlyStore`, `_get_decision`, `_reconstruct_market_evidence`,
and `_validate_binding` verbatim, per the authorization's own "reuse
ID-7F1/ID-7F1.1 hardened infrastructure, do not build a duplicate
framework" instruction. The module's own docstring (previously: "Mode B
... explicitly NOT implemented here") was updated in place to point at
the new function.

### 3.1 Population and the frozen validation cutoff

Unlike Mode A (which derives its population from `entry_qualifications`),
Mode B's population is the **persisted `entry_actionabilities` table
itself** — every row with `persisted_at <= validation_cutoff`, where
`validation_cutoff` is captured (`datetime.now(timezone.utc)`) *before*
the population query runs, so a live natural cycle ticking mid-audit
cannot create a moving denominator (§3 of the authorization, honored
literally). Rows are additionally partitioned on their own composite
identity as defense-in-depth against a duplicate (structurally already
prevented by the table's own `PRIMARY KEY`).

### 3.2 Exact identity resolution

For each persisted row, the exact `decision_id` and the exact upstream
`EntryQualification` (its full 5-field composite identity — instrument,
session_date, `as_of`, `decision_id`, methodology_version — copied
verbatim from the persisted row) are resolved. Never "latest Decision,"
never "latest EQ." A missing or incoherent binding is classified
`BINDING_MISMATCH` and excluded from further processing (never silently
treated as a legitimate methodology outcome).

### 3.3 Point-in-time evidence reconstruction and evaluation

The same bounded M5/VWAP/OR15 reconstruction ID-7E's production stage
performs live is independently re-derived using only canonical persisted
data (`_reconstruct_market_evidence`, unchanged from Mode A) and fed
into the real, unmodified `EntryActionabilityEngine.evaluate(...,
policy=None)`. A fixed, non-semantic `evaluated_at`
(`DEFAULT_REPLAY_EVALUATED_AT`, 2026-01-01 UTC — the same constant Mode A
already uses) is supplied so wall-clock time cannot influence the
methodology output. Each observation is reconstructed and evaluated
**twice**, independently, and the two results compared for exact
equality — a genuine whole-pipeline determinism proof, not merely a
repeated call on cached objects (mirrors Mode A's own determinism
contract exactly).

### 3.4 The comparison mask

The frozen ID-7F0 20-field shadow-equivalence set — "excluding only
`evaluated_at`/`persisted_at`" — is implemented as `_identity_tuple`
(the 7-field composite identity) plus `_methodology_payload`, whose
field list is a direct mirror of
`athena.data.store.repository._entry_actionability_payload`'s own
already-frozen conflict-detection tuple: `decision_type`, `direction`,
`entry_qualification_state`, `state`, `reason_codes`,
`evidence_finality`, `evidence_as_of`, `entry_reference`,
`entry_location_context`, `operative_invalidation`, `reward`,
`opening_range_context`, `explanation`. `run_id`/`cycle_id` are excluded
(already proven against the canonical Decision by binding validation);
`evaluated_at` is excluded (diagnostic wall-clock only, per
`EntryActionability`'s own docstring); `persisted_at` is excluded by
construction — it is not even a domain-object field, only
write/audit metadata the repository layer carries separately. Nothing
is silently dropped: the full included/excluded field lists are echoed
in every run's own `metadata` block.

### 3.5 Mismatch classification

A genuine disagreement is classified most-specific-first, never a
single generic bucket: identity mismatch → `PROVENANCE_MISMATCH`;
denormalized upstream context (`decision_type`/`direction`/
`entry_qualification_state`) mismatch → `PROVENANCE_MISMATCH` (checked
*before* `state`, so a deeper upstream-context disagreement is never
misreported as a mere state difference); `state` → `STATE_MISMATCH`;
`reason_codes` → `REASON_MISMATCH`; any of the five value objects →
`VALUE_OBJECT_MISMATCH`; `evidence_finality`/`evidence_as_of` →
`PROVENANCE_MISMATCH`; `explanation` text alone → `VALUE_OBJECT_MISMATCH`
(fallback). A dedicated mutation/negative test (§5) proves this
classifier actually fires on a genuine disagreement rather than always
reporting a false `EXACT_MATCH`.

### 3.6 Path-specific reporting

Each observation's `run_id` is joined against `runs.config_snapshot_id`:
`'cfg-symbol-validate'` → `symbol_validate` path, anything else →
`scheduled_cycle` path. This is descriptive provenance only — the exact
same frozen evaluator contract is applied to both paths; no different
methodology expectation exists for either.

### 3.7 Defect/exception accounting (ID-7F1.1 conventions reused)

`population_total`, `duplicate_population_total`, `unique_population_total`,
`rows_attempted` (set once to `unique_population_total`, never derived
from summing rows/defects), `rows_reconstructed_successfully`,
`observations_with_defects`, `binding_defects`, `pit_evidence_defects`
(a `ValueError` during reconstruction/evaluation, after binding was
already proven — mirrors Mode A's `PIT_EVIDENCE_DEFECT` rule exactly,
renamed `PIT_EVIDENCE_MISMATCH` for Mode B's own taxonomy),
`evaluation_exceptions` (reported as identical to `pit_evidence_defects`
— every `ValueError` raised during evaluation is, by the frozen rule
above, a PIT-evidence defect; there is no separate "evaluation-only"
exception category the frozen taxonomy distinguishes), a dedicated
`UnexpectedReplayException` diagnostic for any non-`ValueError` failure
(never silently relabeled, forces `mode_b_acceptance = False`),
`determinism_mismatches`, and `production_equivalence_mismatches` (by
kind). No observation is double-counted across categories.

## 4. Focused tests

23 new tests appended to
`tests/data_layer/test_id7f1_entry_actionability_replay.py`:
comparison-mask exclusion proofs (`run_id`/`cycle_id`/`evaluated_at`
differences do not affect payload equality; a real identity difference
does), all mismatch-classification categories including the
context-vs-state ordering proof, a genuine **mutation/negative proof**
that directly `UPDATE`s a persisted row's `reason_codes_json` in a
disposable temp DB and confirms the harness catches it as a real
`REASON_MISMATCH` (not a false `EXACT_MATCH`), path classification
(`symbol_validate` vs. `scheduled_cycle`, via a synthetic `runs` row —
the `OwnerValidationPipeline.run(...)` test-seed path itself never
writes a `runs` row, so this test inserts one directly to exercise the
join), validation-cutoff freeze semantics (a cutoff strictly before the
only row's `persisted_at` excludes it), naive-`validation_cutoff`/naive-
`evaluated_at` rejection, never-mutates-source-DB, schema-version-
unchanged, a zero-`save_entry_actionability`-call-site source scan
(checking the call pattern, not the bare identifier, since the module's
own docstring mentions the name in prose), and infrastructure-failure
propagation (a missing source DB fails fast, never silently absorbed).

Full focused-file result: **58 passed** (35 pre-existing Mode-A tests +
23 new). Full repository suite: **3736 passed, 1 pre-existing unrelated
skip, 0 failures** (was 3644 at ID-7F1.1's own close — the remaining
delta reflects unrelated Portfolio Intelligence V2 / My Portfolio work
committed between milestones, not this change).

## 5. Real production run

Executed against the real, live `db/athena.db` in strict read-only mode
(zero writes, zero provider/network calls, confirmed by source scan and
by the module's own `save_entry_actionability(` /
`INSERT INTO entry_actionabilities` absence checks):

- **`validation_cutoff = 2026-09-07T04:15:24.789127+00:00`** (captured
  immediately before the population query).
- **`population_total = 488`**, **`unique_population_total = 488`**
  (0 duplicates — the table's own composite `PRIMARY KEY` already
  prevents them; independently re-checked here).
- **`rows_attempted = 488`**, **`rows_reconstructed_successfully = 488`**.
- **`binding_defects = 0`. `pit_evidence_defects = 0`.
  `unexpected_replay_exceptions.total = 0`. `determinism_mismatches = 0`.
  `production_equivalence_mismatches.total = 0`.**
- **`exact_match_count = 488` (100.0%).**
- **Path-specific: `scheduled_cycle` 486/486 exact (100%);
  `symbol_validate` 2/2 exact (100%).**
- `schema_version_observed_at_start = 18`,
  `schema_version_observed_at_end = 18` — unchanged by this run.
- **`mode_b_acceptance: true`.**

### 5.1 Population distributions (real, not sampled)

- Session distribution: `2026-09-04` → 2 (0.41%), `2026-09-07` → 486
  (99.59%).
- Decision-type distribution: `WATCH` → 408 (83.61%), `TRADE` → 80
  (16.39%).
- EQ-state distribution: `EXPIRED` → 228 (46.72%), `NOT_YET` → 169
  (34.63%), `UNKNOWN` → 76 (15.57%), **`QUALIFIED` → 15 (3.07%)**.
- Persisted EA-state distribution: `NOT_ACTIONABLE` → 479 (98.16%),
  **`UNKNOWN` → 9 (1.84%)**. `ACTIONABLE` → 0.
- Direction distribution: `NONE` → 408 (83.61%), `SHORT` → 80 (16.39%).
  `LONG` → 0.

### 5.2 New empirical coverage (first time in the entire ID-7 track)

Every prior ID-7B/ID-7B.1/ID-7F0/ID-7F1/ID-7F1.1 report found **zero**
TRADE decisions in the live database at all (the last TRADE predated EQ
persistence itself, 2026-08-27). Because the production system kept
running real scheduled cycles throughout this milestone — the exact
"moving denominator" `validation_cutoff` exists to control for, not
avoid — this run is the first to observe:

- **15 genuine `EntryQualification.state == QUALIFIED` rows**, all
  bound to real `TRADE` Decisions — `TRADE_QUALIFIED_AVAILABLE` for the
  first time.
- **9 genuine persisted `EntryActionability.state == UNKNOWN` rows** —
  `UNKNOWN_AVAILABLE` for the first time. All 9 are TRADE+QUALIFIED
  observations where layer-3 evidence (M5/VWAP/geometry) was
  insufficient — the frozen V0 evaluator's own designed behavior, not
  an anomaly.
- All 15 TRADE_QUALIFIED and all 9 UNKNOWN observations reconstructed
  to the **exact same result** as the persisted production artifact —
  0 mismatches among them.
- `ACTIONABLE` and `LONG` remain **`NOT_AVAILABLE`** — every real TRADE
  decision observed to date carries `direction == SHORT`. This is
  unrelated to, and does not resolve, the previously-documented EQ
  long-bias finding (ID-7B: the EQ v0 formula itself requires VWAP
  ABOVE + trend BULLISH unconditionally, with no symmetric SHORT path)
  — `LONG_VALIDATED_SHORT_UNVALIDATED` stands exactly as before, since
  it concerns EQ's own directional bias, not EntryActionability's
  evaluation of whichever direction a Decision happens to carry. No
  numeric methodology conclusion is drawn from this observation; it is
  recorded purely as new descriptive population evidence.

## 6. Acceptance

All frozen §14 acceptance conditions are met: 0 exact binding defects,
0 PIT reconstruction defects, 0 unexpected exceptions, 0 determinism
mismatches, 0 production-equivalence mismatches, both paths (scheduled-
cycle and `symbol_validate`) match exactly, zero production writes,
zero provider/network calls, schema remains 18, the production service
was never touched, methodology is unchanged, and EMR/DarvaX remain
isolated. The absence of `ACTIONABLE`/`LONG` empirical examples is
recorded as an empirical-coverage limitation, not manufactured, and is
explicitly not required for acceptance per the authorization's own
terms.

## 7. Verification

`git diff --check`: clean. `git status --short` (source/tests only):

```
 M src/athena/data/id7f1_entry_actionability_replay.py
 M tests/data_layer/test_id7f1_entry_actionability_replay.py
```

Zero touches to `schema.py`/`repository.py`/`entry_actionability_engine.py`/
`entry_actionability_models.py`/`owner_validation.py`/Decision/ID-6
methodology/EMR/DarvaX. No live-process, schema, or data-modification
action was taken at any point; PID 2453 and every persisted row remain
untouched.

## 8. Recommended next step (recommendation only)

Mode-B has now proven exact deterministic equivalence against the
complete real production population available today, across both real
invocation paths, including newly-available TRADE+QUALIFIED/UNKNOWN
examples. Natural production accumulation should continue; a future
milestone could re-run this same harness periodically (or the owner may
simply re-invoke `run_shadow_equivalence` ad hoc) as the population
grows toward eventually including `ACTIONABLE`/`LONG` examples, without
requiring a new implementation. No further ID-7F3.x correction appears
necessary from this run's evidence.

---

**ID-7F3 MODE-B PRODUCTION EQUIVALENCE EXACT — READY FOR OWNER / CHIEF
ARCHITECT REVIEW.**
