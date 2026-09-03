# ADR-014 - EMR Live Shadow Operational Architecture

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-03 |
| Accepted | 2026-09-03 |
| Deciders | sandeep (owner) |
| Scope | Explosive Move Radar (EMR) live shadow operation (EM-7) |

## 1. Status

**Accepted 2026-09-03** by Owner/Chief Architect. EM-7A (scanner
correctness hardening) is separately authorized and reported in
`docs/research/EM-7A-SCANNER-CORRECTNESS-HARDENING.md` — see that
document's own findings for one real, source-confirmed contradiction to
this ADR's original §15 atomicity assumption, surfaced during EM-7A's
implementation and reported for owner review rather than silently
resolved there. **EM-7A.1 (2026-09-03) resolved that contradiction** —
Owner Decision: make result persistence genuinely atomic
(`EmrRepository.commit_scan_result`), `PARTIAL` lifecycle state
rejected. §15 and §16 below are corrected accordingly; the correction
preserves rather than erases the original (now-superseded) claim and the
EM-7A finding that disproved it — see each section's own "EM-7A.1
correction" note. The substantive architecture is otherwise unmodified
by either finding.

## 2. Context

EM-0 through EM-6B.1 are owner-approved/closed (`docs/MILESTONES.md`).
EM-4E sealed the frozen model (FINAL_TEST, 2026-08-28); EM-5 built and
validated the deterministic live scanner (`run_scan_cycle`) against a
real 518-instrument production canary; EM-6 built a read-only
presentation/API/UI surface. None of these milestones gave EMR any way to
actually run — `EM-7-DISCOVERY.md` (2026-09-03, owner-approved/closed)
found `run_scan_cycle` has zero non-test invocation sites anywhere in the
repository: no CLI command, no scheduler, no cron entry. `db/emr.db` does
not exist in production for exactly this reason.

ADR-012 §10 and `docs/design/ATHENA-EXPLOSIVE-MOVE-RADAR-ROADMAP.md`
both define EM-7 identically: run the frozen pipeline live, in a mode
that does not affect canonical ATHENA, and measure both statistical
health and canonical performance impact (EMR-disabled vs. EMR-shadow-mode
comparison). Neither document specifies *how*. The EM-7 discovery also
found three real correctness gaps in `run_scan_cycle` (no
`FAILED`/`PARTIAL` run status, non-idempotent persistence, no
concurrency lock) that make it unsafe to run unattended today, and
confirmed the hard data-acquisition problem is already solved
(`EmrMarketDataPort` already reads only already-ingested `db/athena.db`
candles).

ATHENA-002 and this repository's own convention (ADR-012 §16, ADR-013's
own stated trigger) require an accepted ADR before a new architectural
boundary — here, a new production worker/scheduler and a new production
database-lifecycle activation — is introduced.

## 3. Decision

ATHENA will operationalize EMR for live shadow validation as a new,
fully isolated, config-gated scheduled worker owned entirely by
`athena.explosive_move`, reusing the already-existing read-only
market-data port and writing only to EMR's own `db/emr.db`. This ADR
formalizes the architecture; it does not implement it.

## 4. Scope / non-scope

**In scope:** the architectural contract for how EMR will eventually run
live, unattended, in shadow mode, without affecting canonical ATHENA.

**Explicitly not implemented by this ADR** (per owner instruction):
scanner hardening; `FAILED`/`PARTIAL` states; idempotency enforcement;
concurrency locking; the worker itself; scheduling; config-file creation;
production `db/emr.db` activation; any scan execution; any provider call.
This document is architecture only.

## 5. ADR-012 relationship

ADR-012 remains the frozen, foundational EMR isolation ADR — nothing in
it is modified, weakened, or superseded. This ADR **adds** the
operational architecture ADR-012 anticipated but did not specify (its
own §10 requires EM-7 measurements to exist; it does not say how EM-7
should run). Every isolation invariant ADR-012 established (§10 of that
document: no canonical `ScoringEngine`/`Confidence`/`Risk`/`Decision`/
`TradePlan`/eligibility-gate/DarvaX mutation; EMR-owned persistence; no
independent provider clients beyond an authorized seam) is carried
forward unchanged and re-proven for the new worker in §26.

## 6. Architecture / dependency direction

```
canonical ATHENA (db/athena.db, already-ingested candles)
        |
        | read-only, existing EmrMarketDataPort /
        | SqliteEmrMarketDataAdapter (EM-5, unmodified)
        v
isolated EMR scheduled worker  (new, athena.explosive_move-owned)
        |
        v
run_scan_cycle                 (EM-5, hardened by EM-7A)
        |
        v
isolated EmrRepository         (EM-5, unmodified)
        |
        v
db/emr.db                      (EMR-only, activated by EM-7C)
        |
        v
existing EM-6 read-only presentation / API / UI  (unmodified)
```

