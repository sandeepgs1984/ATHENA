# EM-7A — Scanner Correctness Hardening

**Status (superseded by EM-7A.1, 2026-09-03 — see §9): EM-7A COMPLETE,
READY FOR OWNER / CHIEF ARCHITECT CLOSURE REVIEW.** §§1–8 below are the
original, unmodified EM-7A record: concurrency protection, regime wiring
hardening, and isolation-test hardening were complete and tested; the
mandatory pre-implementation persistence audit found the existing
repository architecture could already produce a durable, partial
business result, directly contradicting ADR-014 §15's original stated
assumption that the current design was atomic; per explicit owner
instruction this was not silently resolved and was reported for
Owner/Chief Architect decision instead. **EM-7A.1 (§9) is the owner's
resolution of that contradiction** — persistence is now genuinely atomic,
closing the one item this document originally left open.

---

## 1. Pre-implementation persistence audit (mandatory, performed before any edit)

Read in full, before any source change: `run_scan_cycle`
(`src/athena/explosive_move/live/scanner.py`), `EmrRepository`
(`src/athena/explosive_move/store/repository.py`), the `emr_scan_runs`/
`emr_candidates`/`emr_transitions` schema
(`src/athena/explosive_move/store/schema.py`), `run_id` construction,
candidate/transition identity, `build_canonical_regime_lookup`
(`live/regime_source.py`), `test_em5_isolation.py`,
`CANDIDATE_CHECKPOINTS_IST` (`contracts.py`), and
`TRACK_B_CHECKPOINT_SCHEDULE`
(`data/live_m5_provisional_settlement_diagnostic.py`).

**Q: Is `save_candidates()` one transaction?** Yes —
`EmrRepository.save_candidates` (`repository.py:132-172`) wraps its
`executemany` INSERT in a single `with conn:` block. Atomic *among
candidates*, in isolation.

**Q: Is `save_transitions()` one transaction?** Yes, same pattern
(`repository.py:241-266`) — its own, separate `with conn:` block.

**Q: Are they in the same transaction as terminal run-status
persistence?** **No.** `run_scan_cycle` (`scanner.py:379-393`) calls
`emr_repo.save_candidates(all_candidates)`, then
`emr_repo.save_transitions(all_transitions)`, then (after computing
`finished_ts`/`total_duration_ms`) `emr_repo.save_scan_run({...,
"status": "COMPLETE", ...})` — **three separate top-level repository
calls**, each opening and committing its own independent SQLite
transaction via its own `with conn:` block. Nothing wraps all three in
one shared transaction.

**Q: What happens if candidates persist successfully but transitions
fail?** The candidate rows are **already durably committed** (the first
`with conn:` block succeeded and returned) by the time
`save_transitions` is called. If `save_transitions` then raises (e.g. a
disk-full `sqlite3.Error`, wrapped as `RepositoryError`), that exception
propagates uncaught out of `run_scan_cycle` (no `try`/`except` exists
anywhere in the function). The run's `emr_scan_runs` row is left at
`status="RUNNING"` (never reaches the final `save_scan_run(..., status=
"COMPLETE")` call) — but real, durable `emr_candidates` rows already
exist for that `run_id`, with **no corresponding transitions**.

**Q: What happens if terminal COMPLETE persistence fails?** Both
candidates and transitions are already durably committed by this point.
If the final `save_scan_run` call itself raises, the exception
propagates, the row stays at `status="RUNNING"` forever — but the
**complete, correct candidate and transition result for that run already
exists in the database**, just under a run row that never says so.

**Q: Can current source therefore actually create a persisted partial
business result even though the scanner loop itself is batch-oriented?**
**Yes — confirmed.** The in-memory computation loop is a single atomic
unit (all candidates/transitions for the whole universe are computed
in-memory before any write begins), but **persistence is not** — it is
three independent, non-transactionally-linked writes. Both windows above
(candidates-without-transitions, and complete-results-without-COMPLETE-
status) are real, reachable states in the current architecture, not
hypothetical.

## 2. ADR-014 atomicity assumption verdict

**Contradicted.** ADR-014 §15 states: *"given the current atomic
single-batch-persist-at-the-end architecture, a 'partial' outcome cannot
actually occur at the persistence layer today — a crash either happens
before the batch write... or after it."* This audit found that
assumption is **not accurate as written** — "the batch write" is
actually three separate writes, not one, and a failure between any two
of them produces a real, durable, partial result. **Per explicit owner
instruction, this document reports the contradiction rather than
silently redesigning the lifecycle or introducing `PARTIAL` unilaterally.**
The ADR's body text is left completely unmodified (per instruction, "do
not silently weaken the ADR") — only its Status field was updated to
Accepted, with a pointer to this document.

