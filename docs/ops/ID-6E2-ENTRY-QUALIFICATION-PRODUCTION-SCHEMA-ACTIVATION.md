# ID-6E.2 — Entry Qualification Production Schema Activation & Shadow Canary

**Date:** 2026-09-03. **Status:** Activation complete; shadow accumulation started.
**Scope:** Operational activation only — no methodology, engine, workflow,
repository, or schema code change. See `docs/research/ID-6E-ENTRY-QUALIFICATION-REPLAY-SHADOW-VALIDATION.md`
for the methodology validation this activation unblocks.

## 1. Objective

Safely activate the already-owner-approved Entry Qualification persistence
schema (`entry_qualifications`, ID-6C, SCHEMA_VERSION 17) in real
`db/athena.db`, and verify the already-wired ID-6D `OwnerValidationPipeline`
stage can accumulate genuine shadow observations during normal runtime.

## 2. Preflight (first read-only query against production)

Run at 2026-09-03T08:10:55 IST, against the live, already-running
`athena serve --with-cycles --cycle-interval 60.0` process (started
Tuesday, holding its own connection to `db/athena.db`):

| Fact | Value |
|---|---|
| schema_version | **17** |
| entry_qualifications present | **True** |
| table count | 28 |
| index count | 56 |
| integrity_check | ok |
| foreign_key_check | 0 violations |
| decisions row count | 214,733 |
| latest decision ts | 2026-09-02T15:45:01.314987+05:30 |

**Finding:** the production schema had *already* reached SCHEMA_VERSION 17
— including the `entry_qualifications` table — before this milestone's
first query. Root cause: `_open_repo()` (`src/athena/cli.py:66-70`) and the
FastAPI dependency (`src/athena/api/dependencies.py:129,185`) both call
`SqliteRepository.initialize()` unconditionally on every repo open, and
`initialize()` is idempotent/additive (`CREATE TABLE IF NOT EXISTS` +
guarded `ALTER TABLE ADD COLUMN` migrations only — see
`src/athena/data/store/repository.py:205-228`). The live server process
(or an API request it served) had already run this canonical path — the
same one this milestone would otherwise have triggered explicitly — since
this session's earlier ID-6E audit (which found the table absent). No
separate migration command was needed, issued, or invented; the table
existed with **0 rows** at this preflight, confirming schema activation
had occurred but no shadow canary yet had.

## 3. Backup (before any further mutation)