**Required dependency direction** (Owner Decision 5): the worker depends
on the EMR scanner, which depends on the EMR repository, which depends
on the EMR read-only market-data port. The worker **must not** import or
depend on canonical `athena.ops`/`athena.scheduling` runtime code (e.g.
`CycleWorker`, `HostDueRunner`, `CycleRunnerLock`) merely for its own
poll/lock behavior — it may *mirror* their proven shape, but the
dependency edge must never point from `explosive_move` into canonical
`ops`/`scheduling`. This preserves ADR-012's directional isolation
guarantee exactly as strictly as EMR's existing regime-source module
already does for `athena.regime` (`live/regime_source.py`: "the
dependency stays strictly one-way: this module imports FROM
`athena.regime`... nothing in `athena.regime`... imports
`athena.explosive_move`"). Some small duplication of proven
locking/polling code is accepted as the cost of this isolation.

The worker never writes to `db/athena.db`. EM-6's presentation surface
remains strictly read-only. Canonical
`Decision`/`Scoring`/`Confidence`/`Risk`/`TradePlan`/`EntryQualification`
remain completely unaware EMR exists — no code path in any of those
packages will ever import `athena.explosive_move` (re-verified in §26).

## 7. Disabled-mode semantics (`EMR_DISABLED`)

- The worker is disabled by config (§21) — the safe default.
- No scheduled EMR scans occur; `run_scan_cycle` is never invoked.
- No EMR write traffic of any kind; `db/emr.db` is not touched.
- The existing EM-6 read-only Experimental API/UI may continue running
  unmodified — it honestly shows whatever persisted reality already
  exists (absent database, or an old completed scan with its own visible
  age), exactly as it does today. Disabled EMR does not hide or alter
  this surface.
- **Disabled EMR remains operationally inert** — worker startup with
  `enabled=false` performs no filesystem/database side effect, including
  not creating `db/emr.db` (§18).

## 8. Shadow-mode semantics (`EMR_SHADOW`)

- The isolated worker is enabled by config.
- The frozen EM-4E/EM-5 methodology executes at the frozen, EM-5-validated
  checkpoint schedule (§10) against the frozen mature-history universe
  (§11) — no methodology change of any kind (§25).
- Writes occur only to isolated `db/emr.db` via `EmrRepository`.
- **No canonical decision authority, no order/trade authorization, no
  canonical ranking mutation** — identical to every prior EMR milestone's
  guarantee, unchanged.
- This is the mode ADR-012 §10's OFF-vs-shadow comparison (§27) measures
  against `EMR_DISABLED` — the toggle between the two states is
  literally "is the isolated worker process/thread running," making the
  comparison operationally clean and reversible.

## 9. Worker ownership (Owner Decision 5)

The future worker is fully owned by `athena.explosive_move` (a new
module, e.g. `explosive_move/live/worker.py` or similar — exact naming
deferred to EM-7B implementation, not frozen here). It may structurally
mirror `src/athena/ops/serve_runtime.py`'s `CycleWorker` (a background
thread polling on an interval, acquiring a flock-style lock, invoking a
tick function, releasing the lock) and DarvaX's config-gated mount
pattern, but must not import from `athena.ops`/`athena.scheduling` to do
so (§6). The worker calls `run_scan_cycle` directly, with its own
injected `EmrMarketDataPort`, `EmrRepository`, and (mandatorily — §19)
`regime_lookup`.

## 10. Checkpoint-policy decision (Owner Decision 1)

**Use the existing EM-5-validated 9-checkpoint schedule, unchanged.**
The authoritative existing definition is
`CANDIDATE_CHECKPOINTS_IST` in `src/athena/explosive_move/contracts.py`
(`09:20, 09:30, 09:45, 10:00, 10:30, 11:00, 12:00, 13:00, 14:00`, IST) —
this is also the default `checkpoints` parameter of
`run_em5_production_canary()` (`live/canary_gate.py`), i.e. the exact
schedule the already-accepted Section 14 canary validated.

