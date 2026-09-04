# EM-7C — Controlled Production Activation & Genuine Scheduled Canary

**Status (superseded by EM-7C.1, 2026-09-04 — see §21): EM-7C READY FOR
OWNER / CHIEF ARCHITECT CLOSURE REVIEW; not yet owner-approved.** §§1–20
below are the original, unmodified EM-7C activation/canary record — owner
authorized 2026-09-04, same day as EM-7B/EM-7B.1's closure. The genuine
scheduled canary completed (`COMPLETE`, atomic, safe) with an honest
zero-eligible result — not a defect, explained in §7 — caused by canonical
M5 ingestion not yet having landed today's first bar at the exact checkpoint
instant. Owner/Chief Architect source review then accepted this canary
evidence as genuine but held EM-7C closure for one narrow source-level
isolation defect in `_mount_emr_worker`: config loading sat outside the
protective `try` block, so an EMR-specific configuration failure could have
propagated into and crashed canonical `_cmd_serve`. **EM-7C.1 (§21) is the
owner's resolution** — the entire EMR mount sequence, config loading
included, now lives inside one `try` block; EMR fails closed for itself,
open for canonical ATHENA.

---

## 1. Pre-activation baseline

| Fact | Value |
|---|---|
| Pre-activation cutoff | `2026-09-04T03:11:37Z` / `2026-09-04T08:41:37 IST` |
| Production process (pre-restart) | PID 93626, `python -m athena.cli serve --host 127.0.0.1 --port 8000 --with-cycles --cycle-interval 60.0`, running since 2026-09-03 ~20:15 IST |
| Health | healthy, `cycles_enabled: true`, last cycle idle, no triggers due |
| Canonical schema version | 17 |
| `db/athena.db` | 4755.6 MB, unaffected throughout |
| `db/darvax.db` | 63.9 MB, unaffected throughout |
| `db/emr.db` | absent |
| `config/emr/operational.json` | `enabled: false` |
| ID-7P0 instrumentation | `src/athena/observability/timing.py` present, wired into `scheduling/dry_run.py` |
| Stale artifacts noted | `artifacts/locks/athena-serve.pid` contains a non-running PID (17344) — unused/unreliable, not relied on for shutdown; real PID obtained via `ps` instead |

## 2. Service-mount implementation

`_mount_emr_worker(cfg, *, config_dir, emr_db_path)` (new, `src/athena/cli.py`)
is called from `_cmd_serve` immediately after the existing `CycleWorker` block
and stopped in the same `finally:`. Architecture:

```
_cmd_serve (production service bootstrap)
    |
    +-- CycleWorker (existing, unchanged)   -- canonical runtime
    |
    +-- EmrWorker (new, via _mount_emr_worker) -- isolated EMR worker
```

Never `canonical CycleWorker -> EMR` and never `EMR -> canonical CycleWorker`
— the two share no lock, no repository, no failure path. Reading
`EmrOperationalConfig` is the only EMR work performed when disabled: no
`EmrRepository` construction, no `db/emr.db` creation, no thread, no provider
call (proven by `TestDisabledMountIsInert`, including a required mutation/
negative proof — see §12).

## 3. Restart plan (captured before any change)

- Official launcher: `./athena-serve` — computes `PYTHONPATH` via
  `"$(cd "$(dirname "$0")" && pwd)/src"` (properly quoted, handles the space
  in the repo path correctly) — deliberately used instead of a hand-built
  command, avoiding the exact PYTHONPATH-truncation mistake the earlier
  ID-7P0 restart made.
- Exact flags to preserve: `--host 127.0.0.1 --port 8000 --with-cycles
  --cycle-interval 60.0` (read directly from the running process's own
  command line).
- Graceful stop: `SIGTERM` to the real PID (obtained via `ps`, not the stale
  `.pid` file).

## 4. Actual restart / activation procedure

1. Verified idle (no triggers due) via `/api/v1/health`.
2. Verified EMR lock free (stale content from an earlier-session test run;
   `flock` is process-lifetime-scoped, so absence of the original holding
   process already confirmed it free).
3. Set `config/emr/operational.json`'s `enabled` to `true`; verified it loads
   cleanly (`base_universe=athena_core, model_version=v1,
   max_staleness_minutes=30.0, poll_interval_seconds=30.0`).
4. `kill -TERM 93626` — process exited cleanly within 2 seconds.
5. `./athena-serve --host 127.0.0.1 --port 8000 --with-cycles
   --cycle-interval 60.0` (new PID 52554) — no startup traceback.
