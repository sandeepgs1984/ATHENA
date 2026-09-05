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