**Duplication found and future ownership designated, not consolidated
here**: an identical, independently-defined tuple,
`TRACK_B_CHECKPOINT_SCHEDULE`, exists in
`src/athena/data/live_m5_provisional_settlement_diagnostic.py` — built
earlier for the EM-5 Track B live-capture diagnostic, outside the
`explosive_move` package. **Future canonical ownership point:**
`athena.explosive_move.contracts.CANDIDATE_CHECKPOINTS_IST` — it already
lives inside the EMR-owned contracts module and is already the value
`canary_gate.py` treats as authoritative. EM-7A0 does not consolidate
this duplication; a future hardening slice (EM-7A or EM-7B, at
implementation's discretion) should have the diagnostic module import
`contracts.CANDIDATE_CHECKPOINTS_IST` instead of maintaining its own
copy. The future worker must consume the canonical value, never a third
copy.

## 11. Universe-policy decision (Owner Decision 2)

**Use the existing mature-history subset, not the unfiltered full
ADR-011 universe.** The exact existing resolver is
`select_mature_history_instruments()`
(`src/athena/explosive_move/live/canary_gate.py`) — real D1
admitted-session counts strictly before `session_date`; an instrument is
"mature" iff it has `>= minimum_sessions` (`MATURE_HISTORY_MINIMUM_
SESSIONS`, currently 50) admitted daily bars before the session, applied
over instruments resolved from the base ADR-011 named universe
(`athena_core`, the same base universe Section 14's canary used) via the
existing `market_port.resolved_universe()`/`SqliteRepository.list_
resolved_universe()` mechanism. This is exactly the function and
parameterization that produced the validated **518 mature instruments,
9,324/9,324 all-required-fields-known (100.0000%), zero provider/network
calls during replay, deterministic replay** result.

**Confirmed factually distinct, per instruction**: `athena_core`
resolved (the unfiltered full universe) and the mature-history-filtered
subset (518) do **not** resolve identically in current source —
`select_mature_history_instruments()` is a real, narrowing filter over
whatever `resolved_universe()` returns; the two are different
populations. The initial EM-7 shadow universe is the mature-history
subset, not the unfiltered universe. Future expansion to the full
universe is explicitly out of scope for EM-7A0 and requires separate
evidence/owner approval (no new universe methodology is introduced here).

## 12. Data-acquisition decision

Unchanged from EM-5, re-affirmed as the frozen boundary for live shadow
operation: candles come from already-ingested ATHENA persistence
(`db/athena.db`) through the existing read-only
`EmrMarketDataPort`/`SqliteEmrMarketDataAdapter` — EMR does **not**
independently refetch historical candle data, and this ADR does not
authorize any new provider client or duplicate ingestion path. This
directly avoids overlapping with ID-7P0's own separately-discovered
provider-pacing constraints on ATHENA's canonical ingestion — EMR simply
never competes for that same pacing budget for candle data.

## 13. Provider-boundary decision

The only authorized network seam remains
`checkpoint_reference_price.collect_checkpoint_reference_prices()` — one
narrow, already-existing, batched Kite `/quote` call per checkpoint,
unchanged from EM-5. This ADR does not authorize any new provider client
or endpoint. **Failure behavior for this call (a checkpoint quote
request failing) belongs to EM-7A's run-lifecycle contract, not to this
ADR** — this document defines the boundary (one authorized seam, no
others), not its failure-handling implementation.

## 14. Run-identity decision

Preserved unchanged: `run_id` remains a deterministic SHA256 fingerprint
of `(session_date, checkpoint, universe, model_version)` — replaying
identical inputs must always compute the identical `run_id`. This ADR
does not change the identity formula.

## 15. Lifecycle decision — the primary open engineering question

**This is the decision the owner flagged as most important to settle
here, before EM-7A hardening begins.**

**Original assumption (2026-09-03, at ADR acceptance — since disproven,
kept here for the audit trail, not as current fact):** "Current
architecture (source-confirmed, EM-7 discovery): `run_scan_cycle` has
zero exception handling; `save_candidates`/`save_transitions` are each
called exactly once, after the entire per-instrument,
per-(family,threshold) evidence/scoring loop completes. This means the
current design is already structurally atomic at the persistence
boundary — either the full loop completes and one batch write happens,
or an exception anywhere aborts the function with zero candidate/
transition rows ever persisted."

**EM-7A finding (2026-09-03) that disproved it:** direct source reading
of `EmrRepository.save_candidates`/`save_transitions`/`save_scan_run`
during EM-7A's mandatory pre-implementation audit showed each was its
own independently-committed SQLite transaction (`with conn:` around each
call), and `run_scan_cycle` called all three as three separate calls at
the end of the loop — never inside one transaction. "One batch write" was
true only in the sense of "back-to-back calls with no other work between
them," not in the sense of one atomic database transaction. A crash (or
any exception) between any two of those three calls left a real, durable
**partial** result — e.g. candidates persisted with zero transitions, or
a fully-persisted result with the run's own status stuck at `RUNNING`
forever. This contradicted the assumption above and is reported in full
in `docs/research/EM-7A-SCANNER-CORRECTNESS-HARDENING.md`. Per explicit
owner instruction, EM-7A did not silently redesign the lifecycle to
work around this — it implemented only its unrelated scope (lock,
regime wiring, isolation hardening) and stopped, reporting the
contradiction for owner decision.

**EM-7A.1 owner resolution (2026-09-03) — Option 1 selected, `PARTIAL`
rejected:** rather than introduce a third lifecycle state to describe
the partial-result possibility the EM-7A finding exposed, the owner
directed that persistence itself be made genuinely atomic instead.
`EmrRepository.commit_scan_result(*, run_id, candidates, transitions,
run_update)` (`src/athena/explosive_move/store/repository.py`) is now
the single method that writes candidates, transitions, and the terminal
`COMPLETE` status together inside one SQLite transaction (one `with
conn:` block) — verifying the target run is still `RUNNING` before
writing, deleting any existing rows for that `run_id` (idempotent-retry
safety, §16), inserting the fresh result, and updating the run to
`COMPLETE`, all-or-nothing. `run_scan_cycle` (`scanner.py`) now calls
this once, in place of the three previously-separate calls. A failure
anywhere inside that transaction rolls back in full — zero new candidate
rows, zero new transition rows, the run's own row still `RUNNING` — and
the caller then writes a separate, explicit `FAILED` status via
`mark_scan_failed` (its own, deliberately separate transaction — a
failure marking the run `FAILED` must never be blocked by, or itself
block, the result transaction it is reporting on).

**Decision (unchanged by the correction above): the required
run-lifecycle contract remains `RUNNING → COMPLETE | FAILED` — a
two-terminal-outcome model. `PARTIAL` is not required and is not frozen
by this ADR.** The reasoning is now correct rather than merely assumed:
`commit_scan_result`'s atomicity makes a partial *outcome* structurally
impossible at the persistence layer (not because the old code happened
to call three things back-to-back with nothing in between, but because
the three writes are now one indivisible transaction) — a crash either
happens before that transaction commits (nothing persisted → `FAILED`)
or after it (everything persisted → `COMPLETE`). `PARTIAL` remains
available to propose later, with its own evidence, only if a future
milestone deliberately moves to incremental/streaming persistence — not
invented speculatively here.

**Required of EM-7A** (exit contract, §32): `run_scan_cycle` must catch
exceptions, write an explicit `FAILED` status (with enough detail to
diagnose what failed) instead of leaving an orphaned `RUNNING` row, and
`COMPLETE` must continue to mean exactly what it means today
(successful, fully-persisted, now genuinely atomic result). **Satisfied
by EM-7A.1** — see `docs/research/EM-7A-SCANNER-CORRECTNESS-HARDENING.md`
for the closure record.

## 16. Retry/idempotency decision

Architectural invariant (frozen here): **replay or retry of an identical
semantic EMR run identity (the same deterministic `run_id`) must never
create duplicate candidate or transition rows.** `save_scan_run()`
already satisfied this (upsert on `run_id`) at ADR acceptance;
`save_candidates()`/`save_transitions()` did not (plain inserts, no
uniqueness constraint — confirmed by the EM-7 discovery). This ADR did
not originally prescribe `ON CONFLICT` vs. a uniqueness constraint vs.
delete-then-reinsert, leaving the exact enforcement mechanism to EM-7A.

**EM-7A.1 mechanism (implemented, 2026-09-03):** two layers, matching
the owner's explicit "uniqueness is secondary to atomicity, not the
primary mechanism" guidance —

1. **Primary — delete-then-insert inside the atomic transaction.**
   `commit_scan_result` (§15) deletes any existing `emr_candidates`/
   `emr_transitions` rows for the target `run_id` before inserting the
   freshly computed result, all inside the same transaction as the
   `COMPLETE` write. A retried `FAILED` run (§ idempotency cases below)
   naturally replaces whatever partial state, if any, a prior attempt
   left — though under the atomic transaction a prior attempt leaves
   none, this also makes the operation safe if ever invoked twice for
   the same `run_id` for any other reason.
2. **Defense-in-depth — a UNIQUE index.** `idx_emr_candidates_run_identity`
   / `idx_emr_transitions_run_identity` (`schema.py`, schema v2) enforce
   `UNIQUE(run_id, instrument_id, family, threshold_percent)` — the
   natural, already-frozen per-run domain identity (one candidate/
   transition row per instrument per (family, threshold) combo per run).
   This is never the primary atomicity mechanism; it exists so an
   accidental duplicate insert is impossible even if a future change
   ever bypassed `commit_scan_result`'s own delete-then-insert step.

Three same-`run_id` lifecycle cases are handled explicitly by
`run_scan_cycle` before any provider call (§15, `scanner.py`): an
existing `COMPLETE` run is reconstructed from already-persisted state
with zero recomputation and zero second checkpoint-reference-price call;
an existing `RUNNING` run is conservatively rejected
(`EmrScanAlreadyRunningError`) rather than guessed stale; an existing
`FAILED` run is retried under the same deterministic `run_id`.

## 17. Concurrency/lock decision (Owner Decision 5, ADR-012 boundary)

**Frozen invariant: at most one EMR scan execution may own a given
checkpoint/run at a time.** The future worker requires an **EMR-owned
lock** — it must not reuse ATHENA's canonical `CycleRunnerLock`
(`artifacts/locks/cycle-runner.lock`, owned by `athena.ops`) and must not
share lock ownership with DarvaX. This ADR defines the lock boundary
(one EMR-scoped lock, exclusive per checkpoint/run) and does not
prescribe its exact OS-level implementation — `flock`-based file locking
is the established repository convention (`CycleRunnerLock`'s own
pattern) and is the natural default, but EM-7A/EM-7B may choose the
concrete mechanism.

## 18. Database-activation decision (Owner Decision 5 area, §12 of request)

Frozen sequence, explicit and non-negotiable:

- **EM-7A0 does not create `db/emr.db`.**
- **EM-7A does not require creating it** (hardening work is testable
  against `tmp_path`-style fixtures, exactly as EM-5's own tests already
  are).
- **EM-7B must remain testable without production activation** — the
  worker and scheduler can and should be fully tested against fixture
  databases; wiring the worker does not itself activate production.
- **EM-7C owns first production activation**, and must use an explicit,
  owner-controlled activation/canary process — mirroring the discipline
  already established for ID-6E.2's production schema activation
  (integrity-verified, checksummed backup, idempotency-reconfirmed
  before any real write).
- **Disabled EMR remains operationally inert**: worker startup with
  `enabled=false` must not create `db/emr.db` as a side effect of
  startup/import. No evidence in this discovery suggests any exception is
  needed to this rule, and none is granted.

## 19. Failure-isolation decision

**Frozen invariant: EMR worker/scanner failure must never fail or delay
a canonical ATHENA cycle.** A crashed EMR worker may reduce EMR's own
freshness (an old or absent scan, honestly represented by EM-6's existing
presentation layer — §20) but must not: terminate ATHENA's canonical
cycle worker; mutate any canonical `runs`/`decisions`/
`entry_qualifications` row; block any canonical lock (§17 — the EMR lock
is exclusively EMR's own, never shared); corrupt `db/athena.db` (the
worker never opens a write connection to it, §6); or prevent dashboard
serving (the EM-6 API/UI already handles an absent/stale EMR database
gracefully, per its own existing empty-state contract). **Recovery
expectation**: an EM-7A `FAILED` run (§15) requires no automatic
recovery beyond the next naturally scheduled checkpoint attempting a
fresh run under a new `run_id` (a new checkpoint/session-date pair) —
no retry-storm logic is required or proposed here.

## 20. Regime-source decision — already ruled, not reopened here

**Decision: explicitly wire the existing canonical regime lookup —
`build_canonical_regime_lookup()`
(`src/athena/explosive_move/live/regime_source.py`).** This is not a new
decision this ADR is making; it is a **pre-existing Owner/Chief Architect
ruling from 2026-08-28**, recorded verbatim in that module's own
docstring: *"after the production canary found `run_scan_cycle`'s
`regime_lookup` permanently unwired -- holding all-22-fields-known
completeness at a hard 0%."* `regime_source.py` was built specifically to
resolve this, reading real NIFTY 50/India VIX candles through the same
read-only `EmrMarketDataPort` (never a second provider path), wrapping
the canonical, unmodified `RegimeEngine` via
`regime_replay.reconstruct_session_regime` — the same point-in-time-safe
function EM-1c's own historical regime reconstruction already used. The
already-accepted Section 14 production canary
(`canary_gate.py:run_em5_production_canary`) already wires this function
explicitly (`regime_lookup = build_canonical_regime_lookup(...)`) —
**this ADR requires the future worker to do the same, matching the
already-validated canary configuration exactly.** `run_scan_cycle`'s own
default (`regime_lookup or (lambda _d: None)`) exists only for tests that
don't care about regime features; the future worker must never rely on
that default, since doing so would silently diverge from the validated
research/canary pipeline (EM-4C/EM-4E's own TOUCH_10 regime-stability
results — 105-161x trend, 77-173x volatility, 50-190x gap lift — depend
on real, non-`UNKNOWN` regime features). No new owner question is raised
here; source evidence settles it.

## 21. Provisionality/finality decision

EMR's own existing domain semantics are preserved, not replaced with
ADR-013 vocabulary. `data_freshness` (per-candidate candle-staleness,
computed by the scanner from a caller-supplied `max_staleness_minutes`)
remains distinct from EM-6's viewer-relative `scan_age` (a pure elapsed-
time presentation fact, no threshold). **This ADR does not add a new
explicit provenance/finality field** — current persisted fields
(`model_version`, `run_id`, `checkpoint`, `session_date`, `data_
freshness`) can truthfully represent live-shadow evidence as-is. If a
future milestone's real operational evidence shows this is insufficient,
that would be raised as its own evidence-based decision then — not
anticipated speculatively here.