6. Health check within 5 seconds: healthy, `cycles_enabled: true`, canonical
   cycle worker resumed with the same 60s interval.
7. `src/athena/observability/timing.py` confirmed still present/wired — ID-7P0
   was not modified, reset, restarted-for, or reinterpreted; it resumes as an
   incidental consequence of the same process restart, unchanged.
8. `db/darvax.db` size/mtime unchanged; no DarvaX file touched.

## 5. First production EMR database

`db/emr.db` created intentionally at restart (4.0 KB initial size). Schema
audit (read-only):

- `emr_schema_version = 2` (current isolated schema).
- Tables: `emr_scan_runs`, `emr_candidates`, `emr_transitions`,
  `emr_schema_version`.
- Indexes present, including both `UNIQUE` per-run-identity indexes
  (`idx_emr_candidates_run_identity`, `idx_emr_transitions_run_identity`).
- Immediately post-restart: all three business tables at 0 rows (no
  checkpoint had occurred yet — restart happened at ~08:59 IST, before the
  first 09:20 checkpoint).

## 6. The genuine scheduled canary

Reached exclusively through `EmrWorker` → `run_once` → latest-due-checkpoint
resolution → `run_scan_cycle_with_lock` → `run_scan_cycle`. No direct scanner
call, no manual insertion, no synthetic result, no backdating.

| Field | Value |
|---|---|
| `run_id` | `em5-scan-fffa4633f5bef3ad4b2924fcb37212efa572e0f3a413dc4b2b7050fadb65276d` |
| `session_date` | `2026-09-04` |
| `checkpoint` | `09:20` |
| `checkpoint instant (IST)` | `2026-09-04T09:20:00+05:30` |
| Actual invocation timestamp | `2026-09-04T09:20:20.807822+05:30` (worker tick landed 20.8s after the checkpoint instant, well inside a 30s poll interval) |
| Universe label | `athena_core-mature-history` |
| Model version | `v1` |
| Session type | `NORMAL` |
| Status | `COMPLETE` |

**Independent `run_id` verification:** re-derived via
`compute_run_id(session_date=date(2026,9,4), checkpoint="09:20",
universe="athena_core-mature-history", model_version="v1")` — matches the
persisted `run_id` exactly (the same deterministic SHA-256 fingerprint
formula, unmodified).

## 7. Universe and the honest zero-eligible result

