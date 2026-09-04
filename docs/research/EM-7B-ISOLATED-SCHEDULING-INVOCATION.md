# EM-7B — Isolated EMR Scheduling & Invocation

**Status: EM-7B IMPLEMENTATION COMPLETE — READY FOR OWNER / CHIEF ARCHITECT
REVIEW.** Owner authorized 2026-09-03, same day as EM-7A/EM-7A.1/EM-7A.2's
closure. Implements the isolated EMR operational scheduling/invocation layer
frozen by ADR-014 — makes EMR fully fixture-testable as an unattended
scheduled worker, without activating production EMR in any way.

---

## 1. Scope

Owner-authorized (2026-09-03): "Implement ONLY the isolated EMR operational
scheduling/invocation layer frozen by ADR-014. EM-7B must make EMR fully
fixture-testable as an unattended scheduled worker, but MUST NOT activate
production EMR." Every EM-7A/EM-7A.1/EM-7A.2 contract (`run_scan_cycle`,
`run_scan_cycle_with_lock`, `EmrScanLock`, `commit_scan_result`,
`mark_scan_failed`, the `RUNNING → COMPLETE | FAILED` lifecycle, the
in-memory-only `SKIPPED_SESSION_TYPE` eligibility outcome, mandatory
`regime_lookup`, schema v2) is preserved exactly — this milestone adds
scheduling/invocation around them, never redesigns them.

## 2. Files

**Created:**

- `config/emr/operational.json` — EMR-owned operational config, shipped
  `enabled: false`.