## 22. Observability decision

Minimum required operational record for EM-7 validation (reusing
existing fields wherever already available, not inventing a new
platform): run identity (`run_id`), session date, checkpoint, start/end
timestamps, terminal status (§15), universe/instrument count, coverage,
candidate count, TOUCH-10 count, scanner duration, checkpoint
reference-price/provider failures, persistence failures, data-failure
(missing-instrument) count. Most of these already exist on
`emr_scan_runs`/are derivable from `emr_candidates`; the genuinely new
fields are the terminal-status distinction (§15) and explicit failure
counts. No new observability platform is proposed — this reuses the same
minimal, additive philosophy ID-7P0's own orthogonal timing
instrumentation already established for the canonical side.

## 23. Configuration decision (Owner Decision 4)

**Semantics only — no file is created by this ADR.** The future EMR
configuration must support a simple explicit gate, mirroring DarvaX's
own proven pattern exactly: an `enabled` key (matching DarvaX's
`_ACTIVATION_KEY = "enabled"`, `src/athena/api/darvax_mount.py`), where a
**missing config file or `enabled: false` means disabled** — disabled is
the safe default until owner-authorized activation, exactly as DarvaX's
own doc states: "a missing file means 'not requested'." Conceptually,
future configuration should also carry (by reference, not by
duplicating values): which checkpoint policy to use (pointing at
`contracts.CANDIDATE_CHECKPOINTS_IST`, §10 — never a third hardcoded
copy); which universe policy to use (the mature-history filter + its
parameters, §11); which frozen `model_version` the worker should load
(already a `ScanCycleConfig` field); and the database path (already
resolvable via `ATHENA_EMR_DB_PATH`/the existing default-path resolver —
configuration should document this, not duplicate it as a new key unless
implementation finds a real reason to). **Configuration selects
operational behavior only — it must never make a frozen model parameter,
calibration coefficient, or methodology threshold mutable.** No config
file is created in this milestone.

