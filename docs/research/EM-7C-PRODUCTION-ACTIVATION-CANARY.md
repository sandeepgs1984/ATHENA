# EM-7C — Controlled Production Activation & Genuine Scheduled Canary

**Status: EM-7C PRODUCTION CANARY COMPLETE — READY FOR OWNER / CHIEF ARCHITECT
REVIEW.** Owner authorized 2026-09-04, same day as EM-7B/EM-7B.1's closure.
First controlled production activation of the isolated EMR live-shadow path.
The genuine scheduled canary completed (`COMPLETE`, atomic, safe) with an
honest zero-eligible result — not a defect, explained below (§7) — caused by
canonical M5 ingestion not yet having landed today's first bar at the exact
checkpoint instant. This is reported prominently, not glossed over.

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

The collector polled for ~301.5s (one poll cycle past the 300s bound before
its own loop-exit check fired) attempting to observe a post-checkpoint trade
for the full universe, then returned. This is the collector's own frozen,
unmodified behavior (`checkpoint_reference_price.py`, untouched by this
milestone) — no bound was changed or retuned for this canary. Real Kite
`/quote` traffic occurred and completed successfully at the transport level
(no exceptions propagated); whether any instrument's `last_price` ever
qualified as `FIRST_OBSERVED_POST_CHECKPOINT_TRADE` is moot for this run
since zero candidates were ever assembled (§7) to consume it.

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