**What this does *not* invalidate**: ADR-014's `RUNNING → COMPLETE |
FAILED` (no `PARTIAL`) *decision* may still be correct — but it needs to
be re-grounded in the *actual* persistence boundary, not the assumed one.
Two honest paths forward exist (options only, not decided here):

- **Option 1 — make persistence genuinely atomic.** Wrap candidates,
  transitions, and the terminal status update in one shared transaction
  (all three `INSERT`/`UPDATE` statements inside a single `with conn:`
  block, using one repository-level method rather than three). If this
  is done, ADR-014's original assumption becomes true by construction,
  and `RUNNING → COMPLETE | FAILED` (no `PARTIAL`) is exactly correct
  with no further changes needed.
- **Option 2 — keep persistence as three separate writes, and represent
  the honest intermediate state.** This would require a state the current
  two-terminal model cannot express — some form of `PARTIAL` (or an
  equivalent honest label), contradicting ADR-014's explicit "no
  PARTIAL" decision, and would need its own owner review before being
  adopted.

This document recommends Option 1 as the smaller, cleaner change (one
new repository method combining three existing SQL statements into one
transaction, no new domain state introduced, ADR-014's decision preserved
exactly as written) — but does not implement it, since implementing
either option is itself lifecycle work this milestone was told to stop
on pending owner review.

## 3. What was implemented in EM-7A (independent of the contradiction)

The following EM-7A scope items do not depend on resolving §2 and were
completed:

### 3a. Concurrency protection

New `src/athena/explosive_move/live/scan_lock.py` — `EmrScanLock`, an
EMR-owned, `flock`-based advisory exclusive lock, structurally mirroring
`athena.ops.serve_runtime.CycleRunnerLock`'s own proven pattern without
importing it (ADR-014 §6/§9/§17: the worker/scanner-infrastructure
dependency direction must never point into canonical
`athena.ops`/`athena.scheduling`). Context-manager support
(`__enter__`/`__exit__`) guarantees release on both success and
exception. Default path: `artifacts/locks/emr-scan.lock` — distinct from
and never shared with ATHENA's canonical
`artifacts/locks/cycle-runner.lock` or any DarvaX lock. This is a
primitive only — no worker, no polling, no scheduling loop exists yet;
EM-7B is the intended future consumer.

### 3b. Mandatory regime-lookup wiring

`run_scan_cycle`'s `regime_lookup` parameter (`scanner.py`) is now a
**required** keyword argument — the prior `| None = None` default and
its silent `regime_lookup or (lambda _d: None)` fallback are both
removed. This makes the exact defect a prior production canary run found
(and an Owner/Chief Architect ruling on 2026-08-28 already required be
fixed) structurally impossible to reintroduce by omission at any future
live call site — a caller who forgets to wire
`build_canonical_regime_lookup` now gets an immediate `TypeError`, never
a silently-all-`UNKNOWN` scan. Tests that deliberately want `UNKNOWN`
regime remain fully able to pass `lambda _d: None` explicitly (dependency
injection preserved; nothing about `RegimeEngine`, regime reconstruction,
feature definitions, model inputs, or TOUCH-10 methodology was touched).

### 3c. Isolation-test hardening

Extended `tests/explosive_move/test_em5_isolation.py`:
`_FORBIDDEN_CANONICAL_IMPORTS` now also covers `athena.scoring`,
`athena.confidence`, `athena.intraday`, `athena.darvax`, `athena.ops`,
`athena.scheduling` (previously only
`decision`/`risk`/`portfolio`/`orders`/`execution`/`orchestration` were
checked in the `explosive_move → canonical` direction) — closing the
real coverage gap the EM-7 discovery found. The reverse-direction test
now also checks `intraday`/`darvax` don't import `explosive_move`. A new
test pair (`test_only_the_approved_market_data_adapter_touches_sqlite_
repository_in_live_runtime`, `test_approved_live_runtime_sqlite_adapter_
exists_and_is_read_only_by_construction`) specifically protects "no
canonical write repository from live EMR runtime" — scoped to
`explosive_move/live/` only (the actual runtime path), allowing exactly
`market_data_port.py` (the already-approved, structurally read-only
adapter) and confirming by source inspection that it never calls any
canonical write method. `em1r2_materialize.py` (an offline research
script outside `live/`) is correctly out of scope for this specific
runtime-boundary guarantee, not silently exempted from a rule that
should apply to it — it lives outside the directory this test polices.

### 3d. Checkpoint-constant consolidation — deferred, not forced

Audited both hardcoded 9-checkpoint definitions
(`contracts.CANDIDATE_CHECKPOINTS_IST`,
`data/live_m5_provisional_settlement_diagnostic.TRACK_B_CHECKPOINT_
SCHEDULE`). No circular-import risk exists (`contracts.py` has zero
internal-package imports; nothing in `explosive_move/` imports the
diagnostic module). **Consolidation was deliberately not performed.**
`TRACK_B_CHECKPOINT_SCHEDULE`'s own docstring states its duplication is
**intentional**: *"This is NOT re-derived from
`athena.explosive_move.contracts.CANDIDATE_CHECKPOINTS_IST` (which
already matches it) — it is pinned here as its own independently-verified
constant so Track B's schedule can never silently drift from what was
actually proven, even if the contracts module ever changes."* Forcing a
mechanical merge would destroy a documented, deliberate safety property
(an independent verification pin), not fix an accidental duplicate. Per
ADR-014 §10 and this milestone's own instruction ("if importing across
the current package boundary creates undesirable coupling, leave the
duplicate unchanged and defer consolidation to EM-7B"), this is deferred
— the ownership designation itself (ADR-014 §10: `contracts.
CANDIDATE_CHECKPOINTS_IST` is canonical) stands unchanged.

## 4. What was NOT implemented, and why

Directly gated by §2's contradiction — not implemented in this
milestone, pending owner decision:

- Terminal `FAILED` status / exception handling in `run_scan_cycle`.
- Safe retry/idempotency enforcement on `save_candidates`/
  `save_transitions` (no uniqueness constraint exists today).
- Any transactional-consistency change (Option 1 or Option 2 in §2).
- `emr_scan_runs.status` enum/constant formalization (deferred alongside
  the above — no new terminal states should be added until the
  transaction boundary itself is settled).

No EMR schema change was made. No worker/scheduler/config-gate/CLI code
was added (correctly out of EM-7A scope regardless of §2). No
`db/emr.db` was created; no provider call was made; no EMR scan was
triggered.

## 5. Determinism

Unaffected. `run_scan_cycle`'s deterministic `run_id` fingerprint
(`(session_date, checkpoint, universe, model_version)` → SHA256) is
unchanged — confirmed by
`test_two_independent_runs_against_identical_inputs_produce_byte_
identical_scores`, which still passes unmodified. No feature, evidence
score, model coefficient, calibration, threshold, TOUCH-10 semantic,
label, or MFE/MAE methodology was touched. FINAL_TEST was not reopened.

## 6. Mutation/negative proof (temporary, not left in the tree)

Three targeted mutations were applied, confirmed to fail the relevant
tests, then reverted (confirmed via `git diff` showing no residual
change):

1. **Lock bypass** — commented out the `flock` call inside
   `EmrScanLock.acquire()`. Result: 3 tests failed
   (`test_second_concurrent_acquisition_is_denied`,
   `test_context_manager_acquires_and_releases_on_success`,
   `test_context_manager_raises_busy_error_when_already_held`).
2. **Silent regime fallback reintroduced** — restored the old
   `regime_lookup or (lambda _d: None)` default. Result:
   `test_omitting_regime_lookup_fails_loudly_rather_than_silently_
   defaulting` failed ("DID NOT RAISE TypeError").
3. **Forbidden canonical import** — added `import athena.ops` to
   `scan_lock.py`. Result: both the general isolation test
   (`test_explosive_move_never_imports_canonical_decision_risk_
   execution`) and the lock-specific regression guard
   (`test_lock_never_imports_canonical_ops_or_scheduling`) failed.

All three mutations were reverted; `git diff` on the affected files
after reversion shows only the intended, permanent changes.

## 7. Test results

Focused: `tests/explosive_move/test_em5_scanner.py` (7, was 6 — 1 new),
`tests/explosive_move/test_em5_isolation.py` (6, was 4 — 2 new),
`tests/explosive_move/test_em7a_scan_lock.py` (10, new file) — all
passing. Full `tests/explosive_move/` + `tests/api/v1/test_emr_router.py`:
**460 passed** (was 449). Full repository suite: **3,272 passed** (was
3,259), 0 skipped. Ruff clean on every touched/created file. `git diff
--check` clean.

## 8. Recommendation

Owner/Chief Architect review of §2's contradiction is required before
EM-7A can be completed. This document recommends **Option 1** (wrap
candidate/transition/terminal-status persistence in one shared
transaction) as the smaller, cleaner resolution that preserves ADR-014's
`RUNNING → COMPLETE | FAILED` decision exactly as written — but does not
implement it here, since doing so is itself the lifecycle work this
milestone was instructed to pause on. Once the owner selects a
resolution, the remaining EM-7A scope (terminal failure semantics, retry/
idempotency, transactional consistency, and their tests) can proceed as
a small, focused follow-up slice.

## 9. EM-7A.1 resolution and closure (2026-09-03)

**Owner selected Option 1** exactly as recommended in §8: result
persistence made genuinely atomic; `PARTIAL` lifecycle state rejected.
Full design/implementation record lives in the EM-7A.1 authorization and
its implementation; this section closes out the specific items §4 left
open.

**Terminal `FAILED` status / exception handling** — implemented.
`run_scan_cycle` (`scanner.py`) now wraps its computation in
`try`/`except Exception`; every run-level exception after the `RUNNING`
row is written terminates the run `FAILED` via
`EmrRepository.mark_scan_failed` (its own separate transaction, bounded
`failure_type`/`failure_reason` diagnostics — never an unbounded
traceback or secrets/tokens/headers/provider payloads). If the
`FAILED`-write itself also raises, the original scan exception is
re-raised as primary (`raise exc from mark_exc`) with the secondary
failure chained as `__cause__` — the original failure is never masked.

**Safe retry/idempotency enforcement** — implemented, two layers (ADR-014
§16, corrected): `EmrRepository.commit_scan_result`'s delete-then-insert
replace-for-run step (primary mechanism, inside the atomic transaction)
plus a `UNIQUE(run_id, instrument_id, family, threshold_percent)` index
on `emr_candidates`/`emr_transitions` (defense-in-depth, schema v2).
Three same-`run_id` cases are handled explicitly in `run_scan_cycle`,
checked before any provider call: existing `COMPLETE` → reconstructed
from persisted state with zero recomputation and zero second
checkpoint-price call; existing `RUNNING` → rejected
(`EmrScanAlreadyRunningError`), never guessed stale; existing `FAILED` →
retried under the same deterministic `run_id`.

**Transactional-consistency change (§2's Option 1)** — implemented.
`EmrRepository.commit_scan_result` is the one transaction wrapping
candidates + transitions + the terminal `COMPLETE` write; `scanner.py`
calls it once, replacing the three previously-separate calls. Verified
by direct mutation/negative proof (not merely by passing tests written
under the assumption it works): `commit_scan_result` was temporarily
split back into three separate `with conn:` blocks (mirroring the
original, disproven architecture) and re-run against this document's own
new test suite — the two dedicated one-transaction-boundary tests and
two of the four failure-injection rollback tests failed exactly as
expected (candidates survived a transitions-write failure; the observed
commit count rose from 2 to 4), then the mutation was reverted and
`git diff`/`diff` against the pre-mutation file confirmed byte-identical
restoration. The `UNIQUE` index was separately mutation-tested the same
way (downgraded to a non-unique index; the duplicate-insert protection
test failed as expected; reverted).

**`emr_scan_runs.status` enum/constant formalization** — still not
formalized as a Python enum/constant (remains plain strings
`"RUNNING"`/`"COMPLETE"`/`"FAILED"`/`"SKIPPED_SESSION_TYPE"` throughout,
matching the codebase's existing convention for this table). Not
required by any EM-7A.1 acceptance criterion; left for a future
milestone if it becomes a real pain point, not invented speculatively
here.

Full test suite (`tests/explosive_move/` + `tests/api/v1/test_emr_router.py`):
**467 passed** (was 460), 0 skipped in this scope. Full repository suite:
**3,279 passed**, 1 skipped (pre-existing, unrelated), 0 failed. Ruff
clean on every touched/created file. `git diff --check` clean.

**EM-7A is now COMPLETE.** All items in ADR-014 §30's exit contract are
satisfied: exception handling / explicit `FAILED` (§15), idempotent
candidate/transition persistence under replay (§16), the EMR-owned
concurrency lock exercised by tests (§17, unchanged from §3a),
`regime_lookup` coherence (§20, unchanged from §3b), the checkpoint-
schedule duplication explicitly deferred with a documented reason (§3d,
unchanged), the isolation-test extension passing (§3c, unchanged), and
tests proving no ADR-012 violation was introduced.