## 24. Presentation/API-boundary decision

EM-6's existing read-only API/UI remains the entire presentation surface
— unchanged by this ADR. The worker's only relationship to it is
creating new persisted reality for EM-6's already-built read path to
honestly display. This ADR does not authorize: new top-level navigation;
any mutation endpoint (`POST /emr/run`, `POST /emr/retry`, or
equivalent — explicitly rejected, §29); scanner-control buttons of any
kind; or any trade-authorizing language. The "Experimental" framing
(amber badge, explicit disclaimer, "not a trade recommendation") remains
mandatory and unchanged.

## 25. Statistical shadow-validation boundary

EM-7D (not this milestone) will track precision, lift, calibration, MFE,
MAE, misses, false positives, regime drift, data failures, and latency
against the frozen EM-4E/EM-5 pipeline running on genuinely new live
data. This is **evaluation of the already-frozen model against new
forward evidence** — it is explicitly **not** authorization to refit,
recalibrate, change thresholds, reopen FINAL_TEST, or tune anything to
shadow observations (§27). Any evidence of model deterioration surfaced
during shadow operation must be reported to Owner/Chief Architect and
handled as a separately authorized research decision — never acted on
automatically.

## 26. Canonical performance-isolation comparison boundary

EM-7D must eventually compare `EMR_DISABLED` (§7) against `EMR_SHADOW`
(§8) for exactly ADR-012 §10's required metrics: dashboard load time,
symbol-validation latency, canonical cycle timing, database query
latency and volume, CPU, memory, and EMR scanner-cycle duration. This
ADR defines this as a **future acceptance boundary for EM-7D** — it does
not invent numeric regression thresholds here. "Material regression"
remains an owner-reviewed evidence judgment, per ADR-012 §10's own
wording ("blocks promotion until it is explained, bounded, and
owner-approved"), unless a future milestone's own research justifies
specific numeric thresholds.

## 27. FINAL_TEST sealing

**Frozen, restated explicitly**: EM-4E's FINAL_TEST partition remains
sealed permanently. EM-7 (in any sub-milestone) must never reread it for
comparison, tuning, calibration, or model selection. Live shadow data is
new forward evidence, categorically separate from FINAL_TEST — comparing
shadow results against FINAL_TEST's own historical figures (as
*context*, the way EM-5's Track B already compared its own replay
figures against VALIDATION's, never by re-reading the sealed partition
itself) remains permitted; re-opening the sealed data does not.