| Metric | Value |
|---|---|
| Base universe (`athena_core`) count | 518 |
| Mature-history count | 518 (0 excluded — matches the Section 14 canary's own historically validated population) |
| `eligible_count` | 0 |
| `ineligible_count` | 518 |
| Candidate rows persisted | 0 |
| Transition rows persisted | 0 |

**Root cause (verified, not assumed):** `run_scan_cycle`'s per-instrument
loop only enters `base_eligibility`/candidate assembly when
`today_m5_candles` is non-empty for that instrument
(`if not today: continue`) — this is existing, frozen EM-5 behavior,
untouched by EM-7C. A direct read-only query of `db/athena.db` immediately
after the canary, and again ~7 minutes later (09:28 IST), found **zero** M5
candles for any instrument for `2026-09-04` — i.e. the canonical ingestion
pipeline had not yet landed the first (09:15–09:20) five-minute bar for
*any* of the 518 instruments by the time EMR's checkpoint fired.

This is a real, structural characteristic of how canonical ingestion is
scheduled (`config/scheduling.json`): `premarket` is a one-time 08:15
trigger, `refresh`'s cadence is dynamically computed (not a fixed interval),
and the `fast` tier ingests 5m data for only 150 of the 518 symbols every 10
minutes — none of which guarantees full-universe M5 coverage by 09:20:20,
five minutes after market open. EMR's fixed 9-checkpoint schedule was not
designed with explicit awareness of canonical ingestion's own completion
timing, and this canary is the first evidence that the two can genuinely
be out of phase at the very first checkpoint of a session.

**This is not an EM-7A/EM-7B/EM-7C defect.** The scanner did exactly what it
is supposed to do: read only already-persisted canonical candle data via
`SqliteEmrMarketDataAdapter` (zero historical-candle provider calls of its
own, confirmed structurally and by isolation tests), found none available,
and persisted an honest `COMPLETE` result reflecting that — no fabrication,
no fallback, no silent defaulting. It is, however, a genuine operational
finding worth the owner's attention for a future scheduling-alignment
discussion (explicitly out of scope for EM-7C to act on).

## 8. Reference-price / provider observation

| Metric | Value |
|---|---|
| `quote_request_count` | 136 (batched `/quote` polls, real Kite calls) |
| `quote_capture_duration_ms` | 301,460.68 ms (≈301.46s) |
| Frozen bound (`MAX_CHECKPOINT_OBSERVATION_DELAY_SECONDS`) | 300.0s |

**Wording correction (EM-7C.1):** 301.46s is mathematically NOT "within
300 seconds" — the original draft's "within the frozen bound" phrasing was
imprecise and is corrected here. The collector's own *wall-clock loop
duration* (301.46s) may legitimately exceed its own *admissible observation
delay bound* (300.0s), because the polling loop checks the deadline only at
polling boundaries — it does not pre-empt mid-poll. Concretely: the loop's
own bound check fires after crossing 300.0s, so the measured wall-clock
duration includes one final poll-cycle's worth of overhead past the
deadline. This is the collector's own frozen, unmodified behavior
(`checkpoint_reference_price.py`, untouched by this milestone) — no bound
was changed or retuned for this canary, and none of the traffic that
occurred represents an *accepted observation* exceeding the bound: **zero
candidates were ever assembled this run (§7)**, so there is no accepted
`FIRST_OBSERVED_POST_CHECKPOINT_TRADE` observation to report a delay for at
all — the question "did any accepted observation exceed 300 seconds" has
no data points to answer it either way this run. Real Kite `/quote` traffic
occurred and completed successfully at the transport level (no exceptions
propagated) across all 136 requests.

## 9. Data freshness

`max_staleness_minutes = 30.0` — unchanged, not retuned. No instrument
reached the staleness gate at all in this run (the `today` empty-check
short-circuits before that gate is evaluated).

## 10. Output summary

Instrument count 518, candidate count 0, TOUCH-10 count 0, transition count
0, data-failure count 518 (all 518 instruments hit the `today_m5_candles`
empty short-circuit before eligibility was even evaluated — not a maturity
failure, not a staleness failure; see §7's root cause), scanner
`total_duration_ms = 310,920.15` (≈311s, dominated by the 301.5s
quote-capture phase), terminal status `COMPLETE`. No per-symbol dump
performed (not needed to diagnose — root cause already established at the
aggregate level in §7).

## 11. Atomicity verification

- Exactly one `emr_scan_runs` row, `status=COMPLETE`.
- `emr_candidates`/`emr_transitions`: 0 rows each — internally consistent
  with 0 eligible/assembled instruments (0 is the *correct* full result
  here, not a partial-result anomaly).
- No duplicate rows for this `run_id` (uniqueness trivially holds with zero
  rows).
- `commit_scan_result`'s atomic transaction handled the empty-candidates/
  empty-transitions case correctly (its own `if candidates:`/`if
  transitions:` guards skip the `executemany` calls when both lists are
  empty, then the terminal `COMPLETE` update still applies) — no code path
  exercised here that wasn't already covered by
  `test_em7a1_transactional_lifecycle.py`.

## 12. Regime wiring

Structurally confirmed (unchanged from EM-7B): `worker.py`'s `run_once`
always constructs `build_canonical_regime_lookup(...)` before invoking the
scanner, proven by `test_worker_wires_the_real_canonical_regime_lookup`'s
spy test. **This specific canary did not exercise that code path** — since
zero instruments ever entered the per-symbol evidence-assembly loop (§7),
`regime_lookup(session_date)` (called inside that loop) was never invoked
during this run. Reported precisely rather than claimed as a live behavioral
proof it is not: wiring correctness is structurally guaranteed independent
of this run; this run simply had no opportunity to exercise it.

## 13. EM-6 presentation verification

Direct read-only call to `presentation.latest_scan_snapshot('db/emr.db')`
returned the persisted `COMPLETE` scan correctly:

```
EmrScanSnapshotInfo(run_id='em5-scan-fffa...', session_date='2026-09-04',
checkpoint='09:20', frozen_model_version='v1',
started_ts='2026-09-04T09:20:20.807822+05:30',
finished_ts='2026-09-04T09:20:20.807822+05:30',
eligible_count=0, ineligible_count=518)
```

The presentation layer represents the COMPLETE scan truthfully even with
zero candidates — exactly the "legitimately zero candidates" case the
authorization anticipated. No UI change, no mutation control, no trade
language involved.

## 14. Restart / idempotency proof level

**Level used: fixture/integration proof only — no second production
restart performed.** `test_em7b_worker.py::TestRestartBehavior` already
proves the exact mechanism (entirely fresh `EmrRepository`/`CalendarEngine`
objects pointed at the same on-disk file recover correctly from persisted
state with zero re-invocation of the provider) with injected, deterministic
time. Forcing a second real production restart solely to re-prove a
mechanism already covered by 6+ passing fixture tests would add real risk
(a second live-service interruption) for no additional confidence. Not
performed, per the authorization's own explicit preference for this case.

## 15. Canonical isolation — database

- Canonical `schema_version`: 17, unchanged (checked before and after).
- No `emr_*` table in `db/athena.db` (checked via `.tables`).
- No EMR write API/path exists in canonical code (unchanged from EM-7A/B).
- `db/athena.db` size unchanged (4755.6 MB) apart from whatever canonical
  ingestion writes on its own, independent of EMR.

## 16. Canonical isolation — runtime

- Canonical cycle worker: resumed after restart, `cycles_enabled: true`,
  60s interval, idle/no-triggers-due throughout the EMR canary window —
  unaffected.
- Dashboard/API: healthy before, during, and after.
- Canonical locks: `cycle-runner.lock` content shows the correct new PID
  (52554) after restart — unaffected by the EMR lock.
- DarvaX: `db/darvax.db` untouched; no DarvaX source/config/import changed.
- ID-7P0: `timing.py` present, unmodified, resumed with the same restart
  (incidental, not a deliberate action on it).
- No EMR exception propagated into canonical worker lifecycle (health
  stayed green throughout).

## 17. Performance observations (observation only, no threshold established)

- EMR process (the whole `athena serve` process, both canonical and EMR
  workers): 0.1% CPU, 1.1% memory at spot-check — negligible.
- Dashboard health/latency: healthy at every spot-check, no degradation
  observed.
- No obvious material operational regression observed. This is a single
  canary, not a statistical performance study — EM-7D owns that.

## 18. Failure / rollback actions

None required. No safety trigger fired. `enabled=true` left in place per
§29 of the authorization (genuine canary succeeded, all isolation/health
checks passed).

## 19. Post-canary production state

- `config/emr/operational.json`: `enabled: true` (left as-is).
- `db/emr.db`: 1 `COMPLETE` scan run persisted, 0 candidates, 0 transitions.
- Production service: healthy, both workers running independently.
- Natural evidence accumulation active for subsequent checkpoints
  (09:30, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00, 14:00 IST) — observed
  passively, not triggered, not backfilled, not retried.

## 20. Explicitly not claimed

No precision, lift, calibration quality, profitability, predictive value,
MFE/MAE improvement, false-positive rate, miss rate, or regime-effectiveness
claim is made from this one canary. This document asks and answers only:
does the isolated frozen pipeline operate correctly and safely in
production? **Yes** — atomically, safely, with zero canonical regression,
and with one genuine, honestly-reported zero-eligible outcome whose cause
is fully understood and unrelated to any EM-7A/B/C code defect.

## 21. EM-7C.1 — production mount fail-closed isolation (2026-09-04)

**Source-confirmed defect.** `_mount_emr_worker`'s original shape (§2 above,
preserved as historical record, not rewritten) called
`load_emr_operational_config(config_dir)` and evaluated the `enabled` flag
*before* the protective `try` block that wrapped everything else. Any
exception from that config load — malformed JSON, an unapproved
`base_universe`, a missing or version-mismatched frozen model manifest, an
unreadable file, or any other deterministic `ConfigError` — would propagate
straight out of `_mount_emr_worker` into `_cmd_serve`, which has no
surrounding `try`/`except` of its own around that call. An EMR-specific
configuration problem could therefore have crashed canonical `_cmd_serve`
startup entirely — violating ADR-014's failure-isolation contract ("EMR
unavailable" must never mean "ATHENA unavailable").

**Resolution.** The entire EMR mount sequence — config loading and
validation, the `enabled` check, opening the canonical read-repository,
`EmrRepository` construction/initialization, `CalendarEngine`/`tzinfo`
construction, and `EmrWorker` construction/start — now lives inside one
`try` block. A failure at any of those steps is caught, printed as one
bounded warning line (`WARNING: EMR unavailable for this process --
continuing without it: <exc>`), and never allowed to reach `_cmd_serve`.
Invalid configuration is never silently reinterpreted as a valid disabled
file — it surfaces as the same warning, with EMR simply not mounting.

**Resource cleanup preserved.** If the canonical read-repository was
already opened before a later step fails, it is closed in the `except`
branch (unchanged from EM-7C). A `db/emr.db` file partially created by a
failed schema initialization is deliberately left in place for diagnosis —
never auto-deleted.

**Required tests (`tests/unit/test_em7c_service_mount.py`, new
`TestFailClosedForEmrFailOpenForCanonical` class, 7 tests):** malformed
JSON, an unapproved `base_universe`, a missing frozen model manifest, a
manifest/version mismatch, an `EmrRepository.initialize()` failure
(proving both canonical survival and that the canonical repo is closed,
not leaked), an `EmrWorker` construction/start failure (proving a
later-stage failure is caught too, and that a partially-initialized
`db/emr.db` is preserved rather than deleted), and one service-level proof
that `_mount_emr_worker` always returns a plain `(worker, repo)` tuple —
never raises — for every failure mode above, which is the exact contract
`_cmd_serve`'s subsequent lines depend on to keep running.

**Required mutation/negative proof.** The config load was temporarily
moved back outside the `try` block (reproducing the original defect
exactly). Result: exactly the 5 tests that specifically prove
config-loading isolation failed as expected (raw `ConfigError`/
`json.JSONDecodeError` propagated uncaught); the other 8 tests (later-stage
failure isolation, which doesn't depend on where the config load sits)
were unaffected. Reverted; `diff` against a pre-mutation backup confirmed
byte-identical restoration.

**Incidental finding, fixed alongside.** Running the full EMR test suite
after EM-7C's real production activation surfaced a latent test-isolation
gap, unrelated to the mount-boundary defect above:
`tests/explosive_move/test_em7b_worker.py`'s `_run` helper (and two direct
`run_once` calls in `TestRestartBehavior`) defaulted `lock=None`, which
`run_scan_cycle_with_lock` resolves to
`EmrScanLock(default_emr_scan_lock_path())` — the *real* production lock
file. Once EM-7C's real `EmrWorker` began genuinely acquiring that same
file for its own natural ticks, tests using the default intermittently
observed `LOCK_BUSY` instead of `INVOKED` whenever a real tick happened to
be in flight at the same moment — a real, demonstrated collision, not a
flake. Fixed by giving the test module its own isolated
`_TEST_LOCK_PATH` (a dedicated temp directory, never the shared default)
and threading it through every call site that previously relied on the
default. Confirmed by re-running the full suite twice consecutively with
zero failures.

**Existing production config/state preserved.** `enabled=true,
base_universe=athena_core, model_version=v1, max_staleness_minutes=30.0,
poll_interval_seconds=30.0` — unchanged. `db/emr.db` (1 `COMPLETE` scan
run from the original 09:20 canary) — unchanged, not reset, not deleted.
No new canary was triggered for this correction, per explicit instruction
— the existing 09:20 evidence remains the accepted canary.

**Deployment.** The fixed `cli.py` changes the *code path* future
`athena serve` invocations will run, but does not change any *currently
loaded* runtime behavior of the already-running production process (the
defect only matters at `_cmd_serve` startup time, and the process is not
currently failing). No production restart was performed solely to deploy
this correction — the live service continues running the version it
started with; the corrected mount boundary takes effect at the next
normal deployment/restart, whenever the owner chooses one. `db/emr.db` and
the live worker were not touched.

**Preserved unchanged.** The 09:20 canary's zero-eligible finding (§7),
the frozen 300-second observation-delay bound (§8, wording corrected
above — not retuned), `run_once`/`EmrWorker` scheduling semantics,
latest-due-only catch-up, FAILED no-auto-retry, `run_scan_cycle_with_lock`,
`EmrScanLock`, `RUNNING → COMPLETE | FAILED`, `commit_scan_result`'s
atomicity, mandatory `regime_lookup`, and the mature-history universe
policy — none touched.

**Validation.** Focused: 13/13 `test_em7c_service_mount.py` tests passing.
`tests/explosive_move/` + `tests/api/v1/test_emr_router.py` +
`test_em7c_service_mount.py`: **527 passed**, 1 pre-existing unrelated
skip. Full repository suite: **3,339 passed** (was 3,332), 1 skipped, 0
failed. Ruff clean. `git diff --check` clean.
