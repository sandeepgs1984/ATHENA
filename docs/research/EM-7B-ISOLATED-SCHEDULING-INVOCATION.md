# EM-7B — Isolated EMR Scheduling & Invocation

**Status (superseded by EM-7B.1, 2026-09-04 — see §14): EM-7B READY FOR
OWNER / CHIEF ARCHITECT CLOSURE REVIEW; not yet owner-approved.** §§1–13
below are the original, unmodified EM-7B implementation record — owner
authorized 2026-09-03, same day as EM-7A/EM-7A.1/EM-7A.2's closure,
implementing the isolated EMR operational scheduling/invocation layer
frozen by ADR-014. Owner/Chief Architect source review then provisionally
accepted this implementation but held closure on one narrow
configuration-authority issue: `max_checkpoint_price_delay_seconds` was
an independently operator-tunable field even though the value it carried
was, in fact, a frozen, owner-approved bound elsewhere in the codebase.
**EM-7B.1 (§14) is the owner's resolution** — the frozen bound is now
sourced directly from its real authority, unreachable from any config
edit; `base_universe`/`model_version` remain configurable selectors but
are now validated against already-frozen sources at the config-file
boundary.

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

## 14. EM-7B.1 — frozen runtime-tolerance authority correction (2026-09-04)

**Owner finding.** Source review found `EmrOperationalConfig` carried
`max_checkpoint_price_delay_seconds` (shipped `300.0`) as an independently
operator-tunable JSON field, threaded straight into
`ScanCycleConfig.max_checkpoint_price_delay_seconds`. Audit (not assumed)
of every place this tolerance is used in the repository:

| Value | Where found | Classification |
|---|---|---|
| `max_staleness_minutes = 30.0` | `canary_gate.run_em5_production_canary`'s own accepted default parameter | **A — already frozen/authoritative elsewhere.** `eligibility.py`'s own docstring additionally documents this as "an operational tuning knob, not evidence" — legitimately configurable, matching the accepted default. |
| `max_checkpoint_price_delay_seconds = 300.0` | Exactly equals `checkpoint_reference_price.MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS`, whose own docstring reads: **"Frozen bound: `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS = 300` — deliberately above the diagnostic's observed maximum real latency (188s)... EM-5 must not dynamically retune this."** | **A — already frozen/authoritative elsewhere**, but sitting in an operator-editable JSON field regardless of the number's own correctness was itself the defect — a config edit could silently retune an explicitly must-not-retune bound. The accepted canary itself never threads this tolerance as a live-delay concept at all: it hardcodes `max_checkpoint_price_delay_seconds=0.0` inline (uncomfigurable, not a parameter), appropriate only to its own zero-provider-call historical-replay context, not to a genuinely live worker — confirming this tolerance is not something the canary's own precedent would ever have EM-7B copy as `300.0`; `300.0`'s real authority is the frozen constant, not the canary. |

**Resolution.** `max_checkpoint_price_delay_seconds` removed entirely
from `EmrOperationalConfig`/`config/emr/operational.json` — an operator
supplying it now fails exactly like any other unknown-key typo.
`worker.py` imports `MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS` directly
from `checkpoint_reference_price.py` and passes it into `ScanCycleConfig`
unconditionally; no config path can reach it. Proven by a spy test
capturing the actual `ScanCycleConfig` the worker constructs.
`max_staleness_minutes` is kept as a genuinely operational field (its own
frozen-elsewhere classification is "legitimately tunable," not "must not
retune") — its shipped default is now regression-tested against
`run_em5_production_canary`'s own real signature default via
`inspect.signature`, not a hardcoded duplicate that could silently drift.

**`base_universe`/`model_version` — kept as selectors, now validated.**
Per owner's own framing, these remain configurable but must resolve to an
already-approved source. `load_emr_operational_config` (the boundary an
operator actually reaches by editing JSON — never
`EmrOperationalConfig(...)`'s own constructor, which this module's test
suite uses extensively for fixture isolation) now:

- Rejects any `base_universe` other than `athena_core` — ADR-014 §11's
  own frozen initial-shadow base universe, "the same base universe
  Section 14's canary used" (confirmed by direct quote from the ADR, not
  re-derived).
- Rejects any `model_version` whose `config/emr/frozen_models/<version>/FROZEN_MODEL_MANIFEST.json`
  does not exist, or whose manifest's own recorded `"version"` disagrees
  with the directory name — confirmed the real repo's `v1` manifest
  records `"version": "v1"`, matching the accepted Section 14 canary's
  own artifact set exactly.

No new config framework — two explicit, minimal checks (an exact-match
comparison and a manifest-existence-plus-agreement check), not a generic
validation engine.

**Preserved unchanged (verified, not merely asserted).** Every item in
§13's closure checklist above continues to hold: worker isolation,
`enabled=false` inert startup, `run_once`/`EmrWorker` architecture,
latest-due-only catch-up, `CANDIDATE_CHECKPOINTS_IST`, mature-history
universe policy, canonical regime lookup, `run_scan_cycle_with_lock`, no
FAILED auto-retry, persisted-state restart behavior, no production
mount, no `db/emr.db`, no real provider call, ADR-012 isolation.

**Required mutation/negative proof.** `_validate_resolves_to_frozen_sources`'s
call site temporarily commented out — exactly the 3 tests specifically
proving `base_universe`/`model_version` authority
(`test_unapproved_base_universe_is_rejected`,
`test_never_promoted_model_version_is_rejected`,
`test_manifest_version_mismatch_is_rejected`) failed as expected
("DID NOT RAISE ConfigError"); all 16 other config tests unaffected.
Reverted, `diff` against a pre-mutation backup confirmed byte-identical
restoration.

**Tests.** 12 new/updated tests across `test_em7b_operational_config.py`
(runtime-tolerance authority, base-universe authority, model-version
authority — 19 tests total in that file, up from 8) and one new spy test
in `test_em7b_worker.py` proving the actual `ScanCycleConfig` constructed
at runtime carries the frozen bound (22 tests total in that file, up from
21). `tests/explosive_move/` + `tests/api/v1/test_emr_router.py`: **514
passed** (was 502), 1 pre-existing unrelated skip. Full repository suite:
**3,326 passed** (was 3,314), 1 skipped, 0 failed. Ruff clean. `git diff
--check` clean.

**No ADR-014 change was required** — the ADR already correctly named
`athena_core` (§11) and never asserted any authority over
`max_checkpoint_price_delay_seconds`; this was purely an EM-7B
implementation-level defect, not an ADR-level one.