## 28. Security/control decision (Owner Decision — no mutation endpoint)

No HTTP mutation endpoint is authorized for operational control.
Operational control occurs exclusively through the config enable/disable
gate (§23) and process/service lifecycle (start/stop the isolated
worker) — or, if independently justified by a future milestone, a CLI
command (matching how ATHENA's own canonical cycles are already
controlled via `athena run-due`/`serve --with-cycles`, never a dashboard
button). This ADR explicitly rejects `POST /emr/run`, `POST /emr/retry`,
or any equivalent mutation route. EM-6's presentation API remains
strictly READ-only, unchanged.

## 29. Automated isolation-proof requirement

The EM-7 discovery found a real scope gap in the existing automated
isolation test (`tests/explosive_move/test_em5_isolation.py`): its
`_FORBIDDEN_CANONICAL_IMPORTS` list checks
`decision`/`risk`/`portfolio`/`orders`/`execution`/`orchestration` but
**not** `scoring`/`confidence`/`intraday`/`darvax` in the
`explosive_move → canonical` direction, and does not check
`SqliteRepository` at all (two intentional, narrow, structurally
read-only imports of it already exist and are not currently policed by
any test). **This ADR requires that a future hardening slice (EM-7A or
EM-7B, implementation's choice) extend `test_em5_isolation.py`'s
forbidden-import list to cover the full set** —
`decision`/`scoring`/`confidence`/`risk`/`portfolio`/`intraday`/`darvax`
— and add an explicit, narrow allowance for the two already-known,
already-read-only `SqliteRepository` import sites
(`live/market_data_port.py`, `em1r2_materialize.py`) rather than leaving
that dependency invisible to automated proof. This ADR does not implement
the test extension itself.

## 30. EM-7A exit contract

Scanner correctness hardened:

- `run_scan_cycle` catches exceptions and writes an explicit `FAILED`
  status (§15) — no orphaned `RUNNING` rows.
- Candidate/transition persistence is safely idempotent under
  replay/retry of an identical `run_id` (§16).
- An EMR-owned concurrency lock exists and is exercised by tests (§17).
- `regime_lookup` is coherent with the frozen, already-validated research
  pipeline — i.e. `build_canonical_regime_lookup` is used, never the
  `lambda _d: None` default, in any non-test invocation (§20).
- The checkpoint-schedule duplication (§10) is resolved to the single
  canonical ownership point, OR explicitly deferred with a documented
  reason if not resolved in this slice.
- The isolation-test extension (§29) is implemented and passing.
- Tests prove no ADR-012 violation was introduced by any of the above.

## 31. EM-7B exit contract

Scheduling/invocation implemented:

- An independent EMR worker exists, owned entirely by
  `athena.explosive_move` (§9, §6 — no canonical `ops`/`scheduling`
  import).
- The config enable/disable gate (§23) exists and defaults to disabled.
- The worker invokes `run_scan_cycle` at the frozen checkpoint schedule
  (§10) against the frozen mature-history universe (§11).
- No production `db/emr.db` activation has occurred yet (§18) — the
  worker and scheduler are fully testable against fixtures.
- Scheduler tests are deterministic (no reliance on real wall-clock
  timing for correctness, mirroring ID-7P0's own injectable-clock
  discipline).

## 32. EM-7C exit contract

Production activation:

- Controlled creation/initialization of `db/emr.db` via an explicit,
  owner-approved activation procedure (mirroring ID-6E.2's discipline —
  integrity-verified, checksummed backup, idempotency-reconfirmed).
- A schema/integrity audit of the newly-activated database.
- One genuine scheduled canary run against real production data.
- Zero canonical regression or mutation observed (re-confirming §19's
  failure-isolation invariant held in practice, not just by design).

## 33. EM-7D exit contract

Shadow validation:

- Real live data accumulated over a naturally-scheduled shadow operation
  period (no owner-imposed fixed day-count/sample-count gate invented
  here — see §35).
- Statistical shadow-health reporting per §25.
- ADR-012 §10's OFF-vs-shadow canonical performance comparison per §26,
  with a classification/recommendation for Owner/Chief Architect review.

## 34. EM-7E exit contract

Unattended validation:

- Operational reliability evidence (no orphaned runs, no duplicate rows,
  no canonical incidents) accumulated over the shadow period.
- Owner/Chief Architect review of the complete EM-7 evidence chain
  (EM-7A through EM-7D).
- A recommendation handed to EM-8 — never a self-executed integration
  decision.

## 35. EM-8 boundary

Unchanged from the EM-7 discovery's own finding: EM-8 decides among
remain-research-only, continue-shadow, retire, or start a separately
authorized canonical-integration ADR. **EM-7, in every sub-milestone
defined here, must never perform canonical integration of any kind** —
that decision, and any resulting architecture, belongs exclusively to
EM-8 and its own future ADR.

## Alternatives considered

**Attach EMR's scan as a stage inside ATHENA's canonical scheduled
cycle** (`OwnerValidationPipeline`/`DryRunCycleOrchestrator`), writing
only isolated EMR artifacts. **Rejected** — this would inject
`run_scan_cycle`'s pre-hardening reliability gaps directly into canonical
cycle execution (an unhandled EMR exception could interrupt canonical
Decision/EntryQualification processing for that cycle), and would make
the ADR-012 §10 EMR-disabled-vs-shadow-mode comparison structurally
unmeasurable (there would be no "EMR off" state distinct from "canonical
cycle off"). It also blurs the isolated-satellite pattern ADR-012/
ADR-010 both already established, even though database writes would
remain isolated either way.

**Reuse/extend ATHENA's canonical `CycleWorker` directly** (import and
subclass/extend it from `explosive_move/`). **Rejected** per Owner
Decision 5 — this would create a real, new dependency edge from EMR into
canonical `athena.ops`, which ADR-012's directional isolation guarantee
does not currently have to defend against and should not be made to.
Mirroring the pattern's shape (small, duplicated locking/polling code) is
accepted as strictly preferable.

**Independent process/schedule consuming already-persisted canonical
data via a separate, new read mechanism.** Found, on inspection, to
collapse into this ADR's own recommended architecture — the read-only
port already exists (§12) and already does exactly this; there is no
materially different "Option C" once the actual source state is
accounted for.

## Consequences

**Becomes possible:** EM-7A/B/C/D can each proceed as small, independently
reviewable slices against a settled architectural contract, rather than
each having to re-derive isolation/lifecycle/concurrency/regime
decisions from scratch. The lifecycle decision (§15) in particular
unblocks EM-7A's scope immediately, per the owner's own stated priority.

**Becomes harder / accepted debt:** some small duplication of proven
locking/polling code (worker vs. `CycleWorker`) is accepted rather than
sharing an implementation, in exchange for keeping ADR-012's directional
isolation guarantee simple and unambiguous. The checkpoint-schedule
duplication (§10) and the isolation-test scope gap (§29) are identified
but not fixed here — both must be revisited no later than EM-7A/EM-7B.

**Must be revisited:** the `PARTIAL` lifecycle question (§15) if EM-7A
ever needs incremental/streaming persistence for other reasons; the
universe-expansion question (§11) if EM-7D's results motivate scoring the
full ADR-011 universe; the config-key shape (§23) at EM-7B implementation
time, once real requirements are concrete rather than conceptual.

## Risks

- **Proceeding to EM-7B before EM-7A's hardening lands** would schedule a
  known-unsafe scanner — explicitly sequenced against by Owner Decision 3.
- **A future contributor reusing `CycleWorker` directly** "to save time"
  would silently reintroduce the exact coupling Owner Decision 5 rejects
  — flagged here so a future code review has this ADR to cite.
- **The isolation-test scope gap (§29) going unfixed** would leave a real
  automated-proof blind spot for any future change to
  `explosive_move/`'s imports.
- **Checkpoint/universe duplication (§10-11) persisting past EM-7B**
  would mean the future worker still risks drifting from the
  canonical values if a maintainer edits the wrong copy.

## Open owner decisions

None remain open from this ADR's own scope — all five frozen owner
decisions (checkpoint cadence, universe, hardening sequencing, config
gate, worker isolation) were resolved by the owner's own EM-7A0
authorization message and are recorded as decided throughout this
document. The regime-lookup question (§20), which the EM-7 discovery
flagged as a possible open question, was resolved from source evidence
(an already-existing 2026-08-28 owner ruling) and required no new
question. No further owner decision is needed to accept or reject this
ADR as drafted.