- `src/athena/explosive_move/live/operational_config.py` — `EmrOperationalConfig`
  (pydantic, strict, mirrors DarvaX's `_Strict` pattern independently) +
  loader (missing file → safe disabled default; malformed/unknown-key file →
  fails loudly).
- `src/athena/explosive_move/live/worker.py` — the worker itself: `run_once`
  (pure, synchronous, fully injectable tick), `EmrWorkerTickOutcome`,
  `_MatureHistoryMarketDataPort`, `EmrWorker` (daemon-thread wrapper).
- `tests/explosive_move/test_em7b_operational_config.py` (8 tests),
  `tests/explosive_move/test_em7b_worker.py` (29 tests).

**Modified:**

- `src/athena/explosive_move/live/scanner.py` — one small, behavior-preserving
  extraction: `compute_run_id(*, session_date, checkpoint, universe,
  model_version) -> str` is now a public function; `run_scan_cycle` calls it
  instead of inlining the same four lines. Byte-identical output, verified by
  every existing deterministic-run-id test continuing to pass unmodified
  (including EM-7A.1/EM-7A.2's own independent formula pins). Needed so the
  worker can look up `emr_repo.get_scan_run(...)` for a not-yet-attempted
  checkpoint without duplicating the fingerprint formula (drift risk).
- `tests/explosive_move/test_em5_isolation.py` — extended the existing
  `SqliteRepository`-in-`live/`-boundary test (previously scoped to
  `market_data_port.py` alone) to also approve `worker.py` as a second,
  read-only importer, with the same grep-based "no write-method call" proof
  applied to both.

## 3. Two design decisions requiring an audit before deciding

### 3a. Checkpoint-due / catch-up policy (the primary open question)

Owner: *"If the correct policy is ambiguous from existing source/docs, STOP
with ONE owner question rather than inventing behavior. This is the most
important EM-7B design decision."*

**Audit performed** (grep, not assumed): searched ADR-014 in full, the EM-5
design contract, `docs/research/EM-7-DISCOVERY.md`, and the EM-5 Track B
live-capture record for `catch.up`, `missed`, `every checkpoint`,
`independently captured`, `burst` — **zero matches anywhere.** Track B's own
one-time, all-9-checkpoint capture (2026-09-01) was a deliberate historical
exercise validating settlement/provisional-price semantics for one specific
date; nothing in its record, or anywhere else, states that an *ongoing*
shadow worker must independently capture every checkpoint or back-fill missed
ones after a restart.

**Conclusion:** no evidence contradicts the owner's own explicitly stated
preference ("run the latest due checkpoint not yet represented, not every
missed checkpoint in a burst"), so it is implemented directly rather than
escalated as a genuinely open question — this is applying the owner's own
already-stated default under an audited absence of contradiction, not
inventing new behavior.

**Algorithm** (`worker.py`'s `run_once`): on every tick, derive
`session_date = now.date()`; ask the calendar for that day's `session_type`;
if not scannable, stop (§3b handles this). Otherwise compute the single
LATEST checkpoint (from `CANDIDATE_CHECKPOINTS_IST`'s own frozen, ascending
order) whose instant has arrived (`<= now`). If that checkpoint's
deterministic `run_id` (via `compute_run_id`) already has a persisted
`COMPLETE` or `FAILED` row, do nothing (`ALREADY_REPRESENTED`) — both statuses
are treated as terminal from the *worker's own automatic scheduling*
perspective (§3c explains why FAILED is included). Otherwise, invoke.
Earlier missed checkpoints (before the latest due one) are never separately
attempted by this algorithm, by construction — it only ever looks at the one
latest-due identity per tick.

### 3b. Universe-policy wiring — a real structural gap, resolved without
touching the frozen scanner contract

ADR-014 §11 is unambiguous about *what* the universe must be: "The initial
EM-7 shadow universe is the mature-history subset, not the unfiltered
universe" — and explicitly confirms the two are factually distinct
populations (518 mature vs. the larger raw `athena_core`). But `run_scan_cycle`'s
frozen `ScanCycleConfig.universe` field is a plain name, resolved *internally*
via `market_port.resolved_universe(config.universe)` — there is no parameter
for an explicit instrument-id list, and the read-only `EmrMarketDataPort` has
no write method (correctly, by ADR-012 isolation) to materialize a new
persisted universe in `db/athena.db` that could carry a pre-filtered
population under its own name.

**Resolution (no scanner-contract change):** `_MatureHistoryMarketDataPort`
is a worker-owned wrapper implementing the same `EmrMarketDataPort` Protocol.
Its `resolved_universe()` intercepts the one universe label the worker
constructs (`f"{base_universe}-mature-history"`) and returns the
already-computed `select_mature_history_instruments()` output directly — the
exact, unmodified function `canary_gate.py`'s own already-approved canary
uses for precisely this purpose, computed fresh each checkpoint from real,
already-ingested D1 candles. `list_instruments`/`candles_for_instruments`
delegate straight through to the real, unwrapped port. `run_scan_cycle`
itself is never touched, never gains a new parameter, and behaves exactly as
it did before this milestone from its own perspective — it just happens to
be handed a port whose `resolved_universe()` already did the narrowing.

No new eligibility rule is introduced (§11's own "do not create a new ranking
or eligibility rule" instruction) — `select_mature_history_instruments` is
reused exactly as-is. If it returns an empty set (all-immature or empty
universe), the worker refuses to invoke (`UNEXPECTED_ERROR`, no provider
call) rather than scan a degenerate population.

## 4. Failure/idempotency ownership boundary (§20-22 of the authorization)

- **COMPLETE**: the scanner's own EM-7A.1 short-circuit already makes a
  repeat invocation cheap and safe; the worker additionally pre-filters it
  out entirely (no invocation at all) once a COMPLETE row exists, avoiding
  even that cheap call on every subsequent poll.
- **FAILED**: deliberately **not** auto-retried by the worker's own polling —
  a FAILED checkpoint stays terminal from the worker's perspective for the
  rest of that checkpoint's life, preventing a retry storm (re-running the
  full scan, including a real provider call, on every poll interval). Manual/
  owner-triggered retry of a FAILED run remains possible by invoking the
  scanner directly under the same deterministic `run_id` (EM-7A.1's own
  retry mechanism, untouched) — the worker itself simply never does so
  automatically. Proven by `TestFailedRetryOwnership` and a required
  mutation/negative test (below).
- **RUNNING**: not pre-filtered at the worker level — the worker still
  attempts, and `run_scan_cycle`'s own dispatch raises
  `EmrScanAlreadyRunningError`; the worker catches this, logs "checkpoint
  already owned," and returns without retrying faster than the normal poll
  cadence. No stale-RUNNING-age guessing, matching EM-7A.1's own explicit
  design.

## 5. Restart recoverability

All "already represented" / "already running" / "already failed" state is
derived by querying `emr_repo.get_scan_run(compute_run_id(...))` against
persisted `emr_scan_runs` state — no separate scheduler-state database, no
in-memory-only bookkeeping. `TestRestartBehavior` constructs an entirely
fresh `EmrRepository`/`CalendarEngine` pair pointed at the same on-disk file
(simulating a process restart) and proves: a redundant poll for an
already-COMPLETE checkpoint does not re-invoke the provider, and the next
checkpoint proceeds normally.

## 6. Lock entrypoint

`run_once` calls `run_scan_cycle_with_lock`, never raw `run_scan_cycle`.
Proven behaviorally (not by mutation): `TestLockEntrypointProof` holds the
same `EmrScanLock` path externally and confirms a tick correctly returns
`LOCK_BUSY` rather than wrongly succeeding — if `run_once` called the raw,
lock-free entrypoint instead, external lock-holding would have no effect and
this test would fail.

## 7. Regime wiring

The worker constructs `build_canonical_regime_lookup(market_port=...,
config_dir=..., tzinfo=...)` — the real function, never `lambda _d: None` —
and passes it to `run_scan_cycle_with_lock`. `TestRegimeWiring` spies on the
real function to prove it is actually invoked with the correct dependencies
on every tick.

## 8. Config ownership

`config/emr/operational.json` mirrors DarvaX's config-gate *pattern* only
(independent `_Strict` base, same "unknown keys fail loudly," same
"`enabled` defaults to `False`") — no DarvaX code is imported. Fields are
operational-only (`enabled`, `base_universe`, `model_version` — a version
*selector*, not methodology — `max_staleness_minutes`,
`max_checkpoint_price_delay_seconds`, `poll_interval_seconds`); no
feature/model/calibration/threshold parameter was added or duplicated. A
missing file loads as an explicit `{"enabled": false}`; a present-but-invalid
file (bad JSON, wrong types, unknown keys) fails loudly rather than silently
resolving to enabled behavior.

## 9. Production-DB non-activation

The worker is never mounted into `athena serve`/any production entrypoint —
`src/athena/ops/serve_runtime.py` and the CLI are untouched by this
milestone. `config/emr/operational.json` ships `enabled: false`. Verified by
filesystem check at milestone end: `db/emr.db` absent, no EMR process
running.

## 10. Required mutation/negative proofs (performed, reverted)

1. **Mature-history filter bypass** — `mature_ids` temporarily set to the
   unfiltered `base_universe_ids` (simulating "the filter silently does
   nothing"). Result: exactly the two `TestMatureHistoryUniverseWiring`
   tests failed as expected (the immature instrument appeared in the
   scanned population; the all-immature-universe refusal never fired); all
   other tests unaffected. Reverted, `diff` against a pre-mutation backup
   confirmed byte-identical restoration.
2. **FAILED-auto-retry gate removed** — the `("COMPLETE", "FAILED")`
   terminal-status check temporarily narrowed to `("COMPLETE",)` alone.
   Result: exactly `TestFailedRetryOwnership`'s test failed (the worker
   re-invoked the provider for an already-FAILED checkpoint); all other
   tests unaffected. Reverted, confirmed identical.
3. **Forbidden canonical import** — `import athena.ops` temporarily added to
   `worker.py`. Result: `test_explosive_move_never_imports_canonical_decision_risk_execution`
   failed as expected. Reverted, confirmed identical.

## 11. Validation

Focused: `test_em7b_operational_config.py` (8), `test_em7b_worker.py` (29) —
all passing. `tests/explosive_move/` + `tests/api/v1/test_emr_router.py`:
**502 passed** (was 473), 1 pre-existing unrelated skip. Full repository
suite: **3,314 passed** (was 3,285), 1 skipped, 0 failed. Ruff clean on every
touched/created file. `git diff --check` clean.

## 12. Explicit non-scope (per the owner's own prohibitions)

No EM-7C (production DB activation), no EM-7D (live shadow validation), no
EM-7E, no EM-8. No worker mounted into any production process. No manual-run
CLI (not required for deterministic fixture testing). No HTTP mutation
endpoint. No model/feature/calibration/threshold/ranking/MFE-MAE/FINAL_TEST
change. No EM-6 presentation change. ID-7P0 and DarvaX untouched.

## 13. EM-7B closure checklist

- [x] EMR-owned, config-gated worker; stays inert when disabled (verified:
      zero repository initialization, zero DB creation, zero scanner
      invocation, zero provider call).
- [x] Deterministic checkpoint identity via the frozen 9-checkpoint policy
      (`CANDIDATE_CHECKPOINTS_IST`, consumed directly, never the Track-B
      independent-verification pin).
- [x] Frozen mature-history universe policy, wired without touching the
      scanner contract; proven to actually narrow the population.
- [x] Canonical regime lookup constructed and wired; proven by spy.
- [x] `run_scan_cycle_with_lock` entrypoint used; proven behaviorally.
- [x] Bounded operational logging for every outcome case.
- [x] Continues safely after failed/skipped/no-op checkpoints (failure
      isolation at the worker's own boundary; no auto-retry storm).
- [x] Graceful start/stop; no orphan thread; no duplicate start.
- [x] Fully isolated from canonical `ops`/`scheduling`/DarvaX — isolation
      test extended and mutation-proof confirmed.
- [x] No production activation of any kind.
