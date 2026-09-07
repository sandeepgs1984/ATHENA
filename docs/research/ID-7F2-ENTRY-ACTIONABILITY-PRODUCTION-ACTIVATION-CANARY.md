# ID-7F2 — Entry Actionability Production Activation + First Canonical Canary

**Status (2026-09-05): PRE-ACTIVATION PREPARATION COMPLETE. PRODUCTION
ACTIVATION DEFERRED TO THE NEXT NSE TRADING-DAY, OWNER-OPERATED RESTART.
ID-7F2 REMAINS OPEN.**

Owner/Chief Architect closed ID-7F1.1 and ID-7F1 overall on 2026-09-05
(historical Mode-A replay validation frozen — 11,986/11,986 real
observations reconstructed, `replay_acceptance: true`) and authorized
ID-7F2: safely migrate the canonical database from schema v17 to the
already-implemented/tested schema v18, activate the already-closed ID-7E
canonical `EntryActionability` stage through the normal production
runtime path, and observe the first genuine canonical-cycle canary.

This document records everything performed today (all read-only or
additive/reversible — no live-process action, no schema change, no
restart), the exact reasoning for deferring activation, and the precise
procedure for the owner to execute the restart themselves at the next
trading-day window. **No live-process action was taken today, per
explicit owner instruction** ("Proceed with NO live-process action
today").

---

## 1. Why activation is deferred, not merely delayed by caution

Two independent, source-verified facts converged:

1. **The auto-mode safety classifier blocked the live-process kill/
   restart action** when attempted — correctly, since ending and
   relaunching a real running service on the owner's machine is exactly
   the class of hard-to-reverse action that should go through the owner,
   not be executed autonomously. No permission exception was requested
   or should be requested for this.
2. **Today (2026-09-05) is a genuine NSE non-trading day.** Confirmed
   programmatically via the real `CalendarEngine`:
   `CalendarEngine.from_config_dir(...).context_for(date(2026, 9, 5))`
   returns `session_type=SessionType.WEEKEND`. Even if activation had
   proceeded today, **no scheduled cycle would fire** (`config/scheduling.json`'s
   `premarket`/`refresh`/`closing`/`fast` cadences all gate on session
   scannability), so no natural canary could have been observed today
   regardless. Deferring to the next trading day costs nothing and
   avoids restarting the live service for no immediate benefit.

The owner's own decision confirms this reasoning and explicitly defers
the restart to an owner-operated action at the next trading-day window.

---

## 2. Pre-activation safety check (§2 of the authorization) — performed, read-only

All queries below were executed via a read-only SQLite connection
(`mode=ro` + `PRAGMA query_only=ON`) — a second, independent connection,
never the live service's own writable connection.

| Fact | Value |
|---|---|
| Canonical DB path | `db/athena.db` |
| DB file size | 4,927.0 MB (`db/athena.db`), plus `-wal` 603.5 KB / `-shm` 32 KB |
| `schema_version` | **17** |
| `journal_mode` | `wal` |
| Live `athena-serve` process | PID 2453, `python -m athena.cli serve --host 127.0.0.1 --port 8000 --with-cycles`, running for ~2h8m at time of check |
| Current git revision | `70ed49d` — `fix(intraday): harden Entry Actionability replay harness accounting (ID-7F1.1)` (the last committed ID-track work) |
| Most recent `runs` row | `run-closing-20260904T154545`, trigger `CLOSING`, status `COMPLETED` — no `RUNNING` row found in the last 5 |

**Confirmed:** the canonical DB is still exactly `schema_version = 17`,
as ID-7F1/ID-7F1.1 both found — no drift since those milestones. No
cycle is currently in flight.

---

## 3. V17 → V18 migration source audit (§3) — confirmed clean

`git show --stat 49349a8` (the ID-7A commit) shows `schema.py` gained
exactly 82 insertions / 1 deletion — the `entry_actionabilities` table
DDL (24 columns including `persisted_at`, 7-column composite
`PRIMARY KEY`, FK on `decision_id`) plus its two supporting indexes
(`idx_entry_actionabilities_decision`,
`idx_entry_actionabilities_instrument_session`) and the
`SCHEMA_VERSION` bump 17→18. `git diff <rev>~1 <rev> -- schema.py` for
both later ID-7A.1 and ID-7A.2 commits returns **empty** — neither
touched `schema.py` at all. **No unrelated migration is bundled**;
v18 introduces only the already owner-approved ID-7A persistence
structures.

The migration mechanism itself is `SqliteRepository.initialize()`
(`repository.py:295-318`) — idempotent (`CREATE TABLE IF NOT EXISTS`
for every table in `ddl_statements()`, guarded `ALTER TABLE ADD COLUMN`
migrations only), called unconditionally by `_open_repo()`
(`cli.py:63-69`) on every `athena-serve` startup ("Ensure DB schema
exists before accepting traffic" — `cli.py:785`). **No ad-hoc `CREATE
TABLE`/manual SQL migration is needed or was run** — the next
`athena-serve` startup will perform the entire migration automatically,
exactly as ID-6E.2's own schema-v17 activation for `entry_qualifications`
was performed via this identical mechanism (`docs/ops/ID-6E2-ENTRY-QUALIFICATION-PRODUCTION-SCHEMA-ACTIVATION.md`).

---

## 4. Pre-migration backup (§4) — created and verified

Since the production DB is a live WAL-mode file, the backup used the
same safe pattern ID-6E2 established: a read-only source connection
(`mode=ro` + `PRAGMA query_only=ON`) feeding SQLite's own online backup
API (`sqlite3.Connection.backup()`), written to a temp file and
atomically renamed — the live service's own writable connection was
never touched.

- **Backup path:** `db/backups/athena-pre-id7f2-schema-v18-activation-20260905T064233Z.db`
- **Size:** 5,166,485,504 bytes
- **Backup duration:** 20.77s
- **`integrity_check`:** `ok`
- **`foreign_key_check`:** 0 violations
- **`schema_version` in backup:** 17 (matches pre-migration source exactly)
- **Metadata sidecar:** `<backup>.meta.json` — records schema version,
  full per-table record counts, creation timestamp, source path,
  backup duration, integrity/FK results, size.
- **Record counts captured** (for post-migration comparison):
  `instruments` 2,204; `candles` 2,994,346; `quotes` 317,338;
  `market_snapshots` 2,126; `corporate_actions` 2,009;
  `quarantine_records` 355; `runs` 1,946; `decisions` 233,418;
  `decision_traces` 233,418; `decision_journal` 1; `owner_positions` 3;
  `owner_candidates` 528; `saved_symbols` 30;
  `entry_qualifications` 11,986; `ops_meta` 1.

**Not deleted, not restored, retained exactly as-is** per §30 of the
authorization.

---

## 5. Pre-activation focused tests (§11, partial — full suite already
proven clean by ID-7F1.1)

`tests/data_layer/` + `tests/ops/test_owner_validation.py`: **644
passed, 0 failures.** (The full repository suite was already confirmed
clean — 3,644 passed, 1 pre-existing unrelated skip — at ID-7F1.1's own
closure minutes earlier; no code has changed since.)

---

## 6. Weekend / no-natural-canary fact (§ owner-flagged)

`CalendarEngine.from_config_dir(Path("config"), cfg.market).context_for(date(2026, 9, 5))`
→ `CalendarContext(session_type=SessionType.WEEKEND, open_time=None,
close_time=None, ...)`. No PREMARKET/REFRESH/CLOSING/FAST cadence in
`config/scheduling.json` can scan a non-trading day. Confirmed
independently of the live-process-restart block — restarting today
would not have produced a natural canary regardless.

---

## 7. Exact procedure for the owner-operated activation (next trading day)

The following is presented **for the owner to execute themselves** —
this session will not run any of steps A/B, and will only perform C–G
as read-only verification after the owner confirms the restart is done.

### A. Stop the existing `athena-serve --with-cycles` process cleanly

```bash
ps aux | grep "athena.cli serve" | grep -v grep
```

Note the PID from the output, then:

```bash
kill -TERM <PID>
```

Wait for a clean exit (do **not** `kill -9` unless it fails to exit
after a reasonable wait — a graceful SIGTERM lets uvicorn shut down and
lets the in-process `CycleWorker` release `artifacts/locks/cycle-runner.lock`
cleanly):

```bash
while ps -p <PID> > /dev/null 2>&1; do sleep 1; done; echo "stopped"
```

### B. Start/restart through the repository's established operational path, same flags

The current process was running with `--host 127.0.0.1 --port 8000
--with-cycles` (default `--cycle-interval 60.0`, since none was
specified). Restart with the identical flags, using the repository's own
documented one-command host script (`docs/ops/HOST_SCHEDULE.md`):

```bash
cd "/Users/cbz-sandeep/DEVELOPMENT DRIVE/GITHUB Projects/ATHENA"
nohup ./athena-serve --host 127.0.0.1 --port 8000 --with-cycles >> artifacts/logs/athena-serve.log 2>&1 &
```

(If you normally launch it via the ATHENA.app Dock icon instead, that is
equally acceptable — it execs this same `./athena-serve --with-cycles`
command internally; use whichever you normally use.)

### C. Verify startup succeeded

```bash
sleep 3
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
ps aux | grep "athena.cli serve" | grep -v grep
tail -n 40 artifacts/logs/athena-serve.log
```

Expect `"status": "UP"` from `/health`, a new PID in `ps aux`, and no
traceback in the log tail.

### D. Verify the canonical DB migrated exactly from schema 17 to schema 18

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('file:db/athena.db?mode=ro', uri=True)
conn.execute('PRAGMA query_only=ON')
print('schema_version:', conn.execute('SELECT version FROM schema_version').fetchone())
conn.close()
"
```

Expect exactly `(18,)` — never any other value.

### E. Verify `entry_actionabilities` exists with the approved schema/indexes

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('file:db/athena.db?mode=ro', uri=True)
conn.execute('PRAGMA query_only=ON')
print(conn.execute(\"SELECT sql FROM sqlite_master WHERE type='table' AND name='entry_actionabilities'\").fetchone()[0])
print(conn.execute(\"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='entry_actionabilities' ORDER BY name\").fetchall())
conn.close()
"
```

Compare the printed `CREATE TABLE` statement against
`src/athena/data/store/schema.py`'s `entry_actionabilities` DDL (24
columns, composite `PRIMARY KEY (instrument_id, session_date,
entry_qualification_as_of, decision_id,
entry_qualification_methodology_version, entry_actionability_as_of,
entry_actionability_methodology_version)`) and confirm exactly the two
named indexes (`idx_entry_actionabilities_decision`,
`idx_entry_actionabilities_instrument_session`) exist — no unexpected
extra index/trigger/view.

Also confirm no pre-existing table lost rows (compare against §4's
captured counts):

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('file:db/athena.db?mode=ro', uri=True)
conn.execute('PRAGMA query_only=ON')
for t in ('instruments','candles','quotes','market_snapshots','corporate_actions',
          'quarantine_records','runs','decisions','decision_traces','decision_journal',
          'owner_positions','owner_candidates','saved_symbols','entry_qualifications','ops_meta'):
    print(t, conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
conn.close()
"
```

Every count should be **greater than or equal to** the §4 backup
snapshot (equal, or higher only if a genuine cycle ran between the
backup and the restart — never lower).

### F. Verify no historical `EntryActionability` backfill occurred

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('file:db/athena.db?mode=ro', uri=True)
conn.execute('PRAGMA query_only=ON')
print('entry_actionabilities count:', conn.execute('SELECT COUNT(*) FROM entry_actionabilities').fetchone())
print('min/max persisted_at:', conn.execute('SELECT MIN(persisted_at), MAX(persisted_at) FROM entry_actionabilities').fetchone())
print('min/max entry_actionability_as_of:', conn.execute('SELECT MIN(entry_actionability_as_of), MAX(entry_actionability_as_of) FROM entry_actionabilities').fetchone())
conn.close()
"
```

Immediately after migration and before any cycle has run, expect `count
= 0`. If the check is run after a cycle has already fired naturally,
every `persisted_at`/`entry_actionability_as_of` value must fall strictly
**after** the restart timestamp — never a pre-activation historical
date. Any pre-activation timestamp would indicate an unauthorized
backfill and must be reported immediately, not silently accepted.

### G. Verify the service is healthy and ready for the first natural cycle

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
tail -n 100 artifacts/logs/athena-serve.log | grep -i "cycle\|error\|traceback" || echo "no cycle/error lines yet (expected immediately after restart)"
```

Confirm `/health` reports `"status": "UP"`, no traceback appears in the
log, and (if `--with-cycles` scheduling has already logged a "cycle
worker started" line) that the worker initialized without error. No
manual cycle trigger is required or should be used — the next
`PREMARKET`/`REFRESH`/`FAST` tick will fire on its own normal schedule.

---

## 8. What happens after the owner confirms the restart

This session will then, **read-only only**:

1. Re-run D–G above to confirm the migration and service health.
2. Wait for the first naturally-occurring canonical cycle that produces
   at least one in-scope (WATCH/TRADE) persisted `EntryQualification`
   row — that entire cycle becomes the frozen ID-7F2 canary, per the
   authorization's own §9 definition (not cherry-picked, not
   manufactured, never a manual Validate-All).
3. Audit that canary against every check in §10–§28 of the
   authorization (upstream counts, exact binding, WATCH/TRADE
   semantics, append-only/duplicate audit, M5/VWAP/OR15 provenance,
   stage failure audit, latency, provider-call/currentness absence,
   post-canary DB safety, backfill absence) and apply the frozen
   acceptance contract (§29).
4. If no natural in-scope observation has occurred by the time this
   session next checks, report exactly
   `ID-7F2 ACTIVATION COMPLETE — NATURAL CANARY NOT YET OBSERVED` and
   leave ID-7F2 open — never manufacture a sample.

---

## 9. Today's classification

**ID-7F2 PRE-ACTIVATION PREPARATION COMPLETE.**
**PRODUCTION ACTIVATION DEFERRED TO THE NEXT NSE TRADING-DAY,
OWNER-OPERATED RESTART.**
**ID-7F2 REMAINS OPEN.**

No live-process action was taken. No schema change was made. No code
change was made. The verified pre-migration backup
(`db/backups/athena-pre-id7f2-schema-v18-activation-20260905T064233Z.db`)
is preserved, untouched, and not restored.

---

## 10. Addendum (2026-09-07): activation-provenance forensics + first canonical canary (read-only)

On resuming ID-7F2 on the next trading day (2026-09-07), the fresh
pre-flight required by §9 above (schema must still read 17 before any
owner-operated restart) instead found `schema_version = 18` and a
real, non-empty `entry_actionabilities` table — the activation boundary
had already been crossed by *something*, without any owner-operated
restart procedure (§7 above) having been reported as executed. Per
explicit owner instruction, no restart/migration was attempted; a
read-only forensic investigation was authorized and performed instead.
All work below is 100% read-only (`mode=ro` + `PRAGMA query_only=ON`
for every DB query; log/source files only read, never written).

### 10.1 Activation-provenance classification: `EXECV_RESTART_CONFIRMED`

`artifacts/logs/athena-serve.log` (the live, continuously-appended
service log, 100,502 lines) contains direct, repeated, unambiguous
evidence of the in-place `os.execv`-based restart mechanism ID-7P0.2
first characterized on 2026-09-04: a `POST /api/v1/ops/restart` access
line immediately followed by `Started server process [PID]` carrying
**the exact same PID**, with no intervening `Shutting down` /
`Application shutdown complete` / `Finished server process [PID]`
lines (those lines, when present, mark a genuine clean stop+relaunch
with a *new* PID instead — both patterns are directly distinguishable
in the log and both are observed).

The current serving PID, **2453**, first appears via a genuine clean
restart (`Finished server process [17344]` → `Started server process
[2453]`, log line 92148) and has since undergone **11 further
in-place `execv` restarts** on the identical PID (log lines 94875,
96112, 96587, 96897, 97036, 97248, 97489, 97633, 99195, 99970,
100406), each immediately preceded by its own `POST
/api/v1/ops/restart` line. This is direct log evidence, not an
inference from PID/`ps`-start-time continuity alone (`ps`'s `STARTED`
timestamp is consistent with `execv` semantics — the kernel's
process-start bookkeeping is untouched by `execve()` — but the log
lines above are the actual proof, satisfying the authorization's
"do not infer from PID continuity alone" requirement).

### 10.2 Earliest proven v18/EA activation evidence — bounds, not an exact instant

An exact activation instant cannot be recovered: `athena-serve.log`
carries no per-line timestamps (uvicorn's default access-log format),
so individual `execv` events in the log cannot be dated directly.
Two hard, evidence-backed bounds were established instead:

- **`activation_lower_bound = 2026-09-05T11:00:15+05:30`** — the git
  commit timestamp of `684ec4b` ("wire EntryActionability into the
  canonical workflow (ID-7E)"), the commit that first introduces
  `entry_actionability_stage` into `owner_validation.py`. Before this
  instant existed on disk, no restart of any kind could have activated
  the stage (schema v18 itself landed slightly earlier, in `49349a8`,
  2026-09-05T00:19:09+05:30, but the stage that *invokes* it did not
  exist until `684ec4b`).
- **`activation_upper_bound = 2026-09-06T10:23:07.666132+00:00`**
  (`= 2026-09-06T15:53:07+05:30`) — the `persisted_at`/`evaluated_at`
  value on the two earliest real `entry_actionabilities` rows (see
  §10.3), which is direct proof the full v18 schema + `EntryActionabilityEngine`
  + `entry_actionability_stage` chain was executing for real at that
  exact wall-clock instant.

Activation therefore occurred somewhere in a bounded ~28.9-hour
window; the exact `execv` instant within that window is not
recoverable from available evidence. No further precision is claimed.

### 10.3 The 2026-09-04 `as_of` / 2026-09-06 `persisted_at` gap: fully explained, not backfill

Two of the 228 persisted rows (`NSE:GOLDBEES`, `NSE:SILVERCASE`) carry
`entry_actionability_as_of = 2026-09-04T15:30:00+05:30` (inherited
unconditionally from their bound `EntryQualification.as_of`, exactly
per ID-7C's frozen Option-1 rule) but `persisted_at =
2026-09-06T10:23:0[7/11]+00:00`. Both rows' `run_id`
(`run-refresh-20260904T153000-43787100` and
`run-refresh-20260904T153000-99db7f0c`) exist in `runs`, each with
`config_snapshot_id = 'cfg-symbol-validate'` — traced via source
(`grep`) to exactly one call site, `src/athena/ops/symbol_validate.py:243`,
a **pre-existing** (651 historical runs, oldest dated 2026-07-24 — long
before any ID-7 milestone), on-demand, dashboard/CLI-triggered
single-symbol "Validate" feature (module docstring: *"On-demand symbol
validation (ingest + eligibility + decisions) for dashboard/CLI"*).
`symbol_validate.py` constructs and runs the exact same
`OwnerValidationPipeline` class ID-7E extended — so once ID-7E's stage
existed in the running code, *any* invocation of this pre-existing
feature (not only the scheduled cycle worker) naturally also executes
and persists `EntryActionability`, exactly as designed for the shared
DAG. Because 2026-09-04→2026-09-06 spans the observed `SessionType.WEEKEND`
(2026-09-05/06), the most recent real EQ available to validate against
when this on-demand action ran (2026-09-06, real wall-clock) was
genuinely the last trading day's EOD checkpoint (2026-09-04 15:30 IST)
— there is no newer real data to have used instead. The underlying
`Decision` row (`decision-NSE:GOLDBEES-2026-09-04T15:30:00+05:30`) is a
real, coherent WATCH decision with genuine gate results (score
56.53/100, confidence 91.7, six passing gates) — not a synthetic or
manufactured record.

**Classification: `OTHER_EXPLAINED_PRODUCTION_PATH`.** Grounded
entirely in real `runs`/`decisions`/`entry_qualifications` rows and
one exact source-code call site — not inferred from timestamps alone,
and not treated as proven "no backfill" until that provenance chain
was actually walked, per the authorization's own instruction.

**Historical-backfill verdict: `HISTORICAL_BACKFILL_ABSENT`.**
Supporting evidence: (1) only 2 of 228 rows show this pattern, both
fully traced to the single pre-existing, non-batch, single-symbol
on-demand feature above; (2) the remaining 226/228 rows all trace to
exactly **one** genuine scheduled `PREMARKET` cycle
(`run-premarket-20260907T081534`, `config_snapshot_id='cfg-host-ops'`,
today, 2026-09-07); (3) no code path exists (and none was found) that
iterates the 11,986/12,214-row historical `EntryQualification`
population and calls `save_entry_actionability` — the only production
writer of that table is `entry_actionability_stage` itself, reached
only via `OwnerValidationPipeline` (scheduled cycle worker or the
single-symbol Validate action above); the ID-7F1 replay harness is
confirmed (by design and by a fresh source read) to never call
`save_entry_actionability` at all. A batch backfill across the real
11,986-row EQ history would show thousands of rows, not 228.

### 10.4 Schema-v18 structure verification

`entry_actionabilities` DDL read directly from `sqlite_master`: 23
columns exactly matching ID-7A's approved design (all 7 identity
columns `NOT NULL`, `decision_id REFERENCES decisions(decision_id)`,
value-object columns nullable JSON), composite 7-column `PRIMARY KEY`
(`instrument_id, session_date, entry_qualification_as_of, decision_id,
entry_qualification_methodology_version, entry_actionability_as_of,
entry_actionability_methodology_version`), plus the two approved
supporting indexes (`idx_entry_actionabilities_decision`,
`idx_entry_actionabilities_instrument_session`) and SQLite's own
autoindex for the PK. No unrelated schema drift found.

### 10.5 Pre-existing data preservation

`PRAGMA integrity_check` → `ok`. `PRAGMA foreign_key_check` → 0
violations. `schema_version` → `18`. Table-count deltas vs. the frozen
pre-migration backup (`...20260905T064233Z.db.meta.json`, schema 17):

| Table | Backup (2026-09-05) | Now (2026-09-07) | Δ | Verdict |
|---|---|---|---|---|
| `decisions` | 233,418 | 233,805 | +387 | expected natural growth |
| `entry_qualifications` | 11,986 | 12,214 | +228 | expected — exactly equals new EA row count |
| `runs` | 1,946 | 1,949 | +3 | expected — exactly equals 2 symbol-validate + 1 premarket |
| `candles` | 2,994,346 | 2,994,505 | +159 | expected natural ingestion growth |
| `entry_actionabilities` | 0 (table absent) | 228 | +228 | expected — the new table |

Every delta is mutually coherent (228 new EQ ⇒ 228 new EA; 3 new runs
⇒ 2 validate + 1 premarket). Zero unexpected loss or corruption found.
The pre-migration backup file itself remains present, unrestored, and
byte-identical in size (4927.1MB) with its `.meta.json` sidecar intact.

### 10.6 Full production `EntryActionability` inventory (all 228 rows — no sampling)

- **Total rows: 228.**
- **Session-date distribution:** `2026-09-04` → 2, `2026-09-07` → 226.
- **`run_id` distribution:** `run-refresh-20260904T153000-43787100` → 1,
  `run-refresh-20260904T153000-99db7f0c` → 1,
  `run-premarket-20260907T081534` → 226.
- **`cycle_id` distribution:** `2026-09-04-refresh` → 2,
  `2026-09-07-premarket` → 226.
- **Decision-type distribution:** `WATCH` → 228, `TRADE` → 0.
- **EA-state distribution:** `NOT_ACTIONABLE` → 228, `UNKNOWN` → 0,
  `ACTIONABLE` → 0.
- **Reason-code distribution:** `["UPSTREAM_DECISION_NOT_TRADE",
  "UPSTREAM_EQ_NOT_QUALIFIED"]` → 228 (both codes together on every
  row — exact, deterministic match to the frozen dual-reason
  convention for a WATCH decision bound to a non-QUALIFIED EQ).
- **EQ-state distribution:** `EXPIRED` → 228.
- **Direction distribution:** `NONE` → 228.
- **`entry_actionability_methodology_version`:** `entry-actionability-v0`
  → 228 (100%, no override path exists per ID-7C.1).
- **`evidence_finality`:** `UNKNOWN_PROVENANCE` → 228.
- Earliest `entry_actionability_as_of`: `2026-09-04T15:30:00+05:30`.
  Latest: `2026-09-07T08:15:34.096216+05:30`.
- Earliest `persisted_at`: `2026-09-06T10:23:07.666132+00:00`. Latest:
  `2026-09-07T02:57:0[2].*+00:00` (last row of the premarket batch).

**Out-of-scope row count: 0** (every row's `decision_type` is WATCH or
TRADE, verified by direct query). **Exact binding-defect count: 0**
(every row's `decision_id` resolves to a real `decisions` row; every
row's exact 5-part EQ identity — instrument, session_date, `as_of`,
`decision_id`, methodology version — resolves to a real
`entry_qualifications` row; every row's denormalized
`entry_qualification_state` matches the bound EQ's own `state` column
exactly). **Duplicate/conflicting-identity count: 0** (grouped by the
full 7-column composite identity, zero groups with count > 1).

### 10.7 WATCH semantics audit

WATCH total: 228. `NOT_ACTIONABLE`: 228. `ACTIONABLE`: 0. `UNKNOWN`: 0.
Reason distribution: both `UPSTREAM_DECISION_NOT_TRADE` (228/228, since
all are WATCH) and `UPSTREAM_EQ_NOT_QUALIFIED` (228/228, since all 228
bound EQs are `EXPIRED`, i.e. not `QUALIFIED`) are present together on
every row, per the engine's frozen "both upstream reasons reported
together" rule. **WATCH invariant violations: 0.**

### 10.8 TRADE semantics audit

Zero real TRADE `EntryActionability` rows exist (confirmed above and
independently by `decisions.decision_type='TRADE'` count = 0 within
the canary run). **`TRADE_EMPIRICAL_CANARY_NOT_AVAILABLE`** — not
synthesized.

### 10.9 First eligible post-activation canonical canary

Because activation provenance traces to the pre-existing
single-symbol Validate feature (2 rows, not a scheduled cycle), the
first genuine **scheduled canonical cycle** to touch `EntryActionability`
after activation is frozen as the ID-7F2 canary:

- **`run_id`:** `run-premarket-20260907T081534`
- **`cycle_id`:** `2026-09-07-premarket`
- **Session date:** `2026-09-07`. **Phase:** `PREMARKET` (a normal
  canonical cycle under the production workflow, per its own
  `config_snapshot_id='cfg-host-ops'` — the ordinary host-scheduled
  config, distinct from both `cfg-symbol-validate` and
  `cfg-full-validation`; used as the canary since it is explicitly a
  normal scheduled cycle, not because REGULAR-phase would be
  inconvenient to wait for).
- **Start/end:** both `2026-09-07T08:15:34.096216+05:30` (instantaneous
  `started_ts`/`finished_ts` timestamps, as recorded by `runs`).
- **Instrument population:** 385 total decisions this cycle (226
  WATCH, 159 NO_TRADE, 0 TRADE).

**Canary expected-vs-actual population** (exact composite identity,
not count-only): expected in-scope EA population (EQ rows this
`run_id`, bound to a WATCH/TRADE decision) = **226**. Actual persisted
EA rows this `run_id` = **226**. **Missing: 0. Unexpected/out-of-scope:
0.** **Exact-binding defects: 0. Duplicate/conflicting identities: 0.**

### 10.10 M5/VWAP/OR15, stage health, provider-call contract, currentness

All 226 canary rows resolve to `NOT_ACTIONABLE`/dual-upstream-reason
before layer-3 (M5/VWAP/OR15) evidence is ever read, per ID-7C.2's own
evaluation-order fix (WATCH-bound EQs never reach candidate/checkpoint
evidence) — so no M5/VWAP/OR15 provenance evidence exists to audit for
this canary (expected, not a defect; no violations to report).
`entry_actionability_stage`'s own source (`owner_validation.py`,
current working tree) was re-read in full for this addendum and
confirmed to still read only from `WorkflowContext`/the same-cycle
`Decision` object — zero provider/network imports or calls inside the
stage. **Stage success count (canary): 226/226. Failure count: 0.**
`runs.detail_json` for the canary carries no failure/error keys; a
direct log search for `entry_actionability` paired with
`error`/`fail`/`traceback` across the entire service log returned zero
matches. Per-stage latency is not separately persisted (unchanged from
ID-7E — no new instrumentation added here, per the read-only
constraint); overall cycle `duration_seconds` is available in
`detail_json` but stage-level breakdown is not. All 228 rows'
`state` values are confirmed to be exclusively drawn from the frozen
persisted set (`UNKNOWN`/`NOT_ACTIONABLE`/`ACTIONABLE`) — no
`CURRENT`/`STALE`/`SUPERSEDED`/`SESSION_CLOSED` value exists anywhere
in the table (those remain exclusively read-time, per
`is_currently_usable`, never persisted).

### 10.11 TRADE+QUALIFIED production evidence

Not observed (0 TRADE rows exist). `TRADE_QUALIFIED_PRODUCTION_EVIDENCE_NOT_OBSERVED`
— explicitly not an activation failure, consistent with ID-7F0/ID-7F1's
own repeated finding that the real production population has carried
zero TRADE decisions since well before EQ persistence began.

### 10.12 Activation acceptance

All of the frozen §19 acceptance conditions are met on the evidence
above **except** one: the exact HTTP/operator identity behind each
`POST /api/v1/ops/restart` call is not recoverable from available
logs (the access-log line records only the loopback client address,
not a caller identity). Per the authorization's own fallback:

**`ACTIVATION_PATH_PARTIALLY_UNPROVEN_BUT_RUNTIME_ACTIVATION_VERIFIED`**
— the `execv` mechanism itself is directly proven (§10.1), schema/table
structure is exactly the approved design (§10.4), DB integrity is
healthy with fully explained growth (§10.5), zero out-of-scope/binding/
duplicate defects exist across the complete 228-row population
(§10.6–§10.8), the 2026-09-04/09-06 gap is fully traced to a named,
pre-existing, non-batch source file rather than left as an open
question (§10.3), a genuine post-activation scheduled canonical canary
was identified and its expected-vs-actual population matches exactly
(§10.9–§10.9), and zero actionability-stage-attributable provider
calls or system/contract failures were found (§10.10). No corrective
or restart action was taken; PID 2453, the schema, and every persisted
row were left untouched throughout this investigation.

### 10.13 Updated classification

**ID-7F2 ACTIVATION + CANARY VERIFIED — READY FOR OWNER / CHIEF
ARCHITECT REVIEW.**

ID-7F2 remains open pending this review. Mode-B shadow equivalence
(ID-7F3) was not started. EMR and DarvaX were not touched. No source
code was modified in this addendum — read-only forensics and this
documentation file only.