Since migration had already occurred, a genuine "pre-migration" backup
was no longer possible to take retroactively (and reverting the additive
schema change to fabricate one would itself be a destructive, unnecessary
regression the owner's protocol does not ask for). Instead, a full
integrity-verified safety snapshot was taken immediately, before the next
scheduled cycle, using the same manual `sqlite3.Connection.backup()` /
atomic-replace / checksummed-sidecar pattern established by the real
ID-5A production write (`IMPLEMENTATION_SUMMARY.md`'s ID-5A entry) —
never the gated `athena.data.store.backup.create_backup()` helper, whose
`verify_integrity().ok` precondition require would have refused this
specific pre-activation-adjacent state.

- **Backup path:** `db/backups/athena-pre-id6e2-shadow-canary-20260903T024201Z.db`
- **Size:** 4,767,694,848 bytes
- **SHA-256:** `42c1ecb267d6652389ed59b05cefb690e66d827b4bf572faa3aac1773ff8beaa`
- **integrity_check:** ok — **foreign_key_check:** 0 violations
- **schema_version:** 17
- **record_counts (backup):** instruments 2,204; candles 2,811,654; quotes
  291,398; market_snapshots 2,024; corporate_actions 2,009;
  quarantine_records 355; runs 1,840; decisions 214,733; decision_traces
  214,733; decision_journal 1; owner_positions 3; owner_candidates 528;
  saved_symbols 30; **entry_qualifications 0**; ops_meta 1.
- **Backup duration:** 6.92s. Source connection opened read-only
  (`mode=ro`); the production DB's own write connection (held by the live
  server) was never touched by the backup step.

This is the recovery point if anything about today's genuine cycle needed
to be rolled back. Sidecar: `<backup>.meta.json`.

## 4. Structural verification (post-activation, pre-canary)

Compared production's `sqlite_master` against a freshly-initialized
temp-DB reference schema (`SqliteRepository(tmp).initialize()`):

- Tables: **28 == 28**, identical sets (no drift).
- Indexes: **56 == 56**, identical sets.
- Triggers / views: none in either (`set() == set()`).
- `entry_qualifications` structure: 16 columns, exact column order/types
  matching `schema.py`'s DDL; composite PRIMARY KEY
  `(instrument_id, session_date, as_of, decision_id, methodology_version)`;
  FK `decision_id -> decisions(decision_id)`; exactly one explicit
  secondary index `idx_entry_qualifications_decision(decision_id, as_of DESC)`
  plus the implicit PK index — no unexpected index/trigger/view.

No ad-hoc `CREATE TABLE` SQL was run anywhere in this milestone — every
verification above is a read-only comparison against the same
`ddl_statements()`/`SqliteRepository.initialize()` the rest of the codebase
already uses and tests.

## 5. Migration idempotency proof

`SqliteRepository('db/athena.db').initialize()` was called explicitly a
second time (a fresh, briefly-opened connection, closed immediately after)
at 2026-09-03T08:13:07 IST:

- `record_counts()` before == after (byte-for-byte dict equality).
- `sqlite_master` table set and index set before == after.
- `verify_integrity()` before: `ok=True, integrity_check=ok, foreign_key_violations=0, schema_version_ok=True`.
- `verify_integrity()` after: identical.

Structurally a true no-op, exactly as ID-6C/ID-6D's own design intended —
and exactly what the live server's `_open_repo()` already does on every
call, continuously, without incident.

## 6. Shadow canary — normal runtime path, not fabricated

No SQL was inserted manually and `save_entry_qualification()` was never
called directly by this milestone. The already-running, already-scheduled
live server (`config/scheduling.json`: `premarket.run_at = "08:15"`)
fired its own PREMARKET cycle at **08:15:29 IST** — `runs` row
`run-premarket-20260903T081529` — entirely on its own schedule, with zero
triggering action from this milestone. This milestone only observed it,
read-only, via periodic polling of `entry_qualifications`' row count and
the `runs` table.

- Real Kite-backed ingestion/scoring/decision/entry_qualification chain
  ran end-to-end for the full owner-candidate universe (~528 instruments).
- The cycle took several minutes of genuine wall-clock time (rate-limited
  provider calls) before the `entry_qualification` `WorkflowStage` began
  persisting — row count observed rising from 0 to 48 to 165 across
  successive polls between 08:22 and 08:25 IST, then settling at **165**.
- `runs` row status: `COMPLETED`.

## 7. First-row / full-population coherence audit (read-only)

Across **all 165** genuine rows (not a sample):

| Check | Result |
|---|---:|
| Decision-binding mismatches (instrument_id/decision_type/run_id/cycle_id vs. bound Decision) | **0** |
| Orphaned `decision_id` (no matching Decision row) | **0** |
| `session_date` incoherent with `as_of`'s local calendar date | **0** |
| Naive (non-timezone-aware) `as_of` | **0** |
| Naive (non-timezone-aware) `persisted_at` | **0** |
| Rows with unexpected `reason_codes` for their `state` | **0** |
| `methodology_version` != `entry-qualification-v0` | **0** |
| `DISQUALIFIED_FOR_SESSION` | **0** |
| `confirmation` != `NOT_EVALUATED` | **0** |
| Duplicate logical identity | **0** |

## 8. Why every row is EXPIRED / UNKNOWN_PROVENANCE — verified as correct, not a defect

All 165 observations: `decision_type=WATCH`, `state=EXPIRED`,
`reason_codes=["SESSION_EXPIRED"]`, `evidence_finality=UNKNOWN_PROVENANCE`,
`confirmation=NOT_EVALUATED`.

Audited (read-only, no code change) `classify_session_phase` in
`src/athena/session/engine.py:150-171`:
```
if local_time < sessions.preopen_start:
    return SessionPhase.CLOSED
```
`config/market.nse.json`: `preopen_start = "09:00"`. The PREMARKET cycle's
`as_of` was **08:15:29 IST** — before `preopen_start`, hence
`SessionPhase.CLOSED` by design (NSE's own pre-open auction window is
09:00–09:08; ATHENA's "PREMARKET" operational cadence label is a distinct
concept from NSE's session-phase pre-open window, and 08:15 falls in
neither NSE's PRE_OPEN nor REGULAR window — it is genuinely CLOSED
relative to the calendar). Per the frozen `EntryQualificationEngine` state
precedence (ID-6B.2): `SessionPhase.CLOSED -> EXPIRED`. Per the frozen
`resolve_evidence_finality` (ID-6D): finality is `LIVE_M5_PROVISIONAL`
only when the engine's own REGULAR-phase eligibility gate is met;
otherwise `UNKNOWN_PROVENANCE`. Both are **exactly the expected,
correct output** for a CLOSED-phase evaluation — not a defect, and no
frozen code was touched to reach this conclusion.

## 9. Persistence-latency (genuine, not fabricated)

`persisted_at - as_of` across all 165 rows: median 550.77s, p90 552.58s,
p95 552.82s, max 553.12s, 0 negative-latency rows. This reflects the real
wall-clock duration of the sequential, per-instrument PREMARKET cycle
between `as_of` capture (at cycle start) and each instrument's own
`entry_qualification` stage actually executing — genuine evidence of the
`as_of`/`persisted_at` separation ID-6D.1 built, observed for the first
time in production. No pass/fail threshold is asserted.

## 10. Shadow observation count (full audit, via the unmodified ID-6E `run_shadow_audit`)

- status: `SHADOW_OBSERVATIONS_AVAILABLE`
- observation_count: 165 — distinct_sessions: 1 — distinct_instruments: 165
- decision_type_counts: `{WATCH: 165}` — state_counts: `{EXPIRED: 165}`
- finality_counts: `{UNKNOWN_PROVENANCE: 165}` — confirmation_counts: `{NOT_EVALUATED: 165}`
- methodology_version_counts: `{entry-qualification-v0: 165}`
- integrity: all 0 (duplicates, naive timestamps, DISQUALIFIED, CONFIRMED_BY_POLICY, non-NOT_EVALUATED)

## 11. Post-canary production facts

- schema_version: 17 (unchanged)
- integrity_check: ok — foreign_key_check: 0 violations
- size: 4,774,805,504 bytes (grew from genuine cycle writes — candles/
  decisions/entry_qualifications — not corruption; verified via schema
  diff + integrity + FK checks per the owner's own checksum-semantics
  guidance, not by checksum alone)
- checksum legitimately changed (expected, since real writes occurred)

## 12. Evidence-strength interpretation

165 clean, fully-coherent rows exist, proving the runtime persistence
path (`OwnerValidationPipeline` -> `entry_qualification` stage ->
`save_entry_qualification()`) is **operationally functioning** against
production for the first time. But every row shares the same `as_of`
(one moment), the same `state` (EXPIRED), the same `evidence_finality`
(UNKNOWN_PROVENANCE), and the same `decision_type` (WATCH) — a
CLOSED-session artifact of running before NSE's calendar even reaches
PRE_OPEN. This is **not** yet sufficient to characterize the frozen v0
formula's behavior in production (no REGULAR-phase, QUALIFIED/NOT_YET/
UNKNOWN, or TRADE-type observation exists yet). Runtime persistence is
proven; behavioral shadow characterization is not yet supported by this
evidence.

## 13. Production safety checklist

- Backup created: **YES**
- Migration used canonical repository path: **YES** (already-happened via
  `_open_repo()`/API-dependency `repo.initialize()`; explicitly re-run
  once for an idempotency proof)
- Ad-hoc SQL schema mutation: **NO**
- Provider data manually fabricated: **NO**
- Synthetic Decision inserted: **NO**
- Research result written into production: **NO**
- Real production rows manually edited: **NO**
- Shadow canary produced via the normal runtime path (not a manual
  `save_entry_qualification()` call, not raw SQL): **YES**

## 14. Classification

**ID-6E.2 ACTIVATION COMPLETE — SHADOW ACCUMULATION STARTED.**
